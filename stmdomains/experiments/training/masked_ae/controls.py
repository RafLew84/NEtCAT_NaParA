"""Reserve fresh known control families for masked reconstruction trial25."""
from __future__ import annotations

from pathlib import Path
import tempfile

from ...bundle import file_hash, write_arrays, write_json
from ..graph_ssl import controls as generator

SEEDS = (920031, 920032, 920033)
CASES = generator.CASES


def prepare(output, budget):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".masked25-controls-", dir=output.parent) as temporary:
        staging = Path(temporary) / "controls"
        samples, evaluations = [], []
        for index, (seed, case) in enumerate(((seed, case) for seed in SEEDS for case in CASES), 1):
            budget.check()
            raw, truth, metadata = generator.make_control(case, seed)
            sid = f"masked-heldout-{index:04d}"
            input_file, truth_file = f"samples/{sid}.npz", f"controls/{sid}.npz"
            samples.append(dict(sample_id=sid, kind="synthetic", file=input_file,
                                coordinate_system="raw_edge_xy", shape_hw=list(raw["image"].shape),
                                pixel_spacing_xy=metadata["pixel_spacing_xy"], position_unit="reference_px",
                                annotation_count=len(raw["object_ids"]),
                                **write_arrays(staging / "analysis" / input_file, raw)))
            evaluations.append(dict(sample_id=sid, file=truth_file, **metadata,
                                    split="reserved_masked25_evaluation",
                                    **write_arrays(staging / "evaluation" / truth_file, truth)))
        lookup = {(row["seed"], row["case"]): row["sample_id"] for row in evaluations}
        for row in evaluations:
            if row.get("base_pair"):
                row["base_sample_id"] = lookup[row["seed"], row["base_pair"]]
            if row.get("pair_case"):
                row["paired_sample_id"] = lookup[row["seed"], row["pair_case"]]
        write_json(staging / "analysis/manifest.json", dict(schema="stmdomains-input-v1", samples=samples,
                   coordinate_convention="x,y pixel edges; pixel centers x+0.5,y+0.5",
                   input_policy="Images, measured masks and annotation geometry only; no case, seed or truth"))
        write_json(staging / "evaluation/manifest.json", dict(schema="stmdomains-evaluation-v1", controls=evaluations,
                   references=[], seeds=list(SEEDS), role="Reserved issue25 realizations, never training or selection",
                   novelty="Fresh seeds of known families; no new measurement acquisition",
                   boundary_exclusion_reference_px=3,
                   annotation_perturbation_policy="Image and truth unchanged: exact grid invariance; centers are separate diagnostics",
                   no_centers_policy="Grid windows still evaluate noise/stripes; center graph is empty and has unavailable coverage"))
        result = dict(schema="stmdomains-masked25-controls-v1", samples=len(samples), families=len(CASES),
                      seeds=list(SEEDS), used_for_training=False, predictions_computed=False,
                      analysis_manifest_sha256=file_hash(staging / "analysis/manifest.json"),
                      evaluation_manifest_sha256=file_hash(staging / "evaluation/manifest.json"),
                      generator_sha256=file_hash(Path(generator.__file__)))
        write_json(staging / "audit.json", result)
        staging.rename(output)
    return result
