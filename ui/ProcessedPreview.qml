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
    signal failed(string message)
    signal frameReceived(string mode)
    function activate() {
        if (active) {
            frameUrl = ""
            process.command = [pluginRoot + "/bin/preview-python", pluginRoot + "/bin/process_preview.py", "--request", JSON.stringify(configuration)]
            process.running = true
        } else {
            process.running = false
            frameUrl = ""
        }
    }
    onActiveChanged: activate()
    onConfigurationChanged: updateDelay.restart()
    Component.onDestruction: process.running = false
    Timer {
        id: updateDelay
        interval: 180
        onTriggered: if (process.running && root.configuration) process.write(JSON.stringify(root.configuration) + "\n")
    }
    Process {
        id: process
        stdinEnabled: true
        stdout: SplitParser {
            onRead: function(line) {
                if (line.length > 1048576) { root.failed("Preview frame exceeded its size limit"); return }
                try {
                    var value = JSON.parse(line)
                    if (value.error) root.failed(String(value.error))
                    else if (value.frame) {
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
