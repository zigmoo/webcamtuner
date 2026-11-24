import QtQuick

// Render the original vector glyphs as images so clipped GridView rows stay clipped.
Image {
    id: root
    width: 24; height: 24
    property string kind: "crop"
    property color ink: "#e9ecef"
    readonly property string vectorPath: root.kind === "trash" ? "M4 7H20 M9 7V4H15V7 M6 7L7 21H17L18 7 M10 11V17 M14 11V17"
                : root.kind === "copy" ? "M8 8H21V21H8Z M16 5V3H3V16H5"
                : root.kind === "path" ? "M3 7H10L12 9H21V20H3Z M7 15H17"
                : root.kind === "open" ? "M14 3H21V10 M21 3L10 14 M10 5H4V20H19V14"
                : root.kind === "link" ? "M10 8L14 4A4 4 0 0 1 20 10L16 14 M14 16L10 20A4 4 0 0 1 4 14L8 10 M9 15L15 9"
                : root.kind === "info" ? "M16 10A6 6 0 1 1 4 10A6 6 0 1 1 16 10 M15 15L21 21 M10 9.5V13 M10 7V7.1"
                : root.kind === "preview" ? "M2 11Q12 2 22 11Q12 20 2 11Z M15 11A3 3 0 1 1 9 11A3 3 0 1 1 15 11"
                : root.kind === "locked" ? "M7 10V7A5 5 0 0 1 17 7V10 M6 10H18V21H6Z M12 14V17"
                : root.kind === "unlocked" ? "M8 10V7A5 5 0 0 1 18 7 M6 10H18V21H6Z M12 14V17"
                : "M7 3V17H21 M3 7H17V21"
    sourceSize: Qt.size(24, 24)
    fillMode: Image.PreserveAspectFit
    source: "data:image/svg+xml;utf8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="' + vectorPath + '" fill="none" stroke="' + ink + '" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>')
}
