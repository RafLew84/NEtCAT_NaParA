"""Real SAM2 acceptance on a prepared MOVIE_2 session, through visible Qt controls."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import time
from typing import TYPE_CHECKING, Callable, cast

import numpy as np
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtTest import QTest

from nanotrack.mask_trackers import MaskTrackerKind, default_mask_tracker_config
from scripts.nanotrack_acceptance.scenarios import assert_same

if TYPE_CHECKING:
    from scripts.nanotrack_acceptance.scenarios import Scenarios


def run(scenario: Scenarios, session: Path) -> None:
    window, report = scenario.window, scenario.report
    aligned = window.action_show_aligned_registration
    expanded = window.action_show_expanded_aligned_registration
    assert aligned is not None and expanded is not None
    wait = cast(Callable[[int], None], QTest.qWait)
    click = cast(Callable[..., None], QTest.mouseClick)
    with report.stage("open_prepared_MOVIE_2"):
        scenario.identify(session)
        report.data["inputs"] = [report.data["input"]]
        window.load_session_from_path(str(session))
        snapshot = window.current_session_snapshot()
        assert snapshot is not None and snapshot.sequence.frame_count == 196
        assert snapshot.denoised_frames is not None and snapshot.registration_results is not None
        scenario.identify(Path(snapshot.sequence.source_path))
        report.data["inputs"].append(report.data["input"])
        config = default_mask_tracker_config(MaskTrackerKind.SAM2)
        scenario.identify(Path(config.checkpoint_path))
        report.data["inputs"].append(report.data["input"])
        report.data["input"] = report.data["inputs"][0]
        report.data["backend"] = {key: str(value) for key, value in asdict(config).items()}
        window.slider_frame.setValue(9)
        window.cmb_preview_source.setCurrentIndex(1)
        window.track_list_panel.set_mask_tracker_kind(MaskTrackerKind.SAM2)
        window.track_list_panel.set_run_frame_limit(3)
        window.bbox_tools_panel.sp_width.setValue(14)
        window.bbox_tools_panel.sp_height.setValue(12)

    for mode in ("aligned", "expanded"):
        with report.stage(f"{mode}_place_visible_particle") as stage:
            aligned.setChecked(mode == "aligned")
            expanded.setChecked(mode == "expanded")
            # Same canonical particle for both executions. Geometry is read only;
            # placement uses the same mouse controls as a human operator.
            current = window.current_session_snapshot()
            assert current is not None and current.registration_results is not None
            registration = current.registration_results.get_result(9)
            assert registration is not None
            dx, dy = registration.shift_xy
            if mode == "expanded":
                shifts = [result.shift_xy for result in current.registration_results.results_by_frame.values()]
                dx -= np.floor(min(shift[0] for shift in shifts))
                dy -= np.floor(min(shift[1] for shift in shifts))
            sx, sy = current.sequence.metadata.get_pixel_size_nm()
            assert sx is not None and sy is not None
            source_center = (69., 66.)
            window.bbox_tools_panel.btn_place.setChecked(True)
            view = window.viewer.viewer.plot_item.getViewBox()
            point = view.mapViewToScene(QPointF((source_center[0]+dx)*sx, (source_center[1]+dy)*sy))
            pixel = window.viewer.viewer.glw.mapFromScene(point)
            click(window.viewer.viewer.glw.viewport(), Qt.MouseButton.LeftButton, pos=pixel)
            scenario.check_dialogs()
            draft = window.current_draft_bbox()
            assert draft is not None
            stage["seed_bbox_source"] = draft.as_tuple()
            window.bbox_tools_panel.btn_add_seed.click()
            stage["input_description"] = window.track_list_panel.lbl_input.text()
            window.sidebar_scroll_area.ensureWidgetVisible(window.track_list_panel.lbl_input, 0, 8)
            window.sidebar_scroll_area.horizontalScrollBar().setValue(0)
            wait(20)
            scenario.capture(f"{mode}-01-input")

        with report.stage(f"{mode}_real_SAM2_three_frames") as stage:
            window.track_list_panel.btn_run_selected.click()
            deadline = time.monotonic() + 150
            while not window.track_list_panel.btn_run_selected.isEnabled():
                wait(100)
                scenario.check_dialogs()
                if time.monotonic() >= deadline:
                    from PyQt6.QtWidgets import QApplication, QProgressDialog
                    modal = QApplication.activeModalWidget()
                    if isinstance(modal, QProgressDialog):
                        modal.canceled.emit()
                    raise TimeoutError("SAM2 acceptance exceeded 150 s")
            wait(100)
            scenario.check_dialogs()
            tracks = window.current_tracks()
            track = tracks[-1]
            assert track.frame_indices == [9, 10, 11]
            stage["frames"] = {}
            for index in (9, 10, 11):
                annotation = track.get_annotation(index)
                assert annotation is not None and annotation.mask is not None and annotation.mask.any()
                assert annotation.shape_provenance is not None
                assert annotation.measurement_provenance is not None
                assert annotation.measurement_provenance.source_view == "raw"
                assert annotation.metrics.valid_sample_count is not None and annotation.metrics.valid_sample_count > 0
                # Independent raw measurement check, without calling the metrics implementation.
                raw_values = snapshot.sequence.get_frame(index)[annotation.mask]
                assert np.isfinite(raw_values).all()
                assert annotation.metrics.intensity_sum is not None
                np.testing.assert_allclose(annotation.metrics.intensity_sum, raw_values.sum(), rtol=0, atol=1e-12)
                stage["frames"][str(index+1)] = {
                    "metrics": asdict(annotation.metrics), "shape": asdict(annotation.shape_provenance),
                    "measurement": asdict(annotation.measurement_provenance),
                }
            saved = deepcopy(track)
            stage["track_id"] = track.track_id

        with report.stage(f"{mode}_switch_views_and_save_open"):
            for name in ("original", "aligned", "expanded"):
                window.cmb_preview_source.setCurrentIndex(0 if name == "original" else 1)
                aligned.setChecked(name == "aligned")
                expanded.setChecked(name == "expanded")
                for index in (9, 11):
                    window.slider_frame.setValue(index)
                    assert_same(saved, window.current_tracks()[-1], "track_after_view_change")
                    scenario.capture(f"{mode}-result-{name}-frame-{index+1}")
            path = report.directory / f"MOVIE_2-SAM2-{mode}.nanotrack"
            window.save_session_to_path(str(path))
            window.load_session_from_path(str(path))
            assert_same(saved, window.current_tracks()[-1], "track_after_open")
            assert "raw (Oryginał)" in window.track_list_panel.lbl_analysis.text()
            report.data["artifacts"].append(path.name)
            scenario.capture(f"{mode}-reopened")
            window.slider_frame.setValue(9)

    with report.stage("cancel_real_start_preserves_saved_tracks"):
        from PyQt6.QtWidgets import QApplication, QPushButton, QProgressDialog
        before_cancel = deepcopy(window.current_tracks())
        window.track_list_panel.btn_run_selected.click()
        wait(100)
        modal = QApplication.activeModalWidget()
        assert isinstance(modal, QProgressDialog)
        cancel = next(button for button in modal.findChildren(QPushButton) if button.text() == "Cancel")
        click(cancel, Qt.MouseButton.LeftButton)
        deadline = time.monotonic() + 15
        while not window.track_list_panel.btn_run_selected.isEnabled() and time.monotonic() < deadline:
            wait(100)
            scenario.check_dialogs()
        assert window.track_list_panel.btn_run_selected.isEnabled()
        assert_same(before_cancel, window.current_tracks(), "tracks_after_cancel")
        scenario.capture("cancel-preserved-results")

    (report.directory / "particle-results.json").write_text(
        json.dumps(report.data["stages"], ensure_ascii=False, indent=2), encoding="utf-8",
    )
    report.data["artifacts"].append("particle-results.json")
