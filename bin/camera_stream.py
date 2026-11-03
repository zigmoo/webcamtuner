"""Private latest-frame IPC and a bounded user-session PipeWire publisher."""
import collections
import fcntl
import json
import os
from pathlib import Path
import socket
import select
import re
import struct
import threading
import time

NODE = 'webcamtuner.camera'
UNIT = 'webcamtuner-output.service'
MAX_COMMAND = 16384


def runtime_directory():
    base = Path(os.environ.get('WEBCAMTUNER_RUNTIME_ROOT') or os.environ.get('XDG_RUNTIME_DIR', ''))
    if not base.is_absolute() or not base.is_dir() or base.stat().st_uid != os.getuid():
        raise RuntimeError('A private user-session runtime directory is required.')
    directory = base / 'webcamtuner'
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink() or directory.stat().st_uid != os.getuid():
        raise RuntimeError('WebcamTuner runtime directory is not owned by this user.')
    directory.chmod(0o700)
    return directory


def connect():
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.settimeout(3)
    try:
        connection.connect(str(runtime_directory() / 'camera.sock'))
        return connection
    except BaseException:
        connection.close()
        raise


def command(value):
    data = json.dumps(value, separators=(',', ':')).encode() + b'\n'
    if len(data) > MAX_COMMAND:
        raise ValueError('Camera command exceeds its size limit.')
    with connect() as connection:
        connection.sendall(data)
        with connection.makefile('rb') as incoming:
            line = incoming.readline(MAX_COMMAND + 1)
            if not line or len(line) > MAX_COMMAND:
                raise RuntimeError('Camera service did not return a bounded response.')
            result = json.loads(line)
            if result.get('error'):
                raise RuntimeError(result['error'])
            return result


class ControlServer:
    def __init__(self, receive, stop):
        directory = runtime_directory()
        self.lock = (directory / 'camera.lock').open('a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self.lock.close()
            raise
        self.path = directory / 'camera.sock'
        self.path.unlink(missing_ok=True)
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(str(self.path))
        self.path.chmod(0o600)
        self.socket.listen(8)
        self.socket.settimeout(.5)
        self.receive, self.stop = receive, stop
        self.condition = threading.Condition()
        self.latest = None
        self.metadata = {'state': 'starting', 'published': False, 'processed': True, 'node': NODE}
        self.label = {}
        self.events = collections.deque(maxlen=32)
        self.sequence = 0
        self.closed = False
        self.clients = set()
        threading.Thread(target=self.accept, daemon=True).start()

    def emit(self, value):
        with self.condition:
            self.sequence += 1
            if 'frame' in value:
                for key in ('labelBitmap', 'labelKey', 'labelWidth', 'labelHeight'):
                    if key in value:
                        self.label[key] = value[key]
                self.latest = dict(value, **{k: v for k, v in self.label.items() if k not in value})
                self.metadata = {k: v for k, v in value.items() if k not in ('frame', 'sourceFrame', 'labelBitmap', 'labelKey')}
                self.metadata.update(state='running', published=True, processed=True, node=NODE, lastFrame=time.monotonic())
            else:
                self.events.append((self.sequence, value))
                if value.get('error'):
                    self.metadata['error'] = value['error']
            self.condition.notify_all()

    def status(self):
        with self.condition:
            result = dict(self.metadata)
        if result.get('lastFrame') and time.monotonic() - result['lastFrame'] > 3:
            result.update(state='stalled', published=False)
        return result

    def accept(self):
        while not self.closed:
            try:
                connection, _ = self.socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            pid, uid, gid = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            with self.condition:
                if uid != os.getuid() or len(self.clients) >= 8:
                    connection.close()
                    continue
                self.clients.add(connection)
            threading.Thread(target=self.client, args=(connection,), daemon=True).start()

    def client(self, connection):
        try:
            subscribed = False
            connection.settimeout(3)
            with connection.makefile('rb') as incoming:
                while not self.closed:
                    line = incoming.readline(MAX_COMMAND + 1)
                    if not line:
                        break
                    if len(line) > MAX_COMMAND:
                        raise ValueError('Camera command exceeds its size limit.')
                    value = json.loads(line)
                    operation = value.get('operation')
                    if operation == 'subscribe':
                        if subscribed:
                            raise ValueError('This connection is already subscribed.')
                        subscribed = True
                        # A separate client reader can still send snapshot commands.
                        threading.Thread(target=self.send_frames, args=(connection,), daemon=True).start()
                        connection.settimeout(None)
                        continue
                    if operation == 'status':
                        result = self.status()
                    elif operation == 'stop':
                        result = {'stopping': True}
                    else:
                        self.receive(value)
                        if operation == 'snapshot':
                            continue
                        result = {'accepted': True, 'configurationRevision': value.get('configurationRevision', 0)}
                    connection.sendall(json.dumps(result).encode() + b'\n')
                    if operation == 'stop':
                        self.stop()
                    break
        except (OSError, ValueError, RuntimeError, TypeError, AttributeError) as error:
            try:
                connection.sendall(json.dumps({'error': str(error)[:500]}).encode() + b'\n')
            except OSError:
                pass
        finally:
            with self.condition:
                self.clients.discard(connection)
            connection.close()

    def send_frames(self, connection):
        last_frame, last_event = None, 0
        try:
            while not self.closed:
                with self.condition:
                    self.condition.wait_for(lambda: self.closed or self.latest is not last_frame or (self.events and self.events[-1][0] > last_event), timeout=1)
                    if self.closed:
                        break
                    frame = self.latest
                    events = [(n, value) for n, value in self.events if n > last_event]
                for n, value in events:
                    self.send_bounded(connection, value)
                    last_event = n
                if frame is not None and frame is not last_frame:
                    self.send_bounded(connection, frame)
                    last_frame = frame
        except OSError:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def send_bounded(self, connection, value):
        payload = memoryview(json.dumps(value, separators=(',', ':')).encode() + b'\n')
        deadline = time.monotonic() + 2
        while payload and not self.closed:
            if time.monotonic() >= deadline:
                raise TimeoutError('Preview client stopped reading frames.')
            if not select.select([], [connection], [], .1)[1]:
                continue
            try:
                written = connection.send(payload[:65536], socket.MSG_DONTWAIT)
                if written == 0:
                    raise ConnectionError('Preview client disconnected.')
                payload = payload[written:]
            except BlockingIOError:
                continue

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()
            for connection in self.clients:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        self.socket.close()
        self.path.unlink(missing_ok=True)
        self.lock.close()


class Publisher:
    def __init__(self, width=1280, height=720, node=NODE):
        if not re.fullmatch(r'[a-zA-Z0-9._-]{1,80}', node):
            raise ValueError('Invalid camera node name.')
        import gi
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        self.Gst = Gst
        self.width, self.height = width, height
        Gst.init(None)
        self.pipeline = Gst.parse_launch(
            f'appsrc name=frames is-live=true format=time do-timestamp=true block=false max-buffers=1 max-bytes=0 max-time=0 leaky-type=downstream '
            f'caps=video/x-raw,format=BGR,width={width},height={height},framerate=30/1 ! '
            'videoconvert ! video/x-raw,format=YUY2 ! '
            'queue max-size-buffers=1 max-size-bytes=0 max-size-time=0 leaky=downstream ! '
            'pipewiresink mode=provide sync=false use-bufferpool=false client-name=WebcamTuner '
            f'stream-properties="props,node.name={node},node.description=WebcamTuner,media.class=Video/Source,media.role=Camera"')
        self.pipeline.use_clock(Gst.SystemClock.obtain())
        self.source = self.pipeline.get_by_name('frames')
        if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            self.close()
            raise RuntimeError('Could not publish the user-session camera.')

    def push(self, frame):
        if frame.shape[:2] != (self.height, self.width):
            raise ValueError('Camera publisher received an unexpected frame size.')
        error = self.pipeline.get_bus().pop_filtered(self.Gst.MessageType.ERROR)
        if error:
            raise RuntimeError(str(error.parse_error()[0]))
        data = frame.tobytes()
        buffer = self.Gst.Buffer.new_allocate(None, len(data), None)
        buffer.fill(0, data)
        buffer.duration = self.Gst.SECOND // 30
        result = self.source.emit('push-buffer', buffer)
        if result not in (self.Gst.FlowReturn.OK, self.Gst.FlowReturn.FLUSHING):
            raise RuntimeError('Camera publisher stopped accepting frames: ' + str(result))

    def close(self):
        self.pipeline.set_state(self.Gst.State.NULL)
