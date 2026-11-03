import QtQuick
import Quickshell.Io

Item {
    id: root
    property bool enabled: true
    property bool checked: false
    property var state: ({ready:false,controllerReady:false,checks:[]})
    readonly property bool ready: checked && !!state.ready
    readonly property bool busy: operation.running
    property string message: qsTr("Checking WebcamTuner…")
    property string error: ""
    property string action: "status"
    property var result: null
    property string pluginRoot: Qt.resolvedUrl("../").toString().replace(/^file:\/\//, "").replace(/\/$/, "")
    signal preparing()
    signal refreshed()
    Component.onCompleted: Qt.callLater(function(){root.check()})
    function check(){run("status")}
    function run(action){
        if(!enabled || busy)return
        root.action=action;result=null;error=""
        if(action!=="status")preparing()
        message=action==="status"?qsTr("Checking WebcamTuner…"):qsTr("Preparing WebcamTuner in your home directory…")
        operation.command=["python3",pluginRoot+"/bin/first-run.py",action]
        operation.running=true
    }
    Process {
        id:operation
        stdout:SplitParser {onRead:function(line){
            if(line.length>16384)return
            try{
                var value=JSON.parse(line)
                if(value.progress)root.message=value.progress
                if(value.checks)root.result=value
                if(value.error)root.error=value.error
            }catch(e){} // Tool download/build progress is ordinary text.
        }}
        stderr:StdioCollector {id:errors;waitForEnd:true}
        onExited:function(code){
            if(code===0&&root.result){root.state=root.result;root.checked=true;root.message=root.state.message;root.error=""}
            else {root.checked=true;root.error=root.error||String(errors.text||qsTr("Setup could not finish. Retry Check readiness.")).slice(-1200)}
            Qt.callLater(root.refreshed)
        }
    }
}
