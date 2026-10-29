"""Exercise the real read -> device inventory -> save process handoff, without capture."""
import json
import os
from pathlib import Path
import subprocess
import uuid

root = Path(__file__).resolve().parent.parent
aliases = json.loads(subprocess.check_output([str(root / 'bin' / 'webcamtuner'), 'devices', '--json'], text=True))['aliases']
if not any(item['primary'] for item in aliases):
    print('SKIP: real startup check needs an attached USB webcam')
    raise SystemExit(0)
scratch = Path(os.environ['WEBCAMTUNER_TEST_ROOT']) / ('startup-' + uuid.uuid4().hex)
scratch.mkdir(parents=True)
harness = scratch / 'shell.qml'
harness.write_text('''import QtQuick
import Quickshell
import "''' + (root / 'ui').as_uri() + '''" as Tuner
ShellRoot {
 Tuner.TunerWindow { id:w; Component.onCompleted:openEditor() }
 Timer {
  interval:50; running:true; repeat:true
  onTriggered: {
   var e=w.editor
   if (e.document && e.document.lastCamera && e.savedCamera !== "" && e.cameraChoiceReady && !e.cameraPending && !e.busy) {
    console.log("STARTUP_READY " + JSON.stringify({camera:e.savedCamera, capture:e.previewOn, stable:e.document.lastCamera.indexOf("by-id:") === 0}))
    Qt.quit()
   }
  }
 }
 Timer { interval:7000; running:true; onTriggered: {console.log("STARTUP_FAILED " + w.editor.message); Qt.quit()} }
}''')
env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', WEBCAMTUNER_CONFIG_ROOT=str(scratch / 'profiles'))
result = subprocess.run(['qs', '-p', str(harness)], env=env, capture_output=True, text=True, timeout=12)
output = result.stdout + result.stderr
ready = next((line.split('STARTUP_READY ', 1)[1] for line in output.splitlines() if 'STARTUP_READY ' in line), None)
if result.returncode or ready is None:
    print(output[-4000:])
    raise SystemExit('Real window startup did not settle on a saved camera')
state = json.loads(ready)
assert state['stable'] and not state['capture']
stored = json.loads((scratch / 'profiles' / 'profiles.json').read_text())
assert stored['profiles'][0]['source']['camera'] == state['camera']
print('PASS: real window automatically selected and confirmed a stable webcam identity; capture stays off')
