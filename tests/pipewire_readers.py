"""Read only the synthetic WebcamTuner node through two independent consumers."""
import hashlib
import json
from pathlib import Path
import subprocess
import time
import gi

gi.require_version('Gst', '1.0')
from gi.repository import Gst

root = Path(__file__).resolve().parent.parent
state = json.loads(subprocess.check_output(['python3', str(root / 'bin/output-control.py'), 'status'], text=True))
assert state['published'] and state['synthetic'], 'Start the synthetic test camera before this integration check'
serial = str(state['nodeSerial'])
Gst.init(None)


class Reader:
    def __init__(self):
        self.frames = 0
        self.hashes = set()
        self.pipeline = Gst.parse_launch('pipewiresrc target-object=' + serial + ' ! video/x-raw,width=1280,height=720,framerate=30/1 ! appsink name=frames sync=false max-buffers=1 drop=true')
        self.sink = self.pipeline.get_by_name('frames')
        assert self.pipeline.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE

    def sample(self):
        sample = self.sink.emit('try-pull-sample', 100 * Gst.MSECOND)
        if not sample:
            error = self.pipeline.get_bus().pop_filtered(Gst.MessageType.ERROR)
            if error:
                raise RuntimeError(str(error.parse_error()))
            return
        caps = sample.get_caps().get_structure(0)
        assert caps.get_value('width') == 1280 and caps.get_value('height') == 720
        self.frames += 1
        if self.frames % 15 == 0:
            buffer = sample.get_buffer()
            self.hashes.add(hashlib.sha256(buffer.extract_dup(0, buffer.get_size())).hexdigest())

    def close(self):
        self.pipeline.set_state(Gst.State.NULL)


a, b = Reader(), Reader()
start = time.monotonic()
try:
    while time.monotonic() - start < 10:
        a.sample()
        b.sample()
    assert a.frames >= 240 and b.frames >= 240, (a.frames, b.frames)
    assert len(a.hashes) >= 10 and len(b.hashes) >= 10, 'Frames must change, not merely repeat'
    before = b.frames
    a.close()
    a = Reader()
    second = time.monotonic()
    while time.monotonic() - second < 3:
        a.sample()
        b.sample()
    assert a.frames >= 60 and b.frames - before >= 60, 'Reopening one consumer must preserve the other'
    print(json.dumps({'result': 'PASS', 'secondReaderFrames': b.frames, 'reopenedReaderFrames': a.frames,
                      'distinctFrameHashes': len(b.hashes), 'format': '1280x720/30', 'physicalCameraOpened': False}))
finally:
    a.close()
    b.close()
