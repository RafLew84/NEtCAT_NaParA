"""Pin trial25 inputs and reuse issue20 measurement rows without refitting."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import shutil

import numpy as np

from ...bundle import file_hash, load_sample, write_json
from .. import predict as old
from ..data import SCALES, extract_patch, synthetic_in_normalizer_units
from ..texture import describe_patches, order_mask
from .common import CAPS, PROTOCOL_PATH, reporting_stage


def frozen_file(root, relative, freeze=None):
    root, relative = Path(root).resolve(), Path(relative)
    path = (root / relative).resolve()
    if relative.is_absolute() or not path.is_relative_to(root):
        raise ValueError("Baseline path escapes its root")
    freeze = old.read_json(root / "frozen-predictions.json") if freeze is None else freeze
    if freeze["files"].get(str(relative)) != file_hash(path):
        raise ValueError("Baseline artifact missing or changed: " + str(path))
    return path


def verify_plan(root, budget=None):
    root = Path(root).resolve()
    plan = old.read_json(root / "plan.json")
    if plan["training_caps"] != CAPS or file_hash(Path(plan["protocol_file"])) != plan["protocol_sha256"]:
        raise ValueError("Frozen protocol or caps changed")
    for name, expected in {**plan["code_sha256"], **plan["source_files"]}.items():
        if budget is not None:
            budget.check()
        if file_hash(Path(name)) != expected:
            raise ValueError("Pinned source changed: " + name)
    return plan


def create_plan(prepared, ae_root, ssl_root, output, budget):
    prepared, ae_root, ssl_root, output = [Path(p).resolve() for p in (prepared, ae_root, ssl_root, output)]
    if (output / "plan.json").exists() or (output / "training").exists():
        raise FileExistsError("Plan must precede fits")
    own = Path(__file__).resolve().parent
    required = ("models.py", "fit.py", "audit_training.py", "controls.py", "prepare.py", "predict.py",
                "audit_predictions.py", "evaluate.py", "summarize.py", "diagnostics.py", "common.py")
    if any(not (own / name).is_file() for name in required):
        raise ValueError("All numerical sources must exist before freezing plan")
    source_files = {}

    def pin(path):
        budget.check()
        path = Path(path).resolve()
        source_files[str(path)] = file_hash(path)
        return path

    data = prepared / "data"
    protocol_document = pin(Path("docs/stmdomains/masked-autoencoder-protocol.md"))
    historical_manifest = old.read_json(pin(Path("docs/stmdomains/local-self-supervised-manifest.json")))
    measurement_evaluation_sha256 = historical_manifest["evaluation"]["measurement_manifest_sha256"]
    manifest = old.read_json(pin(data / "manifest.json"))
    for key in ("windows", "split", "normalization"):
        path = pin(data / manifest[key + "_file"])
        if source_files[str(path)] != manifest[key + "_sha256"]:
            raise ValueError("Original preparation changed: " + key)
    analysis = old.read_json(pin(data / "analysis/manifest.json"))
    if file_hash(data / "analysis/manifest.json") != manifest["analysis_manifest_sha256"]:
        raise ValueError("Original analysis manifest changed")
    for row in analysis["samples"]:
        path = pin(data / "analysis" / row["file"])
        if file_hash(path) != row["sha256"]:
            raise ValueError("Original measurement changed")
    control_audit = old.read_json(pin(output / "controls/audit.json"))
    controls = old.read_json(pin(output / "controls/analysis/manifest.json"))
    if len(controls["samples"]) != 93 or control_audit["seeds"] != [920031, 920032, 920033]:
        raise ValueError("Unexpected control matrix")
    for row in controls["samples"]:
        path = pin(output / "controls/analysis" / row["file"])
        if file_hash(path) != row["sha256"]:
            raise ValueError("Control input changed")
    baseline_runs, baseline_freezes = [], {}
    measurement_cache_groups = []
    for source, family in ((ae_root, "ae"), (ssl_root, "local_ssl")):
        freeze = old.read_json(pin(source / "frozen-predictions.json"))
        baseline_freezes[str(source)] = file_hash(source / "frozen-predictions.json")

        def authenticated(relative):
            return pin(frozen_file(source, relative, freeze))

        for name in ("features/index.json", "predictions/index.json", "cache/index.json", "inference-configuration.json"):
            authenticated(name)
        selected = [run for run in old.read_json(source / "features/index.json")
                    if run["family"] == family and run["latent"] == 32]
        if len(selected) != 6:
            raise ValueError("Six completed baseline models required: " + family)
        baseline_runs.extend(dict(run, source_root=str(source), baseline=True) for run in selected)
        run_ids = {run["run_id"] for run in selected}
        if family == "ae":
            run_ids.update(("transfer/fft", "transductive/fft"))
            baseline_runs.extend(dict(run_id=regime + "/fft", regime=regime, family="fft", latent=None,
                                      seed=None, source_root=str(source), baseline=True)
                                 for regime in ("transfer", "transductive"))
            authenticated("cache/order-thresholds.json")
            measurement_cache_groups = [row for row in old.read_json(source / "cache/index.json")
                                        if row["record"]["kind"] == "measurement"]
            for group in measurement_cache_groups:
                for name in ("rows.json.gz", "transfer.npz", "transductive.npz"):
                    authenticated(Path("cache") / group["group_id"] / name)
        for run in selected:
            run_dir = Path(run["directory"])
            for name in ("run.json", "config.json", run["run_metadata"]["selected_checkpoint"]):
                authenticated((run_dir / name).relative_to(source))
            for group in measurement_cache_groups:
                authenticated((Path("features") / run["run_id"] / group["group_id"]).with_suffix(".npz"))
        for run_id in run_ids:
            for scale in SCALES:
                for sampler in ("grid", "centers"):
                    authenticated(Path("predictions") / run_id / sampler / f"s{scale}" / "adapter.json")
        for entry in old.read_json(source / "predictions/index.json"):
            if entry["run_id"] not in run_ids or entry["kind"] != "measurement":
                continue
            folder = Path(entry["directory"])
            for name in ("result.json.gz", "relations.json.gz", "metrics-input.npz"):
                authenticated(folder / name)
            if entry["regime"] == "transfer":
                for name in ("heldout-result.json.gz", "heldout-relations.json.gz", "heldout-metrics-input.npz"):
                    authenticated(folder / name)
    if len(measurement_cache_groups) != 144 or len(baseline_runs) != 14:
        raise ValueError("Unexpected baseline scope")
    specs = [dict(run_id=f"{regime}/{family}/z32/seed-{seed}", regime=regime, family=family,
                  mask_fraction=.25 if family == "mask25" else .5, latent=32, latent_dim=32, seed=seed)
             for regime in ("transfer", "transductive") for family in ("mask25", "mask50")
             for seed in (20261101, 20261102, 20261103)]
    repo = Path.cwd().resolve()
    code_paths = set(own.glob("*.py"))
    code_paths.update(own.parent / name for name in ("data.py", "fit.py", "models.py", "predict.py", "partition.py",
                      "texture.py", "checkpoint.py", "export_contract.py", "evaluate.py", "diagnostics.py", "controls.py", "experiment-plan.json"))
    code_paths.update(own.parent / "local_ssl" / name for name in ("models.py", "predict.py", "diagnostics.py"))
    code_paths.add(own.parent / "graph_ssl/controls.py")
    code_paths.update(own.parent.parent / name for name in ("bundle.py", "results.py", "controls.py"))
    code = {str(path.relative_to(repo)): file_hash(path) for path in sorted(code_paths)}
    plan = dict(schema="masked-ae25-plan-v1", frozen_at_utc=datetime.now(timezone.utc).isoformat(),
                data_root=str(data), prepared_root=str(prepared), baseline_ae_root=str(ae_root), baseline_ssl_root=str(ssl_root),
                controls_root=str(output / "controls"), protocol_file=str(PROTOCOL_PATH.relative_to(repo)),
                protocol_sha256=file_hash(PROTOCOL_PATH), data_manifest_sha256=file_hash(data / "manifest.json"),
                protocol_document=str(protocol_document), protocol_document_sha256=file_hash(protocol_document),
                code_sha256=code, source_files=source_files, baseline_freezes=baseline_freezes,
                training_caps=CAPS, run_specs=specs, baseline_runs=baseline_runs,
                controls_evaluation_manifest_sha256=control_audit["evaluation_manifest_sha256"],
                measurement_evaluation_manifest_sha256=measurement_evaluation_sha256,
                expected=dict(models=32, full_predictions=44928, heldout_archives=4608,
                              test_frame_heldout_archives=3648, empty_non_test_heldout_archives=960,
                              cache_groups=702, measurement_frames=24, controls=93),
                source_labels_used=False, baseline_policy="Exact old measurement cache, adapters, features and predictions; fresh inference on new controls")
    write_json(output / "plan.json", plan)
    return dict(source_files=len(source_files), code_files=len(code), plan_sha256=file_hash(output / "plan.json"))


def cache_inputs(output, budget):
    output = Path(output).resolve()
    plan = verify_plan(output, budget)
    prepared, baseline = Path(plan["prepared_root"]), Path(plan["baseline_ae_root"])
    destination = output / "cache"
    if destination.exists():
        raise FileExistsError(destination)
    destination.mkdir()
    shutil.copyfile(baseline / "cache/order-thresholds.json", destination / "order-thresholds.json")
    thresholds = old.read_json(destination / "order-thresholds.json")
    normalizers = old.read_json(prepared / "data/normalization.json")
    groups = old.make_groups(prepared, output / "controls")
    index, reused = [], 0
    last_sid, raw = None, None
    for group in budget.checked(groups):
        record, rows = group["record"], group["rows"]
        folder = destination / group["group_id"]
        folder.mkdir(parents=True)
        if record["kind"] == "measurement":
            source_folder = baseline / "cache" / group["group_id"]
            if old.read_json(source_folder / "rows.json.gz") != rows:
                raise ValueError("Measurement rows differ from frozen issue21 places")
            for name in ("rows.json.gz", "transfer.npz", "transductive.npz"):
                shutil.copyfile(source_folder / name, folder / name)
                reused += 1
        else:
            if record["sample_id"] != last_sid:
                _, raw = load_sample(Path(group["analysis"]), record["sample_id"])
                last_sid = record["sample_id"]
            old.write_gzip(folder / "rows.json.gz", rows)
            available = np.asarray([i for i, row in enumerate(rows) if row["available"]], np.int64)
            for regime in ("transfer", "transductive"):
                source = synthetic_in_normalizer_units(raw, normalizers[regime])
                native = np.stack([extract_patch(source, rows[i], normalizers[regime], size=group["scale_px"])
                                   for i in available]) if len(available) else np.empty((0, group["scale_px"], group["scale_px"]))
                patches = np.stack([extract_patch(source, rows[i], normalizers[regime]) for i in available]) if len(available) else np.empty((0, 64, 64), np.float32)
                description = describe_patches(native)
                threshold = thresholds["scales"][str(group["scale_px"])]["threshold"]
                cached = dict(available_indices=available, patches=patches, order_pass=np.zeros(len(rows), bool),
                              acf_score=np.full(len(rows), np.nan), fft=np.full((len(rows), 216), np.nan))
                cached["order_pass"][available] = order_mask(description, threshold)
                cached["acf_score"][available] = description["acf_score"]
                cached["fft"][available] = description["features"]
                np.savez_compressed(folder / (regime + ".npz"), **cached)
        index.append({key: value for key, value in group.items() if key != "rows"})
    write_json(destination / "index.json", index)
    write_json(output / "inference-configuration.json", dict(schema="stmdomains-masked-ae25-inference-v1",
               plan_sha256=file_hash(output / "plan.json"), prepared_manifest_sha256=plan["data_manifest_sha256"],
               scales=list(SCALES), main_scale=48, samplers=["grid", "centers"], reused_measurement_cache_files=reused,
               controls_analysis_sha256=file_hash(output / "controls/analysis/manifest.json"),
               descriptor="Unmasked AE content32; SSL22 flattened32x7x7; FFT216; no reconstruction used as measured input",
               graph_context=dict(full_fields="context and transductive assessment", transfer_measurement_metrics="separate test-only graph, including explicit empty non-test frames"),
               order_gate="Exact issue21 thresholds; no recalibration", catalogue="type_id null",
               controls_scope="93 fresh realizations of known families", source_labels_used=False))
    return dict(cache_groups=len(index), reused_measurement_cache_files=reused)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("controls", "plan", "cache"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, default=Path(".scratch/training-20"))
    parser.add_argument("--baseline-ae", type=Path, default=Path(".scratch/autoencoder-21"))
    parser.add_argument("--baseline-ssl", type=Path, default=Path(".scratch/local-ssl-22"))
    args = parser.parse_args()
    if args.stage != "controls":
        old.deny_evaluation_paths()
    with reporting_stage(args.output, args.stage) as budget:
        if args.stage == "controls":
            from .controls import prepare
            result = prepare(args.output / "controls", budget)
        elif args.stage == "plan":
            result = create_plan(args.prepared, args.baseline_ae, args.baseline_ssl, args.output, budget)
        else:
            result = cache_inputs(args.output, budget)
        print(result, flush=True)


if __name__ == "__main__":
    main()
