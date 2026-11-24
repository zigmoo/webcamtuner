"""Opt-in remote source switching on a separate publisher; frames never leave memory."""
import collections,hashlib,importlib.util,json,os,signal,subprocess,sys,threading,time,uuid
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
if os.environ.get('WEBCAMTUNER_REMOTE_LIVE')!='1':raise SystemExit('Explicit WEBCAMTUNER_REMOTE_LIVE=1 required')
sys.path.insert(0,str(ROOT/'bin'))
import camera_stream
spec=importlib.util.spec_from_file_location('remote_preview',ROOT/'bin/process_preview.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
def source_url(host, camera):
    return 'sshcam://' + host + '?' + urlencode({'camera': camera})


sources = []
for number in (1, 2):
    host = os.environ.get(f'WEBCAMTUNER_REMOTE_TEST_HOST_{number}')
    camera = os.environ.get(f'WEBCAMTUNER_REMOTE_TEST_CAMERA_{number}')
    if not host or not camera:
        raise SystemExit(f'Set WEBCAMTUNER_REMOTE_TEST_HOST_{number} and WEBCAMTUNER_REMOTE_TEST_CAMERA_{number}')
    sources.append((host, camera))
urls = [source_url(host, camera) for host, camera in sources]
missing_url = source_url(sources[0][0], '/dev/video99999')
node='webcamtuner.remote-test-'+uuid.uuid4().hex[:8]
base={'camera':urls[0],'mirror':False,'crop':{'zoom':1,'centerX':.5,'centerY':.5},'background':{'mode':os.environ.get('WEBCAMTUNER_REMOTE_EFFECT','none')},'configurationRevision':1}
servers=[];counts=collections.Counter();hashes=collections.defaultdict(set);gaps=[];previous=None;phase=0;failures=[];deadline=time.monotonic()+100;readers=[];read_errors=[];reader_stop=threading.Event()
original_publisher=camera_stream.Publisher;original_server=camera_stream.ControlServer

def server(receive,stop,render_background=None):
    value=original_server(receive,stop,render_background);servers.append(value);return value

def consume():
    import gi
    gi.require_version('Gst','1.0');from gi.repository import Gst
    Gst.init(None)
    try:
        for _ in range(70):
            nodes=json.loads(subprocess.check_output(['pw-dump'],timeout=3));matches=[n for n in nodes if n.get('info',{}).get('props',{}).get('node.name')==node]
            if matches:break
            time.sleep(.1)
        assert matches,'Private publisher was not registered'
        serial=matches[0]['info']['props']['object.serial']
        for _ in range(2):
            pipeline=Gst.parse_launch(f'pipewiresrc target-object={serial} ! video/x-raw,width=1280,height=720 ! appsink name=frames sync=false max-buffers=1 drop=true')
            pipeline.set_state(Gst.State.PLAYING);readers.append([pipeline,pipeline.get_by_name('frames'),0,set()])
        while not reader_stop.is_set():
            for reader in readers:
                sample=reader[1].emit('try-pull-sample',100*Gst.MSECOND)
                if sample:
                    buffer=sample.get_buffer();reader[2]+=1;reader[3].add(hashlib.sha256(buffer.extract_dup(0,buffer.get_size())).hexdigest())
    except Exception as error:read_errors.append(str(error))
    finally:
        for reader in readers:reader[0].set_state(Gst.State.NULL)

def record(value):
    global phase,previous
    if p.OUTPUT_HOOK:p.OUTPUT_HOOK(value)
    now=time.monotonic()
    if now>deadline:failures.append('Timed out');os.kill(os.getpid(),signal.SIGTERM);return
    if value.get('configurationError') and phase==2:
        assert value['camera']==urls[1], 'Failed replacement changed the source'
        phase=3;servers[0].receive({**base,'camera':urls[0],'configurationRevision':4})
        print('PASS missing remote camera rejected; prior source retained',flush=True)
    if 'frame' not in value:return
    if previous is not None and phase in (1,2,3):gaps.append(now-previous)
    previous=now
    camera=value['camera'];counts[camera]+=1;hashes[camera].add(hashlib.sha256(value['frame'].encode()).hexdigest())
    if phase==0 and counts[urls[0]]>=30:
        phase=1;threading.Thread(target=consume,daemon=True).start()
        servers[0].receive({**base,'camera':urls[1],'configurationRevision':2})
    elif phase==1 and camera==urls[1] and counts[urls[1]]>=30:
        phase=2;servers[0].receive({**base,'camera':missing_url,'configurationRevision':3})
    elif phase==3 and camera==urls[0] and value.get('configurationRevision')==4:
        phase=4
        print('PASS switched back to first remote source without replacing publisher',flush=True)
        os.kill(os.getpid(),signal.SIGTERM)

scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('remote-compositor-'+uuid.uuid4().hex[:8]);scratch.mkdir()
os.environ['WEBCAMTUNER_RUNTIME_ROOT']=str(scratch)
try:
    with patch.object(camera_stream,'Publisher',lambda:original_publisher(node=node)),patch.object(camera_stream,'ControlServer',server),patch.object(p,'emit',record):
        p.run(base,publish=True)
finally:reader_stop.set();time.sleep(.4)
assert not failures and phase==4,(phase,failures)
assert len(servers)==1 and all(counts[url]>=30 for url in urls),counts
assert not read_errors and len(readers)==2 and all(r[2]>=30 and len(r[3])>=15 for r in readers),(read_errors,[(r[2],len(r[3])) for r in readers])
assert max(gaps)<1.5, max(gaps)
print(json.dumps({'result':'PASS','compositorFrames':dict(counts),'uniqueFrames':{k:len(v) for k,v in hashes.items()},'independentReaders':[(r[2],len(r[3])) for r in readers],'maxSwitchGapSeconds':round(max(gaps),3),'privateNode':node,'effect':base['background']['mode']}),flush=True)
