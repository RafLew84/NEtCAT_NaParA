"""Method identity and availability, shared by graph presentation and execution."""

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
    if method == HYBRID_METHOD:
        return hybrid_unavailable_reason(options)
    if method == LOCAL_METHOD:
        return local_unavailable_reason(options)
    if method == 'deep_matcher_translation':
        return deep_unavailable_reason(options)
    return registration_unavailable_reason(method)
