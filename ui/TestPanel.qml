import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ScrollView {
    id:root
    objectName:"outputTestPanel"
    property var outputControl:null
    property bool panelOpen:false
    readonly property bool receiving:enabled&&panelOpen&&visible&&outputControl!==null&&outputControl.published
    function consumerStatus(){
        function status(item){return {backend:item.backend,active:item.active,state:item.connectionState,connected:item.connected,pid:item.consumerPid||0,nodeSerial:item.measurement.nodeSerial||item.targetSerial,receivedFrames:item.measurement.receivedFrames||0,receiveFps:item.measurement.receiveFps||0,message:item.message}}
        return {published:!!(outputControl&&outputControl.published),pipewire:status(pipewireProbe),v4l2:status(v4l2Probe)}
    }
    clip:true;padding:22
    rightPadding:38
    contentWidth:availableWidth
    contentHeight:content.implicitHeight
    ScrollBar.vertical:VisibleScrollBar {
        objectName:"testScrollbar"
        parent:root
        x:root.width-width
        y:0
        width:12
        height:root.height
        policy:root.contentHeight>root.availableHeight?ScrollBar.AlwaysOn:ScrollBar.AlwaysOff
    }
    ColumnLayout {
        id:content;width:root.availableWidth;height:implicitHeight;spacing:14
        component Plain:Text {color:"#e9ecef";textFormat:Text.PlainText;wrapMode:Text.WordWrap;Layout.fillWidth:true;font.pixelSize:14}
        Plain {text:qsTr("Test the outputs");font.pixelSize:22;font.bold:true}
        Plain {text:qsTr("These previews read the published camera through two real consumer paths. They include the background, camera crop and label baked into the video; they do not reuse the Camera tab’s preview.")}
        RowLayout {
            Button {text:qsTr("Start camera output");enabled:root.outputControl!==null&&root.outputControl.readyToStart&&!root.outputControl.busy&&!root.outputControl.published;onClicked:root.outputControl.start()}
            Button {text:qsTr("Stop output");enabled:root.outputControl!==null;onClicked:root.outputControl.stop()}
        }
        Plain {text:root.outputControl?root.outputControl.feedback:"";color:"#93c5aa";visible:text!==""}
        GridLayout {
            Layout.fillWidth:true
            columns:root.availableWidth>=760?2:1
            columnSpacing:12;rowSpacing:12
            ReadbackProbe {id:pipewireProbe;objectName:"pipewireReadback";Layout.fillWidth:true;Layout.preferredWidth:1;Layout.alignment:Qt.AlignTop;backend:"pipewire";active:root.receiving;targetSerial:root.outputControl?String(root.outputControl.state.nodeSerial||""):""}
            ReadbackProbe {id:v4l2Probe;objectName:"v4l2Readback";Layout.fillWidth:true;Layout.preferredWidth:1;Layout.alignment:Qt.AlignTop;backend:"v4l2";active:root.receiving&&root.outputControl.adapter.ready;targetSerial:root.outputControl?String(root.outputControl.state.nodeSerial||""):"";inactiveMessage:root.outputControl&&!root.outputControl.adapter.ready?qsTr("Enable the Zoom camera adapter in Setup to connect this consumer."):qsTr("Start camera output to test this consumer.")}
        }
        Plain {text:root.outputControl&&root.outputControl.adapter.ready?qsTr("Zoom adapter is available in your home directory."):qsTr("Enable the Zoom camera adapter in Setup to test the V4L2 path.");color:"#a9b4c1"}
        Plain {objectName:"appAcceptance";text:qsTr("App acceptance");font.pixelSize:18;font.bold:true}
        Plain {text:root.outputControl&&root.outputControl.adapter.adapterLoaded?qsTr("Native Zoom is running with the camera adapter loaded. Select WebcamTuner in Zoom and verify that the same composite appears there."):qsTr("Native Zoom is not connected through the adapter yet. After enabling it in Setup, quit and reopen native Zoom, then select WebcamTuner.")}
        Plain {text:qsTr("Zoom web uses the browser’s PipeWire camera support. Select WebcamTuner in its camera menu; the native Zoom adapter status above does not describe browser calls.");color:"#a9b4c1"}
        Plain {text:qsTr("A passing readback proves that this output can deliver pixels to that consumer path. It does not prove that Zoom, Teams or Meet rendered them. Actual app checks remain separate acceptance results.");color:"#a9b4c1"}
    }
}
