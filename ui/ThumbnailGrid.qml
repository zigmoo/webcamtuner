import QtQuick
import QtQuick.Controls

GridView {
    id: grid
    property var items: []
    property real pendingScrollOffset: -1
    signal modelScrollRestored()

    clip: true
    cellWidth: width / Math.max(1, Math.floor(width / 150))
    cellHeight: 132
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: VisibleScrollBar {
        policy: grid.contentHeight > grid.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
    }

    onItemsChanged: {
        // Replacing the array model resets GridView's viewport.
        if (pendingScrollOffset < 0) {
            cancelFlick()
            pendingScrollOffset = Math.max(0, contentY - originY)
        }
        model = items
        Qt.callLater(restoreModelScroll)
    }

    function restoreModelScroll() {
        forceLayout()
        const maximumOffset = Math.max(0, contentHeight - height)
        contentY = originY + Math.min(pendingScrollOffset, maximumOffset)
        pendingScrollOffset = -1
        modelScrollRestored()
    }
}
