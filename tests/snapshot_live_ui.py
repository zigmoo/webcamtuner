"""One explicitly requested snapshot through QML/worker IPC; remove its test photo."""
import json,os,subprocess
from pathlib import Path
from PIL import Image
root=Path(__file__).resolve().parent.parent
scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])
settings={'camera':os.environ['WEBCAMTUNER_ACCEPTANCE_CAMERA'],'mirror':True,'crop':{'zoom':1.45,'centerX':0.5,'centerY':0.5},'background':{'mode':'image','imagePath':os.environ['WEBCAMTUNER_ACCEPTANCE_IMAGE'],'crop':{'zoom':1.6,'centerX':0.5,'centerY':0.5}}}
harness=scratch/'SnapshotCheck.qml'
harness.write_text('''import QtQuick
import Quickshell
import "''' + (root/'ui').as_uri() + '''" as Tuner
ShellRoot {
 property int frames:0
 property bool requested:false
 property var expected:[]
 Tuner.ProcessedPreview {
  id:preview
  configuration:''' + json.dumps(settings) + '''
  Component.onCompleted:active=true
  onFailed:function(message){console.log("FAIL: "+message);active=false;Qt.exit(1)}
  onSnapshotFailed:function(message){console.log("FAIL: "+message);active=false;Qt.exit(1)}
  onFrameReceived:function(mode){
   frames++
   if(frames>=8 && snapshotReady && !requested){requested=true;expected=[format.retainedWidth,format.retainedHeight];takeSnapshot()}
  }
  onSnapshotSaved:function(result){
   if(result.width!==expected[0] || result.height!==expected[1]){console.log("FAIL: snapshot lost source detail");active=false;Qt.exit(1);return}
   console.log("SNAPSHOT: "+JSON.stringify(result));active=false;Qt.quit()
  }
 }
 Timer{interval:20000;running:true;onTriggered:{console.log("FAIL: snapshot timed out");preview.active=false;Qt.exit(1)}}
}''')
env=dict(os.environ,QT_QPA_PLATFORM='offscreen',WEBCAMTUNER_SNAPSHOT_ROOT=str(scratch/'snapshot-photo-check'))
r=subprocess.run(['qs','-p',str(harness)],env=env,text=True,capture_output=True,timeout=25)
output=r.stdout+r.stderr
lines=[line.split('SNAPSHOT: ',1)[1] for line in output.splitlines() if 'SNAPSHOT: ' in line]
if r.returncode or not lines:raise SystemExit(output[-4000:])
result=json.loads(lines[0]);photo=Path(result['path'])
try:
 with Image.open(photo) as image:assert image.size==(result['width'],result['height'])
 assert result['width']>960
 print(json.dumps({'result':'PASS','size':[result['width'],result['height']],'temporaryTestPhotoRemoved':True}))
finally:photo.unlink(missing_ok=True)
