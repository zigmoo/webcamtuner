import QtQuick

// Render the original vector glyphs as images so clipped GridView rows stay clipped.
Image {
    id: root
    width: 24; height: 24
    property string kind: "crop"
    property color ink: "#e9ecef"
    readonly property string vectorPath: root.kind === "trash" ? "M4 7H20 M9 7V4H15V7 M6 7L7 21H17L18 7 M10 11V17 M14 11V17"
                : root.kind === "locked" ? "M7 10V7A5 5 0 0 1 17 7V10 M6 10H18V21H6Z M12 14V17"
                : root.kind === "unlocked" ? "M8 10V7A5 5 0 0 1 18 7 M6 10H18V21H6Z M12 14V17"
                : "M7 3V17H21 M3 7H17V21"
    sourceSize: Qt.size(24, 24)
    fillMode: Image.PreserveAspectFit
    source: "data:image/svg+xml;utf8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="' + vectorPath + '" fill="none" stroke="' + ink + '" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>')
}
