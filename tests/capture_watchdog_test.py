"""Transient capture gaps must recover; a stale frame must never count as fresh."""
import importlib.util
from pathlib import Path
import threading
import time
import unittest

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('preview', root / 'bin/process_preview.py')
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class CaptureWatchdogTests(unittest.TestCase):
    def capture(self):
        capture = preview.CameraCapture.__new__(preview.CameraCapture)
        capture.condition = threading.Condition()
        capture.stopping = threading.Event()
        capture.sequence, capture.frame, capture.error = 0, None, None
        capture.last_frame_at = time.monotonic()
        return capture

    def test_recovers_after_a_one_second_gap(self):
        capture = self.capture()
        def deliver():
            with capture.condition:
                capture.frame = 'fresh'
                capture.sequence = 1
                capture.last_frame_at = time.monotonic()
                capture.condition.notify_all()
        timer = threading.Timer(1.1, deliver)
        timer.start()
        try:
            self.assertEqual(capture.next(0), ('fresh', 1))
        finally:
            timer.join()

    def test_stale_frame_still_times_out_with_diagnostics(self):
        capture = self.capture()
        capture.frame = 'old'
        with self.assertRaisesRegex(RuntimeError, 'last frame .* ago'):
            capture.next(0, timeout=.02)


if __name__ == '__main__':
    unittest.main()
