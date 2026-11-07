"""Camera identity must resolve to its physical broker node, never the output."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from camera_input import camera_serial


class SharedCameraIdentityTests(unittest.TestCase):
    def test_selects_matching_physical_camera_serial(self):
        nodes = [
            {'info': {'props': {'node.name': 'webcamtuner.camera', 'media.class': 'Video/Source', 'object.serial': 1}}},
            {'info': {'props': {'api.v4l2.path': '/dev/video102', 'media.class': 'Video/Source', 'object.serial': 2}}},
            {'info': {'props': {'api.v4l2.path': '/dev/video101', 'media.class': 'Video/Source', 'object.serial': 3}}},
        ]
        self.assertEqual(camera_serial('/dev/video101', nodes), '3')

    def test_missing_camera_does_not_fall_back_to_exclusive_capture(self):
        with self.assertRaisesRegex(RuntimeError, 'not available through PipeWire'):
            camera_serial('/dev/video101', [])

    def test_rejects_non_camera_node_and_invalid_serial(self):
        for props in [
            {'api.v4l2.path': '/dev/video101', 'media.class': 'Video/Sink', 'object.serial': 3},
            {'api.v4l2.path': '/dev/video101', 'media.class': 'Video/Source', 'object.serial': 'bad ! pipeline'},
        ]:
            with self.assertRaises(RuntimeError):
                camera_serial('/dev/video101', [{'info': {'props': props}}])


if __name__ == '__main__':
    unittest.main()
