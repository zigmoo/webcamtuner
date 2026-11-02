import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    objectName: "previewFpsIndicator"
    property bool active: false
    property real measuredFps: -1
    property int decodedFrames: 0
    property double sampleStarted: 0
    visible: active
    color: "#cc101820"
    radius: 4
    implicitWidth: caption.implicitWidth + 16
    implicitHeight: caption.implicitHeight + 10
    function frameReady() { if (active) decodedFrames++ }
    onActiveChanged: {
        decodedFrames = 0
        measuredFps = -1
        sampleStarted = Date.now()
    }
    Timer {
        interval: 1000
        repeat: true
        running: root.active
        onTriggered: {
            var now = Date.now(), elapsed = (now - root.sampleStarted) / 1000
            if (elapsed > 0) root.measuredFps = root.decodedFrames / elapsed
            root.decodedFrames = 0
            root.sampleStarted = now
        }
    }
    Text {
        id: caption
        anchors.centerIn: parent
        color: "#e9ecef"
        font.pixelSize: 12
        font.bold: true
        text: root.measuredFps < 0 ? qsTr("FPS —") : qsTr("%1 FPS").arg(root.measuredFps.toFixed(1))
        Accessible.name: qsTr("Measured preview frame rate: %1").arg(text)
    }
}
