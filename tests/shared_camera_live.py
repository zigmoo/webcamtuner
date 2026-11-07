"""Opt-in camera sharing check; frames stay in memory and are never recorded."""
import importlib.util
import os
from pathlib import Path
import sys
import time

camera = os.environ.get('WEBCAMTUNER_TEST_CAMERA')
if not camera:
    raise SystemExit('Set WEBCAMTUNER_TEST_CAMERA to the explicitly authorized test camera.')
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'bin'))
spec = importlib.util.spec_from_file_location('preview', root / 'bin/process_preview.py')
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)
from camera_input import SharedCameraInput

primary = preview.CameraCapture(camera)
secondary = None
try:
    frame, sequence = primary.next(0, timeout=4)
    mode = preview.choose_capture_mode(preview.device_modes(camera))
    assert frame.shape == (mode['height'], mode['width'], 3)
    secondary = SharedCameraInput(camera, mode)
    count = 0
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        frame, sequence = primary.next(sequence, timeout=2)
        if secondary.read() is not None:
            count += 1
    assert count >= 5, f'Only {count} simultaneous frames'
    primary.close()
    primary = None
    assert secondary.read() is not None, 'Companion consumer stopped with the compositor'
    print(f'PASS: compositor and companion share {mode["width"]}x{mode["height"]}; '
          f'{count} overlapping frames; companion survives compositor stop')
finally:
    if primary:
        primary.close()
    if secondary:
        secondary.release()
