"""Visible DexiNed preview, range, resume and persistence on prepared MOVIE_2."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import time
from typing import TYPE_CHECKING, Callable, cast

import numpy as np
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton, QProgressDialog

from nanotrack.edges.backend import DexiNedBackendConfig
from nanotrack.ui.dialogs.edge_preview_dialog import EdgePreviewDialog
from scripts.nanotrack_acceptance.scenarios import assert_same

if TYPE_CHECKING:
    from scripts.nanotrack_acceptance.scenarios import Scenarios


def run(scenario: Scenarios, session: Path) -> None:
    window, report = scenario.window, scenario.report
    panel = window.polygon_tools_panel
    wait = cast(Callable[[int], None], QTest.qWait)
    click = cast(Callable[..., None], QTest.mouseClick)
    aligned, expanded = window.action_show_aligned_registration, window.action_show_expanded_aligned_registration
    assert aligned is not None and expanded is not None

    def complete(button: QPushButton, timeout: float = 150.) -> None:
        deadline = time.monotonic()+timeout
        while not button.isEnabled():
            wait(100)
            scenario.check_dialogs()
            if time.monotonic() > deadline:
                raise TimeoutError("Edge operation exceeded its deadline")
        wait(50)
        scenario.check_dialogs()

    def show_description(widget) -> None:
        window.setFocus()
        wait(50)
        window.sidebar_scroll_area.ensureWidgetVisible(widget, 0, 8)
        content = window.sidebar_scroll_area.widget()
        vertical = window.sidebar_scroll_area.verticalScrollBar()
        assert content is not None and vertical is not None
        vertical.setValue(widget.mapTo(content, QPoint(0, 0)).y() - 60)
        scroll = window.sidebar_scroll_area.horizontalScrollBar()
        assert scroll is not None
        scroll.setValue(0)
        wait(50)

    with report.stage("open_prepared_MOVIE_2"):
        scenario.identify(session)
        report.data["inputs"] = [report.data["input"]]
        window.load_session_from_path(str(session))
        snapshot = window.current_session_snapshot()
        assert snapshot is not None and snapshot.sequence.frame_count == 196
        assert snapshot.denoised_frames is not None and snapshot.registration_results is not None
        config = DexiNedBackendConfig()
        for path in (Path(snapshot.sequence.source_path), Path(config.checkpoint_path)):
            scenario.identify(path)
            report.data["inputs"].append(report.data["input"])
        report.data["input"] = report.data["inputs"][0]
        report.data["backend"] = {key: str(value) for key, value in asdict(config).items()}
        window.slider_frame.setValue(193)
        window.cmb_preview_source.setCurrentIndex(1)
        aligned.setChecked(True)
        panel.sp_run_end_frame.setValue(196)
        panel.cmb_edge_backend.setCurrentIndex(0)
        panel.sp_dexined_threshold.setValue(.35)
        panel.sp_edge_components.setValue(1)
        panel.cmb_inference_resolution.setCurrentIndex(1)

    with report.stage("place_visible_edge_roi") as stage:
        registration = snapshot.registration_results.get_result(193)
        assert registration is not None
        dx, dy = registration.shift_xy
        sx, sy = snapshot.sequence.metadata.get_pixel_size_nm()
        assert sx is not None and sy is not None
        panel.btn_draw.setChecked(True)
        view = window.viewer.viewer.plot_item.getViewBox()
        for x,y in [(32.,50.), (232.,50.), (232.,230.), (32.,230.)]:
            scene = view.mapViewToScene(QPointF((x+dx)*sx, (y+dy)*sy))
            pixel = window.viewer.viewer.glw.mapFromScene(scene)
            click(window.viewer.viewer.glw.viewport(), Qt.MouseButton.LeftButton, pos=pixel)
        panel.btn_finish.click()
        polygon = window.current_draft_polygon_roi()
        assert polygon is not None
        stage.update(polygon_source=polygon.as_array().tolist(), input_description=panel.lbl_input.text())
        show_description(panel.lbl_input)
        scenario.capture("01-input-aligned")

    with report.stage("real_DexiNed_preview"):
        panel.btn_preview.click()
        complete(panel.btn_preview)
        dialogs = window.findChildren(EdgePreviewDialog)
        assert dialogs and dialogs[0].isVisible()
        assert dialogs[0].grab().save(str(report.directory / "02-preview.png"))
        report.data["artifacts"].append("02-preview.png")
        dialogs[0].close()

    with report.stage("real_DexiNed_three_frames") as stage:
        panel.btn_run_sequence.click()
        complete(panel.btn_run_sequence)
        track = window.current_edge_tracks()[-1]
        assert track.frame_indices == [193,194,195]
        for index in track.frame_indices:
            annotation = track.get_annotation(index)
            assert annotation is not None and annotation.polyline is not None
            assert annotation.metrics.length_px is not None and annotation.metrics.length_px > 0
            assert annotation.shape_provenance is not None
            assert annotation.shape_provenance.source_view == "bm3d+registration"
        stage["track_id"] = track.edge_track_id
        saved = deepcopy(track)

    with report.stage("switch_original_aligned_expanded_and_save_open"):
        for name in ("original", "aligned", "expanded"):
            window.cmb_preview_source.setCurrentIndex(0 if name=="original" else 1)
            aligned.setChecked(name=="aligned")
            expanded.setChecked(name=="expanded")
            for index in (193,195):
                window.slider_frame.setValue(index)
                assert_same(saved, window.current_edge_tracks()[-1], "view_keeps_analysis")
                show_description(window.edge_track_list_panel.lbl_analysis)
                scenario.capture(f"result-{name}-frame-{index+1}")
        path = report.directory / "MOVIE_2-DexiNed-aligned.nanotrack"
        window.save_session_to_path(str(path))
        window.load_session_from_path(str(path))
        assert_same(saved, window.current_edge_tracks()[-1], "save_open_keeps_analysis")
        report.data["artifacts"].append(path.name)

    with report.stage("resume_from_195_in_Expanded") as stage:
        window.slider_frame.setValue(194)
        panel.btn_load_edge.click()
        panel.btn_resume_edge.click()
        complete(panel.btn_resume_edge)
        track = window.current_edge_tracks()[-1]
        assert_same(saved.get_annotation(193), track.get_annotation(193), "resume_keeps_prefix")
        annotation = track.get_annotation(195)
        assert annotation is not None and annotation.polyline is not None and annotation.shape_provenance is not None
        assert annotation.shape_provenance.source_view == "bm3d+expanded_registration"
        stage["metrics_frame_196"] = asdict(annotation.metrics)
        stage["shape_frame_196"] = asdict(annotation.shape_provenance)
        window.slider_frame.setValue(195)
        show_description(window.edge_track_list_panel.lbl_analysis)
        scenario.capture("resumed-expanded-frame-196")
        saved = deepcopy(track)
        path = report.directory / "MOVIE_2-DexiNed-resumed-expanded.nanotrack"
        window.save_session_to_path(str(path))
        window.load_session_from_path(str(path))
        assert_same(saved, window.current_edge_tracks()[-1], "resumed_save_open")
        report.data["artifacts"].append(path.name)

    with report.stage("cancel_real_detection_preserves_tracks"):
        before = deepcopy(window.current_edge_tracks())
        panel.btn_redetect_edge.click()
        wait(100)
        modal = QApplication.activeModalWidget()
        assert isinstance(modal, QProgressDialog)
        cancel = next(button for button in modal.findChildren(QPushButton) if button.text()=="Cancel")
        cancel.click()
        complete(panel.btn_redetect_edge, 15.)
        assert_same(before, window.current_edge_tracks(), "cancel_keeps_tracks")
        scenario.capture("cancel-preserved-results")
