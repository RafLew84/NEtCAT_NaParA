from __future__ import annotations

from dataclasses import dataclass

from .domain_correction_models import PreparedDomainCorrection


@dataclass(frozen=True)
class ApplyPreparedDomainCorrection:
    preview: PreparedDomainCorrection
    confirmed_prepared_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.preview, PreparedDomainCorrection):
            raise TypeError("preview must be a PreparedDomainCorrection.")
        value = self.confirmed_prepared_fingerprint
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError("confirmed_prepared_fingerprint must be non-empty text.")
        if value is not None:
            object.__setattr__(self, "confirmed_prepared_fingerprint", value.strip())

    @classmethod
    def confirmed(
        cls,
        preview: PreparedDomainCorrection,
    ) -> ApplyPreparedDomainCorrection:
        return cls(preview, preview.prepared_fingerprint)


@dataclass(frozen=True)
class UndoDomainCorrection:
    pass


@dataclass(frozen=True)
class RedoDomainCorrection:
    pass


__all__ = [
    "ApplyPreparedDomainCorrection",
    "RedoDomainCorrection",
    "UndoDomainCorrection",
]
