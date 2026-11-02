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

    def test_low_resolution_matte_uses_the_same_full_source_crop(self):
        mask = np.zeros((360,640,1),dtype=np.float32)
        mask[90:270,160:480] = 1
        crop = {'zoom':2,'centerX':0.5,'centerY':0.5}
        aligned = preview.align_matte(mask,1280,720,crop,640,360)
        self.assertEqual(aligned.shape,(360,640,1))
        self.assertAlmostEqual(float(aligned[180,320,0]),1)
        self.assertGreater(float(aligned[2:-2,2:-2].mean()),0.999)

    def test_background_crop_selects_area_without_moving_foreground(self):
        image = np.zeros((200,400,3),dtype=np.uint8)
        image[:,:200] = (0,0,255)
        image[:,200:] = (0,255,0)
        frame = np.full((90,160,3), 80, dtype=np.uint8)
        mask = np.zeros((90,160,1),dtype=np.float32)
        mask[20:70,60:100] = 1
        crop = {'zoom':2,'centerX':0.75,'centerY':0.5}
        result = preview.composite(frame,mask,'image',image,crop)
        np.testing.assert_array_equal(result[0,0], (0,255,0))
        np.testing.assert_array_equal(result[45,80], frame[45,80])

    def test_blur_changes_background_but_preserves_foreground(self):
        frame = np.zeros((60, 80, 3), dtype=np.uint8)
        frame[::2] = 255
        mask = np.zeros((60, 80, 1), dtype=np.float32)
        mask[20:40, 25:55] = 1
        output = preview.composite(frame, mask, "blur", None)
        np.testing.assert_array_equal(output[25:35, 30:50], frame[25:35, 30:50])
        self.assertNotEqual(int(output[0, 0, 0]), int(frame[0, 0, 0]))

    def test_mirror_reflects_person_and_mask_without_reflecting_the_background(self):
        frame = np.zeros((20, 30, 3), dtype=np.uint8)
        frame[:, :10] = (40, 80, 200)
        mask = np.zeros((20, 30, 1), dtype=np.float32)
        mask[:, :10] = 1
        background = np.zeros_like(frame)
        background[:, :15] = (200, 50, 20)
        background[:, 15:] = (70, 80, 90)
        mirrored, alpha = preview.orient_camera(frame, mask, True)
        output = preview.composite(mirrored, alpha, "image", background)
        np.testing.assert_array_equal(output[5, 25], (40, 80, 200))
        np.testing.assert_array_equal(output[5, 0], (200, 50, 20))
        untouched, _ = preview.orient_camera(frame, mask, False)
        np.testing.assert_array_equal(untouched, frame)

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

    def test_mask_noise_is_damped_without_smearing_real_motion(self):
        still = np.full((40, 60, 3), 80, dtype=np.uint8)
        stable = preview.MaskStabilizer()
        stable.update(still, np.full((40, 60, 1), 0.5, dtype=np.float32))
        smoothed = stable.update(still, np.full((40, 60, 1), 0.9, dtype=np.float32))
        self.assertAlmostEqual(float(smoothed.mean()), 0.6, places=5)
        # A genuine frame change receives a fast update rather than the stationary blend.
        moved = np.full_like(still, 180)
        tracked = stable.update(moved, np.ones((40, 60, 1), dtype=np.float32))
        self.assertGreater(float(tracked.mean()), 0.95)

    def test_mask_and_camera_crop_share_the_same_region(self):
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        mask = np.zeros((720, 1280, 1), dtype=np.float32)
        frame[180:540, 320:960] = 255
        mask[180:540, 320:960] = 1
        crop = {"zoom": 2, "centerX": 0.5, "centerY": 0.5}
        color = preview.crop_frame(frame, crop)
        alpha = preview.crop_frame(mask, crop)
        np.testing.assert_array_equal(color[..., 0] / 255, alpha)

    def test_brio_uses_supported_uhd_and_laptop_keeps_1080p(self):
        modes = [{"width": w, "height": h, "fps": 30, "fourcc": "MJPG"}
                 for w, h in [(1280, 720), (1920, 1080), (3840, 2160), (4096, 2160)]]
        best = preview.choose_capture_mode(modes)
        self.assertEqual((best["width"], best["height"]), (3840, 2160))
        laptop = preview.choose_capture_mode(modes[:2])
        self.assertEqual((laptop["width"], laptop["height"]), (1920, 1080))
        self.assertEqual(preview.crop_bounds(3840, 2160, {"zoom": 2, "centerX": 0.5, "centerY": 0.5})[2:], (1920, 1080))

    def test_v4l2_inventory_retains_compressed_4k_modes(self):
        modes = preview.capture_modes("""[0]: 'MJPG' (Motion-JPEG)
Size: Discrete 3840x2160
Interval: Discrete 0.033s (30.000 fps)
[1]: 'YUYV' (YUYV 4:2:2)
Size: Discrete 640x480
Interval: Discrete 0.033s (30.000 fps)""")
        self.assertEqual(preview.choose_capture_mode(modes)["width"], 3840)

    def test_video_model_preserves_recurrent_states_between_frames(self):
        segmenter = preview.Segmenter()
        frame = np.full((360, 640, 3), 100, dtype=np.uint8)
        segmenter.mask(frame)
        self.assertTrue(all(value.size > 1 for value in segmenter.recurrent))
        first = [value.copy() for value in segmenter.recurrent]
        segmenter.mask(frame)
        self.assertTrue(any(not np.array_equal(a, b) for a, b in zip(first, segmenter.recurrent)))

    def test_crop_before_composition_retains_expected_source_region(self):
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        frame[180:540, 320:960] = (20, 70, 200)
        cropped = preview.crop_frame(frame, {"zoom": 2, "centerX": 0.5, "centerY": 0.5})
        self.assertEqual(cropped.shape, (360, 640, 3))
        np.testing.assert_array_equal(cropped[0, 0], [20, 70, 200])
        np.testing.assert_array_equal(cropped[-1, -1], [20, 70, 200])


if __name__ == "__main__":
    unittest.main()
