import QtQuick
import Quickshell
import Quickshell.Hyprland

FloatingWindow {
    id: window
    property alias editor: editor
    property color accent: "#93c5aa"
    title: "WebcamTuner"
    visible: false
    implicitWidth: Math.min(780, screen ? screen.width - 80 : 780)
    implicitHeight: Math.min(900, screen ? screen.height - 80 : 900)
    minimumSize: Qt.size(540, 460)
    color: "#171c24"

    function openEditor() {
        visible = true
        if (!editor.document) bridge.request("read", [])
    }
    function closeEditor() { editor.previewOn = false; visible = false }

    onVisibleChanged: {
        if (visible) floatWindow.restart()
        else editor.previewOn = false
    }
    Timer {
        id: floatWindow
        interval: 100
        // Only this window is floated; desktop-wide window rules are unnecessary.
        onTriggered: {
            if (!window.visible || Quickshell.env("QT_QPA_PLATFORM").indexOf("offscreen") !== -1) return
            Hyprland.dispatch('(function() local w=hl.get_window("title:^WebcamTuner$"); if w then return hl.dsp.window.float({action="set", window=w}) end; return hl.dsp.no_op() end)()')
        }
    }
    Bridge {
        id: bridge
        onReceived: function(action, result) { editor.accept(action, result) }
        onFailed: function(message) { editor.fail(message) }
    }
    Editor {
        id: editor
        anchors.fill: parent
        panelOpen: window.visible
        busy: bridge.busy
        color: window.color
        accent: window.accent
        onRequest: function(action, args) { bridge.request(action, args) }
        onMoveRequested: window.startSystemMove()
        Keys.onEscapePressed: window.closeEditor()
    }
}
