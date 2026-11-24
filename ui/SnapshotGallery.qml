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
                : qsTr("Couldn’t copy the snapshot.")
            try {
                const result = JSON.parse(actionResult.text)
                if (code !== 0) {
                    root.feedback = result.error || failure
                } else if (action === "open-revelator") {
                    root.feedback = ""
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
    GridView {
        id: grid
        objectName: "snapshotGrid"
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(264, contentHeight)
        visible: count > 0
        clip: true
        model: root.snapshots
        cellWidth: width / Math.max(1, Math.floor(width / 150))
        cellHeight: 132
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: VisibleScrollBar { policy: grid.contentHeight > grid.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff }

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
                anchors.bottomMargin: 26
                source: card.modelData.thumbnail
                sourceSize: Qt.size(320, 180)
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
            }
            Label {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 6
                elide: Text.ElideRight
                text: card.modelData.name.replace(/^WebcamTuner-/, "")
                textFormat: Text.PlainText
                color: root.palette.windowText
            }
            Row {
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.margins: 8
                spacing: 2
                Repeater {
                    model: [
                        {kind: "copy", command: "copy-image", label: qsTr("Copy image")},
                        {kind: "path", command: "copy-path", label: qsTr("Copy file path")},
                        ...(root.revelator ? [{kind: "open", command: "open-revelator", label: qsTr("Open in Revelator")}] : [])
                    ]
                    ToolButton {
                        id: action
                        required property var modelData
                        objectName: modelData.command + "-" + card.modelData.name
                        width: 26
                        height: 26
                        padding: 4
                        enabled: !snapshotAction.running
                        hoverEnabled: true
                        Accessible.name: modelData.label
                        ToolTip.text: modelData.label
                        ToolTip.visible: hovered
                        ToolTip.delay: 500
                        contentItem: BackgroundActionIcon { kind: action.modelData.kind }
                        background: Rectangle { color: action.hovered ? "#40536b" : "#d0171c24"; radius: 4 }
                        onClicked: root.runAction(modelData.command, card.modelData)
                    }
                }
            }
        }
    }
}
