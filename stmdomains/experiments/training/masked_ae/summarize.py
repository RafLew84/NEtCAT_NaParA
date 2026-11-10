"""Compact issue25 evidence: fixed primary mask50, every seed retained."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ...bundle import file_hash, write_json
from .common import reporting_stage


def read(path):
    return json.loads(Path(path).read_text())


def main_results(output):
    measurements, controls = [], []
    for row in read(output / "evaluation/aggregates.json"):
        meta, metrics = row["metadata"], row["metrics"]
        if meta["scale_px"] != 48 or meta["sampler"] != "grid":
            continue
        stages = {}
        for stage in ("before", "after"):
            value = metrics[stage]
            fields = ("coverage", "assigned_evaluated_elements", "assigned_without_support", "pairs", "local_pairs", "boundary", "domain_count_sum", "per_orientation_group")
            stages[stage] = {name: value[name] for name in fields if name in value}
        result = dict(metadata=meta, evaluated_elements=metrics["evaluated_elements"],
                      full_support_elements=metrics["full_support_elements"], sample_count=metrics["sample_count"],
                      criteria=metrics["criteria"], **stages)
        if meta["kind"] == "measurement":
            measurements.append(result)
        else:
            values = list(metrics["criteria"]["checks"].values()) if metrics["criteria"]["applicable"] else []
            result["control_realizations"] = dict(passed=sum(v is True for v in values), failed=sum(v is False for v in values),
                unavailable=metrics["sample_count"] - sum(v is True or v is False for v in values))
            controls.append(result)
    result = dict(schema="stmdomains-masked-ae25-main-results-v1", primary="mask50/grid48",
                  measurement=measurements, controls=controls,
                  counting="Every model seed retained; per-seed control aggregate contains three realizations; FFT has no model seed",
                  interpretation="Coverage is an assigned-element fraction, not molecule detection recall or material area")
    write_json(output / "main-result-summary.json", result)
    return result


def build(output, destination):
    output, destination = Path(output).resolve(), Path(destination).resolve()
    with reporting_stage(output, "summarize") as budget:
        evidence = read(output / "evaluation/evaluation-evidence.json")
        if evidence["frozen_manifest_sha256"] != file_hash(output / "frozen-predictions.json"):
            raise ValueError("Evaluation and current frozen prediction set differ")
        frozen = read(output / "frozen-predictions.json")
        results = main_results(output)
        runs = []
        for path in sorted((output / "training").glob("*/*/z32/seed-*/run.json")):
            budget.check()
            if file_hash(path) != frozen["files"][str(path.relative_to(output))]:
                raise ValueError("Training report changed after prediction freeze")
            run = read(path)
            fields = ("status", "stop_reason", "family", "latent_dim", "seed", "regime", "selected_step",
                      "completed_steps", "completed_optimizer_steps", "selected_checkpoint_sha256", "initial_checkpoint_sha256",
                      "seconds", "parameter_count", "peak_rss_bytes", "cuda_peak_allocated_bytes", "best_validation_loss")
            selected = next((r for r in run.get("validation_history", []) if r["step"] == run.get("selected_step")), None)
            runs.append(dict({name: run.get(name) for name in fields}, run_id=str(path.parent.relative_to(output)), selected_validation=selected))
        if not 1 <= len(runs) <= 12:
            raise ValueError("Expected at most twelve bounded masked reconstruction attempts")
        continuation = read(output / "evaluation/continuation.json")
        benefits = read(output / "evaluation/benefits.json")
        primary_benefits = [r for r in benefits if r["metadata"]["family"] == "mask50" and
                           (r["metadata"]["kind"] == "measurement" or r["metadata"]["case"] == "__all__")]
        resources = {p.name: read(p) for p in sorted(output.glob("*.resources.json"))}
        names = {str(p.relative_to(output)) for p in output.glob("*.json") if p.resolve() != destination and not p.name.endswith(".resources.json")}
        names.update(str(p.relative_to(output)) for p in (output / "training").glob("*/*/z32/seed-*/run.json"))
        for folder in ("evaluation", "figures", "gallery", "audits"):
            names.update(str(p.relative_to(output)) for p in (output / folder).glob("*") if p.is_file())
        for relative in ("training/registry.json", "training/training-audit.json", "features/index.json", "index.html"):
            if (output / relative).exists():
                names.add(relative)
        artifacts = {name: file_hash(output / name) for name in budget.checked(sorted(names))}
        plan = read(output / "plan.json")
        result = dict(schema="stmdomains-masked-autoencoder25-evidence-v1", issue=25, output=str(output),
            primary="mask50; grid48; every seed, both solvers and separate transfer/transduction",
            plan_sha256=file_hash(output / "plan.json"), source_sha256=plan["code_sha256"], fits=runs,
            total_fit_seconds=sum(r.get("seconds") or 0 for r in runs), completed_steps=sum(r.get("completed_steps") or 0 for r in runs),
            resources=resources, postprocess_cpu_seconds=sum(r["cpu_seconds"] for r in resources.values()),
            summary_stage_current_resources=budget.measurements(),
            continuation=continuation, paired_benefits_primary=primary_benefits,
            ttmapp_grid48=results["measurement"], control_grid48=results["controls"],
            any_primary_qualified=any(r["primary_claim_qualified"] for r in continuation),
            evaluation=evidence, artifacts_sha256=artifacts, application_detector_adopted=False,
            limitations=["New seeds of known synthetic families; existing TTMAPP has repeatedly informed development",
                         "One correlated acquisition with uncertain saved registration; no independent STM generalization",
                         "Positive partial references only; no full-image recall, material mask or exact TTMAPP boundary",
                         "Annotation perturbations leave images unchanged; grid invariance is not image-jitter robustness",
                         "Reconstruction and descriptor diagnostics do not establish domain accuracy",
                         "mask25 is diagnostic; no mask-ratio or winning-seed selection using evaluation truth"])
        write_json(destination, result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    value = build(args.output, args.manifest)
    print(json.dumps({name: value[name] for name in ("completed_steps", "total_fit_seconds", "any_primary_qualified")}))


if __name__ == "__main__":
    main()
