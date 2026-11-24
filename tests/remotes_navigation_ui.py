"""An enabled Remotes tab navigates without switching the local camera output."""
import json,os,subprocess,uuid
from pathlib import Path
root=Path(__file__).resolve().parents[1]
scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('remotes-nav-'+uuid.uuid4().hex[:8]);scratch.mkdir(parents=True)
ui=Path(os.environ.get('WEBCAMTUNER_UI_ROOT',str(root/'ui')))
harness='''import QtQuick
import Quickshell
import QtTest
import "UI_PATH" as Tuner
ShellRoot {
 TestCase {id:inspect;when:false}
 Tuner.TunerWindow {id:w;Component.onCompleted:{editor.testing=true;openCamera()}}
 property int phase:0
 property string beforeDraft:""
 property int discoveries:0
 property bool beforePreview:false
 function expect(ok,msg){if(!ok){console.log("FAIL: "+msg);Qt.exit(1)}}
 Timer {interval:200;running:true;repeat:true;onTriggered:{
  if(!w.editor.document||w.editor.busy)return
  var e=w.editor;var panel=inspect.findChild(e,"remoteSources")
  if(phase===0){
   w.setRemotesTabVisible(true)
   expect(inspect.findChild(w,"navigationTabs").itemAt(3).objectName==="remotesTab","Enabled Remotes tab missing")
   expect(inspect.findChild(w,"navigationTabs").count===5,"Five navigation tabs expected")
   e.automaticWritesPaused=true;e.autostartCamera=false;e.previewOn=false
   e.sourceKind="local";e.sourceHost="";e.savedCamera="/dev/video101";e.remoteBrowse=false
   e.outputControl.state=({published:true,processed:true,camera:"/dev/video101"})
   beforeDraft=JSON.stringify(e.draftDocument())
   beforePreview=e.previewOn
   panel.discoveryRequested.connect(function(args){discoveries++})
   w.openRemotes()
  }else if(phase===1){
   expect(e.section==="remotes"&&panel.visible,"Local source hid Remotes")
   expect(e.sourceKind==="local"&&e.savedCamera==="/dev/video101","Navigation changed Brio source")
   expect(e.publishing&&e.previewOn===beforePreview&&!e.remoteConnecting,"Opening Remotes changed capture/output")
   expect(discoveries>0,"Remotes did not request discovery")
   panel.accept({machines:[{host:"omarchy-zbook",name:"ZBook",supported:true,online:true}]})
   panel.inspect(0)
   panel.accept({cameras:[{id:"/dev/video4",stableId:"/dev/v4l/by-id/C930e-video-index0",name:"Logitech C930e",modes:[]}]})
   expect(panel.cameras.length===1,"Discovered camera data missing")
   expect(e.sourceKind==="local"&&e.savedCamera==="/dev/video101"&&!e.remoteConnecting,"Discovery connected implicitly")
   expect(JSON.stringify(e.draftDocument())===beforeDraft,"Discovery modified profile")
   w.showSection("background");w.openCamera();w.openRemotes()
  }else{
   expect(e.section==="remotes"&&panel.visible,"Remotes vanished after other tabs")
   expect(e.publishing&&e.savedCamera==="/dev/video101","Working output was not preserved")
   w.closeEditor();w.openRemotes()
   expect(e.section==="remotes"&&panel.visible,"Cold Remotes route failed")
   console.log("PASS: enabled Remotes survives local profile, tab changes and reopen; discovery populates devices without changing Brio/output/profile")
   Qt.quit()
  }
  phase++
 }}
 Timer {interval:12000;running:true;onTriggered:{console.log("FAIL: navigation timed out");Qt.exit(1)}}
}'''.replace('"UI_PATH"',json.dumps(ui.as_uri()))
(scratch/'shell.qml').write_text(harness)
r=subprocess.run(['qs','-p',str(scratch/'shell.qml')],env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',WEBCAMTUNER_CONFIG_ROOT=str(scratch/'profiles'),XDG_CONFIG_HOME=str(scratch/'config')),capture_output=True,text=True,timeout=16)
out=r.stdout+r.stderr
if r.returncode or 'PASS:' not in out:raise SystemExit(out[-5000:])
print('PASS: enabled Remotes visible for Brio; camera data loads; no capture, output or profile change from discovery/navigation')
