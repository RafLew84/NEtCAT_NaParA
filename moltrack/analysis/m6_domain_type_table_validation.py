from __future__ import annotations

from .m6_domain_type_range_comparison import M6DomainTypeRangeComparison
from .m6_domain_type_results import M6DomainTypeClassificationResult
from .m6_single_range_domain_type_summary import M6SingleRangeDomainTypeSummary


def validate_m6_domain_type_table_result(
    classification: M6DomainTypeClassificationResult,
    table_result: M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison,
) -> None:
    """Require one table result to describe the supplied classification scope."""

    if not isinstance(classification, M6DomainTypeClassificationResult):
        raise TypeError("classification must be a domain type result.")
    if not isinstance(
        table_result,
        (M6SingleRangeDomainTypeSummary, M6DomainTypeRangeComparison),
    ):
        raise TypeError("table_result must be a domain type summary or comparison.")
    if table_result.classification_input_fingerprint != classification.input_fingerprint:
        raise ValueError("Domain type table result uses a different classification.")
    if table_result.source_view != classification.source_view:
        raise ValueError("Domain type table result uses a different source view.")
    if isinstance(table_result, M6SingleRangeDomainTypeSummary):
        actual_ranges = (table_result.frame_range,)
        expected_mode = "single_range"
    else:
        actual_ranges = (table_result.first_range, table_result.second_range)
        expected_mode = "compare_ranges"
    if classification.analysis_scope.analysis_mode != expected_mode:
        raise ValueError("Domain type table result uses a different analysis mode.")
    if actual_ranges != classification.analysis_scope.ranges:
        raise ValueError("Domain type table result uses different frame ranges.")
    if table_result.uses_tracking is not False:
        raise ValueError("Domain type table result must not use tracking.")


__all__ = ["validate_m6_domain_type_table_result"]
