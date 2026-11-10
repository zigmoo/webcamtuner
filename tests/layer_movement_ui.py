"""Three independent grips work in either mirror mode and retain focus through updates."""
import json
import os
from pathlib import Path
import subprocess
import traceback
import uuid

os.environ.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',QT_SCALE_FACTOR='1')
from PIL import Image
from PySide6.QtCore import QUrl,QTimer,QPointF,Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlExpression,qmlContext
from PySide6.QtQuick import QQuickItem,QQuickView
from PySide6.QtTest import QTest

root=Path(__file__).resolve().parents[1]
scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/('layer-movement-'+uuid.uuid4().hex)
scratch.mkdir()
os.environ.update(WEBCAMTUNER_CONFIG_ROOT=str(scratch/'config'),XDG_DATA_HOME=str(scratch/'data'),XDG_CACHE_HOME=str(scratch/'cache'))
source=scratch/'Background.png'
Image.new('RGB',(1600,900),'#275781').save(source)
app=QGuiApplication([])
view=QQuickView()
view.setResizeMode(QQuickView.SizeRootObjectToView)
view.setSource(QUrl.fromLocalFile(str(root/'ui/Editor.qml')))
assert not view.errors(),[e.toString() for e in view.errors()]
view.resize(1100,1000)
editor=view.rootObject()
editor.setProperty('testing',True)

def ev(code):
    expression=QQmlExpression(qmlContext(editor),editor,code)
    value=expression.evaluate()
    assert not expression.hasError(),expression.error().toString()
    return value[0] if isinstance(value,tuple) else value

def controller(action,args):
    if hasattr(args,'toVariant'):args=args.toVariant()
    value=json.loads(subprocess.check_output([str(root/'bin/webcamtuner'),action,*args,'--json'],text=True))
    ev('accept('+json.dumps(action)+','+json.dumps(value)+')')

def find(item,name):
    if item.objectName()==name:return item
    if isinstance(item,QQuickItem):
        for child in item.childItems():
            found=find(child,name)
            if found:return found

def state():
    return json.loads(ev('JSON.stringify({camera:foreground,background:backgroundCrop,label:backgroundLabelOverlay,cameraCrop:{zoom:zoom,x:centerX,y:centerY}})'))

def drag(name,dx,dy,refresh=False):
    item=find(editor,name)
    assert item and item.isEnabled(),name
    start=item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint()
    end=start+QPointF(dx,dy).toPoint()
    QTest.mousePress(view,Qt.LeftButton,Qt.NoModifier,start)
    QTest.mouseMove(view,start+QPointF(dx/2,dy/2).toPoint(),40)
    if refresh:
        editor.setProperty('busy',True)
        controller('backgrounds',[])
        editor.setProperty('busy',False)
        QTest.qWait(900)
        assert item.property('pressed'),'An unrelated refresh/save cancelled the drag'
    QTest.mouseMove(view,end,40)
    QTest.mouseRelease(view,Qt.LeftButton,Qt.NoModifier,end)
    app.processEvents()

editor.request.connect(controller)
controller('read',[])
editor.setProperty('section','background')
ev('addBackgrounds('+json.dumps([str(source)])+')')
editor.setProperty('section','camera')
ev('editLabel({enabled:true,text:"Independent",x:.4,y:.7})')
view.show()
errors=[]
finished=False

def exercise():
    try:
        stage=find(editor,'cameraCompositionStage')
        for mirror in (False,True):
            editor.setProperty('mirror',mirror)
            sign=-1 if mirror else 1
            ev('placeForeground(0,0);editBackgroundCrop({zoom:2,centerX:.5,centerY:.5});editLabel({x:.4,y:.7})')
            app.processEvents()
            # An opposite crop selection must never redirect a movement handle.
            ev('cropTool.target="background"')
            before=state()
            drag('cameraMoveDrag',45,-15,refresh=True)
            after=state()
            assert after['background']==before['background'] and after['label']==before['label'] and after['cameraCrop']==before['cameraCrop']
            assert abs(after['camera']['x']*sign*stage.width()-45)<3
            assert after['camera']['y']<0
            assert ev('cropTool.target')=='background'
            ev('cropTool.target="camera"')
            before=state()
            drag('backgroundMoveDrag',35,-10)
            after=state()
            assert after['camera']==before['camera'] and after['label']==before['label'] and after['cameraCrop']==before['cameraCrop']
            assert (after['background']['centerX']-.5)*sign<0
            assert after['background']['centerY']>.5
            assert ev('cropTool.target')=='camera'
            before=state()
            drag('previewLabelDrag',50,-15,refresh=True)
            after=state()
            assert after['camera']==before['camera'] and after['background']==before['background'] and after['cameraCrop']==before['cameraCrop']
            assert (after['label']['x']-.4)*sign>0 and after['label']['y']<.7
            # Empty-image dragging is deliberately inert; each grip has one target.
            before=state()
            drag('cameraCompositionStage',20,-5)
            assert state()==before
        # Small keyboard nudges offer a precise, independently targeted adjustment.
        handle=find(editor,'cameraMoveHandle')
        handle.forceActiveFocus()
        before=state()
        QTest.keyClick(view,Qt.Key_Right)
        assert state()['camera']['x']<before['camera']['x']
        assert state()['background']==before['background'] and state()['label']==before['label']
        assert all(find(editor,name).height()>=36 for name in ('cameraMoveDrag','backgroundMoveDrag','previewLabelDrag'))
        ev('editLabel({enabled:false})')
        app.processEvents()
        assert not find(editor,'labelMoveHandle').isEnabled()
        assert not find(editor,'interactivePreviewLabel').isVisible()
        ev('editLabel({enabled:true})')
        QTimer.singleShot(1800,verify)
    except Exception:
        errors.append(traceback.format_exc())
        app.quit()

def verify():
    global finished
    try:
        current=state()
        store=json.loads((scratch/'config/profiles.json').read_text())
        profile=store['profiles'][0]
        assert profile['foreground']==current['camera']
        assert profile['background']['crop']==current['background']
        assert profile['background']['labelOverlay']==current['label']
        assert not editor.property('dirty') and not editor.property('busy')
        assert view.grabWindow().save(str(Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/'independent-layer-handles.png'))
        finished=True
        print('PASS: independent camera/background/label grips; opposite crop selection; both mirror modes; 36px hit targets; held drag across refresh/save; keyboard precision; automatic storage readback')
    except Exception:errors.append(traceback.format_exc())
    app.quit()

QTimer.singleShot(700,exercise)
QTimer.singleShot(18000,app.quit)
app.exec()
if errors or not finished:raise SystemExit('; '.join(errors) or 'Layer movement test timed out')
