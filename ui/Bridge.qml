import QtQuick
import Quickshell.Io

Item {
    id: root
    property bool busy: process.running
    property string action: ""
    property string failure: ""
    property string pluginRoot: Qt.resolvedUrl("../").toString().replace(/^file:\/\//, "").replace(/\/$/, "")
    signal received(string action, var result)
    signal failed(string message)
    function request(operation, args) {
        if (busy) return
        action = operation
        failure = ""
        process.command = [pluginRoot + "/bin/webcamtuner", operation].concat(args || []).concat(["--json"])
        process.running = true
    }
    Process {
        id: process
        stdout: StdioCollector { id: output; waitForEnd: true }
        stderr: StdioCollector { id: errors; waitForEnd: true }
        onExited: function(code) {
            if (code !== 0) {
                root.failure = String(errors.text || output.text || "Command failed").slice(0, 500)
                root.failed(root.failure)
                return
            }
            try { root.received(root.action, JSON.parse(output.text)) }
            catch (e) { root.failed("Could not read the controller response: " + e.message) }
        }
    }
}
