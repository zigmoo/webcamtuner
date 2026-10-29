"""Verify palette collapse, restore, and close against the real Quickshell window."""
import os
from pathlib import Path
import subprocess
import uuid

root = Path(__file__).resolve().parent.parent
scratch = Path(os.environ['WEBCAMTUNER_TEST_ROOT']) / ('window-' + uuid.uuid4().hex)
scratch.mkdir(parents=True)
harness = scratch / 'shell.qml'
harness.write_text('''import QtQuick
import Quickshell
import "''' + (root / 'ui').as_uri() + '''" as Tuner
ShellRoot {
 property int phase: 0
 property int fullHeight: 0
 function expect(value, message) { if (!value) { console.log("FAIL: " + message); Qt.exit(1) } }
 Tuner.TunerWindow {
  id:w
  Component.onCompleted: { editor.testing=true; openEditor() }
 }
 Timer {
  interval:150; running:true; repeat:true
  onTriggered: {
   if (!w.editor.document || w.editor.busy) return
   if (phase === 0) {
    fullHeight=w.height
    w.editor.previewOn=true; w.editor.dirty=true
    w.titleBar.minimizeRequested()
   } else if (phase === 1) {
    expect(w.collapsed && w.height === 42, "collapse to titlebar")
    expect(w.editor.previewOn && w.editor.dirty, "minimize retains preview and draft")
    w.titleBar.minimizeRequested()
   } else if (phase === 2) {
    expect(!w.collapsed && w.height === fullHeight, "restore previous height: got " + w.height + " expected " + fullHeight + " saved " + w.expandedHeight + " implicit " + w.implicitHeight + " max " + w.maximumSize.height)
    w.titleBar.closeRequested()
   } else if (phase === 3) {
    expect(!w.visible && !w.editor.previewOn && w.editor.dirty, "close hides, stops camera, keeps draft")
    w.openEditor()
   } else if (phase === 4) {
    expect(w.visible && !w.collapsed, "bar recall restores full window")
    w.closeEditor()
    console.log("PASS: real window collapse/expand preserves geometry, preview and draft; close stops preview; recall expands")
    Qt.quit()
   }
   phase++
  }
 }
 Timer { interval:6000; running:true; onTriggered: {console.log("FAIL: lifecycle timeout"); Qt.exit(1)} }
}''')
env = dict(os.environ, QT_QPA_PLATFORM='wayland' if os.environ.get('WEBCAMTUNER_NATIVE_TEST') else 'offscreen', QT_QUICK_BACKEND='software', WEBCAMTUNER_CONFIG_ROOT=str(scratch / 'profiles'))
result = subprocess.run(['qs', '-p', str(harness)], env=env, capture_output=True, text=True, timeout=10)
output = result.stdout + result.stderr
if result.returncode or 'PASS: real window collapse/expand' not in output:
    print(output[-4000:])
    raise SystemExit('Window controls failed')
print('PASS: real palette collapse/expand retains geometry, preview and draft; close stops preview; recall expands')
