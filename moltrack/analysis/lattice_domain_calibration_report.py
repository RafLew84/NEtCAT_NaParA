"""Atomic JSON, CSV, and Markdown output for M3/M6 calibration."""

from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4

from .lattice_domain_calibration_models import (
    LatticeDomainCalibrationAggregateMetrics,
    LatticeDomainCalibrationReport,
)


def write_lattice_domain_calibration_report(
    report: LatticeDomainCalibrationReport,
    destination: str | Path,
) -> dict[str, Path]:
    """Publish one immutable report directory after every file is complete."""

    if not isinstance(report, LatticeDomainCalibrationReport):
        raise TypeError("report must be a lattice-domain calibration report.")
    output_dir = Path(destination)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = _report_to_dict(report)
    fingerprint = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    payload["report_fingerprint"] = fingerprint
    run_name = (
        "lattice_domain_calibration_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + f"_{fingerprint[:10]}_{uuid4().hex[:8]}"
    )
    final_dir = output_dir / run_name
    staging_dir = Path(
        tempfile.mkdtemp(
            prefix=f".{run_name}_",
            dir=output_dir,
        )
    )
    staging_paths = _report_paths(staging_dir)
    try:
        staging_paths["json"].write_text(
            json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )
        staging_paths["markdown"].write_text(
            _markdown_report(report, fingerprint=fingerprint),
            encoding="utf-8",
        )
        _write_variants_csv(report, staging_paths["variants_csv"])
        staging_dir.rename(final_dir)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    return _report_paths(final_dir)


def _report_paths(directory: Path) -> dict[str, Path]:
    return {
        "json": directory / "lattice_domain_calibration.json",
        "markdown": directory / "lattice_domain_calibration.md",
        "variants_csv": directory / "lattice_domain_calibration_variants.csv",
    }


def _report_to_dict(report: LatticeDomainCalibrationReport) -> dict[str, object]:
    return {
        "schema_version": report.schema_version,
        "status": report.status,
        "reference_dataset_id": report.reference_dataset_id,
        "reference_dataset_fingerprint": report.reference_dataset_fingerprint,
        "source_file_name": report.source_file_name,
        "source_frame_count": report.source_frame_count,
        "source_sample_fingerprint": report.source_sample_fingerprint,
        "source_view": report.source_view,
        "use_segmentation_centroids": report.use_segmentation_centroids,
        "uses_tracking": report.uses_tracking,
        "preset_modified": report.preset_modified,
        "algorithm_versions": dict(report.algorithm_versions),
        "calibration_frame_indices": list(report.calibration_frame_indices),
        "holdout_frame_indices": list(report.holdout_frame_indices),
        "baseline_settings": report.baseline_settings.to_dict(),
        "selected_settings": (
            None
            if report.selected_settings is None
            else report.selected_settings.to_dict()
        ),
        "best_variant_id": report.best_variant_id,
        "variant_results": [
            {
                "variant_id": value.variant.variant_id,
                "phase": value.variant.phase,
                "changed_parameters": list(value.variant.changed_parameters),
                "settings": value.variant.settings.to_dict(),
                "score": value.score,
                "metrics": asdict(value.metrics),
            }
            for value in report.variant_results
        ],
        "skipped_variants": [asdict(value) for value in report.skipped_variants],
        "holdout_metrics": (
            None if report.holdout_metrics is None else asdict(report.holdout_metrics)
        ),
        "holdout_passed": report.holdout_passed,
        "quality_impacts": [
            {
                "quality_tag": value.quality_tag,
                "split": value.split,
                "tagged_metrics": (
                    None
                    if value.tagged_metrics is None
                    else asdict(value.tagged_metrics)
                ),
                "control_metrics": (
                    None
                    if value.control_metrics is None
                    else asdict(value.control_metrics)
                ),
                "mean_adjusted_rand_index_delta": (
                    value.mean_adjusted_rand_index_delta
                ),
            }
            for value in report.quality_impacts
        ],
        "first_shell_validation": [
            asdict(value) for value in report.first_shell_validation
        ],
        "first_shell_validation_passed": report.first_shell_validation_passed,
        "stable_ranges": [asdict(value) for value in report.stable_ranges],
        "indeterminate_parameters": list(report.indeterminate_parameters),
    }


def _write_variants_csv(
    report: LatticeDomainCalibrationReport,
    path: Path,
) -> None:
    metric_names = tuple(
        LatticeDomainCalibrationAggregateMetrics.__dataclass_fields__
    )
    field_names = (
        "variant_id",
        "phase",
        "changed_parameters",
        "score",
        *metric_names,
    )
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=field_names)
        writer.writeheader()
        for value in report.variant_results:
            writer.writerow(
                {
                    "variant_id": value.variant.variant_id,
                    "phase": value.variant.phase,
                    "changed_parameters": ";".join(
                        value.variant.changed_parameters
                    ),
                    "score": value.score,
                    **asdict(value.metrics),
                }
            )


def _markdown_report(
    report: LatticeDomainCalibrationReport,
    *,
    fingerprint: str,
) -> str:
    selected = (
        "none"
        if report.selected_settings is None
        else f"`{report.best_variant_id}`"
    )
    lines = [
        "# Final M3/M6 lattice-domain calibration",
        "",
        f"- Status: `{report.status}`",
        f"- Report fingerprint: `{fingerprint}`",
        f"- Reference dataset: `{report.reference_dataset_id}`",
        f"- Reference fingerprint: `{report.reference_dataset_fingerprint}`",
        f"- Source: `{report.source_file_name}` / `{report.source_view}`",
        f"- Source frame count: `{report.source_frame_count}`",
        f"- Source sample fingerprint: `{report.source_sample_fingerprint}`",
        f"- Calibration frames: `{_frame_numbers(report.calibration_frame_indices)}`",
        f"- Holdout frames: `{_frame_numbers(report.holdout_frame_indices)}`",
        f"- Selected variant: {selected}",
        f"- Tracking used: `{str(report.uses_tracking).lower()}`",
        f"- Preset modified: `{str(report.preset_modified).lower()}`",
        "",
        "## Algorithm versions",
        "",
        *(
            f"- `{name}`: `{version}`"
            for name, version in report.algorithm_versions
        ),
        "",
        "## Calibration variants",
        "",
        (
            "| Variant | Phase | ARI | VI [nat] | Count MAE | Assigned | "
            "Boundary P/R | Brier | ECE | Stability | Over/under |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for value in report.variant_results:
        metrics = value.metrics
        lines.append(
            "| "
            f"{value.variant.variant_id} | {value.variant.phase} | "
            f"{metrics.mean_adjusted_rand_index:.4f} | "
            f"{metrics.mean_variation_of_information_nats:.4f} | "
            f"{metrics.mean_absolute_domain_count_error:.4f} | "
            f"{metrics.mean_correctly_assigned_molecule_fraction:.4f} | "
            f"{_optional_number(metrics.boundary_precision)}/"
            f"{_optional_number(metrics.boundary_recall)} | "
            f"{_optional_number(metrics.mean_confidence_brier_score)} | "
            f"{_optional_number(metrics.mean_confidence_expected_calibration_error)} | "
            f"{_optional_number(metrics.mean_partition_stability_ari)} | "
            f"{metrics.over_segmentation_count}/"
            f"{metrics.under_segmentation_count} |"
        )
    lines.extend(["", "## Skipped variants", ""])
    if not report.skipped_variants:
        lines.append("None.")
    else:
        for value in report.skipped_variants:
            lines.append(f"- `{value.variant_id}`: {value.reason}")
    lines.extend(["", "## Holdout", ""])
    if report.holdout_metrics is None:
        lines.append("Holdout was not opened because no stable solution exists.")
    else:
        lines.append(
            "- Holdout threshold passed: "
            f"`{str(bool(report.holdout_passed)).lower()}`"
        )
        lines.extend(_metric_bullets(report.holdout_metrics))
    lines.extend(["", "## Stable ranges", ""])
    if not report.stable_ranges:
        lines.append("No stable parameter range was identified.")
    else:
        for value in report.stable_ranges:
            lines.append(
                f"- `{value.parameter_name}`: "
                f"{value.minimum_value} to {value.maximum_value}"
            )
    if report.indeterminate_parameters:
        lines.extend(
            [
                "",
                "## Indeterminate parameters",
                "",
                ", ".join(f"`{value}`" for value in report.indeterminate_parameters),
            ]
        )
    lines.extend(["", "## First-shell validation", ""])
    lines.append(
        "- Required M3/M6 geometry validation passed: "
        f"`{str(report.first_shell_validation_passed).lower()}`"
    )
    for value in report.first_shell_validation:
        lines.append(
            f"- {value.symmetry_class}: "
            f"{value.first_shell_r_min_nm:g}-{value.first_shell_r_max_nm:g} nm; "
            f"status `{value.status}`; edges "
            f"{value.true_positive_edge_count}/{value.reference_edge_count}; "
            f"precision {_optional_number(value.precision)}, "
            f"recall {_optional_number(value.recall)}, "
            f"F1 {_optional_number(value.f1_score)}"
        )
    lines.extend(["", "## Quality effects", ""])
    for value in report.quality_impacts:
        lines.append(
            f"- {value.quality_tag} ({value.split}): tagged ARI "
            f"{_metric_ari(value.tagged_metrics)}, control ARI "
            f"{_metric_ari(value.control_metrics)}, delta "
            f"{_optional_number(value.mean_adjusted_rand_index_delta)}"
        )
    lines.append("")
    return "\n".join(lines)


def _metric_bullets(
    metrics: LatticeDomainCalibrationAggregateMetrics,
) -> list[str]:
    return [
        f"- Frames: `{metrics.frame_count}`",
        f"- Molecules: `{metrics.evaluated_molecule_count}`",
        f"- Mean adjusted Rand index: `{metrics.mean_adjusted_rand_index:.6f}`",
        (
            "- Mean variation of information [nat]: "
            f"`{metrics.mean_variation_of_information_nats:.6f}`"
        ),
        (
            "- Mean absolute domain-count error: "
            f"`{metrics.mean_absolute_domain_count_error:.6f}`"
        ),
        (
            "- Mean correctly assigned molecule fraction: "
            f"`{metrics.mean_correctly_assigned_molecule_fraction:.6f}`"
        ),
        f"- Boundary precision: `{_optional_number(metrics.boundary_precision)}`",
        f"- Boundary recall: `{_optional_number(metrics.boundary_recall)}`",
        (
            "- Mean confidence Brier score: "
            f"`{_optional_number(metrics.mean_confidence_brier_score)}`"
        ),
        (
            "- Mean confidence ECE: "
            f"`{_optional_number(metrics.mean_confidence_expected_calibration_error)}`"
        ),
        (
            "- Mean partition stability ARI: "
            f"`{_optional_number(metrics.mean_partition_stability_ari)}`"
        ),
        f"- Over-segmentation count: `{metrics.over_segmentation_count}`",
        f"- Under-segmentation count: `{metrics.under_segmentation_count}`",
    ]


def _metric_ari(
    metrics: LatticeDomainCalibrationAggregateMetrics | None,
) -> str:
    return (
        "n/a"
        if metrics is None
        else f"{metrics.mean_adjusted_rand_index:.4f}"
    )


def _optional_number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _frame_numbers(indices: tuple[int, ...]) -> str:
    return ", ".join(str(value + 1) for value in indices)
