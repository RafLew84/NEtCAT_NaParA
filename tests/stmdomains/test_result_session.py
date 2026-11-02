"""A published frame carries the result for its own series and working index."""

from pathlib import Path
from threading import Event
import gc
import weakref

import pytest

from stmdomains.core.domain_results import DomainResult, FrameResult, MoleculeAssignment, ResultClass
from stmdomains.core.frame_presentation import FramePresenter
from stmdomains.io.moltrack_import import prepare_import
from stmdomains.tools.browsing_demo import create_browsing_demo
from stmdomains.tools.result_demo import create_result_demo
from stmdomains.ui.session_controller import SessionController


class Prompts:
    def __init__(self):
        self.errors = []

    def choose_session(self):
        return None

    def choose_result(self):
        return None

    def choose_source(self, message, suggested):
        raise AssertionError(message)

    def confirm_source(self, path, reasons):
        return True

    def show_error(self, message):
        self.errors.append(message)


def test_presented_result_follows_frame_and_survives_display_changes(tmp_path):
    path = create_browsing_demo(tmp_path)["series"]
    series = prepare_import(path).series
    classes = (ResultClass("q", "#10b9bd"),)
    assignment = MoleculeAssignment("frame-1", 2, "q", "q", "domain", "")
    frame_result = FrameResult(True, {"frame-1": assignment}, classes)
    result = DomainResult(series.identity, tmp_path / "result.zip", {0: frame_result}, classes)
    presenter = FramePresenter(series, result=result)
    for mode, gamma in (("raw", 1), ("expanded_aligned", 2)):
        view = presenter.present(0, mode, gamma)
        assert view.result is frame_result
        assert view.annotations.detections[0].detection_id == "frame-1"
    assert not presenter.present(1).result.analyzed
    assert FramePresenter(series).present(0).result is None


def test_presenter_refuses_result_bound_to_another_series(tmp_path):
    path = create_browsing_demo(tmp_path)["series"]
    series = prepare_import(path).series
    result = DomainResult("another-series", tmp_path / "result.zip", {}, ())
    with pytest.raises(ValueError, match="serii"):
        FramePresenter(series, result=result)


def test_result_import_preserves_frame_and_resets_on_new_series(qtbot, tmp_path):
    paths = create_result_demo(tmp_path)
    prompts = Prompts()
    controller = SessionController(prompts)
    views = []
    controller.frame_changed.connect(views.append)
    try:
        controller.open_session(paths["session"])
        qtbot.waitUntil(lambda: not controller.is_busy)
        controller.show_frame(2)
        qtbot.waitUntil(lambda: not controller.is_busy)
        controller.open_result(paths["manifest"])
        qtbot.waitUntil(lambda: not controller.is_busy)
        assert controller.current_index == 2
        assert views[-1].result.analyzed and views[-1].result.domain_count == 0
        controller.show_frame(0)
        qtbot.waitUntil(lambda: not controller.is_busy)
        assert views[-1].result.domain_count == 2
        controller.show_frame(1)
        qtbot.waitUntil(lambda: not controller.is_busy)
        assert not views[-1].result.analyzed
        controller.open_session(paths["session"])
        qtbot.waitUntil(lambda: not controller.is_busy)
        assert views[-1].result is None
        assert not prompts.errors
    finally:
        controller.shutdown()
        qtbot.waitUntil(lambda: controller.pending_task_count == 0)


@pytest.mark.parametrize("action", ["cancel", "new_series", "navigate"])
def test_late_result_respects_cancel_series_and_latest_frame(qtbot, tmp_path, monkeypatch, action):
    paths = create_result_demo(tmp_path)
    prompts = Prompts()
    controller = SessionController(prompts)
    controller.open_session(paths["session"])
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.open_result(paths["manifest"])
    qtbot.waitUntil(lambda: not controller.is_busy)
    previous = controller.result
    controller.open_result(tmp_path / "missing.zip")
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert prompts.errors and controller.result is previous
    entered, release = Event(), Event()
    open_file = Path.open
    metadata = paths["manifest"].parent / "work/expanded/metadata.json"

    def delayed_read(path, *args, **kwargs):
        if path == metadata:
            entered.set()
            assert release.wait(5)
        return open_file(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", delayed_read)
    try:
        controller.open_result(paths["manifest"])
        qtbot.waitUntil(entered.is_set)
        if action == "cancel":
            controller.cancel()
        elif action == "new_series":
            controller.open_session(paths["session"])
            qtbot.waitUntil(lambda: not controller.is_busy)
        else:
            controller.show_frame(2)
            qtbot.waitUntil(lambda: controller.current_index == 2)
        release.set()
        qtbot.waitUntil(lambda: not controller.is_busy and controller.pending_task_count == 0)
        if action == "cancel":
            assert controller.result is previous
        elif action == "new_series":
            assert controller.result is None
        else:
            assert controller.result is not previous
            assert controller.current_index == 2
    finally:
        release.set()
        controller.shutdown()
        qtbot.waitUntil(lambda: controller.pending_task_count == 0)


def test_pause_of_pending_first_result_frame_does_not_commit_it_later(qtbot, tmp_path):
    paths = create_result_demo(tmp_path)
    controller = SessionController(Prompts())
    controller.open_session(paths["session"])
    qtbot.waitUntil(lambda: not controller.is_busy)
    paused = []

    def pause_when_frame_is_requested(busy, text):
        if busy and text.startswith("Przygotowanie klatki") and not paused:
            paused.append(True)
            controller.play()
            controller.pause()

    controller.busy_changed.connect(pause_when_frame_is_requested)
    try:
        controller.open_result(paths["manifest"])
        qtbot.waitUntil(lambda: bool(paused) and controller.pending_task_count == 0)
        assert controller.result is None
        controller.show_frame(2)
        qtbot.waitUntil(lambda: not controller.is_busy)
        assert controller.result is None
    finally:
        controller.shutdown()
        qtbot.waitUntil(lambda: controller.pending_task_count == 0)


def test_replacing_series_releases_previous_images_and_result(qtbot, tmp_path):
    paths = create_result_demo(tmp_path)
    controller = SessionController(Prompts())
    try:
        controller.open_session(paths["session"])
        qtbot.waitUntil(lambda: not controller.is_busy and controller.pending_task_count == 0)
        controller.open_result(paths["manifest"])
        qtbot.waitUntil(lambda: not controller.is_busy and controller.pending_task_count == 0)
        controller.show_frame(2)
        qtbot.waitUntil(lambda: not controller.is_busy and controller.pending_task_count == 0)
        previous_series, previous_result = weakref.ref(controller.series), weakref.ref(controller.result)
        controller.open_session(paths["session"])
        qtbot.waitUntil(lambda: not controller.is_busy and controller.pending_task_count == 0)
        gc.collect()
        assert previous_series() is None
        assert previous_result() is None
    finally:
        controller.shutdown()
        qtbot.waitUntil(lambda: controller.pending_task_count == 0)
