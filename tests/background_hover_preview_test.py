"""The private hover preview substitutes an image while retaining the shared scene."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

BIN = Path(__file__).resolve().parents[1] / 'bin'
sys.path.insert(0, str(BIN))
from camera_stream import ControlServer, MAX_PREVIEW_RESPONSE, command
from process_preview import BackgroundPreview


class BackgroundHoverPreviewTest(unittest.TestCase):
    def test_hover_composes_library_image_without_reconfiguring_output(self):
        with tempfile.TemporaryDirectory(prefix='hover-', dir=os.environ['WEBCAMTUNER_TEST_ROOT']) as folder:
            with patch.dict(os.environ, WEBCAMTUNER_RUNTIME_ROOT=folder, XDG_DATA_HOME=folder):
                library = Path(folder) / 'webcamtuner/backgrounds'
                library.mkdir(parents=True)
                backdrop = library / 'green.png'
                self.assertTrue(cv2.imwrite(str(backdrop), np.full((270, 480, 3), (0, 240, 0), np.uint8)))
                crop = {'zoom': 1, 'centerX': .5, 'centerY': .5}
                active = {'camera': '/dev/video0', 'background': {'mode': 'blur'}, 'crop': crop, 'mirror': True}
                frame = np.zeros((270, 480, 3), np.uint8)
                matte = np.zeros((270, 480), np.float32)
                frame[70:200, 40:180] = (0, 0, 240)
                matte[70:200, 40:180] = 1
                preview = BackgroundPreview()
                preview.source = (frame, matte, active)
                received = []
                server = ControlServer(received.append, lambda: None, preview.render)
                try:
                    server.emit({'frame': 'unchanged', 'configurationRevision': 8})
                    self.assertTrue(command({'operation': 'status'})['backgroundPreview'])
                    background = {'mode': 'image', 'imagePath': str(backdrop)}
                    request = {'operation': 'background-preview', 'background': background}
                    result = command(request, response_limit=MAX_PREVIEW_RESPONSE)
                    self.assert_composite(result)
                    with subprocess.Popen([sys.executable, str(BIN / 'background-preview-client.py'),
                                           json.dumps(background)], stdout=subprocess.PIPE) as client:
                        try:
                            self.assert_composite(json.loads(client.stdout.readline()))
                        finally:
                            client.terminate()
                    with self.assertRaisesRegex(RuntimeError, 'background library'):
                        command({**request, 'background': {**background, 'imagePath': str(backdrop.parent.parent / 'outside.png')}})
                    self.assertEqual(received, [])
                    self.assertEqual(server.latest['frame'], 'unchanged')
                    self.assertEqual(server.status()['configurationRevision'], 8)
                    self.assertEqual(active['background']['mode'], 'blur')
                finally:
                    server.close()

    def test_hover_keeps_the_published_aspect_for_a_four_by_three_camera(self):
        with tempfile.TemporaryDirectory(dir=os.environ['WEBCAMTUNER_TEST_ROOT']) as folder:
            with patch.dict(os.environ, XDG_DATA_HOME=folder):
                library = Path(folder) / 'webcamtuner/backgrounds'
                library.mkdir(parents=True)
                backdrop = library / 'green.png'
                self.assertTrue(cv2.imwrite(str(backdrop), np.full((270, 480, 3), (0, 240, 0), np.uint8)))
                frame = np.zeros((360, 480, 3), np.uint8)
                matte = np.zeros((360, 480), np.float32)
                frame[:30, 100:380] = (0, 0, 240)
                matte[:30, 100:380] = 1
                frame[100:260, 100:380] = (0, 0, 240)
                matte[100:260, 100:380] = 1
                preview = BackgroundPreview()
                crop = {'zoom': 1, 'centerX': .5, 'centerY': .5}
                preview.source = (frame, matte, {'camera': '/dev/video0', 'crop': crop})
                result = preview.render({'mode': 'image', 'imagePath': str(backdrop)})
                image = self.decode_frame(result)
                self.assertEqual(image.shape, (270, 480, 3))
                self.assertGreater(image[5, 240, 1], 220)
                self.assertGreater(image[135, 240, 2], 220)

    @staticmethod
    def decode_frame(result):
        return cv2.imdecode(np.frombuffer(base64.b64decode(result['frame']), dtype=np.uint8), cv2.IMREAD_COLOR)

    def assert_composite(self, result):
        image = self.decode_frame(result)
        self.assertEqual(image.shape, (270, 480, 3))
        self.assertGreater(image[120, 370, 2], 220)  # Mirrored foreground.
        self.assertGreater(image[120, 110, 1], 220)  # Hovered background.


if __name__ == '__main__':
    unittest.main()
