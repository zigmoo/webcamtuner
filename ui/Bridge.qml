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
            var operation = root.action
            if (code !== 0) {
                root.failure = String(errors.text || output.text || "Command failed").slice(0, 500)
                var failure = root.failure
                Qt.callLater(function() { root.failed(failure) })
                return
            }
            // Settle Process.running before a response handler starts the next command.
            try {
                var result = JSON.parse(output.text)
                Qt.callLater(function() { root.received(operation, result) })
            } catch (e) {
                var message = "Could not read the controller response: " + e.message
                Qt.callLater(function() { root.failed(message) })
            }
        }
    }
}
