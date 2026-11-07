"""A closed controls window still observes output failure; Stop cancels Start."""
import json
import os
from pathlib import Path
import subprocess
import uuid

root=Path(__file__).resolve().parents[1]
scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('output-lifecycle-'+uuid.uuid4().hex[:8])
(scratch/'bin').mkdir(parents=True)
state=scratch/'backend.json';state.write_text(json.dumps({'published':True,'processed':True}))
log=scratch/'calls.jsonl'
(scratch/'bin/output-control.py').write_text('''import json,pathlib,sys
root=pathlib.Path(__file__).resolve().parent.parent
action=sys.argv[1]
with (root/'calls.jsonl').open('a') as f:f.write(json.dumps(action)+'\\n')
path=root/'backend.json'
if action=='stop-output':path.write_text(json.dumps({'published':False,'processed':True,'message':'Stopped'}))
print(json.dumps({'enabled':False} if action=='zoom-status' else json.loads(path.read_text())))
''')
qml='''import QtQuick
import QtQuick.Window
import Quickshell
import Quickshell.Io
import QtTest
import "UI_PATH" as Tuner
ShellRoot {
 FileView {id:backend;path:STATE_PATH;blockLoading:true}
 FileView {id:calls;path:LOG_PATH}
 Window {visible:true;width:200;height:100}
 Tuner.OutputControl {id:output;pluginRoot:FAKE_PATH;panelOpen:false;configuration:({camera:"/dev/fixture"})}
 TestCase {
  name:"OutputLifecycle";when:true
  function test_01_closed_window_observes_publisher_exit(){
   tryCompare(output,"published",true,3000)
   verify(!output.panelOpen)
   backend.setText('{"published":false,"processed":true}')
   tryCompare(output,"published",false,6000)
  }
  function test_02_stop_cancels_pending_start(){
   tryVerify(function(){return !output.busy},3000)
   output.start();verify(output.startingCamera)
   output.stop();verify(output.stopping)
   tryCompare(output,"stopping",false,3000)
   calls.reload();wait(50)
   verify(calls.text().indexOf('"stop-output"')>=0)
   verify(calls.text().indexOf('"start-output"')<0)
   verify(!output.published)
  }
  function cleanupTestCase(){console.log("OUTPUT LIFECYCLE FAIL COUNT",qtest_results.failCount);Qt.callLater(function(){Qt.quit()})}
 }
}'''
for key,value in {'UI_PATH':(root/'ui').as_uri(),'STATE_PATH':str(state),'LOG_PATH':str(log),'FAKE_PATH':str(scratch)}.items():
 qml=qml.replace('"'+key+'"',json.dumps(value)).replace(key,json.dumps(value))
(scratch/'shell.qml').write_text(qml)
result=subprocess.run(['quickshell','-p',str(scratch)],env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',QT_FORCE_STDERR_LOGGING='1'),capture_output=True,text=True,timeout=15)
text=result.stdout+result.stderr
if result.returncode or 'OUTPUT LIFECYCLE FAIL COUNT 0' not in text:raise SystemExit(text[-6000:])
print('PASS: closed-window publisher failure clears live state; Stop cancels pending Start and confirms stopped output')
