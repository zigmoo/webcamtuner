import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ScrollView {
    id: root
    clip: true
    padding: 22
    contentWidth: availableWidth
    ColumnLayout {
        width: root.availableWidth
        spacing: 16
        component Plain: Text { color: "#e9ecef"; textFormat: Text.PlainText; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 14 }
        Plain { text: "WebcamTuner"; font.pixelSize: 24; font.bold: true }
        Plain { text: qsTr("By Jason Benjamin Ziegler Sr") }
        Plain { text: qsTr("Persistent camera framing and locally processed backgrounds for the Omarchy desktop.") }
        Plain { text: qsTr("Application source: Apache License 2.0. The bundled Robust Video Matting model is separately licensed under GPL-3.0.") }
        Button { text: qsTr("Source on GitHub"); onClicked: Qt.openUrlExternally("https://github.com/zigmoo/webcamtuner") }
        Plain { text: "github.com/zigmoo/webcamtuner"; color: "#93c5aa" }
    }
}
