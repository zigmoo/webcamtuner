"""Consumer readbacks and acceptance remain reachable at the smallest window."""
import os
from pathlib import Path
import subprocess
import uuid
root=Path(__file__).resolve().parents[1]
scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('test-viewport-'+uuid.uuid4().hex)
scratch.mkdir()
harness=scratch/'shell.qml'
harness.write_text('''import QtQuick
import Quickshell
import QtTest
import "'''+(root/'ui').as_uri()+'''" as Tuner
ShellRoot {
 TestCase {id:inspect;when:false}
 FloatingWindow {
  implicitWidth:540;implicitHeight:551;visible:true;color:"#171c24"
  Tuner.TestPanel {id:panel;anchors.fill:parent}
 }
 function expect(value,message){if(!value){console.log("FAIL: "+message);Qt.exit(1)}}
 Timer {interval:600;running:true;onTriggered:{
  var bar=inspect.findChild(panel,"testScrollbar")
  expect(bar.visible&&bar.x>=panel.width-20&&bar.height===panel.height,"scrollbar spans right edge")
  expect(panel.contentHeight>panel.availableHeight,"content overflows the small viewport")
  panel.contentItem.contentY=panel.contentHeight-panel.availableHeight
  var acceptance=inspect.findChild(panel,"appAcceptance")
  var point=acceptance.mapToItem(panel,0,0)
  expect(point.y>=0&&point.y<panel.height,"last section is reachable by scrolling")
  expect(inspect.findChild(panel,"pipewireReadback")!==null&&inspect.findChild(panel,"v4l2Readback")!==null,"both readback cards exist")
  console.log("PASS: right-edge full-height Test scrollbar and both output cards/acceptance reachable at540x551")
  Qt.quit()
 }}
 Timer {interval:6000;running:true;onTriggered:Qt.exit(1)}
}''')
result=subprocess.run(['qs','-p',str(harness)],env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software'),capture_output=True,text=True,timeout=10)
output=result.stdout+result.stderr
if result.returncode or 'PASS:' not in output:raise SystemExit(output[-4000:])
print('PASS: right-edge full-height Test scrollbar; both consumer cards and last acceptance section are reachable')
