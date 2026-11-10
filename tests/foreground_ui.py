"""Dragging positions the foreground at 1x and persists it independently of camera crop."""
import os,json,subprocess,uuid
from pathlib import Path
os.environ.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
from PySide6.QtCore import QUrl,QTimer,QObject,QPointF,Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtQml import QQmlExpression,qmlContext
from PySide6.QtTest import QTest
root=Path(__file__).resolve().parent.parent;scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('placement-'+uuid.uuid4().hex);scratch.mkdir()
os.environ['WEBCAMTUNER_CONFIG_ROOT']=str(scratch/'config')
app=QGuiApplication([]);v=QQuickView();v.setResizeMode(QQuickView.SizeRootObjectToView);v.setSource(QUrl.fromLocalFile(str(root/'ui/Editor.qml')));assert v.status()!=QQuickView.Error
v.resize(700,780);editor=v.rootObject();editor.setProperty('testing',True);editor.setProperty('section','camera')
def ev(text):
 e=QQmlExpression(qmlContext(editor),editor,text);r=e.evaluate();assert not e.hasError(),e.error().toString();return r[0] if isinstance(r,tuple) else r
def controller(action,args):
 if hasattr(args,'toVariant'):args=args.toVariant()
 result=json.loads(subprocess.check_output([str(root/'bin/webcamtuner'),action,*args,'--json'],text=True));ev('accept('+json.dumps(action)+','+json.dumps(result)+')')
editor.request.connect(controller);controller('read',[]);v.show();errors=[];finished=False

def exercise():
 global finished
 try:
  stage=editor.findChild(QObject,'cameraCompositionStage')
  for mirror in (True,False):
   editor.setProperty('mirror',mirror);ev('placeForeground(0,0)')
   handle=editor.findChild(QObject,'cameraMoveDrag')
   start=handle.mapToScene(QPointF(handle.width()*.5,handle.height()*.5)).toPoint()
   end=start+QPointF(stage.width()*.3,stage.height()*.2).toPoint()
   QTest.mousePress(v,Qt.LeftButton,Qt.NoModifier,start);QTest.mouseMove(v,end,30);QTest.mouseRelease(v,Qt.LeftButton,Qt.NoModifier,end)
   assert 0.28<ev('foreground.x')*(-1 if mirror else 1)<0.32 and 0.18<ev('foreground.y')<0.22
   assert editor.property('zoom')==1 and editor.property('centerX')==.5
  ev('save()');stored=json.loads((scratch/'config/profiles.json').read_text());assert stored['profiles'][0]['foreground']['x']>.28
  controller('read',[]);assert ev('foreground.x')>.28
  ev('resetFrame()');assert ev('foreground.x')==0 and ev('foreground.y')==0
  finished=True;print('PASS: free foreground drag at 1x, both mirror modes, saved readback and reset')
 except Exception as e:errors.append(str(e))
 app.quit()
QTimer.singleShot(400,exercise);QTimer.singleShot(6000,app.quit);app.exec()
if errors or not finished:raise SystemExit('; '.join(errors) or 'Placement test timed out')
