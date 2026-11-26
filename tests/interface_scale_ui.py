"""Exercise the saved interface scale through real Qt shortcuts and the Setup spinner."""
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


root = Path(__file__).resolve().parents[1]
with TemporaryDirectory(dir=os.environ['WEBCAMTUNER_TEST_ROOT']) as temporary:
    scratch = Path(temporary)
    harness = scratch / 'shell.qml'
    harness.write_text('''import QtQuick
import QtTest
import Quickshell
import UI_PATH as Tuner

ShellRoot {
    TestCase {
        id: test
        when: false

        function exercise() {
            tryVerify(() => !window.editor.busy && window.editor.document)
            const panel = findChild(window.editor, "setupPanel")
            const spinner = findChild(panel, "interfaceScaleSpinner")
            if (Quickshell.env("WEBCAMTUNER_SCALE_RELOAD") === "1") {
                compare(spinner.value, 120)
                verifyVisualScale(1.2)
                return
            }
            compare(spinner.value, 70)
            verifyVisualScale(0.7)
            const output = JSON.stringify(window.editor.previewSettings())
            keyClick(Qt.Key_Plus, Qt.ControlModifier)
            tryCompare(spinner, "value", 80)
            verifyVisualScale(0.8)
            keyClick(Qt.Key_Minus, Qt.ControlModifier)
            tryCompare(spinner, "value", 70)
            keyClick(Qt.Key_Minus, Qt.ControlModifier)
            tryCompare(spinner, "value", 60)
            for (let index = 0; index < 5; index++) keyClick(Qt.Key_Equal, Qt.ControlModifier)
            tryCompare(spinner, "value", 110)

            wait(100)
            mouseClick(spinner.up.indicator, spinner.up.indicator.width / 2, spinner.up.indicator.height / 2)
            tryCompare(window, "interfaceScalePercent", 120)
            verifyVisualScale(1.2)

            const dialog = findChild(panel, "restartZoomDialog")
            dialog.open()
            tryVerify(() => dialog.opened)
            const overlay = dialog.parent
            tryVerify(() => {
                const end = overlay.mapToItem(null, overlay.width, overlay.height)
                return Math.abs(end.x - window.width) < 1 && Math.abs(end.y - window.height) < 1
            }, 1000, "Popup overlay must cover the scaled window")
            const dialogTop = dialog.contentItem.mapToItem(null, 0, 0)
            const dialogBottom = dialog.contentItem.mapToItem(null, dialog.contentItem.width, dialog.contentItem.height)
            verify(dialogTop.x >= 0 && dialogTop.y >= 0)
            verify(dialogBottom.x <= window.width && dialogBottom.y <= window.height)
            dialog.close()
            tryCompare(dialog, "visible", false)

            for (let index = 0; index < 6; index++) keyClick(Qt.Key_Plus, Qt.ControlModifier)
            tryCompare(spinner, "value", 150)
            verifyVisualScale(1.5)
            for (let index = 0; index < 11; index++) keyClick(Qt.Key_Minus, Qt.ControlModifier)
            tryCompare(spinner, "value", 50)
            verifyVisualScale(0.5)
            for (let index = 0; index < 7; index++) keyClick(Qt.Key_Equal, Qt.ControlModifier)
            tryCompare(spinner, "value", 120)
            compare(JSON.stringify(window.editor.previewSettings()), output)
            verify(!window.editor.dirty)
            window.toggleCollapse()
            tryCompare(window, "height", Math.ceil(42 * 1.2))
            window.toggleCollapse()
            tryCompare(window, "height", window.expandedHeight)

            const nativeWindow = window.titleBar.Window.window
            nativeWindow.width = 300
            nativeWindow.height = 240
            tryCompare(window, "width", 300)
            tryCompare(window, "height", 240)
            verifyVisualScale(1.2 * Math.min(300 / 540, 240 / 460))
            compare(spinner.value, 120)
            const spinnerEnd = spinner.mapToItem(null, spinner.width, spinner.height)
            verify(spinnerEnd.x <= window.width && spinnerEnd.y <= window.height)

            window.toggleCollapse()
            tryCompare(window, "height", Math.ceil(42 * 1.2 * 300 / 540))
            tryCompare(window, "width", 300)
            window.toggleCollapse()
            tryCompare(window, "height", 240)
            tryCompare(window, "width", 300)
            window.closeEditor()
            window.openSetup()
            tryCompare(window, "width", 300)
            tryCompare(window, "height", 240)
        }

        function verifyVisualScale(scale) {
            const surface = findChild(window.contentItem, "tunerThemeSurface")
            tryVerify(() => Math.abs(window.titleBar.mapToItem(null, 0, 42).y - 42 * scale) < 0.1)
            fuzzyCompare(surface.mapToItem(null, surface.width, surface.height).x, window.width, 1)
            fuzzyCompare(surface.mapToItem(null, surface.width, surface.height).y, window.height, 1)
        }
    }
    Tuner.TunerWindow {
        id: window
        Component.onCompleted: { editor.testing = true; openSetup() }
    }
    Timer {
        interval: 400
        running: true
        onTriggered: {
            try {
                test.exercise()
                finish.start()
            } catch (error) {
                console.error(error, error.stack)
                Qt.exit(1)
            }
        }
    }
    Timer {
        id: finish
        interval: 700
        onTriggered: { console.log("INTERFACE_SCALE_PASS"); Qt.quit() }
    }
}
'''.replace('UI_PATH', json.dumps((root / 'ui').as_uri())))
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                       WEBCAMTUNER_CONFIG_ROOT=str(scratch / 'profiles'),
                       XDG_CONFIG_HOME=str(scratch / 'config'), XDG_DATA_HOME=str(scratch / 'data'),
                       XDG_CACHE_HOME=str(scratch / 'cache'))
    for reload in ('0', '1'):
        result = subprocess.run(['qs', '-p', str(harness)],
                                env=dict(environment, WEBCAMTUNER_SCALE_RELOAD=reload),
                                capture_output=True, text=True, timeout=18)
        output = result.stdout + result.stderr
        assert result.returncode == 0 and 'INTERFACE_SCALE_PASS' in output, output

print('PASS: 70% default, saved scale controls, popup fit, and compact-window resize and restore')
