import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    property bool testing: false
    readonly property bool discoveryBusy: discovery.item ? discovery.item.busy : false
    signal discoveryRequested(var args)
    function inspectRequest(args) {
        if (testing) discoveryRequested(args)
        else if (discovery.item) discovery.item.request("remote", args)
    }
    property var hosts: []
    property var cameras: []
    property var qualities: [{label: qsTr("Auto · prefer smooth video"), query: ""}]
    property string selectedHost: ""
    property string selectedCamera: ""
    property string feedback: qsTr("Choose a computer to find its cameras.")
    property string connectionFeedback: ""
    property bool connecting: false
    property bool connected: false
    property string activeSource: ""
    readonly property bool sameCamera: activeSource.split("&")[0] === "sshcam://" + selectedHost + "?camera=" + encodeURIComponent(selectedCamera)
    property color accent: palette.link
    signal connectCamera(string uri, string host)
    signal disconnectCamera()
    spacing: 8
    component PlainCombo: ComboBox {
        id: safeCombo
        contentItem: Text {
            text: safeCombo.displayText; font: safeCombo.font; color: safeCombo.palette.buttonText
            textFormat: Text.PlainText; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter
        }
        delegate: ItemDelegate {
            width: safeCombo.width
            contentItem: Text {
                text: String(modelData[safeCombo.textRole] || ""); font: safeCombo.font
                textFormat: Text.PlainText; color: safeCombo.palette.text; elide: Text.ElideRight
            }
        }
    }
    function refresh() {
        if (root.discoveryBusy) return
        feedback = qsTr("Finding computers…")
        root.inspectRequest([])
    }
    function inspect(index) {
        if (root.discoveryBusy || index < 0 || index >= hosts.length) return
        var host = hosts[index]
        selectedHost = host.host; selectedCamera = ""; cameras = []; qualities = [{label: qsTr("Auto · prefer smooth video"), query: ""}]
        if (!host.online) { feedback = qsTr("This computer is offline. Wake it and refresh."); return }
        feedback = qsTr("Looking for cameras on %1…").arg(host.name || host.host)
        root.inspectRequest(["--host", selectedHost])
    }
    function selectCamera(index) {
        if (index < 0 || index >= cameras.length) return
        var camera = cameras[index]
        selectedCamera = camera.stableId || camera.id
        var options = [{label: qsTr("Auto · prefer smooth video"), query: ""}]
        var seen = {}
        ;(camera.modes || []).forEach(function(mode) {
            if (mode.format !== "mjpeg") return
            var key = mode.size + "@" + mode.fps
            if (seen[key]) return
            seen[key] = true
            var dimensions = mode.size.split("x")
            if (Number(dimensions[0]) < 640 || Number(dimensions[1]) < 360) return
            options.push({label: mode.size + " · " + mode.fps + " fps", query: "&size=" + encodeURIComponent(mode.size) + "&fps=" + mode.fps + "&format=mjpeg"})
        })
        qualities = options.slice(0, 60)
        quality.currentIndex = 0
    }
    function accept(result) {
            if (result.machines) {
                root.hosts = result.machines.filter(function(host) { return host.supported && !host.local }).map(function(host) {
                    return Object.assign({}, host, {label: (host.name || host.host) + (host.online ? qsTr(" · online") : qsTr(" · offline"))})
                })
                computers.currentIndex = root.hosts.findIndex(function(host) {return host.host === root.selectedHost})
                root.feedback = root.hosts.length ? qsTr("Choose a computer, then inspect its cameras.") : qsTr("No supported computers found. Check Tailscale.")
            } else {
                root.cameras = result.cameras || []
                cameraChoice.currentIndex = root.cameras.length === 1 ? 0 : -1
                root.selectedCamera = ""
                if (root.cameras.length === 1) root.selectCamera(0)
                root.feedback = root.cameras.length ? qsTr("Choose a camera. Connect starts video; discovery does not.") : qsTr("No camera found. Check its USB connection and permissions.")
                if (result.warnings && result.warnings.length) root.feedback += "\n" + result.warnings.join("\n")
            }
    }
    Loader {
        id: discovery
        active: !root.testing
        source: Qt.resolvedUrl("Bridge.qml")
        onLoaded: {
            item.received.connect(function(action,result) {root.accept(result)})
            item.failed.connect(function(message) {root.feedback=qsTr("Could not inspect this computer: %1").arg(message)})
        }
    }
    RowLayout {
        Layout.fillWidth: true
        PlainCombo {
            id: computers; objectName: "remoteHostChoice"
            Layout.fillWidth: true; model: root.hosts; textRole: "label"
            enabled: !root.discoveryBusy && !root.connecting
            displayText: currentIndex < 0 ? qsTr("Choose remote computer") : currentText
            onActivated: function(index) { root.inspect(index) }
        }
        Button {
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("Look again for reachable remote computers.")
            objectName: "remoteRefresh"
            text: qsTr("Refresh")
            enabled: !root.discoveryBusy && !root.connecting
            onClicked: root.refresh()
        }
        Button {
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("List cameras on the selected remote computer.")
            text: qsTr("Inspect cameras")
            enabled: !root.discoveryBusy && !root.connecting && computers.currentIndex >= 0
            onClicked: root.inspect(computers.currentIndex)
        }
    }
    PlainCombo {
        id: cameraChoice; objectName: "remoteCameraChoice"
        Layout.fillWidth: true; model: root.cameras; textRole: "name"; currentIndex: -1
        enabled: !root.discoveryBusy && !root.connecting && root.cameras.length > 0
        displayText: currentIndex < 0 ? qsTr("Choose remote camera") : currentText
        onActivated: function(index) {root.selectCamera(index)}
    }
    PlainCombo {
        id: quality; objectName: "remoteQualityChoice"
        Layout.fillWidth: true; model: root.qualities; textRole: "label"
        enabled: root.selectedCamera !== "" && !root.connecting
    }
    Text {
        Layout.fillWidth: true; wrapMode: Text.WordWrap; textFormat: Text.PlainText
        color: root.palette.placeholderText; font.pixelSize: 12
        text: qsTr("Video only · microphone off. Streams preserve aspect ratio and are capped at 1280 × 720.")
    }
    Flow {
        Layout.fillWidth: true; spacing: 8
        Button {
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("Use the selected remote camera as the source.")
            objectName: "remoteConnect"
            text: root.connecting ? qsTr("Connecting…") : root.connected && root.sameCamera ? qsTr("Camera connected") : qsTr("Connect camera")
            enabled: !root.discoveryBusy && !root.connecting && !(root.connected && root.sameCamera) && root.selectedCamera !== "" && root.hosts.some(function(host) {return host.host === root.selectedHost && host.online})
            onClicked: root.connectCamera("sshcam://" + root.selectedHost + "?camera=" + encodeURIComponent(root.selectedCamera) + (root.qualities[quality.currentIndex] || {query:""}).query, root.selectedHost)
        }
        Button {
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.delay: 500
            ToolTip.text: qsTr("Cancel the pending connection or disconnect the remote camera.")
            objectName: "remoteDisconnect"; text: root.connecting ? qsTr("Cancel connection") : qsTr("Disconnect")
            enabled: root.connecting || root.connected
            onClicked: root.disconnectCamera()
        }
    }
    Text {
        objectName: "remoteStatus"; Layout.fillWidth: true; wrapMode: Text.WordWrap; textFormat: Text.PlainText
        font.pixelSize: 13; color: root.accent
        text: root.feedback + (root.connectionFeedback ? "\n" + root.connectionFeedback : "")
            + (root.connected && root.sameCamera ? "\n" + qsTr("Disconnect before changing this camera’s capture quality.") : "")
    }
}
