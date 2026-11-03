"""Strict primitive validation shared by versioned MPP metadata codecs."""

import math
from typing import Mapping

from stmviewer.frame import FrameProvenance


def json_object(value: object, keys: set[str] | None = None) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError('Oczekiwano obiektu JSON.')
    result: dict[str, object] = dict(value)
    if keys is not None and result.keys() != keys:
        raise ValueError(f'Pola JSON: brak {sorted(keys - result.keys())}; '
                         f'nieobsługiwane {sorted(result.keys() - keys)}.')
    return result


def optional_number(record: dict[str, object], key: str, *, positive: bool = False) -> float | None:
    value = record[key]
    if value is None:
        return None
    if type(value) not in (int, float):
        raise ValueError(f'{key}: wymagana liczba albo null.')
    assert isinstance(value, (int, float))
    number = float(value)
    if not math.isfinite(number) or (positive and number <= 0):
        raise ValueError(f'{key}: wymagana skończona {"dodatnia " if positive else ""}liczba.')
    return number


def optional_text(record: dict[str, object], key: str) -> str | None:
    value = record[key]
    if value is not None and not isinstance(value, str):
        raise ValueError(f'{key}: wymagany tekst albo null.')
    return value


def source_header(value: object) -> Mapping[str, str | Mapping[str, str]]:
    result: dict[str, str | Mapping[str, str]] = {}
    for key, entry in json_object(value).items():
        if isinstance(entry, str):
            result[key] = entry
        else:
            section: dict[str, str] = {}
            for name, item in json_object(entry).items():
                if not isinstance(item, str):
                    raise ValueError('raw_header: wartości nagłówka muszą być tekstem.')
                section[name] = item
            result[key] = section
    return result



def source_provenance(value: object) -> FrameProvenance:
    """Both provenance and historical reference use the same portable source contract."""
    record = json_object(value, {'source', 'source_frame_index'})
    source = optional_text(record, 'source')
    index = record['source_frame_index']
    if source is None or not source.strip() or '\x00' in source:
        raise ValueError('provenance.source: wymagany niepusty opis źródła.')
    if index is not None and (type(index) is not int or index < 0):
        raise ValueError('source_frame_index: wymagany indeks od zera albo null.')
    assert index is None or isinstance(index, int)
    return FrameProvenance(source, index)
