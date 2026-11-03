"""Visible local support follows the image view without altering image values."""

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor, QImage

from deep_ecc_fixture import controlled_loftr as model_fixture

controlled_loftr = model_fixture


def test_patch_overlay_tracks_zoom_and_pan_without_changing_the_source_image(qtbot):
    from stmviewer.ui.image_preview import ImagePreview, PreviewOverlay

    preview = ImagePreview()
    qtbot.addWidget(preview)
    preview.setFixedSize(400, 400)
    source = QImage(100, 80, QImage.Format.Format_RGB32)
    source.fill(QColor('black'))
    original = source.copy()
    preview.set_image(source, aspect=1.25)
    preview.set_overlays((PreviewOverlay((10, 10, 20, 10), '#23c26b', '1', (4, -2)),))
    preview.show()
    before = preview.grab().toImage()
    assert before.pixelColor(80, 80) == QColor('#23c26b')
    assert source == original

    preview.zoom_in()
    qtbot.mousePress(preview, Qt.MouseButton.LeftButton, pos=QPoint(180, 170))
    qtbot.mouseRelease(preview, Qt.MouseButton.LeftButton, pos=QPoint(200, 180))
    after = preview.grab().toImage()
    # Fit target (0,40,400,320), then 1.2 zoom and (+20,+10) pan.
    assert after.pixelColor(75, 66) == QColor('#23c26b')
    assert source == original
    preview.set_overlays(())
    assert preview.grab().toImage().pixelColor(75, 66) == QColor('black')


def test_user_compares_exact_deep_start_and_local_evidence_without_changing_saved_trial(
        qtbot, controlled_loftr):
    from PyQt6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QLabel, QPushButton, QTableWidget, QWidget
    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.ui.pair_dialog import PairComparisonDialog
    from deep_ecc_fixture import textured_pair

    control, weights = controlled_loftr
    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = PairComparisonDialog(textured_pair(), 1, parent,
                                  deep_options=DeepMatcherOptions(weights, 'cpu'))
    qtbot.addWidget(dialog)
    dialog.show()
    stage = dialog.findChild(QComboBox, 'pairLocalStage')
    assert stage is not None
    run = dialog.findChild(QPushButton, 'runPair')
    run.click()
    qtbot.waitUntil(run.isEnabled)
    saved = dialog.findChild(QLabel, 'pairResult').text()
    dialog.findChild(QPushButton, 'pinPair').click()
    layer = dialog.findChild(QComboBox, 'pairLayer')
    layer.setCurrentText('Klatka bazowa')
    preview = dialog.findChild(QWidget, 'pairPreview')
    preview.setFixedSize(400, 350)
    dialog.findChild(QPushButton, 'pairZoomIn').click()
    qtbot.mousePress(preview, Qt.MouseButton.LeftButton, pos=QPoint(180, 170))
    qtbot.mouseRelease(preview, Qt.MouseButton.LeftButton, pos=QPoint(200, 185))
    gamma = dialog.findChild(QDoubleSpinBox, 'pairGamma')
    gamma.setValue(1.8)
    reference_pixels = preview.grab().toImage()
    contrast = dialog.findChild(QLabel, 'pairContrast').text()

    dialog.findChild(QComboBox, 'pairMethod').setCurrentText('Deep Matcher + lokalne fragmenty (v1)')
    run.click()
    qtbot.waitUntil(run.isEnabled, timeout=10000)
    details = dialog.findChild(QLabel, 'pairLocalDetails')
    assert stage.isVisible()
    assert 'Start Deep' in details.text() and 'Wynik lokalny' in details.text()
    assert 'bez niezależnej oceny' in details.text()
    table = dialog.findChild(QTableWidget, 'pairLocalPatches')
    assert table.rowCount() > 0
    assert any(table.item(row, 1).text() == 'Zgodny' for row in range(table.rowCount()))
    selected = next(row for row in range(table.rowCount()) if table.item(row, 1).text() == 'Zgodny')
    table.setCurrentCell(selected, 0)
    patch_info = dialog.findChild(QLabel, 'pairLocalPatchDetails').text()
    assert 'Kontrast maksimum:' in patch_info and 'heurystyczne' in patch_info
    overlay = dialog.findChild(QCheckBox, 'pairLocalOverlay')
    assert overlay.isChecked()
    assert preview.grab().toImage() != reference_pixels
    overlay.setChecked(False)
    assert preview.grab().toImage() == reference_pixels
    stage.setCurrentText('Start Deep tej próby')
    assert 'Start Deep' in dialog.findChild(QLabel, 'pairPreviewStatus').text()
    assert 'ΔX: 19 px' in dialog.findChild(QLabel, 'pairResult').text()
    assert 'ΔY: -12 px' in dialog.findChild(QLabel, 'pairResult').text()
    assert control.calls == 1
    assert preview.grab().toImage() == reference_pixels
    assert gamma.value() == 1.8 and dialog.findChild(QLabel, 'pairContrast').text() == contrast
    dialog.findChild(QPushButton, 'pairSavedResult').click()
    assert dialog.findChild(QLabel, 'pairResult').text() == saved
    assert not stage.isVisible()
    assert preview.grab().toImage() == reference_pixels
    dialog.close()



def test_local_refusal_exposes_evidence_without_replacing_or_applying_previous_trial(qtbot, controlled_loftr):
    import numpy as np
    from PyQt6.QtWidgets import QCheckBox, QComboBox, QLabel, QPushButton, QTableWidget, QWidget
    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.ui.pair_dialog import PairComparisonDialog
    from make_registration_fixtures import frames_with_data

    control, weights = controlled_loftr
    control.shifts = [(0, 0)]
    yy, xx = np.indices((128, 192))
    periodic = np.cos(xx * np.pi / 4) + np.cos(yy * np.pi / 4)
    frames = frames_with_data(periodic, periodic.copy())
    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = PairComparisonDialog(frames, 1, parent, deep_options=DeepMatcherOptions(weights, 'cpu'))
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.findChild(QPushButton, 'manualPairZero').click()
    dialog.findChild(QPushButton, 'manualPairXPlus').click()
    dialog.findChild(QPushButton, 'manualPairApply').click()
    previous = dialog.findChild(QLabel, 'pairResult').text()
    dialog.findChild(QPushButton, 'pinPair').click()

    dialog.findChild(QComboBox, 'pairMethod').setCurrentText('Deep Matcher + lokalne fragmenty (v1)')
    run = dialog.findChild(QPushButton, 'runPair')
    run.click()
    qtbot.waitUntil(run.isEnabled, timeout=10000)
    refusal = dialog.findChild(QCheckBox, 'pairLocalFailure')
    assert refusal.isVisible() and refusal.isChecked()
    assert 'odmowy' in dialog.findChild(QLabel, 'pairPreviewStatus').text()
    assert 'brak nowego wyniku' in dialog.findChild(QLabel, 'pairPreviewStatus').text()
    assert 'odmowa' in dialog.findChild(QLabel, 'pairLocalDetails').text()
    table = dialog.findChild(QTableWidget, 'pairLocalPatches')
    assert table.rowCount() > 0
    assert any(table.item(row, 1).text() == 'Brak dopasowania' for row in range(table.rowCount()))
    assert not dialog.findChild(QPushButton, 'manualPairCorrect').isEnabled()
    assert not dialog.findChild(QPushButton, 'pinPair').isEnabled()
    assert not dialog.findChild(QPushButton, 'manualMovieApply').isEnabled()
    dialog.findChild(QPushButton, 'pairSavedResult').click()
    assert not refusal.isChecked()
    assert dialog.findChild(QLabel, 'pairResult').text() == previous
    dialog.findChild(QPushButton, 'pairCurrentResult').click()
    assert dialog.findChild(QLabel, 'pairResult').text() == previous
    refusal.setChecked(True)
    dialog.findChild(QPushButton, 'manualPairZero').click()
    dialog.findChild(QPushButton, 'manualPairYPlus').click()
    dialog.findChild(QPushButton, 'manualPairApply').click()
    assert not refusal.isChecked()
    assert 'ΔX: 0 px' in dialog.findChild(QLabel, 'pairResult').text()
    assert 'ΔY: 1 px' in dialog.findChild(QLabel, 'pairResult').text()
    dialog.findChild(QPushButton, 'pairSavedResult').click()
    assert dialog.findChild(QLabel, 'pairResult').text() == previous
    dialog.close()
