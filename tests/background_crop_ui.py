"""Real crop handles move/resize the selected source region and persist it."""
import os,json,subprocess,sys,uuid,traceback
from pathlib import Path
os.environ.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
from PIL import Image,ImageDraw
from PySide6.QtCore import QUrl,QTimer,QPointF,Qt,QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView,QQuickItem
from PySide6.QtQml import QQmlExpression,qmlContext
from PySide6.QtTest import QTest
root=Path(__file__).resolve().parent.parent
scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('crop-tool-'+uuid.uuid4().hex);scratch.mkdir()
os.environ.update(WEBCAMTUNER_CONFIG_ROOT=str(scratch/'config'),XDG_DATA_HOME=str(scratch/'data'),XDG_CACHE_HOME=str(scratch/'cache'))
narrow='--narrow' in sys.argv
source=scratch/'Wide scene.png';image=Image.new('RGB',(1600,550 if narrow else 1200),'#3b6380');draw=ImageDraw.Draw(image)
for i in range(8):
 for j in range(6):
  draw.rectangle((i*200,j*200,(i+1)*200-2,(j+1)*200-2),fill=(40+i*23,30+j*32,110))
image.save(source)
app=QGuiApplication([]);v=QQuickView();v.setResizeMode(QQuickView.SizeRootObjectToView);v.setSource(QUrl.fromLocalFile(str(root/'ui/Editor.qml')))
assert not v.errors(),[e.toString() for e in v.errors()]
v.resize(600 if narrow else 1000,780);editor=v.rootObject();editor.setProperty('testing',True)
def ev(text,item=editor):
 e=QQmlExpression(qmlContext(item),item,text);r=e.evaluate();assert not e.hasError(),e.error().toString()
 return r[0] if isinstance(r,tuple) else r
def controller(action,args):
 if hasattr(args,'toVariant'):args=args.toVariant()
 data=json.loads(subprocess.check_output([str(root/'bin/webcamtuner'),action,*args,'--json'],text=True))
 ev('accept('+json.dumps(action)+','+json.dumps(data)+')')
editor.request.connect(controller);editor.cameraTabRequested.connect(lambda:editor.setProperty('section','camera'));controller('read',[]);editor.setProperty('section','background');ev('addBackgrounds('+json.dumps([str(source)])+')');v.show()
def find(item,name):
 if item.objectName()==name:return item
 if isinstance(item,QQuickItem):
  for child in item.childItems():
   result=find(child,name)
   if result:return result
def drag(item,dx,dy):
 p=item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint()
 QTest.mousePress(v,Qt.LeftButton,Qt.NoModifier,p);QTest.mouseMove(v,p+QPointF(dx,dy).toPoint(),50);QTest.mouseRelease(v,Qt.LeftButton,Qt.NoModifier,p+QPointF(dx,dy).toPoint())
errors=[];finished=False
def guarded(fn):
 def call():
  try:fn()
  except Exception:errors.append(traceback.format_exc());app.quit()
 return call
def open_editor():
 ev('cropBackground(backgroundLibrary.items[0])')
 QTimer.singleShot(350,guarded(exercise))
def exercise():
 global final_crop
 canvas=find(v.contentItem(),'sharedCropCanvas');assert canvas
 bounds=ev('imageBounds',canvas);assert bounds.width()>300 and bounds.height()>(120 if narrow else 300)
 title=find(v.contentItem(),'compositorPreviewTitle');assert title.property('text')=='Compositor Preview'
 raw_title=find(v.contentItem(),'originalImageTitle');assert raw_title.property('text')=='Original Image'
 raw_image=find(v.contentItem(),'cropOriginalImage')
 assert raw_image and raw_image.property('source')==canvas.property('imageSource')
 assert title.mapToScene(QPointF()).y()<canvas.mapToScene(QPointF()).y()
 assert raw_title.mapToScene(QPointF()).y()<raw_image.mapToScene(QPointF()).y()
 if narrow:
  assert raw_title.mapToScene(QPointF()).y()>=canvas.mapToScene(QPointF()).y()+canvas.height()
  assert canvas.height()-bounds.height()<=40,(canvas.height(),bounds.height())
 dialog=editor.findChild(QObject,'compositionCropDialog')
 assert dialog and dialog.property('visible')
 x,y,w,h=(dialog.property(key) for key in ('x','y','width','height'))
 assert x >= 16 and y >= 16 and x+w <= v.width()-16 and y+h <= v.height()-16
 done=find(v.contentItem(),'finishCropEditor')
 assert done and done.property('text')=='Done'
 assert done.mapToScene(QPointF(0,done.height())).y() <= canvas.mapToScene(QPointF()).y()
 drag(find(v.contentItem(),'cropHandle-se'),-130,-80)
 assert ev('backgroundCrop.zoom')>1.2
 before=ev('backgroundCrop.centerX')
 drag(find(v.contentItem(),'cropMoveSelection'),70,40)
 assert ev('backgroundCrop.centerX')>before
 selection=ev('selection',canvas)
 assert abs(selection.width()/selection.height()-16/9)<1e-6
 assert selection.x()>=bounds.x()-1 and selection.y()>=bounds.y()-1
 assert selection.right()<=bounds.right()+1 and selection.bottom()<=bounds.bottom()+1
 final_crop=json.loads(ev('JSON.stringify(backgroundCrop)'))
 assert v.grabWindow().save(str(Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('crop-editor-narrow.png' if narrow else 'crop-editor.png')))
 p=done.mapToScene(QPointF(done.width()/2,done.height()/2)).toPoint()
 QTest.mouseClick(v,Qt.LeftButton,Qt.NoModifier,p)
 assert not dialog.property('visible')
 QTimer.singleShot(150,guarded(verify_saved))
def verify_saved(attempt=0):
 global finished
 profile_path=scratch/'config/profiles.json'
 if attempt<30 and (ev('dirty || savePending') or not profile_path.exists()):
  QTimer.singleShot(150,guarded(lambda:verify_saved(attempt+1)))
  return
 settings=json.loads((scratch/'config/background-crops.json').read_text())
 assert list(settings['crops'].values())==[final_crop]
 store=json.loads(profile_path.read_text())
 assert store['profiles'][0]['background']['crop']==final_crop
 finished=True;print('PASS: full-image crop dialog, resize/move handles, 16:9 bounded source selection and automatic crop/profile persistence');app.quit()
QTimer.singleShot(600,guarded(open_editor));QTimer.singleShot(12000,app.quit);app.exec()
if errors or not finished:raise SystemExit('; '.join(errors) or 'Crop test timed out')
