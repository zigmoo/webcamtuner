import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    property alias layerActions: layerRow.data
    property Palette popupPalette: palette
    property string target: "camera"
    property var cameraCrop: ({zoom:1,centerX:.5,centerY:.5})
    property var backgroundCrop: ({zoom:1,centerX:.5,centerY:.5})
    property bool mirror: true
    property bool cameraActive: false
    property bool backgroundAvailable: false
    property bool backgroundLocked: false
    property url cameraSource
    property url backgroundSource
    property string error: ""
    readonly property url sourceImage: target === "camera" ? cameraSource : backgroundSource
    readonly property bool sourcePreviewRequested: cropDialog.visible && target === "camera"
    readonly property bool dragging: zoomSlider.pressed || cropCanvas.dragging
    readonly property var selectedCrop: target === "camera" ? cameraCrop : backgroundCrop
    readonly property real maximumZoom: target === "camera" ? 4 : 32
    signal cameraEdited(var value)
    signal backgroundEdited(var value)
    function edit(value) {
        if (target === "camera") cameraEdited(value)
        else if (!backgroundLocked && backgroundAvailable) backgroundEdited(value)
    }
    function changeZoom(value) {
        value = Math.max(1, Math.min(maximumZoom,value))
        var c = selectedCrop, x = c.centerX, y = c.centerY
        if (target === "camera") { var edge=.5/value; x=Math.max(edge,Math.min(1-edge,x)); y=Math.max(edge,Math.min(1-edge,y)) }
        edit({zoom:value,centerX:x,centerY:y})
    }
    function openEditor() { cropDialog.open() }
    function closeEditor() { cropDialog.close() }
    RowLayout {
        id: layerRow
        Layout.fillWidth: true
        Label { text: qsTr("Crop layer"); color: root.palette.windowText }
        RadioButton {
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("Crop or zoom the camera layer.")
            objectName: "cropCamera"
            text: qsTr("Camera")
            checked: root.target === "camera"
            onClicked: root.target = "camera"
        }
        RadioButton {
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("Crop or zoom the background image.")
            objectName: "cropBackground"
            text: qsTr("Background")
            checked: root.target === "background"
            enabled: root.backgroundAvailable
            onClicked: root.target = "background"
        }
    }
    RowLayout {
        Layout.fillWidth: true
        enabled: root.target === "camera" || (root.backgroundAvailable && !root.backgroundLocked)
        Slider { id: zoomSlider; objectName: "zoomSlider"; Layout.fillWidth: true; from:0; to:Math.log(root.maximumZoom)/Math.LN2; value:Math.log(root.selectedCrop.zoom)/Math.LN2; onMoved:root.changeZoom(Math.pow(2,value)); Accessible.name: root.target === "camera" ? qsTr("Camera crop size") : qsTr("Background crop size") }
        Label { text: root.selectedCrop.zoom.toFixed(2) + "×"; color: root.palette.windowText; Layout.preferredWidth: 45 }
        Button {
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("Open a larger view to adjust the selected crop.")
            objectName: "editSelectedCrop"
            text: qsTr("Edit crop…")
            onClicked: root.openEditor()
        }
        Button {
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("Restore the selected layer to its uncropped framing.")
            text: qsTr("Reset crop")
            onClicked: root.edit({zoom:1,centerX:.5,centerY:.5})
        }
    }
    Label { visible: root.target === "background" && root.backgroundLocked; text: qsTr("Background crop is locked. Unlock it in Background to edit."); wrapMode: Text.WordWrap; color: root.palette.placeholderText; Layout.fillWidth: true }
    HintedDialog {
        id: cropDialog
        sourcePalette: root.popupPalette
        objectName: "compositionCropDialog"
        width: parent ? Math.min(1400, Math.max(0, parent.width - 2 * margins)) : implicitWidth
        title: root.target === "camera" ? qsTr("Crop camera · 16:9") : qsTr("Crop background · 16:9")
        modal: true
        header: RowLayout {
            Label {
                Layout.fillWidth: true
                Layout.leftMargin: cropDialog.leftPadding
                text: cropDialog.title
                elide: Text.ElideRight
                font.bold: true
            }
            Button {
                objectName: "finishCropEditor"
                Layout.topMargin: 6
                Layout.rightMargin: cropDialog.rightPadding
                text: qsTr("Done")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: qsTr("Close the crop editor.")
                onClicked: cropDialog.close()
            }
        }
        contentItem: ScrollView {
            id: cropScroll
            implicitHeight: cropContent.implicitHeight
            contentHeight: cropContent.implicitHeight
            contentWidth: availableWidth
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ColumnLayout {
                id: cropContent
                width: cropScroll.availableWidth
                spacing: 8

                Label {
                    text: qsTr("Move the selection or drag its handles to resize. Shaded areas are excluded.")
                    wrapMode: Text.WordWrap
                    color: root.palette.windowText
                    Layout.fillWidth: true
                }
                Label {
                    visible: root.error !== ""
                    text: root.error
                    wrapMode: Text.WordWrap
                    color: root.palette.linkVisited
                    Layout.fillWidth: true
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: width >= 720 ? 2 : 1
                    columnSpacing: 16
                    rowSpacing: 10
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 800
                        Label {
                            objectName: "compositorPreviewTitle"
                            text: qsTr("Compositor Preview")
                            color: root.palette.windowText
                            font.bold: true
                        }
                        CropCanvas {
                            id: cropCanvas
                            objectName: "sharedCropCanvas"
                            Layout.fillWidth: true
                            Layout.preferredHeight: Math.min(Math.max(132, cropDialog.parent ? cropDialog.parent.height * 0.66 : 132),
                                Math.max(132, (width - 36) / frameAspect + 36))
                            imageSource: root.sourceImage
                            crop: root.target === "camera"
                                ? ({zoom: root.cameraCrop.zoom, centerX: root.mirror ? 1 - root.cameraCrop.centerX : root.cameraCrop.centerX, centerY: root.cameraCrop.centerY})
                                : root.backgroundCrop
                            maximumZoom: root.maximumZoom
                            locked: root.target === "background" && root.backgroundLocked
                            loadingText: root.target !== "camera" ? qsTr("Loading image…")
                                : root.cameraActive ? qsTr("Waiting for live camera frames…")
                                : qsTr("Start the camera preview to crop the live source.")
                            onEdited: function(value) {
                                if (root.target === "camera" && root.mirror)
                                    value = {zoom: value.zoom, centerX: 1 - value.centerX, centerY: value.centerY}
                                root.edit(value)
                            }
                        }
                    }
                    ColumnLayout {
                        Layout.preferredWidth: 260
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        Label {
                            objectName: "originalImageTitle"
                            text: qsTr("Original Image")
                            color: root.palette.windowText
                            font.bold: true
                        }
                        Image {
                            objectName: "cropOriginalImage"
                            Layout.fillWidth: true
                            Layout.preferredHeight: Math.min(150, implicitWidth > 0 ? width * implicitHeight / implicitWidth : width * 9 / 16)
                            source: root.sourceImage
                            asynchronous: true
                            autoTransform: true
                            fillMode: Image.PreserveAspectFit
                            horizontalAlignment: Image.AlignLeft
                        }
                    }
                }
            }
        }
    }
}
