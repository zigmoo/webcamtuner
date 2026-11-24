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
import QtQuick.Controls
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
  if(phase===0){for(var i=0;i<tabs.count;i++)expect(tabs.itemAt(i).ToolTip.text.length>0,"hover text for tab "+i);expect(w.editor.document!==null,"cold background open reads profiles");w.editor.frame(2,0.5,0.5);pointer.findChild(w.editor,"editorScroll").contentItem.contentY=160;w.showSection("camera");w.showSection("background")}
  if(phase===1){expect(w.editor.section==="background" && w.editor.dirty,"background retains draft");w.showSection("setup")}
  if(phase===2){expect(w.editor.section==="setup" && w.editor.zoom===2,"setup retains crop");expect(pointer.findChild(w,"startTestOutput")!==null,"setup output control exists");w.showSection("test")}
  if(phase===3){
   var setupTabs=pointer.findChild(w,"setupTabs")
   expect(tabs.currentItem.text==="Setup" && setupTabs.visible && setupTabs.currentItem.text==="Test","Test is selected under Setup")
   expect(pointer.findChild(w,"outputTestPanel").visible,"Test panel is visible");expect(pointer.findChild(w,"pipewireReadback")!==null&&pointer.findChild(w,"v4l2Readback")!==null,"both consumer readbacks exist");expect(w.editor.zoom===2,"test retains framing");w.showSection("about")}
  if(phase===4){expect(w.editor.zoom===2,"about retains framing");w.showSection("camera")}
  if(phase===5){
   expect(tabs.count===4 && tabs.itemAt(1).text==="Backgrounds" && tabs.itemAt(3).text==="About","Remotes starts hidden")
   expect(w.editor.localSourceLabel.endsWith(" - This Computer"),"local hostname is shown")
   w.openRemotes()
   expect(w.editor.section==="setup","Hidden Remotes route opens Setup")
  }
  if(phase===6){
   var toggle=pointer.findChild(w,"showRemotesTab")
   expect(toggle && !toggle.checked,"Setup checkbox starts unchecked")
   var viewport=pointer.findChild(w.editor,"editorScroll").contentItem
   viewport.contentY=viewport.contentHeight-viewport.height
   expect(toggle.mapToItem(w.editor,0,toggle.height).y<=w.editor.height,"checkbox fits at bottom of Setup")
   toggle.clicked()
  }
  if(phase===7){
   expect(w.editor.section==="setup","Enabling Remotes preserves the Setup tab")
   expect(pointer.findChild(w.editor,"editorScroll").contentItem.contentY>500,"Enabling Remotes preserves the Setup scroll position")
   expect(tabs.count===5 && tabs.itemAt(3).text==="Remotes" && tabs.itemAt(4).text==="About","Remotes is just before About")
   w.openRemotes()
   expect(w.editor.section==="remotes"&&pointer.findChild(w.editor,"remoteSources").visible,"Enabled Remotes is accessible")
   w.showSection("setup")
  }
  if(phase===8){
   var toggleAgain=pointer.findChild(w,"showRemotesTab")
   expect(toggleAgain && toggleAgain.checked,"Setup checkbox reflects the choice")
   toggleAgain.clicked()
  }
  if(phase===9){
   expect(tabs.count===4 && tabs.itemAt(3).text==="About" && w.editor.section==="setup","Unchecking hides Remotes")
   w.showSection("camera")
   expect(w.editor.section==="camera" && w.editor.zoom===2,"Camera restores the same draft")
   console.log("PASS: optional Remotes tab and active-tab navigation")
   Qt.callLater(Qt.quit)
  }
  for (var tabIndex=0;tabIndex<tabs.count;tabIndex++) {
   var tab=tabs.itemAt(tabIndex), indicator=pointer.findChild(tab,"activeTabIndicator")
   expect(indicator && indicator.visible === (tabIndex===tabs.currentIndex),"only active tab has a visible underline")
   expect(tab.font.bold === (tabIndex===tabs.currentIndex),"only active tab is bold")
  }
  phase++
 }}
 Timer {interval:10000;running:true;onTriggered:Qt.exit(1)}
}''')
env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', WEBCAMTUNER_CONFIG_ROOT=str(scratch / 'profiles'), XDG_CONFIG_HOME=str(scratch / 'config'))
result = subprocess.run(['qs','-p',str(harness)],env=env,capture_output=True,text=True,timeout=15)
output = result.stdout + result.stderr
if result.returncode or 'PASS: optional Remotes tab' not in output:
    raise SystemExit(output[-4000:])
print('PASS: Remotes starts hidden, can be enabled beside About and hidden again; other tabs retain the editor draft')
