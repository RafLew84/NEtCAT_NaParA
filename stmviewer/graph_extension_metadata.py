"""Versioned window baseline retained inside an extended graph session."""
from collections.abc import Callable

from stmviewer.frame import ImageFrame
from stmviewer.graph_types import GraphExtension
from stmviewer.metadata_values import json_object, optional_text


def encode_graph_extension(extension: GraphExtension) -> dict[str, object]:
    from stmviewer.graph_metadata import encode_graph, encode_graph_config

    if extension.base.extension is not None:
        raise ValueError('Dalsze odniesienia: baza musi być grafem samego okna.')
    return {
        'base': encode_graph(extension.base), 'references': extension.references,
        'target_start': extension.target_start, 'target_end': extension.target_end,
        'base_robust_revision': extension.base_robust_revision,
        'measurement_config': encode_graph_config(extension.measurement_config),
        'settings_version': extension.settings_version,
    }


def decode_graph_extension(value: object, frames: tuple[ImageFrame, ...],
                           check_cancelled: Callable[[], None], *, allow_subset: bool) -> GraphExtension:
    from stmviewer.graph_metadata import decode_graph, decode_graph_config

    record = json_object(value, {'base', 'references', 'target_start', 'target_end',
                                 'base_robust_revision', 'measurement_config', 'settings_version'})
    if type(record['settings_version']) is not int or record['settings_version'] != 1:
        raise ValueError('Dalsze odniesienia: nieobsługiwana wersja ustawień.')
    base_record = json_object(record['base'])
    # Reject recursion before calling the graph decoder again, including an empty
    # or unknown extension attached to a legacy base record.
    if base_record.get('schema') not in ('stmviewer-graph-v1', 'stmviewer-graph-v2') or 'extension' in base_record:
        raise ValueError('Dalsze odniesienia: baza musi być grafem samego okna.')
    refs = record['references']
    if not isinstance(refs, (list, tuple)) or any(type(index) is not int for index in refs):
        raise ValueError('Dalsze odniesienia: nieprawidłowa lista klatek odniesienia.')
    start, end = record['target_start'], record['target_end']
    if type(start) is not int or type(end) is not int:
        raise ValueError('Dalsze odniesienia: nieprawidłowy zakres klatek.')
    robust_revision = optional_text(record, 'base_robust_revision')
    if robust_revision is not None and (not robust_revision.strip() or '\x00' in robust_revision):
        raise ValueError('Dalsze odniesienia: nieprawidłowy identyfikator bazowego Hubera.')
    return GraphExtension(
        decode_graph(base_record, frames, check_cancelled, allow_subset=allow_subset),
        tuple(refs), start, end, robust_revision, decode_graph_config(record['measurement_config']))
