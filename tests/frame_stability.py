"""Check rendered pixels during asynchronous frame replacement, without using a camera."""
import os
from pathlib import Path
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_SCALE_FACTOR"] = "1"
from PIL import Image
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtGui import QGuiApplication, QColor
from PySide6.QtQml import QQmlExpression, qmlContext
from PySide6.QtQuick import QQuickView

root = Path(__file__).resolve().parent.parent
scratch = Path(os.environ["WEBCAMTUNER_TEST_ROOT"])
scratch.mkdir(parents=True, exist_ok=True)
paths = [scratch / "frame-red.png", scratch / "frame-green.png"]
for path, color in zip(paths, [(200, 30, 30), (30, 200, 30)]):
    Image.new("RGB", (1920, 1080), color).save(path)
app = QGuiApplication(sys.argv)
view = QQuickView()
view.setResizeMode(QQuickView.SizeRootObjectToView)
view.setColor(QColor("black"))
view.setSource(QUrl.fromLocalFile(str(root / "ui" / "PreviewFrame.qml")))
if view.status() == QQuickView.Error:
    raise SystemExit("Preview frame did not load")
view.resize(640, 360)
frame = view.rootObject()
frame.setProperty("source", QUrl.fromLocalFile(str(paths[0])))
view.show()
failures, samples = [], []
attempts = 0

def inspect():
    global attempts
    attempts += 1
    try:
        if attempts > 100:
            raise RuntimeError("Frame stability check timed out")
        expression = QQmlExpression(qmlContext(frame), frame, "Number(status)")
        status = expression.evaluate()
        if isinstance(status, tuple): status = status[0]
        if status != 1:
            QTimer.singleShot(10, inspect)
            return
        frame.setProperty("source", QUrl.fromLocalFile(str(paths[(len(samples) + 1) % 2])))
        image = view.grabWindow()
        pixel = image.pixelColor(100, 100)
        if pixel.red() + pixel.green() + pixel.blue() < 100:
            raise RuntimeError("Preview went blank while loading its next frame")
        samples.append((pixel.red(), pixel.green(), pixel.blue()))
        if len(samples) >= 12:
            app.quit()
            return
        QTimer.singleShot(25, inspect)
    except Exception as error:
        failures.append(str(error)); app.quit()

QTimer.singleShot(100, inspect)
app.exec()
if failures or len(samples) != 12:
    raise SystemExit("; ".join(failures) or "Incomplete frame check")
print("PASS: 12 asynchronous frame replacements rendered without blank pixels")
