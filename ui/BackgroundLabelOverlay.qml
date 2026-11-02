import QtQuick

Item {
    id: root
    property var overlay: ({enabled: false, opacity: 0.75, text: ""})
    visible: !!overlay.enabled && !!overlay.text
    opacity: overlay.opacity === undefined ? 0.75 : overlay.opacity
    Text {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: Math.max(4, Math.round(parent.height * 0.02))
        width: Math.max(0, parent.width - 2 * anchors.margins)
        text: root.overlay.text || ""
        textFormat: Text.PlainText
        color: "white"
        style: Text.Outline
        styleColor: "#cc000000"
        font.pixelSize: Math.max(10, Math.round(parent.height * 0.034))
        wrapMode: Text.Wrap
        maximumLineCount: 2
        elide: Text.ElideRight
    }
}
