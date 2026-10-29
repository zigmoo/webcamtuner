import QtQuick
import Quickshell
import Quickshell.Hyprland

FloatingWindow {
    id: window
    property alias editor: editor
    property alias titleBar: titlebar
    property color accent: "#93c5aa"
    property bool collapsed: false
    property int expandedWidth: Math.min(780, screen ? screen.width - 80 : 780)
    property int expandedHeight: Math.min(900, screen ? screen.height - 80 : 900)
    title: "WebcamTuner"
    visible: false
    implicitWidth: expandedWidth
    implicitHeight: expandedHeight
    minimumSize: Qt.size(540, collapsed ? 42 : 460)
    maximumSize: Qt.size(16777215, collapsed ? 42 : 16777215)
    color: "#171c24"
    onCollapsedChanged: resizePalette.restart()
    Timer {
        id: resizePalette
        interval: 50
        onTriggered: {
            // FloatingWindow preferences do not resize an already visible native window.
            window.implicitWidth = window.expandedWidth
            window.implicitHeight = window.collapsed ? 42 : window.expandedHeight
            if (!window.visible || Quickshell.env("QT_QPA_PLATFORM").indexOf("offscreen") !== -1) return
            Hyprland.dispatch('(function() local w=hl.get_window("title:^WebcamTuner$"); if w then return hl.dsp.window.resize({x='
                + window.expandedWidth + ', y=' + (window.collapsed ? 42 : window.expandedHeight)
                + ', relative=false, window=w}) end; return hl.dsp.no_op() end)()')
        }
    }

    function openEditor() {
        collapsed = false
        visible = true
        if (!editor.document) bridge.request("read", [])
    }
    function closeEditor() { editor.previewOn = false; visible = false }
    function toggleCollapse() {
        if (!collapsed) {
            expandedWidth = Math.max(540, width)
            expandedHeight = Math.max(460, height)
        }
        collapsed = !collapsed
    }

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
    WindowTitleBar {
        id: titlebar
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 42
        color: Qt.tint(window.color, "#305f83ab")
        collapsed: window.collapsed
        onMoveRequested: window.startSystemMove()
        onMinimizeRequested: window.toggleCollapse()
        onCloseRequested: window.closeEditor()
    }
    Editor {
        id: editor
        anchors.top: titlebar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        visible: !window.collapsed
        panelOpen: window.visible
        busy: bridge.busy
        color: window.color
        accent: window.accent
        onRequest: function(action, args) { bridge.request(action, args) }
        Keys.onEscapePressed: window.closeEditor()
    }
}
