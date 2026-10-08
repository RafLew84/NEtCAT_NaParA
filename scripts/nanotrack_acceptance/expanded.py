"""Visible Expanded acceptance on two S1 sessions with independently known bounds."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Callable, cast

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from nanotrack.core import RegistrationFrameResult
from nanotrack.persistence.session_store import load_session_snapshot, save_session_snapshot
from scripts.nanotrack_acceptance.aligned import create_sample
from scripts.nanotrack_acceptance.scenarios import assert_same

if TYPE_CHECKING:
    from scripts.nanotrack_acceptance.scenarios import Scenarios


def create_samples(directory: Path) -> tuple[Path, Path]:
    base = create_sample(directory)
    snapshot = load_session_snapshot(str(base))
    snapshot.show_aligned_in_viewer = False
    snapshot.show_expanded_aligned_in_viewer = True
    first = directory / "S1-expanded.nanotrack"
    save_session_snapshot(str(first), snapshot)
    assert snapshot.registration_results is not None
    snapshot.registration_results.results_by_frame[2] = RegistrationFrameResult(2, (-7.5, 6.25), "S1-known")
    second = directory / "S1-expanded-extreme.nanotrack"
    save_session_snapshot(str(second), snapshot)
    truth = {
        "scale_nm_per_px": [2., 1.],
        "S1-expanded": {"bounds_xyxy": [-2, -3, 100, 67], "shape_hw": [70, 102], "canvas_offset_xy": [2, 3]},
        "S1-expanded-extreme": {"frame_3_shift_xy": [-7.5, 6.25], "bounds_xyxy": [-8, -3, 100, 71],
                                "shape_hw": [74, 108], "canvas_offset_xy": [8, 3]},
        "frame_2_source_point_xy": [20, 20], "frame_2_expanded_point_xy": [25.25, 20.5],
        "frame_2_expanded_point_nm": [50.5, 20.5],
        "value_y23_x22_frames_1_to_6": [17.123456789, 341.873456789, 292.123456789,
                                      318.123456789, 320.123456789, 320.123456789],
        "processed_source": "Synthetic raw +0.25 control; no new BM3D or registration estimation",
    }
    (directory / "S1-expanded-truth.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
    return first, second


def run(scenario: Scenarios) -> None:
    window, report = scenario.window, scenario.report
    apply = window.action_apply_registration
    aligned = window.action_show_aligned_registration
    expanded = window.action_show_expanded_aligned_registration
    assert aligned is not None and expanded is not None
    with report.stage("S1_sessions_and_default_expanded"):
        first, second = create_samples(report.directory)
        report.data["artifacts"].extend([first.name, second.name, "S1-aligned.MPP", "S1-expanded-truth.json"])
        scenario.identify(report.directory / "S1-aligned.MPP")
        window.load_session_from_path(str(first))
        scenario.check_dialogs()
        before = window.current_session_snapshot()
        assert before is not None
        apply.setChecked(False)
        assert window.viewer.viewer.image_item.image.shape == (64, 96)
        apply.setChecked(True)
        assert expanded.isChecked() and not aligned.isChecked()
        scenario.capture("01-default-expanded")
    with report.stage("fixed_canvas_scale_values_and_missing_frames") as stage:
        values = []
        for index, expected in enumerate([17.123456789, 341.873456789, 292.123456789,
                                          318.123456789, 320.123456789, 320.123456789]):
            window.slider_frame.setValue(index)
            frame = window.current_expanded_aligned_frame()
            assert frame is not None and frame.shape == (70, 102) and frame.dtype == np.float64
            np.testing.assert_allclose(frame[23, 22], expected, atol=1e-12, rtol=0)
            values.append(float(frame[23, 22]))
            transform = window.viewer.viewer.image_item.transform()
            np.testing.assert_allclose((transform.m11(), transform.m22()), (2., 1.), atol=1e-12)
            if index in (4, 5):
                assert "Brak własnego dx/dy" in window.viewer.lbl_meta.text()
                np.testing.assert_array_equal(frame[3:67, 2:98], before.sequence.raw_frames[index])
                assert np.isnan(frame[:3]).all() and np.isnan(frame[:, :2]).all()
        stage.update(shape_hw=[70, 102], scale_nm_per_px=[2., 1.], observed_values=values)
        scenario.capture("02-missing-shift")
        window.slider_frame.setValue(2)
        frame = window.current_expanded_aligned_frame()
        assert frame is not None and np.isnan(frame[16:20, 10:14]).all()
        scenario.capture("03-missing-data")
    with report.stage("overlays_mouse_and_three_views") as stage:
        window.slider_frame.setValue(1)
        QApplication.processEvents()
        plot = window.viewer.viewer.plot_item
        rect = next(item for item in plot.items if isinstance(item, pg.RectROI))
        np.testing.assert_allclose((rect.pos().x(), rect.pos().y()), (50.5, 20.5), atol=1e-12)
        lines = [item for item in plot.items if isinstance(item, pg.PlotDataItem)]
        assert any(np.isclose(np.min(item.getData()[0]), 77.5)
                   for item in lines if len(item.getData()[0]) > 10), "Mask contour has wrong canvas origin"
        assert any(np.allclose(item.getData()[0], [110.5, 122.5, 138.5])
                   for item in lines if len(item.getData()[0]) == 3), "Edge overlay has wrong canvas origin"
        polygon_roi = next(item for item in plot.items if isinstance(item, pg.PolyLineROI) and item.closed)
        polygon_roi.movePoint(polygon_roi.getHandles()[0], QPointF(34.5, 37.5), coords="parent")
        polygon = window.current_draft_polygon_roi()
        assert polygon is not None
        np.testing.assert_allclose(polygon.vertices_xy[0], [12., 37.], atol=1e-12)
        edge_roi = next(item for item in plot.items if isinstance(item, pg.PolyLineROI) and not item.closed)
        edge_roi.movePoint(edge_roi.getHandles()[0], QPointF(114.5, 33.5), coords="parent")
        edge = window.current_draft_edge_polyline()
        assert edge is not None
        np.testing.assert_allclose(edge[0], [52., 33.], atol=1e-12)
        window.bbox_tools_panel.sp_width.setValue(8)
        window.bbox_tools_panel.sp_height.setValue(8)
        window.bbox_tools_panel.btn_place.setChecked(True)
        graphics = window.viewer.viewer.glw
        click = cast(Callable[..., None], QTest.mouseClick)
        point = plot.getViewBox().mapViewToScene(QPointF(42.5, 16.5))
        click(graphics.viewport(), Qt.MouseButton.LeftButton, pos=graphics.mapFromScene(point))
        QApplication.processEvents()
        bbox = window.current_draft_bbox()
        assert bbox is not None
        np.testing.assert_allclose(bbox.center_xy, [16., 16.], atol=.3, rtol=0)
        window.bbox_tools_panel.btn_place.setChecked(False)
        window.polygon_tools_panel.btn_clear.click()
        window.polygon_tools_panel.btn_draw.setChecked(True)
        for x, y in [(70., 50.), (78., 50.), (74., 56.)]:
            point = plot.getViewBox().mapViewToScene(QPointF(2*(x+5.25), y+.5))
            click(graphics.viewport(), Qt.MouseButton.LeftButton, pos=graphics.mapFromScene(point))
            QApplication.processEvents()
        window.polygon_tools_panel.btn_finish.click()
        polygon = window.current_draft_polygon_roi()
        assert polygon is not None
        np.testing.assert_allclose(polygon.vertices_xy, [[70., 50.], [78., 50.], [74., 56.]], atol=.3, rtol=0)
        stage.update(bbox_source=bbox.as_tuple(), polygon_source=polygon.vertices_xy.tolist(), edge_source=edge.tolist())
        scenario.capture("04-edited-expanded")
        aligned.setChecked(True)
        assert apply.isChecked() and not expanded.isChecked()
        scenario.capture("05-edited-aligned")
        apply.setChecked(False)
        scenario.capture("06-edited-original")
        assert_same(bbox, window.current_draft_bbox())
        assert_same(polygon, window.current_draft_polygon_roi())
        assert_same(edge, window.current_draft_edge_polyline())
        apply.setChecked(True)
    with report.stage("source_selection"):
        window.cmb_preview_source.setCurrentIndex(1)
        frame = window.current_expanded_aligned_frame()
        assert frame is not None and frame.shape == (70, 102)
        np.testing.assert_allclose(frame[23, 22], 342.123456789, atol=1e-12, rtol=0)
        scenario.capture("07-processed-expanded")
        window.cmb_preview_source.setCurrentIndex(0)
    scenario.roundtrip()
    with report.stage("restored_annotations_and_second_ready_session") as stage:
        restored = window.current_session_snapshot()
        assert restored is not None and restored.show_expanded_aligned_in_viewer
        assert apply.isChecked() and expanded.isChecked()
        assert_same(before.registration_results, restored.registration_results)
        assert_same(before.sequence.raw_frames, restored.sequence.raw_frames)
        assert_same(before.tracks, restored.tracks)
        assert_same(before.edge_tracks, restored.edge_tracks)
        scenario.capture("09-restored-expanded")
        window.load_session_from_path(str(second))
        scenario.check_dialogs()
        frame = window.current_expanded_aligned_frame()
        assert frame is not None and frame.shape == (74, 108)
        np.testing.assert_allclose(frame[23, 28], 341.873456789, atol=1e-12, rtol=0)
        stage["changed_shape_hw"] = [74, 108]
        rect = next(item for item in window.viewer.viewer.plot_item.items if isinstance(item, pg.RectROI))
        np.testing.assert_allclose((rect.pos().x(), rect.pos().y()), (62.5, 20.5), atol=1e-12)
        scenario.capture("10-second-session")
