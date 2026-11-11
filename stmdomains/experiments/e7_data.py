"""Publish grouped E7 synthetic supervision and unchanged STM analysis inputs."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shutil

from . import controls as original_controls
from .bundle import file_hash, write_arrays, write_json
from .training import controls
from .training.predict import synthetic_rows

TRAIN_SEEDS = (941101, 941102, 941103)
VALIDATION_SEEDS = (941201, 941202, 941203)


def _json(out, relative, value, files):
    write_json(out / relative, value)
    files[relative] = file_hash(out / relative)


def prepare_data(bank, out: Path):
    """Return entries/files; STM reference files are neither opened nor copied.

    A seed's entire27-case family is one split group. Case/seed/generator
    metadata live in truths/index.json, never in the clean analysis manifest.
    The existing renderer and truth rules are reused without modifications.
    """
    out = Path(out)
    if any((out / name).exists() for name in ('analysis', 'rows', 'training_truth', 'evaluation_truth', 'truths')):
        raise FileExistsError('E7 input publication requires fresh data directories')
    if set(TRAIN_SEEDS) & set(VALIDATION_SEEDS) or (set(TRAIN_SEEDS) | set(VALIDATION_SEEDS)) & set(controls.FINAL_SEEDS):
        raise ValueError('Synthetic train/validation/reserved-evaluation seeds overlap')
    files, entries, records, truth_index = {}, [], [], []
    role_content = {'train': set(), 'validation': set()}
    for group_number, (role, seed) in enumerate(
            [(role, seed) for role, seeds in (('train', TRAIN_SEEDS), ('validation', VALIDATION_SEEDS)) for seed in seeds]):
        group_id = f'synthetic-group-{group_number:02d}'
        for case in controls.CASES:
            sample_id = f'e7-synthetic-{len(entries):04d}'
            arrays, truth, meta = controls.make_control(case, seed)
            source_file = f'analysis/samples/{sample_id}.npz'
            digest = write_arrays(out / source_file, arrays)
            files[source_file] = digest['sha256']
            role_content[role].add(digest['content_sha256'])
            record = dict(sample_id=sample_id, kind='synthetic', file=f'samples/{sample_id}.npz',
                          coordinate_system='raw_edge_xy', shape_hw=list(arrays['image'].shape),
                          pixel_spacing_xy=meta['pixel_spacing_xy'], position_unit='reference_px',
                          annotation_count=len(arrays['object_ids']), **digest)
            rows = [row for row in synthetic_rows(record, arrays) if row['sampler'] == 'centers' and row['scale_px'] == 48]
            rows_file = f'rows/{sample_id}.json'
            _json(out, rows_file, rows, files)
            folder = 'training_truth' if role == 'train' else 'evaluation_truth'
            truth_file = f'{folder}/{sample_id}.npz'
            truth_digest = write_arrays(out / truth_file, truth)
            files[truth_file] = truth_digest['sha256']
            entry = dict(sample_id=sample_id, kind='synthetic', role=role, group_id=group_id,
                         record=record, source_file=source_file, rows_file=rows_file,
                         rows_sha256=files[rows_file], truth_file=truth_file)
            entries.append(entry)
            records.append(record)
            truth_index.append(dict(sample_id=sample_id, role=role, group_id=group_id,
                                    truth_file=truth_file, **meta, **truth_digest))
    if role_content['train'] & role_content['validation']:
        raise ValueError('Identical complete synthetic inputs appeared across train and validation')
    truth_lookup = {(row['seed'], row['case']): row['sample_id'] for row in truth_index}
    for row in truth_index:
        if row.get('pair_case'):
            row['paired_sample_id'] = truth_lookup[(row['seed'], row['pair_case'])]
        if row.get('base_pair'):
            row['base_sample_id'] = truth_lookup[(row['seed'], row['base_pair'])]
    sources = []
    groups = sorted((g for g in bank.inputs.groups.values()
                     if g['sampler'] == 'centers' and g['record']['kind'] == 'measurement'),
                    key=lambda g: g['record']['sample_id'])
    if len(groups) != 24:
        raise ValueError('E7 requires all24 known STM fields on the centers sampler')
    for group in groups:
        record, _ = bank.inputs.sample(group)
        record = deepcopy(record)
        sample_id = record['sample_id']
        if any(e['sample_id'] == sample_id for e in entries):
            raise ValueError('Repeated sample ID')
        original = Path(group['analysis']) / record['file']
        if file_hash(original) != record['sha256']:
            raise ValueError('STM source changed after verified input loading')
        source_file = f'analysis/samples/{sample_id}.npz'
        destination = out / source_file
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, destination)
        files[source_file] = file_hash(destination)
        if files[source_file] != record['sha256']:
            raise ValueError('STM copy did not retain exact source bytes')
        record['file'] = f'samples/{sample_id}.npz'
        rows_file = f'rows/{sample_id}.json'
        _json(out, rows_file, bank.inputs.rows(group), files)
        entries.append(dict(sample_id=sample_id, kind='measurement', role='stm_development',
                            group_id='ttmapp-known-acquisition', record=record,
                            source_file=source_file, rows_file=rows_file, truth_file=None,
                            rows_sha256=files[rows_file],
                            cache_group=group['group_id']))
        records.append(record)
        sources.append(dict(sample_id=sample_id, source=str(original.resolve()),
                            source_sha256=record['sha256'], output=source_file))
    if len(entries) != 186 or len(truth_index) != 162:
        raise ValueError('Incomplete E7 input matrix')
    _json(out, 'analysis/manifest.json', dict(schema='stmdomains-input-v1', samples=records,
          coordinate_convention='x,y pixel edges; centers x+0.5,y+0.5',
          input_policy='Images, measured masks and object geometry only; no reference labels'), files)
    _json(out, 'truths/index.json', truth_index, files)
    _json(out, 'data-index.json', entries, files)
    _json(out, 'data-provenance.json', dict(
        schema='stmdomains-e7-data-v1', split_groups=dict(train=3, validation=3),
        cases_per_group=len(controls.CASES), groups=6,
        synthetic_samples=162, stm_samples=24, stm_sources=sources,
        renderer_sha256={str(Path(module.__file__).resolve()): file_hash(Path(module.__file__))
                         for module in (controls, original_controls)},
        cross_role_identical_complete_inputs=0, stm_references_opened=False,
        supervision='generator domain truth for synthetic training only; no new real labels',
        limitation='new random realizations of fixed idealized case geometries, not independent acquisitions'), files)
    return entries, files
