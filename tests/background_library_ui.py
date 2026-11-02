"""Exercise imported gallery images through the real editor/controller without capture."""
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

os.environ.update(QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
from PySide6.QtCore import QUrl, QTimer, QObject
from PySide6.QtGui import QGuiApplication, QColor
from PySide6.QtQml import QQmlExpression, qmlContext
from PySide6.QtQuick import QQuickView
from PIL import Image

root = Path(__file__).resolve().parent.parent
scratch = Path(os.environ['WEBCAMTUNER_TEST_ROOT']) / ('gallery-' + uuid.uuid4().hex)
scratch.mkdir(parents=True)
os.environ.update(WEBCAMTUNER_CONFIG_ROOT=str(scratch/'profiles'), XDG_DATA_HOME=str(scratch/'data'), XDG_CACHE_HOME=str(scratch/'cache'))
source = scratch / 'Test backdrop.png'
Image.new('RGB', (1280,720), '#284e71').save(source)
app = QGuiApplication(sys.argv)
view = QQuickView(); view.setResizeMode(QQuickView.SizeRootObjectToView);view.setColor(QColor('#171c24'))
view.setSource(QUrl.fromLocalFile(str(root/'ui/Editor.qml')))
assert view.status() != QQuickView.Error
view.resize(540,800)
editor = view.rootObject();editor.setProperty('testing',True)

def ev(text):
    expression = QQmlExpression(qmlContext(editor),editor,text)
    result = expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    return result


def controller(action,args):
    if hasattr(args,'toVariant'):args=args.toVariant()
    result=json.loads(subprocess.check_output([str(root/'bin/webcamtuner'),action,*args,'--json'],text=True))
    ev('accept('+json.dumps(action)+','+json.dumps(result)+')')

editor.request.connect(controller)
controller('read',[])
view.show()
failures=[]

def exercise():
    try:
        ev('frame(2,0.6,0.4)')
        editor.setProperty('section','background')
        ev('addBackgrounds('+json.dumps([str(source)])+')')
        assert editor.property('zoom')==2 and editor.property('dirty')
        model=ev('JSON.stringify(backgroundLibrary)')[0]
        model=json.loads(model)
        assert len(model['items'])==1 and Path(model['directory']).is_dir()
        assert Path(editor.property('imagePath')).parent==Path(model['directory'])
        source.unlink()
        ev('save()')
        store=json.loads((scratch/'profiles/profiles.json').read_text())
        assert store['profiles'][0]['crop']=={'zoom':2,'centerX':0.6,'centerY':0.4}
        assert Path(store['profiles'][0]['background']['imagePath']).exists()
        QTimer.singleShot(500,finish)
    except Exception as error:
        failures.append(str(error));app.quit()

def finish():
    try:
        assert view.grabWindow().save(str(Path(os.environ['WEBCAMTUNER_TEST_ROOT'])/'gallery-review.png'))
        print('PASS: gallery copies, lists, selects and saves a managed image without losing crop edits')
    finally:app.quit()

QTimer.singleShot(400,exercise);QTimer.singleShot(10000,app.quit);app.exec()
if failures:raise SystemExit('; '.join(failures))
