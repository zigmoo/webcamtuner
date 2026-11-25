import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Io

Item {
    id: root
    property Palette popupPalette: palette
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
    property var outputControl: null
    property var bootstrapControl: null
    required property int interfaceScalePercent
    required property int minimumInterfaceScale
    required property int maximumInterfaceScale
    required property int interfaceScaleStep
    signal interfaceScaleRequested(int percent)
    property bool showRemotesTab: false
    signal remotesTabVisibilityRequested(bool show)
    readonly property bool setupBusy: bootstrapControl!==null&&bootstrapControl.busy
    readonly property bool canPrepare:!setupBusy&&!(outputControl&&(outputControl.published||outputControl.busy||(outputControl.state&&outputControl.state.serviceActive)))
    Connections {target:root.bootstrapControl;ignoreUnknownSignals:true;function onRefreshed(){root.refreshRuntime()}}
    property string pluginRoot: Qt.resolvedUrl("../").toString().replace(/^file:\/\//, "").replace(/\/$/, "")
    function request(action) {
        if (controller.running) return
        controller.command = ["python3", pluginRoot + "/bin/output-control.py", action]
        controller.running = true
    }
    function openApp(app, restart) {
        if (controller.running) return
        controller.command = ["python3", pluginRoot + "/bin/browser-control.py", app]
        if(restart)controller.command=controller.command.concat(["--restart"])
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
        component Plain: Text { color: root.palette.windowText; textFormat: Text.PlainText; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 14 }
        RowLayout {
            Layout.fillWidth: true
            Plain { text: qsTr("Interface scale") }
            SpinBox {
                objectName: "interfaceScaleSpinner"
                from: root.minimumInterfaceScale
                to: root.maximumInterfaceScale
                stepSize: root.interfaceScaleStep
                value: root.interfaceScalePercent
                Accessible.name: qsTr("Interface scale")
                textFromValue: function(value, locale) { return qsTr("%1%").arg(Number(value).toLocaleString(locale, 'f', 0)) }
                onValueModified: root.interfaceScaleRequested(value)
            }
        }
        Plain { text:qsTr("Set up WebcamTuner");font.pixelSize:22;font.bold:true }
        Plain { text:qsTr("Prepare the controller and local processing libraries here. Setup downloads into your home directory; it does not ask for sudo, install a kernel driver or change Omarchy defaults. It does not start your camera.") }
        Repeater {
            model:root.bootstrapControl?root.bootstrapControl.state.checks:[]
            delegate:Plain {
                required property var modelData
                text:(modelData.ready?"✓  ":"○  ")+modelData.label+(modelData.detail?"\n"+modelData.detail:"")
                color:modelData.ready?root.palette.link:root.palette.linkVisited
            }
        }
        Flow {
            Layout.fillWidth:true;spacing:8
            Button {
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: qsTr("Install or prepare the components WebcamTuner needs in your home directory.")
                objectName:"prepareWebcamTuner"
                text:root.setupBusy?qsTr("Working…"):qsTr("Prepare WebcamTuner")
                enabled:root.bootstrapControl!==null&&root.canPrepare
                onClicked:root.bootstrapControl.run("prepare")
            }
            Button {
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: qsTr("Check that the runtime and desktop camera components are ready.")
                objectName:"checkWebcamTuner"
                text:qsTr("Check readiness")
                enabled:root.bootstrapControl!==null&&!root.setupBusy
                onClicked:root.bootstrapControl.check()
            }
            Button {
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: qsTr("Rebuild the local runtime while keeping your saved data.")
                objectName:"repairWebcamTuner"
                text:qsTr("Repair local runtime")
                enabled:root.bootstrapControl!==null&&root.canPrepare
                onClicked:root.bootstrapControl.run("repair")
            }
        }
        Plain {text:root.bootstrapControl?root.bootstrapControl.error||root.bootstrapControl.message:"";color:root.bootstrapControl&&root.bootstrapControl.error?root.palette.linkVisited:root.palette.link}
        Plain {text:qsTr("Stop output before preparing or repairing libraries. Your profiles, backgrounds and snapshots are kept.");visible:!root.canPrepare&&!root.setupBusy;color:root.palette.placeholderText}
        Plain {text:root.bootstrapControl&&root.bootstrapControl.state.directory?qsTr("Local files: %1").arg(root.bootstrapControl.state.directory):"";visible:text!=="";color:root.palette.placeholderText}
        Plain { text: qsTr("Preview performance"); font.pixelSize: 22; font.bold: true }
        Plain { text: root.runtimeState.gpu ? qsTr("Available GPU: ") + root.runtimeState.gpu : qsTr("No supported NVIDIA GPU detected. CPU processing is available.") }
        Plain { text: root.runtimeMessage }
        RowLayout {
            Button {
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: qsTr("Prepare GPU processing for a supported NVIDIA card.")
                text: runtimeProcess.running ? qsTr("Working…") : qsTr("Enable GPU acceleration")
                enabled: root.canPrepare && !runtimeProcess.running && !!root.runtimeState.gpu && root.bootstrapControl!==null
                onClicked: {
                    root.bootstrapControl.run("gpu")
                }
            }
            Button {
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: qsTr("Use the CPU for camera effects.")
                text: qsTr("Use CPU")
                enabled: root.canPrepare && !runtimeProcess.running && root.runtimeState.gpuEnabled
                onClicked: {
                    runtimeProcess.command = ["python3", root.pluginRoot + "/bin/runtime-control.py", "cpu"]
                    runtimeProcess.running = true
                }
            }
        }
        Plain { text: qsTr("GPU setup downloads processing libraries into your home directory. Camera preview reports its measured fresh-frame rate and active processing backend. Restart preview after changing the runtime."); color: root.palette.placeholderText }
        Plain { text: qsTr("Snapshots"); font.pixelSize: 18; font.bold: true }
        Plain { text: qsTr("Snapshot saves the full camera crop, label and effects in WebcamTuner’s local snapshot folder.") }
        TextField { Layout.fillWidth: true; readOnly: true; selectByMouse: true; text: root.snapshotsPath; Accessible.name: qsTr("Snapshot folder") }
        Button {
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("Open the folder containing WebcamTuner snapshots.")
            text: qsTr("Open snapshot folder")
            enabled: !snapshotFolder.running
            onClicked: {
                root.openSnapshotsRequested = true
                snapshotFolder.command = ["python3", root.pluginRoot + "/bin/snapshot_files.py", "--create"]
                snapshotFolder.running = true
            }
        }
        CheckBox {
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("Keep a copy of each snapshot in the system screenshots folder.")
            objectName:"mirrorSnapshotsToOS"
            Layout.fillWidth:true
            text:snapshotFolder.running?qsTr("Saving snapshot setting…"):qsTr("Mirror snapshots to %1").arg(root.osSnapshotsPath||qsTr("Omarchy screenshots"))
            checked:root.mirrorSnapshots
            enabled:!snapshotFolder.running
            nextCheckState:function(){return checkState}
            contentItem:Text {text:parent.text;textFormat:Text.PlainText;wrapMode:Text.WordWrap;color:root.palette.windowText;leftPadding:parent.indicator.width+parent.spacing;verticalAlignment:Text.AlignVCenter}
            onClicked:{snapshotFolder.command=["python3",root.pluginRoot+"/bin/snapshot_files.py","--mirror-os",String(!root.mirrorSnapshots)];snapshotFolder.running=true}
        }
        Plain { text:qsTr("Copies also appear in Recent Images on supported Omasnap versions.");color:root.palette.placeholderText }
        Plain { text:root.snapshotMessage;visible:text!=="";color:root.palette.link }
        Plain { text: qsTr("Camera sources and output"); font.pixelSize: 22; font.bold: true }
        Plain { text: qsTr("Meeting apps build their camera menus from a capture backend. These are the current V4L2 devices and PipeWire video sources in your session. An app’s permissions and backend determine which it can see.") }
        Button {
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("Rescan local cameras and desktop video sources.")
            objectName: "refreshCameraSources"
            text: sourceProcess.running ? qsTr("Refreshing sources…") : qsTr("Refresh camera sources")
            enabled: !sourceProcess.running
            onClicked: root.refreshSources()
        }
        Plain { text: qsTr("V4L2 capture devices · /dev/video*"); font.bold: true }
        Plain { text: qsTr("No accessible V4L2 capture devices found."); visible: root.cameraSources.devices.length === 0; color: root.palette.placeholderText }
        Repeater {
            model: root.cameraSources.devices
            delegate: Plain {
                required property var modelData
                text: modelData.name + " · " + modelData.path + (modelData.aliases.length ? "\n" + modelData.aliases.join("\n") : "")
                font.pixelSize: 13
            }
        }
        Plain { text: qsTr("PipeWire · Video/Source"); font.bold: true }
        Plain { text: qsTr("No PipeWire video sources are registered."); visible: root.cameraSources.pipewire.length === 0; color: root.palette.placeholderText }
        Repeater {
            model: root.cameraSources.pipewire
            delegate: Plain {
                required property var modelData
                text: modelData.name + " · " + qsTr("node %1 · %2").arg(modelData.id).arg(modelData.state) + "\n" + modelData.node + (modelData.testOutput ? qsTr(" · WebcamTuner test pattern") : "")
                font.pixelSize: 13
                color: modelData.testOutput ? root.palette.link : root.palette.windowText
            }
        }
        Plain { objectName: "publishedOutputIdentity"; text: root.cameraSources.output.published ? qsTr("WebcamTuner output: PipeWire node %1 (%2) · %3").arg(root.cameraSources.output.nodeId).arg(root.cameraSources.output.node).arg(root.cameraSources.output.kind) : qsTr("WebcamTuner output is stopped."); color: root.palette.link }
        Plain { text: qsTr("The processed stream is published in your user PipeWire session. The Zoom adapter exposes these sources through V4L2 inside Zoom; it creates no system /dev/video device and requires no administrator access."); color: root.palette.placeholderText }
        Plain { text: root.sourceMessage; visible: text !== ""; color: root.palette.linkVisited }
        Plain { text: qsTr("Camera output setup"); font.pixelSize: 22; font.bold: true }
        Plain { text: qsTr("Publish your camera crop, background and label as WebcamTuner. Output uses one capture/compositor for the editor and other apps, and keeps running when this window closes. Stop output releases the camera.") }
        RowLayout {
            Button {
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: qsTr("Publish the processed camera for other apps.")
                objectName:"startProcessedOutput"
                text:root.outputControl&&root.outputControl.busy?qsTr("Working…"):qsTr("Start camera output")
                enabled:root.outputControl!==null&&!root.setupBusy&&(!root.bootstrapControl||root.bootstrapControl.ready)&&!root.outputControl.busy&&!root.outputControl.published&&!!root.outputControl.configuration&&!!root.outputControl.configuration.camera
                onClicked:root.outputControl.start()
            }
            Button {
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: qsTr("Stop publishing WebcamTuner and release the camera.")
                objectName:"stopProcessedOutput"
                text:qsTr("Stop output")
                enabled:root.outputControl!==null
                onClicked:root.outputControl.stop()
            }
        }
        Plain { text:root.outputControl?root.outputControl.feedback:"";color:root.palette.link;visible:text!=="" }
        Plain { text:qsTr("Output format: 1280 × 720, up to 30 fresh frames per second. Camera capture keeps its full negotiated resolution. The Camera tab shows the measured processing rate; a negotiated 30 fps format does not guarantee 30 distinct frames.");color:root.palette.placeholderText }
        Plain { text:qsTr("Native Zoom connection");font.pixelSize:18;font.bold:true }
        Plain { text:qsTr("Camera output automatically downloads and verifies a matching signed desktop camera adapter in your home directory, refreshing it after PipeWire updates. When native Zoom is installed, its user launcher is connected automatically. Already-running Zoom loads the adapter the next time you reopen it.") }
        Plain { text:root.outputControl?root.outputControl.adapterMessage:"";color:root.palette.link }
        RowLayout {
            Button {
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: qsTr("Rebuild the user-local camera adapter.")
                objectName:"enableZoomAdapter"
                text:root.outputControl&&root.outputControl.adapterPreparing?qsTr("Preparing adapter…"):qsTr("Repair camera adapter")
                enabled:root.outputControl!==null&&!root.outputControl.busy&&!root.outputControl.adapterPreparing
                onClicked:root.outputControl.prepareAdapter(false)
            }
            Button {
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: qsTr("Restore Zoom’s regular launcher.")
                text:qsTr("Use normal Zoom launcher")
                enabled:root.outputControl!==null&&!root.outputControl.busy&&!root.outputControl.adapterPreparing&&root.outputControl.adapter.enabled
                onClicked:root.outputControl.request("disable-zoom")
            }
            Button {
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: qsTr("Configure the Zoom launcher to load the WebcamTuner adapter.")
                text:qsTr("Connect Zoom launcher")
                visible:root.outputControl!==null&&root.outputControl.adapter.normalLauncher===true
                enabled:root.outputControl!==null&&!root.outputControl.busy&&!root.outputControl.adapterPreparing&&root.outputControl.adapter.zoomInstalled
                onClicked:root.outputControl.request("setup-zoom")
            }
        }
        Plain { text:root.outputControl&&root.outputControl.adapter.restartRequired?qsTr("Zoom is already running without the adapter. Quit Zoom completely and reopen it, or use Restart Zoom below."):root.outputControl&&root.outputControl.adapter.adapterLoaded?qsTr("The running Zoom process has the camera adapter loaded."):qsTr("Start camera output, then open Zoom and select WebcamTuner in its camera menu.");color:root.palette.placeholderText }
        Button {
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("Close and reopen Zoom so it can load the adapter.")
            objectName:"restartNativeZoom"
            text:qsTr("Restart Zoom to connect camera")
            enabled:root.outputControl!==null&&root.outputControl.adapter.enabled&&!controller.running
            onClicked:restartZoomDialog.open()
        }
        Plain { text: qsTr("Diagnostic test pattern"); font.pixelSize:18;font.bold:true }
        Plain { text: qsTr("This separate moving test pattern helps check transport without using a physical camera. Stop processed output before starting the diagnostic source.") }
        Plain { text: qsTr("The test runs in your user session without administrator access. Closing this window leaves it running. Stop it here; it also stops automatically after 30 minutes."); color: root.palette.placeholderText }
        RowLayout {
            Button {
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: qsTr("Publish a synthetic test pattern without using a physical camera.")
                objectName: "startTestOutput"
                text: controller.running ? qsTr("Working…") : qsTr("Start test camera")
                enabled: !controller.running && !root.state.published
                onClicked: root.request("start-test")
            }
            Button {
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: qsTr("Stop the synthetic test pattern.")
                objectName: "stopTestOutput"
                text: qsTr("Stop test camera")
                enabled: !controller.running
                onClicked: root.request("stop-test")
            }
        }
        Plain { objectName: "outputStatus"; text: root.feedback; color: root.palette.link }
        Plain { text: qsTr("In your meeting app's camera settings, look for WebcamTuner. A moving ball and timer confirm reception. Seeing the source here does not confirm that a particular app supports it.") }
        Button {
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("Open the installed Zoom desktop app.")
            objectName: "nativeZoomLauncher"
            text: qsTr("Open Zoom desktop")
            enabled: !controller.running
            onClicked: root.openApp("zoom")
        }
        Plain { text: qsTr("Zoom uses the installed Linux desktop app. Open its Video settings to check its actual camera menu."); color: root.palette.placeholderText }
        Plain { text: qsTr("Google Meet in your normal Brave/Chromium browser needs PipeWire camera support. Enable it here, then fully quit and reopen that browser. The camera must also be started in WebcamTuner; a preview alone is not shared output.") }
        Button {
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("Enable PipeWire camera support in the normal browser.")
            objectName: "enableBrowserCameraSupport"
            text: qsTr("Enable browser camera support")
            enabled: !controller.running
            onClicked: root.openApp("enable-browser-camera")
        }
        Plain { text: qsTr("Optional compatible browser: these buttons open a separate Brave/Chromium profile with PipeWire camera support. Your normal browser settings stay unchanged. You may need to sign in again. Camera access still requires your permission.") }
        Flow {
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: ["Teams", "Meet", "Chat"]
                Button {
                    hoverEnabled: true
                    ToolTip.visible: hovered
                    ToolTip.delay: 500
                    ToolTip.text: qsTr("Open %1 in the meeting browser.").arg(modelData)
                    required property string modelData
                    text: modelData
                    enabled: !controller.running
                    onClicked: root.openApp(modelData.toLowerCase())
                }
            }
        }
        Button {
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("Show detailed runtime and camera checks for troubleshooting.")
            text: qsTr("Show diagnostics")
            enabled: !controller.running
            onClicked: root.request("diagnostics")
        }
        Plain { text: root.diagnostics; visible: text.length > 0; font.pixelSize: 12 }

        Plain { text: qsTr("Tabs"); font.pixelSize: 18; font.bold: true }
        CheckBox {
            objectName: "showRemotesTab"
            text: qsTr("Show Remotes tab")
            checked: root.showRemotesTab
            nextCheckState: function() { return checkState }
            onClicked: root.remotesTabVisibilityRequested(!checked)
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("Show controls for finding and connecting to remote cameras.")
        }
    }
    HintedDialog {
        id:restartZoomDialog
        sourcePalette: root.popupPalette
        standardButtonHelp: ({ [Dialog.Ok]: qsTr("Close and reopen Zoom to load the camera adapter."), [Dialog.Cancel]: qsTr("Leave Zoom running.") })
        objectName: "restartZoomDialog"
        title:qsTr("Restart Zoom?")
        modal:true
        width: parent ? Math.min(440, Math.max(0, parent.width - 2 * margins)) : 440
        standardButtons:Dialog.Ok|Dialog.Cancel
        contentItem:Text {text:qsTr("This closes Zoom windows and leaves any active meeting. Restart only when you are ready to reconnect.");textFormat:Text.PlainText;wrapMode:Text.WordWrap;color:root.palette.windowText}
        onAccepted:root.openApp("zoom",true)
    }
}
