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
            Item {
                objectName: "toolbarGrip"
                width: 10; height: 16
                anchors.verticalCenter: parent.verticalCenter
                Repeater {
                    model: 6
                    Rectangle {
                        required property int index
                        x: (index % 2) * 6; y: Math.floor(index / 2) * 6
                        width: 4; height: 4; radius: 2; color: "#d9e2ed"
                    }
                }
            }
            FontMetrics { id: titleMetrics; font: title.font }
            Text {
                id: title
                objectName: "toolbarTitle"
                x: 22; width: parent.width - 22
                // Center the visible lettering rather than the font's line box.
                y: (parent.height - titleMetrics.tightBoundingRect(text).height) / 2
                    - baselineOffset - titleMetrics.tightBoundingRect(text).y
                text: "WebcamTuner"; color: "#f5f7fa"; font.pixelSize: 14; font.bold: true
                textFormat: Text.PlainText; elide: Text.ElideRight
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
            Layout.alignment: Qt.AlignVCenter
            padding: 0; topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
            text: root.collapsed ? "⌄" : "−"
            Accessible.name: root.collapsed ? qsTr("Expand palette") : qsTr("Minimize window")
            ToolTip.visible: hovered
            ToolTip.text: Accessible.name
            contentItem: Item {
                Rectangle { visible: !root.collapsed; anchors.centerIn: parent; width: 12; height: 2; color: "#f5f7fa" }
                Item {
                    visible: root.collapsed; anchors.centerIn: parent; width: 14; height: 14
                    Rectangle { anchors.centerIn: parent; anchors.horizontalCenterOffset: -2.5; width: 8; height: 2; rotation: 45; color: "#f5f7fa" }
                    Rectangle { anchors.centerIn: parent; anchors.horizontalCenterOffset: 2.5; width: 8; height: 2; rotation: -45; color: "#f5f7fa" }
                }
            }
            background: Rectangle { radius: 4; color: minimizeButton.hovered ? "#506075" : "transparent" }
            onClicked: root.minimizeRequested()
        }
        ToolButton {
            id: closeButton
            objectName: "windowCloseButton"
            Layout.preferredWidth: 32; Layout.preferredHeight: 32
            Layout.alignment: Qt.AlignVCenter
            padding: 0; topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
            text: "×"
            Accessible.name: qsTr("Close window")
            ToolTip.visible: hovered
            ToolTip.text: Accessible.name
            contentItem: Item {
                Rectangle { anchors.centerIn: parent; width: 14; height: 2; rotation: 45; color: "#f5f7fa" }
                Rectangle { anchors.centerIn: parent; width: 14; height: 2; rotation: -45; color: "#f5f7fa" }
            }
            background: Rectangle { radius: 4; color: closeButton.hovered ? "#a83e48" : "transparent" }
            onClicked: root.closeRequested()
        }
    }
}
