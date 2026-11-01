"""Compact versioned evidence26; full per-case evidence remains local."""
from __future__ import annotations

import argparse
from collections import Counter
import itertools
import json
from pathlib import Path
import statistics

from ...bundle import file_hash, write_json
from ..masked_ae.evaluate import primary
from .common import reporting_stage


BOUNDARIES = ("two_orientations", "orientation_8deg", "different_spacing", "phase_boundary")


def read(path):
    return json.loads(Path(path).read_text())


def outcomes(values):
    counts = Counter("passed" if value is True else "failed" if value is False else "unavailable" for value in values)
    return {name: counts[name] for name in ("passed", "failed", "unavailable")}


def compact_verdict(record):
    result = {name: record[name] for name in ("metadata", "available_adaptation_seeds", "missing_adaptation_seeds", "evidence_status",
        "representation_improved_before", "complete_detector_after", "fixed_gate_ceiling", "claim_scope", "paired_benefits")}
    for stage in ("before", "after"):
        value = record[stage]
        checks = value["controls"]["checks"]
        result[stage] = dict(criteria=value["criteria"], stability=value["stability"],
            control_criteria_cases=value["control_criteria_cases"], synthetic_benefit_cohort=value["synthetic_benefit_cohort"],
            control_counts_by_seed={str(seed): outcomes(v for k, v in checks.items() if k.startswith(f"model_seed={seed}/")) for seed in (20261101, 20261102, 20261103)},
            control_counts_by_case={case: outcomes(v for k, v in checks.items() if k.endswith("/case=" + case)) for case in value["control_criteria_cases"]})
    return result


def measurement_table(aggregates):
    rows = []
    for record in aggregates:
        meta, metrics = record["metadata"], record["metrics"]
        if not primary(meta) or meta["kind"] != "measurement":
            continue
        row = dict(metadata={k: meta[k] for k in ("regime", "family", "seed", "partition")},
                   evaluated_elements=metrics["evaluated_elements"], full_support_elements=metrics["full_support_elements"])
        for stage in ("before", "after"):
            value = metrics[stage]
            row[stage] = dict(assigned=value["assigned_evaluated_elements"], coverage=value["coverage"],
                assigned_without_support=value["assigned_without_support"], pairs=value["pairs"],
                per_orientation_group=value["per_orientation_group"], boundary_f1=value["boundary"]["f1"])
        rows.append(row)
    return rows


def boundary_table(aggregates):
    rows = []
    for regime, family, partition, stage in itertools.product(("transfer", "transductive"), ("dino_adapted", "dino_frozen", "fft"), ("fh4", "mws"), ("before", "after")):
        cells = {}
        for case in BOUNDARIES:
            values = sorted([r for r in aggregates if primary(r["metadata"]) and r["metadata"]["regime"] == regime and r["metadata"]["family"] == family
                             and r["metadata"]["partition"] == partition and r["metadata"]["case"] == case], key=lambda r: str(r["metadata"]["seed"]))
            scores = [r["metrics"][stage]["boundary"]["f1"] for r in values]
            expected = 3 if family == "dino_adapted" else 1
            complete = len(scores) == expected and all(v is not None for v in scores)
            cells[case] = dict(model_seeds=[r["metadata"]["seed"] for r in values], per_seed=scores,
                median=statistics.median(scores) if complete else None, minimum=min(scores) if complete else None,
                maximum=max(scores) if complete else None, all_planned_models_available=len(scores) == expected)
        rows.append(dict(regime=regime, family=family, partition=partition, stage=stage, f1=cells))
    return rows


def accounting_snapshot(output, budget):
    reports = {p.name: read(p) for p in sorted(output.glob("*.resources.json"))}
    overhead_names = [name for name in reports if name.endswith("-process-overhead.resources.json")]
    internal_names = [name for name in reports if name not in overhead_names]
    process_reports = {}
    process_files = {}
    for path in sorted((output / ".execution").glob("*.json")):
        result = read(path)
        process_reports[path.name] = {k: result.get(k) for k in ("returncode", "cpu_seconds", "user_cpu_seconds", "system_cpu_seconds", "wall_seconds", "max_rss_bytes", "fit_suite", "internal_report_cpu_seconds", "accounting")}
        process_files[str(path.relative_to(output))] = file_hash(path)
        log = path.with_suffix(".log")
        if log.exists():
            if result.get("stdout_sha256") != file_hash(log):
                raise ValueError("Completed process log differs from its wait4 record")
            process_files[str(log.relative_to(output))] = file_hash(log)
    return dict(internal_stage_cpu_seconds=sum(reports[n]["cpu_seconds"] for n in internal_names),
        process_overhead_residual_cpu_seconds=sum(reports[n]["cpu_seconds"] for n in overhead_names),
        completed_ledger_cpu_seconds=sum(r["cpu_seconds"] for r in reports.values()),
        current_summary_stage_snapshot=budget.measurements(),
        ledger_reports_sha256={name: file_hash(output / name) for name in reports},
        completed_processes=process_reports, completed_process_artifacts_sha256=process_files,
        accounting="Add internal ledgers and process-overhead residuals; wait4 totals are observational, never added again",
        snapshot_scope="Completed reports at manifest writing; current summary ledger and its outer process report close after this snapshot")


def build(output, destination):
    output, destination = Path(output).resolve(), Path(destination).resolve()
    full_path = output / "result-manifest.json"
    if destination == full_path or destination.exists() or full_path.exists():
        raise FileExistsError("Choose a fresh compact manifest; preserve the separate full local manifest")
    with reporting_stage(output, "summarize") as budget:
        evidence = read(output / "evaluation/evaluation-evidence.json")
        if evidence["frozen_manifest_sha256"] != file_hash(output / "frozen-predictions.json"):
            raise ValueError("Evaluation and frozen predictions differ")
        frozen = read(output / "frozen-predictions.json")
        plan = read(output / "plan.json")
        if file_hash(output / "plan.json") != frozen["files"]["plan.json"]:
            raise ValueError("Plan changed after prediction freeze")
        fits = []
        for path in sorted((output / "training").glob("*/dino_adapted/seed-*/run.json")):
            budget.check()
            if file_hash(path) != frozen["files"][str(path.relative_to(output))]:
                raise ValueError("Adaptation report changed after freeze")
            run = read(path)
            names = ("run_id", "status", "stop_reason", "error", "regime", "seed", "selected_step", "completed_steps", "completed_optimizer_steps", "seconds",
                "selected_checkpoint_sha256", "initial_checkpoint_sha256", "base_checkpoint_sha256", "base_state_sha256", "trainable_parameter_count", "parameter_count",
                "peak_rss_bytes", "cuda_peak_allocated_bytes", "frozen_proof")
            fits.append(dict({name: run.get(name) for name in names}, file=str(path.relative_to(output)), sha256=file_hash(path)))
        registry = read(output / "training/registry.json")
        actual = read(output / "predictions/actual-matrix.json")
        aggregates = read(output / "evaluation/aggregates.json")
        verdicts = read(output / "evaluation/verdicts.json")
        benefits = read(output / "evaluation/benefits.json")
        diagnostics = read(output / "feature-diagnostics.json")
        primary_benefits = [r for r in benefits if r["metadata"]["kind"] == "measurement" or
            (r["metadata"]["case"] == ("__positive__" if r["metadata"]["stage"] == "before" else "__all__"))]
        resource_snapshot = accounting_snapshot(output, budget)
        artifacts = {}
        for folder in ("evaluation", "audits", "figures", "gallery", "browser"):
            for path in sorted((output / folder).glob("*")):
                if path.is_file():
                    artifacts[str(path.relative_to(output))] = file_hash(path)
                budget.check()
        for relative in ("plan.json", "frozen-predictions.json", "training/registry.json", "predictions/actual-matrix.json", "feature-diagnostics.json", "index.html"):
            if (output / relative).exists():
                artifacts[relative] = file_hash(output / relative)
        full = dict(schema="stmdomains-pretrained-ssl26-local-evidence-v1", output=str(output), fits=fits, registry=registry,
            actual_matrix=actual, evaluation=evidence, verdicts=verdicts, benefits=benefits,
            primary_aggregates=[r for r in aggregates if primary(r["metadata"])], diagnostics=diagnostics,
            accounting=resource_snapshot, artifacts_sha256=artifacts, plan_sha256=file_hash(output / "plan.json"),
            code_sha256=plan["code_sha256"])
        write_json(full_path, full)
        matrix_fields = ("completed_adaptations", "all_planned_adaptations_completed", "omitted_adaptations", "models", "full_predictions", "heldout_archives",
                         "test_frame_heldout_archives", "empty_non_test_heldout_archives", "adapter_count", "maximum_models", "maximum_full_predictions", "maximum_heldout_archives")
        compact = dict(schema="stmdomains-pretrained-ssl26-evidence-v1", issue=26, output=str(output),
            primary="Fixed1000-step EMA teacher, last block+norm adaptation, mean384, grid48; three planned seeds",
            plan_sha256=file_hash(output / "plan.json"), code_sha256=plan["code_sha256"],
            full_local_manifest=dict(path=str(full_path), sha256=file_hash(full_path)), fits=fits,
            total_fit_seconds=sum(r.get("seconds") or 0 for r in fits),
            fit_time_scope="Sum of available terminal run.json times; all launched worker wall/CPU costs are separately recorded in registry_summary",
            completed_optimizer_steps=None if registry["unknown_optimizer_steps"] else registry["quality_optimizer_steps_known"],
            known_optimizer_steps=registry["quality_optimizer_steps_known"], unknown_optimizer_steps=registry["unknown_optimizer_steps"],
            registry_summary={name: registry.get(name) for name in ("suite_finished", "completed_count", "planned_run_ids", "outcomes", "worker_wall_seconds", "worker_cpu_seconds", "checkpoint_bytes")},
            actual_matrix={name: actual.get(name) for name in matrix_fields},
            verdicts=[compact_verdict(r) for r in verdicts], paired_benefits_primary=primary_benefits,
            any_representation_improved_before=any(r["representation_improved_before"] for r in verdicts),
            any_complete_detector_after=any(r["complete_detector_after"] for r in verdicts),
            ttmapp_grid48=measurement_table(aggregates), boundary_grid48=boundary_table(aggregates),
            evaluation=evidence, resources=resource_snapshot, artifacts_sha256=artifacts, application_detector_adopted=False,
            limitations=["Frozen20 order/connectivity ceiling makes final TTMAPP coverage gates unreachable by descriptor adaptation alone",
                "A positive before-refusal representation verdict would not accept a complete domain detector",
                "The original DINO weights are reused in pipeline26; this is not a bitwise rerun of extraction18/19",
                "New seeds of known synthetic families; one previously studied, correlated STM acquisition",
                "Partial positive TTMAPP references do not provide full-image recall, material area or exact boundaries",
                "Missing adaptation seeds are insufficient evidence; no substitute checkpoint or replacement fit",
                "Moving-teacher CE, entropy, rank and descriptor drift are diagnostics, not domain accuracy or checkpoint ranking",
                "Token-head256 outputs are training coordinates, not a prescribed number of domains or structural types"])
        write_json(destination, compact)
        return compact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.output, args.manifest)
    print(json.dumps({k: result[k] for k in ("completed_optimizer_steps", "total_fit_seconds", "any_representation_improved_before", "any_complete_detector_after")}))


if __name__ == "__main__":
    main()
