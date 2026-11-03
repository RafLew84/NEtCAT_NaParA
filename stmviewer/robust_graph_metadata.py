"""Strict, versioned Huber results; all pixels and raw measurements live elsewhere."""
from dataclasses import asdict

from stmviewer.graph_types import XY
from stmviewer.metadata_values import json_object, optional_number
from stmviewer.robust_graph_types import RobustConfig, RobustTrial

_CONFIG_KEYS = {
    'threshold_px', 'max_iterations', 'position_tolerance_px',
    'objective_relative_tolerance', 'gradient_tolerance', 'max_condition',
    'solver', 'condition_method',
}
_TRIAL_KEYS = {
    'schema', 'measurement_id', 'config', 'positions', 'last_positions', 'residuals',
    'weights', 'status', 'reason', 'iterations', 'objective', 'ls_objective',
    'max_step_px', 'relative_cost_change', 'gradient_inf', 'condition_estimate',
    'solver_s', 'revision',
}


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        raise ValueError('Huber: wymagany niepusty tekst.')
    return value


def _items(value: object) -> list[object]:
    if not isinstance(value, (tuple, list)):
        raise ValueError('Huber: wymagana lista.')
    return list(value)


def _integer(value: object, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError('Huber: nieprawidłowa liczba całkowita.')
    return value


def _number(value: object, *, positive: bool = False) -> float:
    result = optional_number({'value': value}, 'value', positive=positive)
    if result is None:
        raise ValueError('Huber: wymagana skończona liczba.')
    return result


def _xy(value: object) -> XY:
    items = _items(value)
    if len(items) != 2:
        raise ValueError('Huber: wymagane dwie współrzędne.')
    return _number(items[0]), _number(items[1])


def _positions(value: object) -> tuple[XY, ...] | None:
    return None if value is None else tuple(_xy(item) for item in _items(value))


def _config(value: object) -> RobustConfig:
    record = json_object(value, _CONFIG_KEYS)
    return RobustConfig(
        threshold_px=_number(record['threshold_px'], positive=True),
        max_iterations=_integer(record['max_iterations'], 1),
        position_tolerance_px=_number(record['position_tolerance_px'], positive=True),
        objective_relative_tolerance=_number(record['objective_relative_tolerance'], positive=True),
        gradient_tolerance=_number(record['gradient_tolerance'], positive=True),
        max_condition=_number(record['max_condition'], positive=True),
        solver=_text(record['solver']), condition_method=_text(record['condition_method']),
    )


def encode_robust_trial(trial: RobustTrial) -> dict[str, object]:
    return {'schema': 'stmviewer-robust-graph-v1', **asdict(trial)}


def decode_robust_trial(value: object) -> RobustTrial:
    record = json_object(value, _TRIAL_KEYS)
    if record['schema'] != 'stmviewer-robust-graph-v1':
        raise ValueError('Nieobsługiwana wersja wyniku Hubera w sesji.')
    return RobustTrial(
        measurement_id=_text(record['measurement_id']), config=_config(record['config']),
        positions=_positions(record['positions']), last_positions=_positions(record['last_positions']),
        residuals=tuple(None if item is None else _xy(item) for item in _items(record['residuals'])),
        weights=tuple(optional_number({'weight': item}, 'weight') for item in _items(record['weights'])),
        status=_text(record['status']), reason=_text(record['reason']),
        iterations=_integer(record['iterations']),
        objective=optional_number(record, 'objective'), ls_objective=optional_number(record, 'ls_objective'),
        max_step_px=optional_number(record, 'max_step_px'),
        relative_cost_change=optional_number(record, 'relative_cost_change'),
        gradient_inf=optional_number(record, 'gradient_inf'),
        condition_estimate=optional_number(record, 'condition_estimate'),
        solver_s=_number(record['solver_s']), revision=_text(record['revision']),
    )
