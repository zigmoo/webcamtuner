import QtQuick
import QtQuick.Controls

ToolButton {
    id: button
    property string kind: ""
    property bool showToolTip: true

    width: 20
    height: 20
    padding: 3
    hoverEnabled: true
    ToolTip.text: Accessible.name
    ToolTip.visible: showToolTip && hovered
    ToolTip.delay: 500

    contentItem: BackgroundActionIcon {
        kind: button.kind
        ink: button.enabled ? "#e9ecef" : "#7b8490"
    }
    background: Rectangle {
        radius: 3
        color: button.hovered ? "#40536b" : "#d0171c24"
    }
}
