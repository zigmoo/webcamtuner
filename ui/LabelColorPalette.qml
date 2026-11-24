import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Window {
    id: root
    objectName: "labelColorDialog"
    required property Palette sourcePalette
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
    title: qsTr("Label text color")
    flags: Qt.Dialog | Qt.FramelessWindowHint
    modality: Qt.NonModal
    width: 320
    height: controls.implicitHeight + 24
    color: root.palette.window

    property color originalColor: "#ffffff"
    property color selectedColor: "#ffffff"
    property real hue: 0
    property bool sampling: false
    readonly property bool dragging: paletteDrag.pressed || spectrum.pressed || hueSlider.pressed
    property bool activatedSinceOpen: false
    property string pickerMessage: ""
    signal colorEdited(string color)

    function open(initialColor) {
        originalColor = initialColor
        selectedColor = originalColor
        hue = selectedColor.hsvHue < 0 ? 0 : selectedColor.hsvHue
        pickerMessage = ""
        show()
        requestActivate()
    }

    function applyColor(color, syncHue) {
        if (Qt.colorEqual(selectedColor, color)) return
        selectedColor = color
        if (syncHue && selectedColor.hsvHue >= 0) hue = selectedColor.hsvHue
        const hex = selectedColor.toString()
        if (!hexField.activeFocus) hexField.text = hex
        colorEdited(hex)
    }

    function cancel() {
        if (!Qt.colorEqual(selectedColor, originalColor))
            applyColor(originalColor, true)
        close()
    }

    onVisibleChanged: {
        if (visible) {
            activatedSinceOpen = active
            hexField.text = selectedColor.toString()
        } else {
            activatedSinceOpen = false
            sampling = false
        }
    }
    onActiveChanged: {
        if (active && visible) activatedSinceOpen = true
        else if (visible && activatedSinceOpen && !sampling) close()
    }

    Rectangle { anchors.fill: parent; color: "transparent"; border.color: root.palette.mid }
    Shortcut { sequence: "Escape"; enabled: root.visible && !root.sampling; onActivated: root.cancel() }

    ColumnLayout {
        id: controls
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 12
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            Label {
                Layout.fillWidth: true
                Layout.fillHeight: true
                text: "⠿  " + root.title
                color: root.palette.windowText
                font.bold: true
                verticalAlignment: Text.AlignVCenter
                Accessible.name: qsTr("Drag to move the color palette")
                MouseArea {
                    id: paletteDrag
                    objectName: "labelColorDragHandle"
                    anchors.fill: parent
                    cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                    onPressed: root.startSystemMove()
                }
            }
            ToolButton {
                objectName: "labelColorClose"
                text: "×"
                Accessible.name: qsTr("Close and keep the current color")
                onClicked: root.close()
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 138
            Rectangle { anchors.fill: parent; color: Qt.hsva(root.hue, 1, 1, 1) }
            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: "white" }
                    GradientStop { position: 1; color: "transparent" }
                }
            }
            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0; color: "transparent" }
                    GradientStop { position: 1; color: "black" }
                }
            }
            Rectangle {
                width: 12
                height: 12
                radius: 6
                x: Math.min(parent.width - width, Math.max(0, root.selectedColor.hsvSaturation * parent.width - width / 2))
                y: Math.min(parent.height - height, Math.max(0, (1 - root.selectedColor.hsvValue) * parent.height - height / 2))
                color: root.selectedColor
                border.color: root.selectedColor.hsvValue > .5 ? "black" : "white"
                border.width: 2
            }
            MouseArea {
                id: spectrum
                objectName: "labelColorSpectrum"
                anchors.fill: parent
                cursorShape: Qt.CrossCursor
                function pick(x, y) {
                    const saturation = Math.max(0, Math.min(1, x / width))
                    const value = Math.max(0, Math.min(1, 1 - y / height))
                    root.applyColor(Qt.hsva(root.hue, saturation, value, 1), false)
                }
                onPressed: function(mouse) { pick(mouse.x, mouse.y) }
                onPositionChanged: function(mouse) { if (pressed) pick(mouse.x, mouse.y) }
            }
        }
        Slider {
            id: hueSlider
            objectName: "labelColorHue"
            Layout.fillWidth: true
            value: root.hue
            Accessible.name: qsTr("Hue")
            onMoved: {
                root.hue = value
                root.applyColor(Qt.hsva(value, root.selectedColor.hsvSaturation || 1, root.selectedColor.hsvValue || 1, 1), false)
            }
            background: Rectangle {
                x: hueSlider.leftPadding
                y: hueSlider.topPadding + (hueSlider.availableHeight - height) / 2
                width: hueSlider.availableWidth
                height: 8
                radius: 4
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: "red" }
                    GradientStop { position: 1 / 6; color: "yellow" }
                    GradientStop { position: 2 / 6; color: "lime" }
                    GradientStop { position: 3 / 6; color: "cyan" }
                    GradientStop { position: 4 / 6; color: "blue" }
                    GradientStop { position: 5 / 6; color: "magenta" }
                    GradientStop { position: 1; color: "red" }
                }
            }
        }
        RowLayout {
            Rectangle {
                objectName: "labelColorSwatch"
                Layout.preferredWidth: 28
                Layout.preferredHeight: 28
                radius: 3
                color: root.selectedColor
                border.color: root.palette.mid
            }
            ToolButton {
                objectName: "labelColorEyedropper"
                icon.source: "data:image/svg+xml;utf8," + encodeURIComponent(
                    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="none" stroke="' + root.palette.windowText + '" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="m13 6 5-4 4 4-4 5M11 5l8 8M13 7l-8 8-1 4 4-1 8-8M4 19l-2 2"/></svg>')
                enabled: !root.sampling
                Accessible.name: qsTr("Eyedropper")
                ToolTip.visible: hovered
                ToolTip.text: qsTr("Click anywhere on the screen to pick a color.")
                onClicked: {
                    root.pickerMessage = ""
                    root.sampling = true
                }
            }
            TextField {
                id: hexField
                objectName: "labelColorHex"
                Layout.fillWidth: true
                Accessible.name: qsTr("Hex color")
                maximumLength: 7
                selectByMouse: true
                onTextEdited: if (/^#[0-9a-fA-F]{6}$/.test(text)) root.applyColor(text, true)
                onEditingFinished: text = root.selectedColor.toString()
            }
        }
        Label {
            Layout.fillWidth: true
            visible: text !== ""
            text: root.sampling ? qsTr("Click anywhere on the screen to pick a color.") : root.pickerMessage
            color: root.palette.windowText
            wrapMode: Text.WordWrap
        }
        Button {
            objectName: "labelColorCancel"
            Layout.alignment: Qt.AlignRight
            text: qsTr("Cancel")
            onClicked: root.cancel()
        }
    }

    Loader {
        id: sampler
        active: root.sampling
        source: Qt.resolvedUrl("ScreenColorPicker.qml")
        onStatusChanged: if (status === Loader.Error) {
            root.pickerMessage = qsTr("The screen color picker is unavailable.")
            root.sampling = false
        }
    }
    Connections {
        target: sampler.item
        function onFinished(color, failed) {
            if (color) {
                root.applyColor(color, true)
                hexField.text = root.selectedColor.toString()
            } else if (failed) {
                root.pickerMessage = qsTr("Couldn’t sample a screen color.")
            }
            Qt.callLater(function() {
                if (root.visible) root.requestActivate()
                root.sampling = false
            })
        }
    }
}
