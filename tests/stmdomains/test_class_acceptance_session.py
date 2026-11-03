"""Acceptance and domain tuning compose without silently reverting either setting."""

from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.tools.analysis_demo import create_analysis_demo
import pytest
from test_analysis_session import controller  # noqa: F401 — public-controller fixture


def test_reanalysis_and_domain_tuning_keep_applied_acceptance(qtbot, controller, tmp_path):
    controller.open_session(create_analysis_demo(tmp_path)["single"])
    qtbot.waitUntil(lambda: not controller.is_busy)
    assert not controller.can_tune_acceptance
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    catalogue = controller.result.catalogue
    controller.recalculate_class_acceptance(ClassAcceptanceSettings(class_radius_multiplier=.05))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert controller.result.catalogue is catalogue
    controller.recalculate_domains(DomainSettings(minimum_domain_size=6))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    tuned = controller.result
    assert tuned.parameters["class_radius_multiplier"] == .05
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert controller.result.parameters["class_radius_multiplier"] == .05
    assert controller.result.parameters["minimum_domain_size"] == 6
    assert controller.result.assignments == tuned.assignments


@pytest.mark.parametrize("action", ["cancel", "navigate", "reopen"])
def test_interrupted_acceptance_cannot_replace_previous_completed_results(qtbot, controller, tmp_path, action):
    path = create_analysis_demo(tmp_path)["series"]
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    base = controller.result
    controller.recalculate_class_acceptance(ClassAcceptanceSettings(class_radius_multiplier=.05))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    tuned = controller.result
    controller.select_result("previous")
    actions = []

    def interrupt(busy, text):
        if busy and not actions:
            actions.append(action)
            if action == "cancel":
                controller.cancel()
            elif action == "navigate":
                controller.show_frame(1)
            else:
                controller.open_session(path)

    controller.busy_changed.connect(interrupt)
    controller.recalculate_class_acceptance(ClassAcceptanceSettings(.06, 1.5))
    qtbot.waitUntil(lambda: not controller.is_busy and not controller.pending_task_count, timeout=15000)
    controller.busy_changed.disconnect(interrupt)
    assert actions == [action]
    if action == "reopen":
        assert controller.result is controller.previous_result is None
    else:
        if action == "navigate":
            assert controller.result is None
            controller.show_frame(0)
            qtbot.waitUntil(lambda: not controller.is_busy)
        assert controller.result is controller.previous_result is base
        assert controller.latest_result is tuned
    assert not controller.prompts.errors


def test_backend_failure_during_acceptance_preserves_result(qtbot, controller, tmp_path, monkeypatch):
    import numpy as np

    controller.open_session(create_analysis_demo(tmp_path)["single"])
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    base = controller.result

    def unavailable(*args, **kwargs):
        raise RuntimeError("Numerical backend unavailable")

    monkeypatch.setattr(np.linalg, "norm", unavailable)
    controller.recalculate_class_acceptance(ClassAcceptanceSettings(.06, 1.5))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert controller.result is base
    assert "Numerical backend unavailable" in controller.prompts.errors[-1]
