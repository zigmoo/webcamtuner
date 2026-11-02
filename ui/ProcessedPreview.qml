import QtQuick
import Quickshell.Io

Item {
    id: root
    property bool active: false
    property var configuration: ({})
    property string pluginRoot: Qt.resolvedUrl("../").toString().replace(/^file:\/\//, "").replace(/\/$/, "")
    property string frameUrl: ""
    property string effect: ""
    property var format: ({})
    property int desiredGeneration: 0
    property int appliedGeneration: -1
    property bool snapshotPending: false
    property string snapshotRequestId: ""
    readonly property bool snapshotReady: active && frameUrl !== "" && !updateDelay.running && desiredGeneration === appliedGeneration && !snapshotPending
    signal snapshotSaved(var result)
    signal snapshotFailed(string message)
    function takeSnapshot() {
        if (!snapshotReady) return
        snapshotRequestId = Date.now().toString() + "-" + Math.floor(Math.random() * 1000000).toString()
        snapshotPending = true
        process.write(JSON.stringify({operation: "snapshot", requestId: snapshotRequestId, expectedRevision: desiredGeneration}) + "\n")
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
            frameUrl = ""
            process.command = [pluginRoot + "/bin/preview-python", pluginRoot + "/bin/process_preview.py", "--request", JSON.stringify(Object.assign({}, configuration, {configurationRevision: desiredGeneration}))]
            process.running = true
        } else {
            process.running = false
            frameUrl = ""
        }
    }
    onActiveChanged: activate()
    onConfigurationChanged: { desiredGeneration++; updateDelay.restart() }
    Component.onDestruction: process.running = false
    Timer {
        id: updateDelay
        interval: 180
        onTriggered: if (process.running && root.configuration) process.write(JSON.stringify(Object.assign({}, root.configuration, {configurationRevision: root.desiredGeneration})) + "\n")
    }
    Process {
        id: process
        stdinEnabled: true
        stdout: SplitParser {
            onRead: function(line) {
                if (line.length > 1048576) { root.failed("Preview frame exceeded its size limit"); return }
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
                    else if (value.error) root.failed(String(value.error))
                    else if (value.frame) {
                        root.appliedGeneration = value.configurationRevision || 0
                        root.format = { captureWidth: value.captureWidth, captureHeight: value.captureHeight,
                            captureFps: value.captureFps, retainedWidth: value.retainedWidth, retainedHeight: value.retainedHeight,
                            previewWidth: value.width, previewHeight: value.height, previewFps: value.previewFps, provider: value.provider, dropped: value.dropped }
                        root.frameUrl = "data:image/jpeg;base64," + value.frame
                        root.effect = value.effect
                        root.frameReceived(value.effect)
                    }
                } catch (error) { root.failed("Could not read the processed camera preview") }
            }
        }
        stderr: StdioCollector { id: errors; waitForEnd: true }
        onExited: function(code) {
            if (root.active && code !== 0)
                root.failed(String(errors.text || "Camera preview stopped").slice(0, 400))
        }
    }
}
