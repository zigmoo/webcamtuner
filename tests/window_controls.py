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
import QtTest
import "''' + (root / 'ui').as_uri() + '''" as Tuner
ShellRoot {
 TestCase { id: pointer; when: false }
 property int phase: 0
 property int readyTicks: 0
 property int holdTicks: 0
 property int visibilityChanges: 0
 property int beforeCollapse: 0
 property int fullHeight: 0
 function expect(value, message) { if (!value) { console.log("FAIL: " + message); Qt.exit(1) } }
 Tuner.TunerWindow {
  id:w
  Component.onCompleted: { editor.testing=true; openEditor() }
 }
 Connections { target:w; function onVisibleChanged() { visibilityChanges++ } }
 Timer {
  interval:150; running:true; repeat:true
  onTriggered: {
   if (!w.editor.document || w.editor.busy) return
   if (phase === 0) {
    if (++readyTicks < 5) return
    fullHeight=w.height
    w.editor.previewOn=true; w.editor.dirty=true
    beforeCollapse=visibilityChanges
    pointer.mouseClick(pointer.findChild(w.titleBar, "windowMinimizeButton"),16,16)
   } else if (phase === 1) {
    expect(w.collapsed && w.height === w.collapsedHeight, "collapse to titlebar")
    expect(w.editor.previewOn && w.editor.dirty, "minimize retains preview and draft")
    expect(w.visible && visibilityChanges === beforeCollapse, "collapse must not hide/remap the window")
    if (++holdTicks < 12) return
    pointer.mouseClick(pointer.findChild(w.titleBar, "windowMinimizeButton"),16,16)
   } else if (phase === 2) {
    expect(!w.collapsed && (Quickshell.env("QT_QPA_PLATFORM") === "offscreen" ? w.height >= 460 : w.height === fullHeight), "restore height: got " + w.height + " expected " + fullHeight)
    pointer.mouseClick(pointer.findChild(w.titleBar, "windowCloseButton"),16,16)
   } else if (phase === 3) {
    expect(!w.visible && !w.editor.previewOn && w.editor.dirty, "close hides, stops camera, keeps draft")
    w.openEditor()
   } else if (phase === 4) {
    expect(w.visible && !w.collapsed, "bar recall restores full window")
    var nameField = pointer.findChild(w.editor, "profileName")
    nameField.forceActiveFocus()
    nameField.selectAll()
    pointer.keyClick(Qt.Key_Q)
    expect(w.visible && nameField.text.toLowerCase() === "q", "Q stays available in text input")
    pointer.keyClick(Qt.Key_Escape)
   } else if (phase === 5) {
    expect(!w.visible, "Escape closes with focus in a text field")
    w.openEditor()
    var tabs = pointer.findChild(w.contentItem, "navigationTabs")
    tabs.currentIndex = tabs.count - 1
    tabs.itemAt(tabs.currentIndex).forceActiveFocus()
   } else if (phase === 6) {
    pointer.keyClick(Qt.Key_Q)
   } else if (phase === 7) {
    expect(!w.visible, "Q closes with focus outside the editor")
    w.openEditor()
    w.toggleCollapse()
   } else if (phase === 8) {
    pointer.keyClick(Qt.Key_Escape)
   } else if (phase === 9) {
    expect(!w.visible, "Escape closes the collapsed window")
    console.log("PASS: real window collapse/expand preserves geometry, preview and draft; Q and Escape close")
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
print('PASS: real palette controls, Q and Escape close, and text fields retain Q')
