import QtQuick

Rectangle {
    id:root
    objectName:"previewBackendIndicator"
    property string provider:""
    readonly property string label: provider==="CUDAExecutionProvider"?qsTr("GPU · NVIDIA"):provider==="CPUExecutionProvider"?qsTr("CPU"):provider==="No matting"?qsTr("Original · effects off"):qsTr("Starting…")
    color:"#cc101820"
    radius:4
    implicitWidth:caption.implicitWidth+16
    implicitHeight:caption.implicitHeight+10
    Text { id:caption;anchors.centerIn:parent;text:root.label;textFormat:Text.PlainText;color:root.provider==="CUDAExecutionProvider"?"#93c5aa":"#e9ecef";font.pixelSize:12;font.bold:true }
}
