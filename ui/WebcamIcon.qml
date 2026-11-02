import QtQuick
import QtQuick.Shapes

// Original WebcamTuner mark: framing corners and two tuning controls.
Shape {
    id: root
    implicitWidth: 24
    implicitHeight: 24
    width: 24
    height: 24
    fillMode: Shape.PreserveAspectFit
    property color ink: "#93c5aa"
    ShapePath {
        strokeColor: root.ink
        strokeWidth: 1.8
        capStyle: ShapePath.RoundCap
        joinStyle: ShapePath.RoundJoin
        fillColor: "transparent"
        PathSvg { path: "M8 3 H3 V8 M16 3 H21 V8 M21 16 V21 H16 M8 21 H3 V16 M7 9 H17 M7 15 H17" }
    }
    ShapePath {
        strokeWidth: 0
        fillColor: root.ink
        PathSvg { path: "M11.8 9 A1.8 1.8 0 1 0 8.2 9 A1.8 1.8 0 1 0 11.8 9 M15.8 15 A1.8 1.8 0 1 0 12.2 15 A1.8 1.8 0 1 0 15.8 15" }
    }
}
