import QtQuick
import QtQuick.Controls

ScrollBar {
    id: control
    property color ink: "#93c5aa"
    implicitWidth: 12
    minimumSize: 0.08
    active: true
    background: Rectangle { color: "#303944"; radius: 6 }
    contentItem: Rectangle {
        implicitWidth: 8
        implicitHeight: 24
        color: control.pressed ? "#e9ecef" : control.ink
        radius: 5
    }
}
