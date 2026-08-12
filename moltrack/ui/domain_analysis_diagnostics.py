from __future__ import annotations

from dataclasses import dataclass, field

from moltrack.analysis.domain_analysis import (
    DiagnosticExecutionStatus,
    DiagnosticStageResult,
    MoleculeDiagnosticFunnel,
    MoleculeDiagnosticStageId,
)


@dataclass(frozen=True)
class MoleculeDiagnosticSummary:
    """Compact presentation derived directly from one immutable funnel."""

    frame_index: int
    source_id: str
    backend_id: str
    execution_counts: tuple[tuple[DiagnosticExecutionStatus, int], ...]
    q6: float | None
    raw_orientation_label: str | None
    automatic_orientation_label: str | None
    effective_orientation_label: str | None


@dataclass(frozen=True)
class MoleculeDiagnosticView:
    """Thin summary/expansion adapter that never reconstructs the trace."""

    funnel: MoleculeDiagnosticFunnel
    _summary: MoleculeDiagnosticSummary = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.funnel, MoleculeDiagnosticFunnel):
            raise TypeError("funnel must be a MoleculeDiagnosticFunnel.")
        object.__setattr__(self, "_summary", _summarize(self.funnel))

    @property
    def summary(self) -> MoleculeDiagnosticSummary:
        return self._summary

    @property
    def expanded_stages(self) -> tuple[DiagnosticStageResult, ...]:
        return self.funnel.stages

    def stage(self, stage_id: MoleculeDiagnosticStageId) -> DiagnosticStageResult:
        return self.funnel.stage(stage_id)


def _summarize(funnel: MoleculeDiagnosticFunnel) -> MoleculeDiagnosticSummary:
    statuses: tuple[DiagnosticExecutionStatus, ...] = (
        "completed", "not_run", "unavailable", "failed"
    )
    return MoleculeDiagnosticSummary(
        frame_index=funnel.frame_index,
        source_id=funnel.source_id,
        backend_id=funnel.backend_identity.backend_id,
        execution_counts=tuple(
            (
                status,
                sum(
                    stage.execution_status == status
                    for stage in funnel.stages
                ),
            )
            for status in statuses
        ),
        q6=_optional_float(_stage_value(funnel, "local_order", "q6")),
        raw_orientation_label=_optional_text(_stage_value(
            funnel, "orientation_raw", "raw_orientation_label"
        )),
        automatic_orientation_label=_optional_text(_stage_value(
            funnel, "automatic_result", "orientation_label"
        )),
        effective_orientation_label=_optional_text(_stage_value(
            funnel, "effective_result", "orientation_label"
        )),
    )


def _stage_value(
    funnel: MoleculeDiagnosticFunnel,
    stage_id: MoleculeDiagnosticStageId,
    key: str,
) -> object:
    evidence = funnel.stage(stage_id).evidence
    return None if evidence is None else evidence.value(key)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("Diagnostic summary expected text evidence.")
    return value


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("Diagnostic summary expected numeric evidence.")
    return float(value)
