import QtQuick
import QtQuick.Controls

Dialog {
    id: root
    required property Palette sourcePalette
    property var standardButtonHelp: ({})
    palette.window: sourcePalette.window
    palette.base: sourcePalette.base
    palette.alternateBase: sourcePalette.alternateBase
    palette.button: sourcePalette.button
    palette.windowText: sourcePalette.windowText
    palette.text: sourcePalette.text
    palette.buttonText: sourcePalette.buttonText
    palette.mid: sourcePalette.mid
    palette.midlight: sourcePalette.midlight
    palette.light: sourcePalette.light
    palette.dark: sourcePalette.dark
    palette.shadow: sourcePalette.shadow
    palette.placeholderText: sourcePalette.placeholderText
    palette.accent: sourcePalette.accent
    palette.link: sourcePalette.link
    palette.linkVisited: sourcePalette.linkVisited
    palette.highlight: sourcePalette.highlight
    palette.highlightedText: sourcePalette.highlightedText
    palette.toolTipBase: sourcePalette.toolTipBase
    palette.toolTipText: sourcePalette.toolTipText

    parent: Overlay.overlay
    anchors.centerIn: parent
    margins: 16
    width: parent ? Math.min(implicitWidth, Math.max(0, parent.width - 2 * margins)) : implicitWidth
    height: parent ? Math.min(implicitHeight, Math.max(0, parent.height - 2 * margins)) : implicitHeight

    onOpened: {
        for (const role in standardButtonHelp) {
            const button = standardButton(Number(role))
            if (!button) continue
            button.hoverEnabled = true
            button.ToolTip.text = standardButtonHelp[role]
            button.ToolTip.delay = 500
            button.ToolTip.visible = Qt.binding(function() { return button.hovered })
        }
    }
}
