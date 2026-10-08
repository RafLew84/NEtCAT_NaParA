"""Visible Save/Cancel/overwrite acceptance; faults touch only this run's copies."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import os
from pathlib import Path
import shutil
import time
from typing import TYPE_CHECKING, Callable, cast
from unittest.mock import patch

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox, QProgressDialog, QPushButton

from scripts.nanotrack_acceptance.scenarios import assert_same

if TYPE_CHECKING:
    from scripts.nanotrack_acceptance.scenarios import Scenarios


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(scenario: Scenarios, session: Path) -> None:
    window, report = scenario.window, scenario.report
    wait = cast(Callable[[int], None], QTest.qWait)
    click = cast(Callable[..., None], QTest.mouseClick)
    directory = report.directory / "Odbiór zapisu — sesje"
    directory.mkdir()
    target = directory / "MOVIE_2-zapis-ą.nanotrack"

    def save_case(name: str, path: Path, *, cancel: str = "", decline: bool = False,
                  collision: bool = False) -> dict:
        with report.stage(name) as stage:
            ticks: list[float] = []
            labels: list[str] = []
            errors: list[str] = []
            callback_errors: list[str] = []
            cancelled = False
            original_rename = os.rename

            def rename(source, destination, *args, **kwargs):
                if collision and Path(destination) == path:
                    # The old file has been reserved by Windows. Simulate a
                    # competing writer claiming the vacant name at publication.
                    shutil.copyfile(session, path)
                return original_rename(source, destination, *args, **kwargs)

            def capture(widget, suffix: str) -> None:
                name_png = f"{name}-{suffix}.png"
                assert widget.grab().save(str(report.directory / name_png))
                report.data["artifacts"].append(name_png)

            def monitor() -> None:
                nonlocal cancelled
                ticks.append(time.monotonic())
                try:
                    modal = QApplication.activeModalWidget()
                    if isinstance(modal, QMessageBox):
                        if modal.standardButtons() & QMessageBox.StandardButton.Yes:
                            capture(modal, "overwrite")
                            button = modal.button(QMessageBox.StandardButton.No if decline else QMessageBox.StandardButton.Yes)
                        else:
                            errors.append(modal.text())
                            capture(modal, "error")
                            button = modal.button(QMessageBox.StandardButton.Ok)
                        assert button is not None
                        click(button, Qt.MouseButton.LeftButton)
                    elif isinstance(modal, QProgressDialog):
                        label = modal.labelText()
                        phase = label.split("…")[0]
                        if not labels or labels[-1] != phase:
                            labels.append(phase)
                            capture(modal, f"phase-{len(labels)}")
                        if cancel and label.startswith(cancel) and 0 < modal.value() < 100 and not cancelled:
                            capture(window, "window-before-cancel")
                            button = next(b for b in modal.findChildren(QPushButton) if b.text() == "Anuluj")
                            cancelled = True
                            click(button, Qt.MouseButton.LeftButton)
                except Exception as exc:
                    callback_errors.append(str(exc))
                    timer.stop()

            timer = QTimer()
            timer.timeout.connect(monitor)
            timer.start(10)
            started = time.monotonic()
            try:
                with patch.object(os, "rename", rename):
                    window.start_session_save(str(path))
                    assert not window.action_save_session.isEnabled()
                    assert not window.action_open_session.isEnabled()
                    assert not window.spin_frame.isEnabled()
                    while not window.action_save_session.isEnabled():
                        wait(10)
                        assert not callback_errors, callback_errors
                        if time.monotonic() - started > 90:
                            raise TimeoutError(f"Save did not complete: {name}")
                    wait(30)
            finally:
                timer.stop()
            status = window.statusBar()
            assert status is not None
            message = status.currentMessage()
            stage.update(heartbeat_ticks=len(ticks), phases=labels, cancelled=cancelled,
                         errors=errors, message=message, duration_seconds=time.monotonic()-started)
            assert ticks and not callback_errors
            if cancel or decline:
                assert "anulowan" in message.lower() and not errors
                assert not cancel or cancelled
            elif collision:
                assert len(errors) == 1 and "Poprzednia sesja jest zachowana" in errors[0]
                assert "Zapisano" not in message
            else:
                assert "Zapisano" in message and not errors
            return stage

    with report.stage("open_prepared_MOVIE_2_and_choose_working_settings"):
        window.load_session_from_path(str(session))
        initial = window.current_session_snapshot()
        assert initial is not None and initial.sequence.frame_count == 196
        assert initial.denoised_frames is not None and initial.repair_frames is not None
        assert initial.registration_results is not None and initial.tracks and initial.edge_tracks
        report.data["inputs"] = []
        for path in (session, Path(initial.sequence.source_path)):
            scenario.identify(path)
            report.data["inputs"].append(report.data["input"])
        assert window.action_show_expanded_aligned_registration is not None
        window.action_show_expanded_aligned_registration.setChecked(True)
        window.spin_frame.setValue(10)
        window.viewer.viewer.slider_gamma.setValue(135)
        window.viewer.viewer.hist.setLevels(-.2, 1.2)
        window.track_list_panel.sp_run_frame_limit.setValue(3)
        window.polygon_tools_panel.sp_run_end_frame.setValue(11)
        assert window.action_open_results is not None and window.action_open_edge_results is not None
        window.action_open_results.trigger()
        results = window.current_results_dialog()
        assert results is not None
        results.cmb_units.setCurrentIndex(1)
        results.chk_exclude_boundary_pixels.setChecked(True)
        results.spn_boundary_pixel_weight.setValue(.2)
        results.close()
        window.action_open_edge_results.trigger()
        edges = window.current_edge_results_dialog()
        assert edges is not None
        edges.cmb_units.setCurrentIndex(1)
        edges.cmb_trend.setCurrentIndex(2)
        edges.close()
        baseline = deepcopy(window.current_session_snapshot())
        assert baseline is not None
        report.data["working_settings"] = baseline.tool_settings
        scenario.capture("01-initial-expanded-processed")

    save_case("save_unicode_path", target)
    with report.stage("open_saved_session_exact_values_and_settings"):
        window.load_session_from_path(str(target))
        assert_same(baseline, window.current_session_snapshot())
        for action, dialog, name_png in (
            (window.action_open_results, window.current_results_dialog(), "04-results-settings.png"),
            (window.action_open_edge_results, window.current_edge_results_dialog(), "05-edge-results-settings.png"),
        ):
            assert dialog is not None and action is not None
            action.trigger()
            wait(50)
            assert dialog.grab().save(str(report.directory / name_png))
            report.data["artifacts"].append(name_png)
            dialog.close()
        scenario.capture("02-reopened-expanded-processed")
        previous_hash = digest(target)
        report.data["saved_sha256"] = previous_hash
        report.data["artifacts"].append(str(target.relative_to(report.directory)))
        window.spin_frame.setValue(11)
        window.cmb_preview_source.setCurrentIndex(0)
        working = deepcopy(window.current_session_snapshot())

    for name, phase in (("cancel_writing", "Zapisywanie"), ("cancel_verifying", "Weryfikacja")):
        save_case(name, target, cancel=phase)
        assert digest(target) == previous_hash
        assert_same(working, window.current_session_snapshot())
    save_case("refuse_overwrite", target, decline=True)
    assert digest(target) == previous_hash
    assert_same(working, window.current_session_snapshot())

    fault_target = directory / "kopie do kolizji.nanotrack"
    shutil.copyfile(target, fault_target)
    save_case("collision_at_publication_preserves_both_sessions", fault_target, collision=True)
    assert digest(fault_target) == digest(session)
    assert_same(working, window.current_session_snapshot())
    recovery = next(directory.glob(f".{fault_target.name}.recovery-*/previous.nanotrack"))
    assert digest(recovery) == previous_hash
    report.data["artifacts"].append(str(recovery.relative_to(report.directory)))
    report.data["recovery_path"] = str(recovery)

    final = directory / "MOVIE_2-ponowny zapis po błędzie.nanotrack"
    save_case("retry_after_failure_new_name", final)
    with report.stage("open_final_and_recovery_sessions"):
        window.load_session_from_path(str(recovery))
        assert_same(baseline, window.current_session_snapshot())
        window.load_session_from_path(str(final))
        assert_same(working, window.current_session_snapshot())
        assert not list(directory.glob("*.tmp"))
        scenario.capture("03-final-frame-11-raw")
        report.data["artifacts"].append(str(final.relative_to(report.directory)))
        report.data["final_sha256"] = digest(final)
