"""Exercise hover controls and OS Trash through the real snapshot gallery."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from PIL import Image


root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=os.environ['WEBCAMTUNER_TEST_ROOT']) as temporary:
    scratch = Path(temporary)
    data = scratch / 'data'
    snapshots = data / 'webcamtuner/snapshots'
    snapshots.mkdir(parents=True)
    removed = snapshots / 'WebcamTuner-6.jpg'
    last = snapshots / 'WebcamTuner-1.jpg'
    retained = snapshots / 'WebcamTuner-2.jpg'
    mirror = scratch / 'WebcamTuner-6.png'
    for index in range(1, 9):
        Image.new('RGB', (640, 360), (32 * index - 1, 80, 90)).save(snapshots / f'WebcamTuner-{index}.jpg')
    with Image.open(removed) as image:
        image.save(mirror)
    original = removed.read_bytes()
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
               XDG_DATA_HOME=str(data), XDG_CACHE_HOME=str(scratch / 'cache'),
               WEBCAMTUNER_SNAPSHOT_ROOT=str(snapshots))
    helper = ['python3', str(root / 'bin/snapshot-gallery.py'), 'trash']
    symlink = snapshots / 'WebcamTuner-link.jpg'
    symlink.symlink_to(retained)
    for invalid in (symlink.name, '../' + retained.name):
        assert subprocess.run([*helper, invalid], env=env, capture_output=True).returncode != 0
    assert symlink.is_symlink() and retained.is_file()

    harness = scratch / 'shell.qml'
    harness.write_text('''import QtQuick
import QtTest
import Quickshell
import UI_PATH as Tuner

ShellRoot {
    Window {
        width: 380
        height: 340
        visible: true

        Tuner.SnapshotGallery {
            id: gallery
            anchors.fill: parent
            anchors.margins: 12
            revelator: true
        }

        TestCase {
            id: test
            name: "SnapshotGallery"
            when: false

            function exercise() {
                tryVerify(() => gallery.snapshots.length === 8)
                const grid = findChild(gallery, "snapshotGrid")
                tryCompare(grid, "pendingScrollOffset", -1)
                const rowOffset = grid.cellHeight
                grid.contentY = grid.originY + rowOffset
                tryVerify(() => grid.itemAtIndex(2) && grid.itemAtIndex(3))
                const card = grid.itemAtIndex(2)
                const otherCard = grid.itemAtIndex(3)
                compare(card.children.length, 1)
                compare(otherCard.children.length, 1)
                const image = card.children[0]
                compare(card.height - image.y - image.height, 6)
                const actions = image.children[0]
                const otherActions = otherCard.children[0].children[0]
                const trash = findChild(actions, "trash-WebcamTuner-6.jpg")

                verify(!actions.visible && !otherActions.visible)
                compare(actions.spacing, 1)
                compare(actions.y, 2)
                compare(image.width - actions.x - actions.width, 2)
                compare(actions.width, 4 * 20 + 3)
                compare(trash.width, 20)
                compare(trash.contentItem.width, 14)

                mouseMove(image, 8, 32)
                tryCompare(actions, "visible", true)
                verify(!otherActions.visible)
                fuzzyCompare(trash.background.color.a, 208 / 255, 0.01)
                mouseMove(trash, 10, 10)
                tryCompare(trash, "hovered", true)
                verify(actions.visible)
                fuzzyCompare(trash.background.color.a, 1, 0.01)
                mouseMove(card, 3, 60)
                tryCompare(actions, "visible", false)

                mouseMove(image, 8, 32)
                tryCompare(actions, "visible", true)
                mouseClick(trash, 10, 10)
                tryVerify(() => gallery.snapshots.length === 7)
                tryCompare(grid, "pendingScrollOffset", -1)
                compare(grid.contentY - grid.originY, rowOffset)
                compare(gallery.feedback, "Snapshot moved to Trash.")

                const previousBottom = grid.contentHeight - grid.height
                grid.contentY = grid.originY + previousBottom
                tryVerify(() => grid.itemAtIndex(6) !== null)
                const lastCard = grid.itemAtIndex(6)
                const lastImage = lastCard.children[0]
                const lastTrash = findChild(lastImage, "trash-WebcamTuner-1.jpg")
                mouseMove(lastImage, 8, 32)
                tryCompare(lastTrash, "visible", true)
                mouseClick(lastTrash, 10, 10)
                tryVerify(() => gallery.snapshots.length === 6)
                tryCompare(grid, "pendingScrollOffset", -1)
                compare(grid.contentY - grid.originY, previousBottom - grid.cellHeight)
                verify(grid.atYEnd)
                console.log("SNAPSHOT_GALLERY_PASS")
            }
        }
    }

    Timer {
        interval: 250
        running: true
        onTriggered: {
            try {
                test.exercise()
                Qt.quit()
            } catch (error) {
                console.error(error)
                Qt.exit(1)
            }
        }
    }
}
'''.replace('UI_PATH', json.dumps((root / 'ui').as_uri())))
    result = subprocess.run(['qs', '-p', str(harness)], env=env, text=True,
                            capture_output=True, timeout=15)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and 'SNAPSHOT_GALLERY_PASS' in output, output
    assert not removed.exists() and not last.exists() and retained.is_file() and mirror.is_file()
    assert (data / 'Trash/files' / removed.name).read_bytes() == original
    assert (data / 'Trash/info' / (removed.name + '.trashinfo')).is_file()

print('PASS: snapshot hover and Trash preserve the visible row and clamp after the last row disappears')
