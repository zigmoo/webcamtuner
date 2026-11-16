"""Automatic adapter preparation is versioned, signed and independent of Zoom installation."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bin'))
import camera_adapter as adapter


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=os.environ['WEBCAMTUNER_TEST_ROOT'])
        self.root=Path(self.temp.name)
        self.vendor=self.root/'vendor/Zoom.desktop'
        self.vendor.parent.mkdir()
        self.vendor.write_text('[Desktop Entry]\nName=Zoom\nExec=/usr/bin/zoom %U\nType=Application\n')
        self.wrapper=self.root/'bin/webcamtuner-zoom'
        self.patches=[patch.dict(os.environ,XDG_DATA_HOME=str(self.root/'data'),XDG_CACHE_HOME=str(self.root/'cache')),
            patch.object(adapter,'ZOOM_DESKTOP',self.vendor),patch.object(adapter,'wrapper_path',return_value=self.wrapper),
            patch.object(adapter,'package_version',return_value='1:2.0.0-1'),patch.object(adapter,'zoom_processes',return_value=[]),
            patch.object(adapter.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'',''))]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def cached(self):
        path=adapter.library_path();path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(b'\x7fELFverified-fixture')
        return path
    def package(self,command,**kwargs):
        if command[:2]==['pacman','-Si']:return 'Version : 1:2.0.0-1\n'
        if command[:2]==['pacman','-Sp']:return 'https://example.invalid/pipewire-v4l2-2.0.0-1-x86_64.pkg.tar.zst\n'
        if command[:2]==['bsdtar','-xOf']:return b'MIT license' if command[-1].endswith('COPYING') else b'\x7fELFnew-fixture'
        raise AssertionError(command)
    def test_cached_adapter_automatically_connects_native_launcher_without_download(self):
        self.cached()
        with patch.object(adapter,'download',side_effect=AssertionError('Unexpected download')):
            value=adapter.ensure()
        self.assertTrue(value['ready'] and value['enabled'])
        self.assertIn('webcamtuner-zoom',adapter.desktop_path().read_text())
        self.assertEqual(self.wrapper.stat().st_mode&0o777,0o755)
        self.assertEqual(adapter.desktop_path().stat().st_mode&0o777,0o600)
    def test_version_upgrade_installs_matching_library_and_preserves_old_one(self):
        old=adapter.library_path('1:1.9.9-1');old.parent.mkdir(parents=True)
        old.write_bytes(b'\x7fELFold')
        with patch.object(adapter.subprocess,'check_output',side_effect=self.package),patch.object(adapter,'download',return_value=b'package'):
            value=adapter.ensure()
        self.assertTrue(value['ready'] and value['enabled'])
        self.assertEqual(adapter.library_path().read_bytes(),b'\x7fELFnew-fixture')
        self.assertEqual(old.read_bytes(),b'\x7fELFold')
    def test_signature_failure_does_not_enable_or_change_launcher(self):
        desktop=adapter.desktop_path();desktop.parent.mkdir(parents=True);desktop.write_text('Original custom launcher\n')
        with patch.object(adapter.subprocess,'check_output',side_effect=self.package),patch.object(adapter,'download',return_value=b'bad'), \
                patch.object(adapter.subprocess,'run',return_value=subprocess.CompletedProcess([],1)):
            with self.assertRaisesRegex(RuntimeError,'signature'):adapter.ensure()
        self.assertEqual(desktop.read_text(),'Original custom launcher\n')
        self.assertFalse(adapter.library_path().exists())
        self.assertFalse(self.wrapper.exists())
    def test_mismatched_repository_package_is_not_downloaded(self):
        with patch.object(adapter.subprocess,'check_output',return_value='Version : 1:9.9-1\n'),patch.object(adapter,'download') as download:
            with self.assertRaisesRegex(RuntimeError,'matching'):adapter.ensure()
        download.assert_not_called()
    def test_readback_is_prepared_without_native_zoom(self):
        self.cached();self.vendor.unlink()
        value=adapter.ensure()
        self.assertTrue(value['ready'])
        self.assertFalse(value['zoomInstalled'] or value['enabled'])
        self.assertFalse(adapter.desktop_path().exists() or self.wrapper.exists())
    def test_explicit_normal_launcher_choice_survives_automatic_preparation(self):
        self.cached();adapter.setup();adapter.disable()
        before=adapter.desktop_path().read_bytes()
        value=adapter.ensure()
        self.assertTrue(value['ready'] and value['normalLauncher'])
        self.assertFalse(value['enabled'])
        self.assertEqual(adapter.desktop_path().read_bytes(),before)
    def test_normal_choice_is_saved_even_before_launcher_was_wrapped(self):
        self.cached();adapter.disable()
        value=adapter.ensure()
        self.assertTrue(value['normalLauncher'] and value['ready'])
        self.assertFalse(value['enabled'])
    def test_explicit_repair_can_reenable_normal_launcher(self):
        self.cached();adapter.disable()
        value=adapter.setup()
        self.assertTrue(value['ready'] and value['enabled'])
        self.assertFalse(value['normalLauncher'])
    def test_concurrent_preparation_is_rejected_without_overwriting_library(self):
        original=self.cached().read_bytes()
        with adapter.adapter_update_lock():
            with self.assertRaisesRegex(RuntimeError,'already running'):adapter.ensure()
        self.assertEqual(adapter.library_path().read_bytes(),original)
    def test_old_loaded_adapter_requires_reopen_after_upgrade(self):
        self.cached();adapter.setup()
        original=Path.read_text
        current=adapter.library_path().resolve()
        def maps(path,*args,**kwargs):
            if str(path)=='/proc/123/maps':return '1000-2000 r--p 00000000 00:01 123 '+str(current).replace('1_2.0.0-1','1_1.9.9-1')+'\n'
            return original(path,*args,**kwargs)
        with patch.object(adapter,'zoom_processes',return_value=[123]),patch.object(Path,'read_text',autospec=True,side_effect=maps):
            value=adapter.status()
        self.assertFalse(value['adapterLoaded'])
        self.assertTrue(value['restartRequired'])
    def test_launch_waits_for_an_existing_installer_to_finish(self):
        self.cached();held=threading.Event();release=threading.Event()
        def hold():
            with adapter.adapter_update_lock():
                held.set();release.wait(2)
        thread=threading.Thread(target=hold);thread.start()
        self.assertTrue(held.wait(1))
        timer=threading.Timer(.15,release.set);timer.start()
        try:
            value=adapter.ensure(wait_seconds=1)
            self.assertTrue(value['ready'] and value['enabled'])
        finally:
            release.set();thread.join(2);timer.join(2)


if __name__=='__main__':unittest.main()
