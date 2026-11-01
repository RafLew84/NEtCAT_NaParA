"""Reference-free export audits for the masked-AE25 comparison."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import shutil
import tempfile

import numpy as np

from ...bundle import file_hash, write_json
from ...results import validate_result
from .. import predict as old
from ..export_contract import normalize_element
from ..partition import neighbor_edges
from .common import reporting_stage
from .predict import export_partition, trial_runs
from .prepare import frozen_file, verify_plan


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def check_export(folder, rows, group, run, method, *, heldout, gate):
    prefix = "heldout-" if heldout else ""
    path = folder / (prefix + "metrics-input.npz")
    values = load(path)
    n = len(rows)
    require(set(values) == {"before", "after", "edges", "acf_score", "available"}, "Unexpected numerical export fields")
    available = np.asarray([row["available"] for row in rows], bool)
    scope = np.asarray([row["transfer_split"] == "test" for row in rows], bool) if heldout else np.ones(n, bool)
    ids = [row["element_id"] for row in rows]
    xy = np.asarray([np.asarray(row["raw_edge_xy"]) * row["pixel_spacing_xy"] for row in rows]).reshape(-1, 2)
    indices = np.flatnonzero(scope)
    expected_edges = indices[neighbor_edges(xy[scope], [ids[i] for i in indices], mode=group["sampler"], stride=16)]
    require(np.array_equal(values["edges"], expected_edges), "Graph differs from fixed place/test-only scope")
    require(np.array_equal(values["available"], available), "Availability changed")
    require(values["acf_score"].shape == (n,), "ACF score has wrong shape")
    for key in ("before", "after"):
        labels = values[key]
        require(labels.shape == (n,) and labels.dtype.kind in "iu" and np.all(labels >= 0), "Invalid labels")
        require(np.all(labels[~(available & scope)] == 0), "Assignment escapes measured/test support")
    assigned = values["after"] > 0
    require(np.all(gate[assigned]), "Assignment bypassed frozen order evidence")
    payload = old.read_json(folder / (prefix + "result.json.gz"))
    validate_result(payload)
    require(payload["sample_id"] == group["record"]["sample_id"] and
            payload["input_content_sha256"] == group["record"]["content_sha256"] and
            payload["run_id"] == run["run_id"] + "/" + method, "Result identity differs")
    extension = payload["extensions"]["training_v1"]
    require(extension["elements"] == [normalize_element(row, kind=group["record"]["kind"]) for row in rows],
            "Result ID/support rows differ")
    require(len(payload["assignments"]) == n and len(extension["proposals"]) == n and len(extension["evidence"]) == n,
            "Incomplete result rows")
    for i, (row, assignment, proposal) in enumerate(zip(rows, payload["assignments"], extension["proposals"])):
        require(assignment["element_id"] == row["element_id"] == proposal["element_id"], "Element IDs differ")
        require(assignment["xy"] == row["raw_edge_xy"] and assignment["support_xyxy"] == row["feature_support_xyxy"],
                "Assignment geometry differs")
        require((assignment["domain_id"] is not None) == bool(assigned[i]) and
                (proposal["component_id"] is not None) == bool(values["before"][i] > 0), "JSON/NPZ assignment mask differs")
        require(assignment["type_id"] is None and assignment["orientation_deg"] is None, "Unvalidated physical type/angle assigned")
        state = "insufficient_data" if not available[i] else "not_evaluated" if not scope[i] else "ordered_untyped" if assigned[i] else "ambiguous"
        require(assignment["state"] == state, "Scope/availability state differs")
        if not assigned[i]:
            require(bool(assignment["reason"]), "Refusal without reason")
        if available[i] and not scope[i]:
            require(assignment["reason"] == "outside_transfer_test", "Lost explicit out-of-test refusal")
    require(np.array_equal(old.label_numbers([row["domain_id"] for row in payload["assignments"]]), values["after"]),
            "JSON/NPZ domain partition differs")
    require(np.array_equal(old.label_numbers([row["component_id"] for row in extension["proposals"]]), values["before"]),
            "JSON/NPZ proposal partition differs")
    relation = folder / extension["relations_artifact"]["path"]
    require(relation.name == prefix + "relations.json.gz" and file_hash(relation) == extension["relations_artifact"]["sha256"],
            "Missing or changed relation artifact")
    return dict(rows=n, edges=len(values["edges"]), heldout=heldout,
                empty_non_test=bool(heldout and not scope.any()))


def technical(output, baseline, budget):
    output, baseline = Path(output).resolve(), Path(baseline).resolve()
    report = output / "technical-audit.json"
    require(not report.exists(), "Technical audit evidence already exists")
    rows = []
    for index in range(9):
        xy = np.array([40. + 16 * (index % 3), 40. + 16 * (index // 3)])
        rows.append(dict(window_id=f"toy/grid/g-{index}/s48", sample_id="toy", element_id=f"g-{index}",
                         sampler="grid", frame_number=250, raw_edge_xy=xy.tolist(), position_unit="px", pixel_spacing_xy=[1., 1.],
                         scale_px=48, scale_raw_px=48, feature_support_xyxy=np.r_[xy - 24, xy + 24].tolist(),
                         support_xyxy=np.r_[xy - 27, xy + 27].tolist(), available=index != 0,
                         unavailable_reason="incomplete_measured_support" if index == 0 else None,
                         transfer_split="test" if index >= 3 else None))
    group = dict(group_id="toy/grid/s48", sampler="grid", scale_px=48,
                 record=dict(sample_id="toy", kind="measurement", content_sha256="0" * 64))
    run = dict(run_id="transfer/technical", regime="transfer", family="technical", latent=2, seed=None)
    feature = np.ones((9, 2)); feature[0] = np.nan
    gate = np.array([False] + [True] * 8)
    adapter = dict(available=True, input_dimension=2, mean=[0., 0.], components=[[1., 0.], [0., 1.]],
                   edge_median=1., q25=.5, q75=1.5)
    checks = []
    with tempfile.TemporaryDirectory(prefix=".technical25-", dir=output) as name:
        root = Path(name)
        for method in ("fh4", "mws"):
            folder = root / method
            for heldout in (False, True):
                export_partition(root, group, rows, run, method, feature, adapter, gate, np.ones(9), .1,
                                 folder, dict(plan_sha256="0" * 64), heldout=heldout)
                checks.append(check_export(folder, rows, group, run, method, heldout=heldout, gate=gate))
                prefix = "heldout-" if heldout else ""
                numerical = load(folder / (prefix + "metrics-input.npz"))
                relations = old.read_json(folder / (prefix + "relations.json.gz"))
                require([(row["u"], row["v"]) for row in relations] ==
                        [(rows[a]["element_id"], rows[b]["element_id"]) for a, b in numerical["edges"]],
                        "Technical relation endpoint IDs differ")
        freeze = old.read_json(baseline / "frozen-predictions.json")
        relatives = ["cache/ttmapp-250/grid/s48/" + file for file in ("rows.json.gz", "transfer.npz", "transductive.npz")]
        relatives += ["predictions/transfer/fft/grid/s48/adapter.json"]
        relatives += ["predictions/transfer/fft/grid/s48/ttmapp-250/fh4/" + prefix + file
                      for prefix in ("", "heldout-") for file in ("result.json.gz", "relations.json.gz", "metrics-input.npz")]
        copies = []
        for relative in budget.checked(relatives):
            source = frozen_file(baseline, relative, freeze)
            target = root / "baseline" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            require(file_hash(source) == file_hash(target), "Technical baseline copy differs")
            copies.append(dict(file=relative, sha256=file_hash(source)))
    result = dict(schema="stmdomains-masked25-technical-audit-v1", passed=True, export_cases=checks,
                  baseline_bitwise_copies=copies, fitted_models=0, optimizer_steps=0,
                  opened_reference_or_control_truth=False, scope="Small artificial export fixture and one authenticated existing FFT measurement group")
    write_json(report, result)
    return result


def exports(output, budget):
    output = Path(output).resolve()
    plan = verify_plan(output, budget)
    index = old.read_json(output / "predictions/index.json")
    require(len(index) == 44928 and len({row["directory"] for row in index}) == 44928, "Incomplete/duplicate full prediction matrix")
    require(sum(row["evaluation_input"] == "heldout-metrics-input.npz" for row in index) == 4608, "Incorrect heldout matrix")
    groups = {row["group_id"]: row for row in old.read_json(output / "cache/index.json")}
    require(len(groups) == 702, "Incomplete place cache")
    runs = {row["run_id"]: row for row in trial_runs(output)}
    rows_cache = {}
    train_ids = {}
    counts = Counter()
    for group in budget.checked(groups.values()):
        rows = old.read_json(output / "cache" / group["group_id"] / "rows.json.gz")
        rows_cache[group["group_id"]] = rows
        require(len({row["element_id"] for row in rows}) == len(rows), "Duplicate cached element IDs")
        for regime in ("transfer", "transductive"):
            cache = load(output / "cache" / group["group_id"] / (regime + ".npz"))
            eligible = np.asarray([row["available"] for row in rows], bool)
            require(np.array_equal(cache["available_indices"], np.flatnonzero(eligible)), "Patch availability differs")
            require(cache["patches"].shape == (int(eligible.sum()), 64, 64) and np.isfinite(cache["patches"]).all(), "Invalid measured patches")
            if group["record"]["kind"] == "measurement":
                key = (regime, group["scale_px"], group["sampler"])
                train_ids.setdefault(key, []).extend(row["window_id"] for row in rows
                    if row["available"] and (regime == "transductive" or row["transfer_split"] == "train"))
        if group["record"]["kind"] == "measurement":
            for name in ("rows.json.gz", "transfer.npz", "transductive.npz"):
                require(file_hash(output / "cache" / group["group_id"] / name) ==
                        file_hash(Path(plan["baseline_ae_root"]) / "cache" / group["group_id"] / name), "Measurement cache changed")
                counts["baseline_cache_files_bitwise"] += 1
    for run in budget.checked(runs.values()):
        for group in groups.values():
            rows = rows_cache[group["group_id"]]
            feature = old.load_features(output, run, group)
            dimension = 216 if run["family"] == "fft" else 1568 if run["family"] == "local_ssl" else 32
            eligible = np.asarray([row["available"] for row in rows], bool)
            require(feature.shape == (len(rows), dimension) and np.isfinite(feature[eligible]).all() and np.isnan(feature[~eligible]).all(),
                    "Feature dimensions or support differ")
            if run["baseline"] and run["family"] != "fft" and group["record"]["kind"] == "measurement":
                rel = (Path("features") / run["run_id"] / group["group_id"]).with_suffix(".npz")
                require(file_hash(output / rel) == file_hash(Path(run["source_root"]) / rel), "Baseline feature bytes changed")
                counts["baseline_feature_archives_bitwise"] += 1
        for scale in (32, 48, 64):
            for sampler in ("grid", "centers"):
                relative = Path("predictions") / run["run_id"] / sampler / f"s{scale}" / "adapter.json"
                adapter = old.read_json(output / relative)
                require(adapter["fit_window_ids"] == train_ids[(run["regime"], scale, sampler)], "Adapter used different/nontrain places")
                if run["baseline"]:
                    require(file_hash(output / relative) == file_hash(Path(run["source_root"]) / relative), "Baseline adapter changed")
                    counts["baseline_adapters_bitwise"] += 1
                counts["adapters_checked"] += 1
    last_group_key, gate_cache = None, None
    for number, entry in enumerate(budget.checked(index), 1):
        group, run = groups[entry["cache_group"]], runs[entry["run_id"]]
        rows = rows_cache[entry["cache_group"]]
        require(entry["kind"] == group["record"]["kind"] and entry["sample_id"] == group["record"]["sample_id"] and
                entry["scale_px"] == group["scale_px"] and entry["sampler"] == group["sampler"], "Indexed place identity differs")
        key = (entry["cache_group"], run["regime"])
        if key != last_group_key:
            gate_cache = load(output / "cache" / group["group_id"] / (run["regime"] + ".npz"))
            last_group_key = key
        heldout = entry["kind"] == "measurement" and entry["regime"] == "transfer"
        require(entry["evaluation_input"] == ("heldout-metrics-input.npz" if heldout else "metrics-input.npz"), "Incorrect evaluation scope")
        for is_heldout in (False, True) if heldout else (False,):
            result = check_export(output / entry["directory"], rows, group, run, entry["partition"],
                                  heldout=is_heldout, gate=gate_cache["order_pass"])
            prefix = "heldout-" if is_heldout else ""
            data = load(output / entry["directory"] / (prefix + "metrics-input.npz"))
            require(np.array_equal(data["acf_score"], gate_cache["acf_score"], equal_nan=True), "Frozen ACF score changed")
            counts["heldout_archives" if is_heldout else "full_archives"] += 1
            counts["assignment_rows_checked"] += result["rows"]
            counts["empty_non_test_heldout_archives"] += int(result["empty_non_test"])
        if number % 3000 == 0:
            print("audited", number, "full predictions", flush=True)
    copies = old.read_json(output / "baseline-prediction-copies.json")["files"]
    for row in budget.checked(copies):
        require(file_hash(Path(row["source"])) == row["sha256"] == file_hash(output / row["target"]), "Baseline prediction bytes changed")
    require(len(copies) == 18144 and counts["baseline_cache_files_bitwise"] == 432 and
            counts["baseline_feature_archives_bitwise"] == 1728 and counts["baseline_adapters_bitwise"] == 84 and
            counts["adapters_checked"] == 192 and counts["empty_non_test_heldout_archives"] == 960,
            "Final reuse/scope totals differ")
    result = dict(schema="stmdomains-masked25-prediction-audit-v1", passed=True, counts=dict(counts),
                  baseline_prediction_files_bitwise=len(copies), plan_sha256=file_hash(output / "plan.json"),
                  index_sha256=file_hash(output / "predictions/index.json"), auditor_sha256=file_hash(Path(__file__)),
                  opened_reference_or_control_truth=False, source_artifacts_modified=False)
    write_json(output / "prediction-audit.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("technical", "exports"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-ae", type=Path, default=Path(".scratch/autoencoder-21"))
    args = parser.parse_args()
    old.deny_evaluation_paths()
    with reporting_stage(args.output, "audit-" + args.stage) as budget:
        result = technical(args.output, args.baseline_ae, budget) if args.stage == "technical" else exports(args.output, budget)
        print({key: value for key, value in result.items() if key not in ("baseline_bitwise_copies",)}, flush=True)


if __name__ == "__main__":
    main()
