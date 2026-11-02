"""Recovered crop acknowledgements settle and autosave does not pulse controls."""
import json
import os
import subprocess
import traceback
import uuid
from pathlib import Path

os.environ.update(QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlExpression, qmlContext
from PySide6.QtQuick import QQuickView

root = Path(__file__).resolve().parents[1]
scratch = Path(os.environ['WEBCAMTUNER_TEST_ROOT']) / ('steady-controls-' + uuid.uuid4().hex)
scratch.mkdir()
os.environ['WEBCAMTUNER_CONFIG_ROOT'] = str(scratch)
app = QGuiApplication([])
view = QQuickView()
view.setSource(QUrl.fromLocalFile(str(root / 'ui/Editor.qml')))
assert view.status() != QQuickView.Error
editor = view.rootObject()
editor.setProperty('testing', True)
failures = []
finished = False
requests = []


def ev(expression):
    expression = QQmlExpression(qmlContext(editor), editor, expression)
    value = expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    return value[0] if isinstance(value, tuple) else value


def later(delay, callback):
    def guarded():
        try:
            callback()
        except Exception:
            failures.append(traceback.format_exc())
            app.quit()
    QTimer.singleShot(delay, guarded)


def cli(action, args):
    return json.loads(subprocess.check_output([str(root / 'bin/webcamtuner'), action, *args, '--json'], text=True))


def request(action, args):
    args = args.toVariant() if hasattr(args, 'toVariant') else args
    requests.append(action)
    editor.setProperty('busy', True)
    def reply():
        editor.setProperty('busy', False)
        ev('accept(' + json.dumps(action) + ',' + json.dumps(cli(action, args)) + ')')
    later(100, reply)


editor.request.connect(request)
initial = cli('read', [])
initial['lastCamera'] = 'device:/dev/video0'
initial['profiles'][0]['source']['camera'] = '/dev/video0'
ev('accept("read",' + json.dumps(initial) + ')')


def start():
    ev('automaticWritesPaused=true;testCameraInputs=[{id:"/dev/video0",description:"Camera"}];cameraChoiceReady=true;savedCamera="/dev/video0";profileName="Recovered adjustments";mark()')
    crop = {'zoom': 1.478053586130944, 'centerX': .6617172714902477, 'centerY': .7349156490686178}
    ev('cropDrafts={"/image.jpeg":' + json.dumps(crop) + '};cropInFlight={path:"/image.jpeg",crop:cropDrafts["/image.jpeg"]}')
    # Recovery and Python serialization reorder fields and slightly round values.
    ack = {'centerY': crop['centerY'], 'centerX': crop['centerX'], 'zoom': crop['zoom'] + 2e-16}
    ev('accept("background-crop",' + json.dumps({'id': 'image', 'crop': ack}) + ')')
    assert ev('Object.keys(cropDrafts).length') == 0
    # A newer edit must survive an older acknowledgement.
    ev('cropDrafts={"/image.jpeg":{zoom:2,centerX:.5,centerY:.5}};cropInFlight={path:"/image.jpeg",crop:{zoom:1,centerX:.5,centerY:.5}};accept("background-crop",{crop:{zoom:1,centerX:.5,centerY:.5}})')
    assert ev('cropDrafts["/image.jpeg"].zoom') == 2
    ev('cropDrafts={};busy=true')
    for name in ('mirrorToggle', 'cameraChoice', 'reloadSaved', 'remoteCameras'):
        assert editor.findChild(QObject, name).property('enabled'), name + ' disabled by unrelated work'
    ev('toggleMirror()')
    assert editor.property('mirrorQueued') and editor.property('mirror')
    ev('busy=false;resumeAutomaticWrites()')
    later(2300, settled)


def settled():
    assert not editor.property('mirror') and not editor.property('mirrorQueued')
    assert not editor.property('dirty') and not editor.property('busy')
    assert requests.count('save') == 2, requests
    saved = json.loads((scratch / 'profiles.json').read_text())
    assert saved['profiles'][0]['name'] == 'Recovered adjustments'
    assert not saved['profiles'][0]['mirror']
    later(1300, finish)


def finish():
    global finished
    assert requests.count('save') == 2, requests
    finished = True
    print('PASS: recovered crop settles, newer crop survives, controls stay enabled and queued mirror preserves autosaved edits')
    app.quit()


later(200, start)
QTimer.singleShot(8000, app.quit)
app.exec()
if failures or not finished:
    raise SystemExit('\n'.join(failures) or 'Control stability test timed out')
