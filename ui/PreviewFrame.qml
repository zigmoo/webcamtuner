import QtQuick

// Decoding the next frame must not remove the last frame from the scene graph.
Image {
    signal frameDecoded()
    onStatusChanged: if (status === Image.Ready && source.toString() !== "") frameDecoded()
    cache: false
    asynchronous: true
    retainWhileLoading: true
    fillMode: Image.PreserveAspectFit
}
