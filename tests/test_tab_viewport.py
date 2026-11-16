"""Consumer readbacks stay side by side and scroll at all supported widths."""
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
  id:window
  implicitWidth:540;implicitHeight:551;visible:true;color:"#171c24"
  Tuner.TestPanel {id:panel;anchors.fill:parent}
 }
 function expect(value,message){if(!value){console.log("FAIL: "+message);Qt.exit(1)}}
 property var widths:[540,780,1100]
 property int sizeIndex:0
 Timer {interval:400;running:true;repeat:true;onTriggered:{
  var pipewire=inspect.findChild(panel,"pipewireReadback")
  var v4l2=inspect.findChild(panel,"v4l2Readback")
  expect(pipewire!==null&&v4l2!==null,"both readback cards exist")
  var left=pipewire.mapToItem(panel,0,0)
  var right=v4l2.mapToItem(panel,0,0)
  expect(Math.abs(left.y-right.y)<1&&right.x>left.x+pipewire.width,"previews are side by side at"+panel.width)
  expect(Math.abs(pipewire.width-v4l2.width)<1,"equal preview widths at"+panel.width)
  expect(left.x>=0&&right.x+v4l2.width<=panel.width-panel.rightPadding+1,"cards fit inside the viewport")
  expect(pipewire.width>200&&v4l2.width>200,"both previews have meaningful width")
  expect(panel.contentWidth<=panel.availableWidth,"no hidden horizontal overflow")
  var bar=inspect.findChild(panel,"testScrollbar")
  if(panel.contentHeight>panel.availableHeight){
   expect(bar.visible&&bar.x>=panel.width-20&&bar.height===panel.height,"scrollbar spans right edge")
   panel.contentItem.contentY=panel.contentHeight-panel.availableHeight
  }
  var acceptance=inspect.findChild(panel,"appAcceptance")
  var point=acceptance.mapToItem(panel,0,0)
  expect(point.y>=0&&point.y<panel.height,"last section is reachable by scrolling")
  console.log("PASS: side-by-side readbacks, no horizontal overflow and acceptance reachable at"+panel.width)
  sizeIndex++
  if(sizeIndex===widths.length){Qt.quit();return}
  panel.contentItem.contentY=0
  window.implicitWidth=widths[sizeIndex]
 }}
 Timer {interval:6000;running:true;onTriggered:Qt.exit(1)}
}''')
result=subprocess.run(['qs','-p',str(harness)],env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software'),capture_output=True,text=True,timeout=10)
output=result.stdout+result.stderr
if result.returncode or 'PASS:' not in output:raise SystemExit(output[-4000:])
print('PASS: side-by-side readbacks at540/780/1100px; no horizontal overflow; full-height scrollbar and acceptance reachable')
