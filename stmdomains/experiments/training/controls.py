"""Reserve fresh synthetic realizations for evaluation after trials 21/22.

Only ``analysis/`` may be passed to a predictor. Truth, case names, seeds,
pairings and expected behavior live separately in ``evaluation/``. These
controls are not used for representation training or checkpoint selection.
"""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
import tempfile

import numpy as np
import scipy

from .. import controls as original
from ..bundle import file_hash, validate_input, write_arrays, write_json

FINAL_SEEDS = (920001, 920002, 920003)
EXTRA_CASES = (
    "independent_rows", "empty_gap", "missing_band", "insufficient_field",
    "orientation_8deg",
)
CASES = (*original.CASES, *EXTRA_CASES)


def make_control(case: str, seed: int) -> tuple[dict, dict, dict]:
    """Reuse all issue-14 controls and add targeted, explicitly scored cases."""
    if case in original.CASES:
        return original.make_control(case, seed)
    if case not in EXTRA_CASES:
        raise ValueError(f"Unknown control: {case}")
    shape = (20, 20) if case == "insufficient_field" else (192, 192)
    _, xx = np.indices(shape)
    x = xx + .5
    rng = np.random.default_rng(seed)
    points = original.lattice(shape)
    ids = np.array([f"p{i:05}" for i in range(len(points))], dtype="U64")
    observed = points.copy()
    rendered = points.copy()
    domains = np.ones(shape, np.int16)
    types = np.ones(shape, np.int16)
    angles = np.zeros(shape, float)
    spacing = np.full(shape, 12., float)
    boundary = np.zeros(shape, bool)
    support_valid = np.ones(shape, bool)
    extra = {}

    if case == "independent_rows":
        # Each row has its own phase; no common 2D translation is imposed.
        row_y = np.arange(6., shape[0], 12.)
        phases = rng.uniform(0., 12., len(row_y))
        rendered = np.vstack([
            np.column_stack((np.arange(phase, shape[1], 12.),
                             np.full(len(np.arange(phase, shape[1], 12.)), y)))
            for y, phase in zip(row_y, phases)
        ])
        observed = rendered.copy()
        ids = np.array([f"p{i:05}" for i in range(len(observed))], dtype="U64")
        domains[:] = 0
        types[:] = 0
        extra.update(
            expected_state="disordered",
            interpretation="Independent ordered rows are not a common two-dimensional lattice",
            row_phases_reference_px=phases.tolist(),
            chance_local_alignment_is_possible=True,
        )
    elif case in ("empty_gap", "missing_band"):
        # Identical annotation geometry/IDs; only the underlying signal differs.
        keep = np.abs(points[:, 0] - shape[1] / 2) >= 18
        observed = points[keep]
        ids = ids[keep]
        extra.update(
            pair_case="missing_band" if case == "empty_gap" else "empty_gap",
            pair_invariant="centers_xy, boxes_xyxy, object_ids; same image noise realization",
            gap_x_reference_px=[78., 114.],
            missing_annotation_is_not_missing_material=case == "missing_band",
        )
        if case == "empty_gap":
            rendered = observed
            domains[:, 78:114] = 0
            domains[:, 114:] = 2
            types[domains == 0] = 0
            boundary = (np.abs(x - 78) < 3) | (np.abs(x - 114) < 3)
    elif case == "orientation_8deg":
        second = original.lattice(shape, angle=8.)
        rendered = np.vstack((points[points[:, 0] < 96], second[second[:, 0] >= 96]))
        observed = rendered.copy()
        ids = np.array([f"p{i:05}" for i in range(len(observed))], dtype="U64")
        domains[x >= 96] = 2
        angles[x >= 96] = 8.
        boundary = np.abs(x - 96) < 3
    else:
        # The generator knows the lattice but this field is below the smallest
        # planned 32px support. Excluding it prevents scoring refusal as error.
        support_valid[:] = False
        extra.update(
            expected_state="insufficient_data",
            expected_domain_count=None,
            latent_domain_count=1,
            minimum_planned_support_reference_px=32,
            interpretation="Known generative lattice, insufficient observed extent for a domain claim",
        )

    image = original.render_points(rendered, shape, np.random.default_rng(seed + 40000))
    arrays = dict(
        image=image, measured=np.ones(shape, bool), centers_xy=observed,
        boxes_xyxy=np.column_stack((observed - 2.5, observed + 2.5)), object_ids=ids,
    )
    validate_input(arrays)
    angles[domains == 0] = np.nan
    spacing[domains == 0] = np.nan
    truth = dict(
        domain_labels=domains, type_labels=types, orientation_deg=angles,
        spacing_reference_px=spacing, boundary_uncertain=boundary,
        support_valid=support_valid, evaluation_valid=~boundary & support_valid,
    )
    meta = dict(
        case=case, seed=seed, expected_domain_count=int(domains.max()),
        scope="idealized_lattice_domains_not_material_coverage",
        boundary_tolerance_px=3., pixel_spacing_xy=[1., 1.],
        offset_in_base_xy=[0., 0.],
        render=dict(psf_sigma_reference_px=1.25, noise_sigma=.025),
    )
    meta.update(extra)
    return arrays, truth, meta


def prepare(out: Path) -> dict:
    """Publish a complete immutable evaluation bundle; never overwrite one."""
    out = Path(out)
    if out.exists():
        raise FileExistsError(f"Use a fresh output directory: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".training-controls-", dir=out.parent) as temporary:
        staging = Path(temporary) / "bundle"
        inputs, evaluations = [], []
        for index, (seed, case) in enumerate(
            ((seed, case) for seed in FINAL_SEEDS for case in CASES), start=1,
        ):
            ident = f"heldout-{index:04}"
            arrays, truth, meta = make_control(case, seed)
            relative = f"samples/{ident}.npz"
            inputs.append(dict(
                sample_id=ident, kind="synthetic", file=relative,
                coordinate_system="raw_edge_xy", shape_hw=list(arrays["image"].shape),
                pixel_spacing_xy=meta["pixel_spacing_xy"], position_unit="reference_px",
                annotation_count=len(arrays["object_ids"]),
                **write_arrays(staging / "analysis" / relative, arrays),
            ))
            relative = f"controls/{ident}.npz"
            evaluations.append(dict(
                sample_id=ident, file=relative, **meta,
                split="final_evaluation", **write_arrays(staging / "evaluation" / relative, truth),
            ))
        lookup = {(record["seed"], record["case"]): record["sample_id"] for record in evaluations}
        for record in evaluations:
            if record.get("pair_case"):
                record["paired_sample_id"] = lookup[record["seed"], record["pair_case"]]
        write_json(staging / "analysis/manifest.json", dict(
            schema="stmdomains-input-v1", samples=inputs,
            coordinate_convention="x,y pixel edges; pixel centers x+0.5,y+0.5",
            intensity="Synthetic Gaussian PSF plus noise; no preview gamma",
            input_policy="Images, measurement masks and object geometry only; no domain labels",
        ))
        write_json(staging / "evaluation/manifest.json", dict(
            schema="stmdomains-evaluation-v1", controls=evaluations, references=[],
            role="Reserved final realizations for 21/22; exclude from training and selection",
            seeds=list(FINAL_SEEDS), development="Previously used controls from 14-19",
            boundary_exclusion_reference_px=3,
            insufficient_field_policy="Score insufficient_data state; do not score domain pairs",
            independent_rows_limitation="Random row phases can produce short accidental local alignments",
            novelty="Fresh noise/random phases, same idealized case families; not independent acquisitions",
        ))
        audit = dict(
            schema="stmdomains-training-controls-v1", sample_count=len(inputs),
            case_count=len(CASES), seeds=list(FINAL_SEEDS), role="final_evaluation_reserved",
            used_for_training=False, predictions_computed=False,
            analysis_manifest_sha256=file_hash(staging / "analysis/manifest.json"),
            evaluation_manifest_sha256=file_hash(staging / "evaluation/manifest.json"),
            code_sha256={
                "training/controls.py": file_hash(Path(__file__)),
                "controls.py": file_hash(Path(original.__file__)),
                "bundle.py": file_hash(Path(__file__).parent.parent / "bundle.py"),
            },
            environment=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
        )
        write_json(staging / "audit.json", audit)
        staging.rename(out)
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.out), indent=2))


if __name__ == "__main__":
    main()
