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
    property bool initiallyPositioned: false
    property bool cameraLive: false
    property bool cameraStarting: false
    property bool cameraStopping: false
    property var previewSettingsFor: null
    property var labelTextFor: image => image.label || image.name
    property Item previewAnchor: null
    property var previewImage: null
    property bool showingImageInfo: false
    property bool haveLiveFrame: false
    readonly property real toolbarHeight: toolbar.implicitHeight + spacing
    readonly property bool previewRunning: cameraLive && !cameraStopping

    function showPreview(anchor, image, metadata = false) {
        if (previewAnchor === anchor) return
        hidePreview(previewAnchor)
        previewAnchor = anchor
        previewImage = image
        showingImageInfo = metadata
        hoverDelay.restart()
    }
    function hidePreview(anchor) {
        if (previewAnchor !== anchor) return
        hoverDelay.stop()
        dismissPreview.stop()
        previewPopup.close()
        previewImage = null
        previewAnchor = null
        haveLiveFrame = false
    }
    function openPreview() {
        previewPopup.open()
        if (!showingImageInfo && !cameraLive && !cameraStarting && !cameraStopping)
            livePreviewRequested()
    }
    function activatePreview(image) {
        if (!previewPopup.visible || previewImage?.path !== image.path || !haveLiveFrame
            || !livePreview.item?.frameUrl || livePreview.item.failed) return false
        hidePreview(previewAnchor)
        previewAccepted(image.path)
        return true
    }
    onVisibleChanged: if (!visible) hidePreview(previewAnchor)
    Timer {
        id: dismissPreview
        interval: 200
        onTriggered: {
            if (!popupPointer.hovered && !root.previewAnchor?.hovered)
                root.hidePreview(root.previewAnchor)
        }
    }
    Timer {
        id: hoverDelay
        interval: 220
        onTriggered: {
            if (!root.previewAnchor || !root.previewAnchor.hovered) return
            root.openPreview()
        }
    }
    Popup {
        id: previewPopup
        objectName: "backgroundHoverPreview"
        parent: Overlay.overlay
        width: parent ? Math.min(320, parent.width - 16) : 320
        padding: 8
        modal: false
        focus: false
        closePolicy: root.showingImageInfo ? Popup.CloseOnEscape | Popup.CloseOnPressOutside : Popup.NoAutoClose
        x: {
            if (!root.previewAnchor || !parent) return 0
            return Math.max(8, Math.min(parent.width - width - 8, root.previewAnchor.mapToItem(parent, 0, 0).x))
        }
        readonly property real anchorTop: root.previewAnchor && parent
            ? root.previewAnchor.mapToItem(parent, 0, 0).y : 0
        readonly property real anchorBottom: anchorTop + (root.previewAnchor ? root.previewAnchor.height : 0)
        readonly property real roomAbove: Math.max(0, anchorTop - 14)
        readonly property real roomBelow: parent ? Math.max(0, parent.height - anchorBottom - 14) : 0
        readonly property bool opensBelow: roomBelow >= implicitHeight || roomBelow >= roomAbove
        height: root.previewAnchor ? Math.min(implicitHeight, opensBelow ? roomBelow : roomAbove) : implicitHeight
        y: opensBelow ? anchorBottom + 6 : anchorTop - height - 6
        palette: root.palette
        background: Rectangle { color: root.palette.window; border.color: root.palette.mid; radius: 5 }
        contentItem: ColumnLayout {
            spacing: 6
            HoverHandler {
                id: popupPointer
                enabled: !root.showingImageInfo
                cursorShape: root.haveLiveFrame ? Qt.PointingHandCursor : Qt.ArrowCursor
                onHoveredChanged: {
                    if (hovered) dismissPreview.stop()
                    else if (previewPopup.visible) dismissPreview.restart()
                }
            }
            TapHandler {
                enabled: !root.showingImageInfo
                onTapped: if (root.previewImage) root.activatePreview(root.previewImage)
            }
            Label {
                text: root.previewImage ? root.previewImage.label || root.previewImage.name : ""
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: root.palette.windowText
                Layout.fillWidth: true
            }
            Label {
                objectName: "backgroundImageMetadata"
                readonly property var metadata: root.previewImage?.metadata
                visible: root.showingImageInfo
                Layout.fillWidth: true
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                color: root.palette.placeholderText
                text: metadata ? [
                    root.previewImage.label ? root.previewImage.name : "",
                    qsTr("%1 × %2 px · %3").arg(metadata.width).arg(metadata.height).arg(metadata.format),
                    metadata.bytes >= 1048576 ? qsTr("%1 MiB").arg((metadata.bytes / 1048576).toFixed(1))
                        : qsTr("%1 KiB").arg((metadata.bytes / 1024).toFixed(1)),
                    qsTr("Modified %1").arg(new Date(metadata.modified).toLocaleString())
                ].filter(line => line !== "").join("\n") : qsTr("Image details unavailable.")
            }
            PreviewFrame {
                objectName: "hoverPreviewFrame"
                onFrameDecoded: if (root.previewRunning && !root.showingImageInfo && livePreview.item?.frameUrl)
                    root.haveLiveFrame = true
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredHeight: Math.round(width * 9 / 16)
                visible: !root.showingImageInfo && source.toString() !== ""
                source: root.showingImageInfo ? "" : root.previewRunning ? (livePreview.item ? livePreview.item.frameUrl : "")
                    : !root.cameraStarting && !root.cameraStopping && root.previewImage ? root.previewImage.thumbnail : ""
            }
            Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                visible: !root.showingImageInfo && text !== ""
                color: root.palette.placeholderText
                text: root.cameraStopping ? qsTr("Camera is stopping…")
                    : root.cameraStarting && !root.cameraLive ? qsTr("Camera is starting…")
                    : !root.cameraLive ? qsTr("Start the camera to see the live composition.")
                    : livePreview.item && livePreview.item.restartRequired ? qsTr("Live preview is unavailable for the current camera session.")
                    : livePreview.item && livePreview.item.failed ? qsTr("Couldn’t load the live composition. Hover again to retry.")
                    : livePreview.item && livePreview.item.frameUrl ? "" : qsTr("Preparing live composition…")
            }
            Loader {
                id: livePreview
                active: previewPopup.visible && !root.showingImageInfo && root.previewRunning && !!root.previewImage && !!root.previewSettingsFor
                source: Qt.resolvedUrl("BackgroundPreviewStream.qml")
                onLoaded: item.settings = root.previewSettingsFor(root.previewImage)
            }
        }
    }
    function revealSelection() {
        var index = root.library.items.findIndex(i => i.path === root.selectedPath)
        if (index >= 0) grid.positionViewAtIndex(index, GridView.Contain)
    }
    onSelectedPathChanged: Qt.callLater(revealSelection)
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
    signal livePreviewRequested()
    signal addRequested()
    signal openFolderRequested()
    signal refreshRequested()
    signal selected(string path)
    signal previewAccepted(string path)
    signal cropRequested(var image)
    signal lockRequested(var image)
    signal trashRequested(var image)
    signal labelRequested(var image, string label)
    signal labelEditingChanged(bool active)
    signal overlayRequested(var image, bool enabled, real opacity)
    spacing: 10
    RowLayout {
        id: toolbar
        Layout.fillWidth: true
        Label { visible: root.compact; text: qsTr("Images"); textFormat: Text.PlainText; color: root.palette.windowText; font.bold: true; Layout.fillWidth: true }
        Button {
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("Choose images to add. You can also copy images into the background folder.")
            objectName: "addBackgrounds"
            text: root.compact ? qsTr("Add…") : qsTr("Add images…")
            enabled: !root.busy
            onClicked: root.addRequested()
        }
        Button {
            objectName: "openBackgroundFolder"
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("Open the background image library in the file manager.") + "\n" + root.library.directory
            text: qsTr("Open folder")
            enabled: !!root.library.directory
            onClicked: root.openFolderRequested()
        }
        Button {
            objectName: "refreshBackgrounds"
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("Refresh the background library from disk.")
            text: qsTr("Refresh")
            enabled: !root.busy
            onClicked: root.refreshRequested()
        }
        Item { visible: !root.compact; Layout.fillWidth: true }
    }
    Label {
        objectName: "backgroundEmptyState"
        visible: root.library.items.length === 0
        text: root.busy ? qsTr("Loading backgrounds…") : qsTr("No background images yet.")
        textFormat: Text.PlainText
        color: root.palette.placeholderText
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }
    ThumbnailGrid {
        id: grid
        objectName: "backgroundGrid"
        visible: root.library.items.length > 0
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(root.availableGridHeight, contentHeight)
        items: root.library.items
        onModelScrollRestored: {
            if (!root.initiallyPositioned && count > 0) {
                root.revealSelection()
                root.initiallyPositioned = true
            }
        }
        keyNavigationEnabled: true
        activeFocusOnTab: true
        delegate: ItemDelegate {
            id: card
            required property var modelData
            width: grid.cellWidth - 8
            height: grid.cellHeight - 8
            Accessible.name: modelData.label || modelData.name
            highlighted: root.selectedPath === modelData.path
            background: Rectangle { color: parent.highlighted ? root.palette.midlight : root.palette.alternateBase; radius: 4; border.width: 2; border.color: parent.highlighted ? root.palette.link : root.palette.mid }
            contentItem: ColumnLayout {
                spacing: 6
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    Image { anchors.fill: parent; source: card.modelData.thumbnail; asynchronous: true; fillMode: Image.PreserveAspectCrop; sourceSize.width: 320; sourceSize.height: 180 }
                    BackgroundLabelOverlay { anchors.fill: parent; overlay: ({enabled: !!(card.modelData.overlay && card.modelData.overlay.enabled), opacity: card.modelData.overlay ? card.modelData.overlay.opacity : 0.75, text: card.modelData.label || card.modelData.name}) }
                    HoverHandler { id: imagePointer }
                    Row {
                        anchors.top: parent.top
                        anchors.right: parent.right
                        anchors.margins: 2
                        spacing: 1
                        visible: imagePointer.hovered
                        ThumbnailAction {
                            id: imageInfo
                            objectName: "backgroundAction-info-" + card.modelData.id
                            Accessible.name: qsTr("Image metadata")
                            kind: "info"
                            showToolTip: false
                            onHoveredChanged: {
                                if (hovered) root.showPreview(imageInfo, card.modelData, true)
                                else root.hidePreview(imageInfo)
                            }
                            onClicked: {
                                root.showPreview(imageInfo, card.modelData, true)
                                hoverDelay.stop()
                                previewPopup.open()
                            }
                            Component.onDestruction: root.hidePreview(imageInfo)
                        }
                        Repeater {
                            model: ["preview", "crop", "lock", "trash"]
                            ThumbnailAction {
                                id: actionButton
                                required property string modelData
                                readonly property bool isPreview: modelData === "preview"
                                property var image: card.modelData
                                objectName: "backgroundAction-" + modelData + "-" + image.id
                                enabled: isPreview || (root.actionsReady && !root.busy && (modelData === "lock" || !image.locked))
                                Accessible.name: isPreview ? qsTr("Preview this background") : modelData === "crop" ? qsTr("Crop background") : modelData === "trash" ? qsTr("Move background to Trash") : image.locked ? qsTr("Unlock background") : qsTr("Lock crop and protect from Trash")
                                kind: modelData === "lock" ? (image.locked ? "locked" : "unlocked") : modelData
                                showToolTip: !isPreview
                                onHoveredChanged: {
                                    if (!isPreview) return
                                    if (hovered) root.showPreview(actionButton, image)
                                    else if (root.previewAnchor === actionButton) dismissPreview.restart()
                                }
                                Component.onDestruction: if (isPreview) root.hidePreview(actionButton)
                                onClicked: {
                                    if (isPreview) {
                                        if (!root.activatePreview(image)) {
                                            root.showPreview(actionButton, image)
                                            hoverDelay.stop()
                                            root.openPreview()
                                        }
                                        return
                                    }
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
                    readonly property string savedLabel: root.labelTextFor(card.modelData)
                    property bool labelEdited: false
                    Layout.fillWidth: true
                    text: savedLabel
                    placeholderText: card.modelData.name
                    maximumLength: 80
                    selectByMouse: true
                    font.pixelSize: 12
                    color: root.palette.windowText
                    padding: 2
                    Accessible.name: qsTr("Background label")
                    ToolTip.visible: hovered && !activeFocus
                    ToolTip.text: qsTr("Click to add or edit a label · %1").arg(card.modelData.name)
                    background: Rectangle {
                        color: parent.activeFocus ? root.palette.base : "transparent"
                        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: root.palette.link; visible: parent.parent.activeFocus }
                    }
                    onActiveFocusChanged:if(activeFocus)root.labelEditingChanged(true)
                    onTextEdited: labelEdited = true
                    onEditingFinished: {
                        var label = text.trim()
                        var changed = labelEdited && label !== savedLabel
                        var image = card.modelData
                        labelEdited = false
                        if (changed) root.labelRequested(image, label)
                        text = Qt.binding(function() { return savedLabel })
                        root.labelEditingChanged(false)
                    }
                }

            }
            onClicked: root.selected(modelData.path)
        }
    }
}
