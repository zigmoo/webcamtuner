import QtQuick

Item {
    id: root
    property var overlay: ({enabled: false, opacity: 0.75, text: ""})
    visible: !!overlay.enabled && !!overlay.text
    opacity: overlay.opacity === undefined ? 0.75 : overlay.opacity
    Text {
        x:Math.max(0,parent.width-width)*(root.overlay.x===undefined?.02:root.overlay.x)
        y:Math.max(0,parent.height-height)*(root.overlay.y===undefined?.96:root.overlay.y)
        width:Math.min(implicitWidth,parent.width)
        text: root.overlay.allCaps ? (root.overlay.text||"").toUpperCase() : root.overlay.text || ""
        textFormat: Text.PlainText
        color: "white"
        style: Text.Outline
        styleColor: "#cc000000"
        font.pixelSize: Math.max(10, Math.round(parent.height * (root.overlay.fontSize||.034)))
        font.family:root.overlay.fontFamily||"Sans"
        font.bold:!!root.overlay.bold
        font.italic:!!root.overlay.italic
        wrapMode: Text.Wrap
        maximumLineCount: 2
        elide: Text.ElideRight
    }
}
