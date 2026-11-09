"""Snapshots retain source crop detail and the applied mirror/background look."""
import importlib.util,os,tempfile,unittest
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
s=importlib.util.spec_from_file_location('preview',Path(__file__).resolve().parent.parent/'bin/process_preview.py');preview=importlib.util.module_from_spec(s);s.loader.exec_module(preview)

class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.scratch=tempfile.TemporaryDirectory(dir=os.environ['WEBCAMTUNER_TEST_ROOT'])
        self.original=os.environ.get('WEBCAMTUNER_SNAPSHOT_ROOT')
        os.environ['WEBCAMTUNER_SNAPSHOT_ROOT']=str(Path(self.scratch.name)/'photos')
    def tearDown(self):
        if self.original is None:os.environ.pop('WEBCAMTUNER_SNAPSHOT_ROOT',None)
        else:os.environ['WEBCAMTUNER_SNAPSHOT_ROOT']=self.original
        self.scratch.cleanup()
    def test_full_source_crop_is_mirrored_and_background_crop_applied(self):
        self.assertFalse(preview.snapshot_files.directory(create=False).exists())
        frame=np.zeros((2160,3840,3),dtype=np.uint8)
        frame[:,:1920]=(20,70,200);frame[:,1920:]=(200,70,20)
        matte=np.zeros((540,960,1),dtype=np.float32);matte[180:360,320:640]=1
        background=np.zeros((200,400,3),dtype=np.uint8);background[:,:200]=(0,0,255);background[:,200:]=(0,255,0)
        settings={'crop':{'zoom':2,'centerX':.5,'centerY':.5},'mirror':True,'background':{'mode':'image','crop':{'zoom':2,'centerX':.75,'centerY':.5}}}
        saved=preview.save_processed_snapshot(frame,matte,settings,background)
        self.assertEqual((saved['width'],saved['height']),(1920,1080))
        path=Path(saved['path']);self.assertEqual(path.stat().st_mode&0o777,0o600)
        with Image.open(path) as image:
            self.assertEqual(image.size,(1920,1080))
            self.assertLess(np.abs(np.array(image.getpixel((10,10)))-[0,255,0]).max(),4)
            self.assertLess(np.abs(np.array(image.getpixel((480,540)))-[20,70,200]).max(),4)
            self.assertLess(np.abs(np.array(image.getpixel((1440,540)))-[200,70,20]).max(),4)
        self.assertFalse(list(path.parent.glob('*.partial')))
    def test_snapshot_keeps_free_foreground_placement(self):
        frame=np.zeros((720,1280,3),dtype=np.uint8);frame[300:420,600:680]=(0,0,255)
        matte=np.zeros((720,1280,1),dtype=np.float32);matte[300:420,600:680]=1
        background=np.full((720,1280,3),(0,255,0),dtype=np.uint8)
        settings={'crop':{'zoom':1,'centerX':.5,'centerY':.5},'mirror':True,'foreground':{'x':.4,'y':0},'background':{'mode':'image'}}
        saved=preview.save_processed_snapshot(frame,matte,settings,background)
        with Image.open(saved['path']) as image:
            self.assertLess(np.abs(np.array(image.getpixel((120,360)))-[255,0,0]).max(),4)
            self.assertLess(np.abs(np.array(image.getpixel((640,360)))-[0,255,0]).max(),4)

    def test_original_snapshot_and_unique_names(self):
        frame=np.full((120,200,3),80,dtype=np.uint8)
        settings={'crop':{'zoom':1,'centerX':.5,'centerY':.5},'mirror':False,'background':{'mode':'none'}}
        one=preview.save_processed_snapshot(frame,None,settings,None)
        two=preview.save_processed_snapshot(frame,None,settings,None)
        self.assertNotEqual(one['path'],two['path'])
        self.assertTrue(Path(one['path']).exists() and Path(two['path']).exists())
    def test_snapshot_includes_enabled_label_at_requested_opacity(self):
        frame=np.zeros((360,640,3),dtype=np.uint8)
        matte=np.zeros((360,640,1),dtype=np.float32)
        background=np.full_like(frame,30)
        settings={'crop':{'zoom':1,'centerX':.5,'centerY':.5},'mirror':True,'background':{'mode':'image','labelOverlay':{'enabled':True,'opacity':.75,'text':'Sunrise'}}}
        saved=preview.save_processed_snapshot(frame,matte,settings,background)
        with Image.open(saved['path']) as photo:
            pixels=np.asarray(photo)
            self.assertLess(abs(int(pixels[20,20,0])-30),3)
            self.assertGreater(int(pixels[-60:].max()),150)
    def test_effect_snapshot_does_not_fall_back_to_unprocessed_frame(self):
        settings={'crop':{'zoom':1,'centerX':.5,'centerY':.5},'mirror':True,'background':{'mode':'image'}}
        with self.assertRaises(ValueError):preview.save_processed_snapshot(np.zeros((90,160,3),np.uint8),None,settings,None)
        self.assertFalse(preview.snapshot_files.directory(create=False).exists())
if __name__=='__main__':unittest.main()
