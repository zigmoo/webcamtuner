"""The overlay measures decoded frames and returns to zero when they stop."""
import os, uuid
from pathlib import Path
os.environ.update(QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtQml import QQmlExpression, qmlContext
root=Path(__file__).resolve().parent.parent
scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('fps-'+uuid.uuid4().hex); scratch.mkdir()
harness=scratch/'fps.qml'
harness.write_text('''import QtQuick
import "'''+(root/'ui').as_uri()+'''" as Tuner
Item {width:400;height:100
 Tuner.FpsIndicator {id:fps;objectName:"fps";active:true}
 Timer {id:frames;interval:33;running:true;repeat:true;onTriggered:fps.frameReady()}
 function stopFrames(){frames.stop()}
}''')
app=QGuiApplication([]);view=QQuickView();view.setSource(QUrl.fromLocalFile(str(harness)))
assert view.status()!=QQuickView.Error
item=view.rootObject();fps=item.findChild(type(item),'fps');view.show()
errors=[];finished=False
def ev(expression):
    e=QQmlExpression(qmlContext(item),item,expression);e.evaluate();assert not e.hasError(),e.error().toString()
def sample():
    try:
        assert 24<=fps.property('measuredFps')<=36, fps.property('measuredFps')
        ev('stopFrames()');QTimer.singleShot(2200,stopped)
    except Exception as e:errors.append(repr(e));app.quit()
def stopped():
    global finished
    try:
        assert fps.property('measuredFps')==0
        fps.setProperty('active',False);assert not fps.property('visible')
        finished=True;print('PASS: preview overlay updates from decoded frames, shows zero on stall and hides when camera is off')
    except Exception as e:errors.append(repr(e))
    app.quit()
QTimer.singleShot(1200,sample);QTimer.singleShot(7000,app.quit);app.exec()
if errors or not finished:raise SystemExit('; '.join(errors) or 'FPS test timed out')
