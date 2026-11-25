import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import QtMultimedia
import QtCore
import "CameraChoice.js" as CameraChoice

Rectangle {
    id: root
    color: "#171c24"
    implicitWidth: 760
    implicitHeight: 850
    property color accent: "#93c5aa"
    property Palette popupPalette: palette
    property var labelFontFamilies: []
    property bool panelOpen: true
    property var document: null
    property int profileIndex: 0
    property bool dirty: false
    property bool busy: false
    property bool savePending: false
    property var controlIntents: []
    property bool mirrorQueued: false
    property bool cameraQueued: false
    property bool autostartQueued: false
    property bool saveFailed: false
    property bool automaticWritesPaused: false
    property int editGeneration: 0
    property int saveGeneration: -1
    property string message: qsTr("Loading saved profiles…")
    property bool previewOn: false
    property bool resumeOutputPreview: false
    property var outputControl: noOutput
    QtObject {
        id: noOutput
        property bool checked: true
        property bool readyToStart: true
        property bool published: false
        property bool busy: false
        property bool startingCamera: false
        property bool stopping: false
        property var state: ({})
        property bool cameraSwitching: false
        property string cameraFeedback: ""
        property int configurationRevision: 0
        function start() {}
        function stop() {}
    }
    readonly property bool publishing: root.outputControl.published
    readonly property bool cameraOutputActive: publishing || outputControl.startingCamera || !!(outputControl.state && outputControl.state.serviceActive)
    function startCamera() {
        if (outputControl.stopping) return false
        if (publishing) {
            autostartRequested = false
            resumeOutputPreview = true
            previewOn = true
            return true
        }
        if (!outputControl.startingCamera && outputControl.start() === false) return false
        autostartRequested = false
        resumeOutputPreview = true
        return true
    }
    function stopCamera() {
        backgroundPreviewRequestedPath = ""
        autostartRequested = false
        resumeOutputPreview = false
        previewOn = false
        if (sourceKind === "remote" || remoteConnecting) {
            remoteConnecting = false; previousSource = null
            remoteFeedback = qsTr("Disconnected. Remote camera released.")
        }
        if (cameraOutputActive || !outputControl.checked) outputControl.stop()
    }
    property string section: "all"
    property var backgroundLibrary: ({directory: "", items: []})
    property bool libraryPending: false
    property string libraryMessage: ""
    property var trashCandidate: null
    readonly property bool backgroundLocked: {
        var item = backgroundLibrary.items.find(i => i.path === imagePath)
        if (item) return !!item.locked
        return !!(backgroundLibrary.selected && backgroundLibrary.selected.path === imagePath && backgroundLibrary.selected.locked)
    }
    property Component setupContent: null
    property bool testing: false
    property bool processingReady: true
    property string snapshotDirectory: ""
    property bool remoteBrowse: false
    readonly property bool remotesVisible: section === "remotes" && remoteSources.visible
    readonly property int remoteHostCount: remoteSources.hosts.length
    readonly property int remoteCameraCount: remoteSources.cameras.length
    property bool remoteConnecting: false
    property string remoteFeedback: ""
    property var previousSource: null
    readonly property bool sourceReady: sourceKind === "remote" ? savedCamera.indexOf("sshcam://") === 0 : cameraChoiceReady && cameraIndex() >= 0
    readonly property bool remoteConnected: sourceKind === "remote" && !remoteConnecting && ((publishing && outputControl.state.camera === savedCamera) || (previewReady && processor.item.cameraSource === savedCamera))
    function connectRemote(uri, host) {
        if (remoteConnecting || !document || !processingReady) return
        previousSource = {camera:savedCamera, kind:sourceKind, host:sourceHost, preview:previewOn}
        remoteConnecting = true
        remoteFeedback = qsTr("Connecting to %1… The current camera stays live until video arrives.").arg(host)
        autostartRequested = false
        sourceKind = "remote"; sourceHost = host; savedCamera = uri
        previewOn = true
        mark()
    }
    function rejectRemote(message) {
        remoteFeedback = message
        remoteConnecting = false
        if (previousSource) {
            var previous = previousSource; previousSource = null
            sourceKind = previous.kind; sourceHost = previous.host; savedCamera = previous.camera
            previewOn = previous.preview
            mark()
        }
    }
    function disconnectRemote() {
        if (remoteConnecting && previousSource) {
            rejectRemote(qsTr("Connection cancelled. Previous camera retained."))
            return
        }
        stopCamera()
        remoteConnecting = false; previousSource = null
        remoteFeedback = qsTr("Disconnected. Remote camera released.")
    }
    property real zoom: 1
    property real centerX: 0.5
    property real centerY: 0.5
    property var foreground: ({x: 0, y: 0})
    property string backgroundMode: "none"
    property string imagePath: ""
    property string backgroundPreviewRequestedPath: ""
    readonly property bool selectedBackgroundPreviewReady: backgroundPreviewRequestedPath !== ""
        && backgroundPreviewRequestedPath === imagePath && imageReady && panelOpen
        && (section === "camera" || section === "all") && !outputControl.stopping
        && (publishing || outputControl.startingCamera || (processingReady && sourceReady
            && outputControl.readyToStart && !outputControl.busy && !remoteConnecting && !cameraPending))
    onSelectedBackgroundPreviewReadyChanged: {
        if (selectedBackgroundPreviewReady) Qt.callLater(root.startSelectedBackgroundPreview)
    }
    property var backgroundCrop: ({zoom: 1, centerX: 0.5, centerY: 0.5})
    readonly property var defaultPersonMask: ({softness: 0, tightness: 0})
    property var personMask: defaultPersonMask
    readonly property bool adjustingBackground: backgroundMoveHandle.panning
    property var backgroundLabelOverlay: ({enabled: false, opacity: 0.75, text: ""})
    property var labelDrafts: ({})
    property var labelInFlight: null
    property int labelGeneration: 0
    property bool previewLabelEditing: false
    property bool galleryLabelEditing: false
    readonly property bool labelEditing: previewLabelEditing || galleryLabelEditing
    property bool labelSaveFailed: false
    property string labelMessage: ""
    property var deferredLibrary: null
    property var cropDrafts: ({})
    property var cropInFlight: null
    property string cropMessage: ""
    property bool cropSaveFailed: false
    property bool restoreOnStart: true
    property bool mirror: true
    property bool mirrorPending: false
    property bool autostartCamera: true
    property bool autostartPending: false
    property bool autostartRequested: true
    property string localHostname: ""
    readonly property string localSourceLabel: localHostname ? qsTr("%1 - This Computer").arg(localHostname) : qsTr("This Computer")
    readonly property bool profileNeedsAttention: !document || saveFailed || labelSaveFailed || savePending || dirty
    property string lastSaveDetails: ""
    property bool outputHelpExpanded: false
    property string profileName: "Desk"
    property string savedCamera: ""
    property string sourceHost: ""
    property string sourceKind: "local"
    property var cameraAliases: []
    property bool cameraChoiceReady: false
    property bool cameraPending: false
    property string pendingCamera: ""
    property bool cameraStartup: true
    property var testCameraInputs: null
    readonly property bool imageReady: backgroundImage.status === Image.Ready
    readonly property string backgroundFeedback: {
        if (backgroundMode !== "image" || !imagePath.trim() || imageReady) return ""
        if (backgroundUrl(imagePath) === "" || backgroundImage.status === Image.Error)
            return qsTr("Cannot load this background image. Choose another image.")
        return qsTr("Loading background image…")
    }
    signal request(string action, var args)
    signal snapshotCreated()
    readonly property var cameras: CameraChoice.visibleInputs(testing && testCameraInputs !== null ? testCameraInputs : devices.videoInputs, cameraAliases)
    readonly property real cropFraction: 1 / zoom
    readonly property var captureFormat: processor.item ? processor.item.format : ({})
    property bool previewDecoded: false
    readonly property bool previewReady: previewOn && previewDecoded && processor.item!==null && processor.item.frameUrl!==""
    onPreviewOnChanged: if(!previewOn)previewDecoded=false
    readonly property int cropWidth: captureFormat.captureWidth ? Math.floor(captureFormat.captureWidth / zoom / 2) * 2 : 0
    readonly property int cropHeight: captureFormat.captureHeight ? Math.floor(captureFormat.captureHeight / zoom / 2) * 2 : 0

    onImagePathChanged: {
        backgroundMoveHandle.selected = false
        backgroundPreviewRequestedPath = ""
    }
    onProfileIndexChanged: backgroundMoveHandle.selected = false
    onSectionChanged: {
        if (section !== "background" && section !== "all" && backgroundLabelDialog.visible) backgroundLabelDialog.close()
        backgroundMoveHandle.selected = false
        if (section !== "camera" && section !== "all") backgroundPreviewRequestedPath = ""
        resetScroll()
        if (section === "background" && panelOpen) refreshBackgrounds()
        if (section === "camera" && panelOpen && !testing) snapshotGallery.active = true
        if (section === "remotes" && panelOpen) remoteSources.refresh()
    }
    onPanelOpenChanged: {
        autostartRequested = panelOpen
        if (!panelOpen) {
            if (backgroundLabelDialog.visible) backgroundLabelDialog.close()
            backgroundMoveHandle.selected = false
            backgroundPreviewRequestedPath = ""
            previewOn = false
        } else {
            resetScroll()
            if (publishing) previewOn = true
            else if (section !== "remotes") maybeAutostart()
            if (section === "background") refreshBackgrounds()
            if (section === "camera" && !testing) snapshotGallery.active = true
            if (section === "remotes") remoteSources.refresh()
        }
    }
    onBusyChanged: maybeAutostart()
    onProcessingReadyChanged: maybeAutostart()
    onImageReadyChanged: { maybeAutostart(); if (imageReady && dirty && !automaticWritesPaused) autosave.restart() }
    function maybeAutostart() {
        if(!processingReady)return
        if (section === "remotes") return
        if (!testing && !root.outputControl.checked) return
        if (root.outputControl.busy || root.outputControl.stopping || root.outputControl.startingCamera) return
        if (root.outputControl.state && root.outputControl.state.serviceActive && !root.publishing) return
        if (!autostartRequested || !autostartCamera || !panelOpen || !document || !cameraChoiceReady
            || busy || cameraPending || mirrorPending || autostartPending || sourceKind !== "local"
            || savedCamera === "" || cameraIndex() < 0 || (backgroundMode === "image" && !imageReady)) return
        if (outputControl === noOutput) { autostartRequested = false; previewOn = true }
        else startCamera()
    }

    function deselectLabelOutside(preview, section, scenePosition) {
        if (!preview.moveSelected) return
        const withinSection = section.visible && section.contains(section.mapFromItem(null, scenePosition.x, scenePosition.y))
        if (!withinSection && !preview.containsMoveFrame(scenePosition)) preview.moveSelected = false
    }

    readonly property bool draggingComposition: cameraGrip.dragging || backgroundMoveHandle.dragging
        || previewBackgroundDrag.pressed || quickLabelGrip.dragging
        || labelDisclosure.dragging || backgroundLabelControls.moving
        || interactiveLabel.dragging || backgroundLabelPreview.dragging
        || cropTool.dragging || maskDisclosure.dragging
    Binding {
        target: root.ToolTip.toolTip
        property: "opacity"
        when: root.draggingComposition
        value: 0
    }

    MouseArea {
        parent: root.Window.window ? root.Window.window.contentItem : root
        anchors.fill: parent
        z: 100
        enabled: !backgroundLabelDialog.visible && (root.previewLabelEditing || interactiveLabel.moveSelected)
        visible: enabled
        onPressed: function(mouse) {
            const position = mapToItem(null, mouse.x, mouse.y)
            root.deselectLabelOutside(interactiveLabel, labelDisclosure, position)
            interactiveLabel.commitOutside(position)
            mouse.accepted = false
        }
    }

    component CompositionLabelGrip: LayerMoveHandle {
        required property EditablePreviewLabel preview
        text: qsTr("Label")
        accent: root.accent
        enabled: root.backgroundMode === "image" && root.imageReady && !!root.backgroundLabelOverlay.enabled
            && !!root.backgroundLabelOverlay.text && !root.previewLabelEditing
        readonly property bool engaged: visible && enabled && hovered

        onMovementStarted: {
            backgroundMoveHandle.selected = false
            preview.moveSelected = true
            preview.beginMove()
        }
        onMovementRequested: function(dx, dy) { preview.moveBy(dx, dy) }
    }

    component CompositionLabelControls: LabelControls {
        id: labelControls
        required property EditablePreviewLabel preview
        required property string gripName
        required property string dragName
        readonly property bool gripActive: grip.engaged
        readonly property bool moving: grip.dragging || dragging
        popupPalette: root.popupPalette
        fontFamilies: root.labelFontFamilies
        colorContext: JSON.stringify([root.document ? root.document.activeProfile : "", root.imagePath])
        overlay: root.backgroundLabelOverlay
        available: root.backgroundMode === "image" && root.imageReady
        feedback: root.labelMessage
        onChanged: function(patch) { root.editLabel(patch) }
        onEditRequested: preview.beginEditing()
        leadingControls: CompositionLabelGrip {
            id: grip
            objectName: labelControls.gripName
            dragObjectName: labelControls.dragName
            preview: labelControls.preview
            text: qsTr("Drag Label")
            Accessible.name: text
            hint: qsTr("Drag here or click to show handles on the preview. Hold Shift with an arrow key to move farther.")
        }
    }

    component CompositionLabelSection: DisclosureSection {
        id: labelSection
        required property EditablePreviewLabel preview
        required property string gripName
        required property string dragName
        readonly property bool gripActive: controls.gripActive
        readonly property bool dragging: controls.moving
        title: qsTr("Label")
        hint: qsTr("Show, edit, format, or move the label on the composition.")
        onHeightChanged: if (expanded) Qt.callLater(root.revealDisclosure, labelSection)

        CompositionLabelControls {
            id: controls
            Layout.fillWidth: true
            preview: labelSection.preview
            gripName: labelSection.gripName
            dragName: labelSection.dragName
        }
    }

    component LabelText: Text {
        color: root.palette.windowText; font.pixelSize: 14; textFormat: Text.PlainText
        wrapMode: Text.WordWrap
    }
    function revealDisclosure(section) {
        if (!section.expanded || !section.visible) return
        var viewport = editorScroll.contentItem
        var top = section.mapToItem(editorContent, 0, 0).y
        var minimumTop = top + section.height - editorScroll.availableHeight
        if (minimumTop > viewport.contentY)
            viewport.contentY = Math.min(top, minimumTop)
    }
    function resetScroll() {
        Qt.callLater(function() { if (editorScroll.contentItem) editorScroll.contentItem.contentY = 0 })
    }
    function mark() {
        editGeneration++
        dirty = true
        saveFailed = false
        message = qsTr("Saving changes automatically…")
        if (!automaticWritesPaused) autosave.restart()
    }
    function autosaveWhenReady() {
        if (!dirty || automaticWritesPaused || saveFailed || !document) return
        if (cropSaveFailed || labelSaveFailed) return
        if (busy || savePending || controlIntents.length || cameraPending || mirrorPending || autostartPending || cropInFlight !== null || Object.keys(cropDrafts).length || labelEditing || labelInFlight !== null || Object.keys(labelDrafts).length) { autosave.restart(); return }
        if (!profileName.trim() || (backgroundMode === "image" && !imageReady)) return
        save()
    }
    function prepareUpdate() {
        if (busy || savePending || controlIntents.length || cropInFlight !== null || labelInFlight !== null || labelEditing) return null
        automaticWritesPaused = true
        autosave.stop(); cropSave.stop(); labelSave.stop()
        return exportDraft()
    }
    function resumeAutomaticWrites() {
        automaticWritesPaused = false
        if (dirty) autosave.restart()
        if (Object.keys(cropDrafts).length) cropSave.restart()
        if (Object.keys(labelDrafts).length) labelSave.restart()
    }
    function backgroundUrl(path) {
        var value = path.trim()
        try {
            if (value.indexOf("file://localhost/") === 0) value = decodeURIComponent(value.slice(16))
            else if (value.indexOf("file:///") === 0) value = decodeURIComponent(value.slice(7))
        } catch (error) { return "" }
        if (value.indexOf("/") !== 0) return ""
        return "file://" + value.split("/").map(encodeURIComponent).join("/")
    }
    function chooseBackground(path) {
        if (path.indexOf("file:///") === 0) path = decodeURIComponent(path.slice(7))
        if (imagePath !== path) {
            backgroundCrop = cropFor(path)
            backgroundLabelOverlay = {enabled:false, opacity:0.75, text:""}
        }
        imagePath = path
        backgroundMode = "image"
        syncBackgroundOverlay()
        mark()
    }
    function selectBackgroundForPreview(path) {
        chooseBackground(path)
        if (!panelOpen) return
        cameraTabRequested()
        backgroundPreviewRequestedPath = imagePath
        startSelectedBackgroundPreview()
    }
    function startSelectedBackgroundPreview() {
        if (selectedBackgroundPreviewReady && startCamera())
            backgroundPreviewRequestedPath = ""
    }
    function selectedBackground() {
        return backgroundLibrary.items.find(item => item.path === imagePath)
            || (backgroundLibrary.selected && backgroundLibrary.selected.path === imagePath ? backgroundLibrary.selected : null)
    }
    function labelForBackground(image) {
        const draft = labelDrafts[image.path]
        return draft ? draft.spec : Object.assign({enabled: false, opacity: 0.75}, image.overlay || {}, {
            text: cleanBackgroundLabel(image.label || image.name)
        })
    }
    function cleanBackgroundLabel(text) {
        return text.replace(/[\u0000-\u001f\u007f]/g, " ").slice(0, 256)
    }
    function syncBackgroundOverlay() {
        if (labelDrafts[imagePath]) { backgroundLabelOverlay = labelDrafts[imagePath].spec; return }
        const item = selectedBackground()
        if (!item) return
        const next = labelForBackground(item)
        if (labelIdentity(next) !== labelIdentity(backgroundLabelOverlay)) {
            backgroundLabelOverlay = next
            if (document && backgroundMode === "image") mark()
        }
    }
    function labelIdentity(value) {
        var spec=Object.assign({enabled:false,opacity:.75,text:"",x:.02,y:.96,fontFamily:"sans",fontSize:.034,bold:false,italic:false,allCaps:false,color:"#ffffff"},value)
        return JSON.stringify([spec.enabled,spec.opacity,spec.text,spec.x,spec.y,spec.fontFamily,spec.fontSize,spec.bold,spec.italic,spec.allCaps,spec.color.toLowerCase()])
    }
    function installLibrary(value) {
        if (galleryLabelEditing) { deferredLibrary=value; return }
        backgroundLibrary=value
        syncBackgroundOverlay()
    }
    onGalleryLabelEditingChanged: {
        if (!galleryLabelEditing && deferredLibrary !== null) { var next=deferredLibrary;deferredLibrary=null;installLibrary(next) }
    }
    function editLabel(patch, image = selectedBackground()) {
        if (!image) return
        const next = Object.assign({}, labelForBackground(image), patch)
        const drafts = Object.assign({}, labelDrafts)
        const previous = drafts[image.path]
        const textChanged = patch.text !== undefined
        const savedText = textChanged ? (patch.text === image.name ? "" : patch.text) : previous?.savedText
        if (textChanged && !savedText) next.text = cleanBackgroundLabel(image.name)
        drafts[image.path] = {
            image: image, spec: next, textChanged: textChanged || !!(previous && previous.textChanged), savedText: savedText,
            generation: ++labelGeneration
        }
        labelDrafts = drafts
        if (image.path === imagePath) {
            backgroundLabelOverlay = next
            mark()
        }
        labelSaveFailed = false
        labelMessage = qsTr("Saving label…")
        labelSave.restart()
    }
    function flushLabel() {
        if(automaticWritesPaused || labelSaveFailed)return
        if(busy || labelInFlight!==null || labelEditing){labelSave.restart();return}
        var paths=Object.keys(labelDrafts)
        if(!paths.length)return
        var path=paths[0],draft=labelDrafts[path],payload=Object.assign({},draft.spec)
        if(!draft.textChanged)delete payload.text
        else if (draft.savedText !== undefined) payload.text = draft.savedText
        labelInFlight={path:path,generation:draft.generation}
        request("background-overlay",["--path",draft.image.path,"--id",draft.image.id,"--overlay",JSON.stringify(payload)])
    }
    function cropFor(path, fallback) {
        if (cropDrafts[path]) return cropDrafts[path]
        for (var i = 0; i < backgroundLibrary.items.length; i++)
            if (backgroundLibrary.items[i].path === path) return backgroundLibrary.items[i].crop
        if (backgroundLibrary.selected && backgroundLibrary.selected.path === path && backgroundLibrary.selected.hasCrop) return backgroundLibrary.selected.crop
        return fallback || {zoom: 1, centerX: 0.5, centerY: 0.5}
    }
    function editBackgroundCrop(value) {
        backgroundCrop = value
        var drafts = Object.assign({}, cropDrafts)
        drafts[imagePath] = value
        cropDrafts = drafts
        cropMessage = qsTr("Saving background framing…")
        cropSaveFailed = false
        mark()
        cropSave.restart()
    }
    function flushBackgroundCrop() {
        if (automaticWritesPaused) return
        if (busy || cropInFlight !== null) { cropSave.restart(); return }
        var paths = Object.keys(cropDrafts)
        if (!paths.length) return
        var path = paths[0], value = cropDrafts[path]
        cropInFlight = {path: path, crop: value}
        request("background-crop", ["--path", path, "--crop", JSON.stringify(value)])
    }
    function cropBackground(image) {
        chooseBackground(image.path)
        cropTool.target="background"
        Qt.callLater(cropTool.openEditor)
    }
    signal cameraTabRequested()
    function lockBackground(image) {
        request("lock-background", ["--path", image.path, "--id", image.id, "--locked", String(!image.locked)])
    }
    function overlayBackground(image, enabled, opacity) { request("background-overlay", ["--path", image.path, "--id", image.id, "--overlay", JSON.stringify({enabled: enabled, opacity: opacity})]) }
    function requestTrash(image) {
        trashCandidate = image
        var referenced = document && document.profiles.some(p => p.background.mode === "image" && p.background.imagePath === image.path)
        if (image.path === imagePath || referenced) trashBackgroundDialog.open()
        else trashBackground()
    }
    function trashBackground() {
        if (!trashCandidate) return
        request("trash-background", ["--path", trashCandidate.path, "--id", trashCandidate.id])
    }
    function refreshBackgrounds() {
        if(!processingReady)return
        if (busy || libraryPending) { libraryRefresh.restart(); return }
        libraryPending = true
        if (!backgroundLibrary.directory) libraryMessage = qsTr("Loading backgrounds…")
        request("backgrounds", imagePath ? ["--selected-path", imagePath] : [])
    }
    function addBackgrounds(paths) {
        if (busy || libraryPending) return
        libraryPending = true
        libraryMessage = qsTr("Copying and verifying backgrounds…")
        request("add-backgrounds", ["--paths", JSON.stringify(paths)])
    }
    function backgroundPreviewSettings(image) {
        return { mode: "image", imagePath: image.path, crop: cropFor(image.path), labelOverlay: labelForBackground(image) }
    }
    function previewSettings() {
        if (backgroundMode === "image" && !imageReady) return null
        return { camera: savedCamera, mirror: mirror, foreground: foreground, crop: { zoom: zoom, centerX: centerX, centerY: centerY },
            sourcePreview: cropTool.sourcePreviewRequested,
            personMask: personMask,
            background: { mode: backgroundMode, imagePath: imagePath, crop: backgroundCrop, labelOverlay: backgroundLabelOverlay } }
    }
    function adjustPersonMask(next) {
        if (next.softness === personMask.softness && next.tightness === personMask.tightness) return
        personMask = next
        mark()
    }
    function placeForeground(x, y) {
        foreground = {x: Math.max(-1, Math.min(1, x)), y: Math.max(-1, Math.min(1, y))}
        mark()
    }
    function resetFrame() { foreground = {x:0, y:0}; frame(1, 0.5, 0.5) }
    function frame(z, x, y) {
        zoom = Math.max(1, Math.min(4, z))
        var edge = 0.5 / zoom
        centerX = Math.max(edge, Math.min(1 - edge, x))
        centerY = Math.max(edge, Math.min(1 - edge, y))
        mark()
    }
    function restore(index) {
        if (!document || !document.profiles[index]) return
        profileIndex = index
        var p = document.profiles[index]
        if (savedCamera !== p.source.camera && !cameraOutputActive) previewOn = false
        zoom = p.crop.zoom; centerX = p.crop.centerX; centerY = p.crop.centerY
        foreground = p.foreground || {x:0, y:0}
        profileName = p.name; backgroundMode = p.background.mode; imagePath = p.background.imagePath
        personMask = p.personMask || defaultPersonMask
        backgroundCrop = cropFor(imagePath, p.background.crop)
        backgroundLabelOverlay = p.background.labelOverlay || {enabled: false, opacity: 0.75, text: ""}
        savedCamera = p.source.camera; sourceHost = p.source.host; sourceKind = p.source.kind
        if (sourceKind === "remote") remoteBrowse = true
        restoreOnStart = p.restoreOnStart
        mirror = p.mirror === undefined ? true : p.mirror
        autostartCamera = p.autostartCamera === undefined ? true : p.autostartCamera
        dirty = false
        syncBackgroundOverlay()
        if (cameraChoiceReady) chooseCamera()
    }
    function accept(action, result) {
        if (action === "background-crop") {
            var drafts = Object.assign({}, cropDrafts)
            var path=cropInFlight?cropInFlight.path:result.path
            var pending=drafts[path],confirmed=result.crop
            if(pending && confirmed && Math.abs(pending.zoom-confirmed.zoom)<1e-12 && Math.abs(pending.centerX-confirmed.centerX)<1e-12 && Math.abs(pending.centerY-confirmed.centerY)<1e-12)delete drafts[path]
            cropDrafts = drafts
            cropInFlight = null
            var updated = JSON.parse(JSON.stringify(backgroundLibrary))
            for (var i = 0; i < updated.items.length; i++)
                if (updated.items[i].id === result.id) updated.items[i].crop = result.crop
            installLibrary(updated)
            cropMessage = qsTr("Background framing saved for this image")
            cropSaveFailed = false
            if (Object.keys(cropDrafts).length) cropSave.restart()
            else if (dirty && !automaticWritesPaused) autosave.restart()
            return
        }
        if (action === "lock-background" || action === "trash-background" || action === "label-background" || action === "background-overlay") {
            if(action==="background-overlay" && labelInFlight!==null){
                var labels=Object.assign({},labelDrafts)
                if(labels[labelInFlight.path] && labels[labelInFlight.path].generation===labelInFlight.generation)delete labels[labelInFlight.path]
                labelDrafts=labels;labelInFlight=null;labelSaveFailed=false;labelMessage=qsTr("Label saved")
                if(Object.keys(labelDrafts).length)labelSave.restart()
                if(dirty&&!automaticWritesPaused)autosave.restart()
            }
            var selected = backgroundLibrary.selected
            if (selected && selected.path === imagePath) {
                var matching = result.items.find(i => i.id === selected.id)
                if (matching) { result.selected = Object.assign({}, selected, {locked:matching.locked, label:matching.label, overlay:matching.overlay, crop:matching.crop}) }
            }
            installLibrary(result)
            if (action === "trash-background") {
                var currentId = document.profiles[profileIndex].id
                var recovered = JSON.parse(JSON.stringify(result.document))
                recovered.profiles = recovered.profiles.concat(document.profiles.filter(p => !recovered.profiles.some(saved => saved.id === p.id)))
                document = recovered
                profileIndex = Math.max(0, document.profiles.findIndex(p => p.id === currentId))
                if (result.trashError) {
                    dirty = true
                    libraryMessage = result.trashError
                    root.message = result.trashError
                    return
                }
                if (imagePath === result.trashedPath) {
                    backgroundMode = "blur"; imagePath = ""; backgroundCrop = {zoom:1, centerX:0.5, centerY:0.5}
                    if (!result.replacedProfiles.includes(document.profiles[profileIndex].id)) dirty = true
                }
                libraryMessage = qsTr("Image moved to your Trash")
                if (result.cleanupWarning) libraryMessage += "\n" + result.cleanupWarning
                trashCandidate = null
            } else libraryMessage = action === "background-overlay" ? qsTr("Label overlay saved and verified") : action === "label-background" ? qsTr("Background label saved") : qsTr("Background lock saved and verified")
            return
        }
        if (action === "backgrounds" || action === "add-backgrounds") {
            libraryPending = false
            if (JSON.stringify(backgroundLibrary) !== JSON.stringify(result)) installLibrary(result)
            if (result.selected && result.selected.path === imagePath && result.selected.hasCrop && !cropDrafts[imagePath]) backgroundCrop = result.selected.crop
            var notices = []
            if (action === "add-backgrounds") {
                if (result.added.length) {
                    chooseBackground(result.added[0].path)
                    notices.push(qsTr("Images copied and verified. Selection saves automatically."))
                }
                if (result.errors.length)
                    notices.push(result.errors.map(e => e.name + ": " + e.message).join("\n"))
            }
            if (result.limited) notices.push(qsTr("Showing the first 512 images."))
            if (result.unreadable.length) notices.push(qsTr("Some files are not ready or readable yet. They will be checked again automatically."))
            libraryMessage = notices.join("\n")
            return
        }
        if (action === "read" || action === "save") {
            if (action === "read") { cameraStartup = true; cameraChoiceReady = false }
            document = result
            if (cameraPending && action === "save") {
                cameraPending = false
                if (savedCamera !== pendingCamera && !publishing) previewOn = false
                savedCamera = pendingCamera
                sourceKind = "local"; sourceHost = ""
                message = qsTr("Camera ready")
                maybeAutostart()
                return
            }
            if (autostartPending && action === "save") {
                autostartPending = false
                autostartCamera = result.profiles[profileIndex].autostartCamera
                autostartRequested = autostartCamera
                message = qsTr("Autostart camera setting saved")
                maybeAutostart()
                return
            }
            if (mirrorPending && action === "save") {
                mirrorPending = false
                mirror = result.profiles[profileIndex].mirror
                message = qsTr("Mirror setting saved")
                return
            }
            if (action === "save" && savePending) {
                savePending = false
                saveFailed = false
                if (editGeneration !== saveGeneration) {
                    dirty = true
                    message = qsTr("Saving the latest changes…")
                    if (!automaticWritesPaused) autosave.restart()
                    return
                }
            }
            var index = result.profiles.findIndex(p => p.id === result.activeProfile)
            restore(Math.max(0, index))
            lastSaveDetails = action === "save"
                ? qsTr("Saved to disk and verified · revision %1").arg(result.revision)
                : result.revision === 0 ? qsTr("New profile. Changes save automatically.")
                : qsTr("Loaded from disk · revision %1").arg(result.revision)
            message = ""
            if (action === "read") { refreshCameraInventory(); if (backgroundMode === "image") refreshBackgrounds() }
        } else if (action === "devices") {
            cameraAliases = result.aliases || []
            cameraChoiceReady = true
            chooseCamera()
        }
    }
    function draftDocument() {
        if (!document) return null
        var next = JSON.parse(JSON.stringify(document))
        var p = next.profiles[profileIndex]
        p.name = profileName
        p.crop = { zoom: zoom, centerX: centerX, centerY: centerY }
        p.foreground = foreground
        if (personMask.softness || personMask.tightness) p.personMask = personMask
        else delete p.personMask
        p.background = { mode: backgroundMode, imagePath: imagePath, crop: backgroundCrop, labelOverlay: backgroundLabelOverlay }
        p.source = { kind: sourceKind, host: sourceHost, camera: savedCamera }
        p.restoreOnStart = restoreOnStart
        p.mirror = mirror
        p.autostartCamera = autostartCamera
        next.activeProfile = p.id
        return next
    }
    function exportDraft() {
        if (busy || !document) return null
        return {schemaVersion: 1, document: draftDocument(), dirty: dirty, crops: cropDrafts, labels:labelDrafts}
    }
    function restoreDraft(snapshot) {
        if (busy || !document || !snapshot || snapshot.schemaVersion !== 1 || !snapshot.document
            || snapshot.document.revision !== document.revision || !Array.isArray(snapshot.document.profiles)
            || !snapshot.document.profiles.length) return false
        var index = snapshot.document.profiles.findIndex(p => p.id === snapshot.document.activeProfile)
        if (index < 0) return false
        var candidate = snapshot.document.profiles[index]
        if (!candidate.crop || !candidate.background || !candidate.source || typeof candidate.name !== "string") return false
        document = snapshot.document
        cropDrafts = snapshot.crops || {}
        labelDrafts = snapshot.labels || {}
        restore(index)
        dirty = !!snapshot.dirty
        message = dirty ? qsTr("Unsaved adjustments recovered") : qsTr("Profile restored from disk")
        if (Object.keys(cropDrafts).length) cropSave.restart()
        if (Object.keys(labelDrafts).length) labelSave.restart()
        if (dirty && !automaticWritesPaused) autosave.restart()
        return true
    }
    function save() {
        if (!document || busy) return
        var next = draftDocument()
        saveGeneration = editGeneration
        savePending = true
        saveFailed = false
        message = qsTr("Saving and verifying…")
        request("save", ["--document", JSON.stringify(next)])
    }
    function toggleMirror() {
        if (!document || mirrorPending || mirrorQueued || cameraPending || autostartPending) return
        if(busy||savePending){mirrorQueued=true;controlIntents=controlIntents.concat([{kind:"mirror"}]);controlIntentTimer.restart();return}
        var next = JSON.parse(JSON.stringify(document))
        next.profiles[profileIndex].mirror = !mirror
        mirrorPending = true
        message = qsTr("Saving mirror setting…")
        request("save", ["--document", JSON.stringify(next)])
    }
    function toggleAutostart() {
        if (!document || mirrorPending || cameraPending || autostartPending || autostartQueued) return
        if(busy||savePending){autostartQueued=true;controlIntents=controlIntents.concat([{kind:"autostart"}]);controlIntentTimer.restart();return}
        var next = JSON.parse(JSON.stringify(document))
        next.profiles[profileIndex].autostartCamera = !autostartCamera
        autostartPending = true
        message = qsTr("Saving autostart camera setting…")
        request("save", ["--document", JSON.stringify(next)])
    }
    function fail(message) {
        if(labelInFlight!==null){labelInFlight=null;labelSaveFailed=true;labelMessage=qsTr("Could not save label: ")+message}
        if (savePending) { savePending = false; saveFailed = true }
        if (cropInFlight !== null) { cropInFlight = null; cropSaveFailed = true; cropMessage = qsTr("Could not save background framing: ") + message }
        if (libraryPending) { libraryPending = false; libraryMessage = message }
        mirrorPending = false
        cameraPending = false
        autostartPending = false
        root.message = message
    }
    function refreshCameraInventory() {
        if (!document || testing) return
        if (busy || mirrorPending || cameraPending || autostartPending) { cameraRefresh.restart(); return }
        request("devices", [])
    }
    function cameraIndex() {
        for (var i = 0; i < cameras.length; i++)
            if (String(cameras[i].id) === savedCamera) return i
        return -1
    }
    function chooseCamera() {
        if (sourceKind === "remote") return
        if (!document || !cameraChoiceReady || mirrorPending || cameraPending || autostartPending) return
        var id = CameraChoice.pick(cameras, cameraAliases, document.lastCamera || "", cameraStartup ? "" : savedCamera,
            document.profiles[profileIndex].source.camera, String(devices.defaultVideoInput.id))
        cameraStartup = false
        if (id === "") {
            if (cameraOutputActive) return
            previewOn = false; savedCamera = ""; message = qsTr("Connect a webcam to get started."); return
        }
        var key = CameraChoice.keyFor(id, cameraAliases)
        if (document.lastCamera === key && document.profiles[profileIndex].source.camera === id) {
            if (savedCamera !== id && !cameraOutputActive) previewOn = false
            savedCamera = id
            sourceKind = "local"; sourceHost = ""
            maybeAutostart()
            return
        }
        selectCamera(id)
    }
    function selectCamera(id) {
        if (!document || mirrorPending || cameraPending || autostartPending || cameraQueued) return
        if(busy||savePending){cameraQueued=true;controlIntents=controlIntents.concat([{kind:"camera",camera:id}]);controlIntentTimer.restart();return}
        var next = JSON.parse(JSON.stringify(document))
        next.lastCamera = CameraChoice.keyFor(id, cameraAliases)
        next.profiles[profileIndex].source = { kind: "local", host: "", camera: id }
        next.activeProfile = next.profiles[profileIndex].id
        cameraPending = true
        pendingCamera = id
        message = qsTr("Remembering camera choice…")
        request("save", ["--document", JSON.stringify(next)])
    }
    function newProfile() {
        if (!document || dirty) return
        var next = JSON.parse(JSON.stringify(document))
        var p = JSON.parse(JSON.stringify(next.profiles[profileIndex]))
        p.id = "profile-" + Date.now(); p.name = qsTr("New profile")
        next.profiles.push(p); document = next
        restore(next.profiles.length - 1); mark()
    }
    MediaDevices { id: devices; onVideoInputsChanged: cameraRefresh.restart() }
    Timer { id: autosave; interval: 750; onTriggered: root.autosaveWhenReady() }
    Timer {
        id:controlIntentTimer
        interval:60
        onTriggered:{
            if(root.busy||root.savePending||root.mirrorPending||root.cameraPending||root.autostartPending){restart();return}
            if(!root.controlIntents.length)return
            var intent=root.controlIntents[0];root.controlIntents=root.controlIntents.slice(1)
            if(intent.kind==="mirror"){root.mirrorQueued=false;root.toggleMirror()}
            else if(intent.kind==="autostart"){root.autostartQueued=false;root.toggleAutostart()}
            else{root.cameraQueued=false;root.selectCamera(intent.camera)}
            if(root.controlIntents.length)restart()
        }
    }
    Timer { id: cropSave; interval: 400; onTriggered: root.flushBackgroundCrop() }
    Timer { id: labelSave; interval: 400; onTriggered: root.flushLabel() }
    Timer { id: libraryRefresh; interval: 200; onTriggered: root.refreshBackgrounds() }
    Timer { id: cameraRefresh; interval: 200; onTriggered: root.refreshCameraInventory() }
    Connections {
        target:root.outputControl
        ignoreUnknownSignals:true
        function onStarting(){root.resumeOutputPreview=root.resumeOutputPreview||root.panelOpen;root.autostartRequested=false;root.previewOn=false;root.message=qsTr("Starting saved camera…")}
        function onStarted(){root.message="";if(root.resumeOutputPreview&&root.panelOpen)root.previewOn=true}
        function onStopped(){root.resumeOutputPreview=false;if(root.publishing||root.previewOn)root.previewOn=false}
        function onCheckedChanged(){root.maybeAutostart()}
        function onReadyToStartChanged(){root.maybeAutostart()}
        function onBusyChanged(){root.maybeAutostart()}
        function onStateChanged(){root.maybeAutostart()}
        function onPublishedChanged() {
            if (root.publishing && root.panelOpen && !root.outputControl.stopping) root.previewOn = true
            else root.maybeAutostart()
        }
        function onFailed(message){root.message=message}
        function onCameraRejected(camera){
            if(root.remoteConnecting)root.rejectRemote(root.outputControl.cameraFeedback)
            else if(camera.indexOf("sshcam:")!==0)root.selectCamera(camera)
            else{
                root.savedCamera=camera;root.sourceKind="remote";root.sourceHost=camera.split("/")[2].split("?")[0]
                root.remoteFeedback=root.outputControl.cameraFeedback;root.mark()
            }
        }
    }
    Loader {
        id: processor
        active: root.previewOn && root.panelOpen && (root.section === "camera" || root.section === "remotes" || root.section === "all") && !root.testing
        source: Qt.resolvedUrl("ProcessedPreview.qml")
        onLoaded: {
            item.sharedOutput = Qt.binding(function() {return root.cameraOutputActive})
            item.outputRevision = Qt.binding(function() {return root.outputControl.configurationRevision})
            item.adjustingBackground = Qt.binding(function() {return root.adjustingBackground})
            item.configuration = Qt.binding(function() { return root.previewSettings() })
            item.active = true
        }
    }
    Connections {
        target: processor.item
        function onFailed(message) {
            root.previewOn = false; root.message = message
            if (root.sourceKind === "remote") root.rejectRemote(qsTr("Remote video stopped: %1").arg(message))
        }
        function onConfigurationRejected(camera, message) {
            if (root.remoteConnecting) root.rejectRemote(qsTr("Could not connect: %1").arg(message))
            else root.message = message
        }
        function onFrameReceived(mode) {
            if (root.remoteConnecting && processor.item && processor.item.cameraSource === root.savedCamera) {
                root.remoteConnecting = false; root.previousSource = null
                root.remoteFeedback = qsTr("Connected to %1 · video only").arg(root.sourceHost)
            }
        }
        function onSnapshotFailed(message) { root.message = message }
        function onSnapshotSaved(result) {
            root.snapshotCreated()
            if (snapshotGallery.item) snapshotGallery.item.refresh()
            root.snapshotDirectory = result.path.slice(0, result.path.lastIndexOf("/"))
            root.message = result.mirrored ? qsTr("Snapshot saved. Copy added to Screenshots.") : qsTr("Snapshot saved.")
            if (result.recentError) console.warn("WebcamTuner:", result.recentError)
            if (result.mirrorError) {
                console.warn("WebcamTuner:", result.mirrorError)
                root.message = qsTr("Snapshot saved. Couldn’t copy it to Screenshots.")
            }
        }
    }
    ColumnLayout {
        id: footer
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 22
        height: implicitHeight
        visible: implicitHeight > 0
        spacing: 6
        LabelText {
            objectName: "saveStatus"
            visible: text !== ""
            text: root.message
            color: root.accent
            Layout.fillWidth: true
            maximumLineCount: 3
            elide: Text.ElideRight
        }
        RowLayout {
            id: profileActions
            Layout.fillWidth: true
            visible: root.section === "background" ? root.saveFailed || root.labelSaveFailed : root.profileNeedsAttention
            LabelText {
                objectName: "profileSaveState"
                text: !root.document ? (!root.processingReady && root.section === "setup" ? qsTr("Setup needed") : qsTr("Loading…"))
                    : root.saveFailed || root.labelSaveFailed ? qsTr("Could not save")
                    : root.savePending ? qsTr("Saving…")
                    : root.dirty ? (root.profileName.trim() ? qsTr("Waiting to save…") : qsTr("Name this profile"))
                    : qsTr("Saved")
                color: root.saveFailed || root.labelSaveFailed ? root.palette.linkVisited : root.accent
                Layout.preferredWidth: Math.min(160, implicitWidth)
            }
            Button {
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: qsTr("Try saving the current changes again.")
                visible:root.saveFailed||root.labelSaveFailed
                text:qsTr("Retry")
                enabled:!root.busy
                onClicked:{if(root.labelSaveFailed){root.labelSaveFailed=false;root.flushLabel()}else root.save()}
            }
            Item { Layout.fillWidth: true }
        }
    }
    ScrollView {
        id: editorScroll
        objectName: "editorScroll"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: footer.visible ? footer.top : parent.bottom
        anchors.margins: 22
        clip: true
        contentWidth: availableWidth
        contentHeight: editorContent.implicitHeight
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        ScrollBar.vertical: VisibleScrollBar {
            ink: root.accent
            objectName: "editorScrollbar"
            parent: root
            x: editorScroll.x + editorScroll.width + (editorScroll.anchors.rightMargin - width) / 2
            y: editorScroll.y
            width: 12
            height: editorScroll.height
            active: true
            policy: editorScroll.contentHeight > editorScroll.availableHeight ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
        }
        ColumnLayout {
            id: editorContent
            width: editorScroll.availableWidth
            height: implicitHeight
            spacing: 14
            LabelText {
                id: pageIntro
                objectName: "pageIntro"
                visible: root.section !== "background"
                text: root.section === "setup" ? qsTr("Prepare WebcamTuner and connect your output to other apps.")
                    : root.section === "background" ? ""
                    : root.section === "camera" || root.section === "all"
                        ? qsTr("Customize your webcam feed:")
                        : qsTr("Customize your webcam feed! Look for a new camera feed in Zoom, Teams and Google Meet called WebcamTuner.")
                color: root.palette.placeholderText
                Layout.fillWidth: true
            }
            RowLayout {
                id: profileRow
                visible: root.section === "camera" || root.section === "all"
                Layout.fillWidth: true
                ComboBox {
                    id: profileChoice; objectName: "profileChoice"
                    Layout.preferredWidth: 145
                    model: root.document ? root.document.profiles : []
                    textRole: "name"; currentIndex: root.profileIndex
                    enabled: !root.publishing && !root.outputControl.busy && !root.dirty && !root.busy
                    onActivated: function(index) { root.restore(index); root.mark() }
                }
                TextField {
                    objectName: "profileName"; Layout.fillWidth: true
                    text: root.profileName; placeholderText: qsTr("Profile name")
                    maximumLength: 80
                    onTextEdited: { root.profileName = text; root.mark() }
                }
                Button {
                    hoverEnabled: true
                    ToolTip.visible: hovered
                    ToolTip.delay: 500
                    ToolTip.text: qsTr("Create a new camera profile.")
                    text: qsTr("New")
                    enabled: !root.dirty && !root.busy && root.document && root.document.profiles.length < 30
                    onClicked: root.newProfile()
                }
            }
            ColumnLayout {
                id: cameraPanel
                Layout.fillWidth: true
                visible: root.section === "all" || root.section === "camera" || root.section === "remotes"
                RowLayout {
                    id: cameraSelectorRow
                    Layout.fillWidth: true
                    visible: root.section !== "remotes"
                    ComboBox {
                        objectName: "cameraSourceChoice"
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        Accessible.name: qsTr("Computer")
                        model: [root.localSourceLabel, qsTr("Remote computer")]
                        currentIndex: root.remoteBrowse ? 1 : 0
                        onActivated: function(index) { root.remoteBrowse = index === 1; if(root.remoteBrowse)remoteSources.refresh() }
                    }
                    ComboBox {
                        objectName: "cameraChoice"
                        visible: !root.remoteBrowse
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        Accessible.name: qsTr("Camera")
                        model: root.cameras; textRole: "description"
                        currentIndex: root.cameraIndex()
                        enabled: !root.remoteConnecting && !root.outputControl.busy && !root.outputControl.cameraSwitching && root.cameraChoiceReady && !root.cameraQueued && !root.mirrorQueued && !root.autostartQueued && !root.cameraPending && !root.mirrorPending && !root.autostartPending
                        displayText: root.cameraPending || root.cameraQueued || root.outputControl.cameraSwitching ? qsTr("Selecting camera…") : root.cameraChoiceReady && root.cameras.length === 0 ? qsTr("No webcam connected") : currentIndex < 0 ? qsTr("Detecting connected webcams…") : currentText
                        onActivated: function(index) {
                            var id = String(root.cameras[index].id)
                            currentIndex = Qt.binding(function() { return root.cameraIndex() })
                            root.selectCamera(id)
                        }
                    }
                }
                RemoteSources {
                    id: remoteSources; objectName: "remoteSources"
                    Layout.fillWidth: true; visible: root.section === "remotes" || root.remoteBrowse; accent: root.accent; testing: root.testing
                    connecting: root.remoteConnecting; connected: root.remoteConnected
                    activeSource: root.savedCamera
                    connectionFeedback: root.remoteConnected ? qsTr("Connected to %1 · video only").arg(root.sourceHost) : root.remoteFeedback
                    onConnectCamera: function(uri,host) {root.connectRemote(uri,host)}
                    onDisconnectCamera: root.disconnectRemote()
                }
                Flow {
                    id: cameraControlButtons
                    Layout.fillWidth: true
                    spacing: 8
                    Button {
                        hoverEnabled: true
                        ToolTip.visible: hovered
                        ToolTip.delay: 500
                        readonly property bool canStop: root.cameraOutputActive || root.previewOn
                        ToolTip.text: root.publishing ? qsTr("Camera is live and shared with apps as WebCamTuner.")
                            : canStop ? qsTr("Stop camera output.")
                            : qsTr("Publish WebcamTuner as a camera for other apps.")
                        objectName: "cameraPowerButton"
                        text: root.outputControl.stopping ? qsTr("Stopping camera…")
                            : canStop ? qsTr("Stop Camera") : qsTr("Start Camera")
                        enabled: !root.outputControl.stopping && (canStop || (!root.outputControl.busy
                            && root.processingReady && root.sourceReady && !root.remoteConnecting && !root.cameraPending
                            && root.savedCamera !== "" && !root.testing && (root.backgroundMode !== "image" || root.imageReady)))
                        onClicked: canStop ? root.stopCamera() : root.startCamera()
                    }
                }
                LabelText {
                    id: cameraPowerLabel
                    objectName: "cameraPowerStatus"
                    Layout.fillWidth: true
                    visible: text !== ""
                    text: root.outputControl.stopping ? qsTr("Stopping the camera and its shared output…")
                        : !root.outputControl.checked ? qsTr("Checking camera status…")
                        : root.outputControl.startingCamera ? qsTr("Starting shared camera output…")
                        : root.publishing ? ""
                        : root.previewOn ? qsTr("Preview only. Camera output is not shared with apps.")
                        : qsTr("Camera stopped. Start Camera to make WebcamTuner available to apps.")
                }
                LabelText {
                    id: cameraFeedback
                    text: root.outputControl.cameraFeedback || ""
                    visible: text !== ""
                    Layout.fillWidth: true
                    color: root.accent
                }
                Item {
                    objectName: "cameraPreviewArea"
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(width * 9 / 16, Math.max(Math.min(200, width * 9 / 16), editorScroll.availableHeight
                        - pageIntro.implicitHeight - profileRow.implicitHeight - cameraSelectorRow.implicitHeight
                        - cameraControlButtons.implicitHeight
                        - (cameraPowerLabel.visible ? cameraPowerLabel.implicitHeight + cameraPanel.spacing : 0)
                        - (cameraFeedback.visible ? cameraFeedback.implicitHeight + cameraPanel.spacing : 0)
                        - cropDisclosure.collapsedHeight - profileDisclosure.collapsedHeight
                        - labelDisclosure.collapsedHeight - maskDisclosure.collapsedHeight
                        - snapshotsDisclosure.collapsedHeight - layerMovement.implicitHeight
                        - 2 * editorContent.spacing - 8 * cameraPanel.spacing))
                    Rectangle {
                    id: stage
                    objectName: "cameraCompositionStage"
                    anchors.centerIn: parent
                    width: Math.min(parent.width, parent.height * 16 / 9)
                    height: width * 9 / 16
                    color: "#0e131b"; clip: true
                    Item {
                        id: compositionLayer
                        objectName: "cameraCompositionLayer"
                        anchors.fill: parent
                        transform: Scale { origin.x: compositionLayer.width / 2; xScale: root.mirror ? -1 : 1 }
                        Image {
                            id: backgroundImage
                            objectName: "backgroundImage"
                            property real cover: implicitWidth>0&&implicitHeight>0 ? Math.max(stage.width/implicitWidth,stage.height/implicitHeight)*root.backgroundCrop.zoom : 1
                            width:implicitWidth*cover; height:implicitHeight*cover
                            x: Math.min(0, Math.max(stage.width - width, stage.width / 2 - root.backgroundCrop.centerX * width))
                            y: Math.min(0, Math.max(stage.height - height, stage.height / 2 - root.backgroundCrop.centerY * height))
                            source: root.backgroundMode === "image" ? root.backgroundUrl(root.imagePath) : ""
                            fillMode: Image.PreserveAspectFit
                            asynchronous: true
                            autoTransform: true
                            onStatusChanged: if (status === Image.Error && root.backgroundPreviewRequestedPath) {
                                root.backgroundPreviewRequestedPath = ""
                                root.message = root.backgroundFeedback
                            }
                            sourceSize.width: 1280
                            sourceSize.height: 720
                            visible: root.backgroundMode === "image" && !root.previewOn && !root.publishing
                        }
                        Item {
                            anchors.fill: parent
                            transform: Translate { x: root.foreground.x * stage.width; y: root.foreground.y * stage.height }
                        Item {
                            id: source
                            visible: (!root.previewOn || root.testing) && !root.publishing
                            width: stage.width * root.zoom; height: stage.height * root.zoom
                            x: stage.width / 2 - root.centerX * width
                            y: stage.height / 2 - root.centerY * height
                            Rectangle {
                                anchors.fill: parent
                                color: "transparent"
                                Rectangle {
                                    anchors.fill: parent
                                    visible: root.backgroundMode !== "image" || !root.imageReady
                                    gradient: Gradient { GradientStop { position: 0; color: "#314d53" } GradientStop { position: 1; color: "#17232c" } }
                                    Repeater {
                                        model: 9
                                        Rectangle { required property int index; x: source.width * (index + 1) / 10; width: 1; height: source.height; color: "#52676c"; opacity: 0.35 }
                                    }
                                }
                                Rectangle { x: parent.width * 0.43; y: parent.height * 0.24; width: parent.width * 0.14; height: width; radius: width / 2; color: "#b3c8c4" }
                                Rectangle { x: parent.width * 0.30; y: parent.height * 0.53; width: parent.width * 0.40; height: parent.height * 0.65; radius: width * 0.3; color: "#88a5a3" }
                            }
                        }
                        }
                        PreviewFrame {
                            objectName: "processedFrame"
                            anchors.fill: parent
                            visible: root.previewOn
                            source: processor.item ? processor.item.frameUrl : ""
                            onFrameDecoded: {root.previewDecoded=true;fpsBadge.frameReady()}
                        }
                        MouseArea {
                            anchors.fill: parent
                            acceptedButtons: Qt.NoButton
                            onWheel: function(wheel) {
                                if (!(wheel.modifiers & Qt.ControlModifier)) {
                                    var flick = editorScroll.contentItem
                                    var amount = wheel.pixelDelta.y ? -wheel.pixelDelta.y : -wheel.angleDelta.y / 120 * 64
                                    flick.contentY = Math.max(0, Math.min(flick.contentHeight - flick.height, flick.contentY + amount))
                                    wheel.accepted = true; return
                                }
                                cropTool.changeZoom(cropTool.selectedCrop.zoom*(wheel.angleDelta.y>0?1.1:1/1.1)); wheel.accepted=true }
                        }
                        MouseArea {
                            id: previewBackgroundDrag
                            objectName: "previewBackgroundDrag"
                            anchors.fill: parent
                            z: 1
                            enabled: backgroundMoveHandle.enabled && backgroundMoveHandle.selected
                                && backgroundMoveHandle.canPan && (!root.publishing || root.previewOn)
                            preventStealing: true
                            hoverEnabled: true
                            cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                            property point startPointer

                            onPressed: function(mouse) {
                                startPointer = mapToItem(null, mouse.x, mouse.y)
                                backgroundMoveHandle.beginPan()
                            }
                            onPositionChanged: function(mouse) {
                                if (!pressed) return
                                const point = mapToItem(null, mouse.x, mouse.y)
                                backgroundMoveHandle.pan(point.x - startPointer.x, point.y - startPointer.y)
                            }
                            onReleased: backgroundMoveHandle.panning = false
                            onCanceled: backgroundMoveHandle.panning = false
                        }
                        EditablePreviewLabel {
                            id:interactiveLabel
                            mirrored:root.mirror
                            showMoveHandles: labelDisclosure.gripActive || quickLabelGrip.engaged
                            moveAccent: root.accent
                            presentationVisible:root.previewOn||!root.publishing
                            anchors.fill:parent
                            z:2
                            overlay:root.backgroundMode==="image"?root.backgroundLabelOverlay:({enabled:false})
                            onChanged:function(patch){root.editLabel(patch)}
                            onEditingStateChanged:function(active){root.previewLabelEditing=active}
                        }
                    }
                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 14
                        width: reconnectNotice.implicitWidth + 20
                        height: reconnectNotice.implicitHeight + 12
                        radius: 4
                        color: root.palette.window
                        visible: root.previewOn && processor.item !== null && processor.item.reconnecting
                        LabelText {
                            id: reconnectNotice
                            text: qsTr("Reconnecting preview…")
                            anchors.centerIn: parent
                        }
                    }
                    FpsIndicator {
                        id: fpsBadge
                        active: root.previewOn
                        visible: active && !root.draggingComposition
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 10
                    }
                    BackendIndicator {
                        id: backendBadge
                        visible: fpsBadge.visible
                        provider: root.captureFormat.provider || ""
                        anchors.right: fpsBadge.right
                        anchors.top: fpsBadge.bottom
                        anchors.topMargin: 4
                    }
                    LabelText {
                        anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 12
                        visible:!root.previewOn && !root.publishing && stage.width>=380
                        text: root.previewOn ? (processor.item && processor.item.frameUrl !== "" ? qsTr("Processed camera preview") : qsTr("Starting camera…")) : qsTr("Framing test card · camera off")
                        font.pixelSize: 10; font.bold: true; color: "#e9ecef"
                    }
                    LabelText {
                        objectName: "previewZoomIndicator"
                        visible: !root.draggingComposition
                        color: "#e9ecef"
                        anchors.right: fpsBadge.right
                        anchors.top: backendBadge.visible ? backendBadge.bottom : parent.top
                        anchors.topMargin: backendBadge.visible ? 4 : 10
                        text: root.zoom.toFixed(2) + "×"
                        font.bold: true
                    }
                }
                }
                RowLayout {
                    id: layerMovement
                    objectName: "layerMovementControls"
                    Layout.fillWidth: true
                    spacing: 8
                    LabelText { text: qsTr("Drag:") }
                    LayerMoveHandle {
                        id: cameraGrip
                        objectName: "cameraMoveHandle"
                        dragObjectName: "cameraMoveDrag"
                        text: qsTr("Camera")
                        hint: qsTr("Drag to move camera/user-profile. Arrow keys move a little; Shift+arrows move farther.")
                        accent: root.accent
                        enabled: root.document !== null
                        property point origin
                        property real referenceWidth
                        property real referenceHeight
                        property real direction
                        onMovementStarted: {
                            backgroundMoveHandle.selected = false
                            origin = Qt.point(root.foreground.x, root.foreground.y)
                            referenceWidth = Math.max(1, stage.width)
                            referenceHeight = Math.max(1, stage.height)
                            direction = root.mirror ? -1 : 1
                        }
                        onMovementRequested: function(dx, dy) {
                            root.placeForeground(origin.x + direction * dx / referenceWidth, origin.y + dy / referenceHeight)
                        }
                    }
                    LayerMoveHandle {
                        id: backgroundMoveHandle
                        objectName: "backgroundMoveHandle"
                        dragObjectName: "backgroundMoveDrag"
                        text: qsTr("Background")
                        accent: root.accent
                        enabled: root.backgroundMode === "image" && root.imageReady && !root.backgroundLocked
                        hint: qsTr("Drag here, or select Background and drag the image in the preview. Zoom the background in to allow more movement.")
                        readonly property bool canPan: stage.width > 0 && stage.height > 0
                            && (backgroundImage.width > stage.width + 0.01 || backgroundImage.height > stage.height + 0.01)
                        property bool panning: false
                        property string panImage: ""
                        property point origin
                        property real referenceWidth
                        property real referenceHeight
                        property real edgeX
                        property real edgeY
                        property real direction
                        property real startZoom

                        function beginPan() {
                            if (!canPan) return
                            panImage = root.imagePath
                            referenceWidth = backgroundImage.width
                            referenceHeight = backgroundImage.height
                            edgeX = Math.min(0.5, stage.width / (2 * referenceWidth))
                            edgeY = Math.min(0.5, stage.height / (2 * referenceHeight))
                            origin = Qt.point(boundedCenter(root.backgroundCrop.centerX, edgeX),
                                boundedCenter(root.backgroundCrop.centerY, edgeY))
                            direction = root.mirror ? -1 : 1
                            startZoom = root.backgroundCrop.zoom
                            panning = true
                        }
                        function boundedCenter(center, edge) {
                            return Math.max(edge, Math.min(1 - edge, center))
                        }
                        function pan(dx, dy) {
                            if (!panning || panImage !== root.imagePath || startZoom !== root.backgroundCrop.zoom) return
                            const x = boundedCenter(origin.x - direction * dx / referenceWidth, edgeX)
                            const y = boundedCenter(origin.y - dy / referenceHeight, edgeY)
                            if (x === root.backgroundCrop.centerX && y === root.backgroundCrop.centerY) return
                            root.editBackgroundCrop({zoom: startZoom, centerX: x, centerY: y})
                        }

                        onMovementStarted: {
                            selected = canPan
                            beginPan()
                        }
                        onMovementRequested: function(dx, dy) { pan(dx, dy) }
                        onMovementFinished: panning = false
                    }
                    CompositionLabelGrip {
                        id: quickLabelGrip
                        objectName: "quickLabelMoveHandle"
                        dragObjectName: "quickPreviewLabelDrag"
                        preview: interactiveLabel
                    }
                    Item { Layout.fillWidth: true }
                }
                CompositionLabelSection {
                    id: labelDisclosure
                    objectName: "labelDisclosure"
                    headerObjectName: "labelControlsToggle"
                    gripName: "labelMoveHandle"
                    dragName: "previewLabelDrag"
                    preview: interactiveLabel
                    Layout.fillWidth: true
                }
                DisclosureSection {
                    id: cropDisclosure
                    objectName: "cropDisclosure"
                    headerObjectName: "cropControlsToggle"
                    onHeightChanged: if (expanded) Qt.callLater(root.revealDisclosure, cropDisclosure)
                    title: qsTr("Crop & Mirror")
                    hint: qsTr("Show controls for cropping, zooming, and mirroring the composition.")
                    Layout.fillWidth: true
                    CompositionCropTool {
                        id:cropTool
                        popupPalette: root.popupPalette
                        Layout.fillWidth:true
                        cameraCrop:({zoom:root.zoom,centerX:root.centerX,centerY:root.centerY})
                        backgroundCrop:root.backgroundCrop
                        mirror:root.mirror
                        cameraActive:root.previewOn
                        backgroundAvailable:root.backgroundMode==="image"&&root.imageReady
                        backgroundLocked:root.backgroundLocked
                        cameraSource:processor.item?processor.item.sourceFrameUrl:""
                        backgroundSource:root.backgroundUrl(root.imagePath)
                        error: root.cropSaveFailed ? root.cropMessage : ""
                        onCameraEdited:function(value){root.frame(value.zoom,value.centerX,value.centerY)}
                        onBackgroundEdited:function(value){root.editBackgroundCrop(value)}
                        layerActions: [
                            CheckBox {
                                objectName: "mirrorToggle"
                                Layout.leftMargin: 10
                                text: root.mirrorPending || root.mirrorQueued ? qsTr("Mirror (saving…)") : qsTr("Mirror")
                                ToolTip.visible: hovered
                                ToolTip.text: qsTr("Mirror the whole composite: camera, background and label.")
                                checked: root.mirror
                                enabled: root.document !== null && !root.mirrorQueued && !root.cameraQueued && !root.autostartQueued && !root.mirrorPending && !root.cameraPending && !root.autostartPending
                                nextCheckState: function() { return checkState }
                                onClicked: root.toggleMirror()
                            },
                            Item { Layout.fillWidth: true }
                        ]
                    }
                    LabelText {
                        id: captureInfo
                        text: root.cropWidth > 0
                            ? qsTr("Capture %1 × %2 at %3 fps · crop %4 × %5 · preview %6 × %7 at %8 fps · %9")
                                .arg(root.captureFormat.captureWidth).arg(root.captureFormat.captureHeight).arg(Math.round(root.captureFormat.captureFps))
                                .arg(root.cropWidth).arg(root.cropHeight).arg(root.captureFormat.previewWidth).arg(root.captureFormat.previewHeight)
                                .arg(Math.round(root.captureFormat.previewFps || 0)).arg(root.captureFormat.provider === "CUDAExecutionProvider" ? qsTr("NVIDIA GPU") : root.captureFormat.provider === "CPUExecutionProvider" ? qsTr("CPU") : qsTr("Original"))
                            : qsTr("Start preview to see the negotiated capture resolution and available crop detail.")
                        font.pixelSize: 12; color: root.palette.placeholderText; Layout.fillWidth: true
                    }
                }
                DisclosureSection {
                    id: maskDisclosure
                    readonly property bool dragging: softnessControl.dragging || tightnessControl.dragging
                    objectName: "maskDisclosure"
                    headerObjectName: "maskControlsToggle"
                    title: qsTr("Person Mask")
                    hint: qsTr("Adjust the outline used for background effects.")
                    Layout.fillWidth: true
                    onHeightChanged: if (expanded) Qt.callLater(root.revealDisclosure, maskDisclosure)
                    LabelText {
                        visible: root.backgroundMode === "none"
                        text: qsTr("Choose Blur or Background Image to adjust the person mask.")
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        enabled: root.document !== null && root.backgroundMode !== "none"
                        component MaskControl: RowLayout {
                            id: maskControl
                            required property string setting
                            required property string label
                            required property int low
                            required property int high
                            required property string hint
                            readonly property bool dragging: maskSlider.pressed
                            Layout.fillWidth: true
                            function change(value) {
                                root.adjustPersonMask(Object.assign({}, root.personMask, {[setting]: value}))
                            }
                            LabelText {
                                Layout.preferredWidth: 108
                                Layout.fillWidth: false
                                text: maskControl.label
                            }
                            Slider {
                                id: maskSlider
                                objectName: "maskSlider-" + maskControl.setting
                                Layout.fillWidth: true
                                from: maskControl.low
                                to: maskControl.high
                                stepSize: 1
                                value: root.personMask[maskControl.setting]
                                onMoved: maskControl.change(Math.round(value))
                                Accessible.name: maskControl.label
                                ToolTip.visible: hovered
                                ToolTip.delay: 500
                                ToolTip.text: maskControl.hint
                                handle: Rectangle {
                                    x: maskSlider.leftPadding + maskSlider.visualPosition * (maskSlider.availableWidth - width)
                                    y: maskSlider.topPadding + (maskSlider.availableHeight - height) / 2
                                    implicitWidth: 14
                                    implicitHeight: 18
                                    radius: 3
                                    color: maskSlider.enabled
                                        ? (maskSlider.pressed ? maskSlider.palette.windowText : maskSlider.palette.highlight)
                                        : maskSlider.palette.mid
                                    border.color: maskSlider.palette.highlightedText
                                }
                            }
                            SpinBox {
                                objectName: "maskValue-" + maskControl.setting
                                from: maskControl.low
                                to: maskControl.high
                                value: root.personMask[maskControl.setting]
                                editable: true
                                onValueModified: maskControl.change(value)
                                Accessible.name: maskControl.label
                                ToolTip.visible: hovered
                                ToolTip.delay: 500
                                ToolTip.text: maskControl.hint
                            }
                        }
                        MaskControl {
                            id: softnessControl
                            setting: "softness"
                            label: qsTr("Edge softness")
                            low: 0
                            high: 8
                            hint: qsTr("Blend the edge of the person into the background.")
                        }
                        MaskControl {
                            id: tightnessControl
                            setting: "tightness"
                            label: qsTr("Edge tightness")
                            low: -50
                            high: 50
                            hint: qsTr("Increase to trim faint edges. Decrease to keep more of them.")
                        }
                    }
                    Button {
                        objectName: "resetPersonMask"
                        text: qsTr("Reset mask")
                        enabled: root.document !== null
                        onPressed: forceActiveFocus(Qt.MouseFocusReason)
                        onClicked: root.adjustPersonMask(root.defaultPersonMask)
                    }
                }
                DisclosureSection {
                    id: snapshotsDisclosure
                    objectName: "snapshotsDisclosure"
                    headerObjectName: "snapshotsToggle"
                    title: qsTr("Snapshots")
                    hint: qsTr("Capture a snapshot or copy a saved image, file path, or link.")
                    Layout.fillWidth: true
                    onHeightChanged: if (expanded) Qt.callLater(root.revealDisclosure, snapshotsDisclosure)
                    onExpandedChanged: {
                        if (!expanded) return
                        if (snapshotGallery.item) {
                            snapshotGallery.item.refresh()
                            snapshotGallery.item.checkRevelator()
                        } else snapshotGallery.active = true
                    }
                    headerActions: Button {
                        hoverEnabled: true
                        ToolTip.visible: hovered
                        ToolTip.delay: 500
                        ToolTip.text: qsTr("Save a full-resolution image of the current composition.")
                        objectName: "snapshotButton"
                        text: processor.item && processor.item.snapshotPending ? qsTr("Saving…") : qsTr("Snapshot")
                        enabled: root.previewOn && processor.item !== null && processor.item.snapshotReady
                        onClicked: processor.item.takeSnapshot()
                    }
                    Loader {
                        id: snapshotGallery
                        Layout.fillWidth: true
                        Layout.preferredHeight: item ? item.implicitHeight : 0
                        active: false
                        source: Qt.resolvedUrl("SnapshotGallery.qml")
                        onLoaded: item.checkRevelator()
                    }
                }
                DisclosureSection {
                    id: profileDisclosure
                    objectName: "profileDisclosure"
                    headerObjectName: "profileDetailsToggle"
                    visible: root.section === "camera" || root.section === "all"
                    onHeightChanged: if (expanded) Qt.callLater(root.revealDisclosure, profileDisclosure)
                    title: {
                        const savedProfile = root.document ? root.document.profiles[root.profileIndex] : null
                        return savedProfile ? qsTr("Profile Details · %1").arg(savedProfile.name) : qsTr("Profile Details")
                    }
                    hint: qsTr("Show save status, revision details, and the reload command.")
                    Layout.fillWidth: true
                    LabelText {
                        visible: !root.profileNeedsAttention
                        text: qsTr("Saved")
                        color: root.accent
                        Layout.fillWidth: true
                    }
                    LabelText {
                        objectName: "saveVerification"
                        visible: text !== ""
                        text: root.lastSaveDetails
                        color: root.palette.placeholderText
                        Layout.fillWidth: true
                    }
                    Button {
                        hoverEnabled: true
                        ToolTip.visible: hovered
                        ToolTip.delay: 500
                        ToolTip.text: qsTr("Load the last saved profile from disk.")
                        objectName: "reloadSaved"
                        text: qsTr("Reload saved")
                        enabled: root.document !== null
                        onClicked: root.dirty ? discardDialog.open() : root.request("read", [])
                    }
                }
            }
            Rectangle {
                id: backgroundsDivider
                visible: root.section === "all" || root.section === "background"
                Layout.fillWidth: true
                height: 1
                color: root.palette.mid
            }
            ColumnLayout {
                id: backgroundsContent
                Layout.fillWidth: true
                visible: root.section === "all" || root.section === "background"
                LabelText {
                    id: effectsHeading
                    objectName: "localCameraEffectsLabel"
                    text: qsTr("Local Camera Effects")
                    font.bold: true
                    Layout.fillWidth: true
                }
                RowLayout {
                    id: effectsButtons
                    Layout.fillWidth: true
                    objectName: "backgroundEffects"
                    Repeater {
                        model: [
                            { mode: "image", label: qsTr("Backgroundd Image") },
                            { mode: "blur", label: qsTr("Blur") },
                            { mode: "none", label: qsTr("No Background") }
                        ]
                        Button {
                            hoverEnabled: true
                            ToolTip.visible: hovered
                            ToolTip.delay: 500
                            ToolTip.text: modelData.mode === "none" ? qsTr("Keep the original camera background.") : modelData.mode === "blur" ? qsTr("Blur the background behind the subject.") : qsTr("Replace the background with an image.")
                            required property var modelData
                            objectName: "backgroundEffect-" + modelData.mode
                            text: modelData.label; highlighted: root.backgroundMode === modelData.mode
                            onClicked: { root.backgroundMode = modelData.mode; root.mark() }
                        }
                    }
                    Item { Layout.fillWidth: true }
                }
                LabelText {
                    id: backgroundLoadStatus
                    objectName: "backgroundFeedback"
                    visible: text !== ""
                    text: root.backgroundFeedback
                    color: backgroundImage.status === Image.Loading ? root.accent : root.palette.linkVisited
                    Layout.fillWidth: true
                }
                GridLayout {
                    id: backgroundsPane
                    Layout.fillWidth: true
                    columns: 1
                    columnSpacing: 16
                    rowSpacing: 12
                    BackgroundLibrary {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        Layout.preferredWidth: backgroundsPane.width
                        Layout.maximumWidth: Infinity
                        compact: false
                        availableGridHeight: Math.max(132, editorScroll.availableHeight
                            - backgroundsDivider.height - editorContent.spacing
                            - effectsHeading.implicitHeight - effectsButtons.implicitHeight
                            - toolbarHeight - backgroundLabelButton.implicitHeight - 3 * backgroundsContent.spacing
                            - (backgroundLoadStatus.visible ? backgroundLoadStatus.implicitHeight + backgroundsContent.spacing : 0)
                            - (backgroundLibraryStatus.visible ? backgroundLibraryStatus.implicitHeight + backgroundsContent.spacing : 0))
                        library: root.backgroundLibrary
                        watching: root.panelOpen && root.section === "background"
                        selectedPath: root.imagePath
                        cameraLive: root.publishing && !root.testing
                        cameraStarting: root.outputControl.startingCamera && !root.testing
                        cameraStopping: root.outputControl.stopping && !root.testing
                        previewSettingsFor: root.backgroundPreviewSettings
                        labelTextFor: image => root.labelForBackground(image).text || image.name
                        onLivePreviewRequested: {
                            if (!root.testing && !root.cameraOutputActive && root.processingReady && root.sourceReady
                                && !root.remoteConnecting && !root.cameraPending
                                && (root.backgroundMode !== "image" || root.imageReady))
                                root.startCamera()
                        }
                        busy: root.busy || root.libraryPending
                        actionsReady: root.cropInFlight === null && Object.keys(root.cropDrafts).length === 0 && root.labelInFlight===null && Object.keys(root.labelDrafts).length===0
                        onAddRequested: imageDialog.openForBackgrounds()
                        onOpenFolderRequested: Qt.openUrlExternally(root.backgroundUrl(root.backgroundLibrary.directory))
                        onRefreshRequested: root.refreshBackgrounds()
                        onSelected: function(path) { root.chooseBackground(path) }
                        onPreviewAccepted: function(path) { root.selectBackgroundForPreview(path) }
                        onCropRequested: function(image) { root.cropBackground(image) }
                        onLockRequested: function(image) { root.lockBackground(image) }
                        onTrashRequested: function(image) { root.requestTrash(image) }
                        onLabelRequested: function(image, label) { root.editLabel({text: label}, image) }
                        onLabelEditingChanged:function(active){root.galleryLabelEditing=active}
                        onOverlayRequested: function(image, enabled, opacity) { root.overlayBackground(image, enabled, opacity) }
                    }

                }
                LabelText {
                    id: backgroundLibraryStatus
                    text: root.libraryMessage
                    visible: text !== ""
                    color: root.accent
                    Layout.fillWidth: true
                }
                Button {
                    id: backgroundLabelButton
                    objectName: "backgroundLabelControlsToggle"
                    text: qsTr("Label…")
                    enabled: root.backgroundMode === "image" && root.imageReady
                    hoverEnabled: true
                    ToolTip.visible: hovered
                    ToolTip.delay: 500
                    ToolTip.text: qsTr("Open the label preview for the selected background.")
                    onClicked: backgroundLabelDialog.open()
                }
            }
            Loader {
                objectName: "setupLoader"
                Layout.fillWidth: true
                Layout.preferredHeight: item ? item.implicitHeight : 0
                visible: root.section === "setup"
                active: root.section === "setup" && root.setupContent !== null
                sourceComponent: root.setupContent
            }
            CheckBox {
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: qsTr("Use this profile again the next time WebcamTuner opens.")
                objectName: "restoreToggle"
                visible: root.section === "all" || root.section === "setup"
                text: qsTr("Restore this profile when WebcamTuner starts")
                checked: root.restoreOnStart
                onClicked: { root.restoreOnStart = checked; root.mark() }
            }
            CheckBox {
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: qsTr("Start the shared camera automatically when WebcamTuner opens.")
                objectName: "autostartToggle"
                visible: root.section === "all" || root.section === "setup"
                text: root.autostartPending || root.autostartQueued ? qsTr("Autostart camera (saving…)") : qsTr("Autostart camera")
                checked: root.autostartCamera
                enabled: root.document !== null && !root.mirrorQueued && !root.cameraQueued && !root.autostartQueued && !root.mirrorPending && !root.cameraPending && !root.autostartPending
                nextCheckState: function() { return checkState }
                onClicked: root.toggleAutostart()
            }
            Rectangle { visible: root.section === "all" || root.section === "setup"; Layout.fillWidth: true; height: 1; color: root.palette.mid }
            Button {
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: qsTr("Show how to select WebcamTuner in meeting apps.")
                objectName: "outputHelpToggle"
                visible: root.section === "all" || root.section === "setup"
                text: (root.outputHelpExpanded ? "▾  " : "▸  ") + qsTr("Use in other apps")
                Accessible.name: qsTr("Use in other apps")
                Layout.fillWidth: true
                flat: true
                contentItem: LabelText { text: parent.text; font.bold: true; verticalAlignment: Text.AlignVCenter }
                onClicked: root.outputHelpExpanded = !root.outputHelpExpanded
            }
            LabelText { visible: root.section === "all" || root.section === "setup"; text: root.publishing?qsTr("Camera output: published as WebcamTuner"):qsTr("Camera output: stopped"); color: root.accent; Layout.fillWidth: true }
            ColumnLayout {
                objectName: "outputHelpBody"
                Layout.fillWidth: true
                visible: root.outputHelpExpanded && (root.section === "all" || root.section === "setup")
                spacing: 10
                LabelText {
                    text: qsTr("Start camera output to publish your camera crop, background and label through your user PipeWire session. Test shows independent readbacks of that published video.")
                    Layout.fillWidth: true
                }
                LabelText {
                    text: qsTr("1. Start output in WebcamTuner. The desktop camera adapter prepares automatically.\n2. Open native Zoom, or reopen it if it was already running.\n3. Select WebcamTuner in the app’s camera settings.\n4. Turn off the app’s background replacement and blur to use the look you set here.")
                    Layout.fillWidth: true
                }
                LabelText {
                    text: qsTr("For browser calls, allow the site to use your camera and select WebcamTuner. If the camera is missing, start output first, then reopen camera settings or restart the app.")
                    color: root.palette.placeholderText; Layout.fillWidth: true
                }
                LabelText {
                    text: qsTr("Selecting Logitech BRIO or the laptop camera directly uses the original camera feed, bypassing WebcamTuner’s framing and backgrounds.")
                    color: root.palette.placeholderText; Layout.fillWidth: true
                }
            }
            Rectangle { visible: root.section === "all" || root.section === "setup"; Layout.fillWidth: true; height: 1; color: root.palette.mid }
        }
    }
    HintedDialog {
        id: backgroundLabelDialog
        objectName: "backgroundLabelDialog"
        sourcePalette: root.popupPalette
        title: qsTr("Background Label")
        width: parent ? Math.min(720, Math.max(0, parent.width - 2 * margins)) : 720
        modal: true
        onAboutToHide: backgroundLabelPreview.finishEditing(true)

        header: RowLayout {
            Label {
                Layout.fillWidth: true
                Layout.leftMargin: backgroundLabelDialog.leftPadding
                text: backgroundLabelDialog.title
                font.bold: true
                elide: Text.ElideRight
            }
            Button {
                objectName: "finishBackgroundLabelEditor"
                Layout.topMargin: 6
                Layout.rightMargin: backgroundLabelDialog.rightPadding
                text: qsTr("Done")
                onClicked: backgroundLabelDialog.close()
            }
        }
        contentItem: ScrollView {
            id: labelScroll
            implicitHeight: labelContent.implicitHeight
            contentWidth: availableWidth
            contentHeight: labelContent.implicitHeight
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

            ColumnLayout {
                id: labelContent
                width: labelScroll.availableWidth
                spacing: 8

                Rectangle {
                    id: labelSample
                    objectName: "backgroundLabelSample"
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: Layout.preferredHeight * 16 / 9
                    Layout.preferredHeight: Math.min(labelContent.width * 9 / 16,
                        Math.max(90, backgroundLabelDialog.parent.height - 2 * backgroundLabelDialog.margins
                            - backgroundLabelDialog.header.height - backgroundLabelDialog.topPadding
                            - backgroundLabelDialog.bottomPadding - backgroundLabelControls.implicitHeight
                            - labelContent.spacing))
                    color: labelScroll.palette.base
                    clip: true

                    Item {
                        anchors.fill: parent
                        transform: Scale { origin.x: labelSample.width / 2; xScale: root.mirror ? -1 : 1 }
                        Image {
                            readonly property real cover: implicitWidth > 0 && implicitHeight > 0
                                ? Math.max(labelSample.width / implicitWidth, labelSample.height / implicitHeight) * root.backgroundCrop.zoom : 1
                            source: backgroundLabelDialog.visible ? root.backgroundUrl(root.imagePath) : ""
                            asynchronous: true
                            autoTransform: true
                            sourceSize: Qt.size(640, 360)
                            width: implicitWidth * cover
                            height: implicitHeight * cover
                            x: Math.min(0, Math.max(labelSample.width - width, labelSample.width / 2 - root.backgroundCrop.centerX * width))
                            y: Math.min(0, Math.max(labelSample.height - height, labelSample.height / 2 - root.backgroundCrop.centerY * height))
                        }
                        EditablePreviewLabel {
                            id: backgroundLabelPreview
                            objectName: "backgroundLabelPreview"
                            anchors.fill: parent
                            mirrored: root.mirror
                            showMoveHandles: backgroundLabelControls.gripActive
                            moveAccent: root.accent
                            overlay: root.backgroundLabelOverlay
                            onChanged: function(patch) { root.editLabel(patch) }
                            onEditingStateChanged: function(active) { root.previewLabelEditing = active }
                        }
                    }
                }
                CompositionLabelControls {
                    id: backgroundLabelControls
                    objectName: "backgroundLabelControls"
                    Layout.fillWidth: true
                    preview: backgroundLabelPreview
                    gripName: "backgroundLabelMoveHandle"
                    dragName: "backgroundPreviewLabelDrag"
                }
                MouseArea {
                    parent: labelScroll
                    anchors.fill: parent
                    z: 100
                    enabled: backgroundLabelPreview.editing || backgroundLabelPreview.moveSelected
                    onPressed: function(mouse) {
                        const position = mapToItem(null, mouse.x, mouse.y)
                        root.deselectLabelOutside(backgroundLabelPreview, backgroundLabelControls, position)
                        backgroundLabelPreview.commitOutside(position)
                        mouse.accepted = false
                    }
                }
            }
        }
    }
    HintedDialog {
        id: trashBackgroundDialog
        sourcePalette: root.popupPalette
        standardButtonHelp: ({ [Dialog.Ok]: qsTr("Move this background to Trash."), [Dialog.Cancel]: qsTr("Keep this background in your library.") })
        objectName: "trashBackgroundDialog"
        title: qsTr("Move this background to Trash?")
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        Label { text: qsTr("Profiles using this image will switch to Blur. The image can be restored from your user Trash."); textFormat: Text.PlainText; wrapMode: Text.WordWrap; width: Math.min(360, Math.max(0, root.width - 80)) }
        onAccepted: root.trashBackground()
    }
    HintedDialog {
        id: discardDialog
        sourcePalette: root.popupPalette
        standardButtonHelp: ({ [Dialog.Discard]: qsTr("Discard the current changes and reload the saved profile."), [Dialog.Cancel]: qsTr("Keep working with your current changes.") })
        objectName: "discardProfileDialog"
        title: qsTr("Discard unsaved changes?")
        modal: true
        standardButtons: Dialog.Discard | Dialog.Cancel
        onDiscarded: root.request("read", [])
    }
    FileDialog {
        id: imageDialog
        objectName: "backgroundImageDialog"
        title: qsTr("Add backgrounds to WebcamTuner")
        fileMode: FileDialog.OpenFiles
        nameFilters: [qsTr("Images (*.jpg *.jpeg *.png *.webp)")]
        onAccepted: root.addBackgrounds(selectedFiles.map(path => String(path)))

        function openForBackgrounds() {
            for (const name of ["Pictures", "pictures", "Screenshots", "screenshots"]) {
                const folder = StandardPaths.locate(StandardPaths.HomeLocation, name, StandardPaths.LocateDirectory)
                if (folder.toString() !== "") {
                    currentFolder = folder
                    open()
                    return
                }
            }
            currentFolder = StandardPaths.writableLocation(StandardPaths.HomeLocation)
            open()
        }
    }
}
