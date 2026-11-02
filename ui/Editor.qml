import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import QtMultimedia
import "CameraChoice.js" as CameraChoice

Rectangle {
    id: root
    color: "#171c24"
    implicitWidth: 760
    implicitHeight: 850
    property color accent: "#93c5aa"
    property bool panelOpen: true
    property var document: null
    property int profileIndex: 0
    property bool dirty: false
    property bool busy: false
    property bool savePending: false
    property bool saveFailed: false
    property bool automaticWritesPaused: false
    property int editGeneration: 0
    property int saveGeneration: -1
    property string message: qsTr("Loading saved profiles…")
    property bool previewOn: false
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
    property string snapshotDirectory: ""
    property string remoteSummary: ""
    property real zoom: 1
    property real centerX: 0.5
    property real centerY: 0.5
    property var foreground: ({x: 0, y: 0})
    property string backgroundMode: "none"
    property string imagePath: ""
    property var backgroundCrop: ({zoom: 1, centerX: 0.5, centerY: 0.5})
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
        if (backgroundMode === "blur") return previewOn ? qsTr("Blur is applied to the camera background.") : qsTr("Preview camera to see background blur.")
        if (backgroundMode !== "image") return ""
        if (imagePath.trim() === "") return qsTr("Choose an image or paste its absolute path.")
        if (backgroundUrl(imagePath) === "") return qsTr("Use a local image with an absolute path.")
        if (backgroundImage.status === Image.Loading) return qsTr("Loading background image…")
        if (backgroundImage.status === Image.Error) return qsTr("Cannot load this image. Check its path, permissions, and format.")
        if (imageReady) return previewOn ? qsTr("Image loaded. Applying it to the camera preview.") : qsTr("Image loaded. Preview camera to see it behind you.")
        return qsTr("Loading background image…")
    }
    signal request(string action, var args)
    readonly property var cameras: CameraChoice.visibleInputs(testing && testCameraInputs !== null ? testCameraInputs : devices.videoInputs, cameraAliases)
    readonly property real cropFraction: 1 / zoom
    readonly property var captureFormat: processor.item ? processor.item.format : ({})
    property bool previewDecoded: false
    readonly property bool previewReady: previewOn && previewDecoded && processor.item!==null && processor.item.frameUrl!==""
    onPreviewOnChanged: if(!previewOn)previewDecoded=false
    readonly property int cropWidth: captureFormat.captureWidth ? Math.floor(captureFormat.captureWidth / zoom / 2) * 2 : 0
    readonly property int cropHeight: captureFormat.captureHeight ? Math.floor(captureFormat.captureHeight / zoom / 2) * 2 : 0

    onSectionChanged: {
        resetScroll()
        if (section === "background" && panelOpen) refreshBackgrounds()
    }
    onPanelOpenChanged: {
        autostartRequested = panelOpen
        if (!panelOpen) previewOn = false
        else { resetScroll(); maybeAutostart(); if (section === "background") refreshBackgrounds() }
    }
    onBusyChanged: maybeAutostart()
    onImageReadyChanged: { maybeAutostart(); if (imageReady && dirty && !automaticWritesPaused) autosave.restart() }
    function maybeAutostart() {
        if (!autostartRequested || !autostartCamera || !panelOpen || !document || !cameraChoiceReady
            || busy || cameraPending || mirrorPending || autostartPending || sourceKind !== "local"
            || savedCamera === "" || cameraIndex() < 0 || (backgroundMode === "image" && !imageReady)) return
        autostartRequested = false
        previewOn = true
    }

    component LabelText: Text {
        color: "#e9ecef"; font.pixelSize: 14; textFormat: Text.PlainText
        wrapMode: Text.WordWrap
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
        if (busy || savePending || cameraPending || mirrorPending || autostartPending || cropInFlight !== null || Object.keys(cropDrafts).length || labelEditing || labelInFlight !== null || Object.keys(labelDrafts).length) { autosave.restart(); return }
        if (!profileName.trim() || (backgroundMode === "image" && !imageReady)) return
        save()
    }
    function prepareUpdate() {
        if (busy || savePending || cropInFlight !== null || labelInFlight !== null || labelEditing) return null
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
    function syncBackgroundOverlay() {
        if (labelDrafts[imagePath]) { backgroundLabelOverlay = labelDrafts[imagePath].spec; return }
        var item = backgroundLibrary.items.find(i => i.path === imagePath)
        if (!item && backgroundLibrary.selected && backgroundLibrary.selected.path === imagePath) item = backgroundLibrary.selected
        if (!item) return
        var setting = item.overlay || {enabled: false, opacity: 0.75}
        var next = Object.assign({},setting,{enabled:!!setting.enabled,opacity:setting.opacity,text:(item.label||item.name).replace(/[\u0000-\u001f\u007f]/g," ").slice(0,256)})
        if (labelIdentity(next) !== labelIdentity(backgroundLabelOverlay)) {
            backgroundLabelOverlay = next
            if (document && backgroundMode === "image") mark()
        }
    }
    function labelIdentity(value) {
        var spec=Object.assign({enabled:false,opacity:.75,text:"",x:.02,y:.96,fontFamily:"sans",fontSize:.034,bold:false,italic:false,allCaps:false},value)
        return JSON.stringify([spec.enabled,spec.opacity,spec.text,spec.x,spec.y,spec.fontFamily,spec.fontSize,spec.bold,spec.italic,spec.allCaps])
    }
    function installLibrary(value) {
        if (galleryLabelEditing) { deferredLibrary=value; return }
        backgroundLibrary=value
        syncBackgroundOverlay()
    }
    onGalleryLabelEditingChanged: {
        if (!galleryLabelEditing && deferredLibrary !== null) { var next=deferredLibrary;deferredLibrary=null;installLibrary(next) }
    }
    function editLabel(patch) {
        var image=backgroundLibrary.items.find(i=>i.path===imagePath)
        if (!image && backgroundLibrary.selected && backgroundLibrary.selected.path===imagePath) image=backgroundLibrary.selected
        if (!image) return
        var next=Object.assign({},backgroundLabelOverlay,patch)
        var drafts=Object.assign({},labelDrafts), previous=drafts[imagePath]
        drafts[imagePath]={image:image,spec:next,textChanged:!!(previous&&previous.textChanged)||patch.text!==undefined,generation:++labelGeneration}
        labelDrafts=drafts; backgroundLabelOverlay=next; labelSaveFailed=false
        labelMessage=qsTr("Saving label…")
        mark();labelSave.restart()
    }
    function flushLabel() {
        if(automaticWritesPaused || labelSaveFailed)return
        if(busy || labelInFlight!==null || labelEditing){labelSave.restart();return}
        var paths=Object.keys(labelDrafts)
        if(!paths.length)return
        var path=paths[0],draft=labelDrafts[path],payload=Object.assign({},draft.spec)
        if(!draft.textChanged)delete payload.text
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
        cameraTabRequested()
        cropTool.target="background"
        Qt.callLater(cropTool.openEditor)
    }
    signal cameraTabRequested()
    function lockBackground(image) {
        request("lock-background", ["--path", image.path, "--id", image.id, "--locked", String(!image.locked)])
    }
    function labelBackground(image, label) { request("label-background", ["--path", image.path, "--id", image.id, "--label", label]) }
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
    function previewSettings() {
        if (backgroundMode === "image" && !imageReady) return null
        return { camera: savedCamera, mirror: mirror, foreground: foreground, crop: { zoom: zoom, centerX: centerX, centerY: centerY },
            sourcePreview: cropTool.sourcePreviewRequested,
            background: { mode: backgroundMode, imagePath: imagePath, crop: backgroundCrop, labelOverlay: backgroundLabelOverlay } }
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
        if (savedCamera !== p.source.camera) previewOn = false
        zoom = p.crop.zoom; centerX = p.crop.centerX; centerY = p.crop.centerY
        foreground = p.foreground || {x:0, y:0}
        profileName = p.name; backgroundMode = p.background.mode; imagePath = p.background.imagePath
        backgroundCrop = cropFor(imagePath, p.background.crop)
        backgroundLabelOverlay = p.background.labelOverlay || {enabled: false, opacity: 0.75, text: ""}
        savedCamera = p.source.camera; sourceHost = p.source.host; sourceKind = p.source.kind
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
            if (JSON.stringify(drafts[result.path]) === JSON.stringify(result.crop)) delete drafts[result.path]
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
            libraryMessage = qsTr("%1 saved backgrounds").arg(result.items.length)
            if (action === "add-backgrounds") {
                if (result.added.length) {
                    chooseBackground(result.added[0].path)
                    libraryMessage = qsTr("Images copied and verified. Selection saves automatically.")
                }
                if (result.errors.length) libraryMessage += "\n" + result.errors.map(e => e.name + ": " + e.message).join("\n")
            }
            if (result.limited) libraryMessage += "\n" + qsTr("Showing the first 512 images.")
            if (result.unreadable.length) libraryMessage += "\n" + qsTr("Some files are not ready or readable yet. They will be checked again automatically.")
            return
        }
        if (action === "read" || action === "save") {
            if (action === "read") { cameraStartup = true; cameraChoiceReady = false }
            document = result
            if (cameraPending && action === "save") {
                cameraPending = false
                if (savedCamera !== pendingCamera) previewOn = false
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
            message = action === "save" ? qsTr("Saved to disk and verified · revision %1").arg(result.revision) : result.revision === 0 ? qsTr("New profile. Changes save automatically.") : qsTr("Profile restored from disk")
            if (action === "read") { refreshCameraInventory(); if (backgroundMode === "image") refreshBackgrounds() }
        } else if (action === "devices") {
            cameraAliases = result.aliases || []
            cameraChoiceReady = true
            chooseCamera()
        } else if (action === "remote") {
            var items = Array.isArray(result) ? result : (result.cameras || result.hosts || [])
            remoteSummary = items.map(p => p.name || p.hostname || p.host || p.id).join("\n") || JSON.stringify(result).slice(0, 500)
            message = qsTr("Discovery complete. Remote video input is planned.")
        }
    }
    function draftDocument() {
        if (!document) return null
        var next = JSON.parse(JSON.stringify(document))
        var p = next.profiles[profileIndex]
        p.name = profileName
        p.crop = { zoom: zoom, centerX: centerX, centerY: centerY }
        p.foreground = foreground
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
        if (!document || busy || mirrorPending || cameraPending || autostartPending) return
        var next = JSON.parse(JSON.stringify(document))
        next.profiles[profileIndex].mirror = !mirror
        mirrorPending = true
        message = qsTr("Saving mirror setting…")
        request("save", ["--document", JSON.stringify(next)])
    }
    function toggleAutostart() {
        if (!document || busy || mirrorPending || cameraPending || autostartPending) return
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
        if (!document || !cameraChoiceReady || mirrorPending || cameraPending || autostartPending) return
        var id = CameraChoice.pick(cameras, cameraAliases, document.lastCamera || "", cameraStartup ? "" : savedCamera,
            document.profiles[profileIndex].source.camera, String(devices.defaultVideoInput.id))
        cameraStartup = false
        if (id === "") { previewOn = false; savedCamera = ""; message = qsTr("Connect a webcam to get started."); return }
        var key = CameraChoice.keyFor(id, cameraAliases)
        if (document.lastCamera === key && document.profiles[profileIndex].source.camera === id) {
            if (savedCamera !== id) previewOn = false
            savedCamera = id
            sourceKind = "local"; sourceHost = ""
            maybeAutostart()
            return
        }
        selectCamera(id)
    }
    function selectCamera(id) {
        if (!document || busy || mirrorPending || cameraPending || autostartPending) return
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
    Timer { id: cropSave; interval: 400; onTriggered: root.flushBackgroundCrop() }
    Timer { id: labelSave; interval: 400; onTriggered: root.flushLabel() }
    Timer { id: libraryRefresh; interval: 200; onTriggered: root.refreshBackgrounds() }
    Timer { id: cameraRefresh; interval: 200; onTriggered: root.refreshCameraInventory() }
    Loader {
        id: processor
        active: root.previewOn && root.panelOpen && root.sourceKind === "local" && !root.testing
        source: Qt.resolvedUrl("ProcessedPreview.qml")
        onLoaded: {
            item.configuration = Qt.binding(function() { return root.previewSettings() })
            item.active = true
        }
    }
    Connections {
        target: processor.item
        function onFailed(message) { root.previewOn = false; root.message = message }
        function onSnapshotFailed(message) { root.message = message }
        function onSnapshotSaved(result) {
            root.snapshotDirectory = result.path.slice(0, result.path.lastIndexOf("/"))
            root.message = qsTr("Snapshot saved: %1 × %2 · %3").arg(result.width).arg(result.height).arg(result.path)
            if(result.recentError)root.message+="\n"+result.recentError
            if(result.mirrorError)root.message+="\n"+result.mirrorError
        }
    }
    ColumnLayout {
        id: footer
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 22
        height: implicitHeight
        spacing: 6
        RowLayout {
            id: profileActions
            LabelText {
                objectName: "profileSaveState"
                text: !root.document ? qsTr("Loading…") : root.saveFailed ? qsTr("Could not save") : root.savePending ? qsTr("Saving…") : root.dirty ? (root.profileName.trim() ? qsTr("Waiting to save…") : qsTr("Name this profile")) : qsTr("Saved")
                color: root.saveFailed ? "#f1b58a" : root.accent
                Layout.preferredWidth: Math.min(160, implicitWidth)
            }
            Button { visible:root.saveFailed||root.labelSaveFailed; text:qsTr("Retry"); enabled:!root.busy; onClicked:{if(root.labelSaveFailed){root.labelSaveFailed=false;root.flushLabel()}else root.save()} }
            Button { text: qsTr("Reload saved"); enabled: !root.busy; onClicked: root.dirty ? discardDialog.open() : root.request("read", []) }
            Item { Layout.fillWidth: true }
            Button { text: qsTr("Remote cameras"); enabled: !root.busy; onClicked: root.request("remote", []) }
        }
        LabelText { id: saveStatus; objectName: "saveStatus"; text: root.message; color: root.accent; Layout.fillWidth: true; maximumLineCount: 3; elide: Text.ElideRight }
        LabelText { visible: root.remoteSummary !== ""; text: root.remoteSummary; Layout.fillWidth: true; font.pixelSize: 12 }
    }
    ScrollView {
        id: editorScroll
        objectName: "editorScroll"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: footer.top
        anchors.margins: 22
        clip: true
        rightPadding: 16
        contentWidth: availableWidth
        contentHeight: editorContent.implicitHeight
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        ScrollBar.vertical: VisibleScrollBar {
            ink: root.accent
            objectName: "editorScrollbar"
            parent: editorScroll
            x: editorScroll.width - width
            y: 0
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
            LabelText { id: pageIntro; text: qsTr("Frame your camera. Choose a background. Your look saves automatically."); color: "#a9b4c1"; Layout.fillWidth: true }
            RowLayout {
                id: profileRow
                Layout.fillWidth: true
                ComboBox {
                    id: profileChoice; objectName: "profileChoice"
                    Layout.preferredWidth: 145
                    model: root.document ? root.document.profiles : []
                    textRole: "name"; currentIndex: root.profileIndex
                    enabled: !root.dirty && !root.busy
                    onActivated: function(index) { root.restore(index); root.mark() }
                }
                TextField {
                    objectName: "profileName"; Layout.fillWidth: true
                    text: root.profileName; placeholderText: qsTr("Profile name")
                    maximumLength: 80
                    onTextEdited: { root.profileName = text; root.mark() }
                }
                Button { text: qsTr("New"); enabled: !root.dirty && !root.busy && root.document && root.document.profiles.length < 30; onClicked: root.newProfile() }
            }
            ColumnLayout {
                Layout.fillWidth: true
                visible: root.section === "all" || root.section === "camera"
                RowLayout {
                    id: cameraSelectorRow
                    Layout.fillWidth: true
                    ComboBox {
                        objectName: "cameraChoice"; Layout.fillWidth: true
                        model: root.cameras; textRole: "description"
                        currentIndex: root.cameraIndex()
                        enabled: root.cameraChoiceReady && !root.busy && !root.cameraPending && !root.mirrorPending && !root.autostartPending
                        displayText: root.cameraPending ? qsTr("Selecting camera…") : root.cameraChoiceReady && root.cameras.length === 0 ? qsTr("No webcam connected") : currentIndex < 0 ? qsTr("Detecting connected webcams…") : currentText
                        onActivated: function(index) {
                            var id = String(root.cameras[index].id)
                            currentIndex = Qt.binding(function() { return root.cameraIndex() })
                            root.selectCamera(id)
                        }
                    }
                    Button {
                        text: root.previewOn ? qsTr("Camera off") : qsTr("Preview camera")
                        enabled: root.cameraChoiceReady && !root.cameraPending && root.savedCamera !== "" && root.sourceKind === "local" && !root.testing && (root.previewOn || root.backgroundMode !== "image" || root.imageReady)
                        onClicked: { root.autostartRequested = false; root.previewOn = !root.previewOn }
                    }
                    Button {
                        objectName: "snapshotButton"
                        text: processor.item && processor.item.snapshotPending ? qsTr("Saving…") : qsTr("Snapshot")
                        enabled: root.previewOn && processor.item !== null && processor.item.snapshotReady
                        onClicked: processor.item.takeSnapshot()
                    }
                }
                Item {
                    objectName: "cameraPreviewArea"
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(width * 9 / 16, Math.max(90, editorScroll.availableHeight
                        - pageIntro.implicitHeight - profileRow.implicitHeight - cameraSelectorRow.implicitHeight
                        - framingGuide.implicitHeight - cropTool.implicitHeight - mirrorControl.implicitHeight - labelControls.implicitHeight
                        - captureInfo.implicitHeight - 98))
                    Rectangle {
                    id: stage
                    objectName: "cameraCompositionStage"
                    anchors.centerIn: parent
                    width: Math.min(parent.width, parent.height * 16 / 9)
                    height: width * 9 / 16
                    color: "#0e131b"; clip: true
                    Image {
                        id: backgroundImage
                        objectName: "backgroundImage"
                        property real cover: implicitWidth>0&&implicitHeight>0 ? Math.max(stage.width/implicitWidth,stage.height/implicitHeight)*root.backgroundCrop.zoom : 1
                        width:implicitWidth*cover; height:implicitHeight*cover
                        x:stage.width/2-root.backgroundCrop.centerX*width; y:stage.height/2-root.backgroundCrop.centerY*height
                        source: root.backgroundMode === "image" ? root.backgroundUrl(root.imagePath) : ""
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                        autoTransform: true
                        sourceSize.width: 1280
                        sourceSize.height: 720
                        visible: root.backgroundMode === "image" && !root.previewOn
                    }
                    Item {
                        anchors.fill: parent
                        transform: Translate { x: root.foreground.x * stage.width; y: root.foreground.y * stage.height }
                    Item {
                        id: source
                        visible: !root.previewOn || root.testing
                        transform: Scale { origin.x: stage.width / 2 - source.x; xScale: root.mirror ? -1 : 1 }
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
                    FpsIndicator {id:fpsBadge;active:root.previewOn;anchors.right:parent.right;anchors.top:parent.top;anchors.margins:10}
                    BackendIndicator {visible:root.previewOn;provider:root.captureFormat.provider||"";anchors.left:parent.left;anchors.top:parent.top;anchors.margins:10}
                    LabelText {
                        anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 12
                        visible:!root.previewOn && stage.width>=380
                        text: root.previewOn ? (processor.item && processor.item.frameUrl !== "" ? qsTr("PROCESSED CAMERA PREVIEW") : qsTr("STARTING CAMERA…")) : qsTr("FRAMING TEST CARD · camera off")
                        font.pixelSize: 10; font.bold: true
                    }
                    LabelText { anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 12; text: root.zoom.toFixed(2) + "×"; font.bold: true }
                    MouseArea {
                        anchors.fill: parent; preventStealing: true
                        property real startX; property real startY; property real startCX; property real startCY
                        cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                        onPressed: function(mouse) { startX=mouse.x;startY=mouse.y;startCX=cropTool.target==="background"?root.backgroundCrop.centerX:root.foreground.x;startCY=cropTool.target==="background"?root.backgroundCrop.centerY:root.foreground.y }
                        onPositionChanged: function(mouse) {
                            if(!pressed)return
                            if(cropTool.target==="camera")root.placeForeground(startCX+(mouse.x-startX)/stage.width,startCY+(mouse.y-startY)/stage.height)
                            else if(!root.backgroundLocked&&root.imageReady){
                                var ex=stage.width/(2*backgroundImage.width),ey=stage.height/(2*backgroundImage.height)
                                root.editBackgroundCrop({zoom:root.backgroundCrop.zoom,centerX:Math.max(ex,Math.min(1-ex,startCX-(mouse.x-startX)/backgroundImage.width)),centerY:Math.max(ey,Math.min(1-ey,startCY-(mouse.y-startY)/backgroundImage.height))})
                            }
                        }
                        onWheel: function(wheel) {
                            if (!(wheel.modifiers & Qt.ControlModifier)) {
                                var flick = editorScroll.contentItem
                                var amount = wheel.pixelDelta.y ? -wheel.pixelDelta.y : -wheel.angleDelta.y / 120 * 64
                                flick.contentY = Math.max(0, Math.min(flick.contentHeight - flick.height, flick.contentY + amount))
                                wheel.accepted = true; return
                            }
                            cropTool.changeZoom(cropTool.selectedCrop.zoom*(wheel.angleDelta.y>0?1.1:1/1.1)); wheel.accepted=true }
                    }
                    EditablePreviewLabel {
                        id:interactiveLabel
                        anchors.fill:parent
                        z:2
                        overlay:root.backgroundMode==="image"?root.backgroundLabelOverlay:({enabled:false})
                        bitmapSource:processor.item?processor.item.labelBitmapUrl:""
                        bitmapKey:processor.item?processor.item.labelBitmapKey:""
                        bitmapWidth:processor.item?processor.item.labelBitmapWidth:0
                        bitmapHeight:processor.item?processor.item.labelBitmapHeight:0
                        frameWidth:root.captureFormat.previewWidth||960
                        frameHeight:root.captureFormat.previewHeight||540
                        onChanged:function(patch){root.editLabel(patch)}
                        onEditingStateChanged:function(active){root.previewLabelEditing=active}
                    }
                }
                }
                LabelControls {
                    id:labelControls
                    Layout.fillWidth:true
                    overlay:root.backgroundLabelOverlay
                    available:root.backgroundMode==="image"&&root.imageReady
                    feedback:root.labelMessage
                    onChanged:function(patch){root.editLabel(patch)}
                    onEditRequested:interactiveLabel.beginEditing()
                }
                LabelText {
                    id: framingGuide
                    text: qsTr("Drag yourself to position your image. Choose Crop camera or Crop background below; Ctrl+scroll changes the selected crop.")
                    color: "#a9b4c1"
                    Layout.fillWidth: true
                }
                CompositionCropTool {
                    id:cropTool
                    Layout.fillWidth:true
                    cameraCrop:({zoom:root.zoom,centerX:root.centerX,centerY:root.centerY})
                    backgroundCrop:root.backgroundCrop
                    mirror:root.mirror
                    cameraActive:root.previewOn
                    backgroundAvailable:root.backgroundMode==="image"&&root.imageReady
                    backgroundLocked:root.backgroundLocked
                    cameraSource:processor.item?processor.item.sourceFrameUrl:""
                    backgroundSource:root.backgroundUrl(root.imagePath)
                    compositionSource:processor.item?processor.item.frameUrl:""
                    labelOverlay:root.backgroundMode==="image"?root.backgroundLabelOverlay:({enabled:false})
                    feedback:root.cropMessage
                    onCameraEdited:function(value){root.frame(value.zoom,value.centerX,value.centerY)}
                    onBackgroundEdited:function(value){root.editBackgroundCrop(value)}
                }
                CheckBox {
                    id: mirrorControl
                    objectName: "mirrorToggle"
                    text: root.mirrorPending ? qsTr("Mirror (saving…)") : qsTr("Mirror")
                    checked: root.mirror
                    enabled: root.document !== null && !root.busy && !root.mirrorPending && !root.cameraPending && !root.autostartPending
                    nextCheckState: function() { return checkState }
                    onClicked: root.toggleMirror()
                }
                LabelText {
                    id: captureInfo
                    text: root.cropWidth > 0
                        ? qsTr("Capture %1 × %2 at %3 fps · crop %4 × %5 · preview %6 × %7 at %8 fps · %9")
                            .arg(root.captureFormat.captureWidth).arg(root.captureFormat.captureHeight).arg(Math.round(root.captureFormat.captureFps))
                            .arg(root.cropWidth).arg(root.cropHeight).arg(root.captureFormat.previewWidth).arg(root.captureFormat.previewHeight)
                            .arg(Math.round(root.captureFormat.previewFps || 0)).arg(root.captureFormat.provider === "CUDAExecutionProvider" ? qsTr("NVIDIA GPU") : root.captureFormat.provider === "CPUExecutionProvider" ? qsTr("CPU") : qsTr("Original"))
                        : qsTr("Start preview to see the negotiated capture resolution and available crop detail.")
                    font.pixelSize: 12; color: "#a9b4c1"; Layout.fillWidth: true
                }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: "#39414b" }
            ColumnLayout {
                Layout.fillWidth: true
                visible: root.section === "all" || root.section === "background"
                LabelText { text: qsTr("Background"); font.bold: true }
                RowLayout {
                    Repeater {
                        model: [{ mode: "none", label: qsTr("Original") }, { mode: "blur", label: qsTr("Blur") }, { mode: "image", label: qsTr("Image") }]
                        Button {
                            required property var modelData
                            text: modelData.label; highlighted: root.backgroundMode === modelData.mode
                            onClicked: { root.backgroundMode = modelData.mode; root.mark() }
                        }
                    }
                    LabelText { text: qsTr("Local camera effects"); color: "#bdc5cf"; font.pixelSize: 11; Layout.fillWidth: true }
                }
                RowLayout {
                    Layout.fillWidth: true; visible: root.backgroundMode === "image"
                    TextField {
                        objectName: "backgroundPath"
                        Layout.fillWidth: true
                        text: root.imagePath; placeholderText: qsTr("Paste the absolute path to your background image")
                        onTextEdited: root.chooseBackground(text)
                    }
                    Button { text: qsTr("Add this image"); enabled: !root.busy && !root.libraryPending && root.imagePath !== ""; onClicked: root.addBackgrounds([root.imagePath]) }
                }
                RowLayout {
                    Layout.fillWidth: true
                    TextField {
                        objectName: "backgroundLibraryPath"
                        Layout.fillWidth: true
                        readOnly: true; selectByMouse: true
                        text: root.backgroundLibrary.directory || ""
                        placeholderText: qsTr("Loading background folder…")
                        Accessible.name: qsTr("Background storage folder")
                    }
                    Button {
                        text: qsTr("Open folder")
                        enabled: !!root.backgroundLibrary.directory
                        onClicked: Qt.openUrlExternally(root.backgroundUrl(root.backgroundLibrary.directory))
                    }
                }
                LabelText { text: qsTr("Add images here or copy them into this folder. The list updates automatically."); color: "#a9b4c1"; Layout.fillWidth: true }
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
                        availableGridHeight: Math.max(120,Math.min(480,root.height-370))
                        library: root.backgroundLibrary
                        watching: root.panelOpen && root.section === "background"
                        selectedPath: root.imagePath
                        busy: root.busy || root.libraryPending
                        actionsReady: root.cropInFlight === null && Object.keys(root.cropDrafts).length === 0 && root.labelInFlight===null && Object.keys(root.labelDrafts).length===0
                        onAddRequested: imageDialog.open()
                        onRefreshRequested: root.refreshBackgrounds()
                        onSelected: function(path) { root.chooseBackground(path) }
                        onCropRequested: function(image) { root.cropBackground(image) }
                        onLockRequested: function(image) { root.lockBackground(image) }
                        onTrashRequested: function(image) { root.requestTrash(image) }
                        onLabelRequested: function(image, label) { root.labelBackground(image, label) }
                        onLabelEditingChanged:function(active){root.galleryLabelEditing=active}
                        onOverlayRequested: function(image, enabled, opacity) { root.overlayBackground(image, enabled, opacity) }
                    }

                }
                LabelText { text: root.libraryMessage; visible: text !== ""; color: root.accent; Layout.fillWidth: true }
                LabelText { objectName: "backgroundFeedback"; visible: root.backgroundMode !== "none"; text: root.backgroundFeedback; color: root.backgroundMode === "image" && !root.imageReady ? "#f1b58a" : root.accent; Layout.fillWidth: true }
            }
            CheckBox {
                objectName: "restoreToggle"
                visible: root.section === "all" || root.section === "setup"
                text: qsTr("Restore this profile when WebcamTuner starts")
                checked: root.restoreOnStart
                onClicked: { root.restoreOnStart = checked; root.mark() }
            }
            CheckBox {
                objectName: "autostartToggle"
                visible: root.section === "all" || root.section === "setup"
                text: root.autostartPending ? qsTr("Autostart camera (saving…)") : qsTr("Autostart camera")
                checked: root.autostartCamera
                enabled: root.document !== null && !root.busy && !root.mirrorPending && !root.cameraPending && !root.autostartPending
                nextCheckState: function() { return checkState }
                onClicked: root.toggleAutostart()
            }
            Loader {
                objectName: "setupLoader"
                Layout.fillWidth: true
                Layout.preferredHeight: item ? item.implicitHeight : 0
                visible: root.section === "setup"
                active: root.section === "setup" && root.setupContent !== null
                sourceComponent: root.setupContent
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: "#39414b" }
            Button {
                objectName: "outputHelpToggle"
                visible: root.section === "all" || root.section === "setup"
                text: (root.outputHelpExpanded ? "▾  " : "▸  ") + qsTr("Use in other apps")
                Accessible.name: qsTr("Use in other apps")
                Layout.fillWidth: true
                flat: true
                contentItem: LabelText { text: parent.text; font.bold: true; verticalAlignment: Text.AlignVCenter }
                onClicked: root.outputHelpExpanded = !root.outputHelpExpanded
            }
            LabelText { visible: root.section === "all" || root.section === "setup"; text: qsTr("Camera processing: preview only"); color: root.accent; Layout.fillWidth: true }
            ColumnLayout {
                objectName: "outputHelpBody"
                Layout.fillWidth: true
                visible: root.outputHelpExpanded && (root.section === "all" || root.section === "setup")
                spacing: 10
                LabelText {
                    text: qsTr("Camera effects currently stay in the preview. Setup can publish a separate synthetic test camera; your processed camera is not connected to it yet.")
                    Layout.fillWidth: true
                }
                LabelText {
                    text: qsTr("Once virtual-camera output is available:\n1. Start output in WebcamTuner.\n2. Open the other app’s video or camera settings and select WebcamTuner.\n3. Turn off that app’s background replacement and blur to use the look you set here.")
                    Layout.fillWidth: true
                }
                LabelText {
                    text: qsTr("For browser calls, allow the site to use your camera and select WebcamTuner. If the camera is missing, start output first, then reopen camera settings or restart the app.")
                    color: "#a9b4c1"; Layout.fillWidth: true
                }
                LabelText {
                    text: qsTr("Selecting Logitech BRIO or the laptop camera directly uses the original camera feed, bypassing WebcamTuner’s framing and backgrounds.")
                    color: "#a9b4c1"; Layout.fillWidth: true
                }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: "#39414b" }
        }
    }
    Dialog {
        id: trashBackgroundDialog
        objectName: "trashBackgroundDialog"
        title: qsTr("Move this background to Trash?")
        anchors.centerIn: parent
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        Label { text: qsTr("Profiles using this image will switch to Blur. The image can be restored from your user Trash."); textFormat: Text.PlainText; wrapMode: Text.WordWrap; width: Math.min(360, root.width - 80) }
        onAccepted: root.trashBackground()
    }
    Dialog {
        id: discardDialog
        title: qsTr("Discard unsaved changes?")
        anchors.centerIn: parent
        modal: true
        standardButtons: Dialog.Discard | Dialog.Cancel
        onDiscarded: root.request("read", [])
    }
    FileDialog {
        id: imageDialog
        title: qsTr("Add backgrounds to WebcamTuner")
        fileMode: FileDialog.OpenFiles
        nameFilters: [qsTr("Images (*.jpg *.jpeg *.png *.webp)")]
        onAccepted: root.addBackgrounds(selectedFiles.map(path => String(path)))
    }
}
