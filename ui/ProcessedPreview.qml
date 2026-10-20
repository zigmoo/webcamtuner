import QtQuick
import Quickshell.Io

Item {
    id: root
    property bool active: false
    property var configuration: ({})
    property string pluginRoot: Qt.resolvedUrl("../").toString().replace(/^file:\/\//, "").replace(/\/$/, "")
    property string frameUrl: ""
    property string effect: ""
    signal failed(string message)
    function activate() {
        if (active) {
            frameUrl = ""
            process.command = ["python3", pluginRoot + "/bin/process_preview.py", "--request", JSON.stringify(configuration)]
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
                        root.frameUrl = "data:image/jpeg;base64," + value.frame
                        root.effect = value.effect
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
