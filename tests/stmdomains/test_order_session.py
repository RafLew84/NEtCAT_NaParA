"""Applied order configuration survives other operations; abandoned work never publishes."""

import pytest

from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings
from stmdomains.analysis.class_settings import ClassFitSettings
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.order_settings import OrderSettings
from stmdomains.tools.analysis_demo import create_analysis_demo
from stmdomains.ui.main_window import STMDomainsMainWindow
from test_analysis_session import Prompts, controller  # noqa: F401


def test_other_controls_and_series_discovery_preserve_applied_order(qtbot, tmp_path):
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    controller = window.controller
    controller.open_session(create_analysis_demo(tmp_path)["series"])
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    settings = OrderSettings(order_quantile=.925, order_minimum_local_count=12)
    controller.recalculate_order(settings)
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    for operation in (lambda: controller.recalculate_class_acceptance(ClassAcceptanceSettings(.06)),
                      lambda: controller.recalculate_domains(DomainSettings(minimum_domain_size=6)),
                      controller.analyze_current_frame,
                      lambda: controller.fit_current_classes(ClassFitSettings(k=1))):
        operation()
        qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
        assert OrderSettings.from_parameters(controller.result.parameters) == settings
    assert controller.result.catalogue.provenance["frames"][0]["order_settings"] == settings.parameters()
    window.analysis_action.trigger()
    dialog = window.analysis_dialog
    dialog.copy_result.click()
    dialog.class_fields.mode.setCurrentIndex(0)
    dialog.class_fields.k.setValue(1)
    dialog.scope_fields.scope.setCurrentIndex(1)
    dialog.scope_fields.start.setValue(1)
    dialog.scope_fields.end.setValue(2)
    dialog.calculate.click()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert controller.series_run.plan.order_settings == settings
    assert not controller.prompts.errors
    for index in (0, 1):
        controller.show_frame(index)
        qtbot.waitUntil(lambda: not controller.is_busy)
        assert OrderSettings.from_parameters(controller.result.parameters) == settings
    window.close()
    qtbot.waitUntil(lambda: not controller.pending_task_count and not window.filmstrip.pending_task_count)


@pytest.mark.parametrize("action", ["cancel", "navigate", "reopen", "shutdown"])
def test_interruption_during_calibration_preserves_previous_result(qtbot, controller, tmp_path, action):
    path = create_analysis_demo(tmp_path)["series"]
    controller.open_session(path)
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    base = controller.result
    actions = []

    def interrupt(busy, text):
        if busy and "Kalibracja" in text and not actions:
            actions.append(action)
            if action == "cancel":
                controller.cancel()
            elif action == "navigate":
                controller.show_frame(1)
            elif action == "reopen":
                controller.open_session(path)
            else:
                controller.shutdown()

    controller.busy_changed.connect(interrupt)
    controller.recalculate_order(OrderSettings(order_quantile=.925))
    qtbot.waitUntil(lambda: not controller.is_busy and not controller.pending_task_count, timeout=15000)
    controller.busy_changed.disconnect(interrupt)
    assert actions == [action]
    if action == "reopen":
        assert controller.result is None
    else:
        if action == "navigate":
            assert controller.result is None
            controller.show_frame(0)
            qtbot.waitUntil(lambda: not controller.is_busy)
        assert controller.result is base
    assert not controller.prompts.errors


def test_unavailable_calibration_keeps_previous_result_and_explains_failure(qtbot, controller, tmp_path):
    controller.open_session(create_analysis_demo(tmp_path)["single"])
    qtbot.waitUntil(lambda: not controller.is_busy)
    controller.analyze_current_frame()
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    base = controller.result
    controller.recalculate_order(OrderSettings(order_minimum_effective_count=200))
    qtbot.waitUntil(lambda: not controller.is_busy, timeout=15000)
    assert controller.result is base
    assert "Brak wystarczających kontroli" in controller.prompts.errors[-1]
