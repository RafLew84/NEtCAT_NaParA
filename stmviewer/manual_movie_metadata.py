"""Portable manual movie provenance, stored once per result in an MPP sidecar."""
from dataclasses import asdict
import math
from typing import Callable

from stmviewer.manual_movie_types import (
    MovieBaselineFrame, MovieCorrection, MovieHistory, MovieSource,
)
from stmviewer.metadata_values import json_object, optional_number, optional_text


def _xy(value: object, *, integer: bool = False) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError('Korekta filmu: wymagane dwie współrzędne.')
    numbers = []
    for item in value:
        if integer and type(item) is not int:
            raise ValueError('Korekta filmu: ruchy ręczne muszą być całkowite.')
        number = optional_number({'coordinate': item}, 'coordinate')
        if number is None:
            raise ValueError('Korekta filmu: współrzędna nie może być null.')
        numbers.append(number)
    return numbers[0], numbers[1]


def _source(value: object) -> MovieSource:
    record = json_object(value, {'source', 'source_frame_index'})
    text = optional_text(record, 'source')
    index = record['source_frame_index']
    if text is None or not text.strip() or '\x00' in text:
        raise ValueError('Korekta filmu: wymagane źródło klatki.')
    if index is not None and (type(index) is not int or index < 0):
        raise ValueError('Korekta filmu: nieprawidłowy indeks źródłowy.')
    assert isinstance(index, int) or index is None
    return MovieSource(text, index)


def _version(record: dict[str, object]) -> int:
    value = record['settings_version']
    if type(value) is not int or value != 1:
        raise ValueError('Nieobsługiwana wersja ustawień korekty filmu.')
    return value


def _baseline(value: object) -> MovieBaselineFrame:
    record = json_object(value, {'source', 'shift_xy', 'status', 'quality_score',
                                 'inherited_uncertainty'})
    status = optional_text(record, 'status')
    quality = optional_number(record, 'quality_score')
    inherited = record['inherited_uncertainty']
    if status not in ('ok', 'low_confidence', 'manual_review'):
        raise ValueError('Korekta filmu: nieprawidłowy status bazowy.')
    if (quality is None and status != 'manual_review') or (quality is not None and not 0 <= quality <= 1):
        raise ValueError('Korekta filmu: nieprawidłowa pewność bazowa.')
    if type(inherited) is not bool:
        raise ValueError('Korekta filmu: nieprawidłowa odziedziczona niepewność.')
    return MovieBaselineFrame(_source(record['source']), _xy(record['shift_xy']),
                              status, quality, inherited)


def _correction(value: object) -> MovieCorrection:
    record = json_object(value, {'reference', 'moving', 'baseline_xy', 'start_xy',
                                 'correction_xy', 'source_label', 'shift_xy', 'settings_version'})
    start, shift = _xy(record['start_xy']), _xy(record['shift_xy'])
    dx, dy = _xy(record['correction_xy'], integer=True)
    if not all(math.isclose(a + b, c, rel_tol=1e-9, abs_tol=1e-9)
               for a, b, c in zip(start, (dx, dy), shift)):
        raise ValueError('Korekta filmu: wynik nie zgadza się z początkiem i ruchami.')
    reference, moving = _source(record['reference']), _source(record['moving'])
    if reference == moving:
        raise ValueError('Korekta filmu: para wymaga dwóch różnych źródeł.')
    return MovieCorrection(reference, moving, _xy(record['baseline_xy']), start,
                           (int(dx), int(dy)), optional_text(record, 'source_label'),
                           shift, _version(record))


def decode_manual_results(value: object, check_cancelled: Callable[[], None]) -> tuple[MovieHistory, ...]:
    """Validate each shared history before any metadata is published."""
    if not isinstance(value, list) or not value:
        raise ValueError('V4 wymaga niepustej listy historii korekt filmu.')
    results = []
    revisions: set[str] = set()
    for item in value:
        check_cancelled()
        has_graph = isinstance(item, dict) and 'graph_provenance' in item
        record = json_object(item, {'revision', 'settings_version', 'baseline', 'corrections'}
                             | ({'graph_provenance'} if has_graph else set()))
        revision = optional_text(record, 'revision')
        if not revision or not revision.strip() or revision in revisions:
            raise ValueError('Korekta filmu: pusta lub powtórzona wersja wyniku.')
        revisions.add(revision)
        baseline_values, correction_values = record['baseline'], record['corrections']
        if not isinstance(baseline_values, (list, tuple)) or not baseline_values:
            raise ValueError('Korekta filmu: wymagana baza klatek.')
        if not isinstance(correction_values, (list, tuple)):
            raise ValueError('Korekta filmu: wymagany zestaw nadpisań par.')
        baseline = []
        for frame in baseline_values:
            check_cancelled()
            baseline.append(_baseline(frame))
        if len({frame.source for frame in baseline}) != len(baseline):
            raise ValueError('Korekta filmu: powtórzone źródło w bazie.')
        corrections = []
        for correction in correction_values:
            check_cancelled()
            corrections.append(_correction(correction))
        if len({correction.moving for correction in corrections}) != len(corrections):
            raise ValueError('Korekta filmu: powtórzone nadpisanie tej samej pary.')
        provenance = None
        if has_graph:
            from stmviewer.graph_movie_provenance import decode_graph_movie_provenance
            provenance = decode_graph_movie_provenance(record['graph_provenance'])
        history = MovieHistory(revision, _version(record), tuple(baseline), tuple(corrections), provenance)
        _validate_manual_result(history)
        results.append(history)
    return tuple(results)


def encode_manual_results(results: tuple[MovieHistory, ...],
                          check_cancelled: Callable[[], None]) -> list[dict[str, object]]:
    """Write small immutable metadata, with no pixel buffers or edit snapshots."""
    records = []
    for result in results:
        check_cancelled()
        record = asdict(result)
        if result.graph_provenance is None:
            record.pop('graph_provenance')
        records.append(record)
    decode_manual_results(records, check_cancelled)
    return records


def _validate_manual_result(history: MovieHistory) -> None:
    graph = history.graph_provenance
    if graph is not None:
        if (len(graph.final_positions) != len(history.baseline)
                or history.baseline[0].shift_xy != (0., 0.)
                or any(frame.status != 'manual_review' or frame.quality_score is not None
                       or frame.inherited_uncertainty for frame in history.baseline)
                or graph.final_positions != tuple(manual_frame_state(history, i).shift_xy
                                                 for i in range(len(history.baseline)))):
            raise ValueError('Graf: pochodzenie nie odpowiada bazie i końcowym korektom filmu.')
    indices = {frame.source: i for i, frame in enumerate(history.baseline)}
    for correction in history.corrections:
        reference = indices.get(correction.reference)
        moving = indices.get(correction.moving)
        if reference is None or moving is None or moving != reference + 1:
            raise ValueError('Korekta filmu: nadpisanie nie dotyczy sąsiedniej pary bazy.')
        before, after = history.baseline[reference], history.baseline[moving]
        if not all(math.isclose(actual, right - left, rel_tol=1e-9, abs_tol=1e-9)
                   for actual, left, right in zip(correction.baseline_xy, before.shift_xy, after.shift_xy)):
            raise ValueError('Korekta filmu: bazowe XY pary nie zgadza się z bazą filmu.')


def manual_frame_state(history: MovieHistory, index: int) -> MovieBaselineFrame:
    """Expected historical state, including corrections whose source was deleted."""
    base = history.baseline[index]
    overrides = {correction.moving: correction for correction in history.corrections}
    dx = dy = 0.0
    affected = inherited = False
    for position, frame in enumerate(history.baseline):
        if position > index:
            break
        correction = overrides.get(frame.source)
        if correction is not None:
            dx += correction.shift_xy[0] - correction.baseline_xy[0]
            dy += correction.shift_xy[1] - correction.baseline_xy[1]
            affected = True
            inherited = inherited or position < index
    return MovieBaselineFrame(
        base.source, (base.shift_xy[0] + dx, base.shift_xy[1] + dy),
        'manual_review' if affected else base.status, None if affected else base.quality_score,
        inherited or base.inherited_uncertainty,
    )
