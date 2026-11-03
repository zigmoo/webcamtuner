"""Readiness is truthful, setup respects active output, and signed media stays scoped."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid
sys.dont_write_bytecode = True
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'bin'))
spec = importlib.util.spec_from_file_location('wct_first_run', root / 'bin/first-run.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
import media_runtime


class FirstRun(unittest.TestCase):
    def setUp(self):
        self.scratch = Path(os.environ['WEBCAMTUNER_TEST_ROOT']) / ('setup-' + uuid.uuid4().hex[:8])
        self.scratch.mkdir()
        self.environment = patch.dict(os.environ, XDG_DATA_HOME=str(self.scratch / 'data'), XDG_CACHE_HOME=str(self.scratch / 'cache'))
        self.environment.start()
    def tearDown(self): self.environment.stop()

    def test_missing_runtime_remains_not_ready_without_starting_output(self):
        with patch.object(setup, 'controller', return_value=None), patch.object(setup, 'media_probe', return_value={'ready': True, 'message': 'Ready'}), patch.object(setup, 'session_ready', return_value=True):
            value = setup.status()
        self.assertFalse(value['ready'])
        self.assertFalse(value['controllerReady'])
        self.assertFalse(next(c for c in value['checks'] if c['id'] == 'runtime')['ready'])
        self.assertFalse((self.scratch / 'data').exists())

    def test_active_output_blocks_prepare_before_any_library_changes(self):
        active = subprocess.CompletedProcess([], 0, 'active\n', '')
        with patch.object(setup.subprocess, 'run', return_value=active), patch.object(setup, 'prepare_controller') as build:
            with self.assertRaisesRegex(RuntimeError, 'kept running'):
                setup.prepare()
        build.assert_not_called()
        self.assertFalse((self.scratch / 'data/webcamtuner/runtimes').exists())

    def test_signed_plugin_rejection_preserves_previous_media_path(self):
        base = self.scratch / 'data/webcamtuner/media'
        old = base / 'previous'; old.mkdir(parents=True)
        (old / 'libgstpipewire.so').write_bytes(b'original')
        (base / 'current').symlink_to('previous', target_is_directory=True)
        def checked(command, **kwargs):
            if command[:2] == ['pacman', '-Q']: return 'libpipewire 1:1.6.10-1\n'
            if command[:2] == ['pacman', '-Si']: return 'Version : 1:1.6.10-1\n'
            if command[:2] == ['pacman', '-Sp']: return 'https://example.invalid/pipewire/gst-plugin-pipewire-1.6.10-1-x86_64.pkg.tar.zst\n'
            raise AssertionError(command)
        with patch.object(media_runtime, 'probe', return_value={'ready': False, 'missing': ['pipewiresink']}), patch.object(media_runtime.subprocess, 'check_output', side_effect=checked), patch.object(media_runtime, 'download', return_value=b'invalid'), patch.object(media_runtime.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)):
            with self.assertRaisesRegex(RuntimeError, 'signature'):
                media_runtime.prepare(lambda _: None)
        self.assertEqual((base / 'current').resolve(), old)
        self.assertEqual((old / 'libgstpipewire.so').read_bytes(), b'original')

    def test_plugin_environment_is_scoped_and_does_not_mutate_parent(self):
        folder = self.scratch / 'data/webcamtuner/media/plugins/lib'; folder.mkdir(parents=True)
        (folder.parent.parent / 'current').symlink_to('plugins', target_is_directory=True)
        before = dict(os.environ)
        env = media_runtime.environment()
        self.assertEqual(dict(os.environ), before)
        self.assertTrue(env['GST_PLUGIN_PATH_1_0'].startswith(str(folder.parent)))
        self.assertTrue(env['LD_LIBRARY_PATH'].startswith(str(folder)))

    def test_failed_runtime_build_preserves_the_selected_environment(self):
        base = self.scratch / 'data/webcamtuner'
        old = base / 'runtimes/verified'; old.mkdir(parents=True)
        (old / 'original').write_text('previous runtime')
        (base / 'runtime').symlink_to('runtimes/verified', target_is_directory=True)
        with patch.object(setup.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['pip'])):
            with self.assertRaises(subprocess.CalledProcessError):
                setup.prepare_runtime()
        self.assertEqual((base / 'runtime').resolve(), old)
        self.assertEqual((old / 'original').read_text(), 'previous runtime')

    def test_untrusted_local_package_source_is_refused(self):
        from camera_adapter import download
        path = self.scratch / 'package.pkg.tar.zst'; path.write_bytes(b'bad')
        with self.assertRaisesRegex(RuntimeError, 'root-owned'):
            download(path.as_uri(), 100)


if __name__ == '__main__': unittest.main()
