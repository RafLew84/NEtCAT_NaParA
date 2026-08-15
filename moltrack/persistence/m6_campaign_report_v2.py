"""Atomic publication for the complete M6 campaign report v2."""

from __future__ import annotations

import csv
from dataclasses import asdict
import json
from pathlib import Path
import tempfile

from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256
from moltrack.analysis.m6_validation_campaign_models import (
    M6CampaignReportV2,
    M6CampaignReportV2Publication,
)

from .package_io import csv_json_cell, publish_path, remove_path


_REPORT_JSON = "m6_campaign_report_v2.json"
_REPORT_MARKDOWN = "m6_campaign_report_v2.md"
_METRICS_CSV = "m6_validation_metrics.csv"
_RECEIPT_JSON = "validation_access_receipt.json"


def publish_m6_campaign_report_v2(
    report: M6CampaignReportV2,
    destination: str | Path,
) -> M6CampaignReportV2Publication:
    """Stage every artifact, then expose one immutable report directory."""

    if not isinstance(report, M6CampaignReportV2):
        raise TypeError("report must be an M6CampaignReportV2.")
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    run_name = f"m6-campaign-report-v2-{report.receipt.access_fingerprint[:16]}"
    final_directory = root / run_name
    staging_directory = Path(tempfile.mkdtemp(prefix=f".{run_name}-", dir=root))
    try:
        payload = _report_payload(report)
        paths = _paths(staging_directory)
        paths["json"].write_text(
            json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )
        paths["markdown"].write_text(
            _markdown(report, str(payload["report_fingerprint"])),
            encoding="utf-8",
        )
        _write_metrics_csv(report, paths["metrics_csv"])
        paths["receipt"].write_text(
            json.dumps(
                asdict(report.receipt),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        publish_path(staging_directory, final_directory, overwrite=False)
    except BaseException:
        remove_path(staging_directory)
        raise
    final_paths = _paths(final_directory)
    return M6CampaignReportV2Publication(
        report=report,
        output_directory=final_directory,
        report_json_path=final_paths["json"],
        report_markdown_path=final_paths["markdown"],
        metrics_csv_path=final_paths["metrics_csv"],
        receipt_path=final_paths["receipt"],
    )


def _report_payload(report: M6CampaignReportV2) -> dict[str, object]:
    payload = asdict(report)
    payload["shortlist"] = payload.pop("calibration_shortlist")
    payload["validation_access_receipt"] = payload.pop("receipt")
    payload["report_fingerprint"] = canonical_sha256(payload)
    return payload


def _paths(directory: Path) -> dict[str, Path]:
    return {
        "json": directory / _REPORT_JSON,
        "markdown": directory / _REPORT_MARKDOWN,
        "metrics_csv": directory / _METRICS_CSV,
        "receipt": directory / _RECEIPT_JSON,
    }


def _write_metrics_csv(report: M6CampaignReportV2, path: Path) -> None:
    field_names = (
        "backend_id",
        "candidate_fingerprint",
        "measurement_group_id",
        "passed_constraints",
        "objective_loss",
        "membership_precision",
        "membership_recall",
        "adjusted_rand_index",
        "variation_of_information_nats",
        "split_rate",
        "merge_rate",
        "boundary_precision",
        "boundary_recall",
        "funnel_misses",
    )
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=field_names)
        writer.writeheader()
        for result in report.validation_results:
            for metrics in result.group_metrics:
                writer.writerow({
                    "backend_id": result.backend_identity.backend_id,
                    "candidate_fingerprint": result.candidate_fingerprint,
                    "measurement_group_id": metrics.measurement_group_id,
                    "passed_constraints": result.passed_constraints,
                    "objective_loss": result.objective_loss,
                    "membership_precision": metrics.membership_precision,
                    "membership_recall": metrics.membership_recall,
                    "adjusted_rand_index": metrics.adjusted_rand_index,
                    "variation_of_information_nats": (
                        metrics.variation_of_information_nats
                    ),
                    "split_rate": metrics.split_rate,
                    "merge_rate": metrics.merge_rate,
                    "boundary_precision": csv_json_cell(
                        asdict(metrics.boundary_precision)
                    ),
                    "boundary_recall": csv_json_cell(
                        asdict(metrics.boundary_recall)
                    ),
                    "funnel_misses": csv_json_cell(metrics.funnel_misses),
                })


def _markdown(report: M6CampaignReportV2, fingerprint: str) -> str:
    recommendation = report.recommended_backend_id or "none"
    lines = [
        "# M6 campaign report v2",
        "",
        f"- Status: `{report.status}`",
        f"- Report fingerprint: `{fingerprint}`",
        f"- Dataset version: `{report.dataset_version_id}`",
        f"- Validation epoch: `{report.validation_epoch_id}`",
        f"- Geometry fingerprint: `{report.geometry_fingerprint}`",
        f"- Shortlist fingerprint: `{report.calibration_shortlist.shortlist_fingerprint}`",
        f"- Validation open count: `{report.receipt.open_count}`",
        f"- Recommended backend: `{recommendation}`",
        f"- Preset modified: `{str(report.preset_modified).lower()}`",
        "",
        "## Frozen Calibration shortlist",
        "",
    ]
    for entry in report.calibration_shortlist.entries:
        lines.append(
            f"- `{entry.backend_identity.backend_id}` / "
            f"`{entry.candidate.variant.variant_id}` / "
            f"loss `{entry.candidate.objective_loss}`"
        )
    lines.extend(["", "## Validation", ""])
    for result in report.validation_results:
        boundary = result.metrics.boundary_precision
        lines.extend([
            f"### {result.backend_identity.backend_id}",
            "",
            f"- Passed constraints: `{str(result.passed_constraints).lower()}`",
            f"- Objective loss: `{result.objective_loss}`",
            f"- Boundary capability: `{boundary.status}`"
            + ("" if boundary.reason is None else f" (`{boundary.reason}`)"),
            f"- Funnel misses: `{dict(result.metrics.funnel_misses)}`",
            "",
            "| Measurement group | Precision | Recall | ARI | Split/Merge | Funnel |",
            "|---|---:|---:|---:|---:|---|",
        ])
        for metrics in result.group_metrics:
            lines.append(
                f"| {metrics.measurement_group_id} | "
                f"{metrics.membership_precision} | {metrics.membership_recall} | "
                f"{metrics.adjusted_rand_index:.4f} | "
                f"{metrics.split_rate:.4f}/{metrics.merge_rate:.4f} | "
                f"{dict(metrics.funnel_misses)} |"
            )
        lines.append("")
    if report.failure_reason is not None:
        lines.extend(["## Validation failure", "", report.failure_reason, ""])
    return "\n".join(lines)


__all__ = ["publish_m6_campaign_report_v2"]
