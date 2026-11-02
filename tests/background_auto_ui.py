"""External folder changes refresh without resetting per-image crop or dirty camera edits."""
import json,os,subprocess,sys,uuid
from pathlib import Path
os.environ.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
from PIL import Image
from PySide6.QtCore import QUrl,QTimer,QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtQml import QQmlExpression,qmlContext
root=Path(__file__).resolve().parent.parent
scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('auto-'+uuid.uuid4().hex);scratch.mkdir()
os.environ.update(WEBCAMTUNER_CONFIG_ROOT=str(scratch/'config'),XDG_DATA_HOME=str(scratch/'data'),XDG_CACHE_HOME=str(scratch/'cache'))
app=QGuiApplication([]);view=QQuickView();view.setResizeMode(QQuickView.SizeRootObjectToView)
view.setSource(QUrl.fromLocalFile(str(root/'ui/Editor.qml')));assert view.status()!=QQuickView.Error
view.resize(640,760);editor=view.rootObject();editor.setProperty('testing',True)
def ev(text):
 e=QQmlExpression(qmlContext(editor),editor,text);value=e.evaluate();assert not e.hasError(),e.error().toString()
 return value[0] if isinstance(value,tuple) else value
def controller(action,args):
 if hasattr(args,'toVariant'):args=args.toVariant()
 result=json.loads(subprocess.check_output([str(root/'bin/webcamtuner'),action,*args,'--json'],text=True))
 ev('accept('+json.dumps(action)+','+json.dumps(result)+')')
editor.request.connect(controller);controller('read',[]);view.show()
phase=0;ticks=0;first='';folder=None;failures=[];finished=False

def check():
 global phase,ticks,first,folder,finished
 try:
  ticks+=1
  if phase==0:
   source=scratch/'One.png';Image.new('RGB',(640,360),'purple').save(source)
   editor.setProperty('section','background')
   ev('addBackgrounds('+json.dumps([str(source)])+')');first=editor.property('imagePath')
   ev('editBackgroundCrop({zoom:2,centerX:0.6,centerY:0.5});flushBackgroundCrop()')
   source=scratch/'Two.png';Image.new('RGB',(640,360),'green').save(source)
   ev('addBackgrounds('+json.dumps([str(source)])+')')
   assert ev('backgroundCrop.zoom')==1
   ev('chooseBackground('+json.dumps(first)+')');assert ev('backgroundCrop.zoom')==2
   ev('frame(1.8,0.5,0.5)')
   model=json.loads(ev('JSON.stringify(backgroundLibrary)'));folder=Path(model['directory'])
   Image.new('RGB',(400,200),'blue').save(folder/'File manager image.PNG')
   Image.new('RGB',(400,200),'yellow').save(folder/'Another image.jpg')
   library=editor.findChild(QObject,'backgroundLibraryView');assert library
   library.setProperty('refreshInterval',500)
   phase=1
  elif phase==1:
   if ev('backgroundLibrary.items.length')!=4:return
   assert editor.property('imagePath')==first and ev('backgroundCrop.zoom')==2
   assert editor.property('zoom')==1.8 and editor.property('dirty')
   (folder/'Another image.jpg').unlink();phase=2
  elif phase==2:
   if ev('backgroundLibrary.items.length')!=3:return
   assert editor.property('imagePath')==first and ev('backgroundCrop.zoom')==2
   finished=True;print('PASS: external additions/removal refresh automatically; per-image framing and camera drafts survive');app.quit()
 except Exception as e:failures.append(str(e));app.quit()
 if ticks>40:failures.append('Timed out');app.quit()
timer=QTimer();timer.timeout.connect(check);timer.start(250);QTimer.singleShot(15000,app.quit);app.exec()
if not finished or failures:raise SystemExit('; '.join(failures) or 'Automatic refresh did not complete')
