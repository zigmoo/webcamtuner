"""A running compositor changes sources without recreating its published camera."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'bin'))
spec = importlib.util.spec_from_file_location('preview_switch', root / 'bin/process_preview.py')
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class CameraSwitch(unittest.TestCase):
    def test_switch_confirmation_failure_recovery_and_single_publisher(self):
        captures, publishers, records = [], [], []
        class Capture:
            fps = 30
            def __init__(self, camera):
                if camera == '/dev/video999':
                    raise RuntimeError('Camera unavailable')
                self.camera, self.sequence, self.closed = camera, 0, False
                captures.append(self)
            def next(self, previous):
                self.sequence += 1
                return np.full((180, 320, 3), 40 if self.camera == '/dev/video101' else 180, dtype=np.uint8), self.sequence
            def close(self): self.closed = True
        class Publisher:
            def __init__(self): self.frames = []; publishers.append(self)
            def push(self, frame): self.frames.append(int(frame[0, 0, 0]))
            def close(self): pass
        class Server:
            def __init__(self, receive, stop): self.receive = receive; server.append(self)
            def emit(self, value): pass
            def close(self): pass
        server = []
        settings = {'camera': '/dev/video101', 'crop': {'zoom': 1, 'centerX': .5, 'centerY': .5}, 'background': {'mode': 'none'}, 'configurationRevision': 1}
        def emit(record):
            records.append(record)
            frames = [r for r in records if 'frame' in r]
            if 'frame' not in record: return
            # Switch, reject an unavailable source, then switch back.
            if len(frames) in (1, 3, 5):
                n = len(frames)
                camera = {1: '/dev/video102', 3: '/dev/video999', 5: '/dev/video101'}[n]
                server[0].receive({**settings, 'camera': camera, 'configurationRevision': n + 1})
        with patch.object(preview, 'CameraCapture', Capture), patch.object(preview, 'emit', emit), patch('camera_stream.ControlServer', Server), patch('camera_stream.Publisher', Publisher):
            preview.run(settings, frame_limit=7, publish=True)
        frames = [r for r in records if 'frame' in r]
        self.assertEqual(len(publishers), 1)
        self.assertEqual(publishers[0].frames, [40, 180, 180, 180, 180, 40, 40])
        self.assertEqual([r['camera'] for r in frames], ['/dev/video101'] + ['/dev/video102'] * 4 + ['/dev/video101'] * 2)
        self.assertEqual(frames[3]['failedConfigurationRevision'], 4)
        self.assertEqual(frames[3]['configurationRevision'], 2)
        self.assertNotIn('configurationError', frames[-1])
        self.assertTrue(all(c.closed for c in captures))


if __name__ == '__main__': unittest.main()
