import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ScrollView {
    id: root
    clip: true
    padding: 22
    contentWidth: availableWidth
    ScrollBar.vertical: ScrollBar { policy: root.contentHeight > root.availableHeight ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff }
    ColumnLayout {
        width: root.availableWidth
        spacing: 16
        component Plain: Text { color: "#e9ecef"; textFormat: Text.PlainText; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 14 }
        RowLayout {
            WebcamIcon { ink: "#93c5aa"; Layout.preferredWidth: 32; Layout.preferredHeight: 32 }
            Plain { text: "WebcamTuner"; font.pixelSize: 24; font.bold: true }
        }
        Plain { text: qsTr("By Jason Benjamin Ziegler Sr") }
        Plain { text: qsTr("Persistent camera framing and locally processed backgrounds for the Omarchy desktop.") }
        Plain { text: qsTr("How it works"); font.bold: true; font.pixelSize: 18 }
        Plain { text: qsTr("The Omarchy plugin is the control panel. It remembers your camera and saves profiles with framing, mirror and background choices in your home directory.") }
        Plain { text: qsTr("A separate local worker captures the camera and uses person matting to blend you with a chosen image or blurred background. The Camera tab shows that processed preview. Snapshot saves the same look at the camera crop’s full resolution in your Pictures/WebcamTuner folder. Camera images are processed on this computer. When enabled in Setup, the NVIDIA GPU accelerates person matting; the preview reports measured FPS and its active backend.") }
        Plain { text: qsTr("A separate user-session service publishes a camera source through PipeWire, the desktop media system. Meeting apps can discover it through a supported browser camera backend and normal camera permissions. Closing the controls leaves explicitly started test output running.") }
        Plain { text: qsTr("Why no sudo is needed"); font.bold: true; font.pixelSize: 18 }
        Plain { text: qsTr("The panel, worker, settings and output service belong to your signed-in user. They use the desktop’s existing PipeWire session and camera access. WebcamTuner does not install a kernel camera driver, create a /dev/video device, or change system-wide configuration, so its setup does not require administrator privileges.") }
        Plain { text: qsTr("Current limits"); font.bold: true; font.pixelSize: 18 }
        Plain { text: qsTr("This build publishes a moving test pattern. The processed camera and selected background currently appear only in the preview; connecting them to meeting-app output is still being built. Zoom, Teams and Meet/Chat compatibility must be verified in each app. A native app that only accepts V4L2 devices may not see the PipeWire source.") }
        Plain { text: qsTr("WebcamTuner does not bypass browser camera permissions, camera privacy switches or missing desktop dependencies. It does not upload camera images or backgrounds, process your microphone, or join meetings for you.") }
        Plain { text: qsTr("Source and licensing"); font.bold: true; font.pixelSize: 18 }
        Plain { text: qsTr("Application source: Apache License 2.0. The bundled Robust Video Matting model is separately licensed under GPL-3.0.") }
        Button { text: qsTr("Source on GitHub"); onClicked: Qt.openUrlExternally("https://github.com/zigmoo/webcamtuner") }
        Plain { text: "github.com/zigmoo/webcamtuner"; color: "#93c5aa" }
    }
}
