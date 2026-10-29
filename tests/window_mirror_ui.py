"""Exercise mirror confirmation and unsaved crop preservation."""
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
os.environ["WEBCAMTUNER_CONFIG_ROOT"] = str(scratch / ("mirror-ui-" + uuid.uuid4().hex))
app = QGuiApplication(sys.argv)
view = QQuickView()
view.setResizeMode(QQuickView.SizeRootObjectToView)
view.setSource(QUrl.fromLocalFile(str(root / "ui" / "Editor.qml")))
if view.status() == QQuickView.Error:
    raise SystemExit("Editor did not load")
view.resize(760, 1080)
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
        assert editor.property("mirror") is True
        evaluate("frame(2.3, 0.5, 0.5)")
        toggle = editor.findChild(QObject, "mirrorToggle")
        click(toggle)
        assert len(pending) == 1
        assert editor.property("mirrorPending") is True
        assert editor.property("mirror") is True
        execute(*pending.pop(0))
        assert editor.property("mirror") is False
        assert editor.property("mirrorPending") is False
        assert editor.property("zoom") == 2.3 and editor.property("dirty") is True
        app.processEvents()
        click(toggle)
        assert editor.property("mirrorPending") is True
        pending.clear()
        evaluate("fail('Simulated save failure')")
        assert editor.property("mirror") is False and editor.property("mirrorPending") is False
        evaluate("save()")
        execute(*pending.pop(0))
        execute("read", [])
        assert editor.property("mirror") is False and editor.property("zoom") == 2.3
    except Exception as error:
        failures.append(str(error) or type(error).__name__)
    app.quit()

QTimer.singleShot(400, exercise)
app.exec()
if failures:
    raise SystemExit("; ".join(failures))
print("PASS: mirror waits for verified save, retains draft crop, handles failed save")
