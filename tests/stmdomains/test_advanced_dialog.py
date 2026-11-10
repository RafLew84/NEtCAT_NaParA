"""Advanced controls drive real analysis and leave earlier results intact."""

import pytest

from stmdomains.tools.analysis_demo import create_analysis_demo
from stmdomains.ui.main_window import STMDomainsMainWindow
from test_analysis_window import Prompts


@pytest.fixture
def window(qtbot):
    window = STMDomainsMainWindow(prompts=Prompts())
    qtbot.addWidget(window)
    window.show()
    yield window
    window.close()
    window._finish_background_work()


def test_invalid_advanced_draft_is_dirty_and_can_be_discarded(qtbot, tmp_path, window):
    window.controller.open_session(create_analysis_demo(tmp_path)['single'])
    qtbot.waitUntil(lambda: not window.controller.is_busy)
    fields = window.analysis_dialog.advanced_fields.barriers
    fields.low.setValue(99)
    try:
        assert window.project_actions.dirty
        assert window.project_actions.allow_close()
    finally:
        fields.low.setValue(65)


def test_advanced_tab_refits_descriptors_but_reuses_classes_for_barriers(qtbot, tmp_path, window):
    c = window.controller
    c.open_session(create_analysis_demo(tmp_path)['series'])
    qtbot.waitUntil(lambda: not c.is_busy)
    window.analysis_action.trigger()
    dialog = window.analysis_dialog
    assert dialog.tabs.tabText(4) == 'Zaawansowane'
    advanced = dialog.advanced_fields
    dialog.class_fields.k.setValue(4)
    advanced.descriptor.sigma.setValue(1.7)
    advanced.descriptor.radial_bins.setValue(8)
    advanced.descriptor.angle_bins.setValue(18)
    advanced.descriptor.pca.setValue(7)
    dialog.calculate.click()
    qtbot.waitUntil(lambda: not c.is_busy, timeout=20000)
    original = c.result
    assert original.parameters['descriptor_sigma_factor'] == 1.7
    assert original.catalogue.state['pca_components_count'] == 7
    dialog.class_fields.mode.setCurrentIndex(1)
    advanced.barriers.high.setValue(95)
    assert dialog.calculate.isEnabled()
    dialog.calculate.click()
    qtbot.waitUntil(lambda: not c.is_busy, timeout=20000)
    assert c.result.catalogue is original.catalogue
    assert c.result.parameters['barrier_high_percentile'] == 95
    assert original.parameters['barrier_high_percentile'] == 90
    advanced.descriptor.sigma.setValue(2)
    assert not dialog.calculate.isEnabled()
    assert 'Dopasuj' in dialog.validation.text()
    dialog.class_fields.mode.setCurrentIndex(0)
    assert dialog.calculate.isEnabled()
    dialog.calculate.click()
    qtbot.waitUntil(lambda: not c.is_busy, timeout=20000)
    assert c.result.catalogue.identifier != original.catalogue.identifier
    assert c.result.parameters['descriptor_sigma_factor'] == 2
    # A contradictory contrast range must stop before starting any worker.
    advanced.barriers.low.setValue(99)
    assert not dialog.calculate.isEnabled() and not c.is_busy
    dialog.baseline.click()
    assert dialog.calculate.isEnabled()
    assert dialog.plan().descriptor_settings.descriptor_sigma_factor == 1.25
    assert dialog.plan().barrier_settings.high_percentile == 90
    window.close()
