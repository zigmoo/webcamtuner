"""Zoom-first launch repairs the adapter before exec; failures preserve native Zoom/audio."""
from contextlib import redirect_stderr
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bin'))
spec=importlib.util.spec_from_file_location('zoom_launch',ROOT/'bin/zoom-camera.py')
launch=importlib.util.module_from_spec(spec);spec.loader.exec_module(launch)


class ZoomLaunch(unittest.TestCase):
    def test_prepare_before_exec_and_preserve_unrelated_environment(self):
        order=[]
        def ready(**kwargs):
            order.append('prepare');self.assertEqual(kwargs,{'wait_seconds':60})
            return {'ready':True,'library':'/fixture/libpw-v4l2.so'}
        def execute(*args):order.append('exec')
        with patch.dict(os.environ,LD_PRELOAD='/fixture/other.so',PIPEWIRE_V4L2_TARGET='obsolete'), \
                patch.object(launch,'ensure',side_effect=ready),patch.object(launch.os,'execve',side_effect=execute) as run, \
                patch.object(sys,'argv',['zoom-camera.py','--fixture']):
            before=dict(os.environ);launch.main();self.assertEqual(dict(os.environ),before)
        self.assertEqual(order,['prepare','exec'])
        command,argv,environment=run.call_args.args
        self.assertEqual(command,'/usr/bin/zoom');self.assertEqual(argv,['/usr/bin/zoom','--fixture'])
        self.assertEqual(environment['LD_PRELOAD'],'/fixture/libpw-v4l2.so /fixture/other.so')
        self.assertNotIn('PIPEWIRE_V4L2_TARGET',environment)
    def test_failed_preparation_does_not_prevent_zoom_from_opening(self):
        error=io.StringIO()
        for failure in (RuntimeError('Package unavailable'),subprocess.TimeoutExpired('pacman',1),subprocess.CalledProcessError(1,'pacman')):
            with self.subTest(failure=type(failure).__name__),patch.dict(os.environ,LD_PRELOAD='/fixture/other.so'),patch.object(launch,'ensure',side_effect=failure), \
                    patch.object(launch.os,'execve') as run,patch.object(sys,'argv',['zoom-camera.py']),redirect_stderr(error):
                launch.main()
                run.assert_called_once()
                self.assertEqual(run.call_args.args[2]['LD_PRELOAD'],'/fixture/other.so')
        self.assertIn('Package unavailable',error.getvalue())


if __name__=='__main__':unittest.main()
