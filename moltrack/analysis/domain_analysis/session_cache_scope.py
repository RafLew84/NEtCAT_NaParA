from __future__ import annotations

from dataclasses import dataclass, replace

from .session_state import (
    DomainAnalysisClassifierCacheRecord,
    DomainAnalysisM6CacheRecord,
    DomainAnalysisSessionState,
)


@dataclass(frozen=True)
class DomainAnalysisSessionCacheRecords:
    """Complete schema-v2 cache payload owned by one analysis runtime."""

    m6_records: tuple[DomainAnalysisM6CacheRecord, ...] = ()
    classifier_records: tuple[DomainAnalysisClassifierCacheRecord, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "m6_records", tuple(self.m6_records))
        object.__setattr__(
            self,
            "classifier_records",
            tuple(self.classifier_records),
        )
        if any(
            not isinstance(value, DomainAnalysisM6CacheRecord)
            for value in self.m6_records
        ):
            raise TypeError("m6_records contain an invalid value.")
        if any(
            not isinstance(value, DomainAnalysisClassifierCacheRecord)
            for value in self.classifier_records
        ):
            raise TypeError("classifier_records contain an invalid value.")


def with_scoped_domain_analysis_cache(
    state: DomainAnalysisSessionState,
    records: DomainAnalysisSessionCacheRecords,
) -> DomainAnalysisSessionState:
    """Attach only cache entries valid for this schema-v2 workspace."""
    if not isinstance(state, DomainAnalysisSessionState):
        raise TypeError("state must be a DomainAnalysisSessionState.")
    base = replace(
        state,
        m6_cache_records=(),
        classifier_cache_records=(),
    )
    scoped_m6: list[DomainAnalysisM6CacheRecord] = []
    if not isinstance(records, DomainAnalysisSessionCacheRecords):
        raise TypeError("records must be DomainAnalysisSessionCacheRecords.")
    for m6_record in records.m6_records:
        try:
            replace(base, m6_cache_records=(*scoped_m6, m6_record))
        except ValueError:
            continue
        scoped_m6.append(m6_record)
    with_m6 = replace(base, m6_cache_records=tuple(scoped_m6))
    scoped_classifiers: list[DomainAnalysisClassifierCacheRecord] = []
    for classifier_record in records.classifier_records:
        try:
            replace(
                with_m6,
                classifier_cache_records=(
                    *scoped_classifiers,
                    classifier_record,
                ),
            )
        except ValueError:
            continue
        scoped_classifiers.append(classifier_record)
    return replace(
        with_m6,
        classifier_cache_records=tuple(scoped_classifiers),
    )


__all__ = [
    "DomainAnalysisSessionCacheRecords",
    "with_scoped_domain_analysis_cache",
]
