"""Whitelisted JSON codecs for the small diagnostics retained with an alignment."""
from dataclasses import asdict
from typing import Literal

from stmviewer.deep_ecc import HybridDiagnostics
from stmviewer.local_consensus import LocalDiagnostics, LocalPatchEvidence
from stmviewer.metadata_values import json_object, optional_number, optional_text

_HYBRID = {'deep_shift_xy', 'final_shift_xy', 'correction_xy', 'deep_status',
           'deep_quality_score', 'ecc_status', 'ecc_score', 'settings_text', 'weights',
           'requested_device', 'actual_device', 'settings_version'}
_LOCAL = {'deep_shift_xy', 'final_shift_xy', 'patches', 'status', 'reason', 'settings_text',
          'weights', 'requested_device', 'actual_device', 'deep_status', 'deep_quality_score',
          'settings_version'}
_PATCH = {'reference_rect', 'moving_rect', 'shift_xy', 'score', 'peak_margin', 'status',
          'reason', 'peak_contrast'}


def _items(value: object) -> list[object]:
    if not isinstance(value, (list, tuple)):
        raise ValueError('Sesja: diagnostyka wymaga listy.')
    return list(value)


def _text(record: dict[str, object], key: str) -> str:
    value = optional_text(record, key)
    if value is None:
        raise ValueError('Sesja: tekst diagnostyki nie może być null.')
    return value


def _number(record: dict[str, object], key: str) -> float:
    value = optional_number(record, key)
    if value is None:
        raise ValueError('Sesja: liczba diagnostyki nie może być null.')
    return value


def _numbers(value: object, length: int) -> list[float]:
    items = _items(value)
    if len(items) != length:
        raise ValueError('Sesja: nieprawidłowy rozmiar wektora diagnostyki.')
    return [_number({'value': item}, 'value') for item in items]


def _xy(value: object) -> tuple[float, float]:
    x, y = _numbers(value, 2)
    return x, y


def _version(record: dict[str, object]) -> int:
    value = record['settings_version']
    if type(value) is not int or value != 1:
        raise ValueError('Sesja: nieobsługiwana wersja diagnostyki.')
    return value


def encode_pair_diagnostics(values: tuple[HybridDiagnostics | None, ...]) -> list[object]:
    return [asdict(item) if item is not None else None for item in values]


def decode_pair_diagnostics(value: object, count: int) -> tuple[HybridDiagnostics | None, ...]:
    records = _items(value)
    if len(records) not in (0, count):
        raise ValueError('Sesja: diagnostyka par ma inną liczbę klatek.')
    result: list[HybridDiagnostics | None] = []
    for item in records:
        if item is None:
            result.append(None)
            continue
        record = json_object(item, _HYBRID)
        result.append(HybridDiagnostics(
            _xy(record['deep_shift_xy']), _xy(record['final_shift_xy']), _xy(record['correction_xy']),
            _text(record, 'deep_status'), _number(record, 'deep_quality_score'),
            _text(record, 'ecc_status'), _number(record, 'ecc_score'),
            _text(record, 'settings_text'), _text(record, 'weights'),
            _text(record, 'requested_device'), _text(record, 'actual_device'), _version(record)))
    return tuple(result)


def _patch(value: object) -> LocalPatchEvidence:
    record = json_object(value, _PATCH)
    rect = _items(record['reference_rect'])
    if len(rect) != 4 or any(type(item) is not int for item in rect):
        raise ValueError('Sesja: prostokąt diagnostyki musi mieć cztery całkowite współrzędne.')
    x, y, width, height = rect
    assert isinstance(x, int) and isinstance(y, int) and isinstance(width, int) and isinstance(height, int)
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise ValueError('Sesja: nieprawidłowy prostokąt diagnostyki.')
    moving = None
    if record['moving_rect'] is not None:
        mx, my, mw, mh = _numbers(record['moving_rect'], 4)
        if mw <= 0 or mh <= 0:
            raise ValueError('Sesja: nieprawidłowy ruchomy prostokąt diagnostyki.')
        moving = (mx, my, mw, mh)
    status = record['status']
    if status not in ('inlier', 'outlier', 'unmatched'):
        raise ValueError('Sesja: nieznany status fragmentu diagnostyki.')
    # Narrow the allowed literal values without constructing arbitrary classes from JSON.
    label: Literal['inlier', 'outlier', 'unmatched']
    if status == 'inlier':
        label = 'inlier'
    elif status == 'outlier':
        label = 'outlier'
    else:
        label = 'unmatched'
    return LocalPatchEvidence((x, y, width, height), moving,
                              None if record['shift_xy'] is None else _xy(record['shift_xy']),
                              optional_number(record, 'score'), optional_number(record, 'peak_margin'),
                              label, _text(record, 'reason'), optional_number(record, 'peak_contrast'))


def encode_local_diagnostics(values: tuple[LocalDiagnostics | None, ...]) -> list[object]:
    return [asdict(item) if item is not None else None for item in values]


def decode_local_diagnostics(value: object, count: int) -> tuple[LocalDiagnostics | None, ...]:
    records = _items(value)
    if len(records) not in (0, count):
        raise ValueError('Sesja: lokalna diagnostyka ma inną liczbę klatek.')
    result: list[LocalDiagnostics | None] = []
    for item in records:
        if item is None:
            result.append(None)
            continue
        record = json_object(item, _LOCAL)
        result.append(LocalDiagnostics(
            _xy(record['deep_shift_xy']),
            None if record['final_shift_xy'] is None else _xy(record['final_shift_xy']),
            tuple(_patch(patch) for patch in _items(record['patches'])),
            _text(record, 'status'), _text(record, 'reason'), _text(record, 'settings_text'),
            _text(record, 'weights'), _text(record, 'requested_device'),
            _text(record, 'actual_device'), _text(record, 'deep_status'),
            optional_number(record, 'deep_quality_score'), _version(record)))
    return tuple(result)
