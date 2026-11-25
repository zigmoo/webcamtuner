import QtQuick
import QtQuick.Controls

Item {
    id: root
    property var overlay: ({enabled:false,opacity:.75,text:""})
    property bool mirrored: false
    property bool showMoveHandles: false
    property bool moveSelected: false
    property color moveAccent: "#93c5aa"
    property bool presentationVisible: true
    property bool editing: false
    property string draftText: ""
    // Measure in a fixed 16:9 frame, then scale to either preview.
    readonly property real frameWidth: 960
    readonly property real frameHeight: 540
    readonly property bool hasText: !!overlay.text || editing
    readonly property real fontSize: resizeState ? resizeFontSize : (overlay.fontSize ?? .034)
    property point moveOrigin
    property size moveRange
    property var resizeState: null
    property real resizeFontSize: .034
    readonly property bool dragging: positionDrag.pressed || resizeState !== null
    signal changed(var patch)
    signal editingStateChanged(bool active)
    visible: presentationVisible && !!overlay.enabled && hasText
    onVisibleChanged: if (!visible) moveSelected = false
    function containsMoveFrame(scenePosition) {
        return moveFrame.contains(moveFrame.mapFromItem(null, scenePosition.x, scenePosition.y))
    }
    function beginMove() {
        moveOrigin = Qt.point(overlay.x ?? .02, overlay.y ?? .96)
        moveRange = Qt.size(Math.max(1, width - label.width), Math.max(1, height - label.height))
    }
    function moveBy(dx, dy) {
        const direction = mirrored ? -1 : 1
        changed({
            x: Math.max(0, Math.min(1, moveOrigin.x + direction * dx / moveRange.width)),
            y: Math.max(0, Math.min(1, moveOrigin.y + dy / moveRange.height))
        })
    }
    function beginResize(index, pointer) {
        const left = index % 2 === 0
        const top = index < 2
        resizeFontSize = fontSize
        resizeState = {
            anchor: Qt.point(label.x + (left ? label.width : 0), label.y + (top ? label.height : 0)),
            direction: Qt.point(left ? -label.width : label.width, top ? -label.height : label.height),
            startPointer: pointer,
            startSize: fontSize,
            left: left,
            top: top
        }
    }
    function resizeTo(pointer) {
        const state = resizeState
        const vector = state.direction
        const dx = pointer.x - state.startPointer.x
        const dy = pointer.y - state.startPointer.y
        const growth = (dx * vector.x + dy * vector.y) / Math.max(1, vector.x * vector.x + vector.y * vector.y)
        resizeFontSize = Math.max(.012, Math.min(.15, state.startSize * (1 + growth)))
    }
    function finishResize(commit) {
        if (!resizeState) return
        const value = {
            fontSize: resizeFontSize,
            x: width > label.width ? label.x / (width - label.width) : (overlay.x ?? .02),
            y: height > label.height ? label.y / (height - label.height) : (overlay.y ?? .96)
        }
        if (commit && resizeFontSize !== resizeState.startSize) changed(value)
        resizeState = null
    }
    function labelPosition(available, size, fraction, anchor, pinnedFarEdge) {
        const range = Math.max(0, available - size)
        if (!resizeState) return range * fraction
        return Math.max(0, Math.min(range, anchor - (pinnedFarEdge ? size : 0)))
    }
    function beginEditing() {
        draftText = overlay.text || ""
        editing = true
        editingStateChanged(true)
        field.text = draftText
        field.forceActiveFocus()
        field.selectAll()
    }
    function commitOutside(scenePosition) {
        if (!editing) return
        const point = field.mapFromItem(null, scenePosition.x, scenePosition.y)
        if (!field.contains(point)) finishEditing(true)
    }
    function finishEditing(commit) {
        if (!editing) return
        var text = field.text.trim()
        editing = false
        if (commit && text !== (overlay.text || "")) changed({text:text})
        editingStateChanged(false)
    }
    TextMetrics { id: metrics; font: display.font; text: root.editing ? root.draftText : root.overlay.allCaps ? (root.overlay.text||"").toUpperCase() : root.overlay.text||"" }
    Item {
        id: label
        objectName: "interactivePreviewLabel"
        readonly property real referenceWidth: Math.min(root.frameWidth, Math.max(35, metrics.advanceWidth + 8))
        readonly property real referenceHeight: Math.max(display.implicitHeight + 6, 22)
        width: referenceWidth * root.width / root.frameWidth
        height: referenceHeight * root.height / root.frameHeight
        x: root.labelPosition(root.width, width, root.overlay.x ?? .02, root.resizeState?.anchor.x, root.resizeState?.left)
        y: root.labelPosition(root.height, height, root.overlay.y ?? .96, root.resizeState?.anchor.y, root.resizeState?.top)
        opacity: root.editing ? 1 : root.overlay.opacity===undefined?.75:root.overlay.opacity
        Text {
            id: display
            width: label.referenceWidth
            transform: Scale {
                xScale: root.width / root.frameWidth
                yScale: root.height / root.frameHeight
            }
            visible: !root.editing
            text: root.overlay.allCaps ? (root.overlay.text||"").toUpperCase() : root.overlay.text||""
            textFormat: Text.PlainText
            color:root.overlay.color||"#ffffff";style:Text.Outline;styleColor:"#cc000000"
            font.family:root.overlay.fontFamily||"Sans"
            font.pixelSize: Math.max(10, Math.round(root.frameHeight * root.fontSize))
            font.bold:!!root.overlay.bold; font.italic:!!root.overlay.italic
            wrapMode:Text.Wrap;maximumLineCount:2;elide:Text.ElideRight
        }
        MouseArea {
            objectName: "previewLabelTextTarget"
            anchors.fill:parent
            enabled:!root.editing
            preventStealing:true
            cursorShape: Qt.IBeamCursor
            onDoubleClicked:root.beginEditing()
        }
        TextField {
            id:field
            // Editing controls stay readable while the rendered label mirrors.
            transform: Scale { origin.x: field.width / 2; xScale: root.mirrored ? -1 : 1 }
            objectName:"previewLabelText"
            anchors.fill:parent
            visible:root.editing
            maximumLength:80
            font.family: display.font.family
            font.pixelSize: Math.max(10, Math.round(display.font.pixelSize * root.height / root.frameHeight))
            font.bold: display.font.bold
            font.italic: display.font.italic
            color:root.overlay.color||"#ffffff"
            selectByMouse:true
            padding:2
            background:Rectangle{color:"#c0202933";border.color:"#93c5aa";radius:3}
            onTextEdited:root.draftText=text
            onAccepted:root.finishEditing(true)
            onActiveFocusChanged:if(!activeFocus&&root.editing)root.finishEditing(true)
            Keys.onEscapePressed:root.finishEditing(false)
        }
    }
    Rectangle {
        id: moveFrame
        objectName: "previewLabelMoveHandles"
        width: Math.min(root.width, Math.max(24, label.width))
        height: Math.min(root.height, Math.max(24, label.height))
        x: Math.min(root.width - width, Math.max(0, label.x + (label.width - width) / 2))
        y: Math.min(root.height - height, Math.max(0, label.y + (label.height - height) / 2))
        visible: !root.editing && (root.moveSelected || root.showMoveHandles || positionDrag.pressed || root.resizeState !== null)
        color: "transparent"
        border.color: root.moveAccent
        MouseArea {
            id: positionDrag
            objectName: "previewLabelPositionDrag"
            anchors.fill: parent
            preventStealing: true
            cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
            property point startPointer
            onPressed: function(mouse) {
                startPointer = mapToItem(root, mouse.x, mouse.y)
                root.beginMove()
            }
            onPositionChanged: function(mouse) {
                if (!pressed) return
                const point = mapToItem(root, mouse.x, mouse.y)
                root.moveBy(point.x - startPointer.x, point.y - startPointer.y)
            }
            onDoubleClicked: root.beginEditing()
        }
        Repeater {
            model: 4
            MouseArea {
                required property int index
                objectName: "previewLabelResize-" + index
                width: 12
                height: 12
                x: index % 2 === 0 ? 0 : parent.width - width
                y: index < 2 ? 0 : parent.height - height
                cursorShape: ((index === 0 || index === 3) !== root.mirrored)
                    ? Qt.SizeFDiagCursor : Qt.SizeBDiagCursor
                preventStealing: true
                onPressed: function(mouse) { root.beginResize(index, mapToItem(root, mouse.x, mouse.y)) }
                onPositionChanged: function(mouse) {
                    if (pressed) root.resizeTo(mapToItem(root, mouse.x, mouse.y))
                }
                onReleased: root.finishResize(true)
                onCanceled: root.finishResize(false)
                Rectangle {
                    anchors.centerIn: parent
                    width: 8
                    height: 8
                    color: root.moveAccent
                    border.color: "#18202a"
                    radius: 1
                }
            }
        }
    }
}
