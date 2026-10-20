import QtQuick
import Quickshell.Io
import qs.Ui
import qs.Commons as Commons
import "ui" as Tuner

BarWidget {
    id: root
    moduleName: "moo.webcamtuner"
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    readonly property bool opened: panel.open
    property bool popoutSwitchClosing: false
    function open() {
        if (bar && typeof bar.moduleWidgets === "function") {
            var others = bar.moduleWidgets(moduleName)
            for (var i = 0; i < others.length; i++)
                if (others[i] && others[i] !== root && typeof others[i].close === "function") others[i].close()
        }
        panel.open = true
        if (!editor.document) bridge.request("read", [])
    }
    function close() { editor.previewOn = false; panel.open = false }
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
        function toggle(): void { root.toggle() }
        function status(): string {
            return JSON.stringify({ opened: root.opened, busy: bridge.busy, message: editor.message,
                revision: editor.document ? editor.document.revision : -1, broadcasting: false })
        }
    }
    Tuner.Bridge {
        id: bridge
        pluginRoot: Qt.resolvedUrl(".").toString().replace(/^file:\/\//, "").replace(/\/$/, "")
        onReceived: function(action, result) { editor.accept(action, result) }
        onFailed: function(message) { editor.message = message }
    }
    KeyboardPanel {
        id: panel
        anchorItem: button; owner: root; bar: root.bar
        contentWidth: fittedContentWidth(760)
        contentHeight: fittedContentHeight(850, 900)
        Tuner.Editor {
            id: editor
            anchors.fill: parent
            panelOpen: panel.open
            busy: bridge.busy
            color: Commons.Color.background
            accent: Commons.Color.accent
            onRequest: function(action, args) { bridge.request(action, args) }
            Keys.onEscapePressed: root.close()
        }
    }
}
