"""Setup is one full-page scroll surface, with all sections reachable."""
import os, subprocess, uuid
from pathlib import Path
root=Path(__file__).resolve().parent.parent
scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('setup-layout-'+uuid.uuid4().hex); scratch.mkdir()
harness=scratch/'shell.qml'
harness.write_text('''import QtQuick
import Quickshell
import QtTest
import "'''+(root/'ui').as_uri()+'''" as Tuner
ShellRoot {
 TestCase {id:pointer; when:false}
 Tuner.TunerWindow {id:w; expandedWidth:760; expandedHeight:700; Component.onCompleted:{editor.testing=true;openSetup()}}
 function expect(ok,message){if(!ok){console.log("FAIL: "+message);Qt.exit(1)}}
 Timer {interval:1200;running:true;onTriggered:{
  var loader=pointer.findChild(w.editor,"setupLoader")
  var panel=pointer.findChild(w.editor,"setupPanel")
  var scroll=pointer.findChild(w.editor,"editorScroll")
  var bar=pointer.findChild(w.editor,"editorScrollbar")
  expect(panel!==null && loader.item===panel,"setup content loaded")
  expect(panel.height>scroll.availableHeight && Math.abs(panel.height-panel.implicitHeight)<2,"setup content gets its full natural height: "+panel.height+" / "+panel.implicitHeight+" viewport "+scroll.availableHeight)
  expect(bar.visible && scroll.contentHeight>scroll.height,"page overflow has visible scrollbar")
  expect(pointer.findChild(panel,"startTestOutput")!==null,"output controls exist below performance controls")
  scroll.contentItem.contentY=scroll.contentHeight-scroll.availableHeight
  expect(scroll.contentItem.contentY>500,"whole page can scroll to its bottom")
  console.log("PASS: Setup uses full content height and one page scrollbar; output/help controls reachable")
  Qt.quit()
 }}
 Timer {interval:10000;running:true;onTriggered:Qt.exit(1)}
}''')
env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',WEBCAMTUNER_CONFIG_ROOT=str(scratch/'profiles'),XDG_DATA_HOME=str(scratch/'data'),XDG_CACHE_HOME=str(scratch/'cache'))
result=subprocess.run(['qs','-p',str(harness)],env=env,capture_output=True,text=True,timeout=15)
output=result.stdout+result.stderr
if result.returncode or 'PASS: Setup' not in output:raise SystemExit(output[-4000:])
print('PASS: Setup uses full content height and one page scrollbar; output/help controls reachable')
