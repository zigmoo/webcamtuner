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
        ev('labelDisclosure.expanded=true')
        QTest.qWait(150)
        stage = find(editor,'cameraCompositionStage')
        layer = find(editor,'cameraCompositionLayer')
        label = find(editor,'interactivePreviewLabel')
        grip = find(editor,'labelMoveHandle')
        checkbox = find(editor,'showPreviewLabel')
        handles = find(editor,'previewLabelMoveHandles')
        assert grip.property('text') == 'Drag Label'
        assert grip.mapToScene(QPointF(grip.width(), grip.height()/2)).x() <= checkbox.mapToScene(QPointF()).x()
        assert abs(grip.mapToScene(QPointF(0, grip.height()/2)).y() -
                   checkbox.mapToScene(QPointF(0, checkbox.height()/2)).y()) <= 1
        grip_center = grip.mapToScene(QPointF(grip.width()/2, grip.height()/2)).toPoint()
        stage_center = stage.mapToScene(QPointF(stage.width()/2, stage.height()/2)).toPoint()
        QTest.mouseMove(view, grip_center)
        assert handles.isVisible()
        QTest.mouseMove(view, stage_center)
        assert not handles.isVisible()
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
            QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, grip_center)
            QTest.mouseMove(view, stage_center)
            assert handles.isVisible()
            direct = find(editor,'previewLabelPositionDrag')
            drag(direct, 24, 8)
            assert abs(label.mapToScene(QPointF(label.width()/2,label.height()/2)).x()-after-24) < 3
            corner = find(editor,'previewLabelResize-3')
            old_size = ev('backgroundLabelOverlay.fontSize')
            old_width = label.width()
            anchor = label.mapToScene(QPointF())
            drag(corner, 30*sign, 14)
            assert ev('backgroundLabelOverlay.fontSize') > old_size
            assert label.width() > old_width
            assert (label.mapToScene(QPointF())-anchor).manhattanLength() < 2
            ev('editLabel({fontSize:.06})')
            disclosure = find(editor,'labelDisclosure')
            inside = disclosure.mapToScene(QPointF(disclosure.width()-3, disclosure.height()-3)).toPoint()
            QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, inside)
            assert handles.isVisible()
            QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, stage_center)
            assert not handles.isVisible()
            # Camera translation follows the same screen direction in either mode.
            drag(find(editor,'cameraMoveDrag'),40,0)
            assert abs(ev('foreground.x')*stage.width()*sign-40) < 3
            # The source-background crop also follows the pointer under reflection.
            ev('cropTool.target="background";cropTool.changeZoom(2)')
            ev('editBackgroundCrop({zoom:2,centerX:.5,centerY:.5})')
            drag(find(editor,'backgroundMoveDrag'),30,0)
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
        ev('cropTool.target="background";cropTool.openEditor()')
        app.processEvents()
        original_image = find(view.contentItem(),'cropOriginalImage')
        assert original_image
        assert original_image.mapToScene(QPointF(1,0)).x() > original_image.mapToScene(QPointF(0,0)).x()
        ev('cropTool.closeEditor()')
        finished = True
        print('PASS: whole-scene preview pixels; camera/background/label drags follow pointer in both modes; label editor readable; original image stays unmirrored in the crop dialog')
    except Exception:
        errors.append(traceback.format_exc())
    app.quit()

QTimer.singleShot(700,exercise)
QTimer.singleShot(14000,app.quit)
app.exec()
if errors or not finished: raise SystemExit('; '.join(errors) or 'Mirror UI test timed out')
