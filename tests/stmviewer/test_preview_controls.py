"""Preview controls checked through visible pixels and public GUI actions."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDoubleSpinBox, QFileDialog, QListView, QPushButton, QWidget
import pytest

from stmviewer.ui.main_window import STMViewerMainWindow

FIXTURES = Path(__file__).parent / 'fixtures'


def open_files(qtbot, window, monkeypatch, paths):
    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *args: ([str(p) for p in paths], ''))
    button = window.findChild(QPushButton, 'openFrames')
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(button.isEnabled)


def image(widget):
    return widget.grab().toImage().scaled(widget.size())


@pytest.fixture
def window(qtbot):
    window = STMViewerMainWindow()
    qtbot.addWidget(window)
    window.findChild(QWidget, 'imagePreview').setFixedSize(400, 300)
    window.show()
    return window


def test_gamma_changes_main_image_only_and_can_be_reset(window, qtbot, monkeypatch):
    open_files(qtbot, window, monkeypatch, [FIXTURES / 'asymmetric.stp'])
    preview = window.findChild(QWidget, 'imagePreview')
    assert image(preview).pixelColor(300, 50).red() == 63
    gamma = window.findChild(QDoubleSpinBox, 'previewGamma')
    assert gamma is not None and gamma.value() == 1
    assert (gamma.minimum(), gamma.maximum()) == (0.1, 4)
    strip = window.findChild(QListView, 'frameThumbnails')
    original_thumbnail = strip.model().index(0, 0).data(Qt.ItemDataRole.DecorationRole).pixmap(96, 72).toImage()

    gamma.setValue(2)

    assert image(preview).pixelColor(300, 50).red() == 127
    assert image(preview).pixelColor(100, 50).red() == 255
    assert image(preview).pixelColor(200, 50).red() == 0
    assert strip.model().index(0, 0).data(Qt.ItemDataRole.DecorationRole).pixmap(96, 72).toImage() == original_thumbnail
    gamma.setValue(0.5)
    assert image(preview).pixelColor(300, 50).red() == 15
    qtbot.mouseClick(window.findChild(QPushButton, 'resetGamma'), Qt.MouseButton.LeftButton)
    assert gamma.value() == 1
    assert image(preview).pixelColor(300, 50).red() == 63


def test_gamma_and_view_survive_frame_changes_and_failed_import_but_reset_on_success(
    window, qtbot, monkeypatch, tmp_path
):
    from PyQt6.QtCore import QPoint, QPointF
    from PyQt6.QtGui import QWheelEvent
    from PyQt6.QtWidgets import QApplication, QCheckBox, QMessageBox, QSpinBox

    copy = tmp_path / 'second.stp'
    copy.write_bytes((FIXTURES / 'asymmetric.stp').read_bytes())
    open_files(qtbot, window, monkeypatch, [FIXTURES / 'asymmetric.stp', copy])
    preview = window.findChild(QWidget, 'imagePreview')
    fitted = image(preview)
    pixels = window.findChild(QCheckBox, 'pixelProportions')
    pixels.setChecked(True)
    gamma = window.findChild(QDoubleSpinBox, 'previewGamma')
    gamma.setValue(2)
    event = QWheelEvent(QPointF(100, 100), QPointF(preview.mapToGlobal(QPoint(100, 100))),
                        QPoint(), QPoint(0, 120), Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(preview, event)
    qtbot.mousePress(preview, Qt.MouseButton.LeftButton, pos=QPoint(150, 150))
    qtbot.mouseRelease(preview, Qt.MouseButton.LeftButton, pos=QPoint(175, 160))
    configured = image(preview)
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    assert gamma.value() == 2 and pixels.isChecked() and image(preview) == configured
    open_files(qtbot, window, monkeypatch, [])
    assert gamma.value() == 2 and pixels.isChecked() and image(preview) == configured
    open_files(qtbot, window, monkeypatch, [FIXTURES / 'truncated.stp'])
    message = window.findChild(QMessageBox)
    assert message.isVisible()
    message.accept()
    assert gamma.value() == 2 and pixels.isChecked() and image(preview) == configured

    open_files(qtbot, window, monkeypatch, [FIXTURES / 'asymmetric.stp'])

    assert gamma.value() == 1 and not pixels.isChecked()
    assert image(preview) == fitted


def test_zoom_buttons_use_center_and_fit_keeps_gamma(window, qtbot, monkeypatch):
    open_files(qtbot, window, monkeypatch, [FIXTURES / 'unknown.stp'])
    preview = window.findChild(QWidget, 'imagePreview')
    gamma = window.findChild(QDoubleSpinBox, 'previewGamma')
    gamma.setValue(2)
    fitted = image(preview)
    zoom_in = window.findChild(QPushButton, 'zoomIn')
    zoom_out = window.findChild(QPushButton, 'zoomOut')
    assert zoom_in is not None and zoom_out is not None
    qtbot.mouseClick(zoom_in, Qt.MouseButton.LeftButton)
    enlarged = image(preview)
    white = [x for x in range(400) if enlarged.pixelColor(x, 150).red() == 255]
    assert (white[0], white[-1]) == (200, 319)
    qtbot.mouseClick(zoom_out, Qt.MouseButton.LeftButton)
    assert image(preview) == fitted
    qtbot.mouseClick(zoom_in, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.findChild(QPushButton, 'fitImage'), Qt.MouseButton.LeftButton)
    assert image(preview) == fitted and gamma.value() == 2


def test_missing_samples_have_checkerboard_independent_of_gamma(window, qtbot, monkeypatch):
    open_files(qtbot, window, monkeypatch, [FIXTURES / 'preview/pattern1.stp'])
    preview = window.findChild(QWidget, 'imagePreview')
    before = image(preview)
    missing = {(x, y): before.pixelColor(x, y).rgba() for x in range(304, 344) for y in range(4, 44)}
    assert {before.pixelColor(x, y).red() for x, y in missing} == {96, 144}
    assert before.pixelColor(50, 50).red() == 0
    assert before.pixelColor(150, 50).red() == 63
    strip = window.findChild(QListView, 'frameThumbnails')
    icon = strip.model().index(0, 0).data(Qt.ItemDataRole.DecorationRole).pixmap(96, 72).toImage()
    assert icon.pixelColor(90, 5).red() in (96, 144)

    for value, grey in [(2, 127), (0.1, 0), (4, 180)]:
        window.findChild(QDoubleSpinBox, 'previewGamma').setValue(value)
        after = image(preview)
        assert {(x, y): after.pixelColor(x, y).rgba() for x, y in missing} == missing
        assert after.pixelColor(50, 50).red() == 0
        assert after.pixelColor(150, 50).red() == grey
        assert strip.model().index(0, 0).data(Qt.ItemDataRole.DecorationRole).pixmap(96, 72).toImage() == icon


def test_pixel_proportions_override_header_without_changing_metadata(window, qtbot, monkeypatch):
    from PyQt6.QtWidgets import QCheckBox, QLabel, QSpinBox

    open_files(qtbot, window, monkeypatch, [FIXTURES / 'preview/physical.stp', FIXTURES / 'preview/placeholder.stp'])
    preview = window.findChild(QWidget, 'imagePreview')
    gamma = window.findChild(QDoubleSpinBox, 'previewGamma')
    gamma.setValue(2)
    physical = image(preview)
    assert physical.pixelColor(20, 50).red() != 0
    option = window.findChild(QCheckBox, 'pixelProportions')
    assert option is not None and not option.isChecked()
    strip = window.findChild(QListView, 'frameThumbnails')
    assert strip.currentIndex().data(Qt.ItemDataRole.DecorationRole).pixmap(96, 72).width() == 64

    option.setChecked(True)

    assert image(preview).pixelColor(20, 50).red() == 0
    assert image(preview).pixelColor(150, 50).red() == 127
    assert strip.currentIndex().data(Qt.ItemDataRole.DecorationRole).pixmap(96, 72).width() == 96
    text = '\n'.join(label.text() for label in window.findChildren(QLabel))
    assert 'Pole X: 8 nm' in text and 'Pole Y: 9 nm' in text
    window.findChild(QSpinBox, 'frameNumber').setValue(2)
    assert option.isChecked() and gamma.value() == 2
    assert image(preview).pixelColor(20, 50).red() == 0
    assert 'Pole X: 1000 nm' in '\n'.join(label.text() for label in window.findChildren(QLabel))
    open_files(qtbot, window, monkeypatch, [FIXTURES / 'preview/physical.stp'])
    assert not option.isChecked() and gamma.value() == 1
    assert image(preview).pixelColor(20, 50).red() != 0


def test_empty_program_disables_preview_settings(window, qtbot, monkeypatch):
    from PyQt6.QtWidgets import QCheckBox

    controls = [window.findChild(QPushButton, name) for name in ('zoomIn', 'zoomOut', 'fitImage', 'resetGamma')]
    controls += [window.findChild(QDoubleSpinBox, 'previewGamma'), window.findChild(QCheckBox, 'pixelProportions')]
    assert all(control is not None and not control.isEnabled() for control in controls)
    open_files(qtbot, window, monkeypatch, [FIXTURES / 'preview/missing.stp'])
    assert all(control.isEnabled() for control in controls)


@pytest.mark.parametrize('name', ['constant.stp', 'missing.stp'])
def test_constant_and_all_missing_frames_remain_displayable(window, qtbot, monkeypatch, name):
    open_files(qtbot, window, monkeypatch, [FIXTURES / 'preview' / name])
    preview = window.findChild(QWidget, 'imagePreview')
    for gamma, constant_grey in [(1, 127), (2, 180), (0.5, 63)]:
        window.findChild(QDoubleSpinBox, 'previewGamma').setValue(gamma)
        colors = {image(preview).pixelColor(x, 50).red() for x in (4, 12, 20, 28)}
        assert colors == ({constant_grey} if name == 'constant.stp' else {96, 144})


def test_public_preview_actions_never_modify_measurement_values_or_metadata(qtbot):
    import copy
    import numpy as np
    from stmviewer.io import open_stp
    from stmviewer.ui.image_preview import ImagePreview

    frame = open_stp(FIXTURES / 'preview/physical.stp')
    original = frame.data.copy()
    metadata = copy.deepcopy(frame.raw_header)
    frame.data.flags.writeable = False
    preview = ImagePreview()
    qtbot.addWidget(preview)
    preview.resize(400, 300)
    preview.show()
    preview.set_frame(frame)
    for gamma in (0.1, 4, 1):
        preview.set_gamma(gamma)
        preview.zoom_in()
        preview.set_pixel_proportions(True)
        preview.fit_image()
        assert image(preview).pixelColor(50, 50).red() == 0
    np.testing.assert_array_equal(frame.data, original)
    assert frame.raw_header == metadata
    assert (frame.size_x_nm, frame.size_y_nm) == (8, 9)
