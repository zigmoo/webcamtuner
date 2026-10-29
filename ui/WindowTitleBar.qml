import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    implicitHeight: 42
    color: "#293747"
    property bool collapsed: false
    signal moveRequested()
    signal minimizeRequested()
    signal closeRequested()

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: 5
        spacing: 4
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            RowLayout {
                anchors.fill: parent
                spacing: 10
                Text {
                    text: "⠿"; color: "#d9e2ed"; font.pixelSize: 22
                    textFormat: Text.PlainText
                }
                Text {
                    text: "WebcamTuner"; color: "#f5f7fa"; font.pixelSize: 14; font.bold: true
                    textFormat: Text.PlainText; elide: Text.ElideRight; Layout.fillWidth: true
                }
            }
            MouseArea {
                objectName: "windowDragHandle"
                anchors.fill: parent
                cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                onPressed: root.moveRequested()
                onDoubleClicked: root.minimizeRequested()
            }
        }
        ToolButton {
            id: minimizeButton
            objectName: "windowMinimizeButton"
            Layout.preferredWidth: 32; Layout.preferredHeight: 32
            text: root.collapsed ? "⌄" : "−"
            Accessible.name: root.collapsed ? qsTr("Expand palette") : qsTr("Minimize window")
            ToolTip.visible: hovered
            ToolTip.text: Accessible.name
            contentItem: Text {
                text: minimizeButton.text; textFormat: Text.PlainText
                color: "#f5f7fa"; font.pixelSize: 21
                horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle { radius: 4; color: minimizeButton.hovered ? "#506075" : "transparent" }
            onClicked: root.minimizeRequested()
        }
        ToolButton {
            id: closeButton
            objectName: "windowCloseButton"
            Layout.preferredWidth: 32; Layout.preferredHeight: 32
            text: "×"
            Accessible.name: qsTr("Close window")
            ToolTip.visible: hovered
            ToolTip.text: Accessible.name
            contentItem: Text {
                text: closeButton.text; textFormat: Text.PlainText
                color: "#f5f7fa"; font.pixelSize: 23
                horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle { radius: 4; color: closeButton.hovered ? "#a83e48" : "transparent" }
            onClicked: root.closeRequested()
        }
    }
}
