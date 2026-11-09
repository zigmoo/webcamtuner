import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Io

Rectangle {
    id:root
    property string backend:"pipewire"
    property bool active:false
    property string targetSerial:""
    property string inactiveMessage:qsTr("Start camera output to test this consumer.")
    property string pluginRoot:Qt.resolvedUrl("../").toString().replace(/^file:\/\//,"").replace(/\/$/,"")
    property string frame:""
    property var measurement:({})
    property string message:qsTr("Start camera output to test this consumer.")
    property bool stopping:false
    property bool initialized:false
    property int attempts:0
    property bool reconnectRequested:false
    property real lastFrameAt:0
    property real connectionBeganAt:0
    property string connectionState:"disconnected"
    readonly property bool connected:active&&!stopping&&consumer.running&&frame!==""&&lastFrameAt>0&&connectionState==="connected"
    readonly property var consumerPid:consumer.processId
    implicitHeight:content.implicitHeight+24
    color:"#222b35";radius:8
    onActiveChanged:resetConnection()
    onTargetSerialChanged:resetConnection()
    onInactiveMessageChanged:if(!active)message=inactiveMessage
    Component.onCompleted:{initialized=true;Qt.callLater(root.resetConnection)}
    Component.onDestruction:{stopping=true;if(consumer.running)consumer.signal(9)}
    function stopConsumer(){
        if(!consumer.running)return
        stopping=true;consumer.signal(15);stopDeadline.restart()
    }
    function resetConnection(){
        if(!initialized)return
        reconnect.stop();attempts=0;frame="";measurement=({});lastFrameAt=0
        reconnectRequested=active
        connectionState=active?"connecting":"disconnected"
        message=active?qsTr("Connecting an independent camera consumer…"):inactiveMessage
        if(consumer.running)stopConsumer()
        else if(active)reconnect.start()
    }
    function retry(){
        if(!active||consumer.running)return
        attempts=0;reconnectRequested=true;reconnect.restart()
    }
    Timer {id:stopDeadline;interval:1000;onTriggered:if(consumer.running&&root.stopping)consumer.signal(9)}
    Timer {
        id:reconnect;interval:250
        onTriggered:{
            if(!root.active||consumer.running)return
            root.stopping=false;root.reconnectRequested=false;root.attempts++
            root.connectionBeganAt=Date.now()
            root.connectionState="connecting";root.message=qsTr("Connecting an independent camera consumer…")
            consumer.command=[root.pluginRoot+"/bin/preview-python",root.pluginRoot+"/bin/readback-camera.py","--backend",root.backend]
            if(root.targetSerial!=="")consumer.command=consumer.command.concat(["--node-serial",root.targetSerial])
            consumer.running=true
        }
    }
    Timer {
        interval:500;repeat:true;running:root.active&&consumer.running&&!root.stopping
        onTriggered:{
            if(Date.now()-(root.lastFrameAt||root.connectionBeganAt)>(root.lastFrameAt>0?5000:8000)){
                root.frame="";root.connectionState="reconnecting";root.message=qsTr("Consumer stopped receiving frames. Reconnecting…")
                root.reconnectRequested=root.attempts<3;root.stopConsumer()
            }
        }
    }
    ColumnLayout {
        id:content
        x:12;y:12;width:root.width-24;spacing:8
        Text {text:root.backend==="pipewire"?qsTr("PipeWire output · independent readback"):qsTr("V4L2 adapter output · independent readback");textFormat:Text.PlainText;color:"#e9ecef";font.bold:true;wrapMode:Text.WordWrap;Layout.fillWidth:true}
        Text {objectName:"consumerConnection";text:root.connected?qsTr("Connected · consumer %1 · source %2").arg(root.consumerPid).arg(root.measurement.nodeSerial||root.targetSerial):root.connectionState==="connecting"?qsTr("Connecting…"):root.connectionState==="reconnecting"?qsTr("Reconnecting…"):qsTr("Disconnected");textFormat:Text.PlainText;color:root.connected?"#93c5aa":"#edb17a";wrapMode:Text.WordWrap;Layout.fillWidth:true}
        Rectangle {
            Layout.fillWidth:true;Layout.preferredHeight:Math.min(240,width*9/16);color:"#080b10";clip:true
            Image {objectName:"consumerFrame";anchors.fill:parent;source:root.frame;fillMode:Image.PreserveAspectFit;cache:false;asynchronous:true;retainWhileLoading:true}
            Text {anchors.centerIn:parent;width:parent.width-24;text:root.message;visible:root.frame==="";color:"#b8c2cd";textFormat:Text.PlainText;wrapMode:Text.WordWrap;horizontalAlignment:Text.AlignHCenter}
        }
        Text {objectName:"consumerMeasurement";text:root.frame!==""&&root.measurement.receivedFrames?qsTr("Received %1 frames · %2 × %3 · %4 FPS · node %5").arg(root.measurement.receivedFrames).arg(root.measurement.width).arg(root.measurement.height).arg(Number(root.measurement.receiveFps||0).toFixed(1)).arg(root.measurement.nodeId):root.message;textFormat:Text.PlainText;color:"#93c5aa";wrapMode:Text.WordWrap;Layout.fillWidth:true}
        Button {objectName:"retryConsumer";text:qsTr("Retry consumer");visible:root.active&&root.frame==="";enabled:!consumer.running&&!reconnect.running;onClicked:root.retry()}
    }
    Process {
        id:consumer
        stdout:SplitParser {onRead:function(line){
            if(root.stopping||!root.active)return
            if(line.length>1048576){root.message=qsTr("Consumer response exceeded its size limit");root.frame="";root.stopConsumer();return}
            try{var value=JSON.parse(line);if(value.error){root.frame="";root.message=value.error;root.connectionState="disconnected"}else if(value.frame){root.measurement=value;root.frame="data:image/jpeg;base64,"+value.frame;root.lastFrameAt=Date.now();root.connectionState="connected";root.attempts=0;root.message=qsTr("Receiving published camera pixels")}}
            catch(e){root.message=qsTr("Could not read the camera consumer response");root.frame=""}
        }}
        stderr:StdioCollector {id:errors;waitForEnd:true}
        onExited:function(code){
            stopDeadline.stop();root.frame="";root.lastFrameAt=0
            var expected=root.stopping;root.stopping=false
            if(!root.active){root.connectionState="disconnected";root.message=root.inactiveMessage;return}
            if(!expected&&code!==0&&errors.text)root.message=String(errors.text).slice(-600)
            root.connectionState="disconnected"
            if(root.reconnectRequested||root.attempts<3){root.connectionState="reconnecting";Qt.callLater(function(){if(root.active)reconnect.restart()})}
        }
    }
}
