"""Two completed domain results per frame, with explicit selection and no stale publication."""

import numpy as np
import pytest
from threading import Event
from PyQt6.QtCore import QRunnable, QThreadPool

from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.tools.analysis_demo import create_analysis_demo
from test_analysis_session import controller  # noqa: F401 — shared public-controller fixture


def test_compare_restore_navigate_and_reopen_keep_versions_bound_to_frame(qtbot, controller, tmp_path):
    path = create_analysis_demo(tmp_path)["series"]
    views = []
    controller.frame_changed.connect(views.append)
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.recalculate_domains(DomainSettings())
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    base = controller.result
    assert base.status == "complete" and controller.previous_result is None
    controller.recalculate_domains(DomainSettings(minimum_domain_size=6))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    tuned = controller.result
    assert controller.latest_result is tuned and controller.previous_result is base
    assert controller.result_version == "new"
    controller.select_result("previous")
    assert controller.result is base and views[-1].result is base
    controller.set_gamma(1.4)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert views[-1].result is base
    controller.show_frame(1)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.result is controller.previous_result is None
    controller.show_frame(0)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.result is base and controller.latest_result is tuned
    controller.recalculate_domains(DomainSettings())
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    restored = controller.result
    assert controller.previous_result is tuned and controller.result_version == "new"
    assert restored.assignments == base.assignments
    np.testing.assert_array_equal(restored.domain_labels, base.domain_labels)
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.latest_result is controller.previous_result is controller.result is None
    assert not controller.prompts.errors


@pytest.mark.parametrize("action", ["cancel", "navigate", "reopen"])
def test_abandoned_recalculation_keeps_both_completed_versions(qtbot, qapp, controller, tmp_path, action):
    path = create_analysis_demo(tmp_path)["series"]
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy)
    for minimum in (8, 6):
        controller.recalculate_domains(DomainSettings(minimum_domain_size=minimum))
        qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    old, new = controller.previous_result, controller.latest_result
    controller.select_result("previous")
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
        controller.recalculate_domains(DomainSettings(minimum_domain_size=20))
        controller.select_result("new")  # Comparison is blocked during pending work.
        assert controller.result is old
        if action == "cancel":
            controller.cancel()
        elif action == "navigate":
            controller.show_frame(1)
        else:
            controller.open_session(path)
    finally:
        release.set()
    qtbot.waitUntil(lambda: not controller.is_busy and not controller.pending_task_count)
    if action == "reopen":
        assert controller.result is controller.previous_result is controller.latest_result is None
    else:
        if action == "navigate":
            assert controller.result is None
            controller.show_frame(0)
            qtbot.waitUntil(lambda: not controller.is_busy)
        assert controller.result is controller.previous_result is old
        assert controller.latest_result is new
    assert not controller.prompts.errors


def test_failed_recalculation_preserves_displayed_previous_and_latest(qtbot, controller, tmp_path, monkeypatch):
    from scipy import ndimage

    controller.open_session(create_analysis_demo(tmp_path)["single"])
    qtbot.waitUntil(lambda: not controller.is_busy)
    for minimum in (8, 6):
        controller.recalculate_domains(DomainSettings(minimum_domain_size=minimum))
        qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    old, new = controller.previous_result, controller.latest_result
    controller.select_result("previous")

    def broken_components(*args, **kwargs):
        raise RuntimeError("Connected components backend failed")

    monkeypatch.setattr(ndimage, "label", broken_components)
    controller.recalculate_domains(DomainSettings())
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.result is controller.previous_result is old
    assert controller.latest_result is new
    assert "Connected components backend failed" in controller.prompts.errors[-1]
