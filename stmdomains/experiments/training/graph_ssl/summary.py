"""Reproducible issue-24 report from frozen predictions and completed evaluation.

This module never selects a seed, checkpoint, threshold or favourable case.
Its tables retain every family, partition, regime and seed in the evaluation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from ...bundle import file_hash, write_json
from .. import evaluate as old


def read(path):
    return json.loads(Path(path).read_text())


def percentage(value):
    return "—" if value is None else f"{100 * value:.1f}%"


def outcome(value):
    return "tak" if value is True else "nie" if value is False else "brak miary"


def report_tables(evaluation):
    """Pool only already evaluated within-frame counts; retain all seeds."""
    grouped = defaultdict(list)
    keys = ("regime", "family", "latent", "seed", "partition", "kind", "case")
    for row in evaluation["records"]:
        grouped[tuple(row["metadata"].get(name) for name in keys)].append(row["metrics"])
    measurement, controls = [], []
    for ident, records in grouped.items():
        meta = dict(zip(keys, ident))
        pooled = old.aggregate_samples(records)
        for stage in ("before", "after"):
            metrics = pooled[stage]
            row = dict(meta, stage=stage, sample_count=len(records),
                       evaluated_elements=pooled["evaluated_elements"],
                       assigned_evaluated_elements=metrics["assigned_evaluated_elements"],
                       coverage=metrics["coverage"], merge_rate=metrics["pairs"]["merge_rate"],
                       split_rate=metrics["pairs"]["split_rate"],
                       same_reference_pairs=metrics["pairs"]["same_reference_pairs"],
                       different_reference_pairs=metrics["pairs"]["different_reference_pairs"],
                       local_merge_rate=metrics["local_pairs"]["merge_rate"],
                       local_split_rate=metrics["local_pairs"]["split_rate"],
                       domain_count_sum=metrics["domain_count_sum"],
                       boundary_f1=metrics["boundary"]["f1"],
                       assigned_without_support=metrics["assigned_without_support"])
            if meta["kind"] == "measurement":
                row.update(per_orientation_group=metrics["per_orientation_group"],
                           partial_reference_scope=pooled["criteria"],
                           limitations="Positive partial references only; no full image recall or material area")
                measurement.append(row)
            else:
                states = Counter("pass" if r["criteria"]["qualified"] else
                                 "fail" if r["criteria"]["applicable"] and r["criteria"]["passed"] is False
                                 else "unavailable" for r in records)
                row.update(criteria_after=dict(states), criteria=pooled["criteria"] if stage == "after" else None)
                controls.append(row)
    order = lambda row: json.dumps([row.get(k) for k in (*keys, "stage")])
    return sorted(measurement, key=order), sorted(controls, key=order)


def markdown(result):
    lines = ["# Próba grafowa 24 — raport z artefaktów", "",
             f"Fitów: {result['training']['fit_count']}; ukończonych: {result['training']['completed_count']}. "
             f"Predykcji: {result['evidence']['prediction_entries']}; "
             f"ocenionych rekordów: {result['evidence']['evaluated_records']}.", "",
             "Główna metoda: graph_sce_scale. graph_sce jest diagnostyką samego SCE. "
             "geometry i własne graph_untrained porównujemy w tym samym podziale; "
             "legacy15 jest pełną procedurą historyczną na dostosowanym wsparciu.", "",
             "## Warunki kontynuacji", "",
             "| Reżim | Rodzina | Podział | Kontrole | Stabilność | Kontynuacja |",
             "|---|---|---|---|---|---|"]
    for row in result["continuation"]:
        meta = row["metadata"]
        lines.append(f"| {meta['regime']} | {meta['family']} | {meta['partition']} | "
                     f"{outcome(row['synthetic_controls']['passed'])} | {outcome(row['stability'])} | "
                     f"{outcome(row['continuation']['passed']) if row['continuation']['applicable'] else 'punkt odniesienia'} |")
    lines += ["", "Wymagana przewaga końcowa obejmuje klasyczny opis i własną inicjalizację, "
              "osobno na kontrolach i TTMAPP; żaden korzystny pojedynczy seed nie kwalifikuje metody.", "",
              "## Częściowe referencje TTMAPP", "",
              "W transferze podsumowanie używa wyłącznie osobnego grafu miejsc testowych. "
              "Coverage ma mianownik dostępnych, ocenialnych oznaczeń, nie wszystkich molekuł lub powierzchni.", "",
              "| Reżim | Rodzina | Ziarno | Podział | Etap | Przypisania | Coverage | Merge | Split |",
              "|---|---|---|---|---|---|---|---|---|"]
    for row in result["ttmapp"]:
        lines.append(f"| {row['regime']} | {row['family']} | {row['seed'] if row['seed'] is not None else '—'} | "
                     f"{row['partition']} | {row['stage']} | {row['assigned_evaluated_elements']}/{row['evaluated_elements']} | "
                     f"{percentage(row['coverage'])} | {percentage(row['merge_rate'])} | {percentage(row['split_rate'])} |")
    lines += ["", "## Kontrole po odmowach", "",
              "Każdy wiersz zachowuje ziarno modelu i sumuje trzy ziarna danej kontroli. "
              "Puste noise/stripes są brakiem dowodu jakości, a nie zaliczonym negatywem.", "",
              "| Reżim | Rodzina | Ziarno | Podział | Kontrola | Przypisania | Coverage | Merge | Split | F1 | Zaliczone/błędne/brak |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for row in result["controls"]:
        if row["stage"] != "after":
            continue
        counts = row["criteria_after"]
        tally = "/".join(str(counts.get(name, 0)) for name in ("pass", "fail", "unavailable"))
        lines.append(f"| {row['regime']} | {row['family']} | {row['seed'] if row['seed'] is not None else '—'} | "
                     f"{row['partition']} | {row['case']} | {row['assigned_evaluated_elements']}/{row['evaluated_elements']} | "
                     f"{percentage(row['coverage'])} | {percentage(row['merge_rate'])} | "
                     f"{percentage(row['split_rate'])} | {percentage(row['boundary_f1'])} | {tally} |")
    lines += ["", "## Ograniczenia", "", *["- " + text for text in result["limitations"]], "",
              "Pełne liczniki, wszystkie rekordy i kryteria: evaluation/summary.json. "
              "Raport nie zmienia predykcji ani nie wybiera dalszego ticketa.", ""]
    return "\n".join(lines)


def build(root, out=None):
    root = Path(root).resolve()
    out = Path(out or root / "report")
    if out.exists():
        raise FileExistsError(f"Use a fresh report directory: {out}")
    evidence_path = root / "evaluation/evaluation-evidence.json"
    evidence = read(evidence_path)
    frozen_path = root / "frozen-predictions.json"
    if evidence["frozen_manifest_sha256"] != file_hash(frozen_path):
        raise ValueError("Evaluation belongs to another frozen prediction set")
    frozen = read(frozen_path)
    source_files = [evidence_path, frozen_path, root / "plan.json", root / "prepared/manifest.json",
                    root / "evaluation/summary.json"]
    for path in sorted((root / "evaluation").glob("*.json")):
        if path not in source_files:
            source_files.append(path)
    evaluation = read(root / "evaluation/summary.json")
    if len(evaluation["records"]) != evidence["evaluated_records"]:
        raise ValueError("Incomplete evaluation summary")
    runs = []
    for path in sorted((root / "training").rglob("run.json")):
        relative = str(path.relative_to(root))
        if relative not in frozen["files"] or file_hash(path) != frozen["files"][relative]:
            raise ValueError("Training result was not frozen")
        source_files.append(path)
        run = read(path)
        fields = ("run_id", "regime", "loss_name", "seed", "status", "stop_reason", "selected_step",
                  "best_validation_loss", "completed_steps", "seconds", "training_graphs", "validation_graphs",
                  "parameter_count", "completed_optimizer_steps", "skipped_uninformative_steps",
                  "peak_rss_bytes", "cuda_peak_allocated_bytes", "cuda_peak_reserved_bytes",
                  "selected_checkpoint_sha256", "initial_state_sha256")
        runs.append({name: run.get(name) for name in fields})
    measurement, controls = report_tables(evaluation)
    primary = [row for row in evaluation["criteria"] if row["primary"]]
    result = dict(schema="stmdomains-graph24-report-v1", evidence=evidence,
                  primary_family="graph_sce_scale", any_primary_qualified=any(r["continuation"]["qualified"] for r in primary),
                  training=dict(fit_count=len(runs), completed_count=sum(r["status"] == "completed" for r in runs),
                                total_fit_seconds=sum(r["seconds"] for r in runs), runs=runs),
                  prepared_counts=read(root / "prepared/manifest.json")["counts"],
                  ttmapp=measurement, controls=controls, continuation=evaluation["criteria"],
                  benefits=evaluation["benefits"], stability=evaluation["stability"],
                  annotation_perturbations=evaluation["ablations"],
                  limitations=["One correlated acquisition with partial positive references; no independent-acquisition generalization.",
                               "Annotation-node coverage is neither molecular detection recall nor measured material area.",
                               "Missing-band and empty material-gap cases may have identical annotation geometry.",
                               "Noise and stripes with no centres cannot certify image-negative discrimination.",
                               "Legacy15 has its full cell/refusal procedure on both displayed stages; it is not a pure feature comparison.",
                               "No physical type, orientation or material label is inferred from descriptor groups."])
    resources = {}
    for path in sorted(root.glob("*resources.json")):
        resources[path.name] = read(path)
        source_files.append(path)
    result["resources"] = resources
    out.mkdir(parents=True)
    write_json(out / "summary.json", result)
    old._flat_csv(out / "ttmapp.csv", measurement)
    old._flat_csv(out / "controls.csv", controls)
    old._flat_csv(out / "training.csv", runs)
    (out / "report.md").write_text(markdown(result), encoding="utf-8")
    write_json(out / "manifest.json", dict(schema="stmdomains-graph24-report-manifest-v1",
               code_sha256=file_hash(Path(__file__)),
               sources={str(path.relative_to(root)): file_hash(path) for path in source_files},
               files={path.name: file_hash(path) for path in sorted(out.iterdir()) if path.is_file()},
               prediction_modification=False, checkpoint_selection=False))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path)
    args = parser.parse_args()
    result = build(args.output, args.report_output)
    print(json.dumps(dict(fits=result["training"]["fit_count"],
                          primary_qualified=result["any_primary_qualified"],
                          ttmapp_table_rows=len(result["ttmapp"]), control_table_rows=len(result["controls"]))))


if __name__ == "__main__":
    main()
