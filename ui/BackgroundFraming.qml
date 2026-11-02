import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    property url imageSource
    property var crop: ({zoom: 1, centerX: 0.5, centerY: 0.5})
    signal edited(var value)
    function adjust(zoom, x, y) {
        zoom = Math.max(1, Math.min(4, zoom))
        var iw = backdrop.implicitWidth, ih = backdrop.implicitHeight
        if (iw <= 0 || ih <= 0) return
        var cover = Math.max(stage.width / iw, stage.height / ih) * zoom
        var ex = stage.width / (2 * iw * cover), ey = stage.height / (2 * ih * cover)
        edited({zoom: zoom, centerX: Math.max(ex, Math.min(1 - ex, x)), centerY: Math.max(ey, Math.min(1 - ey, y))})
    }
    Label { text: qsTr("Background framing"); textFormat: Text.PlainText; color: "#e9ecef"; font.bold: true }
    Rectangle {
        id: stage
        Layout.fillWidth: true
        Layout.preferredHeight: width * 9 / 16
        color: "#0e131b"
        clip: true
        Image {
            id: backdrop
            source: root.imageSource
            asynchronous: true
            fillMode: Image.PreserveAspectFit
            autoTransform: true
            sourceSize.width: 1280
            sourceSize.height: 1280
            property real cover: implicitWidth > 0 && implicitHeight > 0 ? Math.max(stage.width / implicitWidth, stage.height / implicitHeight) * root.crop.zoom : 1
            width: implicitWidth * cover
            height: implicitHeight * cover
            x: stage.width / 2 - root.crop.centerX * width
            y: stage.height / 2 - root.crop.centerY * height
        }
        MouseArea {
            anchors.fill: parent
            preventStealing: true
            cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
            property real startX; property real startY; property real centerX; property real centerY
            onPressed: function(mouse) { startX = mouse.x; startY = mouse.y; centerX = root.crop.centerX; centerY = root.crop.centerY }
            onPositionChanged: function(mouse) {
                if (pressed) root.adjust(root.crop.zoom, centerX - (mouse.x - startX) / backdrop.width, centerY - (mouse.y - startY) / backdrop.height)
            }
            onWheel: function(wheel) { root.adjust(root.crop.zoom + (wheel.angleDelta.y > 0 ? 0.1 : -0.1), root.crop.centerX, root.crop.centerY); wheel.accepted = true }
        }
    }
    Label { text: qsTr("Drag to choose the background area. Scroll or use Background zoom. Each image remembers its framing."); textFormat: Text.PlainText; wrapMode: Text.WordWrap; color: "#a9b4c1"; Layout.fillWidth: true }
    RowLayout {
        Layout.fillWidth: true
        Label { text: qsTr("Background zoom"); textFormat: Text.PlainText; color: "#e9ecef" }
        Slider { objectName: "backgroundZoom"; Layout.fillWidth: true; from: 1; to: 4; value: root.crop.zoom; onMoved: root.adjust(value, root.crop.centerX, root.crop.centerY) }
        Button { text: qsTr("Reset"); onClicked: root.adjust(1, 0.5, 0.5) }
    }
}
