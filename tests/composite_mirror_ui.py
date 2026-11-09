"""Whole-scene preview reflection, readable label editor and pointer direction."""
import json
import os
from pathlib import Path
import subprocess
import traceback
import uuid

os.environ.update(QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', QT_SCALE_FACTOR='1')
from PIL import Image, ImageDraw, ImageChops, ImageStat
from PySide6.QtCore import QPointF, Qt, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlExpression, qmlContext
from PySide6.QtQuick import QQuickView, QQuickItem
from PySide6.QtTest import QTest

root = Path(__file__).resolve().parents[1]
scratch = Path(os.environ['WEBCAMTUNER_TEST_ROOT']) / ('composite-mirror-' + uuid.uuid4().hex)
scratch.mkdir()
os.environ.update(WEBCAMTUNER_CONFIG_ROOT=str(scratch/'config'), XDG_DATA_HOME=str(scratch/'data'), XDG_CACHE_HOME=str(scratch/'cache'))
image = Image.new('RGB', (1600,900), '#226080')
ImageDraw.Draw(image).rectangle((0,0,550,900), fill='#b04030')
source = scratch/'Asymmetric.png'
image.save(source)
app = QGuiApplication([])
view = QQuickView()
view.setResizeMode(QQuickView.SizeRootObjectToView)
view.setSource(QUrl.fromLocalFile(str(root/'ui/Editor.qml')))
assert not view.errors(), [e.toString() for e in view.errors()]
view.resize(1100,950)
editor = view.rootObject()
editor.setProperty('testing', True)

def ev(code, item=editor):
    expression = QQmlExpression(qmlContext(item), item, code)
    result = expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    return result[0] if isinstance(result,tuple) else result

def controller(action,args):
    if hasattr(args,'toVariant'): args = args.toVariant()
    result = json.loads(subprocess.check_output([str(root/'bin/webcamtuner'),action,*args,'--json'],text=True))
    ev('accept('+json.dumps(action)+','+json.dumps(result)+')')

def find(item,name):
    if item.objectName() == name: return item
    if isinstance(item,QQuickItem):
        for child in item.childItems():
            found = find(child,name)
            if found: return found

def drag(item, dx, dy, point=None):
    start = item.mapToScene(point or QPointF(item.width()/2,item.height()/2)).toPoint()
    end = start + QPointF(dx,dy).toPoint()
    QTest.mousePress(view,Qt.LeftButton,Qt.NoModifier,start)
    QTest.mouseMove(view,end,50)
    QTest.mouseRelease(view,Qt.LeftButton,Qt.NoModifier,end)
    app.processEvents()

editor.request.connect(controller)
controller('read',[])
editor.setProperty('section','background')
ev('addBackgrounds('+json.dumps([str(source)])+')')
editor.setProperty('section','camera')
ev('editLabel({enabled:true,text:"Left > Right",x:.15,y:.75,fontSize:.06})')
view.show()
errors=[]
finished=False

def exercise():
    global finished
    try:
        stage = find(editor,'cameraCompositionStage')
        layer = find(editor,'cameraCompositionLayer')
        label = find(editor,'interactivePreviewLabel')
        # The real background, foreground and label all belong to one transform.
        assert find(editor,'backgroundImage').parentItem() == layer
        assert label.parentItem().parentItem() == layer
        for mirror in (False,True):
            editor.setProperty('mirror',mirror)
            ev('placeForeground(0,0)')
            ev('editLabel({x:.5,y:.75})')
            app.processEvents()
            sign = -1 if mirror else 1
            assert (layer.mapToScene(QPointF(1,0)).x()-layer.mapToScene(QPointF(0,0)).x())*sign > .9
            before = label.mapToScene(QPointF(label.width()/2,label.height()/2)).x()
            drag(find(editor,'previewLabelDrag'),45,-10)
            after = label.mapToScene(QPointF(label.width()/2,label.height()/2)).x()
            assert abs(after-before-45) < 3, (mirror,before,after)
            # Camera translation follows the same screen direction in either mode.
            drag(layer,40,0,QPointF(layer.width()*.45,layer.height()*.35))
            assert abs(ev('foreground.x')*stage.width()*sign-40) < 3
            # The source-background crop also follows the pointer under reflection.
            ev('cropTool.target="background";cropTool.changeZoom(2)')
            ev('editBackgroundCrop({zoom:2,centerX:.5,centerY:.5})')
            drag(layer,30,0,QPointF(layer.width()*.3,layer.height()*.25))
            assert (ev('backgroundCrop.centerX')-.5)*sign < 0
            ev('cropTool.target="camera"')
            ev('interactiveLabel.beginEditing()')
            field = find(editor,'previewLabelText')
            assert field.property('activeFocus')
            assert field.mapToScene(QPointF(1,0)).x() > field.mapToScene(QPointF(0,0)).x(), 'Editor text must remain readable'
            QTest.keyClick(view,Qt.Key_Escape)
        # Compare actual rendered pixels with all composition elements in place.
        ev('placeForeground(.1,0);editBackgroundCrop({zoom:1,centerX:.5,centerY:.5});editLabel({x:.15,y:.75})')
        for child in stage.childItems():
            if child != layer: child.setProperty('visible',False)  # Exclude UI chrome from video pixels.
        def capture(mirror,name):
            editor.setProperty('mirror',mirror)
            QTest.qWait(80)
            top = stage.mapToScene(QPointF(0,0))
            path = scratch/name
            assert view.grabWindow().copy(round(top.x()),round(top.y()),round(stage.width()),round(stage.height())).save(str(path))
            return Image.open(path).convert('RGB')
        normal = capture(False,'normal.png')
        mirrored = capture(True,'mirrored.png')
        diff = ImageStat.Stat(ImageChops.difference(normal.transpose(Image.Transpose.FLIP_LEFT_RIGHT),mirrored))
        assert max(diff.mean) < 4, diff.mean
        ev('cropTool.openEditor()')
        app.processEvents()
        crop_layer = find(view.contentItem(),'cropCompositionLayer')
        assert crop_layer
        assert crop_layer.mapToScene(QPointF(1,0)).x() < crop_layer.mapToScene(QPointF(0,0)).x()
        ev('cropTool.closeEditor()')
        finished = True
        print('PASS: whole-scene preview pixels; camera/background/label drags follow pointer in both modes; label editor readable; crop composite reflected')
    except Exception:
        errors.append(traceback.format_exc())
    app.quit()

QTimer.singleShot(700,exercise)
QTimer.singleShot(14000,app.quit)
app.exec()
if errors or not finished: raise SystemExit('; '.join(errors) or 'Mirror UI test timed out')
