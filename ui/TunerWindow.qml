import QtQuick
import QtQuick.Controls
import QtCore
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland

FloatingWindow {
    id: window
    property alias editor: editor
    property alias titleBar: titlebar
    property alias bootstrap: bootstrap
    property alias bridge: bridge
    property alias testPanel: outputTests
    readonly property int minimumInterfaceScale: 70
    readonly property int maximumInterfaceScale: 150
    readonly property int interfaceScaleStep: 10
    readonly property int interfaceScalePercent: boundedInterfaceScale(preferences.interfaceScalePercent)
    readonly property real interfaceScale: interfaceScalePercent / 100

    function boundedInterfaceScale(percent) {
        return Math.max(minimumInterfaceScale, Math.min(maximumInterfaceScale, percent))
    }
    function setInterfaceScale(percent) {
        preferences.interfaceScalePercent = boundedInterfaceScale(percent)
    }

    Settings {
        id: preferences
        location: StandardPaths.writableLocation(StandardPaths.ConfigLocation) + "/webcamtuner/ui.ini"
        property bool showRemotesTab: false
        property int interfaceScalePercent: 100
    }
    ListModel {
        id: navigation
        ListElement { sectionName: "camera" }
        ListElement { sectionName: "background" }
        ListElement { sectionName: "setup" }
        ListElement { sectionName: "about" }
    }
    readonly property var tabCopy: ({
        camera: { title: qsTr("Camera"), hint: qsTr("Choose your camera, set framing, and start or stop the shared output.") },
        background: { title: qsTr("Backgrounds"), hint: qsTr("Choose an effect or manage background images.") },
        setup: { title: qsTr("Setup"), hint: qsTr("Prepare the runtime and configure camera integrations.") },
        remotes: { title: qsTr("Remotes"), hint: qsTr("Find and connect cameras on other computers.") },
        about: { title: qsTr("About"), hint: qsTr("View the version, documentation, and source code.") }
    })
    readonly property string currentSection: tabs.currentItem?.sectionName || "camera"
    readonly property bool showingOutputTest: currentSection === "setup" && setupTabs.currentIndex === 1

    function showSection(section) {
        if (section === "test" || section === "setup") {
            setupTabs.currentIndex = section === "test" ? 1 : 0
            section = "setup"
        }
        for (let index = 0; index < tabs.count; index++) {
            if (tabs.itemAt(index).sectionName === section) {
                tabs.currentIndex = index
                return
            }
        }
    }
    function updateRemotesTab() {
        const beforeAbout = navigation.count - 1
        const visible = navigation.get(beforeAbout - 1).sectionName === "remotes"
        if (preferences.showRemotesTab === visible) return
        if (preferences.showRemotesTab) {
            navigation.insert(beforeAbout, {sectionName: "remotes"})
        } else {
            if (currentSection === "remotes") showSection("setup")
            navigation.remove(beforeAbout - 1)
        }
    }
    function setRemotesTabVisible(show) {
        preferences.showRemotesTab = show
        updateRemotesTab()
    }
    Component.onCompleted: {
        updateRemotesTab()
        Qt.callLater(requestCompatibleFonts)
        snapshotLinkRetry.start()
    }
    onCurrentSectionChanged: {
        if (currentSection === "background" && !editor.testing && !starterBackgrounds.attempted) {
            starterBackgrounds.attempted = true
            starterBackgrounds.running = true
        }
        if (currentSection === "setup") {
            editor.autostartRequested = false
        }
    }
    property color accent: "#93c5aa"
    property color foreground: "#e9ecef"
    property color warning: "#edb17a"
    property string fontLanguage: Qt.locale().name
    property var compatibleLabelFonts: []
    onFontLanguageChanged: {
        compatibleLabelFonts = []
        Qt.callLater(requestCompatibleFonts)
    }

    function requestCompatibleFonts() {
        if (fontList.running) return
        const candidate = fontLanguage.replace(/_/g, "-")
        fontList.language = /^[a-z]{2,3}(?:-[a-zA-Z0-9]{2,8})*$/.test(candidate) ? candidate : "en"
        fontList.requested = fontLanguage
        fontList.running = true
    }
    property bool collapsed: false
    readonly property int collapsedHeight: Math.ceil(titlebar.height * interfaceScale)
    readonly property size openingSize: Qt.size(680, 700)
    property int expandedWidth: openingSize.width
    property int expandedHeight: openingSize.height
    title: "WebcamTuner"
    visible: false
    implicitWidth: expandedWidth
    implicitHeight: expandedHeight
    minimumSize: Qt.size(540, collapsed ? collapsedHeight : 460)
    maximumSize: Qt.size(16777215, collapsed ? collapsedHeight : 16777215)
    color: "#171c24"
    onCollapsedChanged: resizePalette.restart()
    onInterfaceScaleChanged: if (collapsed) resizePalette.restart()
    Timer {
        id: resizePalette
        interval: 50
        onTriggered: {
            // FloatingWindow preferences do not resize an already visible native window.
            window.implicitWidth = window.expandedWidth
            window.implicitHeight = window.collapsed ? window.collapsedHeight : window.expandedHeight
            if (!window.visible || Quickshell.env("QT_QPA_PLATFORM").indexOf("offscreen") !== -1) return
            Hyprland.dispatch('(function() local w=hl.get_window("title:^WebcamTuner$"); if w then return hl.dsp.window.resize({x='
                + window.expandedWidth + ', y=' + (window.collapsed ? window.collapsedHeight : window.expandedHeight)
                + ', relative=false, window=w}) end; return hl.dsp.no_op() end)()')
        }
    }

    function openEditor() {
        collapsed = false
        visible = true
        if(editor.testing || (bootstrap.checked&&bootstrap.state.controllerReady)){
            if (!editor.document) bridge.request("read", [])
        }else if(bootstrap.checked){showSection("setup")}
    }
    function openSetup() {
        openEditor()
        // Opening setup is not an instruction to capture a physical camera.
        editor.autostartRequested = false
        showSection("setup")
    }
    function openCamera() { openEditor(); showSection("camera") }
    function openRemotes() {
        if (!preferences.showRemotesTab) {
            openSetup()
            return
        }
        editor.autostartRequested = false
        showSection("remotes")
        openEditor()
        showSection("remotes")
        editor.autostartRequested = false
    }
    function openTest() { openEditor();editor.autostartRequested=false;showSection("test") }
    function openBackgrounds() {
        openEditor()
        editor.autostartRequested = false
        showSection("background")
    }
    function closeEditor() { editor.previewOn = false; visible = false }

    Shortcut {
        sequences: ["Ctrl++", "Ctrl+="]
        enabled: window.visible
        onActivated: window.setInterfaceScale(window.interfaceScalePercent + window.interfaceScaleStep)
    }
    Shortcut {
        sequence: "Ctrl+-"
        enabled: window.visible
        onActivated: window.setInterfaceScale(window.interfaceScalePercent - window.interfaceScaleStep)
    }
    Shortcut {
        sequence: "Esc"
        enabled: window.visible
        autoRepeat: false
        onActivated: window.closeEditor()
    }
    Shortcut {
        sequence: "Q"
        enabled: {
            var focusedItem = titlebar.Window.activeFocusItem
            return window.visible && !(focusedItem instanceof TextInput) && !(focusedItem instanceof TextEdit)
        }
        autoRepeat: false
        onActivated: window.closeEditor()
    }

    function toggleCollapse() {
        if (!collapsed) {
            expandedWidth = Math.max(540, width)
            expandedHeight = Math.max(460, height)
        }
        collapsed = !collapsed
    }

    onVisibleChanged: {
        if (visible) {
            floatWindow.restart()
            snapshotLinks.refresh()
        } else editor.previewOn = false
    }
    Connections {
        target: editor
        function onSnapshotCreated() { snapshotLinks.refresh() }
    }
    Timer {
        id: snapshotLinkRetry
        interval: 2000
        onTriggered: snapshotLinks.refresh()
    }
    Process {
        id: snapshotLinks
        property bool refreshPending: false
        readonly property string helper: decodeURIComponent(Qt.resolvedUrl("../bin/snapshot-gallery.py").toString().replace(/^file:\/\//, ""))
        command: ["python3", helper, "register-missing"]
        stdout: StdioCollector { id: snapshotLinkResult; waitForEnd: true }
        function refresh() {
            if (editor.testing) return
            snapshotLinkRetry.stop()
            if (running) refreshPending = true
            else running = true
        }
        onExited: function(code) {
            try {
                const result = code === 0 ? JSON.parse(snapshotLinkResult.text) : {}
                if (code !== 0 || result.failed)
                    console.warn("WebcamTuner could not prepare all snapshot links.")
                if (result.retry) {
                    snapshotLinkRetry.interval = 15000
                    snapshotLinkRetry.start()
                }
            } catch (error) {
                console.warn("WebcamTuner could not read the snapshot link results.")
            }
            if (refreshPending) {
                refreshPending = false
                Qt.callLater(snapshotLinks.refresh)
            }
        }
    }
    Timer {
        id: floatWindow
        interval: 100
        onTriggered: {
            if (!window.visible || Quickshell.env("QT_QPA_PLATFORM").indexOf("offscreen") !== -1) return
            // Use the monitor Hyprland placed the window on, including bars and rotation.
            Hyprland.dispatch('(function() local w=hl.get_window("title:^WebcamTuner$"); if not w then return hl.dsp.no_op() end; '
                + 'local m=w.monitor; if not m then return hl.dsp.no_op() end; '
                + 'local width,height=m.width/m.scale,m.height/m.scale; '
                + 'if (m.transform or 0)%2==1 then width,height=height,width end; '
                + 'local r=m.reserved or {}; width=width-(r.left or 0)-(r.right or 0); '
                + 'height=height-(r.top or 0)-(r.bottom or 0); '
                + 'hl.dispatch(hl.dsp.window.float({action="on",window=w})); '
                + 'hl.dispatch(hl.dsp.window.resize({window=w,relative=false,x=math.max(540,math.min('
                + window.openingSize.width + ',math.floor(width*0.92))),y=math.max(460,math.min('
                + window.openingSize.height + ',math.floor(height*0.92)))})); '
                + 'return hl.dsp.window.center({window=w}) end)()')
        }
    }
    Process {
        command: ["hostname"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: editor.localHostname = text.trim()
        }
    }
    Process {
        id: fontList
        property string language: "en"
        property string requested: ""
        command: ["fc-list", ":lang=" + language, "--format", "%{family}\n"]
        stdout: StdioCollector { id: fontResult; waitForEnd: true }
        onExited: function(code) {
            if (requested !== window.fontLanguage) {
                Qt.callLater(window.requestCompatibleFonts)
                return
            }
            if (code !== 0) return
            const available = new Set(fontResult.text.split(/[\n,]/).map(name => name.trim().toLowerCase()))
            window.compatibleLabelFonts = Qt.fontFamilies().filter(name => available.has(name.toLowerCase()))
                .sort((first, second) => first.localeCompare(second))
        }
    }
    Process {
        id: starterBackgrounds
        property bool attempted: false
        readonly property string packagePath: decodeURIComponent(Qt.resolvedUrl("../bin/preview-python").toString().replace(/^file:\/\//, ""))
        command: [packagePath, packagePath.replace(/preview-python$/, "background-library.py"), "seed"]
        stdout: StdioCollector { id: seedResult; waitForEnd: true }
        onExited: function(code) {
            try {
                if (code === 0 && JSON.parse(seedResult.text).seeded && window.currentSection === "background")
                    editor.refreshBackgrounds()
            } catch (error) {
                console.warn("WebcamTuner could not read the starter background result.")
            }
        }
    }
    OutputControl {
        id:outputController
        enabled:!editor.testing
        readyToStart:bootstrap.ready&&!bootstrap.busy
        configuration:editor.document?editor.previewSettings():null
        adjustingBackground: editor.adjustingBackground
        panelOpen:window.visible&&!editor.testing
    }
    BootstrapControl {
        id:bootstrap
        enabled:!editor.testing
        onPreparing:{editor.autostartRequested=false;editor.previewOn=false}
        onRefreshed:{
            if(!window.visible)return
            if(!ready){window.showSection("setup");if(!state.controllerReady)editor.message=qsTr("Complete Setup to load your profiles.")}
            if(state.controllerReady&&!editor.document&&!bridge.busy)bridge.request("read",[])
            if(ready)editor.maybeAutostart()
        }
    }
    Bridge {
        id: bridge
        onReceived: function(action, result) { editor.accept(action, result) }
        onFailed: function(message) { editor.fail(message) }
    }
    TunerPalette {
        id: themeColors
        objectName: "themeColors"
        themeBackground: window.color
        themeForeground: window.foreground
        themeAccent: window.accent
        themeWarning: window.warning
    }
    Scale {
        id: interfaceTransform
        xScale: window.interfaceScale
        yScale: window.interfaceScale
    }
    Item {
        id: themeSurface
        objectName: "tunerThemeSurface"
        width: window.width / window.interfaceScale
        height: window.height / window.interfaceScale
        transform: interfaceTransform
        readonly property Item popupOverlay: Window.window?.Overlay.overlay ?? null

        // Popups and their dimmers share the surface's scaled coordinates.
        function fitPopupOverlay() {
            if (!popupOverlay) return
            popupOverlay.width = width
            popupOverlay.height = height
        }
        function configurePopupOverlay() {
            if (popupOverlay) popupOverlay.transform = [interfaceTransform]
            Qt.callLater(fitPopupOverlay)
        }
        onWidthChanged: Qt.callLater(fitPopupOverlay)
        onHeightChanged: Qt.callLater(fitPopupOverlay)
        onPopupOverlayChanged: configurePopupOverlay()
        Component.onCompleted: configurePopupOverlay()
        Connections {
            target: themeSurface.popupOverlay
            function onWidthChanged() {
                if (target.width !== themeSurface.width) Qt.callLater(themeSurface.fitPopupOverlay)
            }
            function onHeightChanged() {
                if (target.height !== themeSurface.height) Qt.callLater(themeSurface.fitPopupOverlay)
            }
        }
        palette.window: themeColors.window
        palette.base: themeColors.base
        palette.alternateBase: themeColors.alternateBase
        palette.button: themeColors.button
        palette.windowText: themeColors.windowText
        palette.text: themeColors.text
        palette.buttonText: themeColors.buttonText
        palette.mid: themeColors.mid
        palette.midlight: themeColors.midlight
        palette.light: themeColors.light
        palette.dark: themeColors.dark
        palette.shadow: themeColors.shadow
        palette.placeholderText: themeColors.placeholderText
        palette.accent: themeColors.accent
        palette.link: themeColors.link
        palette.linkVisited: themeColors.linkVisited
        palette.highlight: themeColors.highlight
        palette.highlightedText: themeColors.highlightedText
        palette.toolTipBase: themeColors.toolTipBase
        palette.toolTipText: themeColors.toolTipText
        WindowTitleBar {
            id: titlebar
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 42
            collapsed: window.collapsed
            onMoveRequested: window.startSystemMove()
            onMinimizeRequested: window.toggleCollapse()
            onCloseRequested: window.closeEditor()
        }
        component NavigationTab: TabButton {
            id: tab
            leftPadding: 7
            rightPadding: 7
            topPadding: 5
            bottomPadding: 7
            font.bold: checked
            contentItem: Text {
                text: tab.text
                textFormat: Text.PlainText
                font: tab.font
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                color: tab.checked ? tab.palette.highlightedText : tab.palette.windowText
            }
            background: Rectangle {
                color: tab.checked ? tab.palette.highlight : tab.hovered ? tab.palette.alternateBase : tab.palette.window
                border.color: tab.activeFocus ? tab.palette.mid : "transparent"
                Rectangle {
                    objectName: "activeTabIndicator"
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 3
                    color: tab.palette.highlightedText
                    visible: tab.checked
                }
            }
        }
        TabBar {
            id: tabs
            objectName: "navigationTabs"
            anchors.top: titlebar.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            visible: !window.collapsed
            Repeater {
                model: navigation
                NavigationTab {
                    required property string sectionName
                    objectName: sectionName === "remotes" ? "remotesTab" : ""
                    text: window.tabCopy[sectionName].title
                    hoverEnabled: true
                    ToolTip.visible: hovered
                    ToolTip.delay: 500
                    ToolTip.text: window.tabCopy[sectionName].hint
                }
            }
        }
        TabBar {
            id: setupTabs
            objectName: "setupTabs"
            anchors.top: tabs.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            visible: !window.collapsed && window.currentSection === "setup"

            NavigationTab {
                text: qsTr("General")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: qsTr("Prepare the runtime and configure camera integrations.")
            }
            NavigationTab {
                text: qsTr("Test")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: qsTr("Check the video other apps receive from WebcamTuner.")
            }
        }
        AboutPanel {
            anchors.top: tabs.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            visible: !window.collapsed && window.currentSection === "about"
        }
        TestPanel {
            id:outputTests
            enabled:!editor.testing
            anchors.top:setupTabs.bottom;anchors.left:parent.left;anchors.right:parent.right;anchors.bottom:parent.bottom
            visible: !window.collapsed && window.showingOutputTest
            panelOpen:window.visible
            outputControl:outputController
        }
        Editor {
            id: editor
            anchors.top: setupTabs.visible ? setupTabs.bottom : tabs.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            visible: !window.collapsed && !window.showingOutputTest && window.currentSection !== "about"
            section: window.showingOutputTest ? "test" : window.currentSection
            outputControl:outputController
            processingReady:editor.testing||bootstrap.ready
            setupContent: Component {
                SetupPanel {
                    outputControl: editor.outputControl
                    popupPalette: themeColors
                    bootstrapControl: bootstrap
                    interfaceScalePercent: window.interfaceScalePercent
                    minimumInterfaceScale: window.minimumInterfaceScale
                    maximumInterfaceScale: window.maximumInterfaceScale
                    interfaceScaleStep: window.interfaceScaleStep
                    onInterfaceScaleRequested: percent => window.setInterfaceScale(percent)
                    showRemotesTab: preferences.showRemotesTab
                    onRemotesTabVisibilityRequested: function(show) { window.setRemotesTabVisible(show) }
                }
            }
            panelOpen: window.visible
            busy: bridge.busy
            color: window.color
            accent: themeSurface.palette.link
            popupPalette: themeColors
            labelFontFamilies: window.compatibleLabelFonts
            onRequest: function(action, args) { bridge.request(action, args) }
            onCameraTabRequested: window.showSection("camera")
        }
    }
}
