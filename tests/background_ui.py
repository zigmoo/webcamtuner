"""Verify that choosing an image actually displays it, reports errors, and persists it."""
import json
import os
from pathlib import Path
import subprocess
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_SCALE_FACTOR"] = "1"
from PIL import Image
from PySide6.QtCore import QObject, QUrl, QTimer, QPointF
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlExpression, qmlContext
from PySide6.QtQuick import QQuickView

root = Path(__file__).resolve().parent.parent
scratch = Path(os.environ["WEBCAMTUNER_TEST_ROOT"])
scratch.mkdir(parents=True, exist_ok=True)
os.environ["WEBCAMTUNER_CONFIG_ROOT"] = str(scratch / "background-ui-profiles")
fixture = scratch / "background #1's image.jpeg"
Image.new("RGB", (800, 450), (180, 90, 40)).save(fixture)
path = Path(os.environ.get("WEBCAMTUNER_ACCEPTANCE_IMAGE", str(fixture)))
app = QGuiApplication(sys.argv)
view = QQuickView()
view.setResizeMode(QQuickView.SizeRootObjectToView)
view.setSource(QUrl.fromLocalFile(str(root / "ui" / "Editor.qml")))
if view.status() == QQuickView.Error:
    raise SystemExit("Editor did not load")
view.resize(760, 1120)
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
stage = 0
checks = 0

def exercise():
    global stage, checks
    checks += 1
    try:
        if checks > 60:
            raise RuntimeError("Image UI check timed out: " + str({"stage": stage, "ready": editor.property("imageReady"), "feedback": editor.property("backgroundFeedback"), "source": evaluate("String(backgroundImage.source)"), "status": evaluate("backgroundImage.status"), "expected": evaluate("backgroundUrl(imagePath)")}))
        if stage == 0:
            evaluate("chooseBackground(" + json.dumps(str(path)) + ")")
            stage = 1
        elif stage == 1 and editor.property("imageReady"):
            assert editor.property("backgroundMode") == "image"
            assert "Image loaded" in editor.property("backgroundFeedback")
            evaluate("save()")
            document = json.loads((scratch / "background-ui-profiles" / "profiles.json").read_text())
            assert document["profiles"][0]["background"] == {"mode": "image", "imagePath": str(path)}
            assert not editor.property("dirty")
            image = view.grabWindow()
            assert image.save(str(scratch / "webcamtuner-background.png"))
            background = editor.findChild(QObject, "backgroundImage")
            assert background is not None
            if path == fixture:
                point = background.mapToScene(QPointF(10, 10))
                pixel = image.pixelColor(round(point.x()), round(point.y()))
                assert abs(pixel.red() - 180) < 8 and abs(pixel.green() - 90) < 8 and abs(pixel.blue() - 40) < 8
            evaluate("chooseBackground('/no/such/webcamtuner-background.jpeg')")
            stage = 2
        elif stage == 2 and "Cannot load" in editor.property("backgroundFeedback"):
            assert not editor.property("imageReady")
            button = editor.findChild(QObject, "saveButton")
            assert not button.property("enabled")
            controller("read", [])
            stage = 3
        elif stage == 3 and editor.property("imageReady"):
            assert editor.property("imagePath") == str(path)
            assert not editor.property("dirty")
            stage = 4
            app.quit()
            return
        QTimer.singleShot(100, exercise)
    except Exception as error:
        failures.append(str(error))
        app.quit()

QTimer.singleShot(200, exercise)
app.exec()
if failures or stage != 4:
    raise SystemExit("; ".join(failures) or "Incomplete UI check")
print("PASS: selected image displayed, saved, restored; missing image reported and save disabled")
