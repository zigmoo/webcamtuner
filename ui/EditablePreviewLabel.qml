import QtQuick
import QtQuick.Controls

Item {
    id: root
    property var overlay: ({enabled:false,opacity:.75,text:""})
    property bool editing: false
    property string draftText: ""
    property url bitmapSource
    property string bitmapKey: ""
    property real bitmapWidth: 0
    property real bitmapHeight: 0
    property real frameWidth: 960
    property real frameHeight: 540
    readonly property bool useBitmap: {
        if(editing || bitmapSource.toString()==="" || bitmapKey==="")return false
        try{return JSON.stringify(JSON.parse(bitmapKey))===JSON.stringify([overlay.text||"",frameWidth,frameHeight,overlay.fontFamily||"sans",!!overlay.bold,!!overlay.italic,overlay.fontSize||.034,!!overlay.allCaps])}catch(e){return false}
    }
    readonly property bool hasText: !!overlay.text || editing
    signal changed(var patch)
    signal editingStateChanged(bool active)
    visible: !!overlay.enabled && hasText
    function beginEditing() {
        draftText = overlay.text || ""
        editing = true
        editingStateChanged(true)
        field.text = draftText
        field.forceActiveFocus()
        field.selectAll()
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
        width: root.useBitmap ? root.bitmapWidth*root.width/root.frameWidth : Math.min(root.width,Math.max(35,metrics.advanceWidth+8))
        height: root.useBitmap ? root.bitmapHeight*root.height/root.frameHeight : Math.max(display.implicitHeight+6,22)
        x: Math.max(0,root.width-width)*(root.overlay.x===undefined?.02:root.overlay.x)
        y: Math.max(0,root.height-height)*(root.overlay.y===undefined?.96:root.overlay.y)
        opacity: root.editing ? 1 : root.overlay.opacity===undefined?.75:root.overlay.opacity
        Text {
            id: display
            anchors.fill:parent
            visible: !root.editing && !root.useBitmap
            text: root.overlay.allCaps ? (root.overlay.text||"").toUpperCase() : root.overlay.text||""
            textFormat: Text.PlainText
            color:"white";style:Text.Outline;styleColor:"#cc000000"
            font.family:root.overlay.fontFamily||"Sans"
            font.pixelSize:Math.max(10,Math.round(root.height*(root.overlay.fontSize||.034)))
            font.bold:!!root.overlay.bold; font.italic:!!root.overlay.italic
            wrapMode:Text.Wrap;maximumLineCount:2;elide:Text.ElideRight
        }
        Image {anchors.fill:parent;visible:root.useBitmap;source:root.bitmapSource;fillMode:Image.PreserveAspectFit;cache:false}
        MouseArea {
            objectName: "previewLabelDrag"
            anchors.fill:parent
            enabled:!root.editing
            preventStealing:true
            cursorShape:pressed?Qt.ClosedHandCursor:Qt.OpenHandCursor
            property point startPointer
            property real startX
            property real startY
            onPressed:function(mouse){startPointer=mapToItem(root,mouse.x,mouse.y);startX=label.x;startY=label.y}
            onPositionChanged:function(mouse){
                if(!pressed)return
                var p=mapToItem(root,mouse.x,mouse.y)
                root.changed({x:Math.max(0,Math.min(1,(startX+p.x-startPointer.x)/Math.max(1,root.width-label.width))),y:Math.max(0,Math.min(1,(startY+p.y-startPointer.y)/Math.max(1,root.height-label.height)))})
            }
            onDoubleClicked:root.beginEditing()
        }
        TextField {
            id:field
            objectName:"previewLabelText"
            anchors.fill:parent
            visible:root.editing
            maximumLength:80
            font:display.font
            color:"white"
            selectByMouse:true
            padding:2
            background:Rectangle{color:"#c0202933";border.color:"#93c5aa";radius:3}
            onTextEdited:root.draftText=text
            onAccepted:root.finishEditing(true)
            onActiveFocusChanged:if(!activeFocus&&root.editing)root.finishEditing(true)
            Keys.onEscapePressed:root.finishEditing(false)
        }
    }
}
