"""Real consumer processes retry, identify their source and recover from stuck shutdown."""
import base64,io,json,os,subprocess,uuid
from pathlib import Path
from PIL import Image
root=Path(__file__).resolve().parents[1]
scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('readback-'+uuid.uuid4().hex[:8]);(scratch/'bin').mkdir(parents=True)
pixels=io.BytesIO();Image.new('RGB',(20,12),'green').save(pixels,'JPEG');frame=base64.b64encode(pixels.getvalue()).decode()
launcher=scratch/'bin/preview-python';launcher.write_text('#!/bin/bash\nexec python3 "$@"\n');launcher.chmod(0o755)
(scratch/'bin/readback-camera.py').write_text('''import json,os,signal,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
counter=root/'starts';n=int(counter.read_text())+1 if counter.exists() else 1;counter.write_text(str(n))
serial=sys.argv[sys.argv.index('--node-serial')+1]
if n==1 or serial=='999':print(json.dumps({'error':'Fixture consumer not ready'}),flush=True);sys.exit(1)
signal.signal(signal.SIGTERM,signal.SIG_IGN)
count=0
while True:
 count+=1
 print(json.dumps({'frame':FRAME,'width':20,'height':12,'nodeId':12,'nodeSerial':serial,'receivedFrames':count,'receiveFps':10}),flush=True)
 time.sleep(.1)
'''.replace('FRAME',repr(frame)))
qml='''import QtQuick
import Quickshell
import QtTest
import "UI_PATH" as Tuner
ShellRoot {
 FloatingWindow {visible:true;implicitWidth:640;implicitHeight:500
  Tuner.ReadbackProbe {id:p;anchors.fill:parent;active:true;targetSerial:"100";pluginRoot:FAKE_ROOT}
 }
 TestCase {id:test;when:false}
 property int phase:0
 property var oldPid:0
 function expect(ok,msg){if(!ok){console.log("FAIL: "+msg);Qt.exit(1)}}
 Timer {interval:100;running:true;repeat:true;onTriggered:{
  if(phase===0&&p.connected){expect(p.measurement.nodeSerial==="100","initial source confirmed");expect(test.findChild(p,"consumerConnection").text.indexOf(String(p.consumerPid))>=0,"consumer identifier is complete, not rounded");oldPid=p.consumerPid;p.targetSerial="200";phase=1}
  else if(phase===1&&p.connected&&p.measurement.nodeSerial==="200"){
   expect(p.consumerPid!==oldPid,"stuck previous process was replaced");oldPid=p.consumerPid;p.active=false;p.active=true;phase=2
  }
  else if(phase===2&&p.connected&&p.consumerPid!==oldPid){
   expect(test.findChild(p,"consumerFrame").status===Image.Ready,"actual received image decoded");p.targetSerial="999";phase=3
  }
  else if(phase===3&&p.attempts===3&&!p.consumerPid&&p.connectionState==="disconnected"){
   expect(test.findChild(p,"retryConsumer").enabled,"bounded failures leave Retry enabled")
   console.log("PASS: actual consumer retry, decoded frames, source change, rapid hide/reopen, stuck SIGTERM cleanup and bounded failure")
   Qt.quit()
  }
 }}
 Timer {interval:12000;running:true;onTriggered:{console.log("FAIL: lifecycle timeout phase "+phase+" "+p.connectionState+" attempts "+p.attempts);Qt.exit(1)}}
}'''.replace('"UI_PATH"',json.dumps((root/'ui').as_uri())).replace('FAKE_ROOT',json.dumps(str(scratch)))
(scratch/'shell.qml').write_text(qml)
r=subprocess.run(['qs','-p',str(scratch/'shell.qml')],env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software'),capture_output=True,text=True,timeout=16)
out=r.stdout+r.stderr
if r.returncode or 'PASS:' not in out:raise SystemExit(out[-5000:])
print('PASS: consumer processes connect/retry, decode pixels, change source, survive rapid reopen and bound stuck-process shutdown/failure retries')
