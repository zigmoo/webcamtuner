"""Detect mixed-frame scanlines and held-buffer changes on an isolated PipeWire core.

Only generated grayscale frame IDs are used. The production camera, PipeWire
session and application settings are never changed; no image is written.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


def scanline_id(codes):
    import numpy as np
    wrong = np.flatnonzero(codes != codes[0])
    if len(wrong):
        raise AssertionError(json.dumps({'mixedScanlines':len(wrong),'firstWrongRow':int(wrong[0]),'lastWrongRow':int(wrong[-1]),'ids':np.unique(codes).tolist()}))
    return int(codes[0])


def worker(seconds, rate):
    import gi
    gi.require_version('Gst', '1.0')
    gi.require_version('GstVideo', '1.0')
    from gi.repository import Gst, GstVideo
    import numpy as np
    sys.path.insert(0, str(ROOT/'bin'))
    from camera_stream import Publisher
    Gst.init(None)
    for boundary in (1,240,480,719):
        corrupt=np.full(720,7);corrupt[boundary:]=8
        try:scanline_id(corrupt)
        except AssertionError:pass
        else:raise AssertionError('Integrity detector missed an injected tear')
    print('Private integrity: starting publisher',flush=True)
    publisher = Publisher(node='webcamtuner.integrity')
    print('Private integrity: publisher created',flush=True)
    stop = threading.Event()
    failures = []
    produced = []
    def produce():
        n = 1
        try:
            while not stop.is_set():
                # Every scanline contains the same frame ID. A split between two
                # frame generations, even in the bottom third, changes its ID.
                bits = ((n % 256) >> np.arange(8)) & 1
                row = np.repeat(bits*170+40, 128)
                frame = np.empty((720,1280,3), np.uint8)
                frame[:,:1024] = row[None,:,None]
                frame[:,1024:] = ((np.arange(720)%32)*6+30)[:,None,None]
                publisher.push(frame)
                # Immediately reuse the caller's array: the publisher must own
                # immutable frame data after push returns.
                frame[:] = 0
                produced.append(n)
                n += 1
                stop.wait(1/rate)
        except BaseException as error:
            failures.append(str(error))
    thread = threading.Thread(target=produce, daemon=True)
    readers = []
    thread.start()
    try:
        for i, pooled in enumerate((False, True)):
            pipeline = Gst.parse_launch(
                'pipewiresrc use-bufferpool='+str(pooled).lower()+' min-buffers=4 max-buffers=8 '
                'target-object=webcamtuner.integrity '
                'stream-properties="props,node.name=webcamtuner.integrity.reader'+str(i)+'" ! '
                'video/x-raw,format=YUY2,width=1280,height=720,framerate=30/1 ! '
                'appsink name=frames sync=false enable-last-sample=false max-buffers=1 drop=true')
            pipeline.set_state(Gst.State.PLAYING)
            readers.append({'pipeline':pipeline, 'sink':pipeline.get_by_name('frames'), 'frames':0, 'ids':set(), 'pooled':pooled})
            print('Private integrity: reader created',i,flush=True)
        # Only private policy runs here; no hardware monitors are loaded.
        deadline = time.monotonic()+8
        while time.monotonic()<deadline:
            dump = json.loads(subprocess.check_output(['pw-dump'], timeout=3))
            names = {o['id']:o.get('info',{}).get('props',{}).get('node.name') for o in dump if o.get('type')=='PipeWire:Interface:Node'}
            ports = [o for o in dump if o.get('type')=='PipeWire:Interface:Port']
            output = next((o['id'] for o in ports if names.get(o['info']['props'].get('node.id'))=='webcamtuner.integrity' and o['info']['props'].get('port.direction')=='out'),None)
            inputs = [o['id'] for o in ports if str(names.get(o['info']['props'].get('node.id'), '')).startswith('webcamtuner.integrity.reader') and o['info']['props'].get('port.direction')=='in']
            if output and len(inputs)==2: break
            time.sleep(.1)
        else:
            raise AssertionError('Private test ports did not appear: '+str(names))
        began = time.monotonic()
        last = [0,0]
        while time.monotonic()-began < seconds:
            for i, reader in enumerate(readers):
                error = reader['pipeline'].get_bus().pop_filtered(Gst.MessageType.ERROR)
                if error: raise RuntimeError(str(error.parse_error()[0]))
                sample = reader['sink'].emit('try-pull-sample', 100*Gst.MSECOND)
                if sample is None: continue
                buffer = sample.get_buffer()
                info = GstVideo.VideoInfo.new_from_caps(sample.get_caps())
                data = buffer.extract_dup(0,buffer.get_size())
                # In YUY2 each even byte is luma. All test colors are grayscale.
                pixels = np.ndarray((720,1280),np.uint8,buffer=data,strides=(info.stride[0],2))
                bits = pixels[:,64+128*np.arange(8)] > 120
                codes = (bits * (1 << np.arange(8))).sum(axis=1)
                code = scanline_id(codes)
                assert code != 0 or len(produced)>=256, 'Caller memory was reused or an empty frame escaped'
                reader['ids'].add(code)
                reader['frames'] += 1
                last[i] = time.monotonic()
                if reader['pooled']:
                    # A zero-copy consumer can hold a frame while new ones arrive.
                    # Its pixels must stay unchanged until it releases the buffer.
                    time.sleep(.045)
                    assert data == buffer.extract_dup(0,buffer.get_size()), 'A held PipeWire frame changed in place'
                sample = None
                buffer = None
            if failures: raise RuntimeError(failures[0])
        assert all(r['frames']>=seconds*3 and len(r['ids'])>=seconds*2 for r in readers),[(r['frames'],len(r['ids'])) for r in readers]
        print(json.dumps({'result':'PASS','seconds':round(time.monotonic()-began,2),'inputRate':rate,'produced':len(produced),'readers':[{'pooled':r['pooled'],'frames':r['frames'],'distinctIds':len(r['ids'])} for r in readers],'mixedScanlines':0,'heldBufferChanges':0,'productionSessionTouched':False,'imagesSaved':False}),flush=True)
    finally:
        stop.set()
        thread.join(3)
        for r in readers:r['pipeline'].set_state(Gst.State.NULL)
        publisher.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--seconds',type=float,default=20)
    parser.add_argument('--rate',type=float,default=30)
    args = parser.parse_args()
    if not (1 <= args.seconds <= 120 and 1 <= args.rate <= 60):
        parser.error('Use 1–120 seconds and 1–60 frames/second')
    if args.worker:
        directory = os.environ.get('WEBCAMTUNER_PRIVATE_INTEGRITY')
        if not directory or directory != os.environ.get('XDG_RUNTIME_DIR') or directory != os.environ.get('PIPEWIRE_RUNTIME_DIR') \
                or not Path(directory).is_absolute() or not Path(directory).name.startswith('publisher-integrity-'):
            raise RuntimeError('Integrity worker requires its private core')
        return worker(args.seconds,args.rate)
    base = Path(os.environ['WEBCAMTUNER_TEST_ROOT'])
    with tempfile.TemporaryDirectory(prefix='publisher-integrity-',dir=base) as directory:
        env=dict(os.environ,XDG_RUNTIME_DIR=directory,PIPEWIRE_RUNTIME_DIR=directory,PIPEWIRE_REMOTE='pipewire-0',WEBCAMTUNER_PRIVATE_INTEGRITY=directory,
                 XDG_CONFIG_HOME=directory+'/config',XDG_STATE_HOME=directory+'/state',XDG_CACHE_HOME=directory+'/cache',XDG_DATA_HOME=directory+'/data')
        with open(Path(directory)/'daemon.log','w+') as log:
            daemon=subprocess.Popen(['pipewire','-P','{ support.dbus = false }'],env=env,stdout=log,stderr=log)
            policy=None
            try:
                for _ in range(50):
                    if (Path(directory)/'pipewire-0').exists():break
                    if daemon.poll() is not None:raise RuntimeError('Private PipeWire could not start')
                    time.sleep(.1)
                policy=subprocess.Popen(['wireplumber','--profile','policy'],env=env,stdout=log,stderr=log)
                try:
                    subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker','--seconds',str(args.seconds),'--rate',str(args.rate)],env=env,check=True,timeout=args.seconds+20)
                except BaseException:
                    log.seek(0)
                    print(log.read()[-2500:],file=sys.stderr)
                    raise
            finally:
                if policy is not None:
                    policy.terminate()
                    policy.wait(timeout=3)
                daemon.terminate()
                daemon.wait(timeout=3)


if __name__=='__main__':main()
