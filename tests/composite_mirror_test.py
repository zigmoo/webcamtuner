"""Pixel acceptance: Mirror reflects person, background, placement and label together.

Uses the real worker loop and snapshot renderer with synthetic capture/matting;
never opens a physical camera or connects to the operator's published output.
"""
import base64
import copy
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('composite_mirror', ROOT / 'bin/process_preview.py')
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class CompositeMirror(unittest.TestCase):
    def setUp(self):
        self.frame = np.zeros((180, 320, 3), np.uint8)
        self.frame[:] = (25, 60, 90)
        self.frame[25:135, 30:90] = (200, 30, 80)
        self.frame[25:135, 90:115] = (20, 180, 70)
        self.matte = np.zeros((180, 320, 1), np.float32)
        self.matte[25:135, 30:115] = 1
        self.background = np.zeros_like(self.frame)
        self.background[:, :100] = (190, 40, 30)
        self.background[:, 100:] = (30, 40, 160)
        self.background[150:] = (20, 170, 130)
        self.settings = {
            'camera': '/dev/video101', 'mirror': False,
            'crop': {'zoom': 1.25, 'centerX': .45, 'centerY': .5},
            'foreground': {'x': .22, 'y': .05},
            'background': {'mode': 'image', 'imagePath': '/synthetic/background.png',
                'crop': {'zoom': 1.1, 'centerX': .5, 'centerY': .5},
                'labelOverlay': {'enabled': True, 'text': 'Left > Right', 'x': .08, 'y': .88,
                    'opacity': .75, 'color': '#a0ff30', 'fontSize': .07}},
        }

    def render(self, settings):
        frames, records = [], []
        frame, matte = self.frame, self.matte
        class Capture:
            fps = 30
            def __init__(self, camera): pass
            def next(self, previous): return frame.copy(), previous + 1
            def close(self): pass
        class Segmenter:
            provider = 'Synthetic matting'
            def mask(self, image, full_resolution=False): return matte.copy()
        class Publisher:
            def push(self, image): frames.append(image.copy())
            def close(self): pass
        class Server:
            def __init__(self, receive, stop): pass
            def emit(self, value): records.append(value)
            def close(self): pass
        with patch.object(preview, 'CameraCapture', Capture), patch.object(preview, 'Segmenter', Segmenter), \
                patch.object(preview, 'load_background', return_value=self.background), \
                patch('camera_stream.ControlServer', Server), patch('camera_stream.Publisher', Publisher):
            preview.run(settings, frame_limit=1, publish=True)
        record = next(r for r in records if 'frame' in r)
        panel = cv2.imdecode(np.frombuffer(base64.b64decode(record['frame']), np.uint8), cv2.IMREAD_COLOR)
        return frames[0], panel, record

    def test_publication_flips_every_finished_pixel_once_in_all_effect_modes(self):
        for mode in ('none', 'blur', 'image'):
            with self.subTest(mode=mode):
                settings = copy.deepcopy(self.settings)
                settings['background']['mode'] = mode
                normal, normal_panel, normal_record = self.render(settings)
                settings['mirror'] = True
                mirrored, mirror_panel, mirror_record = self.render(settings)
                np.testing.assert_array_equal(mirrored, normal[:, ::-1])
                self.assertGreater(float(np.abs(normal.astype(float)-mirrored).mean()), 10)
                # Editable UI always gets a canonical unlabelled scene, in either
                # mirror mode; its whole image+label layer applies the same flip.
                np.testing.assert_array_equal(mirror_panel, normal_panel)
                if mode == 'image':
                    self.assertEqual(normal_record['labelBitmap'], mirror_record['labelBitmap'])
                    self.assertGreater(float(np.abs(normal.astype(float)-cv2.resize(normal_panel, (1280,720))).mean()), .1)

    def test_snapshot_reflects_background_person_and_label_as_one_scene(self):
        with tempfile.TemporaryDirectory(dir=os.environ['WEBCAMTUNER_TEST_ROOT']) as scratch, \
                patch.dict(os.environ, {'WEBCAMTUNER_SNAPSHOT_ROOT': scratch}), \
                patch.object(preview.snapshot_files, 'mirror_snapshot', return_value={}):
            normal = preview.save_processed_snapshot(self.frame, self.matte, self.settings, self.background)
            settings = {**self.settings, 'mirror': True}
            mirrored = preview.save_processed_snapshot(self.frame, self.matte, settings, self.background)
            one = cv2.imread(normal['path'])
            two = cv2.imread(mirrored['path'])
            self.assertEqual(one.shape, two.shape)
            # JPEG block/chroma boundaries may differ after a horizontal flip.
            self.assertLess(float(np.abs(two.astype(float)-one[:, ::-1]).mean()), 2)
            self.assertGreater(float(np.abs(two.astype(float)-one).mean()), 10)


if __name__ == '__main__': unittest.main()
