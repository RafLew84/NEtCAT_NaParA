"""Descriptive feature checks after prediction freeze; never select a model."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from ..bundle import file_hash, write_json
from .predict import read_json


def representation_summary(content, brightness, frames):
    values = np.asarray(content, float)
    good = np.isfinite(values).all(axis=1)
    values, brightness, frames = values[good], np.asarray(brightness)[good], np.asarray(frames)[good]
    if not len(values):
        return dict(elements=0, std_min=None, std_max=None, effective_rank=None)
    centered = values-values.mean(axis=0)
    std = centered.std(axis=0)
    singular = np.linalg.svd(centered, compute_uv=False)
    variance = singular**2
    probabilities = variance[variance > 0]/variance.sum() if variance.sum() else np.array([])
    effective_rank = float(np.exp(-np.sum(probabilities*np.log(probabilities)))) if len(probabilities) else 0.
    correlations = {}
    for name, target in [('brightness', brightness), ('frame_number', frames)]:
        target = target-target.mean()
        denominator = np.linalg.norm(centered, axis=0)*np.linalg.norm(target)
        allowed = denominator > 0
        corr = np.zeros(values.shape[1])
        corr[allowed] = target@centered[:, allowed]/denominator[allowed]
        correlations[name] = float(np.max(np.abs(corr[allowed]))) if allowed.any() else None
    return dict(elements=len(values), std_min=float(std.min()), std_max=float(std.max()),
                effective_rank=effective_rank, max_absolute_dimension_correlation=correlations,
                interpretation='Exploratory correlations on emitted features, not a causal test or selection criterion')


def summarize(output, evaluation):
    frozen = output/'frozen-predictions.json'
    if not frozen.exists():
        raise ValueError('Prediction freeze required before diagnostic evaluation')
    # The main evaluator verifies all artifacts. This module also checks every
    # feature/cache file it reads against the already published freeze.
    frozen_manifest = read_json(frozen)
    checked = set()
    def check(path):
        relative = str(path.relative_to(output))
        if relative not in checked:
            if file_hash(path) != frozen_manifest['files'][relative]:
                raise ValueError('Changed frozen artifact: '+relative)
            checked.add(relative)
    groups = read_json(output/'cache/index.json')
    runs = read_json(output/'features/index.json')
    truth_manifest = read_json(evaluation/'manifest.json')
    truth_records = {r['sample_id']: r for r in truth_manifest['controls']}
    feature_rows, angle_rows = [], []
    for run in runs:
        contents, brightness, frames, errors = [], [], [], []
        for group in groups:
            if group['sampler'] != 'grid' or group['scale_px'] != 48:
                continue
            ident = group['record']['sample_id']
            features_path = (output/'features'/run['run_id']/group['group_id']).with_suffix('.npz')
            check(features_path)
            with np.load(features_path, allow_pickle=False) as archive:
                content, angle, mse = archive['content'], archive['angle_radians'], archive['reconstruction_mse']
            rows_path = output/'cache'/group['group_id']/'rows.json.gz'
            check(rows_path)
            rows = read_json(rows_path)
            if group['record']['kind'] == 'measurement':
                cache_path = output/'cache'/group['group_id']/f"{run['regime']}.npz"
                check(cache_path)
                with np.load(cache_path, allow_pickle=False) as archive:
                    patch_brightness = archive['patches'].mean((1, 2))
                    indices = archive['available_indices']
                contents.extend(content[indices])
                brightness.extend(patch_brightness)
                frames.extend([group['record']['frame_number']]*len(indices))
                errors.extend(mse[indices].tolist())
            elif run['family'] == 'rvae':
                record = truth_records[ident]
                path = evaluation/record['file']
                if file_hash(path) != record['sha256']:
                    raise ValueError('Truth artifact changed')
                with np.load(path, allow_pickle=False) as archive:
                    domains, truth_angle = archive['domain_labels'], archive['orientation_deg']
                    valid = archive['evaluation_valid']
                coordinates = np.floor([r['raw_edge_xy'] for r in rows]).astype(int).reshape(-1, 2)
                xy = coordinates[:, 0], coordinates[:, 1]
                domain = domains[xy[1], xy[0]]
                accepted = np.array([r['available'] for r in rows]) & valid[xy[1], xy[0]] & np.isfinite(angle)
                medians = []
                for part in sorted(set(domain[accepted])-{0}):
                    use = accepted & (domain == part)
                    truth = truth_angle[xy[1][use], xy[0][use]]
                    resultant = np.mean(np.exp(1j*angle[use]))
                    concentration = float(abs(resultant))
                    circular_mean = float(np.angle(resultant)*180/np.pi) if concentration > 1e-8 else None
                    medians.append(dict(part=int(part), elements=int(use.sum()),
                                        raw_model_angle_deg=circular_mean,
                                        circular_resultant_length=concentration,
                                        angle_statistic='circular_mean; low concentration means dispersed/ambiguous angle',
                                        truth_orientation_deg=float(np.median(truth)) if np.isfinite(truth).all() else None))
                raw_delta = truth_delta = None
                if len(medians) == 2 and all(r['raw_model_angle_deg'] is not None for r in medians):
                    raw_delta = (medians[1]['raw_model_angle_deg']-medians[0]['raw_model_angle_deg']+180)%360-180
                    if all(r['truth_orientation_deg'] is not None for r in medians):
                        truth_delta = medians[1]['truth_orientation_deg']-medians[0]['truth_orientation_deg']
                angle_rows.append(dict(run_id=run['run_id'], sample_id=ident, case=record['case'],
                                       control_seed=record['seed'], parts=medians,
                                       raw_difference_deg=raw_delta, truth_difference_deg=truth_delta,
                                       interpretation='Raw latent-angle diagnostic; no fitted offset or assumed lattice symmetry, not validated orientation'))
        feature_rows.append(dict(run_id=run['run_id'], **representation_summary(contents, brightness, frames),
                                 mean_clean_reconstruction_mse=float(np.mean(errors)) if errors else None,
                                 scope='All available 48px grid windows in 24 TTMAPP fields; descriptive only'))
    result = dict(schema='stmdomains-issue21-feature-diagnostics-v1',
                  freeze_sha256=file_hash(frozen), features=feature_rows, angles=angle_rows,
                  no_checkpoint_or_threshold_selection=True)
    write_json(output/'feature-diagnostics.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('.scratch/autoencoder-21'))
    parser.add_argument('--evaluation', type=Path, default=Path('.scratch/training-20/controls/evaluation'))
    args = parser.parse_args()
    result = summarize(args.output, args.evaluation)
    print(f"{len(result['features'])} representation summaries; {len(result['angles'])} angle diagnostics")


if __name__ == '__main__':
    main()
