import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "BuildInfo.js" as BuildInfo

ScrollView {
    id: root
    clip: true
    padding: 22
    contentWidth: availableWidth
    contentHeight: aboutContent.implicitHeight
    ScrollBar.vertical: VisibleScrollBar { policy: root.contentHeight > root.availableHeight ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff }
    ColumnLayout {
        id: aboutContent
        height: implicitHeight
        width: root.availableWidth
        spacing: 16
        component Plain: Text { color: "#e9ecef"; textFormat: Text.PlainText; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 14 }
        RowLayout {
            WebcamIcon { ink: "#93c5aa"; Layout.preferredWidth: 32; Layout.preferredHeight: 32 }
            Plain { text: "WebcamTuner"; font.pixelSize: 24; font.bold: true }
        }
        Plain { objectName: "pluginVersion"; text: qsTr("Version %1").arg(BuildInfo.version); color: "#93c5aa" }
        Plain { text: qsTr("By Jason Benjamin Ziegler Sr") }
        Plain { text: qsTr("Persistent camera framing and locally processed backgrounds for the Omarchy desktop.") }
        Plain { text: qsTr("How it works"); font.bold: true; font.pixelSize: 18 }
        Plain { text: qsTr("The Omarchy plugin is the control panel. It remembers your camera and saves profiles with framing, mirror and background choices in your home directory.") }
        Plain { text: qsTr("On first use, Setup checks the controller, processing runtime, bundled model, desktop video components and PipeWire session. Prepare WebcamTuner creates missing components in your home directory with visible progress; Repair local runtime builds a fresh environment while preserving profiles, backgrounds and snapshots. Preparation itself does not open a camera.") }
        Plain { text: qsTr("A local worker captures the camera and uses person matting to blend you with a chosen image or blurred background. Snapshot saves that look at the camera crop’s full resolution in the local snapshot folder shown in Setup, with an optional OS screenshot mirror. Camera images are processed on this computer. When enabled in Setup, the NVIDIA GPU accelerates person matting; the preview reports measured FPS and its active backend.") }
        Plain { text: qsTr("Start camera output runs one persistent user-session capture/compositor and publishes its background, camera crop and label through PipeWire. The editor subscribes to that same producer. Closing the controls leaves output running; Stop output releases the camera. The Test tab reads published pixels through independent PipeWire and V4L2 consumers.") }
        Plain { text: qsTr("The optional user-only Zoom adapter exposes PipeWire cameras to native Zoom through V4L2. Setup downloads and verifies the matching signed library into your home directory and changes only your user Zoom launcher. Restart Zoom once after enabling it. The normal launcher can be restored in Setup.") }
        Plain { text: qsTr("Why no sudo is needed"); font.bold: true; font.pixelSize: 18 }
        Plain { text: qsTr("The panel, worker, settings and output service belong to your signed-in user. They use the desktop’s existing PipeWire session and camera access. WebcamTuner does not install a kernel camera driver, create a /dev/video device, or change system-wide configuration, so its setup does not require administrator privileges.") }
        Plain { text: qsTr("Current limits"); font.bold: true; font.pixelSize: 18 }
        Plain { text: qsTr("Output is 1280 × 720 with a nominal 30 fps format; camera capture keeps its negotiated resolution. Test reports the rate actually received. Native Zoom rendering is verified on the development host. Teams, Meet/Chat and concurrent-app checks remain pending. Processing speed varies, and BRIO 4K with effects does not yet meet the requested 24/30 fresh FPS. One successful readback does not establish universal compatibility.") }
        Plain { text: qsTr("WebcamTuner does not bypass browser camera permissions, camera privacy switches or missing desktop dependencies. It does not upload camera images or backgrounds, process your microphone, or join meetings for you.") }
        Plain { text: qsTr("Source and licensing"); font.bold: true; font.pixelSize: 18 }
        Plain { text: qsTr("Application source: Apache License 2.0. The bundled Robust Video Matting model is separately licensed under GPL-3.0.") }
        Button { text: qsTr("Source on GitHub"); onClicked: Qt.openUrlExternally("https://github.com/zigmoo/webcamtuner") }
        Plain { text: "github.com/zigmoo/webcamtuner"; color: "#93c5aa" }
    }
}
