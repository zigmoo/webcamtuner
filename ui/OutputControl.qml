import QtQuick
import Quickshell.Io

Item {
    id: root
    property var configuration: null
    property int configurationRevision: 0
    property bool panelOpen: false
    property bool enabled: true
    property bool checked: false
    property var state: ({published:false, processed:false})
    readonly property bool published: !!state.published && !!state.processed
    readonly property bool busy: (activeAction !== "" && activeAction !== "status" && activeAction !== "zoom-status") || pending.some(function(item){return item.action!=="status"&&item.action!=="zoom-status"}) || startDelay.running || stopping
    property string feedback: ""
    property string activeAction: ""
    property bool stopping: false
    property var pending: []
    property var adapter: ({ready:false,enabled:false,restartRequired:false})
    property string pluginRoot: Qt.resolvedUrl("../").toString().replace(/^file:\/\//, "").replace(/\/$/, "")
    signal starting()
    signal started()
    signal stopped()
    signal failed(string message)

    onConfigurationChanged: { configurationRevision++; if (enabled && published && configuration) updateDelay.restart() }
    onPanelOpenChanged: if (panelOpen&&enabled) { request("status"); request("zoom-status") }
    Component.onCompleted: Qt.callLater(function(){if(root.enabled){root.request("status");root.request("zoom-status")}})
    onPublishedChanged: { if (!published) stopped(); else if(enabled&&configuration)updateDelay.restart() }
    function request(action, args) {
        if(!enabled)return
        if (action === "status" && (activeAction !== "" || pending.length)) return
        if (pending.length >= 8) { feedback=qsTr("Please wait for the current output action."); return }
        pending=pending.concat([{action:action,args:args||[]}]);pump()
    }
    function pump() {
        if (activeAction!=="" || !pending.length)return
        var next=pending[0];pending=pending.slice(1);activeAction=next.action
        operation.command=["python3",pluginRoot+"/bin/output-control.py",next.action].concat(next.args)
        operation.running=true
    }
    function start() {
        if(!enabled || busy || !configuration || !configuration.camera)return
        starting();feedback=qsTr("Starting your composed camera output…");startDelay.restart()
    }
    function stop() {
        if(!enabled)return
        stopped();feedback=qsTr("Stopping camera output…");startDelay.stop()
        pending=pending.filter(function(item){return item.action!=="start-output"})
        stopping=true
        if(activeAction==="start-output")operation.running=false
        stopDelay.restart()
    }
    Timer { id:stopDelay;interval:200;onTriggered:stopProcess.running=true }
    Process {
        id:stopProcess
        command:["python3",root.pluginRoot+"/bin/output-control.py","stop-output"]
        stdout:StdioCollector {id:stopResult;waitForEnd:true}
        onExited:function(code){
            root.stopping=false
            try{var value=JSON.parse(stopResult.text);if(code!==0)throw new Error(value.message||"Output did not stop");root.state=value;root.feedback=value.message}
            catch(e){root.feedback=String(e.message||e);root.failed(root.feedback)}
        }
    }
    Timer { id:startDelay;interval:500;onTriggered:root.request("start-output",["--request",JSON.stringify(Object.assign({},root.configuration,{configurationRevision:root.configurationRevision}))]) }
    Timer { interval:3000;repeat:true;running:root.enabled&&root.panelOpen;onTriggered:{if(!root.busy){root.request("status");root.request("zoom-status")}} }
    Timer { id:updateDelay;interval:180;onTriggered:root.configure() }
    function configure() {
        if(!enabled || !published || !configuration)return
        if(update.running){updateDelay.restart();return}
        update.command=["python3",pluginRoot+"/bin/stream-client.py","--configure",JSON.stringify(Object.assign({},configuration,{configurationRevision:configurationRevision}))]
        update.running=true
    }
    Process {
        id:update
        stdout:StdioCollector {id:updateResult;waitForEnd:true}
        onExited:function(code){
            if(code!==0){try{root.feedback=JSON.parse(updateResult.text).error||qsTr("Output settings could not be applied")}catch(e){root.feedback=qsTr("Output settings could not be applied")}}
        }
    }
    Process {
        id:operation
        stdout:StdioCollector {id:result;waitForEnd:true}
        stderr:StdioCollector {id:errors;waitForEnd:true}
        onExited:function(code){
            var action=root.activeAction
            try{
                var value=JSON.parse(result.text)
                if(code!==0)throw new Error(value.message||value.error||errors.text||qsTr("Output action failed"))
                if(action==="setup-zoom"||action==="disable-zoom"||action==="zoom-status")root.adapter=value
                else {root.state=value;root.checked=true}
                if(value.message)root.feedback=value.message
                if(action==="start-output"&&!root.stopping) {root.configure();Qt.callLater(root.started)}
            }catch(e){if(!root.stopping){root.feedback=String(e.message||e).slice(0,1200);if(action==="status")root.checked=true;else root.failed(root.feedback)}}
            Qt.callLater(function(){root.activeAction="";root.pump()})
        }
    }
}
