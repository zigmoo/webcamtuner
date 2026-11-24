import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RowLayout {
    id: root
    property alias leadingControls: leading.data
    property Palette popupPalette: palette
    property var fontFamilies: []
    property var overlay: ({enabled:false,opacity:.75,text:""})
    property bool available: false
    readonly property bool dragging: formatDrag.pressed || fontSizeSlider.pressed || opacitySlider.pressed || colorPicker.dragging
    property string colorContext: ""
    onColorContextChanged: colorPicker.close()
    onVisibleChanged: {
        if (visible) return
        formatPopup.close()
        colorPicker.close()
    }
    property string feedback: ""
    signal changed(var patch)
    signal editRequested()

    function openColorPalette() {
        colorPicker.open(root.overlay.color || "#ffffff")
    }
    RowLayout {
        id: leading
        visible: children.length > 0
    }
    CheckBox {
        id: showLabel
        hoverEnabled: true
        ToolTip.visible: hovered
        ToolTip.delay: 500
        ToolTip.text: qsTr("Show the label on the finished camera feed.")
        objectName:"showPreviewLabel"
        text: qsTr("Show Label")
        indicator: Rectangle {
            implicitWidth: 16
            implicitHeight: 16
            x: showLabel.leftPadding
            y: showLabel.topPadding + (showLabel.availableHeight - height) / 2
            radius: 3
            border.width: 2
            border.color: showLabel.activeFocus ? showLabel.palette.highlight : showLabel.palette.windowText
            color: showLabel.checked ? showLabel.palette.highlight : showLabel.palette.window

            Text {
                anchors.centerIn: parent
                visible: showLabel.checked
                text: "✓"
                font.pixelSize: 13
                font.bold: true
                color: showLabel.palette.highlightedText
            }
        }
        checked:root.available && !!root.overlay.enabled
        nextCheckState:function(){return checkState}
        enabled:root.available
        onClicked:root.changed({enabled:!checked})
    }
    Button {
        hoverEnabled: true
        ToolTip.visible: hovered
        ToolTip.delay: 500
        ToolTip.text: qsTr("Edit the label directly on the preview.")
        text:qsTr("Edit label")
        visible:root.available && !!root.overlay.enabled
        onClicked:root.editRequested()
    }
    Button {
        hoverEnabled: true
        ToolTip.visible: hovered
        ToolTip.delay: 500
        ToolTip.text: qsTr("Change the label’s font, color, size, and opacity.")
        objectName:"labelFormatButton"
        text:qsTr("Format…")
        visible:root.available && !!root.overlay.enabled
        onClicked:formatPopup.open()
        Popup {
            id:formatPopup
            objectName:"labelFormatPopup"
            parent: Overlay.overlay
            property point dragOffset: Qt.point(0, 0)
            palette.window: root.popupPalette.window
            palette.base: root.popupPalette.base
            palette.alternateBase: root.popupPalette.alternateBase
            palette.button: root.popupPalette.button
            palette.windowText: root.popupPalette.windowText
            palette.text: root.popupPalette.text
            palette.buttonText: root.popupPalette.buttonText
            palette.mid: root.popupPalette.mid
            palette.midlight: root.popupPalette.midlight
            palette.light: root.popupPalette.light
            palette.dark: root.popupPalette.dark
            palette.shadow: root.popupPalette.shadow
            palette.placeholderText: root.popupPalette.placeholderText
            palette.accent: root.popupPalette.accent
            palette.link: root.popupPalette.link
            palette.linkVisited: root.popupPalette.linkVisited
            palette.highlight: root.popupPalette.highlight
            palette.highlightedText: root.popupPalette.highlightedText
            palette.toolTipBase: root.popupPalette.toolTipBase
            palette.toolTipText: root.popupPalette.toolTipText
            margins: 16
            readonly property real centerX: parent ? (parent.width - width) / 2 : 0
            readonly property real centerY: parent ? (parent.height - height) / 2 : 0
            x: Math.max(margins, Math.min(2 * centerX - margins, centerX + dragOffset.x))
            y: Math.max(margins, Math.min(2 * centerY - margins, centerY + dragOffset.y))
            width: parent ? Math.min(340, Math.max(0, parent.width - 2 * margins)) : 340
            height: parent ? Math.min(implicitHeight, Math.max(0, parent.height - 2 * margins)) : implicitHeight
            focus: true
            padding: 14
            contentItem: ColumnLayout {
                spacing: 8
                Label {
                    Layout.fillWidth: true
                    text: "⠿  " + qsTr("Label format")
                    font.bold: true
                    MouseArea {
                        id: formatDrag
                        objectName: "labelFormatDragHandle"
                        anchors.fill: parent
                        preventStealing: true
                        cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                        property point origin
                        property point pointer
                        onPressed: function(mouse) {
                            pointer = mapToItem(formatPopup.parent, mouse.x, mouse.y)
                            origin = Qt.point(formatPopup.x - formatPopup.centerX, formatPopup.y - formatPopup.centerY)
                        }
                        onPositionChanged: function(mouse) {
                            if (!pressed) return
                            const current = mapToItem(formatPopup.parent, mouse.x, mouse.y)
                            formatPopup.dragOffset = Qt.point(origin.x + current.x - pointer.x,
                                origin.y + current.y - pointer.y)
                        }
                    }
                }
                ScrollView {
                    id: formatScroll
                    objectName: "labelFormatScroll"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    implicitHeight: formatFields.implicitHeight
                    contentWidth: availableWidth
                    contentHeight: formatFields.implicitHeight
                    clip: true
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                    ColumnLayout {
                        id: formatFields
                        width: formatScroll.availableWidth
                        spacing:8
                        ComboBox {
                            objectName:"labelFontFamily"
                            Layout.fillWidth:true
                            model: root.fontFamilies
                            enabled: count > 0
                            currentIndex: root.fontFamilies.indexOf(root.overlay.fontFamily || "Sans")
                            displayText: currentIndex < 0 ? qsTr("Choose a font") : currentText
                            onActivated:function(index){root.changed({fontFamily:model[index]})}
                            Accessible.name:qsTr("Label font")
                        }
                        RowLayout {
                            CheckBox {
                                hoverEnabled: true
                                ToolTip.visible: hovered
                                ToolTip.delay: 500
                                ToolTip.text: qsTr("Toggle bold label text.")
                                objectName:"labelBold"
                                text:qsTr("Bold")
                                checked:!!root.overlay.bold
                                nextCheckState:function(){return checkState}
                                onClicked:root.changed({bold:!checked})
                            }
                            CheckBox {
                                hoverEnabled: true
                                ToolTip.visible: hovered
                                ToolTip.delay: 500
                                ToolTip.text: qsTr("Toggle italic label text.")
                                objectName:"labelItalic"
                                text:qsTr("Italic")
                                checked:!!root.overlay.italic
                                nextCheckState:function(){return checkState}
                                onClicked:root.changed({italic:!checked})
                            }
                            CheckBox {
                                hoverEnabled: true
                                ToolTip.visible: hovered
                                ToolTip.delay: 500
                                ToolTip.text: qsTr("Show the label in uppercase.")
                                objectName:"labelAllCaps"
                                text:qsTr("All caps")
                                checked:!!root.overlay.allCaps
                                nextCheckState:function(){return checkState}
                                onClicked:root.changed({allCaps:!checked})
                            }
                        }
                        RowLayout {
                            Label { text: qsTr("Text Color") }
                            ToolButton {
                                id: colorSwatch
                                objectName: "labelFormatColorSwatch"
                                Layout.preferredWidth: 24
                                Layout.preferredHeight: 24
                                padding: 0
                                hoverEnabled: true
                                Accessible.name: qsTr("Choose label color")
                                ToolTip.visible: hovered
                                ToolTip.delay: 500
                                ToolTip.text: qsTr("Choose a color for the label.")
                                background: Rectangle {
                                    radius: 3
                                    color: root.overlay.color || "#ffffff"
                                    border.color: colorSwatch.activeFocus || colorSwatch.hovered
                                        ? colorSwatch.palette.highlight : colorSwatch.palette.mid
                                }
                                onClicked: root.openColorPalette()
                            }
                            Button {
                                hoverEnabled: true
                                ToolTip.visible: hovered
                                ToolTip.delay: 500
                                ToolTip.text: qsTr("Choose a color for the label.")
                                objectName:"labelColorPicker"
                                text:qsTr("Choose…")
                                onClicked: root.openColorPalette()
                            }
                        }
                        Label { text:qsTr("Text size · %1%").arg(Math.round((root.overlay.fontSize||.034)*100)) }
                        Slider { id: fontSizeSlider; objectName:"labelFontSize";Layout.fillWidth:true;from:.012;to:.15;value:root.overlay.fontSize||.034;onMoved:root.changed({fontSize:value}) }
                        Label { text:qsTr("Opacity · %1%").arg(Math.round((root.overlay.opacity===undefined?.75:root.overlay.opacity)*100)) }
                        Slider { id: opacitySlider; objectName:"labelOpacity";Layout.fillWidth:true;from:0;to:1;value:root.overlay.opacity===undefined?.75:root.overlay.opacity;onMoved:root.changed({opacity:value}) }
                        Label { text:qsTr("Use the Label drag handle beneath the preview to move it. Double-click the label to edit its text.");textFormat:Text.PlainText;wrapMode:Text.WordWrap;Layout.fillWidth:true }
                    }
                }
            }
        }
    }
    Item { Layout.fillWidth:true }
    Label { text:root.feedback;textFormat:Text.PlainText;elide:Text.ElideRight;Layout.maximumWidth:150 }
    MouseArea {
        parent: Overlay.overlay || root
        anchors.fill: parent
        z: 1000
        enabled: colorPicker.visible && !colorPicker.sampling
        visible: enabled
        onPressed: function(mouse) {
            colorPicker.close()
            mouse.accepted = false
        }
    }
    LabelColorPalette {
        id: colorPicker
        sourcePalette: root.popupPalette
        onColorEdited: function(color) { root.changed({color: color}) }
    }
}
