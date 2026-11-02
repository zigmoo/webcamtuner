import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt.labs.folderlistmodel

ColumnLayout {
    id: root
    objectName: "backgroundLibraryView"
    property var library: ({directory: "", items: []})
    property string selectedPath: ""
    property bool busy: false
    property bool actionsReady: true
    property bool compact: false
    property int availableGridHeight: 360
    property bool watching: false
    property int refreshInterval: 15000
    property real previousScroll: 0
    property bool updating: false
    property bool initiallyPositioned: false
    function revealSelection() {
        var index = root.library.items.findIndex(i => i.path === root.selectedPath)
        if (index >= 0) grid.positionViewAtIndex(index, GridView.Contain)
    }
    onSelectedPathChanged: Qt.callLater(revealSelection)
    onLibraryChanged: {
        updating = true
        Qt.callLater(function() {
            grid.contentY = Math.max(0, Math.min(root.previousScroll, grid.contentHeight - grid.height))
            if (!root.initiallyPositioned && root.library.items.length) { root.revealSelection(); root.initiallyPositioned = true }
            root.updating = false
        })
    }
    FolderListModel {
        id: folder
        folder: root.watching && root.library.directory ? "file://" + root.library.directory.split("/").map(encodeURIComponent).join("/") : ""
        nameFilters: ["*.jpg", "*.jpeg", "*.png", "*.webp"]
        caseSensitive: false
        showDirs: false
        showHidden: false
        onCountChanged: if (root.watching) changed.restart()
    }
    Connections {
        target: folder
        function onDataChanged() { if (root.watching) changed.restart() }
    }
    Timer { id: changed; interval: 1200; onTriggered: if (root.watching && !root.busy) root.refreshRequested() }
    Timer { interval: root.refreshInterval; repeat: true; running: root.watching; onTriggered: if (!root.busy) root.refreshRequested() }
    signal addRequested()
    signal refreshRequested()
    signal selected(string path)
    signal cropRequested(var image)
    signal lockRequested(var image)
    signal trashRequested(var image)
    signal labelRequested(var image, string label)
    spacing: 10
    RowLayout {
        Layout.fillWidth: true
        Label { text: root.compact ? qsTr("Images") : qsTr("Saved backgrounds"); textFormat: Text.PlainText; color: "#e9ecef"; font.bold: true; Layout.fillWidth: true }
        Button { objectName: "addBackgrounds"; text: root.compact ? qsTr("Add…") : qsTr("Add images…"); enabled: !root.busy; onClicked: root.addRequested() }
        Button { text: qsTr("Refresh"); enabled: !root.busy; onClicked: root.refreshRequested() }
    }
    Label {
        visible: root.library.items.length === 0
        text: root.busy ? qsTr("Loading backgrounds…") : qsTr("No saved backgrounds yet. Add images to build your library.")
        textFormat: Text.PlainText
        color: "#a9b4c1"
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }
    GridView {
        id: grid
        objectName: "backgroundGrid"
        onContentYChanged: if (!root.updating) root.previousScroll = contentY
        visible: root.library.items.length > 0
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(root.availableGridHeight, contentHeight)
        clip: true
        model: root.library.items
        cellWidth: width / Math.max(1, Math.floor(width / 150))
        cellHeight: 132
        boundsBehavior: Flickable.StopAtBounds
        keyNavigationEnabled: true
        activeFocusOnTab: true
        ScrollBar.vertical: VisibleScrollBar { policy: grid.contentHeight > grid.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff }
        delegate: ItemDelegate {
            id: card
            required property var modelData
            width: grid.cellWidth - 8
            height: grid.cellHeight - 8
            enabled: !root.busy
            Accessible.name: modelData.label || modelData.name
            highlighted: root.selectedPath === modelData.path
            background: Rectangle { color: parent.highlighted ? "#284c44" : "#222b35"; radius: 4; border.width: 2; border.color: parent.highlighted ? "#93c5aa" : "#39414b" }
            contentItem: ColumnLayout {
                spacing: 6
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    Image { anchors.fill: parent; source: card.modelData.thumbnail; asynchronous: true; fillMode: Image.PreserveAspectCrop; sourceSize.width: 320; sourceSize.height: 180 }
                    Row {
                        anchors.top: parent.top; anchors.right: parent.right; anchors.margins: 6
                        spacing: 2
                        Repeater {
                            model: ["crop", "lock", "trash"]
                            ToolButton {
                                required property string modelData
                                property var image: card.modelData
                                objectName: "backgroundAction-" + modelData + "-" + image.id
                                width: 26; height: 26; padding: 4
                                enabled: root.actionsReady && !root.busy && (modelData === "lock" || !image.locked)
                                Accessible.name: modelData === "crop" ? qsTr("Crop background") : modelData === "trash" ? qsTr("Move background to Trash") : image.locked ? qsTr("Unlock background") : qsTr("Lock crop and protect from Trash")
                                ToolTip.visible: hovered
                                ToolTip.text: Accessible.name
                                contentItem: BackgroundActionIcon { kind: parent.modelData === "lock" ? (parent.image.locked ? "locked" : "unlocked") : parent.modelData; ink: parent.enabled ? "#e9ecef" : "#7b8490" }
                                background: Rectangle { color: parent.hovered ? "#40536b" : "#d0171c24"; radius: 4 }
                                onClicked: {
                                    if (modelData === "crop") root.cropRequested(image)
                                    else if (modelData === "lock") root.lockRequested(image)
                                    else root.trashRequested(image)
                                }
                            }
                        }
                    }
                }
                TextField {
                    objectName: "backgroundLabel-" + card.modelData.id
                    property bool labelEdited: false
                    Layout.fillWidth: true
                    text: card.modelData.label || card.modelData.name
                    placeholderText: card.modelData.name
                    maximumLength: 80
                    selectByMouse: true
                    font.pixelSize: 12
                    color: "#e9ecef"
                    padding: 2
                    Accessible.name: qsTr("Background label")
                    ToolTip.visible: hovered && !activeFocus
                    ToolTip.text: qsTr("Click to add or edit a label · %1").arg(card.modelData.name)
                    background: Rectangle {
                        color: parent.activeFocus ? "#303944" : "transparent"
                        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: "#93c5aa"; visible: parent.parent.activeFocus }
                    }
                    onTextEdited: labelEdited = true
                    onEditingFinished: {
                        var label = text.trim()
                        var changed = labelEdited && label !== (card.modelData.label || card.modelData.name)
                        var image = card.modelData
                        labelEdited = false
                        text = Qt.binding(function() { return card.modelData.label || card.modelData.name })
                        if (changed) root.labelRequested(image, label === image.name ? "" : label)
                    }
                }
            }
            onClicked: root.selected(modelData.path)
        }
    }
}
