import QtQuick
import QtQuick.Controls

ScrollBar {
    id: control
    property color ink: palette.link
    implicitWidth: 12
    minimumSize: 0.08
    active: true
    background: Rectangle { color: control.palette.alternateBase; radius: 6 }
    contentItem: Rectangle {
        implicitWidth: 8
        implicitHeight: 24
        color: control.pressed ? control.palette.windowText : control.ink
        radius: 5
    }
}
