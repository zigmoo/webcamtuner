#!/usr/bin/env python3
"""Read published output through a real consumer; never select a physical source."""
import argparse
import base64
from collections import deque
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
sys.dont_write_bytecode = True
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend',choices=['pipewire','v4l2'],default='pipewire')
    parser.add_argument('--loaded',action='store_true')
    parser.add_argument('--frames',type=int,default=0)
    parser.add_argument('--node-serial')
    args=parser.parse_args()
    from camera_stream import NODE
    dump=json.loads(subprocess.check_output(['pw-dump'],timeout=5))
    node=next((n for n in dump if n.get('type')=='PipeWire:Interface:Node' and n.get('info',{}).get('props',{}).get('node.name')==NODE),None)
    if node is None:raise RuntimeError('Camera output is stopped. Start camera output in Setup or Test.')
    serial=str(node['info']['props']['object.serial'])
    if args.node_serial is not None and args.node_serial!=serial:
        raise RuntimeError('The published camera changed. Reconnecting to its new source is required.')
    if args.backend=='v4l2':
        from camera_adapter import library_path
        library=library_path()
        if not library.is_file():raise RuntimeError('Enable the user-only Zoom camera adapter in Setup first.')
        if not args.loaded:
            preload=str(library)+(os.pathsep+os.environ['LD_PRELOAD'] if os.environ.get('LD_PRELOAD') else '')
            environment=dict(os.environ,LD_PRELOAD=preload,PIPEWIRE_V4L2_TARGET=serial)
            os.execve(sys.executable,[sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--loaded'],environment)
        if os.environ.get('PIPEWIRE_V4L2_TARGET')!=serial or 'libpw-v4l2.so' not in Path('/proc/self/maps').read_text():
            raise RuntimeError('V4L2 adapter is not active; refusing to open a physical camera.')
    import gi
    gi.require_version('Gst','1.0')
    from gi.repository import Gst
    import cv2
    import numpy as np
    Gst.init(None)
    source='pipewiresrc use-bufferpool=false always-copy=true min-buffers=4 max-buffers=8 target-object='+serial if args.backend=='pipewire' else 'v4l2src device=/dev/video0 io-mode=mmap'
    pipeline=Gst.parse_launch(source+' ! video/x-raw,width=1280,height=720,framerate=30/1 ! videoconvert ! video/x-raw,format=BGR ! appsink name=frames sync=false enable-last-sample=false max-buffers=1 drop=true')
    sink=pipeline.get_by_name('frames')
    running=True
    def stop(*_):
        nonlocal running
        running=False
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    times=deque(maxlen=90);count=0;last_emit=0;last_frame=time.monotonic()
    try:
        if pipeline.set_state(Gst.State.PLAYING)==Gst.StateChangeReturn.FAILURE:raise RuntimeError('Camera consumer could not start.')
        while running:
            message=pipeline.get_bus().pop_filtered(Gst.MessageType.ERROR|Gst.MessageType.EOS)
            if message:
                raise RuntimeError(str(message.parse_error()[0]) if message.type==Gst.MessageType.ERROR else 'Camera output ended.')
            sample=sink.emit('try-pull-sample',500*Gst.MSECOND)
            now=time.monotonic()
            if sample is None:
                if now-last_frame>4:raise RuntimeError('The consumer is not receiving camera frames.')
                continue
            count+=1;times.append(now);last_frame=now
            if now-last_emit<.1 and not (args.frames and count>=args.frames):
                sample=None
                continue
            caps=sample.get_caps().get_structure(0);w=caps.get_value('width');h=caps.get_value('height')
            buffer=sample.get_buffer();data=buffer.extract_dup(0,buffer.get_size())
            sample=None;buffer=None
            pixels=np.frombuffer(data,np.uint8).reshape(h,w,3)
            okay,jpeg=cv2.imencode('.jpg',cv2.resize(pixels,(640,360)),[cv2.IMWRITE_JPEG_QUALITY,72])
            if not okay:raise RuntimeError('Could not display the received camera frame.')
            fps=(len(times)-1)/(times[-1]-times[0]) if len(times)>1 else 0
            record={'frame':base64.b64encode(jpeg).decode('ascii'),'width':w,'height':h,'receiveFps':fps,'receivedFrames':count,'backend':args.backend,'node':NODE,'nodeId':node['id'],'nodeSerial':serial}
            print(json.dumps(record,separators=(',',':')),flush=True);last_emit=now
            if args.frames and count>=args.frames:break
    finally:pipeline.set_state(Gst.State.NULL)


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        print(json.dumps({'error':str(error)[:800]}),flush=True)
        raise SystemExit(1)
