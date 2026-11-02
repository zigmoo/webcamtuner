"""Measure fresh processed and decoded preview frames; store no camera images."""
import json,os,subprocess
from pathlib import Path
root=Path(__file__).resolve().parent.parent
scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])
settings={'camera':os.environ['WEBCAMTUNER_ACCEPTANCE_CAMERA'],'mirror':True,'crop':{'zoom':1.45,'centerX':0.5,'centerY':0.5},'background':{'mode':'image','imagePath':os.environ['WEBCAMTUNER_ACCEPTANCE_IMAGE']}}
harness=scratch/'PreviewRate.qml'
harness.write_text('''import QtQuick
import Quickshell
import "''' + (root/'ui').as_uri() + '''" as Tuner
ShellRoot {
 property int frames:0
 property int decoded:0
 property double began:0
 Tuner.PreviewFrame {source:preview.frameUrl;onStatusChanged:if(status===Image.Ready && frames>60)decoded++}
 Tuner.ProcessedPreview {
  id:preview
  configuration:''' + json.dumps(settings) + '''
  Component.onCompleted:active=true
  onFailed:function(message){console.log("FAIL: "+message);active=false;Qt.exit(1)}
  onFrameReceived:function(mode){
   frames++
   if(frames===60){began=Date.now();decoded=0}
   if(frames===240){
    var seconds=(Date.now()-began)/1000
    var result={freshFps:180/seconds,decodedFps:decoded/seconds,provider:format.provider,capture:[format.captureWidth,format.captureHeight],imagesStored:false}
    console.log("RESULT: "+JSON.stringify(result));active=false;Qt.quit()
   }
  }
 }
 Timer{interval:30000;running:true;onTriggered:{console.log("FAIL: throughput check timed out");preview.active=false;Qt.exit(1)}}
}''')
r=subprocess.run(['qs','-p',str(harness)],env=dict(os.environ,QT_QPA_PLATFORM='wayland' if os.environ.get('WEBCAMTUNER_NATIVE_TEST') else 'offscreen'),text=True,capture_output=True,timeout=35)
output=r.stdout+r.stderr
lines=[line.split('RESULT: ',1)[1] for line in output.splitlines() if 'RESULT: ' in line]
if r.returncode or not lines:raise SystemExit(output[-4000:])
result=json.loads(lines[0]);print(json.dumps(result))
(scratch/'preview-rate.json').write_text(json.dumps(result,indent=2))
if result['freshFps']<24 or result['decodedFps']<24:raise SystemExit('Fresh or decoded preview rate is below 24 fps')
