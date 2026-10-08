"""Known S1 geometry and visible Original/Aligned acceptance, without estimation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Callable, cast

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from nanotrack.core import (
    BBoxXYXY, EdgeFrameAnnotation, EdgeTrack, ParticleTrack, PolygonROI,
    RegistrationFrameResult, RegistrationResultSet, RegistrationSettings, TrackFrameAnnotation,
)
from nanotrack.core.preview_sources import PreprocessingProvenance, PreprocessingStep
from nanotrack.io import load_mpp_sequence
from nanotrack.persistence.session_store import NanoTrackSessionSnapshot, save_session_snapshot

if TYPE_CHECKING:
    from scripts.nanotrack_acceptance.scenarios import Scenarios


def create_sample(directory: Path) -> Path:
    """Analytic plane, feature and literal shifts; no production resampler builds truth."""
    y, x = np.mgrid[:64, :96]
    plane = 100.123456789 + 10*y + x
    plane[28:34, 34:40] += 500
    frames = np.stack([plane]*6)
    frames[0] = 17.123456789
    frames[2, 10:14, 10:14] = np.nan
    source = directory / "S1-aligned.MPP"
    header = ("[General Info]\nNumber of columns: 96\nNumber of rows: 64\nNumber of Frames: 6\n"
              "Acquisition channel: Topography\nZ unit: nm\n[Control]\nX Amplitude: 192 nm\n"
              "Y Amplitude: 64 nm\n[Frames Synchronization]\n"
              + "".join(f"Frame {i:04d}: {i*.5} s\n" for i in range(6)) + "[Header end]\n")
    source.write_bytes(header.encode("ascii") + frames[:, ::-1, ::-1].astype("<f8").tobytes())
    sequence = load_mpp_sequence(str(source))
    np.testing.assert_array_equal(sequence.raw_frames, frames)
    sequence.set_active_frame(1)
    shifts = [(0., 0.), (3.25, -2.5), (-2., 3.), (-.5, .25)]
    registration = RegistrationResultSet(RegistrationSettings(), {
        i: RegistrationFrameResult(i, shift, "S1-known") for i, shift in enumerate(shifts)
    })
    registration.results_by_frame[5] = RegistrationFrameResult(5, (99., 99.), "excluded_frame", status="manual_review")
    bbox = BBoxXYXY(34., 28., 40., 34.)
    polygon = PolygonROI(np.array([[10., 35.], [18., 35.], [14., 43.]]))
    edge = np.array([[50., 30.], [56., 34.], [64., 31.]])
    mask = np.zeros((64, 96), dtype=bool)
    mask[28:34, 34:40] = True
    track = ParticleTrack(1, 0, bbox, label="S1 feature")
    edge_track = EdgeTrack(1, 0, polygon, edge.copy(), label="S1 edge")
    for index in range(6):
        track.add_annotation(TrackFrameAnnotation(index, bbox=bbox, mask=mask.copy()))
        edge_track.add_annotation(EdgeFrameAnnotation(index, polyline=edge.copy()))
    provenance = PreprocessingProvenance(
        steps=(PreprocessingStep("s1_control_offset", "S1 kontrolny offset", {"offset": .25}),),
        source_path=str(source), value_unit="nm", output_dtype="float64",
        validity_rule="finite_samples", input_scale_preserved=True,
    )
    snapshot = NanoTrackSessionSnapshot(
        sequence, tracks=[track], edge_tracks=[edge_track], registration_results=registration,
        show_aligned_in_viewer=True, preview_source="original",
        draft_bboxes_by_frame={1: BBoxXYXY(20., 20., 28., 28.)},
        draft_polygons_by_frame={1: polygon}, draft_edge_polylines_by_frame={1: edge.copy()},
        repair_frames=frames + .25, preprocessing_provenance=provenance, repair_provenance=provenance,
    )
    path = directory / "S1-aligned.nanotrack"
    save_session_snapshot(str(path), snapshot)
    truth = {
        "shape_hw": [64, 96], "scale_nm_per_px": [2., 1.], "source_plane": "100.123456789 + 10*y + x",
        "feature_source_xyxy": [34, 28, 40, 34], "feature_increment": 500,
        "shifts_xy_frames_1_to_4": shifts,
        "aligned_value_y20_x20_frames_1_to_6": [17.123456789, 341.873456789, 292.123456789, 318.123456789, 320.123456789, 320.123456789],
        "missing_registration_frames_1_based": [5, 6], "nan_source_frame_3_yx": [[10, 14], [10, 14]],
        "processed_source": "Synthetic control offset +0.25; not a BM3D or registration benchmark",
    }
    (directory / "S1-truth.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
    return path


def run(scenario: Scenarios) -> None:
    window, report = scenario.window, scenario.report
    aligned_action = window.action_show_aligned_registration
    assert aligned_action is not None
    with report.stage("S1_source_and_session"):
        path = create_sample(report.directory)
        scenario.identify(path.with_suffix(".MPP"))
        window.load_session_from_path(str(path))
        scenario.check_dialogs()
        report.data["artifacts"].extend([path.name, "S1-aligned.MPP", "S1-truth.json"])
        before = window.current_session_snapshot()
        assert before is not None and before.registration_results is not None
        scenario.capture("01-aligned")
    with report.stage("known_scalar_values_and_missing_shifts") as stage:
        expected = [17.123456789, 341.873456789, 292.123456789, 318.123456789, 320.123456789, 320.123456789]
        observed = []
        for index, value in enumerate(expected):
            window.slider_frame.setValue(index)
            frame = window.current_aligned_frame()
            assert frame is not None and frame.dtype == np.float64 and frame.shape == (64, 96)
            np.testing.assert_allclose(frame[20, 20], value, rtol=0, atol=1e-12)
            observed.append(float(frame[20, 20]))
            if index in (4, 5):
                assert "Brak własnego dx/dy" in window.viewer.lbl_meta.text()
                np.testing.assert_array_equal(frame, before.sequence.raw_frames[index])
        stage["observed_y20_x20"] = observed
        scenario.capture("02-missing-shift")
        window.slider_frame.setValue(2)
        frame = window.current_aligned_frame()
        assert frame is not None
        assert np.isnan(frame[13:17, 8:12]).all()
        assert np.isnan(frame[:3, :]).all() and np.isnan(frame[:, -2:]).all()
        scenario.capture("03-validity-and-borders")
    with report.stage("visible_overlays_and_mouse_edits") as stage:
        window.slider_frame.setValue(1)
        QApplication.processEvents()
        plot = window.viewer.viewer.plot_item
        rect = next(item for item in plot.items if isinstance(item, pg.RectROI))
        np.testing.assert_allclose((rect.pos().x(), rect.pos().y()), (46.5, 17.5), atol=1e-12)
        # Existing contours and polylines are inspected in physical display space.
        lines = [item for item in plot.items if isinstance(item, pg.PlotDataItem)]
        assert any(np.allclose(item.getData()[0], [106.5, 118.5, 134.5])
                   for item in lines if len(item.getData()[0]) == 3), "Edge overlay has wrong coordinates"
        mask_lines = [item for item in lines if len(item.getData()[0]) > 10]
        assert any(np.isclose(np.min(item.getData()[0]), 73.5) for item in mask_lines), "Mask contour did not move"
        roi = next(item for item in plot.items if isinstance(item, pg.PolyLineROI) and item.closed)
        first = roi.getSceneHandlePositions()[0][1]
        view_first = plot.getViewBox().mapSceneToView(first)
        np.testing.assert_allclose((view_first.x(), view_first.y()), (26.5, 32.5), atol=1e-10)
        # Public handle editing must map back into source coordinates.
        roi.movePoint(roi.getHandles()[0], QPointF(30.5, 34.5), coords="parent")
        polygon = window.current_draft_polygon_roi()
        assert polygon is not None
        np.testing.assert_allclose(polygon.vertices_xy[0], (12., 37.), atol=1e-10)
        edge_roi = next(item for item in plot.items if isinstance(item, pg.PolyLineROI) and not item.closed)
        edge_roi.movePoint(edge_roi.getHandles()[0], QPointF(110.5, 30.5), coords="parent")
        edited_edge = window.current_draft_edge_polyline()
        assert edited_edge is not None
        np.testing.assert_allclose(edited_edge[0], (52., 33.), atol=1e-10)
        window.bbox_tools_panel.sp_width.setValue(8)
        window.bbox_tools_panel.sp_height.setValue(8)
        window.bbox_tools_panel.btn_place.setChecked(True)
        # Real mouse event at source (16,16), displayed at (19.25,13.5) px.
        graphics = window.viewer.viewer.glw
        scene_point = plot.getViewBox().mapViewToScene(QPointF(38.5, 13.5))
        viewport_point = graphics.mapFromScene(scene_point)
        # PyQt6's stub gives this C++ namespace function an instance-method signature.
        click = cast(Callable[..., None], QTest.mouseClick)
        click(graphics.viewport(), Qt.MouseButton.LeftButton, pos=viewport_point)
        QApplication.processEvents()
        bbox = window.current_draft_bbox()
        assert bbox is not None
        np.testing.assert_allclose(bbox.center_xy, (16., 16.), atol=.3, rtol=0)
        stage["mouse_bbox_source_xyxy"] = bbox.as_tuple()
        window.bbox_tools_panel.btn_place.setChecked(False)
        window.polygon_tools_panel.btn_clear.click()
        window.polygon_tools_panel.btn_draw.setChecked(True)
        source_vertices = [(70., 50.), (78., 50.), (74., 56.)]
        for x, y in source_vertices:
            scene_point = plot.getViewBox().mapViewToScene(QPointF(2*(x+3.25), y-2.5))
            click(graphics.viewport(), Qt.MouseButton.LeftButton, pos=graphics.mapFromScene(scene_point))
            QApplication.processEvents()
        window.polygon_tools_panel.btn_finish.click()
        drawn_polygon = window.current_draft_polygon_roi()
        assert drawn_polygon is not None
        np.testing.assert_allclose(drawn_polygon.vertices_xy, source_vertices, atol=.3, rtol=0)
        stage["mouse_polygon_source_vertices"] = drawn_polygon.vertices_xy.tolist()
        scenario.capture("04-edited-aligned")
        aligned_action.setChecked(False)
        scenario.capture("05-edited-original")
        original_bbox = window.current_draft_bbox()
        assert original_bbox is not None
        np.testing.assert_allclose(original_bbox.as_tuple(), bbox.as_tuple(), atol=1e-12)
        original_polygon = window.current_draft_polygon_roi()
        assert original_polygon is not None
        np.testing.assert_array_equal(original_polygon.vertices_xy, drawn_polygon.vertices_xy)
        aligned_action.setChecked(True)
    with report.stage("source_selection"):
        window.cmb_preview_source.setCurrentIndex(1)
        frame = window.current_aligned_frame()
        assert frame is not None
        np.testing.assert_allclose(frame[20, 20], 342.123456789, rtol=0, atol=1e-12)
        scenario.capture("06-processed-aligned")
        window.cmb_preview_source.setCurrentIndex(0)
    scenario.roundtrip()
    with report.stage("restored_alignment_and_unchanged_analyses"):
        from scripts.nanotrack_acceptance.scenarios import assert_same
        after = window.current_session_snapshot()
        assert after is not None
        assert after.show_aligned_in_viewer and after.preview_source == "original"
        assert_same(before.registration_results, after.registration_results)
        assert_same(before.tracks, after.tracks)
        assert_same(before.edge_tracks, after.edge_tracks)
        assert_same(before.sequence.raw_frames, after.sequence.raw_frames)
        scenario.capture("07-restored")
