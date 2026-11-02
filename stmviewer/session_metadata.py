"""Strict JSON metadata for a session; array payloads are stored by the archive."""
from dataclasses import asdict, replace
from pathlib import Path
from typing import Callable, Mapping

import numpy as np
from numpy.typing import NDArray

from stmviewer.graph_methods import graph_method_label
from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.correspondence_metadata import (
    decode_correspondence_diagnostics, encode_correspondence_diagnostics, validate_correspondence_shape, validate_correspondence_method,
)
from stmviewer.alignment_metadata import (
    aligned_export_frames, collect_manual_histories, decode_alignment, encode_alignment,
)
from stmviewer.frame import ImageFrame
from stmviewer.graph_metadata import decode_graph, encode_graph
from stmviewer.graph_movie_provenance import movie_history
from stmviewer.movie_snapshot_metadata import decode_movie_snapshot, encode_movie_snapshot
from stmviewer.graph_application_metadata import decode_graph_application, encode_graph_application
from stmviewer import session_paths
from stmviewer.manual_movie_metadata import decode_manual_results, encode_manual_results, manual_frame_state
from stmviewer.manual_movie_types import MovieHistory, MovieSource
from stmviewer.metadata_values import json_object, optional_number, optional_text, source_header, source_provenance
from stmviewer.registration import REGISTRATION_METHODS, AlignedFrame, FrameOrigin, RegistrationResult
from stmviewer.session_diagnostics import (
    decode_local_diagnostics, decode_pair_diagnostics, encode_local_diagnostics, encode_pair_diagnostics,
)
from stmviewer.session_state import SessionState, SessionViewState, ViewTransform

_ROOT_KEYS = {'schema', 'frames', 'registration', 'display', 'manual_histories'}
_FRAME_KEYS = {
    'array', 'shape', 'source', 'raw_header', 'channel', 'signal_unit', 'size_x_nm',
    'size_y_nm', 'offset_x_nm', 'offset_y_nm', 'bias_v', 'setpoint_a', 'scan_angle_deg',
    'calibration_note', 'source_frame_index', 'measurement_time_s', 'measurement_time_raw',
    'provenance', 'metadata_note', 'alignment',
}
_REGISTRATION_KEYS = {
    'frames', 'image_alignments', 'reference', 'canvas_shape', 'padding_ltrb', 'pixel_size_nm',
    'method', 'device', 'settings_version', 'revision', 'manual_state', 'corrections_editable',
    'pair_diagnostics', 'local_diagnostics',
}
_DISPLAY_KEYS = {
    'index', 'view', 'gamma', 'pixel_proportions', 'fps', 'loop', 'method',
    'deep_weights', 'deep_device', 'navigation',
}


def _noop() -> None:
    pass


def _sequence(value: object) -> list[object]:
    if not isinstance(value, (list, tuple)):
        raise ValueError('Sesja: oczekiwano listy.')
    return list(value)


def _integer(value: object, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError('Sesja: nieprawidłowa liczba całkowita.')
    return value


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise ValueError('Sesja: oczekiwano wartości logicznej.')
    return value


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        raise ValueError('Sesja: wymagany niepusty tekst.')
    return value


def _xy(value: object) -> tuple[float, float]:
    values = _sequence(value)
    if len(values) != 2:
        raise ValueError('Sesja: wymagane dwie współrzędne.')
    x = optional_number({'x': values[0]}, 'x')
    y = optional_number({'y': values[1]}, 'y')
    if x is None or y is None:
        raise ValueError('Sesja: współrzędne nie mogą być null.')
    return x, y


def _shape(value: object) -> tuple[int, int]:
    values = _sequence(value)
    if len(values) != 2:
        raise ValueError('Sesja: wymagany dwuwymiarowy obraz.')
    return _integer(values[0], 1), _integer(values[1], 1)


def _root(value: object) -> dict[str, object]:
    record = json_object(value)
    if record.get('schema') == 'stmviewer-state-v1':
        return json_object(record, _ROOT_KEYS)
    if record.get('schema') in ('stmviewer-state-v2', 'stmviewer-state-v3', 'stmviewer-state-v4', 'stmviewer-state-v5', 'stmviewer-state-v6'):
        return json_object(record, _ROOT_KEYS | {'graph'})
    raise ValueError('Nieobsługiwana wersja stanu sesji.')


def _frame_records(value: object, prefix: str) -> list[dict[str, object]]:
    records = []
    for index, item in enumerate(_sequence(value)):
        record = json_object(item, _FRAME_KEYS)
        if record['array'] != f'{prefix}/{index:06d}.npy':
            raise ValueError('Sesja: nieprawidłowa nazwa obrazu.')
        _shape(record['shape'])
        records.append(record)
    if not records:
        raise ValueError('Sesja wymaga przynajmniej jednej klatki.')
    return records


def session_array_shapes(manifest: object) -> dict[str, tuple[int, int]]:
    """Validate names/counts/dimensions before the archive allocates pixel buffers."""
    root = _root(manifest)
    originals = _frame_records(root['frames'], 'original')
    shapes = {_text(frame['array']): _shape(frame['shape']) for frame in originals}
    if len(set(shapes.values())) != 1:
        raise ValueError('Sesja: klatki original mają różne wymiary.')
    if root['registration'] is not None:
        registration = _registration_object(root['registration'])
        aligned = _frame_records(registration.get('frames'), 'aligned')
        if len(originals) != len(aligned):
            raise ValueError('Sesja: liczba obrazów aligned nie odpowiada original.')
        canvas = _shape(registration.get('canvas_shape'))
        for frame in aligned:
            if _shape(frame['shape']) != canvas:
                raise ValueError('Sesja: rozmiar aligned nie odpowiada obszarowi filmu.')
            shapes[_text(frame['array'])] = canvas
    return shapes


def _encode_frame(frame: ImageFrame, name: str, manual_ids: dict[str, int]) -> dict[str, object]:
    return {
        'array': name, 'shape': list(frame.data.shape), 'source': str(frame.source),
        'raw_header': dict(frame.raw_header), 'channel': frame.channel,
        'signal_unit': frame.signal_unit, 'size_x_nm': frame.size_x_nm,
        'size_y_nm': frame.size_y_nm, 'offset_x_nm': frame.offset_x_nm,
        'offset_y_nm': frame.offset_y_nm, 'bias_v': frame.bias_v,
        'setpoint_a': frame.setpoint_a, 'scan_angle_deg': frame.scan_angle_deg,
        'calibration_note': frame.calibration_note, 'source_frame_index': frame.source_frame_index,
        'measurement_time_s': frame.measurement_time_s,
        'measurement_time_raw': frame.measurement_time_raw,
        'provenance': asdict(frame.provenance) if frame.provenance is not None else None,
        'metadata_note': frame.metadata_note,
        'alignment': encode_alignment(frame.alignment, manual_ids=manual_ids),
    }


def _decode_frame(record: dict[str, object], arrays: Mapping[str, NDArray[np.float64]],
                  histories: tuple[MovieHistory, ...]) -> ImageFrame:
    data = arrays[_text(record['array'])]
    if (not isinstance(data, np.ndarray) or data.dtype != np.dtype(np.float64)
            or data.shape != _shape(record['shape'])):
        raise ValueError('Sesja: typ lub wymiary obrazu nie odpowiadają metadanym.')
    # A read-only view preserves the caller's array ownership and never copies samples.
    data = data.view()
    data.setflags(write=False)
    source = source_provenance({'source': record['source'], 'source_frame_index': record['source_frame_index']})
    provenance = None if record['provenance'] is None else source_provenance(record['provenance'])
    native_source = session_paths.native_path(source.source)
    if provenance is None and str(native_source) != source.source:
        provenance = source
    frame = ImageFrame(
        source=native_source, data=data, raw_header=source_header(record['raw_header']),
        channel=optional_text(record, 'channel'), signal_unit=optional_text(record, 'signal_unit'),
        size_x_nm=optional_number(record, 'size_x_nm', positive=True),
        size_y_nm=optional_number(record, 'size_y_nm', positive=True),
        offset_x_nm=optional_number(record, 'offset_x_nm'), offset_y_nm=optional_number(record, 'offset_y_nm'),
        bias_v=optional_number(record, 'bias_v'), setpoint_a=optional_number(record, 'setpoint_a'),
        scan_angle_deg=optional_number(record, 'scan_angle_deg'),
        calibration_note=optional_text(record, 'calibration_note'), source_frame_index=source.source_frame_index,
        measurement_time_s=optional_number(record, 'measurement_time_s'),
        measurement_time_raw=optional_text(record, 'measurement_time_raw'), provenance=provenance,
        metadata_note=optional_text(record, 'metadata_note'),
    )
    if record['alignment'] is not None:
        frame = replace(frame, alignment=decode_alignment(record['alignment'], frame, manual_results=histories))
    return frame


def _decode_roma_options(value: object) -> DeepMatcherOptions | None:
    """Remember the optional model's controls without opening paths or running Python."""
    if value is None:
        return None
    record = json_object(value, {'weights', 'device', 'source', 'interpreter', 'preset', 'samples', 'seed'})
    paths = {}
    for key in ('weights', 'source', 'interpreter'):
        text = optional_text(record, key)
        paths[key] = Path(_text(text)) if text is not None else None
    device, preset = _text(record['device']), _text(record['preset'])
    samples, seed = _integer(record['samples'], 8), _integer(record['seed'])
    if (device not in ('auto', 'cpu', 'cuda') or preset not in ('turbo', 'fast', 'base', 'precise')
            or samples > 10000 or seed > 2**31 - 1):
        raise ValueError('Sesja: nieprawidłowa zapamiętana konfiguracja RoMa.')
    return DeepMatcherOptions(paths['weights'], device, paths['source'], paths['interpreter'],
                              preset, samples, seed)


def _decode_display(value: object, count: int, aligned: bool) -> SessionViewState:
    fields = json_object(value)
    extra = {'deep_source', 'deep_interpreter', 'deep_preset', 'deep_samples', 'deep_seed', 'roma_options'} & fields.keys()
    record = json_object(fields, _DISPLAY_KEYS | extra)
    index = _integer(record['index'])
    view = record['view']
    if index >= count or view not in ('original', 'aligned') or (view == 'aligned' and not aligned):
        raise ValueError('Sesja: nieprawidłowa wyświetlana klatka lub wersja obrazu.')
    gamma = optional_number(record, 'gamma')
    fps = _integer(record['fps'], 1)
    if gamma is None or not 0.1 <= gamma <= 4 or fps > 30:
        raise ValueError('Sesja: nieprawidłowa gamma lub tempo odtwarzania.')
    method = _text(record['method'])
    device = _text(record['deep_device'])
    if method not in REGISTRATION_METHODS or device not in ('auto', 'cpu', 'cuda'):
        raise ValueError('Sesja: nieobsługiwana metoda lub urządzenie rejestracji.')
    navigation = {}
    for key, item in json_object(record['navigation']).items():
        if key not in ('original', 'aligned'):
            raise ValueError('Sesja: nieobsługiwany widok nawigacji.')
        transform = json_object(item, {'zoom', 'pan_xy'})
        zoom = optional_number(transform, 'zoom')
        if zoom is None or not 0.1 <= zoom <= 64:
            raise ValueError('Sesja: nieprawidłowy zoom.')
        navigation[key] = ViewTransform(zoom, _xy(transform['pan_xy']))
    preset = _text(record.get('deep_preset', 'turbo'))
    samples = _integer(record.get('deep_samples', 1000), 8)
    seed = _integer(record.get('deep_seed', 20261102))
    if preset not in ('turbo', 'fast', 'base', 'precise') or samples > 10000 or seed > 2**31 - 1:
        raise ValueError('Sesja: nieprawidłowe ustawienia próbkowania RoMa.')
    interpreter = optional_text(record, 'deep_interpreter') if 'deep_interpreter' in record else None
    if interpreter is not None and (not interpreter.strip() or '\x00' in interpreter):
        raise ValueError('Sesja: nieprawidłowa ścieżka interpretera RoMa.')
    assert isinstance(view, str)
    return SessionViewState(index, view, gamma, _boolean(record['pixel_proportions']), fps,
                            _boolean(record['loop']), method, optional_text(record, 'deep_weights'),
                            device, navigation, optional_text(record, 'deep_source') if 'deep_source' in record else None,
                            interpreter, preset, samples, seed, _decode_roma_options(record.get('roma_options')))


def _registration_record(result: RegistrationResult, images: tuple[ImageFrame, ...],
                         manual_ids: dict[str, int], check_cancelled: Callable[[], None]) -> dict[str, object]:
    record: dict[str, object] = {
        'frames': [_encode_frame(frame, f'aligned/{i:06d}.npy', manual_ids) for i, frame in enumerate(images)],
        'image_alignments': [encode_alignment(frame.image.alignment, manual_ids=manual_ids) for frame in result.frames],
        'reference': {'source': str(result.reference.source), 'source_frame_index': result.reference.source_frame_index},
        'canvas_shape': result.canvas_shape, 'padding_ltrb': result.padding_ltrb,
        'pixel_size_nm': result.pixel_size_nm, 'method': result.method, 'device': result.device,
        'settings_version': result.settings_version, 'revision': result.revision,
        'manual_state': manual_ids[result.revision] if result.baseline else None,
        'corrections_editable': result.corrections_editable,
        'pair_diagnostics': encode_pair_diagnostics(result.pair_diagnostics),
        'local_diagnostics': encode_local_diagnostics(result.local_diagnostics),
    }
    if result.correspondence_diagnostics:
        record['correspondence_diagnostics'] = encode_correspondence_diagnostics(result.correspondence_diagnostics)
    if result.graph_application is not None:
        record['graph_application'] = encode_graph_application(result.graph_application)
    if result.predecessor is not None:
        record['predecessor'] = encode_movie_snapshot(result.predecessor, check_cancelled)
    return record


def _registration_object(value: object) -> dict[str, object]:
    record = json_object(value)
    return json_object(record, _REGISTRATION_KEYS | ({'graph_application', 'predecessor', 'correspondence_diagnostics'} & record.keys()))


def _decode_registration(value: object, originals: tuple[ImageFrame, ...],
                         arrays: Mapping[str, NDArray[np.float64]],
                         histories: tuple[MovieHistory, ...],
                         check_cancelled: Callable[[], None]) -> RegistrationResult:
    record = _registration_object(value)
    images = tuple(_decode_frame(item, arrays, histories) for item in _frame_records(record['frames'], 'aligned'))
    image_histories = _sequence(record['image_alignments'])
    if len(images) != len(originals) or len(image_histories) != len(originals):
        raise ValueError('Sesja: niespójna liczba obrazów aligned.')
    canvas = _shape(record['canvas_shape'])
    padding = tuple(_integer(item) for item in _sequence(record['padding_ltrb']))
    if len(padding) != 4:
        raise ValueError('Sesja: padding wymaga czterech wartości.')
    pixel_size = None if record['pixel_size_nm'] is None else _xy(record['pixel_size_nm'])
    reference = source_provenance(record['reference'])
    method, device = _text(record['method']), _text(record['device'])
    revision = _text(record['revision'])
    version = _integer(record['settings_version'], 1)
    if version != 1:
        raise ValueError('Sesja: nieobsługiwana wersja ustawień rejestracji.')
    editable = _boolean(record['corrections_editable'])
    manual = None
    if record['manual_state'] is not None:
        manual_index = _integer(record['manual_state'])
        if manual_index >= len(histories):
            raise ValueError('Sesja: nieznany stan ręcznych korekt.')
        manual = histories[manual_index]
        if (manual.revision, manual.settings_version) != (revision, version):
            raise ValueError('Sesja: korekty należą do innej wersji rejestracji.')
        sources = [item.source for item in manual.baseline]
        opened = [MovieSource(str(frame.source), frame.source_frame_index) for frame in originals]
        if (any(source not in sources for source in opened)
                or [sources.index(source) for source in opened] != sorted(sources.index(source) for source in opened)
                or (editable and opened != sources)):
            raise ValueError('Sesja: baza korekt nie odpowiada bieżącej kolejności klatek.')
        if (reference.source, reference.source_frame_index) != (sources[0].source, sources[0].source_frame_index):
            raise ValueError('Sesja: odniesienie nie zgadza się z bazą rejestracji.')
    aligned = []
    for index, (original, image) in enumerate(zip(originals, images)):
        check_cancelled()
        history = image.alignment
        if history is None:
            raise ValueError('Sesja: aligned wymaga pełnej geometrii.')
        if (history.canvas_shape, history.padding_ltrb, history.pixel_size_nm, history.reference,
                history.method, history.device) != (canvas, padding, pixel_size, reference, method, device):
            raise ValueError('Sesja: obrazy aligned opisują różne wyniki.')
        if (history.original_shape != original.data.shape
                or history.original_size_nm != (original.size_x_nm, original.size_y_nm)
                or history.original_offset_nm != (original.offset_x_nm, original.offset_y_nm)
                or history.previous != original.alignment
                or (image.source, image.source_frame_index) != (original.source, original.source_frame_index)):
            raise ValueError('Sesja: geometria aligned nie odpowiada obrazowi original.')
        if manual is not None:
            source = MovieSource(str(original.source), original.source_frame_index)
            manual_frame = manual_frame_state(manual, next(i for i, item in enumerate(manual.baseline) if item.source == source))
            if (history.shift_xy, history.status, history.quality_score, history.inherited_uncertainty) != (
                    manual_frame.shift_xy, manual_frame.status, manual_frame.quality_score, manual_frame.inherited_uncertainty):
                raise ValueError('Sesja: aligned nie odpowiada zapisanym korektom.')
            if history.manual_movie is not None and history.manual_movie != manual:
                raise ValueError('Sesja: historia aligned i aktywna korekta są sprzeczne.')
        elif history.manual_movie is not None:
            raise ValueError('Sesja: brak aktywnej historii ręcznych korekt.')
        image = replace(image, alignment=None)
        if image_histories[index] is not None:
            image = replace(image, alignment=decode_alignment(image_histories[index], image, manual_results=histories))
        mask = np.empty(image.data.shape, dtype=np.bool_)
        block_rows = max(1, (4 * 1024 * 1024) // (image.data.shape[1] * 8))
        for row in range(0, image.data.shape[0], block_rows):
            check_cancelled()
            np.isfinite(image.data[row:row + block_rows], out=mask[row:row + block_rows])
        mask.setflags(write=False)
        aligned.append(AlignedFrame(original, image, mask, history.shift_xy, history.origin_xy,
                                    history.status, history.quality_score, history.inherited_uncertainty))
    left, top, right, bottom = padding
    result = RegistrationResult(
        frames=tuple(aligned), reference=FrameOrigin(session_paths.native_path(reference.source), reference.source_frame_index),
        canvas_shape=canvas, padding_ltrb=(left, top, right, bottom), pixel_size_nm=pixel_size,
        method=method, device=device, settings_version=version, revision=revision,
        baseline=manual.baseline if manual else (), corrections=manual.corrections if manual else (),
        corrections_editable=editable,
        pair_diagnostics=decode_pair_diagnostics(record['pair_diagnostics'], len(originals)),
        local_diagnostics=decode_local_diagnostics(record['local_diagnostics'], len(originals)),
        correspondence_diagnostics=decode_correspondence_diagnostics(record.get('correspondence_diagnostics', []), len(originals)),
        graph_application=decode_graph_application(record.get('graph_application'), originals,
            manual.baseline if manual else (), check_cancelled, allow_subset=not editable),
        predecessor=decode_movie_snapshot(record.get('predecessor'), originals, check_cancelled),
    )
    if result.correspondence_diagnostics:
        if method not in ('EfficientLoFTR', 'RoMa v2'):
            raise ValueError('Sesja: metoda nie odpowiada diagnostyce korespondencji.')
        for original, diagnostic in zip(originals, result.correspondence_diagnostics, strict=True):
            shape = (original.data.shape[0], original.data.shape[1])
            validate_correspondence_shape(diagnostic, shape, shape)
            validate_correspondence_method(diagnostic, method)
            if diagnostic is not None and diagnostic.final_shift_xy is None:
                raise ValueError('Sesja: aktywny łańcuch nie może zawierać odmowy dopasowania.')
    if manual is not None and manual.graph_provenance != movie_history(result).graph_provenance:
        raise ValueError('Sesja: pochodzenie grafu nie odpowiada aktywnemu zastosowaniu.')
    if result.graph_application is not None:
        application = result.graph_application
        if (result.method != f'{graph_method_label(application.graph.config.method)} — graf {application.solver}'
                or result.device != application.graph.config.device):
            raise ValueError('Sesja: opis metody grafu nie odpowiada aktywnemu zastosowaniu.')
    return result


def encode_session(state: SessionState, *, check_cancelled: Callable[[], None] = _noop
                   ) -> tuple[dict[str, object], dict[str, NDArray[np.float64]]]:
    """Describe existing buffers without copying images or computing registration."""
    check_cancelled()
    result = state.registration
    exported = aligned_export_frames(result, check_cancelled) if result is not None else ()
    images = tuple(item.image for item in result.frames) if result is not None else ()
    if result is not None and (len(result.frames) != len(state.frames)
                              or any(item.original is not frame for item, frame in zip(result.frames, state.frames))):
        raise ValueError('Sesja: aktywna rejestracja należy do innej serii original.')
    histories = collect_manual_histories(state.frames + images + exported, check_cancelled)
    if result is not None and result.baseline:
        active = movie_history(result)
        existing = next((item for item in histories if item.revision == active.revision), None)
        if existing is not None and existing != active:
            raise ValueError('Sesja: sprzeczne historie tej samej korekty.')
        if existing is None:
            histories += (active,)
    elif result is not None and result.corrections:
        raise ValueError('Sesja: ręczne korekty bez bazy rejestracji.')
    ids = {item.revision: i for i, item in enumerate(histories)}
    arrays = {f'original/{i:06d}.npy': frame.data for i, frame in enumerate(state.frames)}
    arrays.update({f'aligned/{i:06d}.npy': frame.data for i, frame in enumerate(exported)})
    manifest: dict[str, object] = {
        'schema': 'stmviewer-state-v1',
        'frames': [_encode_frame(frame, f'original/{i:06d}.npy', ids) for i, frame in enumerate(state.frames)],
        'registration': _registration_record(result, exported, ids, check_cancelled) if result is not None else None,
        'display': asdict(state.display),
        'manual_histories': encode_manual_results(histories, check_cancelled) if histories else [],
    }
    if state.graph is not None:
        manifest['schema'] = 'stmviewer-state-v2'
        manifest['graph'] = encode_graph(state.graph)
    if result is not None and (result.graph_application is not None or result.predecessor is not None):
        manifest['schema'] = 'stmviewer-state-v3'
        manifest.setdefault('graph', None)
    display = manifest['display']
    assert isinstance(display, dict)
    if state.display.deep_source is None:
        display.pop('deep_source')
    else:
        manifest['schema'] = 'stmviewer-state-v4'
        manifest.setdefault('graph', None)
    if result is not None and result.correspondence_diagnostics:
        manifest['schema'] = 'stmviewer-state-v4'
        manifest.setdefault('graph', None)
    if (state.display.deep_interpreter is not None or state.display.method == 'roma_v2'
            or (state.graph is not None and state.graph.config.method == 'roma_v2')
            or (result is not None and (result.method == 'RoMa v2' or
                (result.graph_application is not None and result.graph_application.graph.config.method == 'roma_v2')))
            or (state.display.deep_preset, state.display.deep_samples, state.display.deep_seed)
               != ('turbo', 1000, 20261102)):
        manifest['schema'] = 'stmviewer-state-v5'
        manifest.setdefault('graph', None)
    else:
        for key in ('deep_interpreter', 'deep_preset', 'deep_samples', 'deep_seed'):
            display.pop(key)
    if state.display.roma_options is None:
        display.pop('roma_options')
    else:
        options = asdict(state.display.roma_options)
        for key in ('weights', 'source', 'interpreter'):
            options[key] = str(options[key]) if options[key] is not None else None
        display['roma_options'] = options
        manifest['schema'] = 'stmviewer-state-v6'
        manifest.setdefault('graph', None)
    decode_session(manifest, arrays, check_cancelled=check_cancelled)
    return manifest, arrays


def decode_session(manifest: object, arrays: Mapping[str, NDArray[np.float64]], *,
                   check_cancelled: Callable[[], None] = _noop) -> SessionState:
    """Restore validated state solely from archived samples and JSON metadata."""
    check_cancelled()
    expected = session_array_shapes(manifest)
    if set(arrays) != set(expected):
        raise ValueError('Sesja: niekompletny lub nadmiarowy zestaw obrazów.')
    root = session_paths.normalize_active_sources(_root(manifest))
    history_records = _sequence(root['manual_histories'])
    histories = decode_manual_results(history_records, check_cancelled) if history_records else ()
    decoded = []
    for record in _frame_records(root['frames'], 'original'):
        check_cancelled()
        decoded.append(_decode_frame(record, arrays, histories))
    frames = tuple(decoded)
    registration = None if root['registration'] is None else _decode_registration(root['registration'], frames, arrays, histories, check_cancelled)
    graph = None if root.get('graph') is None else decode_graph(root['graph'], frames, check_cancelled)
    return SessionState(frames, registration, _decode_display(root['display'], len(frames), registration is not None), graph)
