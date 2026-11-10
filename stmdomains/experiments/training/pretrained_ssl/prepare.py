"""Pin issue26 inputs, official pretrained weights and immutable issue20 places."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import shutil
import tarfile

import numpy as np

from ...bundle import file_hash, load_sample, write_json
from .. import predict as old
from ..data import SCALES, extract_patch, synthetic_in_normalizer_units
from ..texture import describe_patches, order_mask
from .common import CAPS, PROTOCOL_PATH, reporting_stage

REPOSITORY = Path(__file__).resolve().parents[4]
DINO_PIN = "7764ea0f912e53c92e82eb78a2a1631e92725fc8"
DINO_SHA256 = "b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9"
ARCHIVE_SHA256 = "c27dcdaf50e9fb5bbdf2bb529da357716372e19c6afab17d5350f3f0094aed4b"
SEEDS = (20261101, 20261102, 20261103)


def frozen_file(root, relative, freeze=None):
    root, relative = Path(root).resolve(), Path(relative)
    path = (root / relative).resolve()
    if relative.is_absolute() or not path.is_relative_to(root):
        raise ValueError("Baseline artifact escapes its root")
    frozen = old.read_json(root / "frozen-predictions.json") if freeze is None else freeze
    if frozen["files"].get(str(relative)) != file_hash(path):
        raise ValueError("Frozen baseline artifact changed: " + str(path))
    return path


def verify_plan(root, budget=None):
    root = Path(root).resolve()
    plan = old.read_json(root / "plan.json")
    if plan["schema"] != "pretrained-ssl26-plan-v1" or plan["training_caps"] != CAPS:
        raise ValueError("Unexpected issue26 plan or budget")
    protocol = Path(plan["protocol_file"])
    protocol = protocol if protocol.is_absolute() else REPOSITORY / protocol
    if file_hash(protocol) != plan["protocol_sha256"] or file_hash(PROTOCOL_PATH) != plan["protocol_sha256"]:
        raise ValueError("Frozen protocol changed")
    for field in ("code_sha256", "source_files"):
        for name, expected in plan[field].items():
            if budget is not None:
                budget.check()
            path = Path(name)
            if field == "source_files" and not path.is_absolute():
                raise ValueError("Source artifact pins must be absolute")
            path = path if path.is_absolute() else REPOSITORY / path
            if file_hash(path) != expected:
                raise ValueError("Pinned issue26 source changed: " + name)
    return plan


def create_plan(prepared, baseline, assets, output, budget):
    prepared, baseline, assets, output = [Path(path).resolve() for path in (prepared, baseline, assets, output)]
    if (output / "plan.json").exists() or (output / "training").exists():
        raise FileExistsError("Plan must precede every adaptation fit")
    own = Path(__file__).resolve().parent
    required = ("models.py", "fit.py", "audit_training.py", "controls.py", "prepare.py", "predict.py",
                "audit_predictions.py", "evaluate.py", "summarize.py", "diagnostics.py", "common.py", "gallery.py",
                "process.py", "run_fits.py", "check_browser.py")
    missing = [name for name in required if not (own / name).is_file()]
    if missing:
        raise ValueError("All numerical/rendering sources must exist before plan: " + ", ".join(missing))
    source_files = {}

    def pin(path):
        budget.check()
        path = Path(path).resolve()
        source_files[str(path)] = file_hash(path)
        return path

    data = prepared / "data"
    protocol_document = pin(REPOSITORY / "docs/stmdomains/pretrained-self-supervised-protocol.md")
    historical = old.read_json(pin(REPOSITORY / "docs/stmdomains/local-self-supervised-manifest.json"))
    measurement_evaluation_sha256 = historical["evaluation"]["measurement_manifest_sha256"]
    manifest = old.read_json(pin(data / "manifest.json"))
    for name in ("windows", "split", "normalization"):
        path = pin(data / manifest[name + "_file"])
        if source_files[str(path)] != manifest[name + "_sha256"]:
            raise ValueError("Original preparation changed: " + name)
    analysis = old.read_json(pin(data / "analysis/manifest.json"))
    if file_hash(data / "analysis/manifest.json") != manifest["analysis_manifest_sha256"] or len(analysis["samples"]) != 24:
        raise ValueError("Original measurement inventory changed")
    for row in analysis["samples"]:
        if file_hash(pin(data / "analysis" / row["file"])) != row["sha256"]:
            raise ValueError("Original measured input changed")
    control_audit = old.read_json(pin(output / "controls/audit.json"))
    controls = old.read_json(pin(output / "controls/analysis/manifest.json"))
    if len(controls["samples"]) != 93 or control_audit["seeds"] != [930031, 930032, 930033]:
        raise ValueError("Unexpected reserved control matrix")
    if file_hash(output / "controls/analysis/manifest.json") != control_audit["analysis_manifest_sha256"]:
        raise ValueError("Control manifest changed after preparation")
    for row in controls["samples"]:
        if file_hash(pin(output / "controls/analysis" / row["file"])) != row["sha256"]:
            raise ValueError("Reserved control input changed")

    provenance = old.read_json(pin(assets / "sources.json"))
    weights, archive = pin(assets / "dinov2_vits14_pretrain.pth"), pin(assets / "dinov2-source.tar.gz")
    if file_hash(weights) != DINO_SHA256 or file_hash(archive) != ARCHIVE_SHA256 or provenance["dinov2_commit"] != DINO_PIN:
        raise ValueError("Official pretrained assets differ from issue18 pins")
    official_root = assets / ("dinov2-" + DINO_PIN)
    official_files = sorted((official_root / "dinov2").rglob("*.py"))
    if not official_files:
        raise ValueError("Missing local official DINOv2 implementation")
    with tarfile.open(archive, "r:gz") as saved:
        for path in official_files:
            path = pin(path)
            member = saved.extractfile(str(path.relative_to(assets)))
            if member is None or hashlib.sha256(member.read()).hexdigest() != source_files[str(path)]:
                raise ValueError("Local DINOv2 code differs from the pinned source archive")

    frozen = old.read_json(pin(baseline / "frozen-predictions.json"))

    def authenticated(relative):
        return pin(frozen_file(baseline, relative, frozen))

    for name in ("predictions/index.json", "cache/index.json", "inference-configuration.json", "cache/order-thresholds.json"):
        authenticated(name)
    measured_groups = [group for group in old.read_json(baseline / "cache/index.json") if group["record"]["kind"] == "measurement"]
    if len(measured_groups) != 144:
        raise ValueError("Expected all24 measurements×3 scales×2 samplers")
    for group in measured_groups:
        for name in ("rows.json.gz", "transfer.npz", "transductive.npz"):
            authenticated(Path("cache") / group["group_id"] / name)
    baselines = []
    for regime in ("transfer", "transductive"):
        baselines.append(dict(run_id=regime + "/fft", regime=regime, family="fft", seed=None, latent=None,
                              source_root=str(baseline), baseline=True))
        baselines.append(dict(run_id=regime + "/dino_frozen", regime=regime, family="dino_frozen", seed=None,
                              latent=384, baseline=False, weights_sha256=DINO_SHA256, selected_role="official_frozen"))
        for scale in SCALES:
            for sampler in ("grid", "centers"):
                authenticated(Path("predictions") / regime / "fft" / sampler / f"s{scale}" / "adapter.json")
    prediction_count, heldout_count = 0, 0
    for entry in old.read_json(baseline / "predictions/index.json"):
        if entry["family"] != "fft" or entry["kind"] != "measurement":
            continue
        prediction_count += 1
        for prefix in ("", "heldout-") if entry["regime"] == "transfer" else ("",):
            heldout_count += int(bool(prefix))
            for name in ("result.json.gz", "relations.json.gz", "metrics-input.npz"):
                authenticated(Path(entry["directory"]) / (prefix + name))
    if (prediction_count, heldout_count) != (576, 288):
        raise ValueError("Incomplete historical FFT measurement baseline")

    specs = [dict(run_id=f"{regime}/dino_adapted/seed-{seed}", regime=regime, family="dino_adapted",
                  latent=384, latent_dim=384, seed=seed, steps=1000, selected_role="teacher")
             for regime in ("transfer", "transductive") for seed in SEEDS]
    code_paths = set(own.glob("*.py"))
    code_paths.update(own.parent / name for name in (
        "data.py", "fit.py", "models.py", "predict.py", "partition.py", "texture.py", "checkpoint.py",
        "export_contract.py", "evaluate.py", "diagnostics.py", "controls.py", "gallery.py", "experiment-plan.json"))
    code_paths.update(own.parent / "local_ssl" / name for name in ("fit.py", "models.py", "diagnostics.py"))
    code_paths.add(own.parent / "masked_ae/evaluate.py")
    code_paths.add(own.parent / "masked_ae/common.py")
    code_paths.add(own.parent / "graph_ssl/controls.py")
    code_paths.update(own.parent.parent / name for name in ("bundle.py", "results.py", "controls.py"))
    code_paths.add(own.parent.parent / "frozen/models.py")
    code = {str(path.relative_to(REPOSITORY)): file_hash(path) for path in sorted(code_paths)}
    plan = dict(schema="pretrained-ssl26-plan-v1", frozen_at_utc=datetime.now(timezone.utc).isoformat(),
        data_root=str(data), prepared_root=str(prepared), assets_root=str(assets), baseline_fft_root=str(baseline),
        controls_root=str(output / "controls"), protocol_file=str(PROTOCOL_PATH.relative_to(REPOSITORY)),
        protocol_sha256=file_hash(PROTOCOL_PATH), protocol_document=str(protocol_document),
        protocol_document_sha256=file_hash(protocol_document), data_manifest_sha256=file_hash(data / "manifest.json"),
        code_sha256=code, source_files=source_files, training_caps=CAPS, run_specs=specs, baseline_runs=baselines,
        baseline_freezes={str(baseline): file_hash(baseline / "frozen-predictions.json")},
        pretrained=dict(model="dinov2_vits14", official_commit=DINO_PIN, official_python_files=len(official_files),
                        weights_file=str(weights), weights_sha256=DINO_SHA256, archive_sha256=ARCHIVE_SHA256),
        controls_evaluation_manifest_sha256=control_audit["evaluation_manifest_sha256"],
        measurement_evaluation_manifest_sha256=measurement_evaluation_sha256,
        expected=dict(maximum_models=10, maximum_full_predictions=14040, maximum_heldout_archives=1440,
                      maximum_test_frame_heldout_archives=1140, maximum_empty_non_test_heldout_archives=300,
                      cache_groups=702, measurement_frames=24, controls=93,
                      per_run_full_predictions=1404, per_transfer_run_heldout_archives=288),
        missing_fit_policy="Keep failed/omitted outcomes; infer only completed teacher runs, no replacement seeds; qualification requires all3 seeds",
        input_transform="Frozen64gray crop → bilinear112 align_cornersFalse → replicatedRGB → fixedImageNet mean/std; identical before/after adaptation",
        source_labels_used=False,
        baseline_policy="Exact issue21 measurement cache and FFT adapters/predictions; fresh official DINO inference on the same issue26 inputs")
    write_json(output / "plan.json", plan)
    return dict(source_files=len(source_files), code_files=len(code), plan_sha256=file_hash(output / "plan.json"))


def cache_inputs(output, budget):
    output = Path(output).resolve()
    plan = verify_plan(output, budget)
    prepared, baseline = Path(plan["prepared_root"]), Path(plan["baseline_fft_root"])
    destination = output / "cache"
    if destination.exists():
        raise FileExistsError(destination)
    destination.mkdir()
    shutil.copyfile(baseline / "cache/order-thresholds.json", destination / "order-thresholds.json")
    thresholds = old.read_json(destination / "order-thresholds.json")
    normalizers = old.read_json(prepared / "data/normalization.json")
    groups = old.make_groups(prepared, output / "controls")
    if len(groups) != 702:
        raise ValueError("Incomplete issue26 input inventory")
    index, reused = [], 0
    last_sid, raw = None, None
    for group in budget.checked(groups):
        record, rows = group["record"], group["rows"]
        folder = destination / group["group_id"]
        folder.mkdir(parents=True)
        if record["kind"] == "measurement":
            source_folder = baseline / "cache" / group["group_id"]
            if old.read_json(source_folder / "rows.json.gz") != rows:
                raise ValueError("Measurement places differ from issue20/21")
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
    write_json(output / "inference-configuration.json", dict(schema="stmdomains-pretrained-ssl26-inference-v1",
        plan_sha256=file_hash(output / "plan.json"), prepared_manifest_sha256=plan["data_manifest_sha256"],
        scales=list(SCALES), main_scale=48, samplers=["grid", "centers"], reused_measurement_cache_files=reused,
        controls_analysis_sha256=file_hash(output / "controls/analysis/manifest.json"),
        descriptor="Mean finalLayerNorm DINO patch tokens384; noCLS/head; same official layer before/after teacher adaptation",
        model_input_transform=plan["input_transform"], graph_context=dict(full_fields="context and transductive assessment",
            transfer_measurement_metrics="separate test-only graph; explicit empty non-test frames"),
        order_gate="Exact issue21 ACF thresholds; no recalibration", catalogue="type_id null", source_labels_used=False))
    return dict(cache_groups=len(index), reused_measurement_cache_files=reused)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("controls", "plan", "cache"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, default=Path(".scratch/training-20"))
    parser.add_argument("--baseline-fft", type=Path, default=Path(".scratch/autoencoder-21"))
    parser.add_argument("--assets", type=Path, default=Path(".scratch/frozen-feature-assets"))
    args = parser.parse_args()
    if args.stage != "controls":
        old.deny_evaluation_paths()
    with reporting_stage(args.output, args.stage) as budget:
        if args.stage == "controls":
            from .controls import prepare
            result = prepare(args.output / "controls", budget)
        elif args.stage == "plan":
            result = create_plan(args.prepared, args.baseline_fft, args.assets, args.output, budget)
        else:
            result = cache_inputs(args.output, budget)
        print(result, flush=True)


if __name__ == "__main__":
    main()
