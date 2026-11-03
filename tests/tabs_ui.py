"""Real QML navigation retains the single dirty profile and exposes Setup/About."""
import os
from pathlib import Path
import subprocess
import uuid

root = Path(__file__).resolve().parent.parent
scratch = Path(os.environ['WEBCAMTUNER_TEST_ROOT']) / ('tabs-' + uuid.uuid4().hex)
scratch.mkdir(parents=True)
harness = scratch / 'shell.qml'
harness.write_text('''import QtQuick
import Quickshell
import QtTest
import "''' + (root / 'ui').as_uri() + '''" as Tuner
ShellRoot {
 TestCase { id: pointer; when: false }
 Tuner.TunerWindow { id:w; Component.onCompleted: {editor.testing=true; openBackgrounds()} }
 property int phase:0
 function expect(ok,msg) { if(!ok) {console.log("FAIL: "+msg);Qt.exit(1)} }
 Timer {interval:250;running:true;repeat:true;onTriggered:{
  if(!w.editor.document || w.editor.busy) return
  var tabs=pointer.findChild(w,"navigationTabs")
  if(phase===0){expect(w.editor.document!==null,"cold background open reads profiles");w.editor.frame(2,0.5,0.5);pointer.findChild(w.editor,"editorScroll").contentItem.contentY=160;tabs.currentIndex=0;tabs.currentIndex=1}
  if(phase===1){expect(w.editor.section==="background" && w.editor.dirty,"background retains draft");tabs.currentIndex=2}
  if(phase===2){expect(w.editor.section==="setup" && w.editor.zoom===2,"setup retains crop");expect(pointer.findChild(w,"startTestOutput")!==null,"setup output control exists");tabs.currentIndex=3}
  if(phase===3){expect(pointer.findChild(w,"outputTestPanel")!==null,"test tab exists");expect(pointer.findChild(w,"pipewireReadback")!==null&&pointer.findChild(w,"v4l2Readback")!==null,"both consumer readbacks exist");expect(w.editor.zoom===2,"test retains framing");tabs.currentIndex=4}
  if(phase===4){expect(w.editor.zoom===2,"about retains framing");tabs.currentIndex=0}
  if(phase===5){expect(pointer.findChild(w.editor,"editorScroll").contentItem.contentY===0,"camera starts at top");expect(w.editor.section==="camera" && w.editor.zoom===2,"camera restores same draft");console.log("PASS: five tabs preserve one editor draft");Qt.quit()}
  phase++
 }}
 Timer {interval:10000;running:true;onTriggered:Qt.exit(1)}
}''')
env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', WEBCAMTUNER_CONFIG_ROOT=str(scratch / 'profiles'))
result = subprocess.run(['qs','-p',str(harness)],env=env,capture_output=True,text=True,timeout=15)
output = result.stdout + result.stderr
if result.returncode or 'PASS: five tabs' not in output:
    raise SystemExit(output[-4000:])
print('PASS: five tabs preserve one editor draft; Setup has output controls')
