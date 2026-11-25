import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    property string text: ""
    property string dragObjectName: ""
    property string hint: qsTr("Drag to move. Arrow keys move a little; Shift+arrows move farther.")
    property color accent: palette.link
    property bool selected: false
    readonly property bool hovered: dragArea.containsMouse
    readonly property bool dragging: dragArea.pressed
    signal movementStarted()
    signal movementRequested(real dx, real dy)
    signal movementFinished()
    implicitWidth: caption.implicitWidth + 40
    implicitHeight: 36
    radius: 4
    color: dragArea.pressed ? root.palette.midlight : dragArea.containsMouse || selected ? root.palette.midlight : root.palette.alternateBase
    border.color: activeFocus || dragArea.pressed || selected ? accent : root.palette.mid
    opacity: enabled ? 1 : .45
    activeFocusOnTab: enabled
    Accessible.role: Accessible.Button
    Accessible.name: qsTr("Move %1").arg(text)
    Accessible.description: hint
    Repeater {
        model: 6
        Rectangle {
            required property int index
            x: 9 + (index % 2) * 5
            y: (root.height - 13) / 2 + Math.floor(index / 2) * 5
            width: 3; height: 3; radius: 1
            color: root.palette.windowText
        }
    }
    Text {
        id: caption
        x: 27; anchors.verticalCenter: parent.verticalCenter
        text: root.text
        textFormat: Text.PlainText
        color: root.palette.windowText
        font.pixelSize: 14
    }
    function nudge(dx, dy, event) {
        movementStarted()
        var step = event.modifiers & Qt.ShiftModifier ? 10 : 1
        movementRequested(dx * step, dy * step)
        movementFinished()
        event.accepted = true
    }
    Keys.onLeftPressed: function(event) { nudge(-1, 0, event) }
    Keys.onRightPressed: function(event) { nudge(1, 0, event) }
    Keys.onUpPressed: function(event) { nudge(0, -1, event) }
    Keys.onDownPressed: function(event) { nudge(0, 1, event) }
    MouseArea {
        id: dragArea
        objectName: root.dragObjectName
        anchors.fill: parent
        hoverEnabled: true
        preventStealing: true
        cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
        property point startPointer
        onPressed: function(mouse) {
            root.forceActiveFocus()
            startPointer = mapToItem(root.parent, mouse.x, mouse.y)
            root.movementStarted()
        }
        onPositionChanged: function(mouse) {
            if (!pressed) return
            var point = mapToItem(root.parent, mouse.x, mouse.y)
            root.movementRequested(point.x - startPointer.x, point.y - startPointer.y)
        }
        onReleased: root.movementFinished()
        onCanceled: root.movementFinished()
    }
    ToolTip.visible: dragArea.containsMouse && !dragArea.pressed
    ToolTip.delay: 600
    ToolTip.text: hint
}
