import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    objectName: "backgroundCropCanvas"
    color: "#0e131b"
    clip: true
    property url imageSource
    property var crop: ({zoom: 1, centerX: 0.5, centerY: 0.5})
    property bool locked: false
    property real maximumZoom: 32
    property bool hasFrame: false
    property real frameAspect: 16 / 9
    property bool streamSource: false
    property string loadingText: qsTr("Loading image…")
    onImageSourceChanged: {
        var stream=imageSource.toString().indexOf("data:image/")===0
        if(!stream || !streamSource || imageSource.toString()==="")hasFrame=false
        streamSource=stream
    }
    readonly property real aspect: 16 / 9
    readonly property rect imageBounds: {
        var w=Math.min(Math.max(0,width-36),Math.max(0,height-36)*frameAspect),h=w/frameAspect
        return Qt.rect((width-w)/2,(height-h)/2,w,h)
    }
    readonly property real widestCrop: Math.min(imageBounds.width, imageBounds.height * aspect)
    readonly property rect selection: {
        var w = widestCrop / crop.zoom, h = w / aspect, b = imageBounds
        return Qt.rect(b.x + Math.max(0, Math.min(b.width - w, crop.centerX * b.width - w / 2)),
            b.y + Math.max(0, Math.min(b.height - h, crop.centerY * b.height - h / 2)), w, h)
    }
    signal edited(var value)
    function chooseRect(x, y, width) {
        var b = imageBounds
        if (locked || b.width <= 0 || b.height <= 0) return
        var w = Math.max(widestCrop / maximumZoom, Math.min(widestCrop, width)), h = w / aspect
        x = Math.max(b.x, Math.min(b.x + b.width - w, x))
        y = Math.max(b.y, Math.min(b.y + b.height - h, y))
        edited({zoom: widestCrop / w, centerX: (x + w / 2 - b.x) / b.width, centerY: (y + h / 2 - b.y) / b.height})
    }
    function resizeSelection(start, hx, hy, dx, dy) {
        var b = imageBounds
        var ax = hx < 0 ? start.x + start.width : hx > 0 ? start.x : start.x + start.width / 2
        var ay = hy < 0 ? start.y + start.height : hy > 0 ? start.y : start.y + start.height / 2
        var proposed = hx === 0 ? start.width + hy * dy * aspect : start.width + hx * dx
        if (hx !== 0 && hy !== 0) proposed = Math.max(proposed, start.width + hy * dy * aspect)
        var maxX = hx < 0 ? ax - b.x : hx > 0 ? b.x + b.width - ax : 2 * Math.min(ax - b.x, b.x + b.width - ax)
        var maxY = (hy < 0 ? ay - b.y : hy > 0 ? b.y + b.height - ay : 2 * Math.min(ay - b.y, b.y + b.height - ay)) * aspect
        var w = Math.max(widestCrop / maximumZoom, Math.min(maxX, maxY, proposed)), h = w / aspect
        chooseRect(hx < 0 ? ax - w : hx > 0 ? ax : ax - w / 2,
            hy < 0 ? ay - h : hy > 0 ? ay : ay - h / 2, w)
    }
    Image {
        id: photo
        anchors.fill: parent
        anchors.margins: 18
        source: root.imageSource
        asynchronous: true
        cache: false
        retainWhileLoading: true
        autoTransform: true
        fillMode: Image.PreserveAspectFit
        sourceSize: Qt.size(2048, 2048)
        onStatusChanged: if(status===Image.Ready){
            if(implicitWidth>0&&implicitHeight>0)root.frameAspect=implicitWidth/implicitHeight
            root.hasFrame=true
        }
    }
    MouseArea {
        objectName: "cropNewSelection"
        anchors.fill: parent
        enabled: root.hasFrame && !root.locked
        preventStealing: true
        cursorShape: Qt.CrossCursor
        property point start
        property bool drawing: false
        onPressed: function(mouse) {
            var b = root.imageBounds
            drawing = mouse.x >= b.x && mouse.x <= b.x + b.width && mouse.y >= b.y && mouse.y <= b.y + b.height
            start = Qt.point(mouse.x, mouse.y)
        }
        onPositionChanged: function(mouse) {
            if (!pressed || !drawing) return
            var b = root.imageBounds, dx = mouse.x - start.x, dy = mouse.y - start.y
            var w = Math.max(Math.abs(dx), Math.abs(dy) * root.aspect)
            w = Math.min(w, dx < 0 ? start.x - b.x : b.x + b.width - start.x,
                (dy < 0 ? start.y - b.y : b.y + b.height - start.y) * root.aspect)
            if (w < root.widestCrop / root.maximumZoom) return
            root.chooseRect(dx < 0 ? start.x - w : start.x, dy < 0 ? start.y - w / root.aspect : start.y, w)
        }
    }
    // Four shades leave the selected source area visible at its original scale.
    Rectangle { x: root.imageBounds.x; y: root.imageBounds.y; width: root.imageBounds.width; height: Math.max(0, root.selection.y - y); color: "#99000000" }
    Rectangle { x: root.imageBounds.x; y: root.selection.y + root.selection.height; width: root.imageBounds.width; height: Math.max(0, root.imageBounds.y + root.imageBounds.height - y); color: "#99000000" }
    Rectangle { x: root.imageBounds.x; y: root.selection.y; width: Math.max(0, root.selection.x - x); height: root.selection.height; color: "#99000000" }
    Rectangle { x: root.selection.x + root.selection.width; y: root.selection.y; width: Math.max(0, root.imageBounds.x + root.imageBounds.width - x); height: root.selection.height; color: "#99000000" }
    Rectangle {
        id: selected
        objectName: "cropSelection"
        x: root.selection.x; y: root.selection.y; width: root.selection.width; height: root.selection.height
        color: "transparent"
        border.color: root.locked ? "#a9b4c1" : "#93c5aa"
        border.width: 2
        Repeater {
            model: [1/3, 2/3]
            Rectangle { required property real modelData; x: selected.width * modelData; width: 1; height: selected.height; color: "#88ffffff" }
        }
        Repeater {
            model: [1/3, 2/3]
            Rectangle { required property real modelData; y: selected.height * modelData; height: 1; width: selected.width; color: "#88ffffff" }
        }
        MouseArea {
            objectName: "cropMoveSelection"
            anchors.fill: parent
            enabled: root.hasFrame && !root.locked
            preventStealing: true
            cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
            property point startPointer
            property rect startRect
            onPressed: function(mouse) { startPointer = mapToItem(root, mouse.x, mouse.y); startRect = root.selection }
            onPositionChanged: function(mouse) {
                if (!pressed) return
                var p = mapToItem(root, mouse.x, mouse.y)
                root.chooseRect(startRect.x + p.x - startPointer.x, startRect.y + p.y - startPointer.y, startRect.width)
            }
        }
    }
    Repeater {
        model: [{name:"nw",x:-1,y:-1},{name:"n",x:0,y:-1},{name:"ne",x:1,y:-1},{name:"e",x:1,y:0},
            {name:"se",x:1,y:1},{name:"s",x:0,y:1},{name:"sw",x:-1,y:1},{name:"w",x:-1,y:0}]
        Rectangle {
            required property var modelData
            x: root.selection.x + (modelData.x + 1) * root.selection.width / 2 - width / 2
            y: root.selection.y + (modelData.y + 1) * root.selection.height / 2 - height / 2
            width: 12; height: 12; radius: 2
            color: "#e9ecef"; border.color: "#284c44"
            visible: root.hasFrame && !root.locked
            MouseArea {
                objectName: "cropHandle-" + parent.modelData.name
                anchors.fill: parent; anchors.margins: -6
                preventStealing: true
                cursorShape: parent.modelData.x === 0 ? Qt.SizeVerCursor : parent.modelData.y === 0 ? Qt.SizeHorCursor
                    : parent.modelData.x === parent.modelData.y ? Qt.SizeFDiagCursor : Qt.SizeBDiagCursor
                property point startPointer
                property rect startRect
                onPressed: function(mouse) { startPointer = mapToItem(root, mouse.x, mouse.y); startRect = root.selection }
                onPositionChanged: function(mouse) {
                    if (!pressed) return
                    var p = mapToItem(root, mouse.x, mouse.y)
                    root.resizeSelection(startRect, parent.modelData.x, parent.modelData.y, p.x - startPointer.x, p.y - startPointer.y)
                }
            }
        }
    }
    Label {
        objectName: "cropLoadingHint"
        anchors.centerIn: parent
        visible: !root.hasFrame
        text: photo.status === Image.Error ? qsTr("Cannot load this image") : root.loadingText
        color: "#e9ecef"
    }
}
