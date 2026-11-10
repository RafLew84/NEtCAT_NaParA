"""Analysis uses raw inputs and publishes memberships with the correct frame."""

import pytest
from threading import Event

from PyQt6.QtCore import QRunnable, QThreadPool

from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.core.frame_presentation import FramePresenter
from stmdomains.io.moltrack_import import prepare_import
from stmdomains.tools.browsing_demo import create_browsing_demo
from stmdomains.tools.analysis_demo import create_analysis_demo
from stmdomains.ui.session_controller import SessionController


class Prompts:
    def __init__(self):
        self.errors = []

    def choose_session(self):
        return None

    def choose_source(self, message, suggested):
        raise AssertionError(message)

    def confirm_source(self, path, reasons):
        return True

    def show_error(self, message):
        self.errors.append(message)


@pytest.fixture
def controller(qtbot):
    session = SessionController(Prompts())
    yield session
    session.shutdown()
    qtbot.waitUntil(lambda: session.pending_task_count == 0)


def test_analysis_input_and_result_are_bound_to_raw_working_frame(tmp_path):
    path = create_browsing_demo(tmp_path)["series"]
    presenter = FramePresenter(prepare_import(path).series)
    data = presenter.analysis_input(0)
    result = FrameAnalysis(data.series_id, 0, data.frame.source_index, "insufficient_data")
    for mode in ("raw", "expanded_aligned"):
        view = presenter.present(0, mode, 1.8, result=result)
        assert view.result is result
        assert view.annotations.detections[0].detection_id == data.annotations.detections[0].detection_id
    assert presenter.present(1).result is None
    with pytest.raises(ValueError, match="klatki"):
        presenter.present(1, result=result)


def test_analysis_published_on_its_frame_and_cleared_for_another_series(qtbot, controller, tmp_path):
    path = create_browsing_demo(tmp_path)["series"]
    views = []
    controller.frame_changed.connect(views.append)
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.show_frame(3)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert views[-1].result is None
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy)
    result = views[-1].result
    assert result.status == "no_annotations"
    assert result.working_index == 3
    controller.show_frame(1)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert views[-1].result is None
    controller.show_frame(3)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert views[-1].result is result
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert views[-1].result is None
    assert controller.result is None
    assert not controller.prompts.errors


@pytest.mark.parametrize("action", ["cancel", "navigate", "new_series", "gamma", "mode"])
def test_pending_analysis_respects_navigation_cancel_and_display(qtbot, qapp, controller, tmp_path, action):
    path = create_browsing_demo(tmp_path)["series"]
    views = []
    controller.frame_changed.connect(views.append)
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.show_frame(3)
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy and controller.pending_task_count == 0)
    previous = controller.result
    release = Event()

    class Gate(QRunnable):
        def __init__(self):
            super().__init__()
            self.entered = Event()

        def run(self):
            self.entered.set()
            release.wait(5)

    gates = []
    for pool in qapp.findChildren(QThreadPool):
        for _ in range(pool.maxThreadCount()):
            gate = Gate()
            gates.append(gate)
            pool.start(gate)
    try:
        qtbot.waitUntil(lambda: all(gate.entered.is_set() for gate in gates))
        controller.analyze_current_frame()
        assert controller.is_busy and not controller.can_analyze and not controller.can_play
        if action == "cancel":
            controller.cancel()
        elif action == "navigate":
            controller.show_frame(1)
        elif action == "new_series":
            controller.open_session(path)
        elif action == "gamma":
            controller.set_gamma(1.8)
        else:
            controller.set_view_mode("expanded_aligned")
    finally:
        release.set()
    qtbot.waitUntil(lambda: not controller.is_busy and controller.pending_task_count == 0)
    if action == "cancel":
        assert controller.result is previous and views[-1].result is previous
    elif action in ("navigate", "new_series"):
        assert controller.result is None and views[-1].result is None
        if action == "navigate":
            controller.show_frame(3)
            qtbot.waitUntil(lambda: not controller.is_busy)
            assert controller.result is previous
    else:
        assert views[-1].result is controller.result and controller.result is not previous
        assert controller.result.working_index == 3
        assert views[-1].gamma == (1.8 if action == "gamma" else 1.)
        assert views[-1].mode == ("expanded_aligned" if action == "mode" else "raw")
    assert not controller.prompts.errors


def test_numerical_failure_preserves_last_completed_result(qtbot, controller, tmp_path, monkeypatch):
    from sklearn.decomposition import PCA

    path = create_analysis_demo(tmp_path)["single"]
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    previous = controller.result
    assert previous.status == "complete" and previous.domain_count > 0

    def unavailable_numerical_backend(*args, **kwargs):
        raise RuntimeError("Numerical backend unavailable")

    # Failure at the external numerical library boundary; the analysis pipeline remains real.
    monkeypatch.setattr(PCA, "fit", unavailable_numerical_backend)
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert controller.result is previous
    assert "Numerical backend unavailable" in controller.prompts.errors[-1]


def test_display_failure_does_not_hide_a_completed_analysis(qtbot, controller, tmp_path, monkeypatch):
    import numpy as np

    path = create_browsing_demo(tmp_path)["series"]
    views = []
    controller.frame_changed.connect(views.append)
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.show_frame(3)
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy and controller.pending_task_count == 0)
    previous = controller.result
    entered, release = Event(), Event()

    def unavailable_display_backend(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        raise RuntimeError("Display backend unavailable")

    monkeypatch.setattr(np, "rint", unavailable_display_backend)
    changed = []

    def change_gamma_while_analysis_is_pending(busy, text):
        if busy and text == "Analiza klatki…" and not changed:
            changed.append(True)
            controller.set_gamma(1.8)

    controller.busy_changed.connect(change_gamma_while_analysis_is_pending)
    try:
        controller.analyze_current_frame()
        qtbot.waitUntil(lambda: entered.is_set() and controller.result is not previous)
    finally:
        release.set()
    qtbot.waitUntil(lambda: not controller.is_busy and controller.pending_task_count == 0)
    assert controller.gamma == views[-1].gamma == 1.
    assert views[-1].result is controller.result
    assert "Display backend unavailable" in controller.prompts.errors[-1]
