import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Pane {
    id: root
    default property alias body: content.data
    property alias headerActions: actions.data
    property string title: ""
    property string hint: ""
    property string headerObjectName: ""
    property bool expanded: false
    readonly property real collapsedHeight: Math.max(header.implicitHeight, actions.implicitHeight) + topPadding + bottomPadding

    padding: 8
    topPadding: 4
    bottomPadding: 4
    background: Rectangle {
        color: root.palette.alternateBase
        border.color: root.palette.mid
        radius: 5
    }
    contentItem: ColumnLayout {
        spacing: 8
        RowLayout {
            Layout.fillWidth: true
            Button {
                id: header
                objectName: root.headerObjectName
                Layout.fillWidth: true
                topPadding: 2
                bottomPadding: 2
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: caption.truncated ? root.title + "\n" + root.hint : root.hint
                text: (root.expanded ? "▾  " : "▸  ") + root.title
                Accessible.name: root.title
                Accessible.description: root.expanded ? qsTr("Expanded") : qsTr("Collapsed")
                onClicked: root.expanded = !root.expanded
                background: Rectangle {
                    color: header.down ? root.palette.midlight : header.hovered ? root.palette.base : "transparent"
                    border.color: header.visualFocus || (header.activeFocus && header.hovered)
                        ? root.palette.link : "transparent"
                    radius: 3
                }
                contentItem: Text {
                    id: caption
                    elide: Text.ElideRight
                    text: header.text
                    textFormat: Text.PlainText
                    color: root.palette.windowText
                    font.pixelSize: 14
                    font.bold: true
                    verticalAlignment: Text.AlignVCenter
                }
            }
            RowLayout {
                id: actions
                visible: children.length > 0
            }
        }
        ColumnLayout {
            id: content
            Layout.fillWidth: true
            spacing: 8
            visible: root.expanded
        }
    }
}
