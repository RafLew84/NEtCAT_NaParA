"""Portable manual histories with shared result, raster and class-revision records."""

from dataclasses import asdict, replace
import hashlib
import io
from pathlib import Path
import zipfile

import numpy as np

from stmdomains.core.analysis_result import FrameAnalysis, MoleculeAssignment, ResultClass
from stmdomains.core.manual_classes import ManualClass, ManualClassList
from stmdomains.core.manual_class_lists import ManualClassLists
from stmdomains.core.manual_project import ManualProjectState, ManualStep, ManualVariantState
from stmdomains.core.series import Series
from stmdomains.io.project_archive import ProjectError, json_bytes, put_bytes, read_json
from stmdomains.io.project_results import catalogue_record, frame_record, load_catalogue
from stmdomains.io.manual_validation import validate_manual


def revision_key(labels: ManualClassList | None):
    return (labels.identifier, labels.version) if labels is not None else None


def save_manual(archive: zipfile.ZipFile, entries: dict, state: ManualProjectState,
                series: Series, check) -> None:
    validate_manual(state, series, check)
    results: dict[int, int] = {}

    def array_ref(array):
        if array is None:
            return None
        check()
        output = io.BytesIO()
        np.save(output, array, allow_pickle=False)
        content = output.getvalue()
        key = hashlib.sha256(content).hexdigest()
        path = f'manual/arrays/{key}.npy'
        if path not in entries:
            put_bytes(archive, entries, path, content)
        return key

    def result_ref(result):
        if result is None:
            return None
        if id(result) in results:
            return results[id(result)]
        check()
        key = len(results)
        results[id(result)] = key
        record = frame_record(result)
        record.update(class_list=revision_key(result.class_list),
                      labels_ref=array_ref(result.domain_labels), barriers_ref=array_ref(result.barrier_mask))
        if result.catalogue:
            path = f'manual/catalogues/{result.catalogue.identifier}.json'
            if path not in entries:
                put_bytes(archive, entries, path, json_bytes(catalogue_record(result.catalogue)))
        put_bytes(archive, entries, f'manual/results/{key}.json', json_bytes(record))
        return key

    def step_record(step):
        return {'variant_id': step.variant_id, 'variant_ids': step.variant_ids,
                'before': revision_key(step.before), 'after': revision_key(step.after)}

    record = {'version': 1, 'series_id': series.identity,
              'revisions': [asdict(r) for r in state.revisions], 'current': state.current,
              'undo': [step_record(s) for s in state.undo], 'redo': [step_record(s) for s in state.redo],
              'selected': state.selected, 'editing': state.editing, 'comparison': state.comparison,
              'variants': [{'identifier': v.identifier, 'class_list_id': v.class_list_id,
                  'original': result_ref(v.original), 'frames': [result_ref(f) for f in v.frames],
                  'cursor': v.cursor, 'revision': v.revision} for v in state.variants]}
    put_bytes(archive, entries, 'manual/state.json', json_bytes(record))


def load_manual(root: Path, entries: dict, series: Series, check) -> ManualProjectState:
    record = read_json(root / 'manual/state.json')
    if type(record['version']) is not int or record['version'] != 1 or not isinstance(record['series_id'], str):
        raise ProjectError('Nieobsługiwana wersja korekt ręcznych.')
    expected = {'manual/state.json'}
    revisions = {}
    for item in record['revisions']:
        labels = ManualClassList(**{**item, 'classes': tuple(ManualClass(**c) for c in item['classes'])})
        key = revision_key(labels)
        if key in revisions:
            raise ProjectError('Powtórzone rewizje klas.')
        revisions[key] = labels
    arrays, catalogues = {}, {}
    results: dict[int, FrameAnalysis] = {}

    def array(key, *, barrier=False):
        if key is None:
            return None
        if not isinstance(key, str) or len(key) != 64:
            raise ProjectError('Niepoprawne odwołanie do geometrii.')
        name = f'manual/arrays/{key}.npy'
        if name not in entries or entries[name]['sha256'] != key:
            raise ProjectError('Brak geometrii ręcznej lub niezgodna tożsamość.')
        expected.add(name)
        if key not in arrays:
            check()
            value = np.load(root / name, allow_pickle=False)
            if value.shape != series.frame_shape or value.dtype != (np.dtype('bool') if barrier else np.dtype('int32')):
                raise ProjectError('Niepoprawny raster geometrii ręcznej.')
            value.setflags(write=False)
            arrays[key] = value
        return arrays[key]

    def result(key):
        if key is None:
            return None
        if type(key) is not int or key < 0:
            raise ProjectError('Niepoprawne odwołanie do stanu korekt.')
        if key in results:
            return results[key]
        check()
        name = f'manual/results/{key}.json'
        if name not in entries:
            raise ProjectError('Brak stanu korekt.')
        expected.add(name)
        data = read_json(root / name)
        catalogue_id = data['catalogue']
        if catalogue_id is not None and catalogue_id not in catalogues:
            path = f'manual/catalogues/{catalogue_id}.json'
            if path not in entries:
                raise ProjectError('Brak katalogu bazowego korekt.')
            expected.add(path)
            catalogue = load_catalogue(read_json(root / path), series)
            if catalogue.identifier != catalogue_id:
                raise ProjectError('Niepoprawny katalog bazowy korekt.')
            catalogues[catalogue_id] = catalogue
        if (type(data['domain_labels']) is not bool or type(data['barrier_mask']) is not bool
                or data['domain_labels'] != (data['labels_ref'] is not None)
                or data['barrier_mask'] != (data['barriers_ref'] is not None)):
            raise ProjectError('Niespójny opis geometrii korekt.')
        value = FrameAnalysis(series.identity, data['working_index'], data['source_index'], data['status'], data['message'],
            {k: MoleculeAssignment(**v) for k, v in data['assignments'].items()},
            tuple(ResultClass(**c) for c in data['classes']), data['parameters'], data['metadata'],
            array(data['labels_ref']), catalogues.get(catalogue_id), array(data['barriers_ref'], barrier=True),
            revisions[tuple(data['class_list'])] if data['class_list'] is not None else None)
        results[key] = value
        return value

    variants = tuple(ManualVariantState(v['identifier'], v['class_list_id'], result(v['original']),
        tuple(result(k) for k in v['frames']), v['cursor'], v['revision']) for v in record['variants'])
    # Series identities change on opening a portable document. Rebind internal
    # source keys while preserving every list/label/revision and variant ID.
    sources: dict[str, str] = {}
    for variant in variants:
        key = ManualClassLists.source_key(series.identity, variant.original)
        if variant.class_list_id in sources and sources[variant.class_list_id] != key:
            raise ProjectError('Lista korekt łączy niezgodne źródła.')
        sources[variant.class_list_id] = key
    remapped = {}
    for key, labels in revisions.items():
        if not labels.source_key.startswith(record['series_id'] + ':') or labels.identifier not in sources:
            raise ProjectError('Lista klas nie należy do źródła korekt.')
        suffix = labels.source_key[len(record['series_id']):]
        new_suffix = sources[labels.identifier][len(series.identity):]
        if suffix != new_suffix and not (suffix.startswith(':local-result:') and new_suffix.startswith(':local-result:')):
            raise ProjectError('Lista klas odwołuje się do innego katalogu.')
        remapped[key] = replace(labels, source_key=sources[labels.identifier])
    replaced = {id(f): replace(f, class_list=remapped[revision_key(f.class_list)]) if f.class_list else f
                for f in results.values()}
    variants = tuple(replace(v, original=replaced[id(v.original)] if v.original else None,
                             frames=tuple(replaced[id(f)] for f in v.frames)) for v in variants)

    def step(data):
        return ManualStep(data['variant_id'], remapped[tuple(data['before'])] if data['before'] else None,
                          remapped[tuple(data['after'])] if data['after'] else None, tuple(data['variant_ids']))

    state = ManualProjectState(variants, tuple(remapped.values()), tuple(tuple(x) for x in record['current']),
        tuple(step(s) for s in record['undo']), tuple(step(s) for s in record['redo']),
        tuple(tuple(x) for x in record['selected']), record['editing'], record['comparison'])
    if expected != {name for name in entries if name.startswith('manual/')}:
        raise ProjectError('Brakujące lub niepowiązane części korekt.')
    validate_manual(state, series, check)
    return state
