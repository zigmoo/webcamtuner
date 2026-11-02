import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Io

ScrollView {
    id: root
    clip: true
    contentWidth: availableWidth
    property var state: ({state: "unknown", published: false})
    property string feedback: qsTr("Checking your user session…")
    property string diagnostics: ""
    property string pluginRoot: Qt.resolvedUrl("../").toString().replace(/^file:\/\//, "").replace(/\/$/, "")
    function request(action) {
        if (controller.running) return
        controller.command = ["python3", pluginRoot + "/bin/output-control.py", action]
        controller.running = true
    }
    function openApp(app) {
        if (controller.running) return
        controller.command = ["python3", pluginRoot + "/bin/browser-control.py", app]
        controller.running = true
    }
    onVisibleChanged: if (visible) request("status")
    Component.onCompleted: request("status")
    Timer { interval: 2500; repeat: true; running: root.visible; onTriggered: root.request("status") }
    Process {
        id: controller
        stdout: StdioCollector { id: output; waitForEnd: true }
        stderr: StdioCollector { id: errors; waitForEnd: true }
        onExited: function(code) {
            try {
                var result = JSON.parse(output.text)
                if (result.state !== undefined) root.state = result
                root.feedback = result.message || result.state
                if (result.log !== undefined) root.diagnostics = result.log
            } catch (error) { root.feedback = String(errors.text || "Could not read output status").slice(0, 1000) }
        }
    }
    ColumnLayout {
        width: root.availableWidth
        spacing: 16
        component Plain: Text { color: "#e9ecef"; textFormat: Text.PlainText; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 14 }
        Plain { text: qsTr("Camera output setup"); font.pixelSize: 22; font.bold: true }
        Plain { text: qsTr("Compatibility test · This build publishes a moving test pattern as WebcamTuner. Your camera and background are not connected to this output yet.") }
        Plain { text: qsTr("The test runs in your user session without administrator access. Closing this window leaves it running. Stop it here; it also stops automatically after 30 minutes."); color: "#a9b4c1" }
        RowLayout {
            Button { objectName: "startTestOutput"; text: controller.running ? qsTr("Working…") : qsTr("Start test camera"); enabled: !controller.running && !root.state.published; onClicked: root.request("start-test") }
            Button { objectName: "stopTestOutput"; text: qsTr("Stop test camera"); enabled: !controller.running; onClicked: root.request("stop-test") }
        }
        Plain { objectName: "outputStatus"; text: root.feedback; color: "#93c5aa" }
        Plain { text: qsTr("In your meeting app's camera settings, look for WebcamTuner. A moving ball and timer confirm reception. Seeing the source here does not confirm that a particular app supports it.") }
        Plain { text: qsTr("Browser compatibility is under test. No browser preferences or existing launchers are changed automatically."); color: "#a9b4c1" }
        Plain { text: qsTr("Optional compatible browser: these buttons open a separate Brave/Chromium profile with PipeWire camera support. Your normal browser settings stay unchanged. You may need to sign in again. Camera access still requires your permission.") }
        Flow {
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: ["Zoom", "Teams", "Meet", "Chat"]
                Button {
                    required property string modelData
                    text: modelData
                    enabled: !controller.running
                    onClicked: root.openApp(modelData.toLowerCase())
                }
            }
        }
        Button { text: qsTr("Show diagnostics"); enabled: !controller.running; onClicked: root.request("diagnostics") }
        Plain { text: root.diagnostics; visible: text.length > 0; font.pixelSize: 12 }
    }
}
