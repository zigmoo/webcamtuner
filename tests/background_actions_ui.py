"""Real thumbnail controls select crop, confirm locks and move files to OS Trash."""
import os,json,subprocess,uuid
from pathlib import Path
os.environ.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
from PIL import Image
from PySide6.QtCore import QUrl,QTimer,QObject,QPointF,Qt,QEvent
from PySide6.QtGui import QGuiApplication,QKeyEvent
from PySide6.QtQuick import QQuickView,QQuickItem
from PySide6.QtQml import QQmlExpression,qmlContext
from PySide6.QtTest import QTest
root=Path(__file__).resolve().parent.parent;scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('image-actions-'+uuid.uuid4().hex);scratch.mkdir()
os.environ.update(WEBCAMTUNER_CONFIG_ROOT=str(scratch/'config'),XDG_DATA_HOME=str(scratch/'data'),XDG_CACHE_HOME=str(scratch/'cache'))
images=[]
for name,color in [('One','red'),('Two','blue')]:
 p=scratch/(name+'.png');Image.new('RGB',(640,360),color).save(p);images.append(str(p))
app=QGuiApplication([]);v=QQuickView();v.setResizeMode(QQuickView.SizeRootObjectToView);v.setSource(QUrl.fromLocalFile(str(root/'ui/Editor.qml')));assert v.status()!=QQuickView.Error
v.resize(700,780);editor=v.rootObject();editor.setProperty('testing',True)
def ev(text):
 e=QQmlExpression(qmlContext(editor),editor,text);r=e.evaluate();assert not e.hasError(),e.error().toString();return r[0] if isinstance(r,tuple) else r
def controller(action,args):
 if hasattr(args,'toVariant'):args=args.toVariant()
 result=json.loads(subprocess.check_output([str(root/'bin/webcamtuner'),action,*args,'--json'],text=True));ev('accept('+json.dumps(action)+','+json.dumps(result)+')')
editor.request.connect(controller);controller('read',[]);editor.setProperty('section','background');ev('addBackgrounds('+json.dumps(images)+')');ev('save()');v.show()
errors=[];finished=False

def find_visual(item,name):
 if item.objectName()==name:return item
 if isinstance(item,QQuickItem):
  for child in item.childItems():
   result=find_visual(child,name)
   if result:return result
 return None
def click(name):
 item=find_visual(editor,name);assert item,name
 point=item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint();QTest.mouseClick(v,Qt.LeftButton,Qt.NoModifier,point);app.processEvents()
def exercise():
 global finished
 try:
  data=json.loads(ev('JSON.stringify(backgroundLibrary.items)'));second=next(i for i in data if i['name']=='Two.png')
  suffix=second['id'];click('backgroundAction-crop-'+suffix);assert editor.property('imagePath')==second['path']
  caption=find_visual(editor,'backgroundLabel-'+suffix)
  point=caption.mapToScene(QPointF(caption.width()/2,caption.height()/2)).toPoint()
  QTest.mouseClick(v,Qt.LeftButton,Qt.NoModifier,point);QTest.keyClick(v,Qt.Key_A,Qt.ControlModifier)
  QGuiApplication.sendEvent(v,QKeyEvent(QEvent.KeyPress,0,Qt.NoModifier,'Blue sky'))
  QTest.keyClick(v,Qt.Key_Return);app.processEvents()
  data=json.loads(ev('JSON.stringify(backgroundLibrary.items)'));assert next(i for i in data if i['id']==suffix)['label']=='Blue sky'
  assert Path(second['path']).exists() and next(i for i in data if i['id']==suffix)['name']==second['name']
  click('backgroundAction-lock-'+suffix);assert ev('backgroundLocked')
  assert not editor.findChild(QObject,'backgroundZoom').property('enabled')
  assert not find_visual(editor,'backgroundAction-trash-'+suffix).property('enabled')
  click('backgroundAction-lock-'+suffix);assert not ev('backgroundLocked')
  ev('placeForeground(0.2,0.1)');click('backgroundAction-trash-'+suffix)
  assert editor.findChild(QObject,'trashBackgroundDialog').property('visible')
  ev('trashBackgroundDialog.accept()');assert not Path(second['path']).exists()
  assert ev('backgroundLibrary.items.length')==1 and editor.property('backgroundMode')=='blur'
  assert ev('foreground.x')==.2 and editor.property('dirty')
  assert len(list((scratch/'data/Trash/files').iterdir()))==1
  finished=True;print('PASS: inline label, crop/lock/unlock/trash thumbnail actions; OS Trash, grid refresh and unrelated draft preservation')
 except Exception as e:
  import traceback
  errors.append(traceback.format_exc())
 app.quit()
QTimer.singleShot(600,exercise);QTimer.singleShot(10000,app.quit);app.exec()
if errors or not finished:raise SystemExit('; '.join(errors) or 'Action test timed out')
