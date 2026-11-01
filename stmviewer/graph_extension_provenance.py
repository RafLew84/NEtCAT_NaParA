"""Compact provenance of distant references, without image or raw-edge copies."""
from dataclasses import asdict, dataclass

from stmviewer.graph_types import GraphConfig, GraphExtension


@dataclass(frozen=True)
class GraphExtensionProvenance:
    base_revision: str
    base_robust_revision: str | None
    base_solver_settings: tuple[tuple[str, str], ...]
    references: tuple[int, ...]
    target_start: int
    target_end: int
    base_pairs: tuple[tuple[int, int], ...]
    added_pairs: tuple[tuple[int, int], ...]
    measurement_config: GraphConfig
    settings_version: int = 1


def extension_provenance(extension: GraphExtension) -> GraphExtensionProvenance:
    from stmviewer.long_references import plan_long_references

    base = extension.base
    settings: tuple[tuple[str, str], ...] = ()
    if extension.base_robust_revision is not None:
        variant = next(item for item in base.robust_trials if item.revision == extension.base_robust_revision)
        settings = tuple((key, str(value)) for key, value in asdict(variant.config).items())
    return GraphExtensionProvenance(
        base.revision, extension.base_robust_revision, settings, extension.references,
        extension.target_start, extension.target_end, tuple((edge.i, edge.j) for edge in base.edges),
        plan_long_references(base, extension.references, extension.target_start, extension.target_end),
        extension.measurement_config)


def encode_extension_provenance(extension: GraphExtensionProvenance) -> dict[str, object]:
    from stmviewer.graph_metadata import encode_graph_config

    record = asdict(extension)
    record['measurement_config'] = encode_graph_config(extension.measurement_config)
    return record


def decode_extension_provenance(value: object, config: GraphConfig, count: int,
                                 graph_revision: str) -> GraphExtensionProvenance:
    from stmviewer.graph_metadata import decode_graph_config
    from stmviewer.graph_movie_provenance import decode_solver_settings
    from stmviewer.graph_registration import graph_pairs
    from stmviewer.long_reference_identity import validate_extension_config
    from stmviewer.long_references import plan_reference_pairs
    from stmviewer.metadata_values import json_object, optional_text

    record = json_object(value, {'base_revision', 'base_robust_revision', 'base_solver_settings',
                                 'references', 'target_start', 'target_end', 'base_pairs',
                                 'added_pairs', 'measurement_config', 'settings_version'})
    if type(record['settings_version']) is not int or record['settings_version'] != 1:
        raise ValueError('Dalsze odniesienia: nieobsługiwana wersja pochodzenia.')
    revision = optional_text(record, 'base_revision')
    robust_revision = optional_text(record, 'base_robust_revision')
    if not revision or not revision.strip() or '\x00' in revision or revision == graph_revision:
        raise ValueError('Dalsze odniesienia: nieprawidłowy identyfikator bazy.')
    if robust_revision is not None and (not robust_revision.strip() or '\x00' in robust_revision):
        raise ValueError('Dalsze odniesienia: nieprawidłowy identyfikator bazowego Hubera.')
    solver = 'equal-ls-v1' if robust_revision is None else 'block-huber-irls-v1'
    settings = decode_solver_settings(record['base_solver_settings'], solver, robust_revision)
    refs = record['references']
    if (not isinstance(refs, (list, tuple)) or any(type(index) is not int for index in refs)
            or tuple(refs) != tuple(sorted(set(refs)))):
        raise ValueError('Dalsze odniesienia: niekanoniczne numery odniesień.')
    start, end = record['target_start'], record['target_end']
    if type(start) is not int or type(end) is not int:
        raise ValueError('Dalsze odniesienia: nieprawidłowy zakres klatek.')
    base_pairs = _pairs(record['base_pairs'])
    added_pairs = _pairs(record['added_pairs'])
    if base_pairs != graph_pairs(count, config.window):
        raise ValueError('Dalsze odniesienia: bazowe pary nie odpowiadają oknu filmu.')
    expected = plan_reference_pairs(count, base_pairs, tuple(refs), start, end)
    if not expected or added_pairs != expected:
        raise ValueError('Dalsze odniesienia: nowe pary nie odpowiadają odniesieniom i zakresowi.')
    measurement_config = decode_graph_config(record['measurement_config'])
    validate_extension_config(config, measurement_config)
    return GraphExtensionProvenance(revision, robust_revision, settings, tuple(refs), start, end,
                                    base_pairs, added_pairs, measurement_config)


def _pairs(value: object) -> tuple[tuple[int, int], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError('Dalsze odniesienia: wymagany wykaz par.')
    pairs = []
    for pair in value:
        if (not isinstance(pair, (list, tuple)) or len(pair) != 2
                or any(type(index) is not int for index in pair)):
            raise ValueError('Dalsze odniesienia: nieprawidłowe indeksy pary.')
        pairs.append((pair[0], pair[1]))
    return tuple(pairs)
