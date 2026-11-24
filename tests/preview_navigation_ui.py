"""Switching tabs leaves the camera preview available while output is live."""
import json,os,subprocess,uuid
from pathlib import Path
root=Path(__file__).resolve().parents[1]
scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('preview-nav-'+uuid.uuid4().hex[:8]);scratch.mkdir()
qml='''import QtQuick
import Quickshell
import QtTest
import "UI_PATH" as Tuner
ShellRoot {
 TestCase {id:inspect;when:false}
 Tuner.TunerWindow {id:w;Component.onCompleted:{editor.testing=true;openCamera()}}
 property bool done:false
 function expect(value,message){if(!value){console.log("FAIL: "+message);Qt.exit(1)}}
 Timer {interval:200;running:true;repeat:true;onTriggered:{
  if(done||!w.editor.document||w.editor.busy)return
  done=true
  w.editor.outputControl.state=({published:true,processed:true})
  w.editor.previewOn=true
  w.openTest()
  expect(w.editor.previewOn,"Test must preserve the requested preview")
  expect(!w.testPanel.receiving,"fixture cannot connect to production consumers")
  w.openCamera()
  expect(w.editor.previewOn,"returning Camera retains live preview")
  w.openBackgrounds();w.openSetup();w.openCamera()
  expect(w.editor.previewOn,"Backgrounds and Setup preserve the preview")
  expect(inspect.findChild(w.editor,"previewCameraButton")===null,"preview has no separate toggle")
  console.log("PASS: Camera preview survives tab changes while the output is live")
  Qt.quit()
 }}
 Timer {interval:7000;running:true;onTriggered:Qt.exit(1)}
}'''.replace('"UI_PATH"',json.dumps((root/'ui').as_uri()))
(scratch/'shell.qml').write_text(qml)
r=subprocess.run(['qs','-p',str(scratch/'shell.qml')],env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',WEBCAMTUNER_CONFIG_ROOT=str(scratch/'profiles'),XDG_CONFIG_HOME=str(scratch/'config')),capture_output=True,text=True,timeout=10)
out=r.stdout+r.stderr
if r.returncode or 'PASS:' not in out:raise SystemExit(out[-5000:])
print('PASS: live preview is preserved across Camera, Backgrounds, Setup, and Test')
