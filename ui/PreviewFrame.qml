import QtQuick

// Decoding the next frame must not remove the last frame from the scene graph.
Image {
    cache: false
    asynchronous: true
    retainWhileLoading: true
    fillMode: Image.PreserveAspectFit
}
