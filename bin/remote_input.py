"""Video-only SSH source using webcam_tool's public stream-plan contract."""
import collections
import json
import os
import re
import select
import signal
import subprocess
import threading
import time
from urllib.parse import urlparse, parse_qs


def source_options(camera):
    url = urlparse(camera)
    if url.scheme != 'sshcam' or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}', url.netloc):
        raise ValueError('Choose a remote computer and camera.')
    query = parse_qs(url.query, strict_parsing=True)
    if url.path not in ('', '/') or url.fragment or set(query) - {'camera', 'size', 'fps', 'format'}:
        raise ValueError('Invalid remote camera source.')
    if any(len(value) != 1 for value in query.values()) or not query.get('camera'):
        raise ValueError('Choose one remote camera.')
    args = ['stream-plan', url.netloc, '--camera', query['camera'][0]]
    for key in ('size', 'fps', 'format'):
        if key in query:
            args.extend(['--' + key, query[key][0]])
    return args


def validate_source(camera):
    source_options(camera)
    return camera


def read_plan(camera, cancelled):
    child = subprocess.Popen(['webcam_tool', *source_options(camera), '--json'],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    deadline = time.monotonic() + 45
    try:
        while True:
            if cancelled.is_set():
                raise RuntimeError('Remote camera connection cancelled.')
            if time.monotonic() > deadline:
                raise RuntimeError('Remote computer did not respond. Check its connection and retry.')
            try:
                stdout, stderr = child.communicate(timeout=.2)
                break
            except subprocess.TimeoutExpired:
                continue
        if child.returncode:
            raise RuntimeError((stderr or stdout or b'Remote discovery failed.').decode('utf-8', 'replace')[-1500:])
        if len(stdout) > 1048576:
            raise RuntimeError('Remote camera plan exceeded its size limit.')
        if cancelled.is_set():
            raise RuntimeError('Remote camera connection cancelled.')
        return json.loads(stdout)
    finally:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=2)
        for pipe in (child.stdout, child.stderr):
            pipe.close()


class RemoteCameraInput:
    def __init__(self, camera, cancelled=None):
        self.stopping = threading.Event()
        self.transport = self.decoder = None
        self.lock = threading.Lock()
        self.errors = collections.deque(maxlen=16)
        self.pending = bytearray()
        try:
            plan = read_plan(camera, cancelled or self.stopping)
            if plan.get('schemaVersion') != 1 or plan.get('container') != 'mpegts' or plan.get('microphone') is not None:
                raise RuntimeError('Unsupported remote video transport contract.')
            self.width, self.height, self.fps = int(plan['width']), int(plan['height']), float(plan['fps'])
            if not (0 < self.width <= 1280 and 0 < self.height <= 720 and 0 < self.fps <= 240):
                raise RuntimeError('Remote capture returned an invalid video mode.')
            argv = plan['capture']
            if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
                raise RuntimeError('Remote capture did not supply a command.')
            self.transport = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.decoder = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-threads', '2',
                '-probesize', '32768', '-analyzeduration', '0', '-flags', 'low_delay',
                '-i', 'pipe:0', '-an', '-vf', f'scale={self.width}:{self.height}',
                '-threads', '2', '-fps_mode', 'passthrough', '-pix_fmt', 'bgr24', '-f', 'rawvideo', 'pipe:1'],
                stdin=self.transport.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.transport.stdout.close()
            for child in (self.transport, self.decoder):
                threading.Thread(target=self.collect_errors, args=(child,), daemon=True).start()
            threading.Thread(target=self.heartbeat, daemon=True).start()
        except BaseException:
            self.release()
            raise

    def collect_errors(self, child):
        try:
            while True:
                chunk = os.read(child.stderr.fileno(), 512)
                if not chunk:
                    break
                self.errors.append(chunk.decode('utf-8', 'replace'))
        except (OSError, ValueError):
            pass

    def heartbeat(self):
        try:
            while not self.stopping.is_set():
                self.transport.stdin.write(b'alive\n')
                self.transport.stdin.flush()
                self.stopping.wait(2)
        except (BrokenPipeError, OSError, ValueError):
            pass

    def read(self):
        length = self.width * self.height * 3
        deadline = time.monotonic() + .5
        while not self.stopping.is_set():
            if len(self.pending) == length:
                data = bytes(self.pending)
                self.pending.clear()
                return {'data': data, 'width': self.width, 'height': self.height, 'stride': self.width * 3}
            if not select.select([self.decoder.stdout], [], [], max(0, deadline - time.monotonic()))[0]:
                return None
            chunk = os.read(self.decoder.stdout.fileno(), min(65536, length - len(self.pending)))
            if not chunk:
                raise RuntimeError('Remote camera disconnected or delivered no video. ' + ''.join(self.errors)[-1000:])
            self.pending.extend(chunk)
            if time.monotonic() >= deadline:
                return None
        return None

    def release(self):
        with self.lock:
            self.stopping.set()
            if self.transport and self.transport.stdin:
                try:
                    self.transport.stdin.close()
                except (OSError, ValueError):
                    pass
            for child in (self.decoder, self.transport):
                if child is None:
                    continue
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=2)
                for pipe in (child.stdout, child.stderr):
                    if pipe:
                        pipe.close()
