"""Method identity and availability, shared by graph presentation and execution."""

from stmviewer.lightglue_matcher import LIGHTGLUE_METHOD, lightglue_unavailable_reason
from stmviewer.efficient_matcher import EFFICIENT_METHOD, efficient_unavailable_reason
from stmviewer.roma_matcher import ROMA_METHOD, roma_unavailable_reason
from stmviewer.matchanything_matcher import MATCHANYTHING_METHOD, matchanything_unavailable_reason
from stmviewer.deep_matcher import DeepMatcherOptions, deep_unavailable_reason
from stmviewer.deep_ecc import HYBRID_METHOD, hybrid_unavailable_reason
from stmviewer.local_registration import LOCAL_METHOD, local_unavailable_reason
from stmviewer.registration import (
    DEEP_METHODS, REGISTRATION_METHODS, RegistrationError, registration_unavailable_reason,
)


def graph_method_label(method: str) -> str:
    try:
        return REGISTRATION_METHODS[method]
    except KeyError as error:
        raise RegistrationError(f'Nieznana metoda rejestracji: {method}') from error


def graph_requires_deep(method: str) -> bool:
    return method in DEEP_METHODS


def graph_unavailable_reason(method: str, options: DeepMatcherOptions) -> str | None:
    if method not in REGISTRATION_METHODS:
        return f'Nieznana metoda rejestracji: {method}'
    if method == LIGHTGLUE_METHOD:
        return lightglue_unavailable_reason(options)
    if method == MATCHANYTHING_METHOD:
        return matchanything_unavailable_reason(options)
    if method == ROMA_METHOD:
        return roma_unavailable_reason(options)
    if method == EFFICIENT_METHOD:
        return efficient_unavailable_reason(options)
    if method == HYBRID_METHOD:
        return hybrid_unavailable_reason(options)
    if method == LOCAL_METHOD:
        return local_unavailable_reason(options)
    if method == 'deep_matcher_translation':
        return deep_unavailable_reason(options)
    return registration_unavailable_reason(method)
