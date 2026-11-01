"""Frozen issue-24a diagnostics on the already known controls from issue24.

No fitting, checkpoint selection or prediction changes occur here. Every mode
uses the same S24 anchor IDs and available support; refusals remain in that
denominator. Passing these diagnostics is not held-out method validation.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import itertools
import json
from pathlib import Path

import numpy as np

from ...bundle import file_hash, write_json
from .. import evaluate as old
from ..graph_ssl import evaluation as graph24


MODES = ("closed72", "halfopen72", "root_only")
MODEL_SEEDS = graph24.MODEL_SEEDS
CONTROL_SEEDS = graph24.CONTROL_SEEDS
BOUNDARY_CASES = ("two_orientations", "orientation_8deg", "different_spacing", "phase_boundary")
FAMILY_KEYS = ("mode", "family", "partition")
AGGREGATE_KEYS = ("variant_id", "mode", "family", "seed", "partition", "case")
NONREGRESSION_TOLERANCE = .02


def read(path):
    return json.loads(Path(path).read_text())


def key(meta, names):
    return tuple(meta.get(name) for name in names)


class Budget(graph24.Budget):
    def __init__(self, root):
        super().__init__(root)
        self.cpu_limit_seconds = 1800.
        self.rss_limit_bytes = 4 * 1024 ** 3


def artifact_criteria(metrics):
    """A: retain every one of the121 original full-support single-lattice nodes."""
    if metrics["case"] != "single":
        return old._check_result({}, applicable=False)
    checks = dict(original_full_support_121=metrics["full_support_elements"] == 121,
                  original_evaluated_121=metrics["evaluated_elements"] == 121)
    for stage in ("before", "after"):
        value = metrics[stage]
        checks.update({stage + "/one_domain": value["domain_count_in_scope"] == 1,
                       stage + "/all_121_assigned": value["assigned_evaluated_elements"] == 121,
                       stage + "/no_assignment_without_support": value["assigned_without_support"] == 0})
    return old._check_result(checks)


def boundary_criteria(metrics, stage):
    """B: the original absolute boundary gates, also visible before refusals."""
    if metrics["case"] not in BOUNDARY_CASES:
        return old._check_result({}, applicable=False)
    value = metrics[stage]
    regions = [part["coverage"] for part in value["per_region"].values()]
    return old._check_result(dict(
        no_assignment_without_support=value["assigned_without_support"] == 0,
        coverage=old._at_least(value["coverage"], .5),
        both_regions_present=len(regions) == 2,
        each_region_coverage=all(v is not None and v >= .3 for v in regions) if len(regions) == 2 else None,
        merge_rate=old._at_most(value["pairs"]["merge_rate"], .02),
        split_rate=old._at_most(value["pairs"]["split_rate"], .1),
        boundary_f1=old._at_least(value["boundary"]["f1"], .7)))


def cross_boundary_edges(rows, truth, prediction):
    """Keep the fixed local-edge denominator even when an endpoint is refused."""
    xy = old._positions(rows)
    labels = old._sample(truth["domain_labels"], xy, name="domain_labels", fill=0, dtype_kind="iu")
    valid = old._sample(truth.get("evaluation_valid"), xy, name="evaluation_valid", fill=True, dtype_kind="b")
    available = np.asarray([r["available"] for r in rows], bool)
    evaluated = available & valid & (labels > 0)
    edges = old._edges(prediction["edges"], len(rows))
    u, v = edges.T
    cross = evaluated[u] & evaluated[v] & (labels[u] != labels[v])
    u, v = u[cross], v[cross]
    stages = {}
    for stage in ("before", "after"):
        assigned = prediction[stage] > 0
        count = assigned[u].astype(np.int8) + assigned[v].astype(np.int8)
        stages[stage] = dict(reference_cross_boundary_edges=len(u),
                            zero_assigned_endpoints=int((count == 0).sum()),
                            one_assigned_endpoint=int((count == 1).sum()),
                            two_assigned_endpoints=int((count == 2).sum()),
                            both_assigned_fraction=old._ratio((count == 2).sum(), len(u)),
                            merged_with_two_assigned=int(((count == 2) & (prediction[stage][u] == prediction[stage][v])).sum()),
                            separated_with_two_assigned=int(((count == 2) & (prediction[stage][u] != prediction[stage][v])).sum()))
    return stages


def nonregression(baseline, candidate):
    result = {}
    for stage in ("before", "after"):
        a, b = baseline[stage], candidate[stage]
        values = dict(coverage=(a["coverage"], b["coverage"], "higher"),
                      merge_rate=(a["pairs"]["merge_rate"], b["pairs"]["merge_rate"], "lower"),
                      split_rate=(a["pairs"]["split_rate"], b["pairs"]["split_rate"], "lower"),
                      boundary_f1=(a["boundary"]["f1"], b["boundary"]["f1"], "higher"))
        checks, details = {}, {}
        for name, (base, value, direction) in values.items():
            delta = None if base is None or value is None else value - base
            passed = None if delta is None else bool(value >= base - NONREGRESSION_TOLERANCE if direction == "higher" else value <= base + NONREGRESSION_TOLERANCE)
            checks[name] = passed
            details[name] = dict(baseline=base, candidate=value, candidate_minus_baseline=delta,
                                 permitted_change=NONREGRESSION_TOLERANCE, direction=direction,
                                 passed=passed, unavailable_reason="missing_baseline_or_candidate_denominator" if delta is None else None)
        result[stage] = dict(criteria=old._check_result(checks), metrics=details)
    return result


def compare_predictions(data):
    closed, geometry = {}, {}
    for entry in data.values():
        meta = entry["record"]["metadata"]
        if meta["family"] == "geometry":
            geometry[meta["sample_id"], meta["partition"]] = entry
        elif meta["mode"] == "closed72":
            closed[meta["family"], meta["seed"], meta["sample_id"], meta["partition"]] = entry
    comparisons = []
    for entry in data.values():
        meta = entry["record"]["metadata"]
        own = entry if meta["family"] == "geometry" else closed[meta["family"], meta["seed"], meta["sample_id"], meta["partition"]]
        for baseline_name, base in (("own_closed72", own), ("geometry", geometry[meta["sample_id"], meta["partition"]])):
            if entry["rows"] != base["rows"] or not np.array_equal(entry["evaluated"], base["evaluated"]):
                raise ValueError("Modes changed S24 IDs, support or evaluation denominator")
            if not np.array_equal(entry["prediction"]["edges"], base["prediction"]["edges"]):
                raise ValueError("Modes changed the fixed partition graph")
            if not np.array_equal(entry["prediction"]["score"], base["prediction"]["score"], equal_nan=True):
                raise ValueError("Modes changed the fixed order score")
            paired = {}
            for stage in ("before", "after"):
                paired[stage] = old.matched_coverage(entry["reference"], base["prediction"][stage],
                    entry["prediction"][stage], entry["prediction"]["score"],
                    [r["element_id"] for r in entry["rows"]], evaluated_mask=entry["evaluated"])
            comparisons.append(dict(metadata=dict(meta, baseline=baseline_name),
                baseline_variant_id=base["record"]["metadata"]["variant_id"],
                nonregression=nonregression(base["record"]["metrics"], entry["record"]["metrics"]),
                matched_coverage=paired,
                original_denominator_elements=int(entry["evaluated"].sum()),
                interpretation="Same original S24 scope; common-assignment errors do not replace refusal coverage"))
    return comparisons


def group_criteria(records, comparisons):
    groups = defaultdict(list)
    paired = {(r["metadata"]["variant_id"], r["metadata"]["sample_id"], r["metadata"]["partition"]): r
              for r in comparisons if r["metadata"]["baseline"] == "own_closed72"}
    for record in records:
        groups[key(record["metadata"], FAMILY_KEYS)].append(record)
    output = []
    for ident, members in groups.items():
        meta = dict(zip(FAMILY_KEYS, ident))
        model_seeds = (None,) if meta["family"] == "geometry" else MODEL_SEEDS
        lookup = {(r["metadata"]["seed"], r["metadata"]["control_seed"], r["metadata"]["case"]): r for r in members}
        a_checks, b_checks, nr_checks = {}, {}, {}
        for seed, control_seed in itertools.product(model_seeds, CONTROL_SEEDS):
            name = f"model_seed={seed}/control_seed={control_seed}"
            single = lookup.get((seed, control_seed, "single"))
            a_checks[name] = None if single is None else single["diagnostics"]["artifact_A"]["passed"]
            for case in BOUNDARY_CASES:
                entry = lookup.get((seed, control_seed, case))
                comparison = None if entry is None else paired[entry["metadata"]["variant_id"], entry["metadata"]["sample_id"], entry["metadata"]["partition"]]
                for stage in ("before", "after"):
                    field = f"{name}/case={case}/stage={stage}"
                    b_checks[field] = None if entry is None else entry["diagnostics"]["boundary_B"][stage]["passed"]
                    nr_checks[field] = None if comparison is None else comparison["nonregression"][stage]["criteria"]["passed"]
        a, b, nr = (old._check_result(checks) for checks in (a_checks, b_checks, nr_checks))
        joint = old._check_result(dict(artifact_A=a["passed"], boundaries_B=b["passed"], nonregression_vs_own_closed72=nr["passed"]))
        output.append(dict(metadata=meta, artifact_A=a, boundaries_B=b, nonregression=nr,
            joint_conditions_on_known_controls=joint,
            supports_graph_context_repair_on_known_controls=bool(meta["mode"] == "halfopen72" and joint["qualified"]),
            interpretation="node-only aggregation ablation, not a repaired GNN" if meta["mode"] == "root_only" else
                           "historical closed-context baseline" if meta["mode"] == "closed72" else
                           "classical root-descriptor reference" if meta["family"] == "geometry" else
                           "half-open interval diagnostic with frozen weights",
            heldout_validation=False, molecule_detection_claim=False))
    return output


def render_report(criteria, aggregates):
    yn = lambda value: "tak" if value is True else "nie" if value is False else "brak miary"
    lines = ["# Diagnoza kontekstu 24a", "",
             "Wyniki dotyczą 93 znanych kontroli z24. Nie jest to walidacja held-out. "
             "Wagi, adaptery, graf podziału i bramka pozostają zamrożone; mianownik S24 jest stały.", "",
             "| Opis | Tryb | Podział | A: jedna sieć121/121 | B: granice przed/po | Bez regresji wobec closed72 | Wszystkie warunki |",
             "|---|---|---|---|---|---|---|"]
    for r in criteria:
        m = r["metadata"]
        lines.append(f"| {m['family']} | {m['mode']} | {m['partition']} | {yn(r['artifact_A']['passed'])} | "
                     f"{yn(r['boundaries_B']['passed'])} | {yn(r['nonregression']['passed'])} | "
                     f"{yn(r['joint_conditions_on_known_controls']['passed'])} |")
    lines += ["", "A wymaga wszystkich121 dostępnych centrów i dokładnie jednej domeny przed oraz po odmowach. "
              "B zachowuje progi24 dla orientacji, różnicy8°, rozstawu i fazy. Niepogorszenie oznacza najwyżej2pp "
              "utraty coverage/F1 lub wzrostu merge/split względem własnego closed72. Każdy brak mianownika pozostaje null.", "",
              "root_only jest ablacją agregacji. Nawet zaliczenie A+B nie dowodzi naprawy pełnego GNN ani poprawy na nowych danych.", "",
              "## Wszystkie rodziny kontroli i ziarna", "",
              "| Opis | Tryb | Ziarno | Podział | Kontrola | Etap | Przypisania | Coverage | Merge | Split | F1 |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    fmt = lambda v: "—" if v is None else f"{100*v:.2f}%"
    for row in aggregates:
        m, result = row["metadata"], row["metrics"]
        for stage in ("before", "after"):
            r = result[stage]
            lines.append(f"| {m['family']} | {m['mode']} | {m['seed']} | {m['partition']} | {m['case']} | {stage} | "
                         f"{r['assigned_evaluated_elements']}/{result['evaluated_elements']} | {fmt(r['coverage'])} | "
                         f"{fmt(r['pairs']['merge_rate'])} | {fmt(r['pairs']['split_rate'])} | {fmt(r['boundary']['f1'])} |")
    lines += ["", "Pełne liczniki krawędzi przez referencyjną granicę z0/1/2 przypisanymi końcami są w summary.json. "
              "Puste noise/stripes nie potwierdzają rozpoznania negatywnego obrazu. Phase+jitter i braki oznaczeń "
              "pozostają osobnymi kontrolami obciążającymi; nie stroimy na nich wariantów.", ""]
    return "\n".join(lines)


def _evaluate(root, controls_dir, out, budget):
    frozen = graph24.verify_freeze(root, budget)
    plan = read(old._frozen_path(root, "plan.json", frozen))
    controls_dir = Path(controls_dir or Path(plan["source_root"]) / "controls/evaluation").resolve()
    index = read(old._frozen_path(root, "predictions/index.json", frozen))
    prepared = read(old._frozen_path(root, "prepared/manifest.json", frozen))
    if len(index) != 3534 or len(prepared["samples"]) != 93:
        raise ValueError("Expected the frozen19variants x2solvers x93controls matrix")
    samples = {}
    for sample in budget.checked(prepared["samples"]):
        rows_path = old._frozen_path(root, "prepared/" + sample["rows_file"], frozen)
        if file_hash(rows_path) != sample["rows_sha256"]:
            raise ValueError("Copied S24 rows differ from their original source hash")
        rows = read(rows_path)
        samples[sample["sample_id"]] = dict(record=sample["record"], rows=rows)
    if len(samples) != 93:
        raise ValueError("Repeated prepared control identity")
    expected = {(mode, family, seed, partition) for mode, family, seed, partition in
                itertools.product(MODES, ("graph_sce_scale", "graph_untrained"), MODEL_SEEDS, ("fh4", "mws"))}
    expected |= {(None, "geometry", None, partition) for partition in ("fh4", "mws")}
    matrix = defaultdict(set)
    for item in index:
        ident = (None if item["family"] == "geometry" else item["mode"], item["family"], item["seed"], item["partition"])
        if ident in matrix[item["sample_id"]]:
            raise ValueError("Repeated representation/mode/seed/solver slot")
        matrix[item["sample_id"]].add(ident)
    if set(matrix) != set(samples) or any(slots != expected for slots in matrix.values()):
        raise ValueError("Incomplete or extra representation/mode/seed/solver slots")
    # The entire prediction/source freeze above is checked before opening truth.
    truth_manifest, truths = old._truth_bundle(controls_dir, "controls")
    if set(truths) != set(samples):
        raise ValueError("Controls differ from the existing93known controls")
    data, records = {}, []
    for item in budget.checked(index):
        if item["kind"] != "synthetic" or item["regime"] != "transfer":
            raise ValueError("24a evaluates synthetic transfer diagnostics only")
        if item["family"] not in {"geometry", "graph_untrained", "graph_sce_scale"}:
            raise ValueError("Unplanned representation family")
        if item["family"] != "geometry" and (item["mode"] not in MODES or item["seed"] not in MODEL_SEEDS):
            raise ValueError("Unplanned mode or model seed")
        if item["partition"] not in {"fh4", "mws"}:
            raise ValueError("Unplanned solver")
        sample = samples[item["sample_id"]]
        rows = sample["rows"]
        with np.load(old._frozen_path(root, item["file"], frozen), allow_pickle=False) as archive:
            prediction = {k: archive[k] for k in archive.files}
        truth_meta, truth = truths[item["sample_id"]]
        meta = {k: v for k, v in item.items() if k != "file"}
        meta.update(case=truth_meta["case"], control_seed=truth_meta["seed"], assessment="known_control_context_diagnostic")
        metrics = graph24.evaluate_sample(rows, prediction, truth, meta, sample["record"]["pixel_spacing_xy"])
        diagnostic = dict(artifact_A=artifact_criteria(metrics),
                          boundary_B={stage: boundary_criteria(metrics, stage) for stage in ("before", "after")},
                          cross_boundary_endpoints=cross_boundary_edges(rows, truth, prediction))
        record = dict(metadata=meta, metrics=metrics, diagnostics=diagnostic)
        records.append(record)
        ident = (meta["variant_id"], meta["sample_id"], meta["partition"])
        if ident in data:
            raise ValueError("Repeated variant/control/solver")
        data[ident] = dict(record=record, prediction=prediction, rows=rows,
            reference=old._comparison_reference(rows, truth["domain_labels"], truth.get("evaluation_valid"), kind="synthetic", regime="transfer"),
            evaluated=old._evaluated_mask(rows, truth["domain_labels"], truth.get("evaluation_valid"), kind="synthetic", regime="transfer"))
    grouped = defaultdict(list)
    for record in records:
        grouped[key(record["metadata"], AGGREGATE_KEYS)].append(record["metrics"])
    aggregates = [dict(metadata=dict(zip(AGGREGATE_KEYS, ident)), metrics=old.aggregate_samples(items))
                  for ident, items in grouped.items()]
    comparisons = compare_predictions(data)
    criteria = group_criteria(records, comparisons)
    budget.check()
    extras = dict(aggregates=aggregates, criteria=criteria, comparisons=comparisons,
                  schema_note="24a diagnostics on already known controls; not held-out validation",
                  frozen_predictions_sha256=file_hash(root / "frozen-predictions.json"))
    old.write_summary(records, out, extras=extras)
    for name, values in (("aggregates", aggregates), ("criteria", criteria), ("comparisons", comparisons)):
        write_json(out / (name + ".json"), values)
        old._flat_csv(out / (name + ".csv"), values)
    (out / "report.md").write_text(render_report(criteria, aggregates), encoding="utf-8")
    evidence = dict(schema="stmdomains-graph24a-evaluation-evidence-v1",
                    frozen_manifest_sha256=file_hash(root / "frozen-predictions.json"),
                    verified_frozen_files=len(frozen["files"]), evaluated_records=len(records),
                    verified_source_row_hashes=len(samples),
                    control_count=len(truths), control_seeds=truth_manifest["seeds"],
                    controls_manifest_sha256=file_hash(controls_dir / "manifest.json"),
                    no_new_fits=True, known_controls=True, heldout_validation=False,
                    original_support="S24sameIDsandsupport; refused nodes remain in denominator",
                    boundary_cases=list(BOUNDARY_CASES), nonregression_tolerance=NONREGRESSION_TOLERANCE,
                    source_code_sha256=file_hash(Path(__file__)), resources=budget.measurements())
    write_json(out / "evidence.json", evidence)
    return evidence


def evaluate_frozen(root, controls_dir=None, out=None):
    root = Path(root).resolve()
    out = Path(out or root / "evaluation")
    resource_path = root / (out.name + ".resources.json")
    if out.exists() or resource_path.exists():
        raise FileExistsError("Use a fresh24a evaluation output; no implicit retries")
    budget, status = Budget(root), "failed"
    try:
        result = _evaluate(root, controls_dir, out, budget)
        status = "completed"
        return result
    finally:
        write_json(resource_path, dict(status=status, **budget.measurements()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--controls-evaluation", type=Path)
    parser.add_argument("--evaluation-output", type=Path)
    args = parser.parse_args()
    result = evaluate_frozen(args.output, args.controls_evaluation, args.evaluation_output)
    print(json.dumps({k: result[k] for k in ("evaluated_records", "control_count", "known_controls", "heldout_validation")}))


if __name__ == "__main__":
    main()
