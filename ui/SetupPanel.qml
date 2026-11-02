import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Io

Item {
    id: root
    objectName: "setupPanel"
    implicitHeight: setupContent.implicitHeight
    property var state: ({state: "unknown", published: false})
    property string feedback: qsTr("Checking your user session…")
    property var runtimeState: ({gpuEnabled: false, gpu: ""})
    property string runtimeMessage: ""
    property string snapshotsPath: ""
    property string osSnapshotsPath: ""
    property bool mirrorSnapshots: true
    property string snapshotMessage: ""
    property bool openSnapshotsRequested: false
    property string diagnostics: ""
    property var cameraSources: ({devices: [], pipewire: [], errors: [], output: {}})
    property string sourceMessage: ""
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
    onVisibleChanged: if (visible) { request("status"); refreshRuntime(); refreshSources() }
    Component.onCompleted: { request("status"); refreshRuntime(); refreshSources(); snapshotFolder.running = true }
    function refreshSources() { if (!sourceProcess.running) sourceProcess.running = true }
    Process {
        id: sourceProcess
        command: ["python3", root.pluginRoot + "/bin/output-control.py", "inventory"]
        stdout: StdioCollector { id: sourceOutput; waitForEnd: true }
        onExited: function(code) {
            try {
                var value = JSON.parse(sourceOutput.text)
                if (code !== 0 || !Array.isArray(value.devices) || !Array.isArray(value.pipewire)) throw new Error(value.message || "Could not read camera sources")
                root.cameraSources = value
                root.sourceMessage = value.errors.join("\n")
            } catch (e) { root.sourceMessage = String(e.message || e) }
        }
    }
    Timer { interval: 5000; repeat: true; running: root.visible; onTriggered: root.refreshSources() }
    function refreshRuntime() {
        if (runtimeProcess.running) return
        runtimeProcess.command = ["python3", pluginRoot + "/bin/runtime-control.py", "status"]
        runtimeProcess.running = true
    }
    Process {
        id: snapshotFolder
        command: ["python3", root.pluginRoot + "/bin/snapshot_files.py"]
        stdout: StdioCollector { id: folderOutput; waitForEnd: true }
        onExited: function(code) {
            try {
                var result = JSON.parse(folderOutput.text)
                if(code!==0 || typeof result.mirrorToOS!=="boolean")throw new Error(result.error||"Snapshot settings could not be read")
                root.snapshotsPath=result.directory;root.osSnapshotsPath=result.osDirectory;root.mirrorSnapshots=result.mirrorToOS
                root.snapshotMessage=qsTr("Snapshot settings saved and verified")
                if (code === 0 && root.openSnapshotsRequested) Qt.openUrlExternally("file://" + result.directory.split("/").map(encodeURIComponent).join("/"))
            } catch (e) { root.snapshotMessage=String(e.message||e) }
            root.openSnapshotsRequested = false
        }
    }
    Process {
        id: runtimeProcess
        stdout: StdioCollector { id: runtimeOutput; waitForEnd: true }
        stderr: StdioCollector { id: runtimeError; waitForEnd: true }
        onExited: function(code) {
            try {
                var value = JSON.parse(runtimeOutput.text)
                root.runtimeState = value
                root.runtimeMessage = value.message
            } catch (e) {
                root.runtimeMessage = code === 0 ? qsTr("GPU libraries verified. Restart camera preview to apply.") : String(runtimeError.text || runtimeOutput.text).slice(-700)
                if (code === 0) Qt.callLater(root.refreshRuntime)
            }
        }
    }
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
        id: setupContent
        width: root.width
        height: implicitHeight
        spacing: 16
        component Plain: Text { color: "#e9ecef"; textFormat: Text.PlainText; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 14 }
        Plain { text: qsTr("Preview performance"); font.pixelSize: 22; font.bold: true }
        Plain { text: root.runtimeState.gpu ? qsTr("Available GPU: ") + root.runtimeState.gpu : qsTr("No supported NVIDIA GPU detected. CPU processing is available.") }
        Plain { text: root.runtimeMessage }
        RowLayout {
            Button {
                text: runtimeProcess.running ? qsTr("Working…") : qsTr("Enable GPU acceleration")
                enabled: !runtimeProcess.running && !!root.runtimeState.gpu
                onClicked: {
                    root.runtimeMessage = qsTr("Preparing your local GPU runtime…")
                    runtimeProcess.command = ["bash", root.pluginRoot + "/bin/setup-gpu"]
                    runtimeProcess.running = true
                }
            }
            Button {
                text: qsTr("Use CPU")
                enabled: !runtimeProcess.running && root.runtimeState.gpuEnabled
                onClicked: {
                    runtimeProcess.command = ["python3", root.pluginRoot + "/bin/runtime-control.py", "cpu"]
                    runtimeProcess.running = true
                }
            }
        }
        Plain { text: qsTr("GPU setup downloads processing libraries into your home directory. Camera preview reports its measured fresh-frame rate and active processing backend. Restart preview after changing the runtime."); color: "#a9b4c1" }
        Plain { text: qsTr("Snapshots"); font.pixelSize: 18; font.bold: true }
        Plain { text: qsTr("Snapshot saves the full camera crop, label and effects in WebcamTuner’s local snapshot folder.") }
        TextField { Layout.fillWidth: true; readOnly: true; selectByMouse: true; text: root.snapshotsPath; Accessible.name: qsTr("Snapshot folder") }
        Button {
            text: qsTr("Open snapshot folder")
            enabled: !snapshotFolder.running
            onClicked: {
                root.openSnapshotsRequested = true
                snapshotFolder.command = ["python3", root.pluginRoot + "/bin/snapshot_files.py", "--create"]
                snapshotFolder.running = true
            }
        }
        CheckBox {
            objectName:"mirrorSnapshotsToOS"
            Layout.fillWidth:true
            text:snapshotFolder.running?qsTr("Saving snapshot setting…"):qsTr("Mirror snapshots to %1").arg(root.osSnapshotsPath||qsTr("Omarchy screenshots"))
            checked:root.mirrorSnapshots
            enabled:!snapshotFolder.running
            nextCheckState:function(){return checkState}
            contentItem:Text {text:parent.text;textFormat:Text.PlainText;wrapMode:Text.WordWrap;color:"#e9ecef";leftPadding:parent.indicator.width+parent.spacing;verticalAlignment:Text.AlignVCenter}
            onClicked:{snapshotFolder.command=["python3",root.pluginRoot+"/bin/snapshot_files.py","--mirror-os",String(!root.mirrorSnapshots)];snapshotFolder.running=true}
        }
        Plain { text:qsTr("Mirrored copies also appear at the front of Omasnap’s recent screenshot stack.");color:"#a9b4c1" }
        Plain { text:root.snapshotMessage;visible:text!=="";color:"#93c5aa" }
        Plain { text: qsTr("Camera sources and output"); font.pixelSize: 22; font.bold: true }
        Plain { text: qsTr("Meeting apps build their camera menus from a capture backend. These are the current V4L2 devices and PipeWire video sources in your session. An app’s permissions and backend determine which it can see.") }
        Button { objectName: "refreshCameraSources"; text: sourceProcess.running ? qsTr("Refreshing sources…") : qsTr("Refresh camera sources"); enabled: !sourceProcess.running; onClicked: root.refreshSources() }
        Plain { text: qsTr("V4L2 capture devices · /dev/video*"); font.bold: true }
        Plain { text: qsTr("No accessible V4L2 capture devices found."); visible: root.cameraSources.devices.length === 0; color: "#a9b4c1" }
        Repeater {
            model: root.cameraSources.devices
            delegate: Plain {
                required property var modelData
                text: modelData.name + " · " + modelData.path + (modelData.aliases.length ? "\n" + modelData.aliases.join("\n") : "")
                font.pixelSize: 13
            }
        }
        Plain { text: qsTr("PipeWire · Video/Source"); font.bold: true }
        Plain { text: qsTr("No PipeWire video sources are registered."); visible: root.cameraSources.pipewire.length === 0; color: "#a9b4c1" }
        Repeater {
            model: root.cameraSources.pipewire
            delegate: Plain {
                required property var modelData
                text: modelData.name + " · " + qsTr("node %1 · %2").arg(modelData.id).arg(modelData.state) + "\n" + modelData.node + (modelData.testOutput ? qsTr(" · WebcamTuner test pattern") : "")
                font.pixelSize: 13
                color: modelData.testOutput ? "#93c5aa" : "#e9ecef"
            }
        }
        Plain { objectName: "publishedOutputIdentity"; text: root.cameraSources.output.published ? qsTr("WebcamTuner output: PipeWire node %1 (%2). Synthetic test pattern only.").arg(root.cameraSources.output.nodeId).arg(root.cameraSources.output.node) : qsTr("WebcamTuner output is stopped. Starting the test registers PipeWire node webcamtuner.test."); color: "#93c5aa" }
        Plain { text: qsTr("Processed camera output is not connected yet. No WebcamTuner /dev/video device is created by this build."); color: "#a9b4c1" }
        Plain { text: root.sourceMessage; visible: text !== ""; color: "#edb17a" }
        Plain { text: qsTr("Camera output setup"); font.pixelSize: 22; font.bold: true }
        Plain { text: qsTr("Compatibility test · This build publishes a moving test pattern as WebcamTuner. Your camera and background are not connected to this output yet.") }
        Plain { text: qsTr("The test runs in your user session without administrator access. Closing this window leaves it running. Stop it here; it also stops automatically after 30 minutes."); color: "#a9b4c1" }
        RowLayout {
            Button { objectName: "startTestOutput"; text: controller.running ? qsTr("Working…") : qsTr("Start test camera"); enabled: !controller.running && !root.state.published; onClicked: root.request("start-test") }
            Button { objectName: "stopTestOutput"; text: qsTr("Stop test camera"); enabled: !controller.running; onClicked: root.request("stop-test") }
        }
        Plain { objectName: "outputStatus"; text: root.feedback; color: "#93c5aa" }
        Plain { text: qsTr("In your meeting app's camera settings, look for WebcamTuner. A moving ball and timer confirm reception. Seeing the source here does not confirm that a particular app supports it.") }
        Button { objectName: "nativeZoomLauncher"; text: qsTr("Open Zoom desktop"); enabled: !controller.running; onClicked: root.openApp("zoom") }
        Plain { text: qsTr("Zoom uses the installed Linux desktop app. Open its Video settings to check its actual camera menu."); color: "#a9b4c1" }
        Plain { text: qsTr("Optional compatible browser: these buttons open a separate Brave/Chromium profile with PipeWire camera support. Your normal browser settings stay unchanged. You may need to sign in again. Camera access still requires your permission.") }
        Flow {
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: ["Teams", "Meet", "Chat"]
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
