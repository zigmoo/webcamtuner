import QtQuick

Palette {
    id: root
    required property color themeBackground
    required property color themeForeground
    required property color themeAccent
    required property color themeWarning

    function mix(base, added, amount) {
        return Qt.rgba(base.r + (added.r - base.r) * amount, base.g + (added.g - base.g) * amount,
            base.b + (added.b - base.b) * amount, 1)
    }

    function linear(channel) {
        return channel <= 0.04045 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4)
    }

    function luminance(value) {
        return 0.2126 * linear(value.r) + 0.7152 * linear(value.g) + 0.0722 * linear(value.b)
    }

    function contrast(first, second) {
        const a = luminance(first)
        const b = luminance(second)
        return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
    }

    function readable(ink, paper, minimum, raised = paper) {
        const dark = Qt.rgba(0, 0, 0, 1)
        const light = Qt.rgba(1, 1, 1, 1)
        const endpoint = Math.min(contrast(dark, paper), contrast(dark, raised))
            >= Math.min(contrast(light, paper), contrast(light, raised)) ? dark : light
        for (let step = 0; step <= 10; step++) {
            const candidate = mix(ink, endpoint, step / 10)
            if (Math.min(contrast(candidate, paper), contrast(candidate, raised)) >= minimum) return candidate
        }
        return endpoint
    }

    window: themeBackground
    base: mix(themeBackground, themeForeground, 0.04)
    alternateBase: mix(themeBackground, themeForeground, 0.09)
    button: mix(themeBackground, themeForeground, 0.10)
    windowText: readable(themeForeground, window, 4.5, alternateBase)
    text: readable(themeForeground, base, 4.5)
    buttonText: readable(themeForeground, button, 4.5)
    mid: readable(mix(window, windowText, 0.43), window, 3)
    midlight: mix(window, windowText, 0.16)
    light: mix(window, windowText, 0.22)
    dark: mix(window, windowText, 0.28)
    shadow: mix(window, windowText, 0.34)
    placeholderText: readable(mix(window, windowText, 0.66), window, 4.5, alternateBase)
    accent: readable(themeAccent, window, 4.5, alternateBase)
    link: accent
    linkVisited: readable(themeWarning, window, 4.5, alternateBase)
    highlight: accent
    highlightedText: readable(window, highlight, 4.5)
    toolTipBase: alternateBase
    toolTipText: readable(themeForeground, toolTipBase, 4.5)

    disabled: ColorGroup {
        windowText: root.readable(root.placeholderText, root.window, 3)
        text: root.readable(root.placeholderText, root.base, 3)
        buttonText: root.readable(root.placeholderText, root.button, 3)
    }
}
