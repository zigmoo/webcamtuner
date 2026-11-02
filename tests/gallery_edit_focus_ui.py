"""Thumbnail caption editing survives background polling and unrelated controller work."""
import os,json,subprocess,uuid,traceback
from pathlib import Path
os.environ.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
from PIL import Image
from PySide6.QtCore import QUrl,QTimer,QPointF,Qt,QEvent
from PySide6.QtGui import QGuiApplication,QKeyEvent
from PySide6.QtQuick import QQuickView,QQuickItem
from PySide6.QtQml import QQmlExpression,qmlContext
from PySide6.QtTest import QTest
root=Path(__file__).resolve().parent.parent;scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('caption-focus-'+uuid.uuid4().hex);scratch.mkdir()
os.environ.update(WEBCAMTUNER_CONFIG_ROOT=str(scratch/'config'),XDG_DATA_HOME=str(scratch/'data'),XDG_CACHE_HOME=str(scratch/'cache'))
source=scratch/'Scene.png';Image.new('RGB',(640,360),'#246080').save(source)
app=QGuiApplication([]);v=QQuickView();v.setResizeMode(QQuickView.SizeRootObjectToView);v.setSource(QUrl.fromLocalFile(str(root/'ui/Editor.qml')));assert not v.errors()
v.resize(760,780);editor=v.rootObject();editor.setProperty('testing',True)
def ev(code):
 e=QQmlExpression(qmlContext(editor),editor,code);r=e.evaluate();assert not e.hasError(),e.error().toString();return r[0] if isinstance(r,tuple) else r
def controller(action,args):
 if hasattr(args,'toVariant'):args=args.toVariant()
 result=json.loads(subprocess.check_output([str(root/'bin/webcamtuner'),action,*args,'--json'],text=True));ev('accept('+json.dumps(action)+','+json.dumps(result)+')')
editor.request.connect(controller);controller('read',[]);editor.setProperty('section','background');ev('addBackgrounds('+json.dumps([str(source)])+')');v.show()
def caption(item):
 if item.objectName().startswith('backgroundLabel-'):return item
 if isinstance(item,QQuickItem):
  for c in item.childItems():
   result=caption(c)
   if result:return result
errors=[];finished=False
def start():
 global field
 try:
  field=caption(editor);assert field
  point=field.mapToScene(QPointF(field.width()/2,field.height()/2)).toPoint();QTest.mouseClick(v,Qt.LeftButton,Qt.NoModifier,point)
  QTest.keyClick(v,Qt.Key_A,Qt.ControlModifier);QGuiApplication.sendEvent(v,QKeyEvent(QEvent.KeyPress,0,Qt.NoModifier,'Not finished'))
  editor.setProperty('busy',True);controller('backgrounds',[])
  QTimer.singleShot(1100,finish)
 except Exception:errors.append(traceback.format_exc());app.quit()
def finish():
 global finished
 try:
  assert field.property('activeFocus') and field.property('text')=='Not finished'
  assert caption(editor)==field,'A poll must not recreate the active caption delegate'
  editor.setProperty('busy',False);QGuiApplication.sendEvent(v,QKeyEvent(QEvent.KeyPress,0,Qt.NoModifier,' yet'));QTest.keyClick(v,Qt.Key_Return)
  assert ev('backgroundLibrary.items[0].label')=='Not finished yet'
  finished=True;print('PASS: gallery edit keeps focus/text through polling and busy work; Enter commits complete caption')
 except Exception:errors.append(traceback.format_exc())
 app.quit()
QTimer.singleShot(500,start);QTimer.singleShot(8000,app.quit);app.exec()
if errors or not finished:raise SystemExit('; '.join(errors) or 'Caption focus test timed out')
