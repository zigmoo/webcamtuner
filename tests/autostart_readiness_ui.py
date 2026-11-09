"""Autostart intent survives delayed readiness and a previous stopped producer."""
import os
from pathlib import Path
os.environ.update(QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlExpression, qmlContext
from PySide6.QtQuick import QQuickView

root = Path(__file__).resolve().parents[1]
app=QGuiApplication([]);view=QQuickView()
view.setSource(QUrl.fromLocalFile(str(root/'ui/Editor.qml')))
assert not view.errors(), view.errors()
editor=view.rootObject();editor.setProperty('testing',True);editor.setProperty('panelOpen',False)
component=QQmlComponent(view.engine())
component.setData(b'''import QtQuick
QtObject {
 property bool checked:true;property bool readyToStart:false;property bool published:false;property bool busy:false
 property bool startingCamera:false;property bool stopping:false;property bool cameraSwitching:false
 property var state:({processed:true,published:false,state:"stopped"});property string cameraFeedback:"";property int configurationRevision:0
 property int starts:0
 signal starting();signal started();signal stopped();signal failed(string message)
 function start(){if(!readyToStart||busy||stopping)return false;starts++;startingCamera=true;starting();return true}
 function stop(){stopping=true;stopped()}
}''',QUrl())
output=component.create();assert output,component.errors()
view.engine().rootContext().setContextProperty('fixture',output)
def ev(code):
 e=QQmlExpression(qmlContext(editor),editor,code);r=e.evaluate();assert not e.hasError(),e.error().toString();return r
ev('outputControl=fixture;document={profiles:[]};testCameraInputs=[{id:"/dev/video101",description:"Saved camera"}];savedCamera="/dev/video101";cameraChoiceReady=true;section="camera"')
errors=[];finished=False
def check():
 global finished
 try:
  editor.setProperty('panelOpen',True)
  assert output.property('starts')==0 and editor.property('autostartRequested'),'Rejected start must retain intent'
  output.setProperty('readyToStart',True)
  assert output.property('starts')==1 and not editor.property('autostartRequested')
  output.setProperty('published',True);output.setProperty('startingCamera',False);output.started.emit()
  assert editor.property('previewOn')
  editor.setProperty('panelOpen',False);output.setProperty('published',False);output.setProperty('busy',True)
  editor.setProperty('panelOpen',True)
  assert output.property('starts')==1 and editor.property('autostartRequested')
  output.setProperty('busy',False)
  assert output.property('starts')==2,'Previous processed/stopped state must not veto reopening'
  output.setProperty('published',True);output.setProperty('startingCamera',False);output.started.emit()
  ev('stopCamera()');output.setProperty('published',False);output.setProperty('state',{'processed':True,'published':False});output.setProperty('stopping',False)
  assert output.property('starts')==2 and not editor.property('autostartRequested'),'Manual Stop must stay stopped'
  editor.setProperty('panelOpen',False);editor.setProperty('autostartCamera',False);editor.setProperty('panelOpen',True)
  assert output.property('starts')==2
  finished=True;print('PASS: delayed-ready and busy starts retain autostart; stopped producer reopens; manual Stop and disabled checkbox stay off')
 except Exception as e:errors.append(str(e))
 app.quit()
QTimer.singleShot(100,check);QTimer.singleShot(4000,app.quit);app.exec()
if errors or not finished:raise SystemExit('; '.join(errors) or 'Autostart readiness timed out')
