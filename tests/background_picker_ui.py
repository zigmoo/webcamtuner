"""Exercise the Add images picker with and without preferred home folders."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtCore import QObject, QPointF, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest


root = Path(__file__).resolve().parents[1]
with TemporaryDirectory(dir=os.environ['WEBCAMTUNER_TEST_ROOT']) as temporary:
    home = Path(temporary) / 'home with spaces'
    home.mkdir()
    os.environ.update(HOME=str(home), QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')

    app = QGuiApplication([])
    view = QQuickView()
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    view.setSource(QUrl.fromLocalFile(str(root / 'ui/Editor.qml')))
    assert view.status() == QQuickView.Ready
    view.resize(700, 780)
    editor = view.rootObject()
    editor.setProperty('testing', True)
    editor.setProperty('section', 'background')
    editor.setProperty('libraryPending', False)
    view.show()
    QTest.qWait(80)

    button = editor.findChild(QObject, 'addBackgrounds')
    dialog = editor.findChild(QObject, 'backgroundImageDialog')
    point = button.mapToScene(QPointF(button.width() / 2, button.height() / 2)).toPoint()

    pictures, lowercase_pictures, screenshots, lowercase_screenshots = (
        home / name for name in ('Pictures', 'pictures', 'Screenshots', 'screenshots')
    )
    for directory in (lowercase_pictures, screenshots, lowercase_screenshots):
        directory.mkdir()
    pictures.symlink_to(lowercase_pictures, target_is_directory=True)

    for folder in (pictures, lowercase_pictures, screenshots, lowercase_screenshots, home):
        QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, point)
        QTest.qWait(60)
        assert dialog.property('visible')
        assert Path(dialog.property('currentFolder').toLocalFile()) == folder
        dialog.setProperty('visible', False)
        QTest.qWait(20)
        if folder.is_symlink():
            folder.unlink()
            folder.touch()  # A file named Pictures must be skipped.
        elif folder != home:
            folder.rmdir()

print('PASS: Add images opens Pictures, pictures, Screenshots, screenshots, then Home')
