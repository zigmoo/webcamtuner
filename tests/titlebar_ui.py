"""Exercise titlebar pointer actions and the vertical alignment of visible controls."""
import os
from pathlib import Path
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_SCALE_FACTOR"] = "1"
from PySide6.QtCore import QObject, QPoint, Qt, QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QFontMetricsF
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest

root = Path(__file__).resolve().parent.parent
scratch = Path(os.environ["WEBCAMTUNER_TEST_ROOT"])
app = QGuiApplication(sys.argv)
view = QQuickView()
view.setResizeMode(QQuickView.SizeRootObjectToView)
view.setSource(QUrl.fromLocalFile(str(root / "ui" / "WindowTitleBar.qml")))
if view.status() == QQuickView.Error:
    raise SystemExit("Editor did not load")
view.resize(760, 42)
editor = view.rootObject()

dragged, failures = [], []
editor.moveRequested.connect(lambda: dragged.append("move"))
editor.minimizeRequested.connect(lambda: dragged.append("minimize"))
editor.closeRequested.connect(lambda: dragged.append("close"))

def click(item):
    point = item.mapToScene(item.boundingRect().center())
    QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, QPoint(round(point.x()), round(point.y())))

view.show()
def exercise():
    try:
        for name in ("toolbarGrip", "windowMinimizeButton", "windowCloseButton"):
            item = editor.findChild(QObject, name)
            assert abs(item.mapToScene(item.boundingRect().center()).y() - 21) < 0.5, name
        title = editor.findChild(QObject, "toolbarTitle")
        ink = QFontMetricsF(title.property("font")).tightBoundingRect("WebcamTuner")
        ink_center = title.y() + title.property("baselineOffset") + ink.center().y()
        assert abs(ink_center - 21) < 0.5, ink_center
        assert view.grabWindow().save(str(scratch / "centered-titlebar.png"))
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
print("PASS: titlebar grip, title ink and buttons are vertically centered; drag/minimize/close pointer actions work")
