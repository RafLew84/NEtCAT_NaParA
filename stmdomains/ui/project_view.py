"""Plain view/draft records; applied analysis parameters remain in saved results."""

from collections.abc import Mapping
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QSignalBlocker

from stmdomains.io.project_validation import analysis_plan

if TYPE_CHECKING:
    from stmdomains.ui.analysis_dialog import AnalysisDialog
    from stmdomains.ui.main_window import STMDomainsMainWindow


def capture_view(window: 'STMDomainsMainWindow') -> dict:
    controller = window.controller
    annotations, regions = window.annotation_controls, window.result_controls.regions
    return {'current_index': controller.current_index, 'mode': controller.view_mode, 'gamma': controller.gamma,
            'playback_rate': controller.playback_rate, 'assignment_mode': window.result_controls.mode.currentData(),
            'viewport': window.image_view.view_state(),
            'layers': {**{name: getattr(annotations, name).isChecked() for name in ('centers', 'boxes', 'masks')},
                       'barriers': window.analysis_dialog.advanced_fields.show_barriers.isChecked(),
                       **{name: getattr(regions, name).isChecked() for name in ('fill', 'outlines', 'numbers')},
                       'mask_opacity': annotations.opacity.value(), 'domain_opacity': regions.opacity.value()}}


def restore_view(window: 'STMDomainsMainWindow', view: Mapping[str, Any]) -> None:
    # The controller has already prepared the saved frame, gamma and geometry.
    annotations, regions = window.annotation_controls, window.result_controls.regions
    layers = view.get('layers', {})
    window.analysis_dialog.advanced_fields.show_barriers.setChecked(layers.get('barriers', False))
    for controls, names in ((annotations, ('centers', 'boxes', 'masks')), (regions, ('fill', 'outlines', 'numbers'))):
        for name in names:
            if name in layers:
                getattr(controls, name).setChecked(layers[name])
    annotations.opacity.setValue(layers.get('mask_opacity', 45))
    regions.opacity.setValue(layers.get('domain_opacity', 35))
    window.result_controls.mode.setCurrentIndex(window.result_controls.mode.findData(view.get('assignment_mode', 'domains')))
    window.playback_controls.rate.setCurrentIndex(window.playback_controls.rate.findData(view.get('playback_rate', 5)))
    if 'viewport' in view:
        window.image_view.restore_view_state(view['viewport'])


def capture_draft(dialog: 'AnalysisDialog') -> dict:
    classes = dialog.class_fields
    return {'plan': asdict(dialog.plan()), 'scope': dialog.scope_fields.scope.currentData(),
            'scope_start': dialog.scope_fields.start.value() - 1,
            'class_mode': classes.mode.currentData(), 'catalogue_id': classes.catalogue.currentData(),
            'discovery_source': classes.fit_source.currentData()}


def restore_draft(dialog: 'AnalysisDialog', draft: Mapping[str, Any]) -> None:
    if 'plan' not in draft:
        return
    plan = analysis_plan(draft['plan'])
    classes, scope = dialog.class_fields, dialog.scope_fields
    fields = (scope, classes, dialog.acceptance_fields, dialog.order_fields, dialog.domain_fields, dialog.advanced_fields)
    blockers = [QSignalBlocker(item) for item in fields]
    scope.scope.setCurrentIndex(scope.scope.findData(draft['scope']))
    scope.start.setValue(draft.get('scope_start', plan.start) + 1)
    scope.end.setValue(plan.end + 1)
    classes.mode.setCurrentIndex(classes.mode.findData(draft['class_mode']))
    classes.k.setValue(plan.k)
    classes.count_mode.setCurrentIndex(classes.count_mode.findData(plan.class_count_mode))
    classes.auto_max_k.setValue(plan.auto_max_k)
    classes.fit_source.setCurrentIndex(classes.fit_source.findData(draft.get('discovery_source', 'same_range')))
    classes.fit_start.setValue(plan.fit_start + 1)
    classes.fit_end.setValue(plan.fit_end + 1)
    identifier = draft.get('catalogue_id')
    classes.catalogue.setCurrentIndex(classes.catalogue.findData(identifier) if identifier else -1)
    dialog.acceptance_fields.load(plan.acceptance)
    dialog.order_fields.load(plan.order_settings)
    dialog.domain_fields.load(plan.domain_settings)
    dialog.advanced_fields.descriptor.load(plan.descriptor_settings)
    dialog.advanced_fields.barriers.load(plan.barrier_settings)
    del blockers
    dialog.refresh()
