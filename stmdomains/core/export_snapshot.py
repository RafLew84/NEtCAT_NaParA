"""Frozen export selection, independent of the portable project and its undo log."""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any

from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.core.immutable import freeze_metadata
from stmdomains.core.project import ProjectAnalysis, ProjectSnapshot
from stmdomains.core.series import Series
from stmdomains.core.manual_classes import ManualClassList
from stmdomains.core.manual_class_lists import ManualClassLists
from stmdomains.core.manual_domains import MANUAL_METHOD


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
    shared_classes: tuple[ManualClassList, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, 'view', freeze_metadata(self.view))
        object.__setattr__(self, 'corrections', MappingProxyType(dict(self.corrections)))


ExportSource = ProjectSnapshot | ExportSnapshot


def selected_result(snapshot: ExportSource, index: int) -> FrameAnalysis | None:
    if isinstance(snapshot, ExportSnapshot) and index in snapshot.corrections:
        return snapshot.corrections[index].result
    result = snapshot.analysis.frames.get(index) if snapshot.analysis else None
    if isinstance(snapshot, ExportSnapshot) and result is not None and snapshot.variant == 'after_corrections':
        source_key = ManualClassLists.source_key(snapshot.series.identity, result)
        labels = next((c for c in snapshot.shared_classes if c.source_key == source_key and c.generation > 0), None)
        if labels is not None:
            return replace(result, class_list=labels, parameters={**result.parameters, 'domain_method': MANUAL_METHOD})
    return result


def original_result(snapshot: ExportSource, index: int) -> FrameAnalysis | None:
    if isinstance(snapshot, ExportSnapshot) and index in snapshot.corrections:
        return snapshot.corrections[index].original
    return snapshot.analysis.frames.get(index) if snapshot.analysis else None
