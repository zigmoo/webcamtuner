"""Remote discovery never starts capture; an explicit camera selection is required."""
import os
from pathlib import Path
import sys
from urllib.parse import urlparse, parse_qs
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QUICK_BACKEND'] = 'software'
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlExpression, qmlContext
from PySide6.QtQuick import QQuickView

root = Path(__file__).resolve().parents[1]
app = QGuiApplication([])
view = QQuickView()
view.setResizeMode(QQuickView.SizeRootObjectToView)
view.setSource(QUrl.fromLocalFile(str(root / 'ui/RemoteSources.qml')))
assert not view.errors(), [e.toString() for e in view.errors()]
panel = view.rootObject(); panel.setProperty('testing', True)
requests, connections = [], []
panel.discoveryRequested.connect(lambda args: requests.append(args.toVariant() if hasattr(args,"toVariant") else args))
panel.connectCamera.connect(lambda uri, host: connections.append((uri,host)))
def evaluate(expression):
    q = QQmlExpression(qmlContext(panel), panel, expression); result=q.evaluate()
    assert not q.hasError(), q.error().toString()
    return result
evaluate('refresh()')
assert requests == [[]] and connections == []
evaluate('accept({machines:[{host:"zbook.example",name:"ZBook",online:true,supported:true},{host:"offline.example",online:false,supported:true}]})')
evaluate('inspect(1)')
assert len(requests) == 1 and not panel.findChild(QObject,'remoteConnect').property('enabled')
evaluate('inspect(0)')
assert requests[-1] == ['--host','zbook.example'] and connections == []
evaluate('accept({cameras:[{id:"/dev/video4",stableId:"/dev/v4l/by-id/logitech-video-index0",name:"C930e",modes:[{format:"mjpeg",size:"1280x720",fps:30}]},{id:"/dev/video0",name:"Built-in"}]})')
assert not panel.findChild(QObject,'remoteConnect').property('enabled'), 'Do not select a built-in camera implicitly'
evaluate('selectCamera(0)')
assert panel.findChild(QObject,'remoteConnect').property('enabled')
panel.findChild(QObject,'remoteConnect').clicked.emit()
assert len(connections)==1
uri,host=connections[0]
assert host=='zbook.example' and parse_qs(urlparse(uri).query)['camera']==['/dev/v4l/by-id/logitech-video-index0']
panel.setProperty('connecting',True)
assert not panel.findChild(QObject,'remoteConnect').property('enabled')
assert panel.findChild(QObject,'remoteDisconnect').property('enabled')
for width in (496, 736, 1056):
    view.resize(width,480); view.show(); app.processEvents()
    for name in ('remoteHostChoice','remoteCameraChoice','remoteQualityChoice'):
        item=panel.findChild(QObject,name)
        assert item.width()>50 and item.x()+item.width()<=width+1,(name,width,item.width())
    if width==736:
        view.grabWindow().save(str(Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/'remote-sources.png'))
print('PASS: offline/online discovery, explicit camera choice, stable URI, connect/cancel state and responsive layout')
