import QtQuick
import Quickshell
import Quickshell.Hyprland

FloatingWindow {
    id: window
    property alias editor: editor
    property alias titleBar: titlebar
    property color accent: "#93c5aa"
    property bool collapsed: false
    property bool restoringSize: false
    property int expandedWidth: Math.min(780, screen ? screen.width - 80 : 780)
    property int expandedHeight: Math.min(900, screen ? screen.height - 80 : 900)
    title: "WebcamTuner"
    visible: false
    implicitWidth: expandedWidth
    implicitHeight: expandedHeight
    minimumSize: Qt.size(540, collapsed ? 42 : restoringSize ? expandedHeight : 460)
    maximumSize: Qt.size(16777215, collapsed ? 42 : 16777215)
    color: "#171c24"
    onCollapsedChanged: {
        restoringSize = !collapsed
        resizePalette.restart()
        releaseSize.restart()
    }
    Timer { id: releaseSize; interval: 75; onTriggered: window.restoringSize = false }
    Timer {
        id: resizePalette
        interval: 0
        onTriggered: {
            // Apply geometry after the collapsed/expanded size limits settle.
            window.implicitWidth = window.expandedWidth
            window.implicitHeight = window.collapsed ? 42 : window.expandedHeight
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
            expandedWidth = width
            expandedHeight = height
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
