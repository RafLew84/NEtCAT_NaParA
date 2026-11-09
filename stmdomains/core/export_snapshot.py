"""Frozen export selection, independent of the portable project and its undo log."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.core.immutable import freeze_metadata
from stmdomains.core.project import ProjectAnalysis, ProjectSnapshot
from stmdomains.core.series import Series


@dataclass(frozen=True)
class ExportCorrection:
    result: FrameAnalysis | None
    original: FrameAnalysis | None
    variant_id: str
    history: tuple[FrameAnalysis, ...]


@dataclass(frozen=True)
class ExportSnapshot:
    series: Series
    view: Mapping[str, Any]
    analysis: ProjectAnalysis | None
    variant: str = 'after_corrections'
    corrections: Mapping[int, ExportCorrection] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'view', freeze_metadata(self.view))
        object.__setattr__(self, 'corrections', MappingProxyType(dict(self.corrections)))


ExportSource = ProjectSnapshot | ExportSnapshot


def selected_result(snapshot: ExportSource, index: int) -> FrameAnalysis | None:
    if isinstance(snapshot, ExportSnapshot) and index in snapshot.corrections:
        return snapshot.corrections[index].result
    return snapshot.analysis.frames.get(index) if snapshot.analysis else None


def original_result(snapshot: ExportSource, index: int) -> FrameAnalysis | None:
    if isinstance(snapshot, ExportSnapshot) and index in snapshot.corrections:
        return snapshot.corrections[index].original
    return snapshot.analysis.frames.get(index) if snapshot.analysis else None
