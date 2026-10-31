"""Structural and numerical validation of lightweight trial payloads."""

from math import isfinite, isclose
from typing import Any


def object_record(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f'{label}: wymagany obiekt.')
    return value


def integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f'{label}: wymagany indeks całkowity ≥ {minimum}.')
    return value


def number(value: Any, label: str) -> float:
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError(f'{label}: wymagana skończona liczba.')
    return float(value)


def xy(value: Any, label: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f'{label}: wymagane dwie współrzędne XY.')
    for coordinate in value:
        number(coordinate, label)


def _json_values(value: Any, depth: int = 0) -> None:
    if depth > 32:
        raise ValueError('Próba: zbyt głęboka struktura danych.')
    if isinstance(value, dict):
        object_record(value, 'Próba')
        for item in value.values():
            _json_values(item, depth + 1)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _json_values(item, depth + 1)
    elif type(value) in (int, float):
        number(value, 'Próba')
    elif value is not None and type(value) not in (str, bool):
        raise ValueError('Próba może zawierać tylko metadane JSON, bez obrazów.')


def validate_payload(value: Any, *, frame_count: int) -> dict[str, Any]:
    payload = object_record(value, 'Próba')
    _json_values(payload)
    required = {'kind', 'outcome', 'frame_count', 'reference_index', 'method', 'label',
                'settings_text', 'settings', 'device', 'error', 'manual_movie', 'records',
                'code_revision'}
    if not required <= payload.keys():
        raise ValueError('Próba: brak wymaganych pól dokumentu.')
    kind, outcome = payload['kind'], payload['outcome']
    if kind not in ('pair', 'series') or outcome not in ('complete', 'failed', 'cancelled'):
        raise ValueError('Próba: nieznany rodzaj lub stan wyniku.')
    count = integer(payload['frame_count'], 'Liczba klatek', minimum=1)
    if count != frame_count:
        raise ValueError('Próba: liczba klatek nie odpowiada źródłom.')
    if integer(payload['reference_index'], 'Odniesienie') >= count:
        raise ValueError('Próba: odniesienie poza serią.')
    for key in ('method', 'label', 'settings_text', 'device', 'code_revision'):
        if not isinstance(payload[key], str):
            raise ValueError(f'Próba: {key} musi być tekstem.')
    object_record(payload['settings'], 'Ustawienia')
    if payload['error'] is not None and not isinstance(payload['error'], str):
        raise ValueError('Próba: błąd musi być tekstem lub null.')
    if outcome == 'complete' and payload['error'] is not None:
        raise ValueError('Próba kompletna nie może zawierać błędu.')
    records = payload['records']
    if not isinstance(records, list) or len(records) > count:
        raise ValueError('Próba: nieprawidłowa lista wyników.')
    seen: set[int] = set()
    for record in records:
        record = object_record(record, 'Wynik klatki')
        fields = {'index', 'cumulative_xy', 'shift_xy', 'status', 'quality_score',
                  'inherited_uncertainty', 'hybrid', 'local', 'manual'}
        if not fields <= record.keys():
            raise ValueError('Próba: niepełny rekord wyniku.')
        index = integer(record['index'], 'Indeks wyniku')
        if index >= count or index in seen:
            raise ValueError('Próba: powtórzony indeks lub wynik poza serią.')
        seen.add(index)
        xy(record['cumulative_xy'], 'Skumulowane XY', optional=True)
        xy(record['shift_xy'], 'XY pary', optional=True)
        status, quality = record['status'], record['quality_score']
        if status not in ('ok', 'low_confidence', 'manual_review', 'manual', 'failed', 'cancelled'):
            raise ValueError('Próba: nieznany status klatki.')
        if quality is not None and not 0 <= number(quality, 'Jakość') <= 1:
            raise ValueError('Próba: jakość poza zakresem 0–1.')
        if 'pair_status' in record or 'pair_quality_score' in record:
            if not {'pair_status', 'pair_quality_score'} <= record.keys():
                raise ValueError('Próba: niepełna ocena pary.')
            pair_status, pair_quality = record['pair_status'], record['pair_quality_score']
            if pair_status not in (None, 'ok', 'low_confidence', 'manual_review', 'manual', 'failed', 'cancelled'):
                raise ValueError('Próba: nieznany status pary.')
            if pair_quality is not None and not 0 <= number(pair_quality, 'Jakość pary') <= 1:
                raise ValueError('Próba: jakość pary poza zakresem 0–1.')
            if pair_status in (None, 'manual', 'failed', 'cancelled') and pair_quality is not None:
                raise ValueError('Próba: ta para nie ma automatycznej oceny jakości.')
        if status in ('manual', 'failed', 'cancelled') and quality is not None:
            raise ValueError('Próba ręczna lub przerwana nie ma oceny automatycznej.')
        from stmviewer.trial_evidence import validate_evidence
        validate_evidence(record)
        if record['manual'] is not None:
            _manual_record(record, kind)
        if type(record['inherited_uncertainty']) is not bool:
            raise ValueError('Próba: nieprawidłowa odziedziczona niepewność.')
        if outcome == 'complete' and (status in ('failed', 'cancelled') or
                record['cumulative_xy' if kind == 'series' else 'shift_xy'] is None):
            raise ValueError('Próba kompletna wymaga wszystkich wyników XY.')
    if kind == 'series':
        if [r['index'] for r in records] != list(range(len(records))):
            raise ValueError('Próba: nieprawidłowa kolejność klatek wynikowych.')
        if outcome == 'complete' and len(records) != count:
            raise ValueError('Próba kompletna wymaga wyników wszystkich klatek.')
        for previous, current in zip(records, records[1:]):
            if current['cumulative_xy'] is not None:
                if previous['cumulative_xy'] is None or current['shift_xy'] is None:
                    raise ValueError('Próba: skumulowane XY wymaga pełnego łańcucha par.')
                if not all(isclose(a + b, c, rel_tol=1e-9, abs_tol=1e-9) for a, b, c in zip(
                        previous['cumulative_xy'], current['shift_xy'], current['cumulative_xy'])):
                    raise ValueError('Próba: skumulowane XY nie zgadza się z wynikami par.')
    elif (len(records) > 1 or (outcome == 'complete' and len(records) != 1)
          or any(r['index'] != payload['reference_index'] + 1 for r in records)):
        raise ValueError('Próba pary wymaga różnych klatek i jednego wyniku.')
    if payload['manual_movie'] is not None:
        from stmviewer.manual_movie_metadata import decode_manual_results, manual_frame_state
        if kind != 'series' or outcome != 'complete':
            raise ValueError('Historia korekt filmu wymaga kompletnej próby serii.')
        history = decode_manual_results([payload['manual_movie']], lambda: None)[0]
        if len(history.baseline) == count:
            for index, record in enumerate(records):
                expected = manual_frame_state(history, index)
                if (not all(isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
                            for a, b in zip(expected.shift_xy, record['cumulative_xy']))
                        or record['quality_score'] != expected.quality_score
                        or record['status'] != expected.status):
                    raise ValueError('Korekta filmu: wynik nie odpowiada zapisanej historii.')
    return payload


def _manual_record(record: dict[str, Any], kind: str) -> None:
    manual = object_record(record['manual'], 'Korekta ręczna')
    fields = {'start_xy', 'correction_xy', 'source_label', 'settings_version'}
    if kind == 'series':
        fields |= {'reference', 'moving', 'baseline_xy', 'shift_xy'}
    if set(manual) != fields:
        raise ValueError('Korekta ręczna: nieprawidłowe pola pochodzenia.')
    if manual['settings_version'] != 1 or type(manual['settings_version']) is not int:
        raise ValueError('Nieobsługiwana wersja korekty ręcznej.')
    xy(manual['start_xy'], 'Początek korekty ręcznej')
    xy(manual['correction_xy'], 'Korekta ręczna')
    if not all(type(value) is int for value in manual['correction_xy']):
        raise ValueError('Korekta ręczna: ruchy muszą być całkowite.')
    if manual['source_label'] is not None and not isinstance(manual['source_label'], str):
        raise ValueError('Korekta ręczna: nieprawidłowy opis pochodzenia.')
    shift = record['shift_xy']
    if (shift is None or record['quality_score'] is not None
            or record['status'] not in ('manual', 'manual_review')):
        raise ValueError('Korekta ręczna wymaga XY i braku automatycznej oceny jakości.')
    if not all(isclose(a + b, c, rel_tol=1e-9, abs_tol=1e-9)
               for a, b, c in zip(manual['start_xy'], manual['correction_xy'], shift)):
        raise ValueError('Korekta ręczna: wynik nie zgadza się z początkiem i ruchami.')
