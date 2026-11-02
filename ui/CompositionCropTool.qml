import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    property string target: "camera"
    property var cameraCrop: ({zoom:1,centerX:.5,centerY:.5})
    property var backgroundCrop: ({zoom:1,centerX:.5,centerY:.5})
    property bool mirror: true
    property bool cameraActive: false
    property bool backgroundAvailable: false
    property bool backgroundLocked: false
    property url cameraSource
    property url backgroundSource
    property url compositionSource
    property var labelOverlay: ({enabled:false})
    property string feedback: ""
    readonly property bool sourcePreviewRequested: cropDialog.visible && target === "camera"
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
        Layout.fillWidth: true
        RadioButton { objectName: "cropCamera"; text: qsTr("Crop camera"); checked: root.target === "camera"; onClicked: root.target = "camera" }
        RadioButton { objectName: "cropBackground"; text: qsTr("Crop background"); checked: root.target === "background"; enabled: root.backgroundAvailable; onClicked: root.target = "background" }
        Item { Layout.fillWidth: true }
    }
    RowLayout {
        Layout.fillWidth: true
        enabled: root.target === "camera" || (root.backgroundAvailable && !root.backgroundLocked)
        Slider { objectName: "zoomSlider"; Layout.fillWidth: true; from:0; to:Math.log(root.maximumZoom)/Math.LN2; value:Math.log(root.selectedCrop.zoom)/Math.LN2; onMoved:root.changeZoom(Math.pow(2,value)); Accessible.name: root.target === "camera" ? qsTr("Camera crop size") : qsTr("Background crop size") }
        Label { text: root.selectedCrop.zoom.toFixed(2) + "×"; color: "#e9ecef"; Layout.preferredWidth: 45 }
        Button { objectName: "editSelectedCrop"; text: qsTr("Edit crop…"); onClicked: root.openEditor() }
        Button { text: qsTr("Reset crop"); onClicked: root.edit({zoom:1,centerX:.5,centerY:.5}) }
    }
    Label { visible: root.target === "background" && root.backgroundLocked; text: qsTr("Background crop is locked. Unlock it in Background to edit."); wrapMode: Text.WordWrap; color: "#a9b4c1"; Layout.fillWidth: true }
    Dialog {
        id: cropDialog
        objectName: "compositionCropDialog"
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.max(300, Math.min(1400,parent.width-32))
        height: Math.max(280,parent.height-48)
        title: root.target === "camera" ? qsTr("Crop camera · 16:9") : qsTr("Crop background · 16:9")
        modal: true
        standardButtons: Dialog.Close
        contentItem: ColumnLayout {
            spacing: 10
            Label { text: qsTr("Move the selection or drag an edge/corner to resize. Shaded areas are excluded. Changes appear in the compositor and save automatically."); wrapMode: Text.WordWrap; color: "#e9ecef"; Layout.fillWidth: true }
            GridLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                columns: width >= 720 ? 2 : 1
                CropCanvas {
                    objectName: "sharedCropCanvas"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 800
                    imageSource: root.target === "camera" ? root.cameraSource : root.backgroundSource
                    crop: root.target === "camera" ? ({zoom:root.cameraCrop.zoom,centerX:root.mirror?1-root.cameraCrop.centerX:root.cameraCrop.centerX,centerY:root.cameraCrop.centerY}) : root.backgroundCrop
                    maximumZoom: root.maximumZoom
                    locked: root.target === "background" && root.backgroundLocked
                    loadingText: root.target!=="camera"?qsTr("Loading image…"):root.cameraActive?qsTr("Waiting for live camera frames…"):qsTr("Start Preview camera to crop the live source")
                    onEdited: function(value) {
                        if (root.target === "camera" && root.mirror) value = {zoom:value.zoom,centerX:1-value.centerX,centerY:value.centerY}
                        root.edit(value)
                    }
                }
                ColumnLayout {
                    Layout.preferredWidth: 260
                    Layout.fillWidth: parent.columns === 1
                    Layout.alignment: Qt.AlignTop
                    Label { text: qsTr("Compositor preview"); color:"#e9ecef"; font.bold:true }
                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: parent.parent.columns === 1 ? 100 : width * 9 / 16
                        clip:true
                        Image {
                            id:croppedBackdrop
                            visible:root.compositionSource.toString()==="" && root.backgroundAvailable
                            source:root.backgroundSource
                            asynchronous:true;autoTransform:true
                            property real cover:implicitWidth>0&&implicitHeight>0?Math.max(parent.width/implicitWidth,parent.height/implicitHeight)*root.backgroundCrop.zoom:1
                            width:implicitWidth*cover;height:implicitHeight*cover
                            x:parent.width/2-root.backgroundCrop.centerX*width;y:parent.height/2-root.backgroundCrop.centerY*height
                        }
                        PreviewFrame { anchors.fill:parent; source:root.compositionSource }
                        BackgroundLabelOverlay { anchors.fill:parent; overlay:root.labelOverlay }
                    }
                }
            }
            Label { text: root.feedback || qsTr("Changes save automatically"); color:"#93c5aa"; wrapMode: Text.WordWrap; Layout.fillWidth:true }
        }
    }
}
