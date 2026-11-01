"""Fresh issue-24 controls, with analysis and evaluation trees kept separate.

The four annotation perturbations preserve the rendered image and domain truth.
Generating truth is not model evaluation; training never receives this tree.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile

import numpy as np

from ...bundle import arrays_hash, file_hash, validate_input, write_arrays, write_json
from .. import controls as previous


SEEDS = (920021, 920022, 920023)
PERTURBATIONS = ("centers_jitter_036", "centers_jitter_072",
                 "centers_duplicates_10", "phase_centers_jitter_072")
CASES = (*previous.CASES, *PERTURBATIONS)


def make_control(case: str, seed: int) -> tuple[dict, dict, dict]:
    if case in previous.CASES:
        return previous.make_control(case, seed)
    if case not in PERTURBATIONS:
        raise ValueError(f"Unknown issue-24 control: {case}")
    base = "phase_boundary" if case == "phase_centers_jitter_072" else "single"
    arrays, truth, metadata = previous.make_control(base, seed)
    arrays = {name: value.copy() for name, value in arrays.items()}
    before = {name: arrays_hash({name: arrays[name]}) for name in ("image", "measured")}
    rng = np.random.default_rng(seed + 240000)
    original_ids = arrays["object_ids"].copy()
    duplicate_sources = {}
    perturbation = {}
    if case == "centers_duplicates_10":
        indices = rng.permutation(len(original_ids))[:round(.1 * len(original_ids))]
        new_ids = np.array([f"{original_ids[index]}--duplicate" for index in indices], dtype="U64")
        arrays["centers_xy"] = np.concatenate((arrays["centers_xy"], arrays["centers_xy"][indices]))
        arrays["boxes_xyxy"] = np.concatenate((arrays["boxes_xyxy"], arrays["boxes_xyxy"][indices]))
        arrays["object_ids"] = np.concatenate((original_ids, new_ids))
        duplicate_sources = {str(new): str(original_ids[index]) for new, index in zip(new_ids, indices)}
        perturbation = dict(kind="exact_duplicate_annotations", fraction=.1,
                            duplicate_count=len(indices), position_offset_reference_px=0.)
    else:
        sigma = .36 if case == "centers_jitter_036" else .72
        spacing = np.asarray(metadata["pixel_spacing_xy"], float)
        positions = arrays["centers_xy"] + rng.normal(0., sigma, arrays["centers_xy"].shape) / spacing
        height, width = arrays["image"].shape
        positions = np.clip(positions, [1e-7, 1e-7], [width - 1e-7, height - 1e-7])
        offset = positions - arrays["centers_xy"]
        arrays["centers_xy"] = positions
        arrays["boxes_xyxy"] = arrays["boxes_xyxy"] + np.tile(offset, (1, 2))
        perturbation = dict(kind="gaussian_position_error", sigma_reference_px=sigma,
                            boundary_policy="clip annotation centers into original image; image unchanged")
    validate_input(arrays)
    for name in before:
        if arrays_hash({name: arrays[name]}) != before[name]:
            raise ValueError("Annotation perturbation changed the image or measured mask")
    metadata = dict(metadata, case=case, base_pair=base,
                    perturbation=perturbation, duplicate_source_ids=duplicate_sources,
                    original_annotation_count=len(original_ids),
                    observed_annotation_count=len(arrays["object_ids"]),
                    invariant_fields=["image", "measured", "all truth rasters"],
                    evaluation_note="Truth raster is sampled at observed annotation positions; preserve IDs for paired annotation diagnostics")
    return arrays, truth, metadata


def prepare(output: Path) -> dict:
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Controls must use a fresh directory: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".graph24-controls-", dir=output.parent) as temporary:
        staging = Path(temporary) / "controls"
        samples, evaluations = [], []
        for index, (seed, case) in enumerate(((seed, case) for seed in SEEDS for case in CASES), 1):
            arrays, truth, metadata = make_control(case, seed)
            ident = f"graph-heldout-{index:04}"
            input_file = f"samples/{ident}.npz"
            samples.append(dict(sample_id=ident, kind="synthetic", file=input_file,
                                coordinate_system="raw_edge_xy", shape_hw=list(arrays["image"].shape),
                                pixel_spacing_xy=metadata["pixel_spacing_xy"], position_unit="reference_px",
                                annotation_count=len(arrays["object_ids"]),
                                **write_arrays(staging / "analysis" / input_file, arrays)))
            truth_file = f"controls/{ident}.npz"
            evaluations.append(dict(sample_id=ident, file=truth_file, **metadata,
                                    split="reserved_graph24_evaluation",
                                    **write_arrays(staging / "evaluation" / truth_file, truth)))
        lookup = {(row["seed"], row["case"]): row["sample_id"] for row in evaluations}
        for row in evaluations:
            if row.get("base_pair"):
                row["base_sample_id"] = lookup[row["seed"], row["base_pair"]]
            if row.get("pair_case"):
                row["paired_sample_id"] = lookup[row["seed"], row["pair_case"]]
        write_json(staging / "analysis/manifest.json", dict(
            schema="stmdomains-input-v1", samples=samples,
            coordinate_convention="x,y pixel edges; pixel centers x+0.5,y+0.5",
            input_policy="Only images, measurement masks and annotation geometry; no cases, seeds or domain truth"))
        write_json(staging / "evaluation/manifest.json", dict(
            schema="stmdomains-evaluation-v1", controls=evaluations, references=[], seeds=list(SEEDS),
            role="Reserved issue24 realizations; never representation training or checkpoint selection",
            novelty="New realizations of known synthetic families, plus explicit annotation perturbations; not new STM acquisitions",
            boundary_exclusion_reference_px=3,
            no_centers_policy="Noise and stripes contain no annotation nodes; report empty graph and unavailable node coverage, not proof of a negative image",
            annotation_perturbation_policy="Image and truth fixed; report behavior on retained IDs, changed denominator and duplicate provenance separately"))
        audit = dict(schema="stmdomains-graph24-controls-v1", sample_count=len(samples),
                     case_count=len(CASES), seeds=list(SEEDS), used_for_training=False,
                     predictions_computed=False,
                     analysis_manifest_sha256=file_hash(staging / "analysis/manifest.json"),
                     evaluation_manifest_sha256=file_hash(staging / "evaluation/manifest.json"),
                     source_sha256={str(Path(__file__).resolve()): file_hash(Path(__file__)),
                                    str(Path(previous.__file__).resolve()): file_hash(Path(previous.__file__))})
        write_json(staging / "audit.json", audit)
        staging.rename(output)
    return audit
