import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    property bool locked: false
    property real maximumPreviewHeight: 240
    property url imageSource
    property var crop: ({zoom: 1, centerX: 0.5, centerY: 0.5})
    property string feedback: ""
    property var labelOverlay: ({enabled: false, opacity: 0.75, text: ""})
    function openEditor() { if (!locked) cropDialog.open() }
    function closeEditor() { cropDialog.close() }
    signal edited(var value)
    signal pageScrollRequested(real amount)
    function adjust(zoom, x, y) {
        if (locked) return
        zoom = Math.max(1, Math.min(32, zoom))
        var iw = backdrop.implicitWidth, ih = backdrop.implicitHeight
        if (iw <= 0 || ih <= 0) return
        var cover = Math.max(stage.width / iw, stage.height / ih) * zoom
        var ex = stage.width / (2 * iw * cover), ey = stage.height / (2 * ih * cover)
        edited({zoom: zoom, centerX: Math.max(ex, Math.min(1 - ex, x)), centerY: Math.max(ey, Math.min(1 - ey, y))})
    }
    Label { text: qsTr("Background crop"); textFormat: Text.PlainText; color: "#e9ecef"; font.bold: true }
    Label { text: root.locked ? qsTr("Crop is locked. Unlock this image in the gallery to edit it.") : qsTr("Edit crop to select an area of the full image. Drag the selection or its resize handles. Crops save automatically."); textFormat: Text.PlainText; wrapMode: Text.WordWrap; color: "#a9b4c1"; Layout.fillWidth: true }
    RowLayout {
        Layout.fillWidth: true
        enabled: !root.locked
        Button { objectName: "backgroundZoom"; text: qsTr("Edit crop…"); onClicked: root.openEditor() }
        Label { text: qsTr("16:9 · %1×").arg(root.crop.zoom.toFixed(2)); color: "#a9b4c1"; Layout.fillWidth: true }
        Button { text: qsTr("Reset crop"); onClicked: root.adjust(1, 0.5, 0.5) }
    }
    Item {
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(width * 9 / 16, root.maximumPreviewHeight)
        Rectangle {
        id: stage
        objectName: "backgroundPreviewStage"
        anchors.centerIn: parent
        width: Math.min(parent.width, parent.height * 16 / 9)
        height: width * 9 / 16
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
        BackgroundLabelOverlay { anchors.fill: parent; overlay: root.labelOverlay }
        MouseArea {
            objectName: "backgroundDragSurface"
            anchors.fill: parent
            preventStealing: true
            cursorShape: root.locked ? Qt.ArrowCursor : Qt.PointingHandCursor
            onClicked: root.openEditor()
            onWheel: function(wheel) {
                if (!(wheel.modifiers & Qt.ControlModifier)) {
                    root.pageScrollRequested(wheel.pixelDelta.y ? -wheel.pixelDelta.y : -wheel.angleDelta.y / 120 * 64)
                    wheel.accepted = true
                    return
                }
                root.adjust(root.crop.zoom * (wheel.angleDelta.y > 0 ? 1.1 : 1/1.1), root.crop.centerX, root.crop.centerY); wheel.accepted = true }
        }
    }
    }
    Dialog {
        id: cropDialog
        objectName: "backgroundCropDialog"
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.max(300, Math.min(1200, parent.width - 32))
        height: Math.max(280, parent.height - 48)
        title: qsTr("Crop background · 16:9")
        modal: true
        standardButtons: Dialog.Close
        contentItem: ColumnLayout {
            spacing: 10
            Label { text: qsTr("Drag inside the rectangle to move it. Drag a corner or edge to resize. Drag outside to select a new area. Shaded areas are excluded."); wrapMode: Text.WordWrap; color: "#e9ecef"; Layout.fillWidth: true }
            BackgroundCropCanvas {
                Layout.fillWidth: true
                Layout.fillHeight: true
                imageSource: root.imageSource
                crop: root.crop
                locked: root.locked
                onEdited: function(value) { root.edited(value) }
            }
            RowLayout {
                Layout.fillWidth: true
                Label { text: root.feedback || qsTr("Changes save automatically for this image"); color: "#93c5aa"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                Button { text: qsTr("Reset crop"); enabled: !root.locked; onClicked: root.adjust(1, 0.5, 0.5) }
            }
        }
    }
}
