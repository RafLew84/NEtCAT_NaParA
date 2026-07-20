from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class M6DomainTypeSelection:
    """One validated structural-type table and overlay selection."""

    status: Literal["classified", "unclassified"]
    domain_type_id: int | None

    def __post_init__(self) -> None:
        if self.status == "classified":
            value = self.domain_type_id
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(
                    "A classified selection requires a non-negative type ID."
                )
            return
        if self.status != "unclassified":
            raise ValueError("Unsupported domain type selection status.")
        if self.domain_type_id is not None:
            raise ValueError("An unclassified selection cannot have a type ID.")

    @classmethod
    def classified(cls, domain_type_id: int) -> "M6DomainTypeSelection":
        return cls(status="classified", domain_type_id=domain_type_id)

    @classmethod
    def unclassified(cls) -> "M6DomainTypeSelection":
        return cls(status="unclassified", domain_type_id=None)

    @property
    def is_unclassified(self) -> bool:
        return self.status == "unclassified"


__all__ = ["M6DomainTypeSelection"]
