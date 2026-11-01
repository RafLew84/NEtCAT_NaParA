"""Strict image-free predecessor snapshots, portable across session hosts."""
from dataclasses import asdict, replace
import math
from typing import Callable

from stmviewer.frame import ImageFrame
from stmviewer.graph_application_types import MovieSnapshot, SourceGeometry
from stmviewer.graph_application_metadata import decode_graph_application, encode_graph_application
from stmviewer.graph_metadata import bind_graph_sources, decode_graph_source
from stmviewer.manual_movie_metadata import decode_manual_results, encode_manual_results, manual_frame_state
from stmviewer.manual_movie_types import MovieHistory, MovieSource
from stmviewer.metadata_values import json_object, optional_number, optional_text, source_provenance
from stmviewer.session_diagnostics import (
    decode_local_diagnostics, decode_pair_diagnostics, encode_local_diagnostics, encode_pair_diagnostics,
)
from stmviewer.session_paths import native_path

_KEYS = {'schema', 'sources', 'source_geometry', 'final', 'manual', 'reference', 'canvas_shape',
         'padding_ltrb', 'pixel_size_nm', 'method', 'device', 'corrections_editable',
         'pair_diagnostics', 'local_diagnostics', 'graph_application'}


def encode_movie_snapshot(saved: MovieSnapshot | None,
                          check_cancelled: Callable[[], None]) -> dict[str, object] | None:
    if saved is None:
        return None
    final = MovieHistory(saved.revision, saved.settings_version, saved.final_frames, ())
    manual = (MovieHistory(saved.revision, saved.settings_version, saved.baseline, saved.corrections)
              if saved.baseline else None)
    return {
        'schema': 'stmviewer-movie-snapshot-v1',
        'sources': [asdict(source) for source in saved.sources],
        'source_geometry': saved.source_geometry,
        'final': encode_manual_results((final,), check_cancelled)[0],
        'manual': encode_manual_results((manual,), check_cancelled)[0] if manual else None,
        'reference': asdict(saved.reference), 'canvas_shape': saved.canvas_shape,
        'padding_ltrb': saved.padding_ltrb, 'pixel_size_nm': saved.pixel_size_nm,
        'method': saved.method, 'device': saved.device,
        'corrections_editable': saved.corrections_editable,
        'pair_diagnostics': encode_pair_diagnostics(saved.pair_diagnostics),
        'local_diagnostics': encode_local_diagnostics(saved.local_diagnostics),
        'graph_application': encode_graph_application(saved.graph_application),
    }


def _items(value: object, size: int | None = None) -> list[object]:
    if not isinstance(value, (list, tuple)) or (size is not None and len(value) != size):
        raise ValueError('Zachowany wynik: nieprawidłowa lista lub liczba elementów.')
    return list(value)


def _integers(value: object, size: int, minimum: int) -> list[int]:
    values: list[int] = []
    for item in _items(value, size):
        if type(item) is not int or item < minimum:
            raise ValueError('Zachowany wynik: nieprawidłowa geometria.')
        values.append(item)
    return values


def _geometry(value: object) -> SourceGeometry:
    values = _items(value, 4)
    sx, sy, ox, oy = (optional_number({'n': item}, 'n', positive=index < 2)
                      for index, item in enumerate(values))
    return sx, sy, ox, oy


def _native_source(source: MovieSource) -> MovieSource:
    return replace(source, source=str(native_path(source.source)))


def _history(value: object, check_cancelled: Callable[[], None]) -> MovieHistory:
    history, = decode_manual_results([value], check_cancelled)
    return replace(history,
        baseline=tuple(replace(frame, source=_native_source(frame.source)) for frame in history.baseline),
        corrections=tuple(replace(c, reference=_native_source(c.reference), moving=_native_source(c.moving))
                          for c in history.corrections))


def decode_movie_snapshot(value: object, frames: tuple[ImageFrame, ...],
                          check_cancelled: Callable[[], None]) -> MovieSnapshot | None:
    if value is None:
        return None
    record = json_object(value, _KEYS)
    if record['schema'] != 'stmviewer-movie-snapshot-v1':
        raise ValueError('Zachowany wynik: nieobsługiwana wersja.')
    sources = bind_graph_sources(tuple(decode_graph_source(item) for item in _items(record['sources'])),
                                 frames, check_cancelled, allow_subset=True)
    geometries = tuple(_geometry(item) for item in _items(record['source_geometry'], len(sources)))
    source_ids = tuple(MovieSource(source.source, source.source_frame_index) for source in sources)
    for frame in frames:
        check_cancelled()
        index = source_ids.index(MovieSource(str(frame.source), frame.source_frame_index))
        if geometries[index] != (frame.size_x_nm, frame.size_y_nm, frame.offset_x_nm, frame.offset_y_nm):
            raise ValueError('Zachowany wynik: geometria fizyczna nie odpowiada oryginałom.')
    final = _history(record['final'], check_cancelled)
    if (tuple(item.source for item in final.baseline) != source_ids or final.corrections
            or final.graph_provenance is not None):
        raise ValueError('Zachowany wynik: końcowe pozycje nie odpowiadają źródłom.')
    manual = None if record['manual'] is None else _history(record['manual'], check_cancelled)
    editable = record['corrections_editable']
    if type(editable) is not bool:
        raise ValueError('Zachowany wynik: nieprawidłowa możliwość edycji.')
    reference = source_provenance(record['reference'])
    reference_source = MovieSource(str(native_path(reference.source)), reference.source_frame_index)
    if manual is not None:
        baseline_ids = tuple(item.source for item in manual.baseline)
        if ((manual.revision, manual.settings_version) != (final.revision, final.settings_version)
                or reference_source != baseline_ids[0] or any(source not in baseline_ids for source in source_ids)
                or (editable and source_ids != baseline_ids)
                or tuple(baseline_ids.index(source) for source in source_ids) !=
                   tuple(sorted(baseline_ids.index(source) for source in source_ids))):
            raise ValueError('Zachowany wynik: niezgodna baza lub kolejność korekt.')
        for item in final.baseline:
            if item != manual_frame_state(manual, baseline_ids.index(item.source)):
                raise ValueError('Zachowany wynik: końcowe XY lub pewność nie odpowiadają korektom.')
    height, width = _integers(record['canvas_shape'], 2, 1)
    left, top, right, bottom = _integers(record['padding_ltrb'], 4, 0)
    pixel_size = None
    if record['pixel_size_nm'] is not None:
        coordinates = _items(record['pixel_size_nm'], 2)
        px, py = (optional_number({'n': item}, 'n', positive=True) for item in coordinates)
        if px is None or py is None:
            raise ValueError('Zachowany wynik: skala nie może być null.')
        pixel_size = (px, py)
    for source, geometry, item in zip(sources, geometries, final.baseline, strict=True):
        check_cancelled()
        oh, ow = source.shape
        ox, oy = left + item.shift_xy[0], top + item.shift_xy[1]
        if ((height, width) != (oh + top + bottom, ow + left + right)
                or ox < -1e-9 or oy < -1e-9 or ox + ow > width + 1e-9 or oy + oh > height + 1e-9):
            raise ValueError('Zachowany wynik: końcowe XY wykracza poza geometrię.')
        if pixel_size is not None:
            for actual, expected in zip(geometry[:2], (ow * pixel_size[0], oh * pixel_size[1])):
                if actual is None or not math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9):
                    raise ValueError('Zachowany wynik: skala nie odpowiada oryginałom.')
    method, device = optional_text(record, 'method'), optional_text(record, 'device')
    if not method or not method.strip() or not device or not device.strip():
        raise ValueError('Zachowany wynik: brak metody lub urządzenia.')
    application = decode_graph_application(record['graph_application'], frames,
        manual.baseline if manual else (), check_cancelled, allow_subset=True)
    if application is not None and (method != f'Deep Matcher — graf {application.solver}'
                                    or device != application.graph.config.device):
        raise ValueError('Zachowany wynik: opis metody nie odpowiada grafowi.')
    return MovieSnapshot(sources, geometries, final.baseline, reference_source,
        (height, width), (left, top, right, bottom), pixel_size, method, device,
        final.settings_version, final.revision, manual.baseline if manual else (),
        manual.corrections if manual else (), editable,
        decode_pair_diagnostics(record['pair_diagnostics'], len(sources)),
        decode_local_diagnostics(record['local_diagnostics'], len(sources)), application)
