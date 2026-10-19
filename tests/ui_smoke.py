"""Render the real editor and verify a crop save through its controller protocol without capture."""
import json
import os
from pathlib import Path
import subprocess
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_SCALE_FACTOR"] = "1"
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlExpression, qmlContext
from PySide6.QtQuick import QQuickView

root = Path(__file__).resolve().parent.parent
scratch = Path(os.environ["WEBCAMTUNER_TEST_ROOT"])
os.environ["WEBCAMTUNER_CONFIG_ROOT"] = str(scratch / "ui-profiles")
app = QGuiApplication(sys.argv)
view = QQuickView()
view.setResizeMode(QQuickView.SizeRootObjectToView)
view.setSource(QUrl.fromLocalFile(str(root / "ui" / "Editor.qml")))
if view.status() == QQuickView.Error:
    raise SystemExit("Editor did not load")
view.resize(760, 1040)
editor = view.rootObject()
editor.setProperty("testing", True)

def evaluate(expression):
    value = QQmlExpression(qmlContext(editor), editor, expression)
    result = value.evaluate()
    if value.hasError():
        raise RuntimeError(value.error().toString())
    return result

def controller(action, args):
    if hasattr(args, "toVariant"):
        args = args.toVariant()
    result = json.loads(subprocess.check_output([str(root / "bin" / "webcamtuner"), action, *args, "--json"], text=True))
    evaluate("accept(" + json.dumps(action) + ", " + json.dumps(result) + ")")

editor.request.connect(controller)
controller("read", [])
view.show()
failures = []
finished = False

def exercise():
    try:
        evaluate("frame(2, 0.6, 0.4)")
        editor.setProperty("backgroundMode", "blur")
        evaluate("save()")
        document = json.loads((scratch / "ui-profiles" / "profiles.json").read_text())
        assert document["profiles"][0]["crop"] == {"zoom": 2, "centerX": 0.6, "centerY": 0.4}
        assert document["profiles"][0]["background"]["mode"] == "blur"
        assert editor.property("dirty") is False
        evaluate("frame(3, 0.5, 0.5)")
        controller("read", [])
        assert editor.property("zoom") == 2
        assert editor.property("dirty") is False
        QTimer.singleShot(300, finish)
    except Exception as error:
        failures.append(str(error))
        app.quit()

def finish():
    global finished
    image = view.grabWindow()
    if image.isNull() or not image.save(str(scratch / "webcamtuner-design.png")):
        failures.append("Could not render screenshot")
    finished = True
    app.quit()

QTimer.singleShot(400, exercise)
QTimer.singleShot(10000, app.quit)
app.exec()
if not finished:
    failures.append("UI check did not complete before shutdown")
if failures:
    raise SystemExit("; ".join(failures))
print("PASS: real QML editor saved and reloaded crop/background preferences; no camera capture")
