"""Editing rectangles uses original pixel coordinates through public Qt controls."""

from dataclasses import replace

import numpy as np
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QComboBox, QLabel, QListWidget, QPushButton, QWidget

from make_registration_fixtures import frames_with_data
from stmviewer.registration_masks import FrameMasks, MaskRectangle
from stmviewer.ui.mask_editor import MaskEditorDialog


def editor(qtbot, *, frames=None, masks=None):
    if frames is None:
        values = np.arange(400, dtype=float).reshape(20, 20)
        frames = tuple(replace(f, size_x_nm=20, size_y_nm=20)
                       for f in frames_with_data(values, values + 100))
    masks = masks if masks is not None else FrameMasks()
    dialog = MaskEditorDialog(frames, masks, None)
    qtbot.addWidget(dialog)
    preview = dialog.findChild(QWidget, 'maskPreview')
    preview.setFixedSize(400, 400)
    dialog.show()
    return dialog, preview, masks, frames


def draw(qtbot, dialog, preview, mode, start, end):
    dialog.findChild(QComboBox, 'maskEditMode').setCurrentText(mode)
    qtbot.mousePress(preview, Qt.MouseButton.LeftButton, pos=QPoint(*start))
    qtbot.mouseRelease(preview, Qt.MouseButton.LeftButton, pos=QPoint(*end))


def test_include_exclude_overlay_and_removal_preserve_measurements(qtbot):
    dialog, preview, masks, frames = editor(qtbot)
    original = frames[0].data.copy()
    draw(qtbot, dialog, preview, 'Dodaj: użyj', (80, 80), (180, 200))
    assert masks.get(frames[0]).rectangles == (MaskRectangle(4, 4, 9, 10, 'use'),)
    assert '30 / 400' in dialog.findChild(QLabel, 'maskSummary').text()
    draw(qtbot, dialog, preview, 'Dodaj: pomiń', (100, 100), (140, 160))
    assert masks.get(frames[0]).rectangles[-1] == MaskRectangle(5, 5, 7, 8, 'omit')
    assert '24 / 400' in dialog.findChild(QLabel, 'maskSummary').text()
    image = preview.grab().toImage()
    included, omitted, outside = [image.pixelColor(*p) for p in [(90, 90), (110, 110), (50, 50)]]
    assert included.green() > included.red()
    assert omitted.red() > omitted.green() and outside.red() > outside.green()
    np.testing.assert_array_equal(frames[0].data, original)
    assert masks.get(frames[1]).rectangles == ()
    dialog.findChild(QListWidget, 'maskRectangles').setCurrentRow(1)
    dialog.findChild(QPushButton, 'removeMaskRectangle').click()
    assert '30 / 400' in dialog.findChild(QLabel, 'maskSummary').text()
    dialog.findChild(QPushButton, 'clearFrameMask').click()
    assert masks.get(frames[0]).rectangles == ()
    assert '400 / 400' in dialog.findChild(QLabel, 'maskSummary').text()


def test_wheel_zoom_and_pan_keep_drawn_rectangles_in_original_pixels(qtbot):
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QWheelEvent
    from PyQt6.QtWidgets import QApplication

    dialog, preview, masks, frames = editor(qtbot)
    draw(qtbot, dialog, preview, 'Dodaj: użyj', (20, 20), (60, 60))
    first = MaskRectangle(1, 1, 3, 3, 'use')
    assert masks.get(frames[0]).rectangles == (first,)
    QApplication.sendEvent(preview, QWheelEvent(
        QPointF(200, 200), QPointF(preview.mapToGlobal(QPoint(200, 200))),
        QPoint(), QPoint(0, 120), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False))
    draw(qtbot, dialog, preview, 'Przesuwaj', (200, 200), (224, 212))
    assert masks.get(frames[0]).rectangles == (first,)
    # At 1.2x, source pixels are 24 screen px; image origin is (-16,-28).
    draw(qtbot, dialog, preview, 'Dodaj: użyj', (80, 92), (200, 212))
    assert masks.get(frames[0]).rectangles == (first, MaskRectangle(4, 5, 9, 10, 'use'))
    dialog.findChild(QPushButton, 'maskFit').click()
    draw(qtbot, dialog, preview, 'Dodaj: pomiń', (80, 100), (180, 200))
    assert masks.get(frames[0]).rectangles[-1] == MaskRectangle(4, 5, 9, 10, 'omit')
    assert '4 / 400' in dialog.findChild(QLabel, 'maskSummary').text()


def test_physical_aspect_clipping_and_fit_keep_the_drawing_mode(qtbot):
    from PyQt6.QtWidgets import QCheckBox

    frame = replace(frames_with_data(np.arange(800, dtype=float).reshape(20, 40))[0],
                    size_x_nm=20, size_y_nm=20)
    dialog, preview, masks, frames = editor(qtbot, frames=(frame,))
    dialog.findChild(QCheckBox, 'maskPixelProportions').setChecked(False)
    draw(qtbot, dialog, preview, 'Dodaj: pomiń', (300, 300), (450, 450))
    assert masks.get(frame).rectangles == (MaskRectangle(30, 15, 40, 20, 'omit'),)
    assert '750 / 800' in dialog.findChild(QLabel, 'maskSummary').text()
    dialog.findChild(QPushButton, 'maskFit').click()
    assert preview.cursor().shape() == Qt.CursorShape.CrossCursor
    dialog.findChild(QCheckBox, 'maskPixelProportions').setChecked(True)
    assert masks.get(frame).rectangles == (MaskRectangle(30, 15, 40, 20, 'omit'),)
    overlay = dialog.findChild(QCheckBox, 'showMaskOverlay')
    overlay.setChecked(False)
    color = preview.grab().toImage().pixelColor(50, 150)
    assert color.red() == color.green() == color.blue()


def test_frame_navigation_cancels_unfinished_rectangles_and_busy_state_blocks_edits(qtbot):
    from PyQt6.QtWidgets import QDoubleSpinBox, QSpinBox

    dialog, preview, masks, frames = editor(qtbot)
    draw(qtbot, dialog, preview, 'Dodaj: pomiń', (20, 40), (100, 120))
    first = MaskRectangle(1, 2, 5, 6, 'omit')
    assert masks.get(frames[0]).rectangles == (first,)
    number = dialog.findChild(QSpinBox, 'maskFrameNumber')
    qtbot.mousePress(preview, Qt.MouseButton.LeftButton, pos=QPoint(150, 150))
    number.setValue(2)
    qtbot.mouseRelease(preview, Qt.MouseButton.LeftButton, pos=QPoint(250, 250))
    assert masks.get(frames[1]).rectangles == ()
    assert 'MPP 2' in dialog.findChild(QLabel, 'maskSource').text()
    draw(qtbot, dialog, preview, 'Dodaj: użyj', (120, 140), (180, 200))
    second = MaskRectangle(6, 7, 9, 10, 'use')
    assert masks.get(frames[1]).rectangles == (second,)
    dialog.select_frame(0)
    assert dialog.findChild(QListWidget, 'maskRectangles').count() == 1
    assert '384 / 400' in dialog.findChild(QLabel, 'maskSummary').text()
    dialog.findChild(QListWidget, 'maskRectangles').setCurrentRow(0)
    dialog.set_available(False)
    assert not dialog.findChild(QComboBox, 'maskEditMode').isEnabled()
    assert not dialog.findChild(QPushButton, 'removeMaskRectangle').isEnabled()
    assert not dialog.findChild(QPushButton, 'clearFrameMask').isEnabled()
    assert dialog.findChild(QDoubleSpinBox, 'maskGamma').isEnabled()
    qtbot.mousePress(preview, Qt.MouseButton.LeftButton, pos=QPoint(180, 180))
    qtbot.mouseRelease(preview, Qt.MouseButton.LeftButton, pos=QPoint(260, 260))
    assert masks.get(frames[0]).rectangles == (first,)
    dialog.set_available(True)
    assert dialog.findChild(QPushButton, 'removeMaskRectangle').isEnabled()
    # A changed series ordinal does not change the source frame's selections.
    masks.remove(frames[0])
    reopened, _, _, _ = editor(qtbot, frames=(frames[1],), masks=masks)
    assert 'MPP 2' in reopened.findChild(QLabel, 'maskSource').text()
    assert '9 / 400' in reopened.findChild(QLabel, 'maskSummary').text()
    assert masks.get(frames[1]).rectangles == (second,)
