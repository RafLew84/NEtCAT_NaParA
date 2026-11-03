from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True, kw_only=True)
class DetectionIdentity:
    physical_frame_id: str
    source_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "physical_frame_id",
            _text(self.physical_frame_id, "physical_frame_id"),
        )
        object.__setattr__(self, "source_id", _text(self.source_id, "source_id"))


@dataclass(frozen=True, order=True, kw_only=True)
class CorrectionSourceMapping:
    source_identity: DetectionIdentity
    target_source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_identity, DetectionIdentity):
            raise TypeError("source_identity must be a DetectionIdentity.")
        object.__setattr__(
            self,
            "target_source_ids",
            tuple(sorted({
                _text(value, "target_source_id")
                for value in self.target_source_ids
            })),
        )


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text.")
    return value.strip()


__all__ = ["CorrectionSourceMapping", "DetectionIdentity"]
