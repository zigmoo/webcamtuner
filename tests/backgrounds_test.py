"""Exercise image decoding, composition, crop ordering, and the actual segmentation model."""
import importlib.util
from pathlib import Path
import os
import tempfile
import unittest

import cv2
import numpy as np
from PIL import Image

spec = importlib.util.spec_from_file_location("preview", Path(__file__).resolve().parent.parent / "bin" / "process_preview.py")
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class BackgroundTests(unittest.TestCase):
    def test_foreground_is_preserved_and_background_is_replaced(self):
        frame = np.full((20, 30, 3), (10, 20, 30), dtype=np.uint8)
        image = np.full((40, 20, 3), (210, 150, 90), dtype=np.uint8)
        mask = np.zeros((20, 30, 1), dtype=np.float32)
        mask[5:15, 10:20] = 1
        output = preview.composite(frame, mask, "image", image)
        np.testing.assert_array_equal(output[8, 14], frame[8, 14])
        np.testing.assert_array_equal(output[0, 0], image[0, 0])

    def test_blur_changes_background_but_preserves_foreground(self):
        frame = np.zeros((60, 80, 3), dtype=np.uint8)
        frame[::2] = 255
        mask = np.zeros((60, 80, 1), dtype=np.float32)
        mask[20:40, 25:55] = 1
        output = preview.composite(frame, mask, "blur", None)
        np.testing.assert_array_equal(output[25:35, 30:50], frame[25:35, 30:50])
        self.assertNotEqual(int(output[0, 0, 0]), int(frame[0, 0, 0]))

    def test_image_paths_with_spaces_hashes_and_exif_orientation(self):
        scratch = os.environ["WEBCAMTUNER_TEST_ROOT"]
        Path(scratch).mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            path = Path(directory) / "camera #1's background.jpeg"
            image = Image.new("RGB", (40, 20), (30, 60, 90))
            exif = image.getexif()
            exif[274] = 6
            image.save(path, exif=exif)
            decoded = preview.load_background(path.as_uri())
            self.assertEqual(decoded.shape, (40, 20, 3))
            with self.assertRaisesRegex(ValueError, "not found"):
                preview.load_background(str(path.parent / "missing.jpeg"))
            with self.assertRaisesRegex(ValueError, "absolute"):
                preview.load_background("relative.jpeg")
            with self.assertRaisesRegex(ValueError, "local"):
                preview.load_background("file://remote-host/a.jpeg")

    def test_model_executes_with_finite_person_mask(self):
        segmenter = preview.Segmenter()
        mask = segmenter.mask(np.zeros((360, 640, 3), dtype=np.uint8))
        self.assertEqual(mask.shape, (360, 640, 1))
        self.assertTrue(np.isfinite(mask).all())
        self.assertGreaterEqual(float(mask.min()), 0)
        self.assertLessEqual(float(mask.max()), 1)

    def test_crop_before_composition_retains_expected_source_region(self):
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        frame[180:540, 320:960] = (20, 70, 200)
        cropped = preview.crop_frame(frame, {"zoom": 2, "centerX": 0.5, "centerY": 0.5})
        self.assertEqual(cropped.shape, (360, 640, 3))
        np.testing.assert_array_equal(cropped[0, 0], [20, 70, 200])
        np.testing.assert_array_equal(cropped[-1, -1], [20, 70, 200])


if __name__ == "__main__":
    unittest.main()
