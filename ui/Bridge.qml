import QtQuick
import Quickshell.Io

Item {
    id: root
    readonly property bool busy: activeRequest !== null || pending.length > 0
    property var activeRequest: null
    property var pending: []
    property string action: ""
    property string failure: ""
    property string pluginRoot: Qt.resolvedUrl("../").toString().replace(/^file:\/\//, "").replace(/\/$/, "")
    signal received(string action, var result)
    signal failed(string message)
    function request(operation, args) {
        if (pending.length >= 16) {
            Qt.callLater(function() { root.failed(qsTr("Too many pending operations. Please retry.")) })
            return
        }
        pending = pending.concat([{operation: operation, args: (args || []).slice()}])
        pump()
    }
    function pump() {
        if (activeRequest !== null || pending.length === 0) return
        // Reserve the request before Process.running changes asynchronously.
        activeRequest = pending[0]
        pending = pending.slice(1)
        action = activeRequest.operation
        failure = ""
        process.command = [pluginRoot + "/bin/webcamtuner", action].concat(activeRequest.args).concat(["--json"])
        process.running = true
    }
    Process {
        id: process
        stdout: StdioCollector { id: output; waitForEnd: true }
        stderr: StdioCollector { id: errors; waitForEnd: true }
        onExited: function(code) {
            var operation = root.activeRequest.operation
            var result = null
            var error = ""
            if (code !== 0) error = String(errors.text || output.text || "Command failed").slice(0, 500)
            else {
                try { result = JSON.parse(output.text) }
                catch (e) { error = "Could not read the controller response: " + e.message }
            }
            // Deliver this operation's response after Process settles, then drain.
            Qt.callLater(function() {
                root.activeRequest = null
                if (error !== "") { root.failure = error; root.failed(error) }
                else root.received(operation, result)
                root.pump()
            })
        }
    }
}
