"""Session catalogue selection, result versions and explicit reuse across frames."""

from stmdomains.analysis.class_settings import ClassFitSettings
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.tools.analysis_demo import create_analysis_demo
from stmdomains.tools.class_discovery_demo import create_class_discovery_demo
from test_analysis_session import controller  # noqa: F401
from threading import Event

import pytest
from PyQt6.QtCore import QRunnable, QThreadPool


def test_local_shared_previous_and_unanalysed_results_keep_their_own_catalogues(qtbot, controller, tmp_path, monkeypatch):
    from sklearn.decomposition import PCA

    path = create_analysis_demo(tmp_path)["series"]
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.fit_current_classes(ClassFitSettings(k=4))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    local = controller.result
    assert controller.active_catalogue is local.catalogue and local.catalogue.k == 4
    controller.show_frame(4)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.catalogue_status == "unanalysed" and controller.result is None
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    other_local = controller.result
    assert other_local.catalogue.scope == "current_frame"
    controller.show_frame(0)
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.fit_current_classes(ClassFitSettings(k=5, scope="selected_range", start=0, end=1))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    shared = controller.result
    assert shared.catalogue.scope == "selected_range" and controller.previous_result is local
    controller.show_frame(4)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.result is other_local and controller.catalogue_status == "earlier"

    def forbid_fit(*args, **kwargs):
        raise AssertionError("Shared catalogue must be reused")

    monkeypatch.setattr(PCA, "fit", forbid_fit)
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert controller.result.catalogue is shared.catalogue and controller.catalogue_status == "current"
    assert controller.previous_result is other_local
    controller.show_frame(0)
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.select_result("previous")
    assert controller.result is local and controller.active_catalogue is local.catalogue
    controller.recalculate_domains(DomainSettings(minimum_domain_size=6))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert controller.result.catalogue is local.catalogue and controller.result.parameters["k"] == 4
    assert controller.previous_result is shared
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert controller.active_catalogue is None and controller.result is None
    assert not controller.prompts.errors


def test_failed_new_fit_keeps_previous_result_and_catalogue(qtbot, controller, tmp_path):
    controller.open_session(create_class_discovery_demo(tmp_path)["single"])
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.fit_current_classes(ClassFitSettings(k=1))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    saved = controller.result
    controller.fit_current_classes(ClassFitSettings(k=8))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert controller.result is saved and controller.active_catalogue is saved.catalogue
    assert "K8" in controller.prompts.errors[-1]


@pytest.mark.parametrize("action", ["cancel", "navigate", "reopen", "gamma"])
def test_pending_shared_fit_is_atomic_with_navigation_and_cancel(qtbot, qapp, controller, tmp_path, action):
    path = create_analysis_demo(tmp_path)["series"]
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.fit_current_classes(ClassFitSettings(k=4))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    saved = controller.result
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
        controller.fit_current_classes(ClassFitSettings(k=5, scope="selected_range", start=0, end=1))
        assert controller.is_busy and controller.active_catalogue is saved.catalogue
        if action == "cancel":
            controller.cancel()
        elif action == "navigate":
            controller.show_frame(4)
        elif action == "reopen":
            controller.open_session(path)
        else:
            controller.set_gamma(1.4)
    finally:
        release.set()
    qtbot.waitUntil(lambda: not controller.is_busy and not controller.pending_task_count, timeout=15000)
    if action == "reopen":
        assert controller.active_catalogue is None and controller.result is None
    elif action == "gamma":
        assert controller.result.catalogue.scope == "selected_range"
        assert controller.active_catalogue is controller.result.catalogue and controller.gamma == 1.4
        assert controller.previous_result is saved
    else:
        assert controller.active_catalogue is saved.catalogue
        if action == "navigate":
            assert controller.result is None
            controller.show_frame(0)
            qtbot.waitUntil(lambda: not controller.is_busy)
        assert controller.result is saved
    assert not controller.prompts.errors
