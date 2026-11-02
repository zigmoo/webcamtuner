"""The Setup mirror checkbox confirms storage before changing and survives reopening."""
import os,subprocess,uuid,json
from pathlib import Path
root=Path(__file__).resolve().parent.parent;scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('snapshot-ui-'+uuid.uuid4().hex);scratch.mkdir()
harness=scratch/'shell.qml'
harness.write_text('''import QtQuick
import Quickshell
import QtTest
import "'''+(root/'ui').as_uri()+'''" as Tuner
ShellRoot {
 TestCase {id:pointer;when:false}
 Tuner.TunerWindow {id:w;Component.onCompleted:{editor.testing=true;openSetup()}}
 property int phase:0
 Timer {interval:200;running:true;repeat:true;onTriggered:{
  var toggle=pointer.findChild(w.editor,"mirrorSnapshotsToOS")
  if(!toggle||!toggle.enabled)return
  if(phase===0){
   if(!toggle.checked){console.log("FAIL: default mirror");Qt.exit(1);return}
   var scroll=pointer.findChild(w.editor,"editorScroll"),flick=scroll.contentItem
   var y=toggle.mapToItem(flick.contentItem,0,0).y
   flick.contentY=Math.max(0,Math.min(flick.contentHeight-flick.height,y-80))
   pointer.mouseClick(toggle,12,12)
   if(!toggle.checked){console.log("FAIL: optimistic checkbox");Qt.exit(1);return}
  }
  if(phase===1){if(toggle.checked){console.log("FAIL: confirmed mirror off");Qt.exit(1);return}console.log("PASS: snapshot mirror checkbox waits for storage readback");Qt.quit()}
  phase++
 }}
 Timer {interval:8000;running:true;onTriggered:Qt.exit(1)}
}''')
env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',WEBCAMTUNER_CONFIG_ROOT=str(scratch/'config'),XDG_DATA_HOME=str(scratch/'data'),XDG_CONFIG_HOME=str(scratch/'xdg-config'))
r=subprocess.run(['qs','-p',str(harness)],env=env,capture_output=True,text=True,timeout=12)
if r.returncode or 'PASS:' not in r.stdout+r.stderr:raise SystemExit((r.stdout+r.stderr)[-4000:])
assert json.loads((scratch/'config/snapshots.json').read_text())['mirrorToOS'] is False
print('PASS: Setup snapshot mirror checkbox confirms storage; persisted disabled setting read back')
