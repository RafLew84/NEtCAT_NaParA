from __future__ import annotations

from dataclasses import dataclass

from .domain_correction import DomainCorrectionModule
from .domain_correction_models import (
    ApplyPreparedDomainCorrection,
    DomainCorrectionWorkspace,
    EffectiveDomainProjection,
    ManualOrientationIntent,
    PreparedDomainCorrection,
)
from .manual_domain_models import ManualDomainIntent
from .models import DomainAnalysisResult
from .workspace_lifecycle_actions import DomainAnalysisWorkspaceIntentError


@dataclass(frozen=True)
class SelectDomainMolecules:
    source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        values = tuple(sorted({_text(value, "source_id") for value in self.source_ids}))
        object.__setattr__(self, "source_ids", values)


@dataclass(frozen=True)
class PreviewManualOrientation:
    orientation_label: str
    reason_code: str | None = None


@dataclass(frozen=True)
class PreviewManualOrientationReset:
    pass


@dataclass(frozen=True)
class DiscardPreparedDomainCorrection:
    pass


@dataclass(frozen=True)
class PreviewCreateManualDomain:
    pass


@dataclass(frozen=True)
class PreviewMoveToManualDomain:
    manual_domain_id: str


@dataclass(frozen=True)
class PreviewDeleteManualDomain:
    manual_domain_id: str


@dataclass(frozen=True)
class PreviewRestoreManualDomain:
    manual_domain_id: str


DomainCorrectionWorkspaceAction = (
    SelectDomainMolecules
    | PreviewManualOrientation
    | PreviewManualOrientationReset
    | DiscardPreparedDomainCorrection
    | PreviewCreateManualDomain
    | PreviewMoveToManualDomain
    | PreviewDeleteManualDomain
    | PreviewRestoreManualDomain
    | ApplyPreparedDomainCorrection
)


@dataclass(frozen=True)
class DomainCorrectionWorkspaceState:
    correction_set: DomainCorrectionWorkspace | None = None
    effective_projection: EffectiveDomainProjection | None = None
    selected_source_ids: tuple[str, ...] = ()
    prepared: PreparedDomainCorrection | None = None

    def __post_init__(self) -> None:
        if (self.correction_set is None) != (self.effective_projection is None):
            raise ValueError("Correction set and effective projection must coexist.")
        if self.correction_set is not None and (
            self.effective_projection is None
            or self.correction_set.revision
            != self.effective_projection.correction_revision
        ):
            raise ValueError("Effective projection must match the correction revision.")
        if self.prepared is not None and self.correction_set is None:
            raise ValueError("Prepared correction requires an initialized set.")


def initialize_domain_corrections(
    module: DomainCorrectionModule,
    automatic: DomainAnalysisResult,
) -> DomainCorrectionWorkspaceState:
    correction_set = module.initialize(automatic)
    return DomainCorrectionWorkspaceState(
        correction_set=correction_set,
        effective_projection=module.project(automatic, correction_set),
    )


def reduce_domain_corrections(
    state: DomainCorrectionWorkspaceState,
    automatic: DomainAnalysisResult | None,
    physical_frame_id: str,
    action: DomainCorrectionWorkspaceAction,
    module: DomainCorrectionModule,
) -> DomainCorrectionWorkspaceState:
    if isinstance(action, DiscardPreparedDomainCorrection) and state.prepared is None:
        return state
    correction_set = state.correction_set
    if automatic is None or correction_set is None:
        raise DomainAnalysisWorkspaceIntentError(
            "Manual orientation requires a published automatic result."
        )
    if isinstance(action, SelectDomainMolecules):
        available = set(_frame_source_ids(automatic, physical_frame_id))
        missing = tuple(value for value in action.source_ids if value not in available)
        if missing:
            raise DomainAnalysisWorkspaceIntentError(
                f"Selected molecules do not exist in the active frame: {missing!r}."
            )
        if action.source_ids == state.selected_source_ids and state.prepared is None:
            return state
        return DomainCorrectionWorkspaceState(
            correction_set=correction_set,
            effective_projection=state.effective_projection,
            selected_source_ids=action.source_ids,
        )
    if isinstance(action, DiscardPreparedDomainCorrection):
        return DomainCorrectionWorkspaceState(
            correction_set=correction_set,
            effective_projection=state.effective_projection,
            selected_source_ids=state.selected_source_ids,
        )
    needs_selection = isinstance(action, (
        PreviewManualOrientation,
        PreviewManualOrientationReset,
        PreviewCreateManualDomain,
        PreviewMoveToManualDomain,
    ))
    if needs_selection and not state.selected_source_ids:
        raise DomainAnalysisWorkspaceIntentError(
            "Select at least one molecule before previewing a correction."
        )
    if isinstance(action, PreviewManualOrientation):
        intent = ManualOrientationIntent.assign(
            physical_frame_id=physical_frame_id,
            source_ids=state.selected_source_ids,
            orientation_label=action.orientation_label,
            reason_code=action.reason_code,
        )
        return _with_preview(state, module.prepare(correction_set, automatic, intent))
    if isinstance(action, PreviewManualOrientationReset):
        reset_intent = ManualOrientationIntent.reset(
            physical_frame_id=physical_frame_id,
            source_ids=state.selected_source_ids,
        )
        return _with_preview(
            state,
            module.prepare(correction_set, automatic, reset_intent),
        )
    domain_intent = _manual_domain_intent(
        action,
        physical_frame_id,
        state.selected_source_ids,
    )
    if domain_intent is not None:
        return _with_preview(
            state,
            module.prepare(correction_set, automatic, domain_intent),
        )
    if not isinstance(action, ApplyPreparedDomainCorrection):
        raise TypeError("Unsupported Domain Correction Workspace action.")
    return _apply_prepared_correction(
        state,
        automatic,
        action,
        module,
    )


def _manual_domain_intent(
    action: DomainCorrectionWorkspaceAction,
    physical_frame_id: str,
    source_ids: tuple[str, ...],
) -> ManualDomainIntent | None:
    if isinstance(action, PreviewCreateManualDomain):
        return ManualDomainIntent.create(
            physical_frame_id=physical_frame_id,
            source_ids=source_ids,
        )
    if isinstance(action, PreviewMoveToManualDomain):
        return ManualDomainIntent.move(
            physical_frame_id=physical_frame_id,
            source_ids=source_ids,
            manual_domain_id=action.manual_domain_id,
        )
    if isinstance(action, PreviewDeleteManualDomain):
        return ManualDomainIntent.delete(
            physical_frame_id=physical_frame_id,
            manual_domain_id=action.manual_domain_id,
        )
    if isinstance(action, PreviewRestoreManualDomain):
        return ManualDomainIntent.restore(
            physical_frame_id=physical_frame_id,
            manual_domain_id=action.manual_domain_id,
        )
    return None


def _apply_prepared_correction(
    state: DomainCorrectionWorkspaceState,
    automatic: DomainAnalysisResult,
    action: ApplyPreparedDomainCorrection,
    module: DomainCorrectionModule,
) -> DomainCorrectionWorkspaceState:
    if action.preview != state.prepared:
        raise DomainAnalysisWorkspaceIntentError(
            "Apply requires the current prepared Domain Correction."
        )
    assert state.correction_set is not None
    updated_set = module.dispatch(state.correction_set, automatic, action)
    return DomainCorrectionWorkspaceState(
        correction_set=updated_set,
        effective_projection=module.project(automatic, updated_set),
        selected_source_ids=state.selected_source_ids,
    )


def clear_domain_correction_selection(
    state: DomainCorrectionWorkspaceState,
) -> DomainCorrectionWorkspaceState:
    if not state.selected_source_ids and state.prepared is None:
        return state
    return DomainCorrectionWorkspaceState(
        correction_set=state.correction_set,
        effective_projection=state.effective_projection,
    )


def _with_preview(
    state: DomainCorrectionWorkspaceState,
    prepared: PreparedDomainCorrection,
) -> DomainCorrectionWorkspaceState:
    return DomainCorrectionWorkspaceState(
        correction_set=state.correction_set,
        effective_projection=state.effective_projection,
        selected_source_ids=state.selected_source_ids,
        prepared=prepared,
    )


def _frame_source_ids(
    automatic: DomainAnalysisResult,
    physical_frame_id: str,
) -> tuple[str, ...]:
    gate = automatic.m6_gate
    assert gate is not None
    try:
        return next(
            frame.analyzed_source_ids
            for frame in gate.frames
            if frame.physical_frame_id == physical_frame_id
        )
    except StopIteration as error:
        raise DomainAnalysisWorkspaceIntentError(
            "The active frame is absent from the published result."
        ) from error


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text.")
    return value.strip()


__all__ = [
    "DomainCorrectionWorkspaceAction",
    "DomainCorrectionWorkspaceState",
    "DiscardPreparedDomainCorrection",
    "PreviewManualOrientation",
    "PreviewManualOrientationReset",
    "PreviewCreateManualDomain",
    "PreviewMoveToManualDomain",
    "PreviewDeleteManualDomain",
    "PreviewRestoreManualDomain",
    "SelectDomainMolecules",
]
