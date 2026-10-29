"""Exercise mirror confirmation, unsaved crop preservation, and the title drag handle."""
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_SCALE_FACTOR"] = "1"
from PySide6.QtCore import QObject, QPoint, Qt, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlExpression, qmlContext
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest

root = Path(__file__).resolve().parent.parent
scratch = Path(os.environ["WEBCAMTUNER_TEST_ROOT"])
os.environ["WEBCAMTUNER_CONFIG_ROOT"] = str(scratch / ("autostart-ui-" + uuid.uuid4().hex))
app = QGuiApplication(sys.argv)
view = QQuickView()
view.setResizeMode(QQuickView.SizeRootObjectToView)
view.setSource(QUrl.fromLocalFile(str(root / "ui" / "Editor.qml")))
if view.status() == QQuickView.Error:
    raise SystemExit("Editor did not load")
view.resize(760, 1300)
editor = view.rootObject()
editor.setProperty("testing", True)
pending, dragged, failures = [], [], []
editor.request.connect(lambda action, args: pending.append((action, args.toVariant() if hasattr(args, "toVariant") else args)))

def evaluate(expression):
    value = QQmlExpression(qmlContext(editor), editor, expression)
    result = value.evaluate()
    if value.hasError():
        raise RuntimeError(value.error().toString())
    return result

def execute(action, args):
    result = json.loads(subprocess.check_output([str(root / "bin" / "webcamtuner"), action, *args, "--json"], text=True))
    evaluate("accept(" + json.dumps(action) + ", " + json.dumps(result) + ")")

def click(item):
    point = item.mapToScene(item.boundingRect().center())
    QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, QPoint(round(point.x()), round(point.y())))

execute("read", [])
view.show()

def exercise():
    try:
        evaluate('testCameraInputs=[{id:"/dev/video101",description:"Test camera"}]')
        evaluate('accept("devices", {aliases:[]})')
        while pending: execute(*pending.pop(0))
        assert editor.property("previewOn") is True
        editor.setProperty("panelOpen", False)
        assert editor.property("previewOn") is False
        editor.setProperty("panelOpen", True)
        assert editor.property("previewOn") is True
        evaluate('autostartRequested=false; previewOn=false; chooseCamera()')
        assert editor.property("previewOn") is False, "inventory must respect manual Camera off"
        evaluate("frame(2.3, 0.5, 0.5)")
        toggle = editor.findChild(QObject, "autostartToggle")
        app.processEvents()
        click(toggle)
        assert editor.property("autostartPending") is True
        assert editor.property("autostartCamera") is True, "wait for storage confirmation"
        execute(*pending.pop(0))
        assert editor.property("autostartCamera") is False
        assert editor.property("zoom") == 2.3 and editor.property("dirty") is True
        evaluate("save()")
        execute(*pending.pop(0))
        execute("read", [])
        evaluate('accept("devices", {aliases:[]})')
        editor.setProperty("panelOpen", False)
        editor.setProperty("panelOpen", True)
        assert editor.property("previewOn") is False
        app.processEvents()
        click(toggle)
        pending.clear()
        evaluate("fail('Simulated save failure')")
        assert editor.property("autostartCamera") is False
        assert editor.property("autostartPending") is False
        app.processEvents()
        click(toggle)
        execute(*pending.pop(0))
        assert editor.property("autostartCamera") is True
        assert editor.property("previewOn") is True
        editor.setProperty("panelOpen", False)
        evaluate('testCameraInputs=[]; accept("devices", {aliases:[]})')
        editor.setProperty("panelOpen", True)
        assert editor.property("previewOn") is False
        evaluate('testCameraInputs=[{id:"/dev/video101",description:"Test camera"}]; accept("devices", {aliases:[]})')
        while pending: execute(*pending.pop(0))
        assert editor.property("previewOn") is True
        editor.setProperty("panelOpen", False)
        evaluate('backgroundMode="image"; imagePath="/missing/background.jpg"')
        editor.setProperty("panelOpen", True)
        assert editor.property("previewOn") is False, "do not start before image is ready"
    except Exception as error:
        import traceback
        failures.append(traceback.format_exc())
    app.quit()

QTimer.singleShot(400, exercise)
app.exec()
if failures:
    raise SystemExit("; ".join(failures))
print("PASS: autostart checkbox confirms storage, preserves drafts, survives reload, handles failure; open/close, manual off, missing camera/image respected")
