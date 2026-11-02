import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

RowLayout {
    id: root
    property var overlay: ({enabled:false,opacity:.75,text:""})
    property bool available: false
    property string feedback: ""
    signal changed(var patch)
    signal editRequested()
    CheckBox {
        objectName:"showPreviewLabel"
        text:qsTr("Show label")
        checked:root.available && !!root.overlay.enabled
        nextCheckState:function(){return checkState}
        enabled:root.available
        onClicked:root.changed({enabled:!checked})
    }
    Button { text:qsTr("Edit label"); visible:root.available && !!root.overlay.enabled; onClicked:root.editRequested() }
    Button {
        objectName:"labelFormatButton"
        text:qsTr("Format…")
        visible:root.available && !!root.overlay.enabled
        onClicked:formatPopup.open()
        Popup {
            id:formatPopup
            objectName:"labelFormatPopup"
            width:Math.min(340,Overlay.overlay?Overlay.overlay.width-32:340)
            padding:14
            contentItem:ColumnLayout {
                spacing:8
                Label { text:qsTr("Label format"); font.bold:true }
                ComboBox {
                    objectName:"labelFontFamily"
                    Layout.fillWidth:true
                    model:Qt.fontFamilies()
                    currentIndex:Math.max(0,model.indexOf(root.overlay.fontFamily||"Sans"))
                    onActivated:function(index){root.changed({fontFamily:model[index]})}
                    Accessible.name:qsTr("Label font")
                }
                RowLayout {
                    CheckBox { objectName:"labelBold";text:qsTr("Bold");checked:!!root.overlay.bold;nextCheckState:function(){return checkState};onClicked:root.changed({bold:!checked}) }
                    CheckBox { objectName:"labelItalic";text:qsTr("Italic");checked:!!root.overlay.italic;nextCheckState:function(){return checkState};onClicked:root.changed({italic:!checked}) }
                    CheckBox { objectName:"labelAllCaps";text:qsTr("ALL CAPS");checked:!!root.overlay.allCaps;nextCheckState:function(){return checkState};onClicked:root.changed({allCaps:!checked}) }
                }
                Label { text:qsTr("Text size · %1%").arg(Math.round((root.overlay.fontSize||.034)*100)) }
                Slider { objectName:"labelFontSize";Layout.fillWidth:true;from:.012;to:.15;value:root.overlay.fontSize||.034;onMoved:root.changed({fontSize:value}) }
                Label { text:qsTr("Opacity · %1%").arg(Math.round((root.overlay.opacity===undefined?.75:root.overlay.opacity)*100)) }
                Slider { objectName:"labelOpacity";Layout.fillWidth:true;from:0;to:1;value:root.overlay.opacity===undefined?.75:root.overlay.opacity;onMoved:root.changed({opacity:value}) }
                Label { text:qsTr("Drag the label on the preview to position it. Double-click it to edit its text.");textFormat:Text.PlainText;wrapMode:Text.WordWrap;Layout.fillWidth:true }
            }
        }
    }
    Item { Layout.fillWidth:true }
    Label { text:root.feedback;textFormat:Text.PlainText;elide:Text.ElideRight;Layout.maximumWidth:150 }
}
