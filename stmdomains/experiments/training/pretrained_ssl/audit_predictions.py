"""Reference-free export audits for the pretrained26 comparison."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import shutil
import tempfile

import numpy as np

from ...bundle import file_hash, load_sample, write_json
from ...results import validate_result
from .. import predict as old
from ..export_contract import normalize_element
from ..partition import neighbor_edges
from ..data import support_available
from .common import reporting_stage
from .predict import export_partition, graph_for, trial_runs
from .prepare import frozen_file, verify_plan


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def check_export(folder, rows, group, run, method, *, heldout, gate, expected_graph=None, hashes=None):
    prefix = "heldout-" if heldout else ""
    path = folder / (prefix + "metrics-input.npz")
    values = load(path)
    n = len(rows)
    expected_fields = {"before", "after", "edges", "acf_score", "available"}
    require(set(values) in (expected_fields, expected_fields | {"states"}), "Unexpected numerical export fields")
    if run["family"] != "fft" or group["record"]["kind"] != "measurement":
        require("states" in values, "New26 archives must store states for direct evaluation")
    available = np.asarray([row["available"] for row in rows], bool)
    scope = np.asarray([row["transfer_split"] == "test" for row in rows], bool) if heldout else np.ones(n, bool)
    ids = [row["element_id"] for row in rows]
    expected_edges = (graph_for(rows, group["sampler"], heldout)[1] if expected_graph is None else expected_graph[1])
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
    if hashes is not None:
        require(all(extension.get(name) == value for name, value in hashes.items()), "Wrong run/plan/adapter provenance")
    if "states" in values:
        require(values["states"].shape == (n,) and values["states"].dtype.kind == "U", "Invalid state archive")
        require(values["states"].tolist() == [row["state"] for row in payload["assignments"]], "JSON/NPZ states differ")
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
    relations = old.read_json(relation)
    require([(row["u"], row["v"]) for row in relations] == [(ids[a], ids[b]) for a, b in values["edges"]], "Relation endpoints differ from graph")
    for row in relations:
        available_relation = row["appearance_distance"] is not None
        require(row["availability"] == ("available" if available_relation else "unavailable"), "Relation availability disagrees")
        if not available_relation:
            require(bool(row["missing_reasons"]), "Unavailable relation lacks a reason")
        if available_relation:
            require(np.isfinite(row["appearance_distance"]) and row["appearance_distance"] >= 0 and row["solver_relation"]["strength"] is not None, "Invalid available relation")
    return dict(rows=n, edges=len(values["edges"]), heldout=heldout, acf_score=values["acf_score"],
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
    with tempfile.TemporaryDirectory(prefix=".technical26-", dir=output) as name:
        root = Path(name)
        for method in ("fh4", "mws"):
            folder = root / method
            for heldout in (False, True):
                export_partition(root, group, rows, run, method, feature, adapter, gate, np.ones(9), .1,
                                 folder, dict(plan_sha256="0" * 64), heldout=heldout)
                checked = check_export(folder, rows, group, run, method, heldout=heldout, gate=gate)
                checked.pop("acf_score")
                checks.append(checked)
                prefix = "heldout-" if heldout else ""
                numerical = load(folder / (prefix + "metrics-input.npz"))
                relations = old.read_json(folder / (prefix + "relations.json.gz"))
                require([(row["u"], row["v"]) for row in relations] ==
                        [(rows[a]["element_id"], rows[b]["element_id"]) for a, b in numerical["edges"]],
                        "Technical relation endpoint IDs differ")
        # Noise/stripe controls still have a scored grid, but no center rows.
        # Exercise that empty-center export without generating/scoring controls.
        empty_group = dict(group_id="toy-empty/centers/s48", sampler="centers", scale_px=48,
                           record=dict(sample_id="toy-empty", kind="synthetic", content_sha256="0" * 64))
        non_test_rows = [dict(row, transfer_split=None) for row in rows]
        for method in ("fh4", "mws"):
            folder = root / "empty-centers" / method
            export_partition(root, empty_group, [], run, method, np.empty((0, 2)), adapter,
                             np.empty(0, bool), np.empty(0), .1, folder, dict(plan_sha256="0" * 64))
            checked = check_export(folder, [], empty_group, run, method, heldout=False, gate=np.empty(0, bool))
            checked.pop("acf_score")
            checks.append(dict(checked, case="empty_center_inventory_including_noise_and_stripes"))
            folder = root / "outside-test" / method
            export_partition(root, group, non_test_rows, run, method, feature, adapter, gate, np.ones(9), .1,
                             folder, dict(plan_sha256="0" * 64), heldout=True)
            checked = check_export(folder, non_test_rows, group, run, method, heldout=True, gate=gate)
            checked.pop("acf_score")
            require(checked["empty_non_test"], "Expected explicit empty non-test graph")
            checks.append(dict(checked, case="complete_non_test_frame"))
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
    result = dict(schema="stmdomains-pretrained26-technical-audit-v1", passed=True, export_cases=checks,
                  baseline_bitwise_copies=copies, fitted_models=0, optimizer_steps=0,
                  opened_reference_or_control_truth=False, scope="Small artificial export fixture and one authenticated existing FFT measurement group")
    write_json(report, result)
    return result


def exports(output, budget):
    """One JSON parse per saved result/relation; evaluation uses states in NPZ."""
    output = Path(output).resolve()
    plan = verify_plan(output, budget)
    runs, matrix = trial_runs(output)
    run_map = {run["run_id"]: run for run in runs}
    require(old.read_json(output / "features/actual-matrix.json") == matrix ==
            old.read_json(output / "predictions/actual-matrix.json"), "Actual run matrices differ")
    index = old.read_json(output / "predictions/index.json")
    groups = {row["group_id"]: row for row in old.read_json(output / "cache/index.json")}
    require(len(groups) == 702, "Incomplete sampling inventory")
    expected_keys = {(run["run_id"], gid, method) for run in runs for gid in groups for method in ("fh4", "mws")}
    actual_keys = {(row["run_id"], row["cache_group"], row["partition"]) for row in index}
    require(len(index) == matrix["full_predictions"] == len(actual_keys) and actual_keys == expected_keys,
            "Incomplete/duplicate actual prediction matrix")
    rows_cache, graphs, gates, train_ids, adapter_hashes = {}, {}, {}, {}, {}
    counts = Counter()
    last_sid, raw = None, None
    for group in budget.checked(groups.values()):
        gid, sid = group["group_id"], group["record"]["sample_id"]
        rows = old.read_json(output / "cache" / gid / "rows.json.gz")
        rows_cache[gid] = rows
        require(len({row["element_id"] for row in rows}) == len(rows), "Duplicate sampling IDs")
        if last_sid != sid:
            record, raw = load_sample(Path(group["analysis"]), sid)
            require(record == group["record"], "Input record differs from source manifest")
            last_sid = sid
        for row in rows:
            require(row["available"] == support_available(np.asarray(row["support_xyxy"]), raw["measured"]),
                    "Availability does not match complete measured support")
            require(row["window_id"] == f'{sid}/{group["sampler"]}/{row["element_id"]}/s{group["scale_px"]}',
                    "Window identity disagrees with its group")
        for heldout in (False, True) if group["record"]["kind"] == "measurement" else (False,):
            graphs[gid, heldout] = graph_for(rows, group["sampler"], heldout)
        for regime in ("transfer", "transductive"):
            cache = load(output / "cache" / gid / (regime + ".npz"))
            eligible = np.asarray([row["available"] for row in rows], bool)
            require(np.array_equal(cache["available_indices"], np.flatnonzero(eligible)), "Patch indices differ from support")
            require(cache["patches"].shape == (int(eligible.sum()), 64, 64) and
                    cache["patches"].dtype == np.float32 and np.isfinite(cache["patches"]).all(), "Invalid measured input tensor")
            require(not cache["order_pass"][~eligible].any(), "Order evidence outside complete support")
            gates[gid, regime] = (cache["order_pass"], cache["acf_score"])
            if group["record"]["kind"] == "measurement":
                key = (regime, group["scale_px"], group["sampler"])
                train_ids.setdefault(key, []).extend(row["window_id"] for row in rows if row["available"] and
                    (regime == "transductive" or row["transfer_split"] == "train"))
        if group["record"]["kind"] == "measurement":
            for name in ("rows.json.gz", "transfer.npz", "transductive.npz"):
                relative = Path("cache") / gid / name
                require(file_hash(output / relative) == file_hash(Path(plan["baseline_fft_root"]) / relative),
                        "Original measurement cache bytes changed")
                counts["baseline_cache_files_bitwise"] += 1
    features_index = old.read_json(output / "features/index.json")
    require({row["run_id"] for row in features_index} == {r["run_id"] for r in runs if r["family"] != "fft"}
            and len(features_index) == len(runs) - 2, "Incomplete DINO feature index")
    for run in budget.checked(runs):
        for group in budget.checked(groups.values()):
            rows = rows_cache[group["group_id"]]
            feature = old.load_features(output, run, group)
            dimension = 216 if run["family"] == "fft" else 384
            eligible = np.asarray([row["available"] for row in rows], bool)
            require(feature.shape == (len(rows), dimension) and np.isfinite(feature[eligible]).all() and
                    np.isnan(feature[~eligible]).all(), "Descriptor dimension or availability differs")
            counts["feature_groups_checked"] += 1
        for scale in (32, 48, 64):
            for sampler in ("grid", "centers"):
                relative = Path("predictions") / run["run_id"] / sampler / f"s{scale}" / "adapter.json"
                adapter = old.read_json(output / relative)
                require(adapter["fit_window_ids"] == train_ids[run["regime"], scale, sampler],
                        "Adapter used different or forbidden training positions")
                require(adapter["scope"] == dict(regime=run["regime"], scale_px=scale, sampler=sampler, feature_id=run["run_id"]),
                        "Adapter scope differs")
                adapter_hashes[run["run_id"], scale, sampler] = file_hash(output / relative)
                if run["family"] == "fft":
                    require(file_hash(output / relative) == file_hash(Path(plan["baseline_fft_root"]) / relative),
                            "Frozen FFT adapter bytes changed")
                    counts["baseline_adapters_bitwise"] += 1
                counts["adapters_checked"] += 1
    plan_sha = file_hash(output / "plan.json")
    split_sha = file_hash(Path(plan["data_root"]) / "split.json")
    from .prepare import DINO_SHA256
    for number, entry in enumerate(budget.checked(index), 1):
        group, run = groups[entry["cache_group"]], run_map[entry["run_id"]]
        gid = group["group_id"]
        rows = rows_cache[gid]
        for name in ("kind", "sample_id"):
            require(entry[name] == group["record"][name], "Prediction input identity differs")
        for name in ("scale_px", "sampler"):
            require(entry[name] == group[name], "Prediction place grouping differs")
        for name in ("regime", "family", "seed", "latent"):
            require(entry[name] == run[name], "Prediction model identity differs")
        expected_folder = Path("predictions") / run["run_id"] / group["sampler"] / f's{group["scale_px"]}' / group["record"]["sample_id"] / entry["partition"]
        require(entry["directory"] == str(expected_folder), "Prediction path escapes declared identity")
        heldout = entry["regime"] == "transfer" and entry["kind"] == "measurement"
        copied = run["family"] == "fft" and entry["kind"] == "measurement"
        require(entry["baseline_reused_measurement"] == copied, "Historical-copy declaration differs")
        require(entry["evaluation_input"] == ("heldout-metrics-input.npz" if heldout else "metrics-input.npz"),
                "Evaluation points at the wrong graph scope")
        gate, acf = gates[gid, run["regime"]]
        expected_hashes = None if copied else dict(plan_sha256=plan_sha, split_sha256=split_sha,
            adapter_sha256=adapter_hashes[run["run_id"], group["scale_px"], group["sampler"]],
            checkpoint_sha256=DINO_SHA256 if run["family"] == "dino_frozen" else run.get("run_metadata", {}).get("selected_checkpoint_sha256"),
            protocol_id="stmdomains-pretrained-ssl26-plan-v1", selected_model_role=run.get("selected_role"))
        for is_heldout in (False, True) if heldout else (False,):
            checked = check_export(output / expected_folder, rows, group, run, entry["partition"],
                heldout=is_heldout, gate=gate, expected_graph=graphs[gid, is_heldout], hashes=expected_hashes)
            require(np.array_equal(checked["acf_score"], acf, equal_nan=True), "Order score differs from fixed input cache")
            counts["heldout_archives" if is_heldout else "full_archives"] += 1
            counts["assignment_rows_checked"] += checked["rows"]
            counts["relation_edges_checked"] += checked["edges"]
            counts["empty_non_test_heldout_archives"] += int(checked["empty_non_test"])
        if number % 1500 == 0:
            print("audited", number, "full predictions", flush=True)
    copies = old.read_json(output / "baseline-prediction-copies.json")["files"]
    require(len(copies) == 2592 and len({row["target"] for row in copies}) == 2592, "Incomplete FFT measurement copies")
    for row in budget.checked(copies):
        target, source = (output / row["target"]).resolve(), Path(row["source"]).resolve()
        require(target.is_relative_to(output) and source.is_relative_to(Path(plan["baseline_fft_root"])), "FFT copy path escaped")
        require(file_hash(source) == row["sha256"] == file_hash(target), "FFT prediction bytes changed")
    require(counts["full_archives"] == matrix["full_predictions"] and counts["heldout_archives"] == matrix["heldout_archives"] and
            counts["empty_non_test_heldout_archives"] == matrix["empty_non_test_heldout_archives"] and
            counts["adapters_checked"] == matrix["adapter_count"] and counts["baseline_adapters_bitwise"] == 12 and
            counts["baseline_cache_files_bitwise"] == 432, "Completed export inventory disagrees")
    result = dict(schema="stmdomains-pretrained26-prediction-audit-v1", passed=True, counts=dict(counts),
        omitted_adaptations=matrix["omitted_adaptations"], all_planned_adaptations_completed=matrix["all_planned_adaptations_completed"],
        baseline_prediction_files_bitwise=len(copies), plan_sha256=plan_sha, index_sha256=file_hash(output / "predictions/index.json"),
        auditor_sha256=file_hash(Path(__file__)), opened_reference_or_control_truth=False, source_artifacts_modified=False,
        parsing_policy="Each result/relation JSON read once in independent full audit; evaluation consumes statesNPZ for every new export")
    write_json(output / "prediction-audit.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("technical", "exports"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-fft", type=Path, default=Path(".scratch/autoencoder-21"))
    args = parser.parse_args()
    old.deny_evaluation_paths()
    with reporting_stage(args.output, "audit-" + args.stage) as budget:
        result = technical(args.output, args.baseline_fft, budget) if args.stage == "technical" else exports(args.output, budget)
        print({name: value for name, value in result.items() if name != "baseline_bitwise_copies"}, flush=True)


if __name__ == "__main__":
    main()

