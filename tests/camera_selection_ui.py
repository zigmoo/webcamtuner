"""Verify automatic, immediate persistent camera selection without enabling capture."""
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_SCALE_FACTOR"] = "1"
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlExpression, qmlContext
from PySide6.QtQuick import QQuickView

root = Path(__file__).resolve().parent.parent
scratch = Path(os.environ["WEBCAMTUNER_TEST_ROOT"])
os.environ["WEBCAMTUNER_CONFIG_ROOT"] = str(scratch / ("camera-ui-" + uuid.uuid4().hex))
app = QGuiApplication(sys.argv)
view = QQuickView()
view.setResizeMode(QQuickView.SizeRootObjectToView)
view.setSource(QUrl.fromLocalFile(str(root / "ui" / "Editor.qml")))
if view.status() == QQuickView.Error:
    raise SystemExit("Editor did not load")
editor = view.rootObject()
editor.setProperty("testing", True)
pending, failures = [], []
editor.request.connect(lambda action, args: pending.append((action, args.toVariant() if hasattr(args, 'toVariant') else args)))

def evaluate(expression):
    value = QQmlExpression(qmlContext(editor), editor, expression)
    result = value.evaluate()
    if value.hasError(): raise RuntimeError(value.error().toString())
    return result

def execute(action, args):
    result = json.loads(subprocess.check_output([str(root / 'bin' / 'webcamtuner'), action, *args, '--json'], text=True))
    evaluate('accept(' + json.dumps(action) + ',' + json.dumps(result) + ')')

def inventory(inputs, aliases):
    evaluate('testCameraInputs=' + json.dumps(inputs))
    evaluate('accept("devices",' + json.dumps({'aliases': aliases}) + ')')

def flush():
    while pending: execute(*pending.pop(0))

A = {'id': '/dev/video101', 'description': 'Camera A'}
B = {'id': '/dev/video102', 'description': 'Camera B'}
aliases = [{'path': A['id'], 'key': 'by-id:camera-A-video-index0', 'primary': True},
           {'path': B['id'], 'key': 'by-id:camera-B-video-index0', 'primary': True}]
execute('read', [])

def exercise():
    try:
        inventory([A], aliases[:1])
        assert editor.property('cameraPending') is True
        flush()
        assert editor.property('savedCamera') == A['id']
        assert editor.property('previewOn') is True
        evaluate('frame(2, 0.5, 0.5)')
        inventory([A, B], aliases)
        flush()
        evaluate('selectCamera("' + B['id'] + '")')
        assert editor.property('savedCamera') == A['id']
        flush()
        assert editor.property('savedCamera') == B['id']
        assert editor.property('zoom') == 2 and editor.property('dirty') is True
        execute('read', [])
        renumbered = {'id': '/dev/video108', 'description': 'Camera B'}
        updated = [aliases[0], {**aliases[1], 'path': renumbered['id']}]
        inventory([A, renumbered], updated)
        flush()
        assert editor.property('savedCamera') == renumbered['id']
        inventory([A], aliases[:1])
        flush()
        assert editor.property('savedCamera') == A['id']
        inventory([], [])
        assert editor.property('savedCamera') == '' and editor.property('previewOn') is False
    except Exception as error: failures.append(str(error) or type(error).__name__)
    app.quit()

QTimer.singleShot(100, exercise)
app.exec()
if failures: raise SystemExit('; '.join(failures))
print('PASS: sole camera selected with autostart; choice saved immediately; stable identity restored after renumber; unplug fallback works')
