"""Burst requests stay correlated, ordered and survive an individual failure."""
import os
from pathlib import Path
import subprocess
import uuid
root = Path(__file__).resolve().parent.parent
scratch = Path(os.environ['WEBCAMTUNER_TEST_ROOT']) / ('bridge-' + uuid.uuid4().hex)
scratch.mkdir(parents=True)
harness = scratch / 'shell.qml'
harness.write_text('''import QtQuick
import Quickshell
import "''' + (root/'ui').as_uri() + '''" as Tuner
ShellRoot {
 property var replies:[]
 function check() {
  if(replies.length<4)return
  if(JSON.stringify(replies)!==JSON.stringify(["read","backgrounds","failed","devices"])) {console.log("FAIL: "+JSON.stringify(replies));Qt.exit(1)}
  console.log("PASS: queued replies retain correlation and recover after failure");Qt.quit()
 }
 Tuner.Bridge {
  id:bridge
  onReceived:function(action,result){
   if(action==="read" && !result.profiles) Qt.exit(1)
   if(action==="backgrounds" && !result.directory) Qt.exit(1)
   if(action==="devices" && !result.aliases) Qt.exit(1)
   replies=replies.concat([action]);check()
  }
  onFailed:function(message){replies=replies.concat(["failed"]);check()}
 }
 Component.onCompleted:{
  bridge.request("read",[])
  bridge.request("backgrounds",[])
  bridge.request("not-a-real-operation",[])
  bridge.request("devices",[])
  if(!bridge.busy){console.log("FAIL: requests not reserved synchronously");Qt.exit(1)}
 }
 Timer{interval:10000;running:true;onTriggered:Qt.exit(1)}
}''')
env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',WEBCAMTUNER_CONFIG_ROOT=str(scratch/'profiles'),XDG_DATA_HOME=str(scratch/'data'),XDG_CACHE_HOME=str(scratch/'cache'))
result=subprocess.run(['qs','-p',str(harness)],env=env,capture_output=True,text=True,timeout=15)
output=result.stdout+result.stderr
if result.returncode or 'PASS: queued replies' not in output:raise SystemExit(output[-4000:])
print('PASS: queued replies retain correlation and recover after failure')
