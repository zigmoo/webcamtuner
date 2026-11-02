import QtQuick
import Quickshell
import Quickshell.Io
import qs.Ui
import qs.Commons as Commons
import "ui" as Tuner

BarWidget {
    id: root
    moduleName: "moo.webcamtuner"
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    readonly property bool opened: panel.visible
    property bool popoutSwitchClosing: false
    function open() {
        if (bar && typeof bar.moduleWidgets === "function") {
            var others = bar.moduleWidgets(moduleName)
            for (var i = 0; i < others.length; i++)
                if (others[i] && others[i] !== root && typeof others[i].close === "function") others[i].close()
        }
        panel.openEditor()
    }
    function close() { panel.closeEditor() }
    function toggle() { opened ? close() : open() }
    function closeForPopoutSwitch() { close() }
    BarIconButton {
        id: button
        anchors.fill: parent; bar: root.bar
        text: "󰖠"; tooltipText: "WebcamTuner · framing profiles"
        onPressed: root.toggle()
    }
    IpcHandler {
        target: root.moduleName
        function open(): void { root.open() }
        function close(): void { root.close() }
        function setup(): void { panel.openSetup() }
        function toggle(): void { root.toggle() }
        function minimize(): void { if (root.opened && !panel.collapsed) panel.toggleCollapse() }
        function status(): string {
            return JSON.stringify({ opened: root.opened, collapsed: panel.collapsed, width: panel.width, height: panel.height,
                busy: panel.editor.busy, dirty: panel.editor.dirty, message: panel.editor.message,
                mirror: panel.editor.mirror, autostartCamera: panel.editor.autostartCamera, previewOn: panel.editor.previewOn,
                revision: panel.editor.document ? panel.editor.document.revision : -1, broadcasting: false })
        }
    }
    Tuner.TunerWindow {
        id: panel
        color: Commons.Color.background
        accent: Commons.Color.accent
    }
}
