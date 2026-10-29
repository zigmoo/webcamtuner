"""Exercise the real read -> device inventory -> save process handoff, without capture."""
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

root = Path(__file__).resolve().parent.parent
autostart = '--autostart' in sys.argv
aliases = json.loads(subprocess.check_output([str(root / 'bin' / 'webcamtuner'), 'devices', '--json'], text=True))['aliases']
if not any(item['primary'] for item in aliases):
    print('SKIP: real startup check needs an attached USB webcam')
    raise SystemExit(0)
scratch = Path(os.environ['WEBCAMTUNER_TEST_ROOT']) / ('startup-' + uuid.uuid4().hex)
scratch.mkdir(parents=True)
profiles = scratch / 'profiles'
profiles.mkdir()
store = json.loads(subprocess.check_output([str(root / 'bin' / 'webcamtuner'), 'read', '--json'], env=dict(os.environ, WEBCAMTUNER_CONFIG_ROOT=str(profiles)), text=True))
store['profiles'][0]['autostartCamera'] = autostart
(profiles / 'profiles.json').write_text(json.dumps(store))
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
   if (e.document && e.document.lastCamera && e.savedCamera !== "" && e.cameraChoiceReady && !e.cameraPending && !e.busy && (!e.autostartCamera || e.captureFormat.captureWidth > 0)) {
    console.log("STARTUP_READY " + JSON.stringify({camera:e.savedCamera, capture:e.previewOn, stable:e.document.lastCamera.indexOf("by-id:") === 0}))
    Qt.quit()
   }
  }
 }
 Timer { interval:12000; running:true; onTriggered: {console.log("STARTUP_FAILED " + w.editor.message); Qt.quit()} }
}''')
env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', WEBCAMTUNER_CONFIG_ROOT=str(scratch / 'profiles'))
result = subprocess.run(['qs', '-p', str(harness)], env=env, capture_output=True, text=True, timeout=17)
output = result.stdout + result.stderr
ready = next((line.split('STARTUP_READY ', 1)[1] for line in output.splitlines() if 'STARTUP_READY ' in line), None)
if result.returncode or ready is None:
    print(output[-4000:])
    raise SystemExit('Real window startup did not settle on a saved camera')
state = json.loads(ready)
assert state['stable'] and state['capture'] == autostart
stored = json.loads((scratch / 'profiles' / 'profiles.json').read_text())
assert stored['profiles'][0]['source']['camera'] == state['camera']
print('PASS: real window selected a stable camera; ' + ('autostart delivered a processed frame' if autostart else 'disabled autostart keeps capture off'))
