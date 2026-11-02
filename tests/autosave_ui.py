"""Profile autosave preserves newer edits, reports errors and saves after close."""
import json, os, subprocess, uuid, traceback
from pathlib import Path
os.environ.update(QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtQml import QQmlExpression, qmlContext
root = Path(__file__).resolve().parent.parent
scratch = Path(os.environ['WEBCAMTUNER_TEST_ROOT']) / ('autosave-' + uuid.uuid4().hex)
scratch.mkdir()
os.environ['WEBCAMTUNER_CONFIG_ROOT'] = str(scratch)
app = QGuiApplication([])
view = QQuickView(); view.setResizeMode(QQuickView.SizeRootObjectToView)
view.setSource(QUrl.fromLocalFile(str(root/'ui/Editor.qml')))
assert view.status() != QQuickView.Error
view.resize(700, 780); editor = view.rootObject(); editor.setProperty('testing', True)
def ev(expression):
    e = QQmlExpression(qmlContext(editor), editor, expression); value = e.evaluate()
    assert not e.hasError(), e.error().toString()
    return value[0] if isinstance(value, tuple) else value
def cli(action, args):
    return json.loads(subprocess.check_output([str(root/'bin/webcamtuner'), action, *args, '--json'], text=True))
def saved(): return json.loads((scratch/'profiles.json').read_text())
errors = []; pending = []; fail_next = False; finished = False
def guard(callback):
    def wrapped():
        try: callback()
        except Exception: errors.append(traceback.format_exc()); app.quit()
    return wrapped
def later(delay, callback): QTimer.singleShot(delay, guard(callback))
def controller(action, args):
    global fail_next
    if hasattr(args, 'toVariant'): args = args.toVariant()
    if action != 'save': ev('accept('+json.dumps(action)+','+json.dumps(cli(action,args))+')'); return
    pending.append(json.loads(args[1]))
    editor.setProperty('busy', True)
    simulate_failure = fail_next; fail_next = False
    def reply():
        editor.setProperty('busy', False)
        if simulate_failure: ev('fail("Simulated disk failure")')
        else: ev('accept("save",'+json.dumps(cli(action,args))+')')
    later(600, reply)
editor.request.connect(controller)
ev('accept("read",'+json.dumps(cli('read',[]))+')')
view.show()
def start():
    ev('profileName="Desk renamed"; backgroundMode="blur"; frame(2,.5,.5); placeForeground(.2,.1)')
    later(900, newer_edit)
def newer_edit():
    assert editor.property('savePending') and len(pending)==1
    ev('profileName="Latest name"; placeForeground(.7,-.2)')
    later(2600, check_latest)
def check_latest():
    global fail_next
    p=saved()['profiles'][0]
    assert p['name']=='Latest name' and p['foreground']=={'x':.7,'y':-.2}
    assert p['crop']['zoom']==2 and p['background']['mode']=='blur'
    assert not editor.property('dirty') and len(pending)==2
    fail_next=True; ev('placeForeground(-.4,.3)')
    later(1500, check_failure)
def check_failure():
    assert editor.property('saveFailed') and editor.property('dirty')
    assert saved()['profiles'][0]['foreground']=={'x':.7,'y':-.2}
    ev('placeForeground(-.5,.4)'); editor.setProperty('panelOpen',False); view.hide()
    later(1600, check_closed)
def check_closed():
    global finished
    assert not editor.property('saveFailed') and not editor.property('dirty')
    assert saved()['profiles'][0]['foreground']=={'x':-.5,'y':.4}
    ev('accept("read",'+json.dumps(cli('read',[]))+')')
    assert editor.property('profileName')=='Latest name' and ev('foreground.x')==-.5
    finished=True
    print('PASS: automatic named-profile persistence, edits during save, failure retention, retry on edit and save after close')
    app.quit()
later(200,start); QTimer.singleShot(14000,app.quit); app.exec()
if errors or not finished: raise SystemExit('; '.join(errors) or 'Autosave test timed out')
