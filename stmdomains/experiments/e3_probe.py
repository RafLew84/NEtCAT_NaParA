"""Truth-free paired E3 structure/photometry probe using frozen E2 adapters."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from .bundle import file_hash, write_json
from .e2_features import geometry_features, photometry_features
from .e2_pipeline import spaces
from .e3_inference import encode_readouts
from .e3_metrics import feature_change
from .e3_pipeline import models_for
from .e3_structures import make_structure_probe
from .e3_transforms import CONDITIONS, pixel_stats, transform
from .training.texture import describe_patches

SPACES = ("native", "l2", "adapted")


def _scalar(value):
    return float(value) if value is not None and np.isfinite(value) else None


def run_probe(bank, adapters, gradients, output, check_budget=lambda: None) -> dict:
    """Write paired input/feature changes before any reference evaluation.

    Both samplers use IDENTICAL probe images and encoder outputs; only their
    previously fitted E2 adapters differ. Photometric changes apply directly
    to identity, whereas the three structural conditions use unchanged
    renderer photometry and shared noise. No compound perturbation, adapter
    refit, domain label, physical-pose calibration or model selection occurs.
    """
    output = Path(output)
    names = ("probe-inputs.npz", "probe-metrics.csv", "probe-metadata.json")
    if any((output / name).exists() for name in names):
        raise FileExistsError("Preserve previous E3 probe artifacts")
    output.mkdir(parents=True, exist_ok=True)
    check_budget()
    probe = make_structure_probe()
    structure_conditions = tuple(c for c in probe["conditions"] if c != "identity")
    conditions = tuple(CONDITIONS) + structure_conditions
    count = len(probe["metadata"])
    ids = [f"probe-{i}" for i in range(count)]
    scope = np.ones(count, bool)
    indices = np.arange(count)
    inputs = dict(conditions=np.asarray(conditions), window_ids=np.asarray(ids),
                  structural_conditions=np.asarray(probe["conditions"]),
                  structural_sources96=np.stack([probe["sources96"][c] for c in probe["conditions"]]))
    rows_written, adapter_hashes = 0, {}
    with (output / names[1]).open("w", newline="") as stream:
        writer = None
        for regime in ("transfer", "transductive"):
            check_budget()
            models = models_for(bank, regime)
            features, poses, stats = [], [], []
            regime64, regime48 = [], []
            for condition in conditions:
                check_budget()
                if condition in CONDITIONS:
                    x64 = transform(probe["patches64"]["identity"], condition, gradients[regime]["value"], ids)
                    x48 = transform(probe["native48"]["identity"], condition, gradients[regime]["value"], ids)
                else:
                    x64, x48 = probe["patches64"][condition], probe["native48"][condition]
                regime64.append(x64)
                regime48.append(x48)
                stats.append(pixel_stats(probe["patches64"]["identity"], x64))
                description = dict(describe_patches(x48), available=scope)
                values = {("fft", None): description["features"],
                          ("geometry", None): geometry_features(description),
                          ("photometry", None): photometry_features(dict(available_indices=indices, patches=x64), count)}
                pose = {}
                for (family, seed), model in models.items():
                    encoded = encode_readouts(model, x64)
                    values.update({(name, seed): value for name, value in encoded.items() if not name.startswith("_")})
                    if family == "rvae":
                        pose[seed] = (encoded["_angle"], encoded["_translation"])
                features.append(values)
                poses.append(pose)
            inputs[f"{regime}_patches64"] = np.stack(regime64)
            inputs[f"{regime}_native48"] = np.stack(regime48)
            for run in (r for r in bank.runs if r["regime"] == regime):
                for sampler in ("grid", "centers"):
                    check_budget()
                    adapter = adapters[(run["run_id"], sampler)]
                    relative = f"adapters/{run['run_id']}/{sampler}.json"
                    adapter_hashes[relative] = file_hash(output / relative)
                    prepared = [spaces(v[(run["family"], run["seed"])], adapter, scope) for v in features]
                    base_coordinates, base_valid = prepared[0]
                    for ci, condition in enumerate(conditions):
                        coordinates, valid = prepared[ci]
                        paired = base_valid & valid
                        pixel = stats[ci]
                        delta_angle = delta_translation = None
                        if run["family"].startswith("rvae"):
                            angle0, shift0 = poses[0][run["seed"]]
                            angle1, shift1 = poses[ci][run["seed"]]
                            delta_angle = np.arctan2(np.sin(angle1 - angle0), np.cos(angle1 - angle0))
                            delta_translation = shift1 - shift0
                        for si, space in enumerate(SPACES):
                            scale = adapter["edge_median"] if si == 2 and adapter["available"] else 1.
                            movement = feature_change(base_coordinates[si] / scale, coordinates[si] / scale, paired)
                            for i, realization in enumerate(probe["metadata"]):
                                row = dict(regime=regime, family=run["family"], seed=run["seed"], sampler=sampler,
                                    condition=condition, condition_kind="structure" if condition in structure_conditions else "photometry",
                                    space=space, realization=realization["id"], window_id=ids[i],
                                    baseline_phase_x=realization["baseline_phase_xy"][0], baseline_phase_y=realization["baseline_phase_xy"][1],
                                    renderer_noise_seed=realization["noise_seed"], base_valid=bool(base_valid[i]),
                                    changed_valid=bool(valid[i]), paired_valid=bool(paired[i]), relative_valid=bool(movement["relative_valid"][i]))
                                row.update({key: _scalar(movement[key][i]) for key in
                                            ("absolute_l2", "relative_l2", "base_norm", "changed_norm", "norm_change")})
                                row.update({key: _scalar(pixel[key][i]) for key in pixel})
                                row.update(mean_delta=float(pixel["mean"][i] - pixel["baseline_mean"][i]),
                                    std_delta=float(pixel["std"][i] - pixel["baseline_std"][i]),
                                    angle_delta_radians=None if delta_angle is None else _scalar(delta_angle[i]),
                                    angle_shift_radians=None if delta_angle is None else _scalar(abs(delta_angle[i])),
                                    translation_delta_x=None if delta_translation is None else _scalar(delta_translation[i, 0]),
                                    translation_delta_y=None if delta_translation is None else _scalar(delta_translation[i, 1]),
                                    translation_shift_normalized=None if delta_translation is None else _scalar(np.linalg.norm(delta_translation[i])))
                                if writer is None:
                                    writer = csv.DictWriter(stream, fieldnames=list(row))
                                    writer.writeheader()
                                writer.writerow(row)
                                rows_written += 1
            del models
    check_budget()
    np.savez_compressed(output / names[0], **inputs)
    hashes = {name: file_hash(output / name) for name in names[:2]}
    write_json(output / names[2], dict(
        schema="stmdomains-e3-paired-probe-v1", conditions=list(conditions), window_ids=ids,
        realizations=probe["metadata"], structural_changes=probe["changes"],
        photometry=probe["photometry"], interpretation=probe["interpretation"], rows=rows_written,
        gradient_calibration=gradients, adapter_sha256=adapter_hashes,
        checkpoint_lineage=bank.audit()["checkpoint_lineage"],
        files=hashes, code_sha256={name: file_hash(Path(__file__).with_name(name)) for name in
            ("e3_probe.py", "e3_structures.py", "e3_transforms.py", "e3_inference.py", "e3_metrics.py")},
        spaces=list(SPACES), adapted_units="PCA coordinates divided by the frozen training edge median",
        pose_units="angle radians with full2pi wrap; translation in decoder normalized coordinates, already scaled0.1",
        sampler_interpretation="identical images and raw features; only the frozen adapter differs",
        inference_device="cpu", posterior="deterministic encoder mean", encoder_training=False,
        adapter_fitting=False, references_opened=False, domain_claims=False))
    hashes[names[2]] = file_hash(output / names[2])
    return hashes
