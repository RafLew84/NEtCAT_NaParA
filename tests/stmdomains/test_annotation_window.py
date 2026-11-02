"""Real input and mouse interaction keep image and annotations in one geometry."""

import json

import numpy as np
import pytest
from PyQt6.QtCore import QPointF, Qt

from stmdomains.tools.demo_inputs import write_mpp, write_session
from stmdomains.tools.annotation_demo import create_annotation_demo
from stmdomains.ui.main_window import STMDomainsMainWindow


def annotated_session(tmp_path):
    raw = np.zeros((2, 32, 48))
    raw[:, 8:16, 12:20] = 100
    source = write_mpp(tmp_path / "molecules.mpp", raw[:, ::-1, ::-1])
    path = write_session(tmp_path / "molecules.json", source, [0, 1])
    payload = json.loads(path.read_text())
    payload["registration"] = {"reference_frame_index": 0, "results_by_frame": [
        {"frame_index": 0, "shift_xy": [0, 0], "status": "ok"},
        {"frame_index": 1, "shift_xy": [-0.5, 0.25], "status": "low_confidence"},
    ]}
    payload["molecular_detections"] = {"frame_count": 2, "detections": [
        {"frame_index": 0, "detection_id": "molecule-A", "source_view": "expanded_aligned",
         "bbox_xyxy": [13, 8, 21, 16], "confidence": 0.8, "selected": False},
    ]}
    path.write_text(json.dumps(payload))
    return path


def test_user_sees_and_selects_same_molecule_in_both_views(qtbot, tmp_path):
    path = annotated_session(tmp_path)
    before = path.read_bytes()
    window = STMDomainsMainWindow()
    qtbot.addWidget(window)
    window.show()
    window.controller.open_session(path)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    controls = window.annotation_controls
    assert controls.view_mode.isEnabled()
    point = window.image_view.mapFromScene(QPointF(16, 12))
    color = window.image_view.viewport().grab().toImage().pixelColor(point)
    assert color.green() > color.red()  # Center on the literal raw molecule location.
    qtbot.mouseClick(window.image_view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert "molecule-A" in window.selection_label.text()
    assert "0.8" in window.selection_label.text()
    controls.view_mode.setCurrentIndex(1)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert window.image_view.sceneRect().width() == 49
    point = window.image_view.mapFromScene(QPointF(17, 12))
    qtbot.mouseClick(window.image_view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert "molecule-A" in window.selection_label.text()
    controls.centers.setChecked(False)
    controls.boxes.setChecked(False)
    color = window.image_view.viewport().grab().toImage().pixelColor(point)
    assert color.red() == color.green() == color.blue()
    qtbot.mouseClick(window.next_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Klatka 2 / 2" in window.frame_label.text())
    assert "nisk" in window.registration_label.text().lower()
    assert "brak zapisanych" in window.annotation_status.text().lower()
    assert "molecule-A" not in window.selection_label.text()
    assert path.read_bytes() == before


def test_masks_opacity_and_missing_registration_remain_independent(qtbot, tmp_path):
    paths = create_annotation_demo(tmp_path)
    window = STMDomainsMainWindow()
    qtbot.addWidget(window)
    window.show()
    window.controller.open_session(paths["registered"])
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    controls = window.annotation_controls
    controls.centers.setChecked(False)
    controls.masks.setChecked(True)
    point = window.image_view.mapFromScene(QPointF(12, 9))
    color = window.image_view.viewport().grab().toImage().pixelColor(point)
    assert color.green() > color.red()
    controls.opacity.setValue(0)
    color = window.image_view.viewport().grab().toImage().pixelColor(point)
    assert color.red() == color.green() == color.blue()
    controls.opacity.setValue(65)
    qtbot.mouseClick(window.image_view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert "mask-raw-A" in window.selection_label.text()
    controls.centers.setChecked(True)
    controls.view_mode.setCurrentIndex(1)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    fitted = window.image_view.transform().m11()
    window.image_view.zoom_by(2)
    qtbot.mouseClick(window.next_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Klatka 2 / 2" in window.frame_label.text())
    assert window.image_view.transform().m11() == pytest.approx(fitted * 2)
    window.resize(1250, 850)
    point = window.image_view.mapFromScene(QPointF(12.5, 10.25))
    qtbot.mouseClick(window.image_view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert "fractional-A" in window.selection_label.text()
    window.controller.open_session(paths["no_registration"])
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert not controls.view_mode.isEnabled()
    assert controls.view_mode.currentIndex() == 0
    point = window.image_view.mapFromScene(QPointF(12, 9))
    qtbot.mouseClick(window.image_view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert "raw-A" in window.selection_label.text()
    assert "niedostęp" in window.registration_label.text().lower()
    point = window.image_view.mapFromScene(QPointF(34, 23))
    qtbot.mouseClick(window.image_view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert "aligned-B" not in window.selection_label.text()


def test_invalid_optional_mask_keeps_standalone_segmentation_box(qtbot, tmp_path):
    paths = create_annotation_demo(tmp_path)
    path = paths["bad_mask"]
    payload = json.loads(path.read_text())
    payload["molecular_detections"]["detections"] = []
    segment = payload["molecular_segmentations"]["segmentations"][0]
    segment["prompt_detection_ids"] = []
    segment["polygon_xy"] = None
    payload["molecular_segmentations"]["segmentations"] = [segment]
    path.write_text(json.dumps(payload))
    window = STMDomainsMainWindow()
    qtbot.addWidget(window)
    window.show()
    window.controller.open_session(path)
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    assert window.annotation_controls.boxes.isEnabled()
    window.annotation_controls.boxes.setChecked(True)
    point = window.image_view.mapFromScene(QPointF(8, 9))
    color = window.image_view.viewport().grab().toImage().pixelColor(point)
    assert color.green() > color.red()
    point = window.image_view.mapFromScene(QPointF(12, 9))
    qtbot.mouseClick(window.image_view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert "mask-raw-A" in window.selection_label.text()
