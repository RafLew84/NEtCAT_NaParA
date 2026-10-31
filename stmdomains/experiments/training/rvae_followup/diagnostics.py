"""Post-freeze descriptive diagnostics for the bounded issue-21a matrix.

No metric in this module selects a checkpoint, threshold, or another training
configuration. Quarter turns have identical pixel support and no interpolation;
their symmetry-reduced error is explicitly uninformative on a square lattice.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path

import numpy as np

from ...bundle import file_hash, write_json
from ..diagnostics import representation_summary
from ..fit import TrainingData
from ..predict import read_json


FAMILIES = ("rvae", "rvae_lowkl", "rvae_fourier", "rvae_fourier_lowkl")
FAMILY_LABELS = {
    "ae": "AE — odniesienie", "rvae": "rVAE — oryginalny, β=0,001",
    "rvae_lowkl": "rVAE — oryginalny, β=0,0001",
    "rvae_fourier": "rVAE — Fourier, β=0,001",
    "rvae_fourier_lowkl": "rVAE — Fourier, β=0,0001",
    "fft": "FFT — odniesienie",
}
ROTATION_RULE = dict(
    quarter_turns=[-1, 0, 1], expected_latent_delta_degrees="-90*k",
    support="Entire cached 64x64 patch; exact np.rot90; no interpolation or padding",
    selection="Up to16 available patches per sample, evenly spaced in sorted window-ID order",
    symmetry="Infer finite proper rotational lattice group from known generator basis only; real images have no assumed period",
    limitation="A90-degree turn is already equivalent for a square lattice; zero symmetry-reduced error alone does not demonstrate angle learning",
)


@contextmanager
def reporting_stage(output: Path, name: str):
    """Share the two-hour postprocessing ledger with inference/evaluation."""
    from .evaluate import PostprocessBudget
    target = output / f"{name}.resources.json"
    if target.exists():
        raise FileExistsError(target)
    budget = PostprocessBudget(output)
    status = "failed"
    try:
        budget.check()
        yield budget
        budget.check()
        status = "completed"
    finally:
        write_json(target, dict(stage=name, status=status, **budget.measurements()))


def wrap_degrees(values, period=360.):
    return (np.asarray(values, dtype=float) + period / 2) % period - period / 2


def lattice_period_degrees(basis) -> float:
    """Smallest proper rotation preserving the supplied two-dimensional lattice.

    The crystallographic restriction supplies candidate orders, but no order is
    assumed: a rotated basis must be an integer unimodular change of basis.
    """
    basis = np.asarray(basis, dtype=float)
    if basis.shape != (2, 2) or not np.isfinite(basis).all() or abs(np.linalg.det(basis)) < 1e-12:
        raise ValueError("A nonsingular finite2D lattice basis is required")
    inverse = np.linalg.inv(basis)
    for degrees in (60., 90., 120., 180., 360.):
        angle = np.deg2rad(degrees)
        rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        coefficients = basis @ rotation @ inverse
        rounded = np.rint(coefficients)
        if np.allclose(coefficients, rounded, atol=1e-7, rtol=0) and np.isclose(np.linalg.det(rounded), 1.):
            return degrees
    raise AssertionError("Identity must preserve a lattice")


def selected_indices(available_indices, maximum=16, *, window_ids=None):
    indices = np.asarray(available_indices, dtype=int)
    if not len(indices):
        return indices
    order = np.arange(len(indices)) if window_ids is None else np.array(sorted(
        range(len(indices)), key=lambda position: window_ids[indices[position]]))
    return order[np.linspace(0, len(indices) - 1, min(maximum, len(indices)), dtype=int)]


def circular_statistic(degrees, period=360.) -> dict:
    values = np.asarray(degrees, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return dict(elements=0, mean_deg=None, resultant_length=None)
    resultant = np.mean(np.exp(2j * np.pi * values / period))
    concentration = float(abs(resultant))
    return dict(elements=len(values), mean_deg=float(np.angle(resultant) * period / (2 * np.pi)) if concentration > 1e-8 else None,
                resultant_length=concentration)


def residual_summary(values, period=360.) -> dict:
    values = wrap_degrees(values, period)
    values = values[np.isfinite(values)]
    return dict(period_deg=float(period), **circular_statistic(values, period),
                mean_absolute_deg=float(np.mean(abs(values))) if len(values) else None,
                median_absolute_deg=float(np.median(abs(values))) if len(values) else None,
                q90_absolute_deg=float(np.quantile(abs(values), .9)) if len(values) else None)


def support_domain(row, truth) -> tuple[int, float | None]:
    """Require one positive truth domain across the complete effective support."""
    if not row["available"]:
        return 0, None
    x0, y0, x1, y1 = row["support_xyxy"]
    x0, y0, x1, y1 = int(np.floor(x0)), int(np.floor(y0)), int(np.ceil(x1)), int(np.ceil(y1))
    domains = truth["domain_labels"]
    if x0 < 0 or y0 < 0 or x1 > domains.shape[1] or y1 > domains.shape[0] or x0 >= x1 or y0 >= y1:
        return 0, None
    region = domains[y0:y1, x0:x1]
    valid = truth["evaluation_valid"][y0:y1, x0:x1]
    if not valid.all() or region[0, 0] <= 0 or not np.all(region == region[0, 0]):
        return 0, None
    angles = truth["orientation_deg"][y0:y1, x0:x1]
    angle = float(np.median(angles)) if np.isfinite(angles).all() else None
    return int(region[0, 0]), angle


def known_period(record, truth) -> float | None:
    if not np.any(truth["domain_labels"] > 0):
        return None
    # The audited generator uses lattice(spacing, skew=0) for its finite-angle
    # lattice truths. Its oblique case explicitly supplies the non-square basis.
    basis = record.get("lattice_basis_reference_px")
    if basis is None and np.isfinite(truth["orientation_deg"][truth["domain_labels"] > 0]).any():
        basis = [[1., 0.], [0., 1.]]
    return lattice_period_degrees(basis) if basis is not None else None


def angle_parts(angles, rows, truth, period) -> dict:
    labels = np.array([support_domain(row, truth)[0] for row in rows])
    expected = np.array([support_domain(row, truth)[1] for row in rows], dtype=float)
    degrees = np.rad2deg(angles)
    parts = []
    for label in sorted(set(labels) - {0}):
        use = (labels == label) & np.isfinite(degrees)
        if not use.any():
            continue
        true_values = expected[use]
        parts.append(dict(part=int(label), elements=int(use.sum()),
                          raw=circular_statistic(degrees[use]),
                          lattice=circular_statistic(degrees[use], period) if period is not None else None,
                          truth_orientation_deg=float(np.median(true_values)) if np.isfinite(true_values).all() else None))
    raw_difference = truth_difference = lattice_difference = lattice_error = None
    if len(parts) == 2:
        if all(p["raw"]["mean_deg"] is not None for p in parts):
            raw_difference = float(wrap_degrees(parts[1]["raw"]["mean_deg"] - parts[0]["raw"]["mean_deg"]))
        if all(p["truth_orientation_deg"] is not None for p in parts):
            truth_difference = parts[1]["truth_orientation_deg"] - parts[0]["truth_orientation_deg"]
        if period is not None and all(p["lattice"]["mean_deg"] is not None for p in parts):
            lattice_difference = float(wrap_degrees(parts[1]["lattice"]["mean_deg"] - parts[0]["lattice"]["mean_deg"], period))
            if truth_difference is not None:
                lattice_error = float(wrap_degrees(lattice_difference - truth_difference, period))
    return dict(parts=parts, lattice_period_deg=period, raw_difference_deg=raw_difference,
                truth_difference_deg=truth_difference, lattice_difference_deg=lattice_difference,
                lattice_difference_error_deg=lattice_error,
                support="Complete effective support in one positive valid truth part")


def _run_beta(run):
    return .0001 if run["family"].endswith("lowkl") else .001 if run["family"].startswith("rvae") else 0.


def _validation_diagnostic(model, batches, device, beta, check):
    import torch
    contents, means, frames = [], [], []
    total_mse = total_kl = 0.
    count = 0
    with torch.inference_mode():
        for inputs, targets in batches:
            check()
            output = model(inputs.to(device), sample=False)
            error = (output["reconstruction"] - targets.to(device)).square().mean((1, 2, 3))
            total_mse += float(error.sum())
            total_kl += float(output["kl_per_sample"].sum())
            contents.extend(output["content"].cpu().numpy())
            means.extend(targets.numpy().mean((1, 2, 3)))
            frames.extend([0] * len(inputs))
            count += len(inputs)
    mse, kl = total_mse / count, total_kl / count
    return dict(elements=count, mse=mse, kl=kl, beta=beta, weighted_kl=beta * kl,
                loss=mse + beta * kl, representation=representation_summary(contents, means, frames))


def summarize(output: Path, baseline: Path, evaluation: Path, prepared: Path, *, device="cpu"):
    from .evaluate import verify_freeze
    from .models import load_model
    import torch
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    with reporting_stage(output, "diagnostics") as budget:
        verify_freeze(output, check_budget=budget.check)
        groups = read_json(output / "cache/index.json")
        runs = read_json(output / "features/index.json")
        groups = [g for g in groups if g["sampler"] == "grid" and g["scale_px"] == 48]
        manifest = read_json(evaluation / "manifest.json")
        controls = {record["sample_id"]: record for record in manifest["controls"]}
        truths = {}
        for ident, record in controls.items():
            path = evaluation / record["file"]
            if file_hash(path) != record["sha256"]:
                raise ValueError(f"Changed truth: {ident}")
            with np.load(path, allow_pickle=False) as archive:
                truths[ident] = {key: archive[key] for key in ("domain_labels", "orientation_deg", "evaluation_valid")}
        rotation_data, caches = [], {}
        for group in groups:
            budget.check()
            ident = group["record"]["sample_id"]
            folder = output / "cache" / group["group_id"]
            rows = read_json(folder / "rows.json.gz")
            with np.load(folder / "transfer.npz", allow_pickle=False) as archive:
                available, patches = archive["available_indices"], archive["patches"]
            pick = selected_indices(available, window_ids=[row["window_id"] for row in rows])
            period = known_period(controls[ident], truths[ident]) if ident in truths else None
            pure = np.array([support_domain(rows[i], truths[ident])[0] > 0 for i in available[pick]], dtype=bool) if ident in truths else np.zeros(len(pick), bool)
            rotation_data.append(dict(group=group, rows=rows, indices=available[pick], patches=patches[pick],
                                      period=period, pure=pure))
            caches[group["group_id"]] = dict(rows=rows, available=available,
                                             brightness=patches.mean((1, 2)) if len(patches) else np.array([]))
        features, angles, rotations, checkpoints = [], [], [], []
        validation = TrainingData(prepared, "transfer").validation_batches()
        for run in runs:
            budget.check()
            contents, brightness, frames, errors = [], [], [], []
            for group in groups:
                ident = group["record"]["sample_id"]
                path = (output / "features" / run["run_id"] / group["group_id"]).with_suffix(".npz")
                with np.load(path, allow_pickle=False) as archive:
                    content, angle, mse = archive["content"], archive["angle_radians"], archive["reconstruction_mse"]
                cache = caches[group["group_id"]]
                if group["record"]["kind"] == "measurement":
                    indices = cache["available"]
                    contents.extend(content[indices]); brightness.extend(cache["brightness"])
                    frames.extend([group["record"]["frame_number"]] * len(indices)); errors.extend(mse[indices])
                elif run["family"].startswith("rvae"):
                    period = known_period(controls[ident], truths[ident])
                    angles.append(dict(run_id=run["run_id"], family=run["family"], seed=run["seed"],
                                       sample_id=ident, case=controls[ident]["case"], control_seed=controls[ident]["seed"],
                                       **angle_parts(angle, cache["rows"], truths[ident], period)))
            features.append(dict(run_id=run["run_id"], family=run["family"], seed=run["seed"],
                                 **representation_summary(contents, brightness, frames),
                                 mean_clean_reconstruction_mse=float(np.mean(errors)) if errors else None,
                                 scope="All available real48grid windows, descriptive; not held-out generalization"))
            if not run["family"].startswith("rvae"):
                continue
            directory = Path(run["directory"])
            for step in (None, 2000):
                budget.check()
                if step and not (directory / f"step-{step:04}.pt").exists():
                    checkpoints.append(dict(run_id=run["run_id"], checkpoint="step2000", available=False))
                    continue
                model = load_model(directory, device=device, step=step)
                checkpoints.append(dict(run_id=run["run_id"], family=run["family"], seed=run["seed"],
                                        checkpoint="selected" if step is None else "step2000", available=True,
                                        step=run["run_metadata"]["selected_step"] if step is None else step,
                                        validation=_validation_diagnostic(model, validation, device, _run_beta(run), budget.check)))
                if step is None:
                    with torch.inference_mode():
                        for item in rotation_data:
                            budget.check()
                            patches = item["patches"]
                            if not len(patches):
                                continue
                            zero = model.encode(torch.from_numpy(patches[:, None]).to(device))["angle_radians"].cpu().numpy()
                            for k in (-1, 1):
                                turned = np.ascontiguousarray(np.rot90(patches, k, axes=(-2, -1)))
                                theta = model.encode(torch.from_numpy(turned[:, None]).to(device))["angle_radians"].cpu().numpy()
                                residual = np.rad2deg(theta - zero) + 90 * k
                                period = item["period"]
                                symmetry = residual_summary(residual[item["pure"]], period) if period is not None else None
                                rotations.append(dict(run_id=run["run_id"], family=run["family"], seed=run["seed"],
                                                      sample_id=item["group"]["record"]["sample_id"],
                                                      kind=item["group"]["record"]["kind"], quarter_turn=k,
                                                      element_ids=[item["rows"][i]["element_id"] for i in item["indices"]],
                                                      original_angle_deg=np.rad2deg(zero).tolist(), rotated_angle_deg=np.rad2deg(theta).tolist(),
                                                      raw=residual_summary(residual), known_lattice=symmetry,
                                                      quarter_turn_is_lattice_equivalence=bool(period is not None and np.isclose(90 % period, 0.))))
                del model
            print(f"diagnostics {run['run_id']}", flush=True)
        result = dict(schema="stmdomains-issue21a-feature-diagnostics-v1", freeze_sha256=file_hash(output / "frozen-predictions.json"),
                      source_sha256=file_hash(Path(__file__)), baseline=str(baseline.resolve()), device=device,
                      features=features, angles=angles, checkpoints=checkpoints, rotation_rule=ROTATION_RULE,
                      rotations=rotations, no_checkpoint_or_threshold_selection=True)
        write_json(output / "feature-diagnostics.json", result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, default=Path(".scratch/autoencoder-21"))
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, default=Path(".scratch/training-20"))
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    result = summarize(args.output, args.baseline, args.evaluation, args.prepared, device=args.device)
    print(json.dumps(dict(features=len(result["features"]), angles=len(result["angles"]), rotations=len(result["rotations"]))))


if __name__ == "__main__":
    main()
