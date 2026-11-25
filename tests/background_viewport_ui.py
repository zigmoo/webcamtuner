"""Background editing fits normally; ordinary wheel scrolling reaches every control."""
import json,os,subprocess,sys,uuid,traceback
from pathlib import Path
os.environ.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
from PIL import Image
from PySide6.QtCore import QUrl,QTimer,QObject,QPointF,QPoint,Qt
from PySide6.QtGui import QGuiApplication,QColor,QWheelEvent
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest
from PySide6.QtQml import QQmlExpression,qmlContext
root=Path(__file__).resolve().parent.parent;scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('background-layout-'+uuid.uuid4().hex);scratch.mkdir()
os.environ.update(WEBCAMTUNER_CONFIG_ROOT=str(scratch/'profiles'),XDG_DATA_HOME=str(scratch/'data'),XDG_CACHE_HOME=str(scratch/'cache'))
empty='--empty' in sys.argv
folder=scratch/'data/webcamtuner/backgrounds';folder.mkdir(parents=True)
for i in range(0 if empty else 22):Image.new('RGB',(640,360),(i*9,70,130)).save(folder/f'Photo-{i:02}.jpg')
app=QGuiApplication([]);v=QQuickView();v.setResizeMode(QQuickView.SizeRootObjectToView);v.setColor(QColor('#171c24'));v.setSource(QUrl.fromLocalFile(str(root/'ui/Editor.qml')));assert v.status()!=QQuickView.Error
v.resize(700,780);editor=v.rootObject();editor.setProperty('testing',True)
def ev(text):
 e=QQmlExpression(qmlContext(editor),editor,text);r=e.evaluate();assert not e.hasError(),e.error().toString()
 return r[0] if isinstance(r,tuple) else r
def controller(action,args):
 if hasattr(args,'toVariant'):args=args.toVariant()
 result=json.loads(subprocess.check_output([str(root/'bin/webcamtuner'),action,*args,'--json'],text=True));ev('accept('+json.dumps(action)+','+json.dumps(result)+')')
editor.request.connect(controller);controller('read',[]);editor.setProperty('section','background')
if not empty:ev('chooseBackground('+json.dumps(str(folder/'Photo-21.jpg'))+')')
v.show()
failures=[];finished=False

def normal():
 global finished
 try:
  for name in ('addBackgrounds','openBackgroundFolder','refreshBackgrounds'):
   item=editor.findChild(QObject,name);point=item.mapToItem(editor,QPointF(0,0))
   assert point.y()>=0 and point.y()+item.height()<=editor.height(),(name,point.y(),item.height(),editor.height())
  assert not editor.findChild(QObject,'pageIntro').isVisible()
  for name in ('profileChoice','profileName','profileDetailsToggle','profileSaveState'):
   assert not editor.findChild(QObject,name).isVisible(),name
  effects=editor.findChild(QObject,'localCameraEffectsLabel')
  row=editor.findChild(QObject,'backgroundEffects')
  button=next(item for item in row.childItems() if item.objectName()=='backgroundEffect-none')
  assert effects.property('text') == 'Local Camera Effects' and button.property('text') == 'No Background'
  effect_buttons=[item for item in row.childItems() if item.objectName().startswith('backgroundEffect-')]
  assert [item.property('text') for item in sorted(effect_buttons,key=lambda item:item.x())] == ['Backgroundd Image','Blur','No Background']
  assert effects.mapToItem(editor,QPointF()).y()+effects.height()<=button.mapToItem(editor,QPointF()).y()
  add=editor.findChild(QObject,'addBackgrounds')
  assert add.property('text') == 'Add images…'
  assert editor.findChild(QObject,'backgroundPath') is None
  assert editor.findChild(QObject,'backgroundLibraryPath') is None
  assert editor.findChild(QObject,'openBackgroundFolder').parentItem() == add.parentItem()
  assert not editor.findChild(QObject,'backgroundFeedback').isVisible()
  tip=QQmlExpression(qmlContext(add),add,'ToolTip.text').evaluate()
  assert 'copy images' in (tip[0] if isinstance(tip,tuple) else tip)
  if empty:
   empty_label=editor.findChild(QObject,'backgroundEmptyState')
   assert empty_label.isVisible() and empty_label.property('text')=='No background images yet.'
   assert add.isVisible() and add.property('enabled')
   assert not editor.findChild(QObject,'backgroundGrid').isVisible()
   assert not editor.property('libraryMessage')
   assert v.grabWindow().save(str(Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/'backgrounds-empty.png'))
   finished=True;print('PASS: empty Backgrounds library has a visible add action and no empty grid');app.quit();return
  grid=editor.findChild(QObject,'backgroundGrid')
  initial_height=grid.height()
  v.resize(700,1170);QTest.qWait(150)
  assert grid.height()>initial_height and grid.height()>480
  label_button=editor.findChild(QObject,'backgroundLabelControlsToggle')
  assert label_button.mapToScene(QPointF()).y()>=grid.mapToScene(QPointF(0,grid.height())).y()
  def info_items(item):
   if item.objectName().startswith('backgroundAction-info-'):
    yield item
   for child in item.childItems():
    yield from info_items(child)
  top=grid.mapToScene(QPointF()).y()
  bottom=top+grid.height()
  info=next(item for item in info_items(grid)
            if top+10<item.mapToScene(QPointF(13,13)).y()<bottom-10)
  actions=info.parentItem()
  image=actions.parentItem()
  assert not actions.isVisible()
  assert actions.y()==2 and image.width()-actions.x()-actions.width()==2
  assert actions.width()==5*20+4
  icon_geometry=QQmlExpression(qmlContext(info),info,
   'width === 20 && height === 20 && contentItem.width === 14'
   ' && Math.abs(background.color.a - 208/255) < 0.01').evaluate()
  assert icon_geometry[0] if isinstance(icon_geometry,tuple) else icon_geometry
  library=editor.findChild(QObject,'backgroundLibraryView')
  camera_requests=[]
  library.livePreviewRequested.connect(lambda: camera_requests.append(True))
  QTest.mouseMove(v,info.mapToScene(QPointF(10,25)).toPoint());QTest.qWait(30)
  assert actions.isVisible() and sum(item.isVisible() for item in info_items(grid))==1
  QTest.mouseMove(v,info.mapToScene(QPointF(10,10)).toPoint());QTest.qWait(450)
  metadata=editor.findChild(QObject,'backgroundImageMetadata')
  assert metadata.isVisible() and '640 × 360 px · JPEG' in metadata.property('text')
  assert not camera_requests
  QTest.mouseMove(v,QPoint(2,2));QTest.qWait(30)
  assert not actions.isVisible() and not metadata.isVisible()
  point=label_button.mapToScene(QPointF(label_button.width()/2,label_button.height()/2)).toPoint()
  QTest.mouseClick(v,Qt.LeftButton,Qt.NoModifier,point)
  dialog=editor.findChild(QObject,'backgroundLabelDialog')
  assert dialog.property('visible')
  ev('editLabel({enabled:true,text:"Shared label",x:.4,y:.7})')
  QTest.qWait(160)
  handle=editor.findChild(QObject,'backgroundPreviewLabelDrag')
  assert handle and handle.isVisible()
  point=handle.mapToScene(QPointF(handle.width()/2,handle.height()/2)).toPoint()
  QTest.mousePress(v,Qt.LeftButton,Qt.NoModifier,point)
  QTest.mouseMove(v,point+QPoint(25,-15),40)
  QTest.mouseRelease(v,Qt.LeftButton,Qt.NoModifier,point+QPoint(25,-15))
  assert ev('backgroundLabelOverlay.y')<.7 and ev('backgroundLabelOverlay.text')=='Shared label'
  done=editor.findChild(QObject,'finishBackgroundLabelEditor')
  v.resize(540,390);QTest.qWait(100)
  controls=editor.findChild(QObject,'backgroundLabelControls')
  sample=editor.findChild(QObject,'backgroundLabelSample')
  for item in (sample,handle,controls,done):
   p=item.mapToScene(QPointF())
   assert 0<=p.x()<=p.x()+item.width()<=v.width()
   assert 0<=p.y()<=p.y()+item.height()<=v.height()
  assert sample.height()>90 and abs(sample.width()/sample.height()-16/9)<.01
  assert v.grabWindow().save(str(Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/'background-label-palette.png'))
  QTest.mouseClick(v,Qt.LeftButton,Qt.NoModifier,done.mapToScene(QPointF(done.width()/2,done.height()/2)).toPoint())
  QTest.qWait(100)
  assert not dialog.property('visible')
  assert v.grabWindow().save(str(Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/'background-layout-fixed.png'))
  v.resize(540,390);QTimer.singleShot(200,scroll_into_view)
 except Exception as e:failures.append(traceback.format_exc());app.quit()
def scroll_into_view():
 try:
  global stage
  scroll=editor.findChild(QObject,'editorScroll');stage=editor.findChild(QObject,'backgroundGrid')
  assert scroll.property('contentHeight') <= scroll.property('availableHeight')
  assert stage.property('contentHeight') > stage.height()
  stage.setProperty('contentY',132)
  QTimer.singleShot(100,wheel)
 except Exception as e:failures.append(traceback.format_exc());app.quit()
def wheel():
 try:
  global before
  before=stage.property('contentY')
  pos=stage.mapToScene(QPointF(stage.width()/2,stage.height()/2))
  event=QWheelEvent(pos,QPointF(v.mapToGlobal(pos.toPoint())),QPoint(0,0),QPoint(0,120),Qt.NoButton,Qt.NoModifier,Qt.ScrollUpdate,False)
  QGuiApplication.sendEvent(v,event);QTimer.singleShot(200,finish)
 except Exception as e:failures.append(traceback.format_exc());app.quit()
def finish():
 global finished
 try:
  assert stage.property('contentY')<before,'Wheel over the background grid must scroll its images'
  assert ev('backgroundCrop.zoom')==1,'Plain scrolling must not change background zoom'
  finished=True;print('PASS: consolidated Backgrounds controls fit the window and the grid scrolls normally')
 except Exception as e:failures.append(traceback.format_exc())
 app.quit()
QTimer.singleShot(600,normal);QTimer.singleShot(10000,app.quit);app.exec()
if failures or not finished:raise SystemExit('; '.join(failures) or 'Layout test timed out')
