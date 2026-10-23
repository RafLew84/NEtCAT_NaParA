"""CLI: build an immutable, reproducible issue-14 bundle from audited TTMAPP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import tempfile

import numpy as np
import scipy
import PIL

from .bundle import file_hash, write_arrays, write_json
from .controls import CASES, SEEDS, make_control
from .real_input import PILOT_NUMBERS, load_ttmapp


def build_analysis(samples, output: Path) -> tuple[dict, list]:
    """Does not accept any reference path or manual labels."""
    records, truths = [], []
    for record, arrays in samples:
        relative = f'samples/{record["sample_id"]}.npz'
        records.append({**record, "file": relative, **write_arrays(output/relative, arrays)})
    counter = 0
    for split, seeds in SEEDS.items():
        for seed in seeds:
            for case in CASES:
                counter += 1
                sample_id = f"control-{counter:04}"
                arrays, truth, meta = make_control(case, seed)
                relative = f"samples/{sample_id}.npz"
                # Case names, split, seed and expected counts are evaluation-only.
                records.append(dict(sample_id=sample_id, kind="synthetic", file=relative,
                                    coordinate_system="raw_edge_xy", shape_hw=list(arrays["image"].shape),
                                    pixel_spacing_xy=meta["pixel_spacing_xy"], position_unit="reference_px",
                                    annotation_count=len(arrays["object_ids"]),
                                    **write_arrays(output/relative, arrays)))
                truths.append((sample_id, truth, {**meta, "split": split}))
    manifest = dict(schema="stmdomains-input-v1", samples=records,
                    coordinate_convention="x,y in pixel-edge coordinates; pixel centers x+0.5,y+0.5",
                    intensity="MPP reader values, no preview gamma; synthetic Gaussian PSF plus noise",
                    input_policy="Images, measurement mask, current object geometry/IDs only; no domain labels")
    write_json(output/"manifest.json", manifest)
    return manifest, truths


def prepare(mpp: Path, session: Path, review: Path | None, out: Path, *, full_series=False) -> dict:
    if out.exists():
        raise FileExistsError(f"Use a fresh output directory: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".preparing-domains-", dir=out.parent) as temp:
        staging = Path(temp)/"bundle"
        samples, geometry, audit = load_ttmapp(mpp, session, range(1, 269) if full_series else PILOT_NUMBERS)
        manifest, truths = build_analysis(samples, staging/"analysis")
        evaluation = staging/"evaluation"
        control_records = []
        for sample_id, arrays, meta in truths:
            relative = f"controls/{sample_id}.npz"
            control_records.append(dict(sample_id=sample_id, file=relative, **meta,
                                        **write_arrays(evaluation/relative, arrays)))
        references = []
        if review is not None:
            from .references import prepare_references
            if not review.is_dir():
                raise ValueError("Reference directory does not exist")
            references = prepare_references(review, geometry, evaluation)
            expected = set(range(250, 269)) - {255}
            if {int(r["sample_id"].split('-')[1]) for r in references} != expected:
                raise ValueError("Expected the 18 audited manual/clean pairs")
            if sum(len(r["regions"]) for r in references) != 54:
                raise ValueError("Reference extraction differs from audited 54 cores")
        write_json(evaluation/"manifest.json", dict(schema="stmdomains-evaluation-v1",
                   controls=control_records, references=references,
                   reference_semantics="Partial, previously used orientation-group cores; not complete domains/types/coverage",
                   reference_labels={"0": "unlabeled_or_excluded", "1": "BLACK", "2": "RED", "3": "YELLOW"},
                   missing_reference_frame_numbers=[255],
                   core_margin_raw_px=3, margin_is_calibrated_boundary_error=False))
        audit.update(schema="stmdomains-preparation-v1", synthetic_count=len(truths),
                     reference_frame_count=len(references), reference_core_count=sum(len(r["regions"]) for r in references),
                     control_cases=list(CASES), seeds=SEEDS,
                     environment=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__, pillow=PIL.__version__),
                     code_sha256={p.name: file_hash(p) for p in sorted(Path(__file__).parent.glob('*.py'))},
                     analysis_manifest_sha256=file_hash(staging/"analysis/manifest.json"),
                     evaluation_manifest_sha256=file_hash(evaluation/"manifest.json"))
        write_json(staging/"audit.json", audit)
        from .preview import make_preview
        make_preview(staging, manifest)
        staging.rename(out)
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mpp', type=Path, required=True)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--review', type=Path, help='Evaluation-only clean/manual pairs; omit to verify input independence')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--full-series', action='store_true', help='Export all 268 frames instead of the 24-frame pilot')
    args = parser.parse_args()
    audit = prepare(args.mpp, args.session, args.review, args.out, full_series=args.full_series)
    print(json.dumps({k: audit[k] for k in ('selected_frame_numbers', 'synthetic_count', 'reference_frame_count', 'reference_core_count')}, indent=2))


if __name__ == '__main__':
    main()
