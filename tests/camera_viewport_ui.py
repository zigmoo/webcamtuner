"""Primary camera controls fit a normal opening size; overflow has a scrollbar."""
import json,os,subprocess,sys
from pathlib import Path
os.environ.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
from PySide6.QtCore import QUrl,QTimer,QObject,QPointF
from PySide6.QtGui import QGuiApplication,QColor
from PySide6.QtQuick import QQuickView
from PySide6.QtQml import QQmlExpression,qmlContext
root=Path(__file__).resolve().parent.parent
scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])
os.environ['WEBCAMTUNER_CONFIG_ROOT']=str(scratch/'viewport-profiles')
app=QGuiApplication([]);view=QQuickView();view.setResizeMode(QQuickView.SizeRootObjectToView);view.setColor(QColor('#171c24'))
view.setSource(QUrl.fromLocalFile(str(root/'ui/Editor.qml')));assert view.status()!=QQuickView.Error
view.resize(640,680);editor=view.rootObject();editor.setProperty('testing',True);editor.setProperty('section','camera')
e=QQmlExpression(qmlContext(editor),editor,'accept("read",'+subprocess.check_output([str(root/'bin/webcamtuner'),'read','--json'],text=True)+')');e.evaluate();assert not e.hasError()
view.show();failures=[];finished=False

def check():
 try:
  for name in ('cameraChoice','zoomSlider','mirrorToggle','saveButton'):
   item=editor.findChild(QObject,name);assert item,name
   point=item.mapToItem(editor,QPointF(0,0))
   assert point.y()>=0 and point.y()+item.height()<=editor.height(),(name,point.y(),item.height(),editor.height())
  assert view.grabWindow().save(str(scratch/'camera-viewport.png'))
  view.resize(540,350)
  QTimer.singleShot(200,small)
 except Exception as error:failures.append(str(error));app.quit()

def small():
 global finished
 try:
  bar=editor.findChild(QObject,'editorScrollbar');assert bar and bar.property('visible')
  finished=True;print('PASS: camera controls fit initial viewport; small-window overflow has a persistent scrollbar')
 except Exception as error:failures.append(str(error))
 app.quit()
QTimer.singleShot(400,check);QTimer.singleShot(5000,app.quit);app.exec()
if failures or not finished:raise SystemExit('; '.join(failures) or 'Viewport test timed out')
