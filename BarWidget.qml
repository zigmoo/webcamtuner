import QtQuick
import qs.Ui
import "ui" as Tuner
import "BarServiceBridge.js" as BarServiceBridge

BarWidget {
    id: root
    moduleName: "moo.webcamtuner"
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    property var bridgeController: null
    property var unsubscribeBridge: null
    readonly property var controller: {
        var api = bar ? bar.shell : null
        var direct = api && typeof api.serviceFor === "function" ? api.serviceFor(moduleName) : null
        return direct || bridgeController
    }
    readonly property bool opened: controller ? controller.opened : false
    property bool popoutSwitchClosing: false
    function open() { if (controller) controller.open() }
    function close() { if (controller) controller.close() }
    function toggle() { if (controller) controller.toggle() }
    function closeForPopoutSwitch() { close() }
    Component.onCompleted: unsubscribeBridge = BarServiceBridge.subscribe(function(api) {
        root.bridgeController = api
    })
    Component.onDestruction: if (unsubscribeBridge) unsubscribeBridge()
    BarIconButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        iconComponent: Component { Tuner.WebcamIcon { ink: button.active && button.useActiveColor ? button.activeColor : button.foreground } }
        tooltipText: root.controller ? qsTr("Custom post-camera composite feed with person mask, background, label & crops") : qsTr("WebcamTuner · service unavailable")
        onPressed: root.toggle()
    }
}
