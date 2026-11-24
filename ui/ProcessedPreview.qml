import QtQuick
import Quickshell.Io

Item {
    id: root
    property bool active: false
    property bool sharedOutput: false
    property bool adjustingBackground: false
    property int outputRevision: 0
    readonly property int effectiveGeneration: sharedOutput ? outputRevision : desiredGeneration
    property var configuration: ({})
    property string pluginRoot: Qt.resolvedUrl("../").toString().replace(/^file:\/\//, "").replace(/\/$/, "")
    property string frameUrl: ""
    property string sourceFrameUrl: ""
    property string labelBitmapUrl: ""
    property string labelBitmapKey: ""
    property int labelBitmapWidth: 0
    property int labelBitmapHeight: 0
    property string effect: ""
    property var format: ({})
    property int desiredGeneration: 0
    property int appliedGeneration: -1
    property bool snapshotPending: false
    property string snapshotRequestId: ""
    property bool starting: false
    property bool reconnecting: false
    property bool shuttingDown: false
    property string cameraSource: ""
    property int rejectedRevision: -1
    signal configurationRejected(string camera, string message)
    readonly property bool snapshotReady: active && frameUrl !== "" && !updateDelay.running && effectiveGeneration === appliedGeneration && !snapshotPending
    signal snapshotSaved(var result)
    signal snapshotFailed(string message)
    function takeSnapshot() {
        if (!snapshotReady) return
        snapshotRequestId = Date.now().toString() + "-" + Math.floor(Math.random() * 1000000).toString()
        snapshotPending = true
        process.write(JSON.stringify({operation: "snapshot", requestId: snapshotRequestId, expectedRevision: effectiveGeneration}) + "\n")
        snapshotTimeout.restart()
    }
    Timer {
        id: snapshotTimeout
        interval: 15000
        onTriggered: {
            root.snapshotPending = false
            root.snapshotFailed(qsTr("Snapshot took too long. Check your Pictures folder before trying again."))
        }
    }
    signal failed(string message)
    signal frameReceived(string mode)
    function activate() {
        if (active) {
            if(!configuration || !configuration.camera || !configuration.crop || !configuration.background || starting || process.running)return
            starting=true
            if (!reconnecting) {
                frameUrl = ""
                labelBitmapUrl = ""
                labelBitmapKey = ""
            }
            process.command = sharedOutput ? ["python3",pluginRoot+"/bin/stream-client.py"] : [pluginRoot + "/bin/preview-python", pluginRoot + "/bin/process_preview.py", "--ui-overlay", "--request", JSON.stringify(Object.assign({}, configuration, {configurationRevision: desiredGeneration}))]
            process.running = true
            firstFrameTimeout.restart()
        } else {
            starting=false
            reconnecting=false
            reconnectDelay.stop()
            firstFrameTimeout.stop()
            process.running = false
            frameUrl = ""
            sourceFrameUrl = ""
        }
    }
    onActiveChanged: activate()
    onConfigurationChanged: {
        desiredGeneration++
        if (active && !process.running && !starting && !reconnectDelay.running) activate()
        else if (!adjustingBackground || !updateDelay.running) updateDelay.restart()
    }
    Component.onDestruction: {root.shuttingDown=true;process.running=false}
    function streamFailed(message) {
        if (!active || shuttingDown) return
        if (!sharedOutput) {
            frameUrl = ""
            sourceFrameUrl = ""
            failed(message)
            return
        }
        if (reconnectDelay.running) return
        reconnecting = true
        starting = false
        appliedGeneration = -1
        sourceFrameUrl = ""
        firstFrameTimeout.stop()
        if (snapshotPending) {
            snapshotTimeout.stop()
            snapshotPending = false
            snapshotFailed(qsTr("The preview disconnected before confirming the snapshot."))
        }
        reconnectDelay.start()
        process.running = false
    }
    Timer {
        id: reconnectDelay
        interval: 600
        onTriggered: if (root.active && root.sharedOutput) root.activate()
    }
    Timer {
        id: firstFrameTimeout
        interval: root.sharedOutput ? 6000
            : root.configuration && String(root.configuration.camera).indexOf("sshcam:") === 0 ? 65000 : 15000
        onTriggered: root.streamFailed(qsTr("Camera did not deliver a preview."))
    }
    Timer {
        id: updateDelay
        interval: root.adjustingBackground ? 100 : 180
        onTriggered: if (process.running && root.configuration && !root.sharedOutput) process.write(JSON.stringify(Object.assign({}, root.configuration, {configurationRevision: root.desiredGeneration})) + "\n")
    }
    Process {
        id: process
        stdinEnabled: true
        stdout: SplitParser {
            onRead: function(line) {
                if (line.length > 1048576) { root.streamFailed("Preview frame exceeded its size limit"); return }
                try {
                    var value = JSON.parse(line)
                    if (value.snapshot || value.snapshotError) {
                        if (value.requestId === root.snapshotRequestId) {
                            snapshotTimeout.stop()
                            root.snapshotPending = false
                            if (value.snapshot) root.snapshotSaved(value.snapshot)
                            else root.snapshotFailed(String(value.snapshotError))
                        }
                    }
                    else if (value.error) root.streamFailed(String(value.error))
                    else if (value.configurationError && value.failedConfigurationRevision !== root.rejectedRevision) {
                        root.rejectedRevision = value.failedConfigurationRevision
                        root.configurationRejected(String(value.camera || ""), String(value.configurationError))
                    }
                    else if (value.frame) {
                        if (root.sharedOutput) firstFrameTimeout.restart()
                        else firstFrameTimeout.stop()
                        root.reconnecting = false
                        root.appliedGeneration = value.configurationRevision || 0
                        root.format = { captureWidth: value.captureWidth, captureHeight: value.captureHeight,
                            captureFps: value.captureFps, retainedWidth: value.retainedWidth, retainedHeight: value.retainedHeight,
                            previewWidth: value.width, previewHeight: value.height, previewFps: value.previewFps, provider: value.provider, dropped: value.dropped }
                        root.frameUrl = "data:image/jpeg;base64," + value.frame
                        if (value.sourceFrame) root.sourceFrameUrl = "data:image/jpeg;base64," + value.sourceFrame
                        if(value.labelBitmap){root.labelBitmapUrl="data:image/png;base64,"+value.labelBitmap;root.labelBitmapKey=value.labelKey;root.labelBitmapWidth=value.labelWidth;root.labelBitmapHeight=value.labelHeight}
                        root.effect = value.effect
                        root.cameraSource = String(value.camera || "")
                        root.frameReceived(value.effect)
                    }
                } catch (error) { root.streamFailed("Could not read the processed camera preview") }
            }
        }
        stderr: StdioCollector { id: errors; waitForEnd: true }
        onExited: function(code) {
            root.starting=false
            firstFrameTimeout.stop()
            root.streamFailed(String(errors.text || "Camera preview stopped").slice(0, 400))
        }
    }
}
