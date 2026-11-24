import QtQuick
import Quickshell.Io

Item {
    id: root
    property var settings: null
    readonly property string clientPath: decodeURIComponent(Qt.resolvedUrl("../bin/background-preview-client.py").toString().replace(/^file:\/\//, ""))
    property string frameUrl: ""
    property bool failed: false
    property bool restartRequired: false

    function fail() {
        frameUrl = ""
        failed = true
    }

    Process {
        command: ["python3", root.clientPath, JSON.stringify(root.settings)]
        running: root.settings !== null
        stdout: SplitParser {
            onRead: function(line) {
                if (line.length > 262144) return
                try {
                    var result = JSON.parse(line)
                    if (result.frame) root.frameUrl = "data:image/jpeg;base64," + result.frame
                    else if (result.restartRequired) root.restartRequired = true
                    else if (result.error) root.fail()
                } catch (error) {
                    root.fail()
                }
            }
        }
        onExited: function() { if (!root.restartRequired) root.fail() }
    }
}
