"""Shared camera/background crop, label editing without focus loss, position/style persistence."""
import os,json,subprocess,uuid,traceback
from pathlib import Path
os.environ.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
from PIL import Image
from PySide6.QtCore import QUrl,QTimer,QObject,QPointF,Qt,QEvent
from PySide6.QtGui import QGuiApplication,QKeyEvent
from PySide6.QtQuick import QQuickView,QQuickItem
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
def click(item):
 assert item
 p=item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint();QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,p);app.processEvents()
def type_text(text):QGuiApplication.sendEvent(view,QKeyEvent(QEvent.KeyPress,0,Qt.NoModifier,text))
errors=[];finished=False
def guard(fn):
 def call():
  try:fn()
  except Exception:errors.append(traceback.format_exc());app.quit()
 return call
def begin():
 click(find(editor,'cropBackground'));assert ev('cropTool.target')=='background'
 ev('cropTool.changeZoom(2)');assert ev('backgroundCrop.zoom')==2 and editor.property('zoom')==1
 click(find(editor,'cropCamera'));ev('cropTool.changeZoom(1.5)');assert editor.property('zoom')==1.5 and ev('backgroundCrop.zoom')==2
 ev('editLabel({enabled:true})');ev('interactiveLabel.beginEditing()')
 field=find(editor,'previewLabelText');assert field.property('activeFocus')
 QTest.keyClick(view,Qt.Key_A,Qt.ControlModifier);type_text('Still typing')
 editor.setProperty('busy',True);controller('backgrounds',[]);editor.setProperty('busy',False)
 QTimer.singleShot(1200,guard(continue_typing))
def continue_typing():
 field=find(editor,'previewLabelText');assert field.property('activeFocus') and field.property('text')=='Still typing'
 type_text(' without interruption');QTest.keyClick(view,Qt.Key_Return)
 click(find(editor,'labelFormatButton'));QTest.qWait(100)
 for name in ('labelBold','labelItalic','labelAllCaps'):click(find(view.contentItem(),name))
 color=editor.findChild(QObject,'labelColorDialog');assert color
 ev('selectedColor="#25a0ff";accepted()',color)
 ev('editLabel({fontFamily:"DejaVu Sans",fontSize:.05})')
 QTest.keyClick(view,Qt.Key_Escape);QTest.qWait(150)
 label=find(editor,'previewLabelDrag');p=label.mapToScene(QPointF(label.width()/2,label.height()/2)).toPoint()
 QTest.mousePress(view,Qt.LeftButton,Qt.NoModifier,p);QTest.mouseMove(view,p+QPointF(150,-70).toPoint(),60);QTest.mouseRelease(view,Qt.LeftButton,Qt.NoModifier,p+QPointF(150,-70).toPoint())
 assert ev('backgroundLabelOverlay.x')>.1 and ev('backgroundLabelOverlay.y')<.9
 assert ev('foreground.x')==0,'Label dragging must not move the person'
 QTimer.singleShot(2000,guard(verify))
def verify():
 global finished
 store=json.loads((scratch/'config/profiles.json').read_text());spec=store['profiles'][0]['background']['labelOverlay']
 assert spec['text']=='Still typing without interruption' and spec['bold'] and spec['italic'] and spec['allCaps'] and spec['fontSize']==.05
 assert spec['color']=='#25a0ff'
 assert spec['x']>.1 and spec['y']<.9
 controller('read',[]);assert ev('backgroundLabelOverlay.text')==spec['text']
 assert not editor.property('dirty'),'Readback must not start another save merely because JSON keys were reordered'
 assert view.grabWindow().save(str(Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/'composition-edit.png'))
 finished=True;print('PASS: camera/background crop targeting; uninterrupted preview label typing; drag, font/style/caps and automatic metadata/profile readback');app.quit()
QTimer.singleShot(500,guard(begin));QTimer.singleShot(14000,app.quit);app.exec()
if errors or not finished:raise SystemExit('; '.join(errors) or 'Composition test timed out')
