"""Series import and navigation through visible Qt controls."""

from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QLabel, QListView, QPushButton, QSlider, QSpinBox, QWidget

from stmviewer.ui.main_window import STMViewerMainWindow

FIXTURES = Path(__file__).parent / "fixtures"


def choose(monkeypatch, paths):
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *a, **kw: (
        [str(path) for path in paths], ""
    ))


def labels(window):
    return "\n".join(label.text() for label in window.findChildren(QLabel) if label.isVisible())


def open_selection(qtbot, window, monkeypatch, paths):
    choose(monkeypatch, paths)
    button = window.findChild(QPushButton, "openFrames")
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(button.isEnabled)


@pytest.fixture
def series_window(qtbot, monkeypatch, tmp_path):
    paths = []
    for number, source in [(10, "unknown.stp"), (2, "asymmetric.stp"), (1, "unknown.stp")]:
        path = tmp_path / f"klatka{number}.stp"
        path.write_bytes((FIXTURES / source).read_bytes())
        paths.append(path)
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_selection(qtbot, window, monkeypatch, paths)
    return window


def test_controls_thumbnails_metadata_and_image_follow_the_same_frame(series_window, qtbot):
    window = series_window
    assert "Klatka 1 z 3" in window.statusBar().currentMessage()
    preview = window.findChild(QWidget, "imagePreview")
    first_image = preview.grab().toImage()
    previous = window.findChild(QPushButton, "previousFrame")
    next_button = window.findChild(QPushButton, "nextFrame")
    slider = window.findChild(QSlider, "frameSlider")
    number = window.findChild(QSpinBox, "frameNumber")
    strip = window.findChild(QListView, "frameThumbnails")
    assert [strip.model().index(i, 0).data() for i in range(3)] == [
        "1 · klatka1.stp", "2 · klatka2.stp", "3 · klatka10.stp"
    ]
    assert not previous.isEnabled() and next_button.isEnabled()

    qtbot.mouseClick(next_button, Qt.MouseButton.LeftButton)
    assert "klatka2.stp" in labels(window) and "8 nm" in labels(window)
    assert preview.grab().toImage() != first_image
    assert number.value() == slider.value() == 2
    assert strip.currentIndex().row() == 1

    slider.setValue(3)
    assert "Klatka 3 z 3" in window.statusBar().currentMessage()
    assert "klatka10.stp" in labels(window) and "Pole X: nieznane" in labels(window)
    assert number.value() == 3 and not next_button.isEnabled()
    assert strip.currentIndex().row() == 2

    number.setValue(1)
    assert slider.value() == 1 and strip.currentIndex().row() == 0
    index = strip.model().index(1, 0)
    qtbot.mouseClick(strip.viewport(), Qt.MouseButton.LeftButton, pos=strip.visualRect(index).center())
    assert number.value() == slider.value() == 2
    qtbot.mouseClick(previous, Qt.MouseButton.LeftButton)
    assert "Klatka 1 z 3" in window.statusBar().currentMessage()
    assert preview.grab().toImage() == first_image


@pytest.mark.parametrize("action", ["cancel", "close"])
@pytest.mark.parametrize("extension", ["stp", "s94"])
def test_background_import_can_be_cancelled_or_closed_without_blocking(
    series_window, qtbot, monkeypatch, tmp_path, action, extension
):
    from threading import Event
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QProgressBar

    window = series_window
    number = window.findChild(QSpinBox, "frameNumber")
    number.setValue(2)
    preview = window.findChild(QWidget, "imagePreview")
    previous_image = preview.grab().toImage()
    path = tmp_path / f"slow.{extension}"
    source = FIXTURES / ("unknown.stp" if extension == "stp" else "s94/frame2.s94")
    path.write_bytes(source.read_bytes())
    entered, release = Event(), Event()
    real_open = Path.open

    def slow_open(filename, *args, **kwargs):
        if str(filename) == str(path):
            entered.set()
            if not release.wait(5):
                raise OSError("File I/O did not finish")
        return real_open(filename, *args, **kwargs)

    monkeypatch.setattr(Path, "open", slow_open)
    choose(monkeypatch, [FIXTURES / "asymmetric.stp", path])
    button = window.findChild(QPushButton, "openFrames")
    try:
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(entered.is_set)
        assert not button.isEnabled()
        progress = window.findChild(QProgressBar, "importProgress")
        assert progress.isVisible()
        qtbot.waitUntil(lambda: progress.value() > 0)
        assert progress.value() < progress.maximum()
        heartbeat = []
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        qtbot.waitUntil(lambda: bool(heartbeat))
        cancel = window.findChild(QPushButton, "cancelImport")
        if action == "close":
            window.close()
        else:
            qtbot.mouseClick(cancel, Qt.MouseButton.LeftButton)
        assert not cancel.isEnabled()
    finally:
        release.set()
        qtbot.waitUntil(button.isEnabled)

    if action == "close":
        assert not window.isVisible()
        return
    assert number.value() == 2 and "Klatka 2 z 3" in window.statusBar().currentMessage()
    assert preview.grab().toImage() == previous_image
    assert "klatka2.stp" in labels(window)
    open_selection(qtbot, window, monkeypatch, [path])
    assert "Klatka 1 z 1" in window.statusBar().currentMessage()


@pytest.mark.parametrize("invalid", ["truncated", "dimensions"])
def test_failed_series_import_preserves_selection_and_identifies_bad_source(
    series_window, qtbot, monkeypatch, tmp_path, invalid
):
    from PyQt6.QtWidgets import QMessageBox

    window = series_window
    number = window.findChild(QSpinBox, "frameNumber")
    number.setValue(3)
    before = window.findChild(QWidget, "imagePreview").grab().toImage()
    if invalid == "truncated":
        path = FIXTURES / "truncated.stp"
    else:
        path = tmp_path / "smaller.stp"
        path.write_bytes((FIXTURES / "unknown.stp").read_bytes().replace(
            b"Number of columns: 4", b"Number of columns: 2"
        )[:-48])

    open_selection(qtbot, window, monkeypatch, [FIXTURES / "asymmetric.stp", path])

    message = window.findChild(QMessageBox)
    assert message.isVisible() and path.name in message.text()
    message.accept()
    assert number.value() == 3 and "Klatka 3 z 3" in window.statusBar().currentMessage()
    assert "klatka10.stp" in labels(window)
    assert window.findChild(QWidget, "imagePreview").grab().toImage() == before
    assert window.findChild(QListView, "frameThumbnails").currentIndex().row() == 2


def test_frame_changes_preserve_zoom_and_pan_but_new_series_fits(
    series_window, qtbot, monkeypatch
):
    from PyQt6.QtCore import QPoint, QPointF
    from PyQt6.QtGui import QWheelEvent
    from PyQt6.QtWidgets import QApplication

    window = series_window
    preview = window.findChild(QWidget, "imagePreview")
    preview.setFixedSize(400, 300)
    QApplication.processEvents()
    fitted = preview.grab().toImage()
    event = QWheelEvent(QPointF(100, 100), QPointF(preview.mapToGlobal(QPoint(100, 100))),
                        QPoint(), QPoint(0, 120), Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(preview, event)
    qtbot.mousePress(preview, Qt.MouseButton.LeftButton, pos=QPoint(150, 150))
    qtbot.mouseRelease(preview, Qt.MouseButton.LeftButton, pos=QPoint(180, 170))
    navigated = preview.grab().toImage()
    assert navigated != fitted

    window.findChild(QSpinBox, "frameNumber").setValue(3)  # Same pattern, another frame.
    assert preview.grab().toImage() == navigated
    open_selection(qtbot, window, monkeypatch, [])  # Cancel file selection.
    assert "Klatka 3 z 3" in window.statusBar().currentMessage()
    assert preview.grab().toImage() == navigated
    open_selection(qtbot, window, monkeypatch, [FIXTURES / "unknown.stp"])
    assert preview.grab().toImage() == fitted
    assert not window.findChild(QPushButton, "previousFrame").isEnabled()
    assert not window.findChild(QPushButton, "nextFrame").isEnabled()
    assert window.findChild(QSpinBox, "frameNumber").value() == 1


def test_thumbnail_has_the_known_asymmetric_orientation(series_window):
    strip = series_window.findChild(QListView, "frameThumbnails")
    icon = strip.model().index(1, 0).data(Qt.ItemDataRole.DecorationRole)
    image = icon.pixmap(96, 72).toImage()
    assert image.size().width() == 64 and image.size().height() == 72
    assert image.pixelColor(8, 12).red() == 255  # L down the left edge.
    assert image.pixelColor(40, 60).red() == 255  # L along the bottom.
    assert image.pixelColor(40, 12).red() == 0
    assert image.pixelColor(56, 12).red() == 63  # Quarter-height top-right marker.


def test_selecting_a_distant_frame_scrolls_its_thumbnail_into_view(qtbot, monkeypatch, tmp_path):
    paths = []
    for index in range(20):
        path = tmp_path / f"frame{index}.stp"
        path.write_bytes((FIXTURES / "unknown.stp").read_bytes())
        paths.append(path)
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.show()
    open_selection(qtbot, window, monkeypatch, paths)

    window.findChild(QSpinBox, "frameNumber").setValue(20)

    strip = window.findChild(QListView, "frameThumbnails")
    assert strip.currentIndex().row() == 19
    assert strip.horizontalScrollBar().value() > 0
    assert strip.viewport().rect().contains(strip.visualRect(strip.currentIndex()).center())
    assert "Klatka 20 z 20" in window.statusBar().currentMessage()


def test_frame_buttons_repaint_the_previous_thumbnail_selection(series_window, qtbot):
    from PyQt6.QtCore import QEvent, QObject
    from PyQt6.QtGui import QRegion

    strip = series_window.findChild(QListView, "frameThumbnails")
    repainted = []

    class PaintObserver(QObject):
        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.Paint:
                repainted.append(QRegion(event.region()))
            return False

    observer = PaintObserver(strip)
    strip.viewport().installEventFilter(observer)
    qtbot.wait(50)  # Finish the initial layout/paint before observing navigation.
    for button_name, old_row, new_row in [
        ("nextFrame", 0, 1), ("nextFrame", 1, 2),
        ("previousFrame", 2, 1), ("previousFrame", 1, 0),
    ]:
        old_center = strip.visualRect(strip.model().index(old_row, 0)).center()
        new_center = strip.visualRect(strip.model().index(new_row, 0)).center()
        repainted.clear()

        qtbot.mouseClick(series_window.findChild(QPushButton, button_name), Qt.MouseButton.LeftButton)

        assert [index.row() for index in strip.selectionModel().selectedIndexes()] == [new_row]
        qtbot.waitUntil(lambda: any(region.contains(old_center) for region in repainted), timeout=500)
        qtbot.waitUntil(lambda: any(region.contains(new_center) for region in repainted), timeout=500)
