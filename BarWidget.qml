import QtQuick
import qs.Ui
import "ui" as Tuner

BarWidget {
    id: root
    moduleName: "moo.webcamtuner"
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    readonly property var controller: bar && bar.shell ? bar.shell.serviceFor(moduleName) : null
    readonly property bool opened: controller ? controller.opened : false
    property bool popoutSwitchClosing: false
    function open() { if (controller) controller.open() }
    function close() { if (controller) controller.close() }
    function toggle() { if (controller) controller.toggle() }
    function closeForPopoutSwitch() { close() }
    BarIconButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        iconComponent: Component { Tuner.WebcamIcon { ink: button.active && button.useActiveColor ? button.activeColor : button.foreground } }
        tooltipText: "WebcamTuner · framing and backgrounds"
        onPressed: root.toggle()
    }
}
