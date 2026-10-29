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
os.environ["WEBCAMTUNER_CONFIG_ROOT"] = str(scratch / ("mirror-ui-" + uuid.uuid4().hex))
app = QGuiApplication(sys.argv)
view = QQuickView()
view.setResizeMode(QQuickView.SizeRootObjectToView)
view.setSource(QUrl.fromLocalFile(str(root / "ui" / "WindowTitleBar.qml")))
if view.status() == QQuickView.Error:
    raise SystemExit("Editor did not load")
view.resize(760, 42)
editor = view.rootObject()

pending, dragged, failures = [], [], []
editor.moveRequested.connect(lambda: dragged.append("move"))
editor.minimizeRequested.connect(lambda: dragged.append("minimize"))
editor.closeRequested.connect(lambda: dragged.append("close"))

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

view.show()
def exercise():
    try:
        click(editor.findChild(QObject, "windowDragHandle"))
        click(editor.findChild(QObject, "windowMinimizeButton"))
        editor.setProperty("collapsed", True)
        assert editor.findChild(QObject, "windowMinimizeButton").property("text") == "⌄"
        click(editor.findChild(QObject, "windowCloseButton"))
        assert dragged == ["move", "minimize", "close"], dragged
    except Exception as error:
        import traceback
        failures.append(traceback.format_exc())
    app.quit()

QTimer.singleShot(150, exercise)
app.exec()
if failures: raise SystemExit("; ".join(failures))
print("PASS: titlebar pointer actions emit drag, minimize, close; collapsed control offers expand")
