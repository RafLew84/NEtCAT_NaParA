"""Consistent availability feedback for pair and whole-series method selectors."""

from collections.abc import Mapping

from stmviewer.efficient_matcher import EFFICIENT_METHOD, efficient_unavailable_reason
from stmviewer.deep_ecc import HYBRID_METHOD, hybrid_unavailable_reason
from stmviewer.local_registration import LOCAL_METHOD, local_unavailable_reason
from stmviewer.deep_matcher import DeepMatcherOptions, deep_unavailable_reason


def method_unavailable_reason(method: str, options: DeepMatcherOptions,
                              cpu_errors: Mapping[str, str | None]) -> str | None:
    if method == EFFICIENT_METHOD:
        return efficient_unavailable_reason(options)
    if method == LOCAL_METHOD:
        return cpu_errors['phase_correlation'] or local_unavailable_reason(options)
    if method == HYBRID_METHOD:
        return cpu_errors['phase_correlation'] or hybrid_unavailable_reason(options)
    if method == 'deep_matcher_translation':
        reason = cpu_errors['phase_correlation'] or deep_unavailable_reason(options)
        return f'Deep Matcher niedostępny: {reason}' if reason else None
    return cpu_errors[method]
