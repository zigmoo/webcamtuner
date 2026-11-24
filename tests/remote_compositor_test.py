"""Source replacement is asynchronous, cancellable, and preserves 4:3 composition."""
import importlib.util,threading,time,unittest,sys
from pathlib import Path
from unittest.mock import patch
import numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'bin'))
spec=importlib.util.spec_from_file_location('remote_compositor',root/'bin/process_preview.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
class RemoteCompositor(unittest.TestCase):
 def exercise(self,cancel):
  records=[];frames=[];servers=[];created=[];settings={'camera':'/dev/video101','crop':{'zoom':1,'centerX':.5,'centerY':.5},'background':{'mode':'none'},'mirror':False,'configurationRevision':1}
  class Capture:
   fps=30
   def __init__(self,camera,cancel=None):
    if camera.startswith('sshcam:'):
     time.sleep(.2)
     if cancel and cancel.is_set():raise RuntimeError('cancelled')
    self.camera=camera;self.closed=False;created.append(self)
   def next(self,previous):return np.full((240,320,3),180 if self.camera.startswith('sshcam:') else 40,np.uint8),previous+1
   def close(self):self.closed=True
  class Publisher:
   def push(self,frame):frames.append(frame.copy())
   def close(self):pass
  class Server:
   def __init__(self,receive,stop,render_background=None):self.receive=receive;servers.append(self)
   def emit(self,value):pass
   def close(self):pass
  def emit(value):
   records.append(value)
   if 'frame' not in value:return
   count=len([v for v in records if 'frame' in v])
   if count==1:servers[0].receive({**settings,'camera':'sshcam://host?camera=x','configurationRevision':2})
   if cancel and count==3:servers[0].receive({**settings,'configurationRevision':3})
  with patch.object(p,'CameraCapture',Capture),patch.object(p,'emit',emit),patch('camera_stream.ControlServer',Server),patch('camera_stream.Publisher',Publisher):p.run(settings,frame_limit=20,publish=True)
  self.assertTrue(all(c.closed for c in created))
  cameras=[r['camera'] for r in records if 'frame' in r]
  if cancel:self.assertEqual(set(cameras),{'/dev/video101'})
  else:
   self.assertGreater(cameras.index('sshcam://host?camera=x'),3,'Old frames must continue during slow SSH preparation')
   last=frames[-1];self.assertEqual(last.shape,(720,1280,3));self.assertTrue(np.all(last[:,:150]==0));self.assertTrue(np.all(last[:,200:1080]==180))
 def test_slow_replacement_keeps_old_frames_and_pads_4_by_3(self):self.exercise(False)
 def test_cancel_does_not_switch_or_leak_prepared_capture(self):self.exercise(True)
if __name__=='__main__':unittest.main()
