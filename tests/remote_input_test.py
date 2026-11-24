"""Validate source boundaries and cancellation without reaching SSH or opening cameras."""
from pathlib import Path
import sys, threading, time, unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
import remote_input as r

class RemoteSourceTests(unittest.TestCase):
    def test_structured_arguments_preserve_device_and_reject_unsafe_host(self):
        args=r.source_options('sshcam://zbook.example?camera=%2Fdev%2Fv4l%2Fby-id%2Fcamera-video-index0&size=800x600&fps=25')
        self.assertEqual(args[:4],['stream-plan','zbook.example','--camera','/dev/v4l/by-id/camera-video-index0'])
        for source in ('sshcam://user@host?camera=x','sshcam://host?camera=x&camera=y','sshcam://host?camera=x&microphone=default','http://host?camera=x','sshcam://host/path?camera=x'):
            with self.assertRaises(ValueError,msg=source):r.source_options(source)
    def test_cancelled_plan_never_activates_transport(self):
        cancellation=threading.Event();cancellation.set()
        class Child:
            pid=123
            stdout=type('Pipe',(),{'close':lambda s:None})()
            stderr=type('Pipe',(),{'close':lambda s:None})()
            def __init__(self):self.code=None
            def poll(self):return self.code
            def wait(self,timeout):self.code=0
        with patch.object(r.subprocess,'Popen',return_value=Child()) as spawn,patch.object(r.os,'killpg') as kill:
            with self.assertRaisesRegex(RuntimeError,'cancelled'):
                r.RemoteCameraInput('sshcam://host?camera=x',cancellation)
        self.assertEqual(spawn.call_count,1);kill.assert_called_once()
    def test_rejects_unsupported_plan_before_starting_capture(self):
        with patch.object(r,'read_plan',return_value={'schemaVersion':9}),patch.object(r.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError,'contract'):
                r.RemoteCameraInput('sshcam://host?camera=x')
        spawn.assert_not_called()

if __name__=='__main__':unittest.main()
