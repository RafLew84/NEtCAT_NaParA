from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AnalysisExportPackageResult:
    """Published analysis package and its portable relative contents."""

    package_path: Path
    package_format: str
    relative_files: tuple[str, ...]
    record_counts: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class AnalysisExportProgress:
    """One observable stage of an analysis package export."""

    phase: str
    completed_count: int = 0
    total_count: int = 0

    def __post_init__(self) -> None:
        phase = str(self.phase).strip()
        completed_count = int(self.completed_count)
        total_count = int(self.total_count)
        if not phase:
            raise ValueError("Analysis export progress phase must not be empty.")
        if completed_count < 0 or total_count < 0 or completed_count > total_count:
            raise ValueError("Analysis export progress counts are invalid.")
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "completed_count", completed_count)
        object.__setattr__(self, "total_count", total_count)


__all__ = ["AnalysisExportPackageResult", "AnalysisExportProgress"]
