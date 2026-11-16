"""Closed-window/live/start/upgrade preparation is automatic and failures preserve video."""
import json
import os
from pathlib import Path
import subprocess
import uuid

ROOT=Path(__file__).resolve().parents[1]
scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('adapter-autostart-'+uuid.uuid4().hex[:8])
(scratch/'bin').mkdir(parents=True)
state=scratch/'backend.json'
state.write_text(json.dumps({'published':True,'processed':True,'version':'one','ready':False,'zoomInstalled':True,'enabled':False,'normalLauncher':False,'attempts':0,'fail':False}))
(scratch/'bin/output-control.py').write_text('''import json,pathlib,sys,time
path=pathlib.Path(__file__).resolve().parent.parent/'backend.json'
value=json.loads(path.read_text());action=sys.argv[1]
with (path.parent/'calls.jsonl').open('a') as log:log.write(json.dumps({'action':action,'state':value})+'\\n')
if action in ('ensure-zoom','setup-zoom'):
 value['attempts']+=1;path.write_text(json.dumps(value));time.sleep(.15)
 if value['fail']:
  print(json.dumps({'message':'Fixture download unavailable'}));raise SystemExit(1)
 value['ready']=True
 if not value['normalLauncher']:value['enabled']=True
 path.write_text(json.dumps(value))
elif action=='start-output':value['published']=True;path.write_text(json.dumps(value))
print(json.dumps(value))
''')
(scratch/'bin/stream-client.py').write_text("import json,pathlib;print((pathlib.Path(__file__).resolve().parent.parent/'backend.json').read_text())\n")
qml='''import QtQuick
import QtQuick.Window
import Quickshell
import Quickshell.Io
import QtTest
import "UI_PATH" as Tuner
ShellRoot {
 FileView {id:backend;path:STATE_PATH;blockLoading:true;blockAllReads:true}
 Window {visible:true;width:300;height:160}
 Tuner.OutputControl {id:output;pluginRoot:FAKE_PATH;panelOpen:false}
 TestCase {
  name:"AdapterAutostart";when:true
  function value(){backend.reload();return JSON.parse(backend.text())}
  function set(patch){backend.setText(JSON.stringify(Object.assign(value(),patch)))}
  function test_01_live_output_prepares_while_controls_are_closed(){
   tryVerify(function(){return output.adapter.ready&&output.adapter.enabled},5000)
   verify(output.published);compare(value().attempts,1);verify(!output.panelOpen)
   compare(output.adapterError,"")
  }
  function test_02_upgrade_is_repaired_without_opening_controls(){
   set({version:"two",ready:false,enabled:true})
   output.request("zoom-status")
   tryVerify(function(){return output.adapter.ready&&output.adapter.version==="two"},5000)
   compare(value().attempts,2);verify(output.published)
  }
  function test_03_failed_download_is_bounded_and_does_not_stop_video(){
   set({version:"three",ready:false,fail:true})
   output.request("zoom-status")
   tryVerify(function(){return output.adapterError!==""},5000)
   compare(value().attempts,3);verify(output.published);verify(!output.busy)
   for(var i=0;i<3;i++)output.maybePrepareAdapter()
   output.request("zoom-status");wait(350)
   compare(value().attempts,3);verify(output.published)
   set({fail:false});output.prepareAdapter(false)
   tryVerify(function(){return output.adapter.ready&&output.adapterError===""},5000)
   compare(value().attempts,4)
  }
  function test_04_explicit_normal_launcher_is_preserved(){
   set({normalLauncher:true,enabled:false})
   output.request("zoom-status")
   tryVerify(function(){return output.adapter.normalLauncher===true},3000)
   output.maybePrepareAdapter();wait(200)
   compare(value().attempts,4);verify(output.adapter.ready);verify(!output.adapter.enabled)
  }
  function test_05_stopped_camera_defers_preparation_until_start(){
   set({published:false,version:"four",ready:false,normalLauncher:false})
   output.request("status");output.request("zoom-status")
   tryVerify(function(){return !output.published&&output.adapter.version==="four"},3000)
   output.maybePrepareAdapter();wait(200);compare(value().attempts,4)
   output.configuration={camera:"/dev/fixture"};verify(output.start())
   tryVerify(function(){return output.published&&output.adapter.ready},6000)
   compare(value().attempts,5)
  }
  function cleanupTestCase(){console.log("ADAPTER AUTOSTART FAIL COUNT",qtest_results.failCount);Qt.callLater(function(){Qt.quit()})}
  function cleanup(){console.log("ADAPTER STATE",JSON.stringify(output.state),JSON.stringify(output.adapter),output.adapterError,output.adapterMessage,output.adapterAttemptKey,output.activeAction,output.enabled,output.adapterPreparing)}
 }
}'''
for key,value in {'UI_PATH':(ROOT/'ui').as_uri(),'STATE_PATH':str(state),'FAKE_PATH':str(scratch)}.items():
 qml=qml.replace('"'+key+'"',json.dumps(value)).replace(key,json.dumps(value))
(scratch/'shell.qml').write_text(qml)
result=subprocess.run(['quickshell','-p',str(scratch)],env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',QT_FORCE_STDERR_LOGGING='1'),capture_output=True,text=True,timeout=35)
text=result.stdout+result.stderr
if result.returncode or 'ADAPTER AUTOSTART FAIL COUNT 0' not in text:raise SystemExit(text[-7000:])
print('PASS: automatic live/start/upgrade adapter preparation; bounded failure preserves video; retry and normal-launcher preference')
