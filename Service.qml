import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons as Commons
import "ui" as Tuner
import "ui/BuildInfo.js" as BuildInfo

Scope {
    id: root
    property var shell: null
    readonly property bool opened: panel.visible
    readonly property var window: panel
    property alias editor: panel.editor
    function open() { panel.openEditor() }
    function close() { panel.closeEditor() }
    function setup() { panel.openSetup() }
    function backgrounds() { panel.openBackgrounds() }
    function toggle() { opened ? close() : open() }
    IpcHandler {
        target: "moo.webcamtuner"
        function open(): void { root.open() }
        function close(): void { root.close() }
        function setup(): void { panel.openSetup() }
        function backgrounds(): void { panel.openBackgrounds() }
        function camera(): void { panel.openCamera() }
        function toggle(): void { root.toggle() }
        function minimize(): void { if (root.opened && !panel.collapsed) panel.toggleCollapse() }
        function prepareUpdate(): string { return JSON.stringify(panel.editor.prepareUpdate()) }
        function resumeWrites(): void { panel.editor.resumeAutomaticWrites() }
        function draft(): string { return JSON.stringify(panel.editor.exportDraft()) }
        function restoreDraft(snapshot: string): bool {
            if (snapshot.length > 131072) return false
            try { return panel.editor.restoreDraft(JSON.parse(snapshot)) }
            catch (e) { return false }
        }
        function status(): string {
            return JSON.stringify({ version: BuildInfo.version, section:panel.editor.section, opened: root.opened, collapsed: panel.collapsed, width: panel.width, height: panel.height,
                busy: panel.editor.busy, dirty: panel.editor.dirty, message: panel.editor.message,
                mirror: panel.editor.mirror, autostartCamera: panel.editor.autostartCamera, previewOn: panel.editor.previewOn,
                sharedControls: true, draftRecovery: true, autosave: true, labelEditing:panel.editor.labelEditing, labelPending:panel.editor.labelInFlight!==null || Object.keys(panel.editor.labelDrafts).length>0, saving: panel.editor.savePending, saveFailed: panel.editor.saveFailed || panel.editor.labelSaveFailed, revision: panel.editor.document ? panel.editor.document.revision : -1, broadcasting: false })
        }
    }
    Tuner.TunerWindow {
        id: panel
        color: Commons.Color.background
        accent: Commons.Color.accent
    }
}
