import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Io

ColumnLayout {
    id: root
    objectName: "snapshotGallery"
    property var snapshots: []
    property bool revelator: false
    property string feedback: ""
    property bool refreshPending: false
    readonly property string helper: decodeURIComponent(Qt.resolvedUrl("../bin/snapshot-gallery.py").toString().replace(/^file:\/\//, ""))

    function refresh() {
        if (listing.running) {
            refreshPending = true
            return
        }
        listing.running = true
    }
    function runAction(action, snapshot) {
        if (snapshotAction.running) return
        feedback = action === "open-revelator" ? qsTr("Opening in Revelator…") : ""
        snapshotAction.command = ["python3", helper, action, snapshot.name]
        snapshotAction.running = true
    }
    Component.onCompleted: refresh()

    function checkRevelator() {
        if (!revelatorCheck.running) revelatorCheck.running = true
    }

    Process {
        id: revelatorCheck
        command: ["python3", root.helper, "revelator"]
        stdout: StdioCollector { id: revelatorResult; waitForEnd: true }
        onExited: function(code) {
            try { root.revelator = code === 0 && JSON.parse(revelatorResult.text).available }
            catch (error) { root.revelator = false }
        }
    }

    Process {
        id: listing
        command: ["python3", root.helper, "list"]
        stdout: StdioCollector { id: listResult; waitForEnd: true }
        onExited: function(code) {
            try {
                const result = JSON.parse(listResult.text)
                if (code !== 0 || !Array.isArray(result.items)) throw new Error()
                root.snapshots = result.items
            } catch (error) {
                root.feedback = qsTr("Couldn’t load saved snapshots.")
            }
            if (root.refreshPending) {
                root.refreshPending = false
                Qt.callLater(root.refresh)
            }
        }
    }
    Process {
        id: snapshotAction
        stdout: StdioCollector { id: actionResult; waitForEnd: true }
        onExited: function(code) {
            const action = command[2]
            const failure = action === "open-revelator" ? qsTr("Couldn’t open the snapshot in Revelator.")
                : action === "trash" ? qsTr("Couldn’t move the snapshot to Trash.")
                : qsTr("Couldn’t copy the snapshot.")
            try {
                const result = JSON.parse(actionResult.text)
                if (code !== 0) {
                    root.feedback = result.error || failure
                } else if (action === "open-revelator") {
                    root.feedback = ""
                } else if (action === "trash") {
                    root.feedback = qsTr("Snapshot moved to Trash.")
                    root.refresh()
                } else {
                    root.feedback = action === "copy-path" ? qsTr("Snapshot path copied.") : qsTr("Snapshot copied.")
                }
            } catch (error) {
                root.feedback = failure
            }
        }
    }
    Label {
        Layout.fillWidth: true
        visible: root.feedback !== ""
        text: root.feedback
        textFormat: Text.PlainText
        wrapMode: Text.WordWrap
    }
    Label {
        Layout.fillWidth: true
        visible: root.snapshots.length === 0 && root.feedback === ""
        text: listing.running ? qsTr("Loading snapshots…") : qsTr("No snapshots yet.")
        color: root.palette.placeholderText
    }
    ThumbnailGrid {
        id: grid
        objectName: "snapshotGrid"
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(264, contentHeight)
        visible: count > 0
        items: root.snapshots

        delegate: Rectangle {
            id: card
            required property var modelData
            width: grid.cellWidth - 8
            height: grid.cellHeight - 8
            radius: 4
            color: root.palette.alternateBase
            border.color: root.palette.mid
            Image {
                anchors.fill: parent
                anchors.margins: 6
                source: card.modelData.thumbnail
                sourceSize: Qt.size(320, 180)
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                clip: true
                HoverHandler { id: imagePointer }
                Row {
                    anchors.top: parent.top
                    anchors.right: parent.right
                    anchors.margins: 2
                    spacing: 1
                    visible: imagePointer.hovered
                    Repeater {
                        model: [
                            {kind: "copy", command: "copy-image", label: qsTr("Copy image")},
                            {kind: "path", command: "copy-path", label: qsTr("Copy file path")},
                            ...(root.revelator ? [{kind: "open", command: "open-revelator", label: qsTr("Open in Revelator")}] : []),
                            {kind: "trash", command: "trash", label: qsTr("Move snapshot to Trash")}
                        ]
                        ThumbnailAction {
                            required property var modelData
                            objectName: modelData.command + "-" + card.modelData.name
                            enabled: !snapshotAction.running
                            Accessible.name: modelData.label
                            kind: modelData.kind
                            onClicked: root.runAction(modelData.command, card.modelData)
                        }
                    }
                }
            }
        }
    }
}
