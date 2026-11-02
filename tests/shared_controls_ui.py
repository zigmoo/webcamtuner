"""Multiple monitor bar entries must share one control window and draft."""
import os,subprocess,uuid
from pathlib import Path
root=Path(__file__).resolve().parent.parent
scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('service-'+uuid.uuid4().hex);scratch.mkdir()
shell=Path(os.environ.get('OMARCHY_PATH','/usr/share/omarchy'))/'shell'
for name in ['Commons','Ui']:(scratch/name).symlink_to(shell/name,target_is_directory=True)
harness='import QtQuick\nimport Quickshell\nimport "{{PLUGIN_ROOT}}" as Tuner\nShellRoot {\n Tuner.Service {id:service;Component.onCompleted:editor.testing=true}\n QtObject {id:api;function serviceFor(id){return service}}\n QtObject {id:host;property var shell:api;property bool vertical:false;property int barSize:32;property color foreground:"white";property color background:"black";property color accent:"green";property string fontFamily:"sans"}\n Tuner.BarWidget {id:a;bar:host}\n Tuner.BarWidget {id:b;bar:host}\n property int phase:0\n Timer {interval:300;running:true;repeat:true;onTriggered:{\n  if(phase===0){if(a.controller!==service || b.controller!==service){console.log("FAIL: shared owner");Qt.exit(1);return}a.open()}\n  if(phase===1){if(!service.editor.document || service.editor.busy)return;service.editor.placeForeground(.2,.3);b.open()}\n  if(phase===2){if(a.controller.window!==b.controller.window || service.editor.foreground.x!==.2){console.log("FAIL: one window/draft");Qt.exit(1);return}b.close();if(service.opened){console.log("FAIL: close");Qt.exit(1);return}console.log("PASS: two bar instances share one controls window and profile draft");Qt.quit()}\n  phase++\n }}\n Timer {interval:8000;running:true;onTriggered:Qt.exit(1)}\n}'
(scratch/'shell.qml').write_text(harness.replace('{{PLUGIN_ROOT}}',root.as_uri()))
env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',WEBCAMTUNER_CONFIG_ROOT=str(scratch/'profiles'))
r=subprocess.run(['qs','-p',str(scratch/'shell.qml')],env=env,capture_output=True,text=True,timeout=12)
if r.returncode or 'PASS:' not in r.stdout+r.stderr:raise SystemExit((r.stdout+r.stderr)[-6000:])
print('PASS: two bar instances share one controls window and profile draft')
