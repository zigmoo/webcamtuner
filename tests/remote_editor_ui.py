"""Remote selection stays explicit, survives inventory refresh and rolls back on failure."""
import json,os,subprocess
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['QT_QUICK_BACKEND']='software'
from PySide6.QtCore import QObject,QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlExpression,qmlContext
from PySide6.QtQuick import QQuickView
root=Path(__file__).resolve().parents[1];scratch=Path(os.environ['WEBCAMTUNER_TEST_ROOT'])
os.environ['WEBCAMTUNER_CONFIG_ROOT']=str(scratch/'remote-editor-profiles')
app=QGuiApplication([]);view=QQuickView();view.setResizeMode(QQuickView.SizeRootObjectToView)
view.setSource(QUrl.fromLocalFile(str(root/'ui/Editor.qml')));assert not view.errors(),[e.toString() for e in view.errors()]
editor=view.rootObject();editor.setProperty('testing',True)
def ev(code):
 q=QQmlExpression(qmlContext(editor),editor,code);v=q.evaluate();assert not q.hasError(),q.error().toString();return v
store=json.loads(subprocess.check_output([str(root/'bin/webcamtuner'),'read','--json']))
ev('accept("read",'+json.dumps(store)+')');ev('savedCamera="/dev/video101";sourceKind="local";sourceHost="";previewOn=false;remoteBrowse=true')
uri='sshcam://omarchy-zbook?camera=%2Fdev%2Fv4l%2Fby-id%2FC930e-video-index0'
ev('connectRemote('+json.dumps(uri)+',"omarchy-zbook")')
assert editor.property('sourceKind')=='remote' and editor.property('remoteConnecting')
assert editor.property('previewOn') and not editor.property('publishing'),'Connect must preview without publishing'
ev('chooseCamera()');assert editor.property('savedCamera')==uri,'Local inventory must not replace remote choice'
ev('rejectRemote("Camera is busy. Previous camera retained.")')
assert editor.property('savedCamera')=='/dev/video101' and not editor.property('previewOn')
assert not editor.property('remoteConnecting')
panel=editor.findChild(QObject,'remoteSources');context=qmlContext(panel)
def pv(code):
 q=QQmlExpression(context,panel,code);q.evaluate();assert not q.hasError(),q.error().toString()
pv('accept({machines:[{name:"ZBook",host:"omarchy-zbook",online:true,supported:true},{name:"EliteBook",host:"omarchy-elitebook",online:true,supported:true}]})')
pv('inspect(0)');pv('accept({cameras:[{id:"/dev/video4",stableId:"/dev/v4l/by-id/C930e-video-index0",name:"Logitech C930e",modes:[{format:"mjpeg",size:"1280x720",fps:30}]},{id:"/dev/video0",name:"Built-in HP"}]})')
pv('selectCamera(0)')
panel.findChild(QObject,'remoteHostChoice').setProperty('currentIndex',0);panel.findChild(QObject,'remoteCameraChoice').setProperty('currentIndex',0)
for width in (540,780,1100):
 view.resize(width,900);view.show();app.processEvents()
 for name in ('remoteHostChoice','remoteCameraChoice','remoteQualityChoice'):
  item=panel.findChild(QObject,name);assert item.width()>40 and item.x()+item.width()<width,(name,item.width(),width)
 if width==780:view.grabWindow().save(str(scratch/'remote-editor.png'))
print('PASS: remote connect is preview-only; hotplug does not silently replace source; failed connection restores prior source; editor widths 540/780/1100')
