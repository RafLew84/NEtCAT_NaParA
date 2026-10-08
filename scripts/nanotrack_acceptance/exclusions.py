"""Registration-only exclusions with real SAM2, DexiNed and Phase in visible Qt."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
import time
from typing import TYPE_CHECKING, Callable, cast

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QAbstractItemView, QPushButton

from nanotrack.edges import DexiNedBackendConfig
from nanotrack.mask_trackers import MaskTrackerKind, default_mask_tracker_config
from nanotrack.ui.dialogs.registration_results_dialog import RegistrationResultsDialog
from scripts.nanotrack_acceptance.scenarios import assert_same

if TYPE_CHECKING:
    from scripts.nanotrack_acceptance.scenarios import Scenarios


def run(scenario: Scenarios, session: Path) -> None:
    window, report = scenario.window, scenario.report
    panel = window.polygon_tools_panel
    wait = cast(Callable[[int], None], QTest.qWait)
    click = cast(Callable[..., None], QTest.mouseClick)

    def complete(button: QPushButton) -> None:
        deadline = time.monotonic() + 150
        while not button.isEnabled():
            wait(100)
            scenario.check_dialogs()
            if time.monotonic() > deadline:
                raise TimeoutError("Model operation exceeded 150 seconds")
        wait(100)
        scenario.check_dialogs()

    def click_source(x: float, y: float) -> None:
        point = view.mapViewToScene(QPointF((x+dx)*scale_x, (y+dy)*scale_y))
        pixel = window.viewer.viewer.glw.mapFromScene(point)
        click(window.viewer.viewer.glw.viewport(), Qt.MouseButton.LeftButton, pos=pixel)

    with report.stage("open_prepared_MOVIE_2_and_identify_models"):
        window.load_session_from_path(str(session))
        initial = window.current_session_snapshot()
        assert initial is not None and initial.registration_results is not None
        assert initial.sequence.frame_count == 196 and initial.denoised_frames is not None
        sam = default_mask_tracker_config(MaskTrackerKind.SAM2)
        dex = DexiNedBackendConfig()
        report.data["backends"] = [{key: str(value) for key, value in asdict(config).items()} for config in (sam, dex)]
        report.data["inputs"] = []
        for path in (session, Path(initial.sequence.source_path), Path(sam.checkpoint_path), Path(dex.checkpoint_path)):
            scenario.identify(path)
            report.data["inputs"].append(report.data["input"])
        report.data["input"] = report.data["inputs"][0]
        window.spin_frame.setValue(9)
        window.cmb_preview_source.setCurrentIndex(1)
        assert window.action_show_aligned_registration is not None
        window.action_show_aligned_registration.setChecked(True)
        window.track_list_panel.set_mask_tracker_kind(MaskTrackerKind.SAM2)
        window.track_list_panel.set_run_frame_limit(3)
        panel.sp_run_end_frame.setValue(11)
        panel.cmb_edge_backend.setCurrentIndex(0)
        panel.cmb_inference_resolution.setCurrentIndex(1)

    with report.stage("place_particle_and_edge_ROI_on_frame_9") as stage:
        result = initial.registration_results.get_result(8)
        assert result is not None
        dx, dy = result.shift_xy
        sx, sy = initial.sequence.metadata.get_pixel_size_nm()
        assert sx is not None and sy is not None
        scale_x, scale_y = float(sx), float(sy)
        view = window.viewer.viewer.plot_item.getViewBox()
        window.bbox_tools_panel.sp_width.setValue(14)
        window.bbox_tools_panel.sp_height.setValue(12)
        window.bbox_tools_panel.btn_place.setChecked(True)
        click_source(69., 66.)
        draft = window.current_draft_bbox()
        assert draft is not None
        stage["particle_bbox_source"] = draft.as_tuple()
        window.bbox_tools_panel.btn_add_seed.click()
        panel.btn_draw.setChecked(True)
        for x, y in ((32.,50.), (232.,50.), (232.,230.), (32.,230.)):
            click_source(x, y)
        panel.btn_finish.click()
        polygon = window.current_draft_polygon_roi()
        assert polygon is not None
        stage["polygon_source"] = polygon.as_array().tolist()
        scenario.capture("01-input-frame-9")

    for label in ("before_exclusion", "with_hidden_frame_10"):
        with report.stage(f"{label}_real_SAM2_9_to_11"):
            window.track_list_panel.btn_run_selected.click()
            complete(window.track_list_panel.btn_run_selected)
            particle = window.current_tracks()[-1]
            assert particle.frame_indices == [8,9,10]
            annotation = particle.get_annotation(9)
            assert annotation is not None and annotation.mask is not None and annotation.mask.any()
            assert annotation.metrics.valid_sample_count is not None and annotation.metrics.valid_sample_count > 0
        with report.stage(f"{label}_real_DexiNed_9_to_11") as stage:
            # Navigation can reset the existing End control; select the range
            # immediately before each run, as in the manual acceptance steps.
            panel.sp_run_end_frame.setValue(11)
            stage["frame_range"] = [window.spin_frame.value(), panel.sp_run_end_frame.value()]
            assert stage["frame_range"] == [9, 11]
            panel.btn_run_sequence.click()
            complete(panel.btn_run_sequence)
            edge = window.current_edge_tracks()[-1]
            assert edge.frame_indices == [8,9,10]
            for index in (8,9,10):
                edge_annotation = edge.get_annotation(index)
                assert edge_annotation is not None and edge_annotation.polyline is not None
                assert edge_annotation.metrics.length_px is not None and edge_annotation.metrics.length_px > 0

        if label == "before_exclusion":
            with report.stage("exclude_frame_10_preserve_results_and_hide_navigation") as stage:
                window.spin_frame.setValue(10)
                before = deepcopy(window.current_session_snapshot())
                assert before is not None
                window.chk_exclude_frame.setChecked(True)
                after = window.current_session_snapshot()
                assert after is not None
                for field in ("tracks", "edge_tracks", "registration_results", "draft_polygons_by_frame"):
                    assert_same(getattr(before, field), getattr(after, field), field)
                assert window.chk_exclude_frame.text() == "Wyklucz z rejestracji"
                scenario.capture("02-excluded-frame-10-with-results")
                window.chk_hide_excluded_frames.setChecked(True)
                assert window.spin_frame.value() == 9
                window.btn_next.click()
                assert window.spin_frame.value() == 11
                window.btn_prev.click()
                assert window.spin_frame.value() == 9
                stage["navigation_frame_numbers"] = [9,11,9]
                scenario.capture("03-hidden-frame-10-navigation")

    with report.stage("real_Phase_skips_10_and_retains_its_own_shift") as stage:
        before_batch = deepcopy(window.current_session_snapshot())
        assert before_batch is not None and before_batch.registration_results is not None
        old = before_batch.registration_results.get_result(9)
        assert old is not None
        window.cmb_registration_backend.setCurrentIndex(0)
        assert window.action_run_registration is not None
        window.action_run_registration.trigger()
        scenario.check_dialogs()
        after_batch = window.current_session_snapshot()
        assert after_batch is not None and after_batch.registration_results is not None
        retained = after_batch.registration_results.get_result(9)
        assert_same(replace(old, recomputed=False), retained, "retained_frame_10")
        assert_same(before_batch.tracks, after_batch.tracks, "particle_results_after_registration")
        assert_same(before_batch.edge_tracks, after_batch.edge_tracks, "edge_results_after_registration")
        stage["retained_frame_10"] = asdict(retained) if retained is not None else None
        stage["registration_backend"] = after_batch.registration_results.settings.backend
        assert window.action_open_registration_results is not None
        window.action_open_registration_results.trigger()
        dialogs = window.findChildren(RegistrationResultsDialog)
        assert dialogs and dialogs[0].isVisible()
        status_item = dialogs[0].table_results.item(9, 4)
        assert status_item is not None and "nieprzeliczony" in status_item.text()
        dialogs[0].table_results.selectRow(9)
        dialogs[0].table_results.scrollToItem(status_item, QAbstractItemView.ScrollHint.PositionAtCenter)
        wait(50)
        assert dialogs[0].grab().save(str(report.directory / "04-registration-results.png"))
        report.data["artifacts"].append("04-registration-results.png")
        dialogs[0].close()

    with report.stage("save_open_and_restore_without_reanalysis"):
        path = report.directory / "MOVIE_2-excluded-frame-10.nanotrack"
        window.save_session_to_path(str(path))
        window.load_session_from_path(str(path))
        restored = window.current_session_snapshot()
        assert restored is not None
        assert_same(after_batch, restored, "save_open")
        assert window.chk_hide_excluded_frames.isChecked()
        window.chk_hide_excluded_frames.setChecked(False)
        window.spin_frame.setValue(10)
        scenario.capture("05-reopened-excluded-frame-10")
        window.chk_exclude_frame.setChecked(False)
        final = window.current_session_snapshot()
        assert final is not None and not final.sequence.is_frame_excluded(9)
        for field in ("tracks", "edge_tracks", "registration_results"):
            assert_same(getattr(restored, field), getattr(final, field), field)
        path = report.directory / "MOVIE_2-restored-frame-10.nanotrack"
        window.save_session_to_path(str(path))
        report.data["artifacts"].extend(["MOVIE_2-excluded-frame-10.nanotrack", path.name])
        scenario.capture("06-restored-frame-10")
