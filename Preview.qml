import QtQuick
import Quickshell
import "ui" as Tuner

ShellRoot {
    property bool openedOnce: false
    Tuner.TunerWindow {
        id: window
        Component.onCompleted: openEditor()
    }
    Connections {
        target: window
        function onVisibleChanged() {
            if (window.visible) openedOnce = true
            else if (openedOnce) Qt.quit()
        }
    }
}
