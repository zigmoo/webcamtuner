"""Live frame replacement must not cancel crop drags or flash Loading text."""
import os,io,base64,traceback
from pathlib import Path
os.environ.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
from PIL import Image
from PySide6.QtCore import QUrl,QTimer,QPointF,Qt,QObject
from PySide6.QtGui import QGuiApplication,QColor
from PySide6.QtQuick import QQuickView,QQuickItem
from PySide6.QtTest import QTest
root=Path(__file__).resolve().parent.parent
frames=[]
for color in ('#b23d29','#345fb0'):
 stream=io.BytesIO();Image.new('RGB',(1920,1080),color).save(stream,'JPEG');frames.append('data:image/jpeg;base64,'+base64.b64encode(stream.getvalue()).decode())
app=QGuiApplication([]);v=QQuickView();v.setColor(QColor('black'));v.setResizeMode(QQuickView.SizeRootObjectToView);v.setSource(QUrl.fromLocalFile(str(root/'ui/CropCanvas.qml')));assert not v.errors()
v.resize(960,640);canvas=v.rootObject();canvas.setProperty('maximumZoom',4)
canvas.edited.connect(lambda value:canvas.setProperty('crop',value.toVariant() if hasattr(value,'toVariant') else value))
canvas.setProperty('imageSource',QUrl(frames[0]));v.show()
def find(item,name):
 if item.objectName()==name:return item
 if isinstance(item,QQuickItem):
  for child in item.childItems():
   result=find(child,name)
   if result:return result
errors=[];finished=False;step=0
def begin():
 global handle,start,bounds
 try:
  assert canvas.property('hasFrame')
  handle=find(canvas,'cropHandle-se');assert handle.property('visible')
  bounds=canvas.property('imageBounds');start=handle.mapToScene(QPointF(handle.width()/2,handle.height()/2)).toPoint()
  QTest.mousePress(v,Qt.LeftButton,Qt.NoModifier,start);timer.start(35)
 except Exception:errors.append(traceback.format_exc());app.quit()
def tick():
 global step,finished
 try:
  step+=1;canvas.setProperty('imageSource',QUrl(frames[step%2]))
  assert canvas.property('hasFrame') and handle.property('visible')
  assert not canvas.findChild(QObject,'cropLoadingHint').property('visible')
  assert canvas.property('imageBounds')==bounds
  p=start+QPointF(-step*18,-step*10).toPoint();QTest.mouseMove(v,p,5)
  pixel=v.grabWindow().pixelColor(v.width()//2,v.height()//2);assert pixel.red()+pixel.green()+pixel.blue()>60,'Retained frame went blank'
  if step==12:
   QTest.mouseRelease(v,Qt.LeftButton,Qt.NoModifier,p)
   value=canvas.property('crop');value=value.toVariant() if hasattr(value,'toVariant') else value
   assert value['zoom']>1.2,value
   finished=True;print('PASS: corner crop survives 12 asynchronous camera frames; stable bounds, retained pixels and no Loading flash');timer.stop();app.quit()
 except Exception:errors.append(traceback.format_exc());timer.stop();app.quit()
timer=QTimer();timer.timeout.connect(tick);QTimer.singleShot(500,begin);QTimer.singleShot(8000,app.quit);app.exec()
if errors or not finished:raise SystemExit('; '.join(errors) or 'Live crop test timed out')
