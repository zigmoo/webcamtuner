"""An active preview waits for configuration before starting its worker."""
import os,json,subprocess,uuid,base64,io
from pathlib import Path
from PIL import Image
root=Path(__file__).resolve().parent.parent;scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('preview-start-'+uuid.uuid4().hex);(scratch/'bin').mkdir(parents=True)
stream=io.BytesIO();Image.new('RGB',(20,12),'green').save(stream,'JPEG');frame=base64.b64encode(stream.getvalue()).decode()
worker=scratch/'bin/preview-python'
worker.write_text('#!/usr/bin/env python3\nimport sys,json\nfrom pathlib import Path\nargs=sys.argv;config=json.loads(args[args.index("--request")+1])\nPath('+repr(str(scratch/'started.json'))+').write_text(json.dumps(config))\nif not config or not config.get("camera"):print(json.dumps({"error":"Started without configuration"}),flush=True);sys.exit(1)\nprint(json.dumps({"frame":'+repr(frame)+',"effect":"none","width":20,"height":12,"captureWidth":1920,"captureHeight":1080,"provider":"CPUExecutionProvider","configurationRevision":config.get("configurationRevision",0)}),flush=True)\nfor line in sys.stdin:pass\n')
worker.chmod(0o755)
harness=scratch/'shell.qml';harness.write_text('''import QtQuick
import Quickshell
import "'''+(root/'ui').as_uri()+'''" as Tuner
ShellRoot {
 Tuner.ProcessedPreview {
  id:preview;pluginRoot:''' +json.dumps(str(scratch))+''';configuration:null;active:true
  onFailed:function(message){console.log("FAIL: "+message);Qt.exit(1)}
  onFrameReceived:{active=false;console.log("PASS: delayed configuration starts a real worker and receives its first frame");Qt.quit()}
 }
 Timer {interval:300;running:true;onTriggered:preview.configuration=({camera:"/dev/video101",crop:{zoom:1,centerX:.5,centerY:.5},background:{mode:"none",imagePath:""}})}
 Timer {interval:7000;running:true;onTriggered:Qt.exit(1)}
}''')
env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
result=subprocess.run(['qs','-p',str(harness)],env=env,capture_output=True,text=True,timeout=10)
if result.returncode or 'PASS:' not in result.stdout+result.stderr:raise SystemExit((result.stdout+result.stderr)[-4000:])
assert json.loads((scratch/'started.json').read_text())['camera']=='/dev/video101'
print('PASS: active preview waits for delayed valid configuration; first frame received without a failed/empty startup')
