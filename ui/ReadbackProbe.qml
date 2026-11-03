import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Io

Rectangle {
    id:root
    property string backend:"pipewire"
    property bool active:false
    property string pluginRoot:Qt.resolvedUrl("../").toString().replace(/^file:\/\//,"").replace(/\/$/,"")
    property string frame:""
    property var measurement:({})
    property string message:qsTr("Start camera output to test this consumer.")
    property bool stopping:false
    implicitHeight:content.implicitHeight+24
    color:"#222b35";radius:8
    onActiveChanged:{
        frame="";measurement=({});stopping=!active
        if(active)retry()
        else{consumer.running=false;message=qsTr("Start camera output to test this consumer.")}
    }
    Component.onDestruction:{stopping=true;consumer.running=false}
    function retry(){if(!active||consumer.running)return;frame="";measurement=({});message=qsTr("Connecting an independent camera consumer…");consumer.command=[pluginRoot+"/bin/preview-python",pluginRoot+"/bin/readback-camera.py","--backend",backend];consumer.running=true}
    ColumnLayout {
        id:content
        x:12;y:12;width:root.width-24;spacing:8
        Text {text:root.backend==="pipewire"?qsTr("PipeWire output · independent readback"):qsTr("V4L2 adapter output · independent readback");textFormat:Text.PlainText;color:"#e9ecef";font.bold:true;wrapMode:Text.WordWrap;Layout.fillWidth:true}
        Rectangle {
            Layout.fillWidth:true;Layout.preferredHeight:Math.min(240,width*9/16);color:"#080b10";clip:true
            Image {anchors.fill:parent;source:root.frame;fillMode:Image.PreserveAspectFit;cache:false;asynchronous:true;retainWhileLoading:true}
            Text {anchors.centerIn:parent;width:parent.width-24;text:root.message;visible:root.frame==="";color:"#b8c2cd";textFormat:Text.PlainText;wrapMode:Text.WordWrap;horizontalAlignment:Text.AlignHCenter}
        }
        Text {objectName:"consumerMeasurement";text:root.frame!==""&&root.measurement.receivedFrames?qsTr("Received %1 frames · %2 × %3 · %4 FPS · node %5").arg(root.measurement.receivedFrames).arg(root.measurement.width).arg(root.measurement.height).arg(Number(root.measurement.receiveFps||0).toFixed(1)).arg(root.measurement.nodeId):root.message;textFormat:Text.PlainText;color:"#93c5aa";wrapMode:Text.WordWrap;Layout.fillWidth:true}
        Button {text:qsTr("Retry consumer");visible:root.active&&root.frame==="";enabled:!consumer.running;onClicked:root.retry()}
    }
    Process {
        id:consumer
        stdout:SplitParser {onRead:function(line){
            if(line.length>1048576){root.message=qsTr("Consumer response exceeded its size limit");root.frame="";consumer.running=false;return}
            try{var value=JSON.parse(line);if(value.error){root.frame="";root.message=value.error}else if(value.frame){root.measurement=value;root.frame="data:image/jpeg;base64,"+value.frame;root.message=qsTr("Receiving published camera pixels")}}
            catch(e){root.message=qsTr("Could not read the camera consumer response");root.frame=""}
        }}
        stderr:StdioCollector {id:errors;waitForEnd:true}
        onExited:function(code){if(root.active&&!root.stopping){root.frame="";if(code!==0&&errors.text)root.message=String(errors.text).slice(-600)}}
    }
}
