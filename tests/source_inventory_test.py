"""Capture menus exclude metadata endpoints and identify the exact test output."""
import importlib.util
import struct
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, root / 'bin' / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


output = load('output', 'output-control.py')
apps = load('apps', 'browser-control.py')


class Sources(unittest.TestCase):
    def query(self, caps, device_caps):
        def ioctl(fd, request, data, mutate):
            self.assertEqual(request, 0x80685600)
            struct.pack_into('=16s32s32sIII', data, 0, b'uvcvideo', b'Test camera', b'usb-test', 1, caps, device_caps)
        with patch.object(output.os, 'open', return_value=42), patch.object(output.os, 'close') as close, patch.object(output.fcntl, 'ioctl', side_effect=ioctl):
            info = output.capture_info('/dev/video0')
            close.assert_called_once_with(42)
            return info

    def test_metadata_is_not_video(self):
        self.assertIsNone(self.query(0x80000001, 0x00800000))

    def test_single_and_multi_planar_capture(self):
        self.assertEqual(self.query(0x80000000, 1)['name'], 'Test camera')
        self.assertEqual(self.query(0x80000000, 0x1000)['driver'], 'uvcvideo')
        self.assertEqual(self.query(1, 0)['bus'], 'usb-test')

    def test_close_on_query_error(self):
        with patch.object(output.os, 'open', return_value=42), patch.object(output.os, 'close') as close, patch.object(output.fcntl, 'ioctl', side_effect=OSError('denied')):
            with self.assertRaises(OSError):
                output.capture_info('/dev/video0')
            close.assert_called_once_with(42)

    def test_pipewire_only_video_sources(self):
        def node(id, name, media):
            return {'id': id, 'type': 'PipeWire:Interface:Node', 'info': {'state': 'suspended', 'props': {'node.name': name, 'media.class': media}}}
        sources = output.video_sources([node(10, 'webcamtuner.test', 'Video/Source'), node(11, 'microphone', 'Audio/Source'), node(12, 'camera', 'Video/Source'), {'type': 'PipeWire:Interface:Device'}, None])
        self.assertEqual(len(sources), 2)
        self.assertEqual(next(s for s in sources if s['testOutput'])['id'], 10)
        with self.assertRaises(ValueError):
            output.video_sources({})

    def test_native_zoom_only(self):
        with patch.object(apps.shutil, 'which', return_value='/usr/bin/zoom'), patch.object(apps.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
            self.assertIn('Zoom desktop', apps.launch('zoom')['message'])
            self.assertEqual(run.call_args.args[0][-1], '/usr/bin/zoom')
            self.assertFalse(any('http' in arg for arg in run.call_args.args[0]))

    def test_missing_zoom_never_falls_back_to_browser(self):
        with patch.object(apps.shutil, 'which', return_value=None), patch.object(apps.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'not installed'):
                apps.launch('zoom')
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
