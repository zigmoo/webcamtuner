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
    property string message: qsTr("Loading saved profiles…")
    property bool previewOn: false
    property bool testing: false
    property string remoteSummary: ""
    property real zoom: 1
    property real centerX: 0.5
    property real centerY: 0.5
    property string backgroundMode: "none"
    property string imagePath: ""
    property bool restoreOnStart: true
    property bool mirror: true
    property bool mirrorPending: false
    property bool autostartCamera: true
    property bool autostartPending: false
    property bool autostartRequested: true
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
    readonly property int cropWidth: captureFormat.captureWidth ? Math.floor(captureFormat.captureWidth / zoom / 2) * 2 : 0
    readonly property int cropHeight: captureFormat.captureHeight ? Math.floor(captureFormat.captureHeight / zoom / 2) * 2 : 0

    onPanelOpenChanged: {
        autostartRequested = panelOpen
        if (!panelOpen) previewOn = false
        else maybeAutostart()
    }
    onBusyChanged: maybeAutostart()
    onImageReadyChanged: maybeAutostart()
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
    function mark() { dirty = true; message = qsTr("Unsaved changes") }
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
        imagePath = path
        backgroundMode = "image"
        mark()
    }
    function previewSettings() {
        if (backgroundMode === "image" && !imageReady) return null
        return { camera: savedCamera, mirror: mirror, crop: { zoom: zoom, centerX: centerX, centerY: centerY },
            background: { mode: backgroundMode, imagePath: imagePath } }
    }
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
        profileName = p.name; backgroundMode = p.background.mode; imagePath = p.background.imagePath
        savedCamera = p.source.camera; sourceHost = p.source.host; sourceKind = p.source.kind
        restoreOnStart = p.restoreOnStart
        mirror = p.mirror === undefined ? true : p.mirror
        autostartCamera = p.autostartCamera === undefined ? true : p.autostartCamera
        dirty = false
        if (cameraChoiceReady) chooseCamera()
    }
    function accept(action, result) {
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
            var index = result.profiles.findIndex(p => p.id === result.activeProfile)
            restore(Math.max(0, index))
            message = action === "save" ? qsTr("Saved to disk and verified · revision %1").arg(result.revision) : result.revision === 0 ? qsTr("New profile. Save to keep your settings.") : qsTr("Profile restored from disk")
            if (action === "read") refreshCameraInventory()
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
    function save() {
        if (!document || busy) return
        var next = JSON.parse(JSON.stringify(document))
        var p = next.profiles[profileIndex]
        p.name = profileName
        p.crop = { zoom: zoom, centerX: centerX, centerY: centerY }
        p.background = { mode: backgroundMode, imagePath: imagePath }
        p.source = { kind: sourceKind, host: sourceHost, camera: savedCamera }
        p.restoreOnStart = restoreOnStart
        p.mirror = mirror
        p.autostartCamera = autostartCamera
        next.activeProfile = p.id
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
    }
    ScrollView {
        anchors.fill: parent
        anchors.margins: 22
        clip: true
        contentWidth: availableWidth
        ColumnLayout {
            width: parent.width
            spacing: 14
            LabelText { text: qsTr("Frame your camera. Choose a background. Save your look."); color: "#a9b4c1"; Layout.fillWidth: true }
            RowLayout {
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
            Rectangle {
                id: stage
                Layout.fillWidth: true; Layout.preferredHeight: width * 9 / 16
                color: "#0e131b"; clip: true
                Image {
                    id: backgroundImage
                    objectName: "backgroundImage"
                    anchors.fill: parent
                    source: root.backgroundMode === "image" ? root.backgroundUrl(root.imagePath) : ""
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    autoTransform: true
                    sourceSize.width: 1280
                    sourceSize.height: 720
                    visible: root.backgroundMode === "image" && !root.previewOn
                }
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
                PreviewFrame {
                    objectName: "processedFrame"
                    anchors.fill: parent
                    visible: root.previewOn
                    source: processor.item ? processor.item.frameUrl : ""
                }
                LabelText {
                    anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 12
                    text: root.previewOn ? (processor.item && processor.item.frameUrl !== "" ? qsTr("PROCESSED CAMERA PREVIEW") : qsTr("STARTING CAMERA…")) : qsTr("FRAMING TEST CARD · camera off")
                    font.pixelSize: 10; font.bold: true
                }
                LabelText { anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 12; text: root.zoom.toFixed(2) + "×"; font.bold: true }
                MouseArea {
                    anchors.fill: parent; preventStealing: true
                    property real startX; property real startY; property real startCX; property real startCY
                    cursorShape: root.zoom > 1 ? (pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor) : Qt.ArrowCursor
                    onPressed: function(mouse) { startX = mouse.x; startY = mouse.y; startCX = root.centerX; startCY = root.centerY }
                    onPositionChanged: function(mouse) { if (pressed && root.zoom > 1) root.frame(root.zoom, startCX + (root.mirror ? 1 : -1) * (mouse.x - startX) / source.width, startCY - (mouse.y - startY) / source.height) }
                    onWheel: function(wheel) { root.frame(root.zoom + (wheel.angleDelta.y > 0 ? 0.1 : -0.1), root.centerX, root.centerY); wheel.accepted = true }
                }
            }
            RowLayout {
                LabelText { text: qsTr("Zoom"); Layout.preferredWidth: 45 }
                Slider { objectName: "zoomSlider"; Layout.fillWidth: true; from: 1; to: 4; value: root.zoom; stepSize: 0.05; onMoved: root.frame(value, root.centerX, root.centerY) }
                Button { text: qsTr("Reset frame"); onClicked: root.frame(1, 0.5, 0.5) }
            }
            RowLayout {
                CheckBox {
                    objectName: "mirrorToggle"
                    text: root.mirrorPending ? qsTr("Mirror (saving…)") : qsTr("Mirror")
                    checked: root.mirror
                    enabled: root.document !== null && !root.busy && !root.mirrorPending && !root.cameraPending && !root.autostartPending
                    nextCheckState: function() { return checkState }
                    onClicked: root.toggleMirror()
                }
                Layout.fillWidth: true
                LabelText { text: qsTr("Drag the image to frame your shot. Scroll to zoom."); color: "#a9b4c1"; Layout.fillWidth: true }
                Button {
                    text: root.previewOn ? qsTr("Camera off") : qsTr("Preview camera")
                    enabled: root.cameraChoiceReady && !root.cameraPending && root.savedCamera !== "" && root.sourceKind === "local" && !root.testing && (root.previewOn || root.backgroundMode !== "image" || root.imageReady)
                    onClicked: { root.autostartRequested = false; root.previewOn = !root.previewOn }
                }
            }
            LabelText {
                text: root.cropWidth > 0
                    ? qsTr("Capture %1 × %2 at %3 fps · crop %4 × %5 · scaled preview %6 × %7")
                        .arg(root.captureFormat.captureWidth).arg(root.captureFormat.captureHeight).arg(Math.round(root.captureFormat.captureFps))
                        .arg(root.cropWidth).arg(root.cropHeight).arg(root.captureFormat.previewWidth).arg(root.captureFormat.previewHeight)
                    : qsTr("Start preview to see the negotiated capture resolution and available crop detail.")
                font.pixelSize: 12; color: "#a9b4c1"; Layout.fillWidth: true
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: "#39414b" }
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
                Button { text: qsTr("Browse…"); onClicked: imageDialog.open() }
            }
            LabelText { objectName: "backgroundFeedback"; visible: root.backgroundMode !== "none"; text: root.backgroundFeedback; color: root.backgroundMode === "image" && !root.imageReady ? "#f1b58a" : root.accent; Layout.fillWidth: true }
            CheckBox {
                objectName: "restoreToggle"
                text: qsTr("Restore this profile when WebcamTuner starts")
                checked: root.restoreOnStart
                onClicked: { root.restoreOnStart = checked; root.mark() }
            }
            CheckBox {
                objectName: "autostartToggle"
                text: root.autostartPending ? qsTr("Autostart camera (saving…)") : qsTr("Autostart camera")
                checked: root.autostartCamera
                enabled: root.document !== null && !root.busy && !root.mirrorPending && !root.cameraPending && !root.autostartPending
                nextCheckState: function() { return checkState }
                onClicked: root.toggleAutostart()
            }
            LabelText { text: qsTr("Output: not broadcasting. Virtual-camera processing is the next implementation stage."); color: root.accent; Layout.fillWidth: true }
            RowLayout {
                Button { objectName: "saveButton"; text: root.busy ? qsTr("Working…") : qsTr("Save profile"); highlighted: true; enabled: root.document !== null && root.dirty && !root.busy && root.profileName.trim() !== "" && (root.backgroundMode !== "image" || root.imageReady); onClicked: root.save() }
                Button { text: qsTr("Reload saved"); enabled: !root.busy; onClicked: root.dirty ? discardDialog.open() : root.request("read", []) }
                Item { Layout.fillWidth: true }
                Button { text: qsTr("Remote cameras"); enabled: !root.busy; onClicked: root.request("remote", []) }
            }
            LabelText { objectName: "saveStatus"; text: root.message; color: root.accent; Layout.fillWidth: true }
            LabelText { visible: root.remoteSummary !== ""; text: root.remoteSummary; Layout.fillWidth: true; font.pixelSize: 12 }
        }
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
        title: qsTr("Choose a webcam background")
        nameFilters: [qsTr("Images (*.jpg *.jpeg *.png *.webp *.bmp)"), qsTr("All files (*)")]
        onAccepted: root.chooseBackground(String(selectedFile))
    }
}
