import QtQuick
import QtQuick.Controls
import "ui" as Tuner

ApplicationWindow {
    id: window
    width: 800; height: 960; visible: true
    title: "WebcamTuner · design preview"
    Tuner.Bridge {
        id: bridge
        onReceived: function(action, result) { editor.accept(action, result) }
        onFailed: function(message) { editor.message = message }
    }
    Tuner.Editor {
        id: editor
        anchors.fill: parent; busy: bridge.busy
        onRequest: function(action, args) { bridge.request(action, args) }
    }
    Component.onCompleted: bridge.request("read", [])
}
