"""Camera starts link preview to shared output; Stop shuts both down."""
import os
from pathlib import Path
import sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QUICK_BACKEND'] = 'software'
from PySide6.QtCore import QObject, QPoint, Qt, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlExpression, qmlContext
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest

root=Path(__file__).resolve().parents[1]
scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])
app=QGuiApplication(sys.argv);view=QQuickView();view.setResizeMode(QQuickView.SizeRootObjectToView)
view.setSource(QUrl.fromLocalFile(str(root/'ui/Editor.qml')))
assert view.status()!=QQuickView.Error
editor=view.rootObject();editor.setProperty('testing',True);editor.setProperty('section','camera')
component=QQmlComponent(view.engine())
component.setData(b'''import QtQuick
QtObject {
 property bool checked:true; property bool published:true; property bool busy:false
 property bool startingCamera:false; property bool stopping:false; property bool cameraSwitching:false
 property var state:({serviceActive:true}); property string cameraFeedback:""; property int configurationRevision:0
 property int stops:0; property int starts:0
 signal starting(); signal started(); signal stopped(); signal failed(string message); signal cameraRejected(string camera)
 function stop(){stops++;stopping=true;stopped()}
 function start(){starts++;startingCamera=true;starting()}
}''',QUrl())
fake=component.create();assert fake is not None,component.errors()
view.engine().rootContext().setContextProperty('powerFixture',fake)
def evaluate(text):
 e=QQmlExpression(qmlContext(editor),editor,text);value=e.evaluate()
 assert not e.hasError(),e.error().toString()
 return value
def click(button):
 point=button.mapToScene(button.boundingRect().center())
 QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,QPoint(round(point.x()),round(point.y())))
evaluate('outputControl=powerFixture;autostartRequested=true;previewOn=true')
view.resize(760,1000);view.show();failures=[]
def exercise():
 try:
  stop=editor.findChild(QObject,'stopCameraButton');assert stop is not None and stop.property('visible') and stop.property('enabled')
  assert stop.property('text')=='Stop Camera'
  point=stop.mapToScene(stop.boundingRect().center());QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,QPoint(round(point.x()),round(point.y())))
  assert fake.property('stops')==1
  assert not editor.property('previewOn') and not editor.property('autostartRequested')
  assert fake.property('published'), 'Published state must wait for backend confirmation'
  assert stop.property('text')=='Stopping Camera…' and not stop.property('enabled')
  fake.setProperty('published',False);fake.setProperty('state',{});fake.setProperty('stopping',False)
  evaluate('previewOn=true;autostartRequested=true');app.processEvents()
  point=stop.mapToScene(stop.boundingRect().center());QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,QPoint(round(point.x()),round(point.y())))
  assert not editor.property('previewOn') and fake.property('stops')==1, 'Preview-only Stop must not start output'
  assert editor.findChild(QObject,'startCameraButton') is not None
  start=editor.findChild(QObject,'startCameraButton');preview=editor.findChild(QObject,'previewCameraButton')
  # Keep real media capture disabled while exercising each actual button handler.
  view.engine().rootContext().setContextProperty('startFixture',start)
  view.engine().rootContext().setContextProperty('previewFixture',preview)
  evaluate('startFixture.enabled=true;previewFixture.enabled=true;previewOn=false')
  click(start)
  assert fake.property('starts')==1 and editor.property('resumeOutputPreview')
  assert not editor.property('previewOn'), 'Wait for the shared publisher before previewing'
  fake.setProperty('published',True);fake.setProperty('startingCamera',False);fake.started.emit();app.processEvents()
  assert editor.property('previewOn'), 'Start Camera must also show the preview'
  click(preview)
  assert not editor.property('previewOn') and fake.property('published'), 'Hide preview must keep calls live'
  click(preview)
  assert editor.property('previewOn') and fake.property('starts')==1, 'Showing a live camera must reuse output'
  evaluate('previewOn=false');fake.setProperty('published',False)
  click(preview)
  assert fake.property('starts')==2 and editor.property('resumeOutputPreview'), 'Preview camera must start shared output'
  click(preview)
  assert fake.property('starts')==2, 'Pending start must not be duplicated'
  fake.setProperty('published',True);fake.setProperty('startingCamera',False);fake.started.emit();app.processEvents()
  assert editor.property('previewOn')
  click(stop)
  assert fake.property('stops')==2 and not editor.property('previewOn')
  fake.setProperty('published',False);fake.setProperty('stopping',False)
  evaluate('document={profiles:[]};testCameraInputs=[{id:"/dev/video101",description:"Test camera"}];savedCamera="/dev/video101";cameraChoiceReady=true;autostartRequested=true;maybeAutostart()')
  assert fake.property('starts')==3, 'Automatic preview must also start shared output'
  fake.setProperty('published',True);fake.setProperty('startingCamera',False);fake.started.emit();app.processEvents()
  assert editor.property('previewOn')
  view.grabWindow().save(str(scratch/'camera-power.png'))
  print('PASS: Start Camera, Preview camera and autostart share output and preview; Hide preserves output; Stop shuts both down')
 except Exception as error:failures.append(str(error))
 app.quit()
QTimer.singleShot(400,exercise);QTimer.singleShot(6000,app.quit);app.exec()
if failures:raise SystemExit('; '.join(failures))
