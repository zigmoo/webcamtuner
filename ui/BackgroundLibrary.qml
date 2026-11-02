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
    property bool watching: false
    property int refreshInterval: 15000
    property real previousScroll: 0
    property bool updating: false
    onLibraryChanged: {
        updating = true
        Qt.callLater(function() {
            grid.contentY = Math.max(0, Math.min(root.previousScroll, grid.contentHeight - grid.height))
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
    spacing: 10
    RowLayout {
        Layout.fillWidth: true
        Label { text: qsTr("Saved backgrounds"); textFormat: Text.PlainText; color: "#e9ecef"; font.bold: true; Layout.fillWidth: true }
        Button { objectName: "addBackgrounds"; text: qsTr("Add images…"); enabled: !root.busy; onClicked: root.addRequested() }
        Button { text: qsTr("Refresh"); enabled: !root.busy; onClicked: root.refreshRequested() }
    }
    TextField {
        objectName: "backgroundLibraryPath"
        Layout.fillWidth: true
        readOnly: true
        selectByMouse: true
        text: root.library.directory || ""
        placeholderText: qsTr("Loading background folder…")
        Accessible.name: qsTr("Background storage folder")
    }
    RowLayout {
        Layout.fillWidth: true
        Label { text: qsTr("Added images are copied here. Your originals stay in place."); textFormat: Text.PlainText; color: "#a9b4c1"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        Button {
            text: qsTr("Open folder")
            enabled: !!root.library.directory
            onClicked: Qt.openUrlExternally("file://" + root.library.directory.split("/").map(encodeURIComponent).join("/"))
        }
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
        Layout.preferredHeight: Math.min(360, contentHeight)
        clip: true
        model: root.library.items
        cellWidth: width / Math.max(1, Math.floor(width / 150))
        cellHeight: 132
        boundsBehavior: Flickable.StopAtBounds
        keyNavigationEnabled: true
        activeFocusOnTab: true
        ScrollBar.vertical: ScrollBar { policy: grid.contentHeight > grid.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff }
        delegate: ItemDelegate {
            required property var modelData
            width: grid.cellWidth - 8
            height: grid.cellHeight - 8
            enabled: !root.busy
            Accessible.name: modelData.name
            highlighted: root.selectedPath === modelData.path
            background: Rectangle { color: parent.highlighted ? "#284c44" : "#222b35"; radius: 4; border.width: 2; border.color: parent.highlighted ? "#93c5aa" : "#39414b" }
            contentItem: ColumnLayout {
                spacing: 6
                Image { source: modelData.thumbnail; asynchronous: true; fillMode: Image.PreserveAspectCrop; clip: true; Layout.fillWidth: true; Layout.fillHeight: true; sourceSize.width: 320; sourceSize.height: 180 }
                Text { text: modelData.name; textFormat: Text.PlainText; color: "#e9ecef"; elide: Text.ElideRight; Layout.fillWidth: true; font.pixelSize: 12 }
            }
            onClicked: root.selected(modelData.path)
        }
    }
}
