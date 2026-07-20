from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import json
from itertools import combinations
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from moltrack.analysis import (
    M6DomainTypeAnalysisStore,
    M6DomainTypeClassificationResult,
    M6DomainTypeClassificationSettings,
    MolecularFrameRange,
    MolecularFrameRangeSelection,
    TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET,
    adapt_m6_domain_type_analysis_source,
    compare_molecular_frame_ranges,
)
from moltrack.analysis.m6_domain_type_similarity import (
    compute_m6_domain_type_distance,
)
from moltrack.core import build_moltrack_expanded_aligned_stack
from moltrack.persistence import (
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
)
from moltrack.visualization.m6_domain_type_colors import (
    M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR,
    m6_domain_type_color,
)


def build_tolerance_sweep(
    baseline: M6DomainTypeClassificationSettings,
) -> dict[str, M6DomainTypeClassificationSettings]:
    """Return small, isolated perturbations around the analytical defaults."""

    if not isinstance(baseline, M6DomainTypeClassificationSettings):
        raise TypeError("baseline must be M6DomainTypeClassificationSettings.")
    return {
        "baseline": baseline,
        "orientation_narrow": replace(
            baseline,
            orientation_tolerance_deg=baseline.orientation_tolerance_deg * 0.9,
        ),
        "orientation_wide": replace(
            baseline,
            orientation_tolerance_deg=baseline.orientation_tolerance_deg * 1.1,
        ),
        "bond_length_narrow": replace(
            baseline,
            bond_length_tolerance_value=baseline.bond_length_tolerance_value * 0.9,
        ),
        "bond_length_wide": replace(
            baseline,
            bond_length_tolerance_value=baseline.bond_length_tolerance_value * 1.1,
        ),
    }


def build_classification_summary(
    classification: M6DomainTypeClassificationResult,
) -> dict[str, object]:
    """Build auditable separation and representative-domain diagnostics."""

    if not isinstance(classification, M6DomainTypeClassificationResult):
        raise TypeError("classification must be an M6 domain type classification.")
    assignment_by_key = {
        assignment.observation_key: assignment
        for assignment in classification.assignments
    }
    representatives = []
    for domain_type in classification.domain_types:
        assigned = tuple(
            observation
            for observation in classification.observations
            if assignment_by_key[observation.stable_key].domain_type_id
            == domain_type.domain_type_id
        )
        candidates = tuple(
            (
                observation,
                compute_m6_domain_type_distance(
                    observation.orientation_deg,
                    observation.domain_median_bond_length_nm,
                    domain_type.prototype_orientation_deg,
                    domain_type.prototype_bond_length_nm,
                    settings=classification.classification_settings,
                ).normalized_distance,
            )
            for observation in assigned
        )
        representative, distance = min(
            candidates,
            key=lambda value: (value[1], value[0].stable_key),
        )
        representatives.append({
            "type_id": domain_type.domain_type_id,
            "type_label": domain_type.label,
            "frame_index": representative.frame_index,
            "source_frame_index": representative.source_frame_index,
            "range_name": representative.range_name,
            "ordered_component_id": representative.ordered_component_id,
            "orientation_deg": representative.orientation_deg,
            "median_bond_length_nm": representative.domain_median_bond_length_nm,
            "molecule_count": representative.molecule_count,
            "centroid_nm": [
                representative.centroid_x_nm,
                representative.centroid_y_nm,
            ],
            "normalized_distance_to_prototype": distance,
        })

    prototype_distances = tuple(
        compute_m6_domain_type_distance(
            left.prototype_orientation_deg,
            left.prototype_bond_length_nm,
            right.prototype_orientation_deg,
            right.prototype_bond_length_nm,
            settings=classification.classification_settings,
        ).normalized_distance
        for left, right in combinations(classification.domain_types, 2)
    )
    return {
        "observation_count": classification.observation_count,
        "classified_observation_count": classification.classified_observation_count,
        "unclassified_observation_count": classification.unclassified_observation_count,
        "domain_type_count": len(classification.domain_types),
        "minimum_normalized_prototype_distance": (
            min(prototype_distances) if prototype_distances else None
        ),
        "domain_types": [
            {
                "type_id": value.domain_type_id,
                "type_label": value.label,
                "prototype_orientation_deg": value.prototype_orientation_deg,
                "prototype_bond_length_nm": value.prototype_bond_length_nm,
                "observation_count": value.observation_count,
            }
            for value in classification.domain_types
        ],
        "representative_domains": representatives,
        "unclassified_reason_counts": dict(
            classification.qc_report.unclassified_reason_counts
        ),
    }


def compare_classification_partitions(
    reference: M6DomainTypeClassificationResult,
    candidate: M6DomainTypeClassificationResult,
) -> dict[str, int | float | None]:
    """Compare classifications without assuming stable type labels."""

    for name, value in (("reference", reference), ("candidate", candidate)):
        if not isinstance(value, M6DomainTypeClassificationResult):
            raise TypeError(f"{name} must be an M6 domain type classification.")
    reference_assignments = {
        value.observation_key: value for value in reference.assignments
    }
    candidate_assignments = {
        value.observation_key: value for value in candidate.assignments
    }
    shared_keys = tuple(sorted(
        set(reference_assignments).intersection(candidate_assignments)
    ))
    if not shared_keys:
        return {
            "shared_observation_count": 0,
            "classification_status_agreement_percent": None,
            "jointly_classified_observation_count": 0,
            "classified_pair_partition_agreement_percent": None,
        }

    status_matches = sum(
        reference_assignments[key].status == candidate_assignments[key].status
        for key in shared_keys
    )
    jointly_classified = tuple(
        key for key in shared_keys
        if reference_assignments[key].status == "classified"
        and candidate_assignments[key].status == "classified"
    )
    pair_total = _pair_count(len(jointly_classified))
    if pair_total:
        contingency = Counter(
            (
                reference_assignments[key].domain_type_id,
                candidate_assignments[key].domain_type_id,
            )
            for key in jointly_classified
        )
        reference_sizes = Counter(
            reference_assignments[key].domain_type_id
            for key in jointly_classified
        )
        candidate_sizes = Counter(
            candidate_assignments[key].domain_type_id
            for key in jointly_classified
        )
        same_in_both = sum(_pair_count(value) for value in contingency.values())
        same_in_reference = sum(
            _pair_count(value) for value in reference_sizes.values()
        )
        same_in_candidate = sum(
            _pair_count(value) for value in candidate_sizes.values()
        )
        different_in_both = (
            pair_total - same_in_reference - same_in_candidate + same_in_both
        )
        pair_agreement = 100.0 * (same_in_both + different_in_both) / pair_total
    else:
        pair_agreement = None
    return {
        "shared_observation_count": len(shared_keys),
        "classification_status_agreement_percent": (
            100.0 * status_matches / len(shared_keys)
        ),
        "jointly_classified_observation_count": len(jointly_classified),
        "classified_pair_partition_agreement_percent": pair_agreement,
    }


def _pair_count(count: int) -> int:
    return count * (count - 1) // 2


def validate_session(
    session_path: Path,
    output_dir: Path,
    *,
    m6_settings_source: str = "ttmapp-preset",
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Loading session: {session_path}", flush=True)
    session = load_moltrack_session(session_path)
    position = session.position_analysis
    m6_state = session.m6_analysis_state
    if position is None or m6_state is None or not m6_state.enabled:
        raise ValueError("Session must contain enabled M6 and Position Analysis state.")
    if m6_settings_source == "ttmapp-preset":
        m6_settings = TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET
    elif m6_settings_source == "session":
        m6_settings = m6_state.settings
    else:
        raise ValueError("m6_settings_source must be 'ttmapp-preset' or 'session'.")

    print("Restoring image series and cached structural analysis...", flush=True)
    series = restore_moltrack_image_series_from_session(session)
    if position.source_view == "expanded_aligned":
        build_moltrack_expanded_aligned_stack(series)
    selection = MolecularFrameRangeSelection(
        frame_count=series.frame_count,
        source_view=position.source_view,
        first_range=MolecularFrameRange(
            position.first_range.name,
            position.first_range.start_frame,
            position.first_range.end_frame,
        ),
        second_range=MolecularFrameRange(
            position.second_range.name,
            position.second_range.start_frame,
            position.second_range.end_frame,
        ),
    )

    def progress(completed: int, total: int, frame_index: int) -> None:
        print(
            f"M6 frame {completed}/{total} (working frame {frame_index + 1})",
            flush=True,
        )

    comparison = compare_molecular_frame_ranges(
        series,
        selection,
        use_segmentation_centroids=position.use_segmentation_centroids,
        intensity_metric=position.intensity_metric,
        background_inner_radius_px=position.background_inner_radius_px,
        background_outer_radius_px=position.background_outer_radius_px,
        progress_callback=progress,
        m6_orientation_settings=m6_settings,
    )
    source = adapt_m6_domain_type_analysis_source(
        comparison,
        frame_count=series.frame_count,
    )
    sweep = build_tolerance_sweep(M6DomainTypeClassificationSettings())
    run_results = {}
    baseline_classification = None
    for name, settings in sweep.items():
        print(f"Classifying tolerance variant: {name}", flush=True)
        started = time.perf_counter()
        outcome = M6DomainTypeAnalysisStore().analyze(
            source,
            classification_settings=settings,
        )
        elapsed = time.perf_counter() - started
        if outcome.classification is None:
            raise RuntimeError(f"Variant {name} did not produce a classification.")
        if name == "baseline":
            baseline_classification = outcome.classification
        run_results[name] = {
            "settings": settings.to_dict(),
            "elapsed_seconds": elapsed,
            "summary": build_classification_summary(outcome.classification),
        }
        run_results[name]["stability_vs_baseline"] = (
            compare_classification_partitions(
                baseline_classification,
                outcome.classification,
            )
        )
    assert baseline_classification is not None

    scatter_path = _export_scatter_plot(
        baseline_classification,
        output_dir / "plots" / "domain_type_scatter.png",
    )
    representative_files = _export_representative_overlays(
        series,
        comparison,
        baseline_classification,
        run_results["baseline"]["summary"]["representative_domains"],
        output_dir / "representatives",
    )
    report = {
        "validation_id": "m6-domain-types-ttmapp-step-83.3",
        "source_session": str(session_path.resolve()),
        "source_mpp": session.source_path,
        "source_view": position.source_view,
        "use_segmentation_centroids": position.use_segmentation_centroids,
        "ranges": [
            {
                "name": value.name,
                "working_start_frame_1_based": value.start_frame + 1,
                "working_end_frame_1_based": value.end_frame + 1,
            }
            for value in (position.first_range, position.second_range)
        ],
        "m6_settings_source": m6_settings_source,
        "m6_settings": m6_settings.to_dict(),
        "classification_runs": run_results,
        "generated_plots": [str(scatter_path)],
        "representative_overlays": representative_files,
        "preset_modified": False,
        "manual_review": {
            "status": "pending_visual_review",
            "scatter": "Open plots/domain_type_scatter.png.",
            "representatives": "Open every PNG in representatives/.",
        },
    }
    (output_dir / "validation_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "validation_report.md").write_text(
        _markdown_report(report),
        encoding="utf-8",
    )
    return report


def _export_representative_overlays(
    series,
    comparison,
    classification,
    representatives,
    destination: Path,
) -> list[str]:
    from PIL import Image, ImageDraw

    destination.mkdir(parents=True, exist_ok=True)
    assignment_by_key = {
        value.observation_key: value for value in classification.assignments
    }
    frame_results = {
        result.frame_index: result
        for analysis in (comparison.first_analysis, comparison.second_analysis)
        for result in analysis.frame_results
        if result.m6_orientation_analysis is not None
    }
    files = []
    for representative in representatives:
        frame_index = representative["frame_index"]
        frame_result = frame_results[frame_index]
        analysis = frame_result.m6_orientation_analysis
        component_by_id = {
            value.ordered_component_id: value
            for value in analysis.frame_aggregates.domain_metrics.components
        }
        point_by_source_id = dict(zip(
            analysis.sample_coordinates.point_source_ids,
            analysis.sample_coordinates.source_points_xy_px,
        ))
        frame_points = []
        for observation in classification.observations:
            if observation.frame_index != frame_index:
                continue
            assignment = assignment_by_key[observation.stable_key]
            color = (
                m6_domain_type_color(assignment.domain_type_id)[:3]
                if assignment.status == "classified"
                else M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR[:3]
            )
            component = component_by_id[observation.ordered_component_id]
            selected = (
                observation.ordered_component_id
                == representative["ordered_component_id"]
            )
            frame_points.extend(
                (source_id, point_by_source_id[source_id], color, selected)
                for source_id in component.source_ids
            )
        image = (
            series.raw_frames[frame_index]
            if classification.analysis_scope.source_view == "raw"
            else series.expanded_aligned_stack.frames[frame_index]
        )
        canvas = Image.fromarray(_normalize_image_to_uint8(image)).convert("RGB")
        draw = ImageDraw.Draw(canvas)
        for _source_id, point, color, selected in frame_points:
            radius = 5 if selected else 2
            x, y = (float(value) for value in point)
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                fill=tuple(color),
                outline=(255, 255, 255) if selected else None,
                width=2 if selected else 1,
            )
        path = destination / f"type_{representative['type_label']}_representative.png"
        canvas.save(path)
        files.append(str(path))
    return files


def _normalize_image_to_uint8(image):
    import numpy as np

    values = np.asarray(image, dtype=np.float64)
    finite_mask = np.isfinite(values)
    normalized = np.zeros(values.shape, dtype=np.float64)
    if not np.any(finite_mask):
        return np.zeros(values.shape, dtype=np.uint8)
    low, high = np.percentile(values[finite_mask], (1.0, 99.0))
    normalized[finite_mask] = np.clip(
        (values[finite_mask] - low) / max(high - low, 1e-12),
        0.0,
        1.0,
    )
    return np.uint8(normalized * 255)


def _export_scatter_plot(
    classification: M6DomainTypeClassificationResult,
    path: Path,
) -> Path:
    from PIL import Image, ImageDraw

    path.parent.mkdir(parents=True, exist_ok=True)
    width, height, margin = 1200, 800, 80
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.line((margin, height - margin, width - margin, height - margin), fill="black", width=2)
    draw.line((margin, margin, margin, height - margin), fill="black", width=2)
    bond_lengths = tuple(
        value.domain_median_bond_length_nm
        for value in classification.observations
        if value.domain_median_bond_length_nm is not None
    )
    if not bond_lengths:
        draw.text((margin + 20, margin + 20), "No domain observations", fill="black")
        canvas.save(path)
        return path
    bond_min = min(bond_lengths)
    bond_max = max(bond_lengths)
    bond_span = max(bond_max - bond_min, 1e-12)
    assignment_by_key = {
        value.observation_key: value for value in classification.assignments
    }
    for observation in classification.observations:
        bond_length = observation.domain_median_bond_length_nm
        if bond_length is None:
            continue
        assignment = assignment_by_key[observation.stable_key]
        color = (
            m6_domain_type_color(assignment.domain_type_id)[:3]
            if assignment.status == "classified"
            else M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR[:3]
        )
        x = margin + (observation.orientation_deg % 60.0) / 60.0 * (width - 2 * margin)
        y = height - margin - (bond_length - bond_min) / bond_span * (height - 2 * margin)
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=tuple(color))
    draw.text((width // 2 - 90, height - 40), "M6 orientation [deg]", fill="black")
    draw.text((10, 20), "Median bond length [nm]", fill="black")
    canvas.save(path)
    return path


def _markdown_report(report: dict[str, object]) -> str:
    lines = [
        "# TTMAPP M6 domain-type validation (step 83.3)",
        "",
        f"- Session: `{report['source_session']}`",
        f"- Source view: `{report['source_view']}`",
        f"- Segmentation centroids: `{report['use_segmentation_centroids']}`",
        f"- M6 settings source: `{report['m6_settings_source']}`",
        "- Preset modified: `false`",
        "",
        "## Tolerance runs",
        "",
        "| Run | Orientation [deg] | Bond tolerance | Types | Observations | Unclassified | Status agreement | Partition agreement |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    runs = report["classification_runs"]
    for name, run in runs.items():
        settings = run["settings"]
        summary = run["summary"]
        stability = run["stability_vs_baseline"]
        lines.append(
            f"| {name} | {settings['orientation_tolerance_deg']:.3g} | "
            f"{settings['bond_length_tolerance_value']:.3g} "
            f"{settings['bond_length_tolerance_mode']} | {summary['domain_type_count']} | "
            f"{summary['observation_count']} | {summary['unclassified_observation_count']} | "
            f"{_percent(stability['classification_status_agreement_percent'])} | "
            f"{_percent(stability['classified_pair_partition_agreement_percent'])} |"
        )
    lines.extend([
        "",
        "## Representative domains",
        "",
        "| Type | Working frame | Source frame | Component | Orientation [deg] | Bond length [nm] | Molecules |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    representatives = runs["baseline"]["summary"]["representative_domains"]
    for value in representatives:
        lines.append(
            f"| {value['type_label']} | {value['frame_index'] + 1} | "
            f"{value['source_frame_index'] + 1} | {value['ordered_component_id']} | "
            f"{value['orientation_deg']:.3f} | {value['median_bond_length_nm']:.3f} | "
            f"{value['molecule_count']} |"
        )
    lines.extend([
        "",
        "## Visual review",
        "",
        "Status: `pending_visual_review`. Review the scatter and every representative overlay, then document the conclusion here. Tolerances are not copied to the TTMAPP preset automatically.",
        "",
    ])
    return "\n".join(lines)


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}%"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate M6 domain types on a saved TTMAPP session.",
    )
    parser.add_argument("session", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument(
        "--m6-settings",
        choices=("ttmapp-preset", "session"),
        default="ttmapp-preset",
        help="Use the validated TTMAPP preset or settings stored in the session.",
    )
    args = parser.parse_args()
    validate_session(
        args.session,
        args.output_dir,
        m6_settings_source=args.m6_settings,
    )
    print(f"Validation report: {args.output_dir / 'validation_report.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
