"""Versioned, image-free graph state in portable session metadata."""
from dataclasses import asdict, replace
import re
from typing import Callable

from stmviewer.frame import ImageFrame
from stmviewer.correspondence_metadata import decode_correspondence
from stmviewer.graph_provenance import graph_sources
from stmviewer import session_paths
from stmviewer.graph_types import GraphConfig, GraphEdge, GraphSource, GraphTrial, XY
from stmviewer.graph_validation import validate_graph_result
from stmviewer.metadata_values import json_object, optional_number, source_provenance

_GRAPH_KEYS = {
    'schema', 'sources', 'config', 'edges', 'positions', 'chain_positions',
    'components', 'bridges', 'revision', 'anchor', 'solver', 'measured_pairs',
    'reused_pairs', 'measurement_s', 'solver_s',
}
_SOURCE_KEYS = {'source', 'source_frame_index', 'shape', 'pixels_sha256'}
_CONFIG_KEYS = {
    'window', 'weights_path', 'weights_sha256', 'requested_device', 'device',
    'backend_settings', 'libraries', 'code_version', 'settings_version',
}
_EDGE_KEYS = {'i', 'j', 'shift_xy', 'status', 'reason', 'quality_score', 'residual_xy'}
_CORRESPONDENCE_SCHEMAS = {
    'efficient_loftr': 'stmviewer-graph-v5',
    'roma_v2': 'stmviewer-graph-v6',
    'matchanything_eloftr': 'stmviewer-graph-v7',
    'lightglue_superpoint': 'stmviewer-graph-v8',
    'akaze': 'stmviewer-graph-v9',
}


def _items(value: object) -> list[object]:
    if not isinstance(value, (list, tuple)):
        raise ValueError('Graf: wymagana lista.')
    return list(value)


def _integer(value: object, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError('Graf: nieprawidłowa liczba całkowita.')
    return value


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        raise ValueError('Graf: wymagany niepusty tekst.')
    return value


def _digest(value: object) -> str:
    text = _text(value)
    if re.fullmatch(r'[0-9a-f]{64}', text) is None:
        raise ValueError('Graf: nieprawidłowy SHA-256.')
    return text


def _number(value: object) -> float:
    number = optional_number({'value': value}, 'value')
    if number is None:
        raise ValueError('Graf: wymagana skończona liczba.')
    return number


def _xy(value: object) -> XY:
    items = _items(value)
    if len(items) != 2:
        raise ValueError('Graf: wymagane dwie współrzędne.')
    return _number(items[0]), _number(items[1])


def _indices(value: object) -> tuple[int, int]:
    items = _items(value)
    if len(items) != 2:
        raise ValueError('Graf: wymagana para indeksów.')
    return _integer(items[0]), _integer(items[1])


def _settings(value: object) -> tuple[tuple[str, str], ...]:
    pairs = []
    for entry in _items(value):
        items = _items(entry)
        if len(items) != 2:
            raise ValueError('Graf: ustawienie wymaga nazwy i wartości.')
        pairs.append((_text(items[0]), _text(items[1])))
    if len({key for key, _ in pairs}) != len(pairs):
        raise ValueError('Graf: powtórzone ustawienie.')
    return tuple(pairs)


def decode_graph_source(value: object) -> GraphSource:
    record = json_object(value, _SOURCE_KEYS)
    source = source_provenance({key: record[key] for key in ('source', 'source_frame_index')})
    shape = _indices(record['shape'])
    if min(shape) < 1:
        raise ValueError('Graf: nieprawidłowy rozmiar obrazu.')
    return GraphSource(source.source, source.source_frame_index, shape, _digest(record['pixels_sha256']))


def decode_graph_config(value: object) -> GraphConfig:
    record = json_object(value)
    version = _integer(record.get('settings_version'))
    record = json_object(record, _CONFIG_KEYS | ({'method'} if version == 2 else set()))
    window = _integer(record['window'])
    version = _integer(record['settings_version'])
    if window not in (3, 5) or version not in (1, 2):
        raise ValueError('Graf: nieobsługiwane okno lub wersja ustawień.')
    requested, device = _text(record['requested_device']), _text(record['device'])
    if requested not in ('auto', 'cpu', 'cuda'):
        raise ValueError('Graf: nieobsługiwane urządzenie.')
    from stmviewer.registration import DEEP_METHODS, REGISTRATION_METHODS
    method = 'deep_matcher_translation' if version == 1 else _text(record['method'])
    if method not in REGISTRATION_METHODS:
        raise ValueError('Graf: nieobsługiwana metoda pomiaru.')
    if method == 'akaze':
        from stmviewer.correspondence_metadata import validate_akaze_provenance
        validate_akaze_provenance(_settings(record['backend_settings']))
    if method == 'roma_v2':
        from stmviewer.correspondence_metadata import validate_roma_provenance
        validate_roma_provenance(_settings(record['backend_settings']))
    if method == 'matchanything_eloftr':
        from stmviewer.correspondence_metadata import validate_matchanything_provenance
        validate_matchanything_provenance(_settings(record['backend_settings']))
    if method == 'lightglue_superpoint':
        from stmviewer.correspondence_metadata import validate_lightglue_provenance
        validate_lightglue_provenance(_settings(record['backend_settings']))
    deep = method in DEEP_METHODS
    weights = _text(record['weights_path']) if deep else None
    digest = _digest(record['weights_sha256']) if deep else None
    if not deep and (record['weights_path'] is not None or record['weights_sha256'] is not None
                     or requested != 'cpu' or device.lower() != 'cpu'):
        raise ValueError('Graf: metoda CPU ma sprzeczne metadane modelu lub urządzenia.')
    return GraphConfig(window, weights, digest, requested, device, _settings(record['backend_settings']),
                       _settings(record['libraries']), _text(record['code_version']), version, method)


def encode_graph_config(config: GraphConfig) -> dict[str, object]:
    record = asdict(config)
    if config.settings_version == 1:
        if config.method != 'deep_matcher_translation':
            raise ValueError('Graf: starsza wersja ustawień wymaga Deep Matcher.')
        record.pop('method')
    decode_graph_config(record)
    return record


def _edge(value: object, *, modern: bool = False, correspondence: bool = False) -> GraphEdge:
    extra = {'hybrid_diagnostics', 'local_diagnostics'} if modern else set()
    if correspondence:
        extra.add('correspondence_diagnostics')
    record = json_object(value, _EDGE_KEYS | extra)
    status = _text(record['status'])
    if status not in ('ok', 'low_confidence', 'manual_review', 'missing'):
        raise ValueError('Graf: nieobsługiwany stan relacji.')
    shift = None if record['shift_xy'] is None else _xy(record['shift_xy'])
    reason = None if record['reason'] is None else _text(record['reason'])
    residual = None if record['residual_xy'] is None else _xy(record['residual_xy'])
    if (status == 'missing') != (shift is None) or (shift is None and reason is None):
        raise ValueError('Graf: stan i przyczyna relacji są niespójne.')
    hybrid = local = None
    if modern:
        from stmviewer.session_diagnostics import decode_pair_diagnostics, decode_local_diagnostics
        hybrid = decode_pair_diagnostics([record['hybrid_diagnostics']], 1)[0]
        local = decode_local_diagnostics([record['local_diagnostics']], 1)[0]
    return GraphEdge(_integer(record['i']), _integer(record['j']), shift, status, reason,
                     optional_number(record, 'quality_score'), residual, hybrid, local,
                     decode_correspondence(record.get('correspondence_diagnostics')))


def encode_graph(trial: GraphTrial) -> dict[str, object]:
    """Store measurements and positions; never store rendered candidate images."""
    record = asdict(trial)
    record.pop('robust_trials')
    record['config'] = encode_graph_config(trial.config)
    modern = trial.config.settings_version == 2
    correspondence = trial.config.method in _CORRESPONDENCE_SCHEMAS
    if not correspondence:
        for edge in record['edges']:
            if edge.pop('correspondence_diagnostics') is not None:
                raise ValueError('Graf: metoda nie obsługuje diagnostyki korespondencji.')
    if not modern:
        for edge in record['edges']:
            if edge.pop('hybrid_diagnostics') is not None or edge.pop('local_diagnostics') is not None:
                raise ValueError('Graf: starsza wersja nie obsługuje diagnostyki metod.')
    if modern or trial.robust_trials:
        from stmviewer.robust_graph_metadata import encode_robust_trial
        schema = _CORRESPONDENCE_SCHEMAS.get(
            trial.config.method, 'stmviewer-graph-v4' if modern else 'stmviewer-graph-v2')
        return {'schema': schema, **record,
                'robust_trials': [encode_robust_trial(item) for item in trial.robust_trials]}
    return {'schema': 'stmviewer-graph-v1', **record}


def decode_graph(value: object, frames: tuple[ImageFrame, ...],
                 check_cancelled: Callable[[], None], *, allow_subset: bool = False) -> GraphTrial:
    """Restore graph values without loading weights or running registration."""
    check_cancelled()
    record = json_object(value)
    schema = record.get('schema')
    if schema not in ('stmviewer-graph-v1', 'stmviewer-graph-v2', 'stmviewer-graph-v4',
                       *_CORRESPONDENCE_SCHEMAS.values()):
        raise ValueError('Nieobsługiwana wersja grafu sesji.')
    correspondence = schema in _CORRESPONDENCE_SCHEMAS.values()
    modern = schema == 'stmviewer-graph-v4' or correspondence
    variants_present = schema != 'stmviewer-graph-v1'
    record = json_object(record, _GRAPH_KEYS | ({'robust_trials'} if variants_present else set()))
    positions = None if record['positions'] is None else tuple(_xy(item) for item in _items(record['positions']))
    chain = None if record['chain_positions'] is None else tuple(_xy(item) for item in _items(record['chain_positions']))
    trial = GraphTrial(
        tuple(decode_graph_source(item) for item in _items(record['sources'])), decode_graph_config(record['config']),
        tuple(_edge(item, modern=modern, correspondence=correspondence) for item in _items(record['edges'])), positions, chain,
        tuple(tuple(_integer(item) for item in _items(component)) for component in _items(record['components'])),
        tuple(_indices(item) for item in _items(record['bridges'])), _text(record['revision']),
        _integer(record['anchor']), _text(record['solver']), _integer(record['measured_pairs']),
        _integer(record['reused_pairs']), _number(record['measurement_s']), _number(record['solver_s']),
    )
    if any((schema == model_schema) != (trial.config.method == method)
           for method, model_schema in _CORRESPONDENCE_SCHEMAS.items()):
        raise ValueError('Graf: format diagnostyki nie odpowiada metodzie.')
    if trial.config.settings_version != (2 if modern else 1):
        raise ValueError('Graf: wersja konfiguracji nie odpowiada formatowi grafu.')
    if len(trial.sources) < 2:
        raise ValueError('Graf: wymaga przynajmniej dwóch źródeł.')
    bind_graph_sources(trial.sources, frames, check_cancelled, allow_subset=allow_subset)
    validate_graph_result(trial, check_cancelled)
    if variants_present:
        from stmviewer.robust_graph_metadata import decode_robust_trial
        from stmviewer.robust_graph_validation import validate_robust_result
        variants = []
        for item in _items(record['robust_trials']):
            check_cancelled()
            variant = decode_robust_trial(item)
            validate_robust_result(trial, variant, check_cancelled)
            variants.append(variant)
        if len({variant.revision for variant in variants}) != len(variants):
            raise ValueError('Huber: powtórzony identyfikator wariantu.')
        trial = replace(trial, robust_trials=tuple(variants))
    # Runtime graph identities follow the native frame spelling, as active manual
    # histories do. The frame's provenance preserves historical source text.
    return replace(trial, sources=tuple(replace(source, source=str(session_paths.native_path(source.source)))
                                        for source in trial.sources))


def bind_graph_sources(sources: tuple[GraphSource, ...], frames: tuple[ImageFrame, ...],
                       check_cancelled: Callable[[], None], *, allow_subset: bool = False
                       ) -> tuple[GraphSource, ...]:
    if not frames or not sources or (not allow_subset and len(sources) != len(frames)):
        raise ValueError('Graf: liczba źródeł nie odpowiada serii.')

    def cancelled() -> bool:
        check_cancelled()
        return False

    current = graph_sources(frames, cancelled=cancelled)
    saved_sources = tuple(replace(source, source=str(session_paths.native_path(source.source)))
                          for source in sources)
    if len({(s.source, s.source_frame_index) for s in saved_sources}) != len(saved_sources):
        raise ValueError('Graf: powtórzone źródło w serii.')
    previous = -1
    for original in current:
        try:
            index = saved_sources.index(original)
        except ValueError as error:
            raise ValueError('Graf: powiązanie źródła lub wartości obrazu nie odpowiada sesji.') from error
        if index <= previous or (not allow_subset and index != previous + 1):
            raise ValueError('Graf: kolejność źródeł nie odpowiada sesji.')
        previous = index
    return saved_sources
