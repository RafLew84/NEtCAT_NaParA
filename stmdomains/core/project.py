"""One portable work snapshot; analysis data and the next parameter draft stay separate."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from types import MappingProxyType

from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.core.class_catalogue import ClassCatalogue
from stmdomains.core.immutable import freeze_metadata
from stmdomains.core.series import Series
from stmdomains.core.manual_project import ManualProjectState


@dataclass(frozen=True)
class ProjectAnalysis:
    identifier: str
    indices: tuple[int, ...]
    frames: Mapping[int, FrameAnalysis]
    statuses: Mapping[int, Mapping[str, Any]]
    catalogues: tuple[ClassCatalogue, ...] = ()
    execution: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.frames, dict):
            object.__setattr__(self, 'frames', MappingProxyType(dict(self.frames)))
        object.__setattr__(self, 'statuses', freeze_metadata(self.statuses))
        object.__setattr__(self, 'execution', freeze_metadata(self.execution))


@dataclass(frozen=True)
class ProjectSnapshot:
    series: Series
    view: Mapping[str, Any] = field(default_factory=dict)
    draft: Mapping[str, Any] = field(default_factory=dict)
    analysis: ProjectAnalysis | None = None
    manual: ManualProjectState | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, 'view', freeze_metadata(self.view))
        object.__setattr__(self, 'draft', freeze_metadata(self.draft))
