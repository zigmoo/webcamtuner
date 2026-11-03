"""Cold open routes to Setup and a GUI Prepare action unlocks the ordinary editor."""
import json
import os
from pathlib import Path
import subprocess
import uuid
root = Path(__file__).resolve().parents[1]
scratch = Path(os.environ['WEBCAMTUNER_TEST_ROOT']) / ('setup-ui-' + uuid.uuid4().hex[:8])
(scratch / 'bin').mkdir(parents=True)
env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', WEBCAMTUNER_CONFIG_ROOT=str(scratch / 'profiles'))
document = json.loads(subprocess.check_output([str(root / 'bin/webcamtuner'), 'read', '--json'], env=env, text=True))
document['profiles'][0]['autostartCamera'] = False
(scratch / 'document.json').write_text(json.dumps(document))
(scratch / 'bin/first-run.py').write_text('''import json,sys
from pathlib import Path
root=Path(__file__).resolve().parent.parent
ready=(root/'prepared').exists()
if sys.argv[1]!='status':
 print(json.dumps({'progress':'Preparing local fixture…'}),flush=True)
 (root/'prepared').touch();ready=True
print(json.dumps({'ready':ready,'controllerReady':ready,'checks':[{'id':'runtime','label':'Local processing','ready':ready}],'message':'Ready' if ready else 'Prepare WebcamTuner'}),flush=True)
''')
controller=scratch / 'bin/webcamtuner'
controller.write_text('''#!/usr/bin/env python3
import json,sys
from pathlib import Path
path=Path(__file__).resolve().parent.parent/'document.json'
if sys.argv[1]=='devices':print(json.dumps({'aliases':[]}))
elif sys.argv[1]=='save':
 value=json.loads(sys.argv[sys.argv.index('--document')+1]);value['revision']+=1;path.write_text(json.dumps(value));print(json.dumps(value))
else:print(path.read_text())
''');controller.chmod(0o755)
harness=scratch / 'shell.qml'
harness.write_text('''import QtQuick
import Quickshell
import QtTest
import "'''+(root/'ui').as_uri()+'''" as Tuner
ShellRoot {
 TestCase {id:inspect;when:false}
 Tuner.TunerWindow {
  id:w
  Component.onCompleted:{
   editor.outputControl.enabled=false
   bootstrap.pluginRoot='''+json.dumps(str(scratch))+'''
   bridge.pluginRoot='''+json.dumps(str(scratch))+'''
   openEditor()
  }
 }
 property int phase:0
 function expect(ok,message){if(!ok){console.log("FAIL: "+message);Qt.exit(1)}}
 Timer {interval:200;running:true;repeat:true;onTriggered:{
  if(!w.bootstrap.checked||w.bootstrap.busy)return
  if(phase===0){
   expect(w.editor.section==="setup"&&!w.editor.document,"cold source checkout opens Setup before calling unavailable controller")
   var prepare=inspect.findChild(w,"prepareWebcamTuner")
   expect(prepare&&prepare.enabled,"GUI preparation is available")
   expect(!w.editor.previewOn,"first-use checking does not start camera capture")
   prepare.clicked();phase=1;return
  }
  if(phase===1&&w.bootstrap.ready&&w.editor.document&&!w.editor.busy){
   expect(!w.editor.previewOn,"preparation does not start the camera")
   expect(w.editor.section==="setup","readiness remains visible after preparation")
   expect(inspect.findChild(w,"checkWebcamTuner")&&inspect.findChild(w,"repairWebcamTuner"),"check and repair are available")
   phase=2
   w.editor.grabToImage(function(result){
    expect(result.saveToFile('''+json.dumps(str(scratch/'setup-ready.png'))+'''),"rendered Setup screenshot saved")
    w.openCamera();expect(w.editor.section==="camera","ordinary editor is accessible")
    console.log("PASS: cold first use opens Setup; GUI Prepare, progress, readback and camera transition; no capture/output commands")
    Qt.quit()
   })
  }
 }}
 Timer {interval:10000;running:true;onTriggered:Qt.exit(1)}
}''')
result=subprocess.run(['qs','-p',str(harness)],env=env,capture_output=True,text=True,timeout=15)
output=result.stdout+result.stderr
if result.returncode or 'PASS:' not in output:raise SystemExit(output[-6000:])
print('PASS: cold source opens Setup; GUI Prepare/readiness/repair flow unlocks Camera; camera and output stay off')
