"""Primary camera controls fit a normal opening size; overflow has a scrollbar."""
import json,os,subprocess,sys,traceback
from pathlib import Path
os.environ.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
from PySide6.QtCore import QUrl,QTimer,QObject,QPointF,Qt
from PySide6.QtGui import QGuiApplication,QColor
from PySide6.QtQuick import QQuickView
from PySide6.QtQml import QQmlExpression,qmlContext
from PySide6.QtTest import QTest
root=Path(__file__).resolve().parent.parent
scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])
os.environ['WEBCAMTUNER_CONFIG_ROOT']=str(scratch/'viewport-profiles')
app=QGuiApplication([]);view=QQuickView();view.setResizeMode(QQuickView.SizeRootObjectToView);view.setColor(QColor('#171c24'))
view.setSource(QUrl.fromLocalFile(str(root/'ui/Editor.qml')));assert view.status()!=QQuickView.Error
view.resize(640,680);editor=view.rootObject();editor.setProperty('testing',True);editor.setProperty('section','camera');editor.setProperty('localHostname','demo-host')
e=QQmlExpression(qmlContext(editor),editor,'accept("read",'+subprocess.check_output([str(root/'bin/webcamtuner'),'read','--json'],text=True)+')');e.evaluate();assert not e.hasError()
view.show();failures=[];finished=False

def item(name):
 value=editor.findChild(QObject,name);assert value,name
 return value

def center(control):
 return control.mapToScene(control.boundingRect().center()).toPoint()

def click(control):
 QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,center(control))
 QTest.qWait(60)

def evaluate(obj, expression):
 value=QQmlExpression(qmlContext(obj),obj,expression)
 result=value.evaluate()
 assert not value.hasError(),value.error().toString()
 return result[0] if isinstance(result,tuple) else result

def verify_enclosed(section_name, names):
 section=item(section_name)
 bounds=section.boundingRect()
 for name in names:
  control=item(name)
  point=control.mapToItem(section,QPointF(0,0))
  assert bounds.contains(point) and point.y()+control.height()<=bounds.bottom(), (section_name,name,point,control.height(),bounds)

def check():
 try:
  assert item("pageIntro").property("text") == "Customize your webcam feed:"
  for name in ('cameraChoice','cropControlsToggle','profileDetailsToggle','labelControlsToggle','snapshotsToggle'):
   control=item(name);assert control.isVisible(),name
   point=control.mapToItem(editor,QPointF(0,0))
   assert point.y()>=0 and point.y()+control.height()<=editor.height(),(name,point.y(),control.height(),editor.height())
  for name in ('zoomSlider','mirrorToggle','profileSaveState','reloadSaved','saveVerification','showPreviewLabel'):
   assert not item(name).isVisible(),name
  assert item('cameraSourceChoice').property('currentText') == 'demo-host - This Computer'
  computer, camera = item('cameraSourceChoice'), item('cameraChoice')
  assert computer.parentItem() == camera.parentItem()
  assert computer.x()+computer.width() < camera.x()
  assert item('cameraMoveHandle').property('hint').startswith('Drag to move camera/user-profile.')
  assert item('cameraPowerButton').property('text') == 'Start Camera'
  assert item('labelDisclosure').property('topPadding') == item('labelDisclosure').property('bottomPadding') == 4
  sections=[item(name) for name in ('labelDisclosure','cropDisclosure','maskDisclosure','snapshotsDisclosure','profileDisclosure')]
  gaps=[following.mapToItem(editor,QPointF()).y()-previous.mapToItem(editor,QPointF(0,previous.height())).y()
        for previous,following in zip(sections,sections[1:])]
  assert min(gaps)>0 and max(gaps)-min(gaps)<0.5, gaps
  snapshot=item('snapshotButton')
  snapshots_header=item('snapshotsToggle')
  assert snapshot.isVisible()
  assert snapshot.mapToScene(QPointF()).x()>snapshots_header.mapToScene(QPointF()).x()
  assert abs(center(snapshot).y()-center(snapshots_header).y())<=1
  primary=item('backgroundMoveHandle')
  quick=item('quickLabelMoveHandle')
  assert primary.parentItem()==quick.parentItem() and primary.x()+primary.width()<quick.x()
  preview_height=item('cameraPreviewArea').height()
  crop=item('cropControlsToggle')
  assert crop.property('text') == '▸  Crop & Mirror'
  profile_header=item('profileDetailsToggle')
  assert profile_header.property('text') == '▸  Profile Details · '+evaluate(editor,'document.profiles[profileIndex].name')
  QTest.mouseMove(view,center(crop))
  QTest.qWait(550)
  assert evaluate(crop,'hovered && ToolTip.visible && ToolTip.text.length > 0')
  click(crop)
  assert item('zoomSlider').isVisible() and item('mirrorToggle').isVisible()
  QTest.qWait(50)
  background_crop, mirror = item('cropBackground'), item('mirrorToggle')
  assert mirror.parentItem() == background_crop.parentItem()
  assert mirror.x() >= background_crop.x() + background_crop.width()
  assert abs(center(mirror).y()-center(background_crop).y()) <= 1
  verify_enclosed('cropDisclosure',('cropControlsToggle','cropBackground','zoomSlider','mirrorToggle'))
  assert item('cameraPreviewArea').height() == preview_height
  click(crop)
  assert not item('mirrorToggle').isVisible()
  QTest.mouseMove(view,center(crop))
  QTest.qWait(30)
  assert evaluate(crop,'activeFocus && hovered && background.border.color.a > 0')
  QTest.mouseMove(view,center(item('profileDetailsToggle')))
  QTest.qWait(30)
  assert evaluate(crop,'activeFocus && !hovered && background.border.color.a === 0')
  evaluate(item('profileDetailsToggle'),'forceActiveFocus(Qt.TabFocusReason)')
  assert evaluate(item('profileDetailsToggle'),'visualFocus && background.border.color.a > 0')
  details=item('profileDetailsToggle')
  point_before=center(details)
  click(details)
  assert item('reloadSaved').isVisible() and item('saveVerification').isVisible(), (point_before,center(details),item('profileDisclosure').property('expanded'),item('reloadSaved').isVisible(),item('saveVerification').isVisible(),item('saveVerification').property('text'))
  QTest.qWait(50)
  verify_enclosed('profileDisclosure',('profileDetailsToggle','reloadSaved','saveVerification'))
  assert item('cameraPreviewArea').height() == preview_height
  click(details)
  assert not item('reloadSaved').isVisible()
  mask=item('maskControlsToggle')
  assert not item('maskSlider-softness').isVisible()
  click(mask)
  assert not item('maskSlider-softness').isEnabled()
  editor.setProperty('backgroundMode','blur')
  slider=item('maskSlider-softness')
  click(slider)
  assert slider.property('value') > 0
  assert item('maskValue-softness').property('value') == slider.property('value')
  tightness=item('maskSlider-tightness')
  offset=QPointF(tightness.width()*.78,tightness.height()/2)
  QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,tightness.mapToScene(offset).toPoint())
  assert tightness.property('value') > 0
  tightness_value=item('maskValue-tightness')
  assert tightness_value.property('value') == tightness.property('value')
  evaluate(tightness_value,'contentItem.forceActiveFocus()')
  QTest.keyClick(view,Qt.Key_A,Qt.ControlModifier)
  for key in (Qt.Key_Minus, Qt.Key_2, Qt.Key_5):
   QTest.keyClick(view,key)
  click(item('resetPersonMask'))
  assert slider.property('value') == 0 and item('maskValue-softness').property('value') == 0
  assert tightness.property('value') == 0 and tightness_value.property('value') == 0
  assert evaluate(tightness_value,'contentItem.text') == '0'
  evaluate(tightness_value,'contentItem.forceActiveFocus()')
  QTest.keyClick(view,Qt.Key_A,Qt.ControlModifier)
  for key in (Qt.Key_Minus, Qt.Key_2, Qt.Key_5):
   QTest.keyClick(view,key)
  assert evaluate(tightness_value,'contentItem.text') == '-25'
  click(item('resetPersonMask'))
  assert evaluate(tightness_value,'contentItem.text') == '0'
  assert evaluate(editor,'personMask.softness === 0 && personMask.tightness === 0 && !draftDocument().profiles[profileIndex].personMask')
  click(mask)
  editor.setProperty('backgroundMode','none')
  editor.setProperty('saveFailed',True)
  assert item('profileSaveState').isVisible() and item('profileSaveState').property('text') == 'Could not save'
  editor.setProperty('saveFailed',False)
  for name in ('trashBackgroundDialog','discardProfileDialog'):
   dialog=item(name)
   evaluate(dialog,'open()')
   QTest.qWait(150)
   assert evaluate(dialog,'standardButton(Dialog.Cancel).ToolTip.text.length > 0')
   x,y,w,h=(dialog.property(key) for key in ('x','y','width','height'))
   assert x >= 16 and y >= 16 and x+w <= view.width()-16 and y+h <= view.height()-16
   evaluate(dialog,'close()')
  assert view.grabWindow().save(str(scratch/'camera-viewport.png'))
  view.resize(540,350)
  QTimer.singleShot(200,small)
 except Exception as error:failures.append(traceback.format_exc());app.quit()

def small():
 global finished
 try:
  bar=editor.findChild(QObject,'editorScrollbar');assert bar and bar.property('visible')
  scroll=item('editorScroll');viewport=scroll.property('contentItem')
  editor.setProperty('message','')
  editor.setProperty('dirty',False)
  QTest.qWait(30)
  viewport.setProperty('contentY',scroll.property('contentHeight')-scroll.property('availableHeight'))
  QTest.qWait(30)
  last=item('profileDisclosure');bottom=last.mapToItem(editor,QPointF(0,last.height())).y()
  assert abs(editor.height()-bottom-scroll.x())<=1
  assert abs(editor.width()-scroll.x()-scroll.width()-scroll.x())<=1
  assert abs(scroll.property('availableWidth')-scroll.width())<=1
  editor.setProperty('previewOn',True)
  QTest.qWait(50)
  backend=item('previewBackendIndicator');zoom_badge=item('previewZoomIndicator')
  assert backend.isVisible() and zoom_badge.isVisible()
  assert zoom_badge.y()==backend.y()+backend.height()+4
  assert zoom_badge.x()+zoom_badge.width()==backend.x()+backend.width()

  finished=True;print('PASS: Camera viewport, hover help, collapsed controls, visible errors, and small-window scrolling')
 except Exception as error:failures.append(traceback.format_exc())
 app.quit()
QTimer.singleShot(400,check);QTimer.singleShot(5000,app.quit);app.exec()
if failures or not finished:raise SystemExit('; '.join(failures) or 'Viewport test timed out')
