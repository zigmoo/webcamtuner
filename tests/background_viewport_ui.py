"""Background editing fits normally; ordinary wheel scrolling reaches every control."""
import json,os,subprocess,uuid
from pathlib import Path
os.environ.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
from PIL import Image
from PySide6.QtCore import QUrl,QTimer,QObject,QPointF,QPoint,Qt
from PySide6.QtGui import QGuiApplication,QColor,QWheelEvent
from PySide6.QtQuick import QQuickView
from PySide6.QtQml import QQmlExpression,qmlContext
root=Path(__file__).resolve().parent.parent;scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('background-layout-'+uuid.uuid4().hex);scratch.mkdir()
os.environ.update(WEBCAMTUNER_CONFIG_ROOT=str(scratch/'profiles'),XDG_DATA_HOME=str(scratch/'data'),XDG_CACHE_HOME=str(scratch/'cache'))
folder=scratch/'data/webcamtuner/backgrounds';folder.mkdir(parents=True)
for i in range(22):Image.new('RGB',(640,360),(i*9,70,130)).save(folder/f'Photo-{i:02}.jpg')
app=QGuiApplication([]);v=QQuickView();v.setResizeMode(QQuickView.SizeRootObjectToView);v.setColor(QColor('#171c24'));v.setSource(QUrl.fromLocalFile(str(root/'ui/Editor.qml')));assert v.status()!=QQuickView.Error
v.resize(700,780);editor=v.rootObject();editor.setProperty('testing',True)
def ev(text):
 e=QQmlExpression(qmlContext(editor),editor,text);r=e.evaluate();assert not e.hasError(),e.error().toString()
 return r[0] if isinstance(r,tuple) else r
def controller(action,args):
 if hasattr(args,'toVariant'):args=args.toVariant()
 result=json.loads(subprocess.check_output([str(root/'bin/webcamtuner'),action,*args,'--json'],text=True));ev('accept('+json.dumps(action)+','+json.dumps(result)+')')
editor.request.connect(controller);controller('read',[]);editor.setProperty('section','background');ev('chooseBackground('+json.dumps(str(folder/'Photo-21.jpg'))+')');v.show()
failures=[];finished=False

def normal():
 try:
  for name in ('backgroundLibraryPath','profileSaveState'):
   item=editor.findChild(QObject,name);point=item.mapToItem(editor,QPointF(0,0))
   assert point.y()>=0 and point.y()+item.height()<=editor.height(),(name,point.y(),item.height(),editor.height())
  assert v.grabWindow().save(str(Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/'background-layout-fixed.png'))
  v.resize(540,420);QTimer.singleShot(200,scroll_into_view)
 except Exception as e:failures.append(str(e));app.quit()
def scroll_into_view():
 try:
  global flick,stage,before
  scroll=editor.findChild(QObject,'editorScroll');flick=scroll.property('contentItem');stage=editor.findChild(QObject,'backgroundGrid')
  bar=editor.findChild(QObject,'editorScrollbar');assert bar.property('visible')
  assert bar.height()>200 and bar.mapToItem(editor,QPointF(0,0)).x()>editor.width()-50
  y=stage.mapToItem(editor,QPointF(0,0)).y();flick.setProperty('contentY',max(0,flick.property('contentY')+y-140));stage.setProperty('contentY',132)
  QTimer.singleShot(100,wheel)
 except Exception as e:failures.append(str(e));app.quit()
def wheel():
 try:
  global before
  before=stage.property('contentY')
  pos=stage.mapToScene(QPointF(stage.width()/2,stage.height()/2))
  event=QWheelEvent(pos,QPointF(v.mapToGlobal(pos.toPoint())),QPoint(0,0),QPoint(0,120),Qt.NoButton,Qt.NoModifier,Qt.ScrollUpdate,False)
  QGuiApplication.sendEvent(v,event);QTimer.singleShot(200,finish)
 except Exception as e:failures.append(str(e));app.quit()
def finish():
 global finished
 try:
  assert stage.property('contentY')<before,'Wheel over the background grid must scroll its images'
  assert ev('backgroundCrop.zoom')==1,'Plain scrolling must not change background zoom'
  flick.setProperty('contentY',flick.property('contentHeight'))
  item=editor.findChild(QObject,'profileSaveState');point=item.mapToItem(editor,QPointF(0,0));assert 0<=point.y()<editor.height()
  finished=True;print('PASS: bounded background editor, pinned actions, visible overflow scrollbar and ordinary wheel scrolling')
 except Exception as e:failures.append(str(e))
 app.quit()
QTimer.singleShot(600,normal);QTimer.singleShot(10000,app.quit);app.exec()
if failures or not finished:raise SystemExit('; '.join(failures) or 'Layout test timed out')
