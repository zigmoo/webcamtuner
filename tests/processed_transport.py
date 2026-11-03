"""Actual appsrc -> PipeWire -> two readers, with generated labelled pixels only."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid
import numpy as np
import cv2
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'bin'))
from camera_stream import Publisher
import gi
gi.require_version('Gst','1.0')
from gi.repository import Gst
Gst.init(None)
name='webcamtuner.verify.'+uuid.uuid4().hex[:8]
publisher=Publisher(1280,720,node=name)
stop=threading.Event()
errors=[]
def produce():
    n=0
    try:
        while not stop.is_set():
            image=np.zeros((720,1280,3),dtype=np.uint8);image[:]=(30,120,220)
            cv2.rectangle(image,(n%260,30),(n%260+40,65),(200,20,20),-1)
            cv2.putText(image,'COMPOSED',(15,150),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,255,255),2)
            publisher.push(image);n+=1;stop.wait(1/30)
    except BaseException as e:errors.append(str(e))
thread=threading.Thread(target=produce);thread.start()
time.sleep(1) # Readers join a publisher that is already running.
readers=[]
class Reader:
    def __init__(self, serial):
        self.frames=0;self.hashes=set();self.label=False
        self.pipeline=Gst.parse_launch('pipewiresrc target-object='+str(serial)+' ! video/x-raw,width=1280,height=720,framerate=30/1 ! videoconvert ! video/x-raw,format=BGR ! appsink name=frames sync=false max-buffers=1 drop=true')
        self.sink=self.pipeline.get_by_name('frames')
        self.pipeline.set_state(Gst.State.PLAYING)
    def sample(self):
        value=self.sink.emit('try-pull-sample',100*Gst.MSECOND)
        if value:
            data=value.get_buffer().extract_dup(0,value.get_buffer().get_size())
            self.frames+=1;self.hashes.add(hashlib.sha256(data).hexdigest())
            image=np.frombuffer(data,np.uint8).reshape(720,1280,3)
            self.label=self.label or bool(np.any(np.all(image[130:155]>200,axis=2)))
            assert np.allclose(image[5,5],(30,120,220),atol=7), image[5,5]
    def close(self):self.pipeline.set_state(Gst.State.NULL)
try:
    deadline=time.monotonic()+5;node=None
    while time.monotonic()<deadline:
        dump=json.loads(subprocess.check_output(['pw-dump']))
        node=next((x for x in dump if x.get('info',{}).get('props',{}).get('node.name')==name),None)
        if node:break
        time.sleep(.1)
    assert node,'Publisher did not register'
    serial=node['info']['props']['object.serial']
    readers=[Reader(serial),Reader(serial)]
    deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        for reader in readers:reader.sample()
    assert all(r.frames>=60 and len(r.hashes)>20 and r.label for r in readers),[(r.frames,len(r.hashes),r.label) for r in readers]
    before=readers[1].frames;readers[0].close();readers[0]=Reader(serial)
    deadline=time.monotonic()+2
    while time.monotonic()<deadline:
        for reader in readers:reader.sample()
    assert readers[0].frames>=40 and readers[1].frames-before>=40
    print(json.dumps({'result':'PASS','readerFrames':[r.frames for r in readers],'labelPixels':True,'movingPixels':True,'reopenIsolation':True,'cameraOpened':False}))
finally:
    stop.set();thread.join(3)
    for reader in readers:reader.close()
    publisher.close()
assert not errors,errors
