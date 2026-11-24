"""Shared camera/background crop, label editing without focus loss, position/style persistence."""
import os,json,subprocess,uuid,traceback
from pathlib import Path
os.environ.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
from PIL import Image
from PySide6.QtCore import QUrl,QTimer,QObject,QPointF,Qt,QEvent
from PySide6.QtGui import QGuiApplication,QKeyEvent
from PySide6.QtQuick import QQuickView,QQuickItem,QQuickWindow
from PySide6.QtQml import QQmlExpression,qmlContext
from PySide6.QtTest import QTest
root=Path(__file__).resolve().parent.parent;scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('composition-'+uuid.uuid4().hex);scratch.mkdir()
os.environ.update(WEBCAMTUNER_CONFIG_ROOT=str(scratch/'config'),XDG_DATA_HOME=str(scratch/'data'),XDG_CACHE_HOME=str(scratch/'cache'))
source=scratch/'Scene.png';Image.new('RGB',(1600,900),'#246080').save(source)
app=QGuiApplication([]);view=QQuickView();view.setResizeMode(QQuickView.SizeRootObjectToView);view.setSource(QUrl.fromLocalFile(str(root/'ui/Editor.qml')));assert not view.errors(),[e.toString() for e in view.errors()]
view.resize(1100,900);editor=view.rootObject();editor.setProperty('testing',True)
def ev(code,item=editor):
 e=QQmlExpression(qmlContext(item),item,code);r=e.evaluate();assert not e.hasError(),e.error().toString();return r[0] if isinstance(r,tuple) else r
def controller(action,args):
 if hasattr(args,'toVariant'):args=args.toVariant()
 value=json.loads(subprocess.check_output([str(root/'bin/webcamtuner'),action,*args,'--json'],text=True))
 ev('accept('+json.dumps(action)+','+json.dumps(value)+')')
editor.request.connect(controller);editor.cameraTabRequested.connect(lambda:editor.setProperty('section','camera'))
controller('read',[]);editor.setProperty('section','background');ev('addBackgrounds('+json.dumps([str(source)])+')');editor.setProperty('section','camera');view.show()
def find(item,name):
 if item.objectName()==name:return item
 if isinstance(item,QQuickItem):
  for c in item.childItems():
   r=find(c,name)
   if r:return r
def click(item,window=view):
 assert item
 p=item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint();QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,p);app.processEvents()
def type_text(text,window=view):QGuiApplication.sendEvent(window,QKeyEvent(QEvent.KeyPress,0,Qt.NoModifier,text))
errors=[];finished=False
def guard(fn):
 def call():
  try:fn()
  except Exception:errors.append(traceback.format_exc());app.quit()
 return call
def begin():
 editor.setProperty('mirror',False)
 click(find(editor,'cropControlsToggle'))
 click(find(editor,'cropBackground'));assert ev('cropTool.target')=='background'
 ev('cropTool.changeZoom(2)');assert ev('backgroundCrop.zoom')==2 and editor.property('zoom')==1
 click(find(editor,'cropCamera'));ev('cropTool.changeZoom(1.5)');assert editor.property('zoom')==1.5 and ev('backgroundCrop.zoom')==2
 click(find(editor,"labelControlsToggle"))
 QTest.qWait(150)
 show_label=find(editor,"showPreviewLabel");assert show_label.property("text")=="Show Label"
 click(show_label);assert show_label.property("checked")
 ev('interactiveLabel.beginEditing()')
 field=find(editor,'previewLabelText');assert field.property('activeFocus')
 QTest.keyClick(view,Qt.Key_A,Qt.ControlModifier);type_text('Still typing')
 editor.setProperty('busy',True);controller('backgrounds',[]);editor.setProperty('busy',False)
 QTimer.singleShot(1200,guard(continue_typing))
def continue_typing():
 field=find(editor,'previewLabelText');assert field.property('activeFocus') and field.property('text')=='Still typing'
 type_text(' without interruption')
 click(find(editor,'cameraCompositionStage'))
 assert not field.isVisible() and ev('backgroundLabelOverlay.text')=='Still typing without interruption'
 click(find(editor,'labelFormatButton'));QTest.qWait(100)
 popup=editor.findChild(QObject,'labelFormatPopup');assert popup.property('visible')
 def popup_fits():
  x,y,w,h=(popup.property(key) for key in ('x','y','width','height'))
  assert x >= 16 and y >= 16 and x+w <= view.width()-16 and y+h <= view.height()-16
 popup_fits()
 header=find(view.contentItem(),'labelFormatDragHandle')
 beginning=(popup.property('x'),popup.property('y'))
 p=header.mapToScene(QPointF(header.width()/2,header.height()/2)).toPoint()
 end=p+QPointF(54,38).toPoint()
 QTest.mousePress(view,Qt.LeftButton,Qt.NoModifier,p)
 QTest.mouseMove(view,end,40)
 assert ev('draggingComposition && ToolTip.toolTip.opacity === 0')
 QTest.mouseRelease(view,Qt.LeftButton,Qt.NoModifier,end)
 assert ev('!draggingComposition && ToolTip.toolTip.opacity === 1')
 assert popup.property('x')>beginning[0] and popup.property('y')>beginning[1]
 popup_fits()
 view.resize(540,240);QTest.qWait(150);popup_fits()
 scroll=find(view.contentItem(),'labelFormatScroll')
 assert scroll.property('contentHeight') > scroll.property('availableHeight') > 0
 view.resize(1100,900);QTest.qWait(150);popup_fits()
 for name in ('labelBold','labelItalic','labelAllCaps'):click(find(view.contentItem(),name))
 original_color=ev('backgroundLabelOverlay.color||"#ffffff"')
 color=editor.findChild(QQuickWindow,'labelColorDialog');assert color
 click(find(view.contentItem(),'labelFormatColorSwatch'));QTest.qWait(100);assert color.isVisible()
 palette=color.contentItem()
 swatch=find(palette,'labelColorSwatch');eyedropper=find(palette,'labelColorEyedropper')
 assert 0 <= eyedropper.x()-swatch.x()-swatch.width() < 12
 assert find(palette,'labelColorDragHandle')
 def change_color(hex_color):
  click(find(palette,'labelColorHex'),color)
  QTest.keyClick(color,Qt.Key_A,Qt.ControlModifier)
  type_text(hex_color,color)
  assert ev('backgroundLabelOverlay.color')==hex_color
 change_color('#25a0ff')
 click(find(palette,'labelColorCancel'),color)
 assert not color.isVisible() and ev('backgroundLabelOverlay.color')==original_color
 if not find(view.contentItem(),"labelColorPicker"): click(find(editor,"labelFormatButton"))
 click(find(view.contentItem(),"labelColorPicker"));QTest.qWait(100);assert color.isVisible()
 change_color('#25a0ff')
 assert color.isActive()
 click(find(editor,'cameraCompositionStage'))
 assert not color.isVisible() and ev('backgroundLabelOverlay.color')=='#25a0ff'
 fps=find(editor,'previewFpsIndicator');backend=find(editor,'previewBackendIndicator')
 assert backend.y()==fps.y()+fps.height()+4
 assert backend.x()+backend.width()==fps.x()+fps.width()
 ev('editLabel({fontFamily:"DejaVu Sans",fontSize:.05})')
 QTest.keyClick(view,Qt.Key_Escape);QTest.qWait(150)
 label=find(editor,'previewLabelDrag');p=label.mapToScene(QPointF(label.width()/2,label.height()/2)).toPoint()
 QTest.mousePress(view,Qt.LeftButton,Qt.NoModifier,p);QTest.mouseMove(view,p+QPointF(150,-70).toPoint(),60);QTest.mouseRelease(view,Qt.LeftButton,Qt.NoModifier,p+QPointF(150,-70).toPoint())
 assert ev('backgroundLabelOverlay.x')>.1 and ev('backgroundLabelOverlay.y')<.9
 assert ev('foreground.x')==0,'Label dragging must not move the person'
 ev('editBackgroundCrop({zoom:2,centerX:.6,centerY:.6})')
 def label_bounds(preview):
  label=find(preview,'interactivePreviewLabel')
  return (label.x()/preview.width(),(label.y()+label.height())/preview.height())
 camera_stage = find(editor,'cameraCompositionStage')
 camera_label = find(camera_stage,'interactivePreviewLabel')
 camera_preview = camera_label.parentItem()
 camera_bounds = label_bounds(camera_preview)
 editor.setProperty('section','background')
 QTest.qWait(80)
 click(find(editor,'backgroundLabelControlsToggle'))
 QTest.qWait(200)
 background_section=find(view.contentItem(),'backgroundLabelControls')
 background_preview=find(view.contentItem(),'backgroundLabelPreview')
 done=find(view.contentItem(),'finishBackgroundLabelEditor')
 assert all(abs(a-b)<.001 for a,b in zip(label_bounds(background_preview),camera_bounds))
 assert ev('overlay.color',background_preview)=='#25a0ff' and ev('overlay.fontFamily',background_preview)=='DejaVu Sans'
 click(find(background_section,'backgroundLabelMoveHandle'))
 assert find(background_preview,'previewLabelMoveHandles').isVisible()
 corner=find(background_preview,'previewLabelResize-3')
 p=corner.mapToScene(QPointF(corner.width()/2,corner.height()/2)).toPoint()
 QTest.mousePress(view,Qt.LeftButton,Qt.NoModifier,p)
 QTest.mouseMove(view,p+QPointF(26,12).toPoint(),60)
 QTest.mouseRelease(view,Qt.LeftButton,Qt.NoModifier,p+QPointF(26,12).toPoint())
 size=ev('backgroundLabelOverlay.fontSize')
 assert size>.05
 resized_bounds=label_bounds(background_preview)
 click(done);QTest.qWait(100)
 editor.setProperty('section','camera')
 assert ev('interactiveLabel.overlay.fontSize')==size
 assert all(abs(a-b)<.001 for a,b in zip(label_bounds(camera_preview),resized_bounds))
 editor.setProperty('section','background')
 QTest.qWait(100);click(find(editor,'backgroundLabelControlsToggle'));QTest.qWait(100)
 click(find(background_section,'labelFormatButton'));QTest.qWait(100)
 click(find(view.contentItem(),'labelItalic'))
 click(find(view.contentItem(),'labelFormatColorSwatch'));QTest.qWait(100)
 color=next(palette for palette in editor.findChildren(QQuickWindow,'labelColorDialog') if palette.isVisible())
 click(find(color.contentItem(),'labelColorCancel'),color)
 assert not color.isVisible()
 QTest.keyClick(view,Qt.Key_Escape);QTest.qWait(100)
 ev('backgroundLabelPreview.beginEditing()')
 field=find(background_preview,'previewLabelText')
 type_text('Edited on Backgrounds')
 click(find(background_section,'showPreviewLabel'))
 assert not field.isVisible() and ev('backgroundLabelOverlay.text')=='Edited on Backgrounds'
 click(done);QTest.qWait(100)
 editor.setProperty('section','camera')
 assert ev('interactiveLabel.overlay.text')=='Edited on Backgrounds'
 assert not ev('interactiveLabel.overlay.italic') and not ev('interactiveLabel.overlay.enabled')
 ev('editLabel({enabled:true})')
 editor.setProperty('section','background')
 assert ev('overlay.enabled',background_preview)
 gallery_label=find(editor,'backgroundLabel-'+ev('selectedBackground().id'))
 click(gallery_label)
 QTest.keyClick(view,Qt.Key_A,Qt.ControlModifier)
 type_text('Edited in the gallery')
 QTest.keyClick(view,Qt.Key_Return)
 assert ev('overlay.text',background_preview)=='Edited in the gallery'
 assert ev('overlay.color',background_preview)=='#25a0ff'
 editor.setProperty('section','camera')
 assert ev('interactiveLabel.overlay.text')=='Edited in the gallery'
 QTimer.singleShot(2000,guard(verify))
def verify():
 global finished
 store=json.loads((scratch/'config/profiles.json').read_text());spec=store['profiles'][0]['background']['labelOverlay']
 assert spec['text']=='Edited in the gallery' and spec['bold'] and not spec['italic'] and spec['allCaps'] and spec['fontSize']>.05
 assert spec['color']=='#25a0ff'
 assert spec['x']>.1 and spec['y']<.9
 controller('read',[]);assert ev('backgroundLabelOverlay.text')==spec['text']
 assert not editor.property('dirty'),'Readback must not start another save merely because JSON keys were reordered'
 assert view.grabWindow().save(str(Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/'composition-edit.png'))
 finished=True;print('PASS: camera/background crop targeting; uninterrupted preview label typing; drag, font/style/caps and automatic metadata/profile readback');app.quit()
QTimer.singleShot(500,guard(begin));QTimer.singleShot(14000,app.quit);app.exec()
if errors or not finished:raise SystemExit('; '.join(errors) or 'Composition test timed out')
