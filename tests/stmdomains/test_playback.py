"""Observe complete frame publications through the public session controller."""

from threading import Event
import json

import numpy as np
import pytest
from PyQt6.QtCore import QRunnable, QThreadPool

from stmdomains.tools.demo_inputs import write_mpp, write_session
from stmdomains.tools.annotation_demo import create_annotation_demo
from stmdomains.ui.session_controller import SessionController


class Prompts:
    def choose_session(self):
        return None

    def choose_source(self, message, suggested):
        raise AssertionError(message)

    def confirm_source(self, path, reasons):
        return True

    def show_error(self, message):
        raise AssertionError(message)


@pytest.fixture
def controller(qtbot):
    session = SessionController(Prompts())
    yield session
    session.shutdown()
    qtbot.waitUntil(lambda: session.pending_task_count == 0)


def open_sequence(qtbot, controller, tmp_path, count=4):
    images = np.arange(count * 24., dtype=float).reshape(count, 4, 6)
    source = write_mpp(tmp_path / "play.mpp", images)
    path = write_session(tmp_path / "play.json", source, list(reversed(range(count))))
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy)
    return path


def test_playback_publishes_every_frame_then_stops_and_restarts(qtbot, controller, tmp_path):
    open_sequence(qtbot, controller, tmp_path)
    shown = []
    controller.frame_changed.connect(lambda view: shown.append(
        (view.frame.working_index, view.frame.source_index)
    ))
    controller.set_playback_rate(20)
    controller.play()
    qtbot.waitUntil(lambda: not controller.is_playing)
    assert shown == [(1, 2), (2, 1), (3, 0)]
    assert controller.current_index == 3
    controller.play()
    qtbot.waitUntil(lambda: not controller.is_playing)
    assert shown[3:] == [(0, 3), (1, 2), (2, 1), (3, 0)]


def test_slow_worker_keeps_one_step_and_pause_discards_it(qtbot, qapp, controller, tmp_path):
    open_sequence(qtbot, controller, tmp_path)
    qtbot.waitUntil(lambda: controller.pending_task_count == 0)
    shown = []
    controller.frame_changed.connect(lambda view: shown.append(view.frame.working_index))
    # Occupy real Qt workers, controlling the scheduler rather than mocking rendering.
    release = Event()

    class WorkerGate(QRunnable):
        def __init__(self):
            super().__init__()
            self.entered = Event()

        def run(self):
            self.entered.set()
            release.wait(5)

    gates = []
    for pool in qapp.findChildren(QThreadPool):
        for _ in range(pool.maxThreadCount()):
            gate = WorkerGate()
            gates.append(gate)
            pool.start(gate)
    try:
        qtbot.waitUntil(lambda: all(gate.entered.is_set() for gate in gates))
        controller.set_playback_rate(20)
        controller.play()
        qtbot.waitUntil(lambda: controller.is_busy)
        qtbot.wait(180)  # Several playback intervals, still only one outstanding step.
        assert controller.current_index == 0
        assert controller.pending_task_count == 1
        controller.pause()
        assert not controller.is_playing
        assert not controller.is_busy
        # Play adopts an already requested frame; pause must discard it too.
        controller.show_frame(2)
        controller.play()
        controller.pause()
        assert not controller.is_busy
    finally:
        release.set()
    qtbot.waitUntil(lambda: controller.pending_task_count == 0)
    qtbot.wait(80)
    assert shown == []
    controller.play()
    qtbot.waitUntil(lambda: not controller.is_playing)
    assert shown == [1, 2, 3]


def test_single_frame_and_manual_navigation_stop_playback(qtbot, controller, tmp_path):
    open_sequence(qtbot, controller, tmp_path)
    controller.play()
    controller.show_frame(2)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert not controller.is_playing
    assert controller.current_index == 2
    controller.play()
    controller.open_session()  # Opening (and cancelling) the file picker pauses.
    assert not controller.is_playing
    assert controller.current_index == 2
    open_sequence(qtbot, controller, tmp_path, count=1)
    controller.play()
    controller.restart()
    assert not controller.is_playing
    assert not controller.is_busy
    assert controller.current_index == 0


@pytest.mark.parametrize("name, expected", [("registered", "expanded_aligned"), ("no_registration", "raw")])
def test_saved_view_restored_only_if_geometry_available(qtbot, controller, tmp_path, name, expected):
    path = create_annotation_demo(tmp_path)[name]
    payload = json.loads(path.read_text())
    payload["ui"] = {"registration_view_mode": "Show expanded aligned"}
    payload["working_series"]["active_frame_index"] = 1
    path.write_text(json.dumps(payload))
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.current_index == 1
    assert controller.view_mode == expected
