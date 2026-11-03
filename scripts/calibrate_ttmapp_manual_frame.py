"""Diagnose and tune one TTMAPP lattice-domain frame against colored outlines."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import replace
from itertools import product
from math import atan2, cos, degrees, radians, sin
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from moltrack.analysis import (  # noqa: E402
    LatticeDomainPartitionLabels,
    MolecularFrameRange,
    TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET,
    analyze_molecular_frame_range,
    analyze_molecular_m6_orientation,
    evaluate_lattice_domain_partition,
    lattice_domain_partition_labels_from_analysis,
)
from moltrack.core import build_moltrack_expanded_aligned_stack  # noqa: E402
from moltrack.persistence import (  # noqa: E402
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
)
from render_ttmapp_frame_domains import _render  # noqa: E402


REGION_COLORS = {
    "BLACK": (0, 0, 0),
    "RED": (255, 30, 30),
    "YELLOW": (255, 225, 0),
}


def _outline_masks(
    clean_path: Path,
    manual_path: Path,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    clean = np.asarray(Image.open(clean_path).convert("RGB"), dtype=np.int16)
    manual = np.asarray(Image.open(manual_path).convert("RGB"), dtype=np.int16)
    if clean.shape != manual.shape:
        raise ValueError("Clean and manually annotated images must have equal dimensions.")
    red = (
        (manual[:, :, 0] > 150)
        & (manual[:, :, 0] > manual[:, :, 1] * 1.55)
        & (manual[:, :, 0] > manual[:, :, 2] * 1.55)
    )
    yellow = (
        (manual[:, :, 0] > 150)
        & (manual[:, :, 1] > 120)
        & (manual[:, :, 2] < 130)
        & (np.abs(manual[:, :, 0] - manual[:, :, 1]) < 130)
    )
    clean_gray = np.mean(clean, axis=2)
    manual_gray = np.mean(manual, axis=2)
    black = (
        (np.max(manual, axis=2) < 100)
        & ((clean_gray - manual_gray) > 3)
    )
    outlines = {"BLACK": black, "RED": red, "YELLOW": yellow}
    regions = {}
    for name, outline in outlines.items():
        closed = ndimage.binary_closing(
            ndimage.binary_dilation(outline, iterations=2),
            iterations=6,
        )
        filled = ndimage.binary_fill_holes(closed)
        labels, count = ndimage.label(filled)
        if count == 0:
            raise ValueError(f"No {name.lower()} manual outline was found.")
        sizes = ndimage.sum(filled, labels, range(1, count + 1))
        selected = int(np.argmax(sizes)) + 1
        region = labels == selected
        if int(np.count_nonzero(region)) < 100:
            raise ValueError(f"The {name.lower()} outline does not enclose a region.")
        regions[name] = region
    return outlines, regions


def _reference_labels(
    sample,
    regions: dict[str, np.ndarray],
    *,
    image_shape: tuple[int, int],
    source_image_shape: tuple[int, int],
) -> tuple[LatticeDomainPartitionLabels, dict[str, tuple[int, ...]], tuple[int, ...]]:
    height, width = image_shape
    source_height, source_width = source_image_shape
    scale_x = width / float(source_width)
    scale_y = height / float(source_height)
    selected_by_region: dict[str, list[int]] = {name: [] for name in regions}
    ambiguous = []
    for index, (x, y) in enumerate(sample.source_points_xy_px):
        px = min(width - 1, max(0, int(round(float(x) * scale_x))))
        py = min(height - 1, max(0, int(round(float(y) * scale_y))))
        membership = [
            name for name, region in regions.items() if bool(region[py, px])
        ]
        if len(membership) == 1:
            selected_by_region[membership[0]].append(index)
        elif len(membership) > 1:
            ambiguous.append(index)
    selected_indices = tuple(
        sorted(index for values in selected_by_region.values() for index in values)
    )
    label_by_index = {
        index: name
        for name, values in selected_by_region.items()
        for index in values
    }
    reference = LatticeDomainPartitionLabels(
        source_ids=tuple(sample.point_source_ids[index] for index in selected_indices),
        domain_labels=tuple(label_by_index[index] for index in selected_indices),
        boundary=(False,) * len(selected_indices),
        confidence=(1.0,) * len(selected_indices),
    )
    return (
        reference,
        {name: tuple(values) for name, values in selected_by_region.items()},
        tuple(ambiguous),
    )


def _subset_prediction(
    analysis,
    source_ids: tuple[str, ...],
) -> LatticeDomainPartitionLabels:
    prediction = lattice_domain_partition_labels_from_analysis(
        analysis.lattice_domain_analysis
    )
    row_by_id = dict(
        zip(
            prediction.source_ids,
            zip(
                prediction.domain_labels,
                prediction.boundary,
                prediction.confidence,
            ),
        )
    )
    return LatticeDomainPartitionLabels(
        source_ids=source_ids,
        domain_labels=tuple(row_by_id[source_id][0] for source_id in source_ids),
        boundary=tuple(row_by_id[source_id][1] for source_id in source_ids),
        confidence=tuple(row_by_id[source_id][2] for source_id in source_ids),
    )


def _periodic_summary(
    values: tuple[float | None, ...],
    *,
    period: float,
) -> dict[str, float | int | None]:
    finite = tuple(float(value) for value in values if value is not None)
    if not finite:
        return {"count": 0, "mean_deg": None, "spread_deg": None}
    angles = tuple(2.0 * np.pi * value / period for value in finite)
    mean_x = sum(cos(value) for value in angles) / len(angles)
    mean_y = sum(sin(value) for value in angles) / len(angles)
    mean = (degrees(atan2(mean_y, mean_x)) % 360.0) * period / 360.0
    differences = tuple(
        abs(((value - mean + period / 2.0) % period) - period / 2.0)
        for value in finite
    )
    return {
        "count": len(finite),
        "mean_deg": mean,
        "spread_deg": float(np.median(differences)),
    }


def _region_diagnostics(
    analysis,
    indices_by_region: dict[str, tuple[int, ...]],
) -> dict[str, object]:
    local = analysis.local_multisymmetry_order
    evidence = analysis.local_symmetry_evidence
    result = {}
    for name, indices in indices_by_region.items():
        q3_values = tuple(
            float(local.q3[index])
            for index in indices
            if local.q3[index] is not None
        )
        q6_values = tuple(
            float(local.q6[index])
            for index in indices
            if local.q6[index] is not None
        )
        result[name] = {
            "molecule_count": len(indices),
            "q3_median": None if not q3_values else float(np.median(q3_values)),
            "q6_median": None if not q6_values else float(np.median(q6_values)),
            "theta3_lattice": _periodic_summary(
                tuple(local.theta3_lattice_deg[index] for index in indices),
                period=60.0,
            ),
            "theta6": _periodic_summary(
                tuple(local.theta6_deg[index] for index in indices),
                period=60.0,
            ),
            "symmetry_evidence": dict(
                Counter(evidence.best_model[index] for index in indices)
            ),
        }
    return result


def _extracted_region_overlay(
    clean_path: Path,
    regions: dict[str, np.ndarray],
    destination: Path,
) -> None:
    image = Image.open(clean_path).convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    values = np.zeros((image.height, image.width, 4), dtype=np.uint8)
    for name, region in regions.items():
        color = REGION_COLORS[name]
        values[region] = (*color, 65 if name != "BLACK" else 85)
    layer = Image.fromarray(values, mode="RGBA")
    Image.alpha_composite(image, layer).convert("RGB").save(destination)


def _manual_reference_overlay(
    clean_path: Path,
    sample,
    indices_by_region: dict[str, tuple[int, ...]],
    destination: Path,
    *,
    source_image_shape: tuple[int, int],
) -> None:
    image = Image.open(clean_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    source_height, source_width = source_image_shape
    scale_x = image.width / float(source_width)
    scale_y = image.height / float(source_height)
    for name, indices in indices_by_region.items():
        color = REGION_COLORS[name]
        for index in indices:
            x, y = sample.source_points_xy_px[index]
            x, y = float(x) * scale_x, float(y) * scale_y
            radius = 5
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                fill=color,
                outline="white",
                width=2,
            )
    try:
        label_font = ImageFont.truetype("DejaVuSans.ttf", 18)
    except OSError:
        label_font = ImageFont.load_default()
    y = 15
    for name, indices in indices_by_region.items():
        draw.text(
            (15, y),
            f"{name}: {len(indices)} molecules",
            fill=REGION_COLORS[name],
            stroke_width=2,
            stroke_fill="white",
            font=label_font,
        )
        y += 25
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)


def _sweep_settings():
    baseline = TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET
    profiles = (
        {
            "profile": "baseline",
            "q_seed": 0.65,
            "q_grow": 0.25,
            "local_symmetry_sixfold_minimum_model_score": 0.50,
            "lattice_seed_min_model_score": 0.65,
            "lattice_halo_min_model_score": 0.25,
            "min_neighbors_for_seed": 5,
            "min_seed_size": 5,
            "min_domain_size": 12,
        },
        {
            "profile": "moderate",
            "q_seed": 0.55,
            "q_grow": 0.20,
            "local_symmetry_sixfold_minimum_model_score": 0.45,
            "lattice_seed_min_model_score": 0.55,
            "lattice_halo_min_model_score": 0.20,
            "min_neighbors_for_seed": 4,
            "min_seed_size": 4,
            "min_domain_size": 8,
        },
        {
            "profile": "loose",
            "q_seed": 0.45,
            "q_grow": 0.15,
            "local_symmetry_sixfold_minimum_model_score": 0.40,
            "lattice_seed_min_model_score": 0.45,
            "lattice_halo_min_model_score": 0.15,
            "min_neighbors_for_seed": 3,
            "min_seed_size": 3,
            "min_domain_size": 6,
        },
    )
    seen = set()
    for profile, edge, seed_spread, grow_spread in product(
        profiles,
        (2.0, 4.0, 6.0, 8.0),
        (4.0, 8.0),
        (4.0, 8.0, 12.0),
    ):
        settings = replace(
            baseline,
            q_seed=profile["q_seed"],
            q_grow=profile["q_grow"],
            local_symmetry_sixfold_minimum_model_score=(
                profile["local_symmetry_sixfold_minimum_model_score"]
            ),
            lattice_edge_sixfold_orientation_tolerance_deg=edge,
            lattice_seed_min_model_score=profile["lattice_seed_min_model_score"],
            lattice_halo_min_model_score=profile["lattice_halo_min_model_score"],
            min_neighbors_for_seed=profile["min_neighbors_for_seed"],
            min_seed_size=profile["min_seed_size"],
            seed_angle_tolerance_deg=seed_spread,
            grow_angle_tolerance_deg=grow_spread,
            min_domain_size=profile["min_domain_size"],
        )
        if settings in seen:
            continue
        seen.add(settings)
        yield profile["profile"], settings


def _evaluate_sweep(sample, reference, *, progress_every: int = 25):
    rows = []
    best = None
    variants = tuple(_sweep_settings())
    total = len(variants)
    for variant_index, (profile, settings) in enumerate(variants, start=1):
        analysis = analyze_molecular_m6_orientation(sample, settings=settings)
        prediction = _subset_prediction(analysis, reference.source_ids)
        report = evaluate_lattice_domain_partition(prediction, reference)
        score = (
            report.adjusted_rand_index
            + 0.5 * float(report.correctly_assigned_molecule_fraction or 0.0)
            - 0.08 * abs(report.domain_count_error)
            - 0.03 * (
                report.over_segmentation_count + report.under_segmentation_count
            )
        )
        row = {
            "variant_index": variant_index,
            "profile": profile,
            "score": score,
            "adjusted_rand_index": report.adjusted_rand_index,
            "correctly_assigned_molecule_fraction": (
                report.correctly_assigned_molecule_fraction
            ),
            "predicted_domain_count": report.predicted_domain_count,
            "domain_count_error": report.domain_count_error,
            "over_segmentation_count": report.over_segmentation_count,
            "under_segmentation_count": report.under_segmentation_count,
            "q_seed": settings.q_seed,
            "q_grow": settings.q_grow,
            "local_symmetry_sixfold_minimum_model_score": (
                settings.local_symmetry_sixfold_minimum_model_score
            ),
            "lattice_edge_sixfold_orientation_tolerance_deg": (
                settings.lattice_edge_sixfold_orientation_tolerance_deg
            ),
            "lattice_seed_min_model_score": settings.lattice_seed_min_model_score,
            "lattice_halo_min_model_score": settings.lattice_halo_min_model_score,
            "min_neighbors_for_seed": settings.min_neighbors_for_seed,
            "min_seed_size": settings.min_seed_size,
            "seed_angle_tolerance_deg": settings.seed_angle_tolerance_deg,
            "grow_angle_tolerance_deg": settings.grow_angle_tolerance_deg,
            "min_domain_size": settings.min_domain_size,
        }
        rows.append(row)
        rank = (
            score,
            report.adjusted_rand_index,
            float(report.correctly_assigned_molecule_fraction or 0.0),
            -abs(report.domain_count_error),
            -variant_index,
        )
        if best is None or rank > best[0]:
            best = (rank, settings, analysis, row)
        if variant_index % progress_every == 0:
            print(f"Evaluated {variant_index}/{total} variants...", flush=True)
    assert best is not None
    return rows, best


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("clean_image", type=Path)
    parser.add_argument("manual_image", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--frame", type=int, default=255)
    parser.add_argument(
        "--centroid-mode",
        choices=("mask", "bbox"),
        default="mask",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame_index = args.frame - 1
    print(f"Loading snapshot: {args.snapshot}", flush=True)
    session = load_moltrack_session(args.snapshot)
    series = restore_moltrack_image_series_from_session(session)
    source_view = session.position_analysis.source_view
    if source_view == "expanded_aligned":
        build_moltrack_expanded_aligned_stack(series)
        frame_image = series.expanded_aligned_stack.frames[frame_index]
    else:
        frame_image = series.raw_frames[frame_index]
    use_masks = args.centroid_mode == "mask"
    baseline_result = analyze_molecular_frame_range(
        series,
        MolecularFrameRange(f"frame {args.frame}", frame_index, frame_index),
        source_view=source_view,
        use_segmentation_centroids=use_masks,
        m6_orientation_settings=TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET,
    ).frame_results[0]
    baseline = baseline_result.m6_orientation_analysis
    if baseline is None:
        raise RuntimeError("Baseline analysis is unavailable.")

    outlines, regions = _outline_masks(args.clean_image, args.manual_image)
    _extracted_region_overlay(
        args.clean_image,
        regions,
        args.output_dir / f"frame_{args.frame}_extracted_manual_regions.png",
    )
    manual_shape = np.asarray(Image.open(args.manual_image)).shape[:2]
    reference, indices_by_region, ambiguous = _reference_labels(
        baseline.sample_coordinates,
        regions,
        image_shape=manual_shape,
        source_image_shape=frame_image.shape[:2],
    )
    if any(not indices for indices in indices_by_region.values()):
        raise ValueError("Every manual region must contain at least one centroid.")
    print(
        "Manual region molecule counts: "
        + ", ".join(f"{name}={len(indices)}" for name, indices in indices_by_region.items()),
        flush=True,
    )
    print(f"Ambiguous overlap points excluded: {len(ambiguous)}", flush=True)
    _manual_reference_overlay(
        args.clean_image,
        baseline.sample_coordinates,
        indices_by_region,
        args.output_dir / f"frame_{args.frame}_{args.centroid_mode}_manual_reference.png",
        source_image_shape=frame_image.shape[:2],
    )

    baseline_prediction = _subset_prediction(baseline, reference.source_ids)
    baseline_report = evaluate_lattice_domain_partition(
        baseline_prediction,
        reference,
    )
    diagnostics = _region_diagnostics(baseline, indices_by_region)
    print(json.dumps(diagnostics, indent=2), flush=True)
    print("Baseline:", json.dumps(baseline_report.__dict__, indent=2), flush=True)
    print("Running bounded 72-variant sweep...", flush=True)
    rows, best = _evaluate_sweep(baseline.sample_coordinates, reference)
    _rank, best_settings, best_analysis, best_row = best
    rows.sort(
        key=lambda row: (
            -float(row["score"]),
            -float(row["adjusted_rand_index"]),
            int(row["variant_index"]),
        )
    )
    csv_path = args.output_dir / f"frame_{args.frame}_{args.centroid_mode}_sweep.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    _render(
        frame_image,
        best_analysis,
        args.output_dir / f"frame_{args.frame}_{args.centroid_mode}_best_domains.png",
        frame_number=args.frame,
        centroid_label=f"{args.centroid_mode} centroids, tuned candidate",
    )
    report = {
        "status": "single_frame_experimental_candidate",
        "frame_number_1_based": args.frame,
        "working_frame_index": frame_index,
        "centroid_mode": args.centroid_mode,
        "manual_region_counts": {
            name: len(indices) for name, indices in indices_by_region.items()
        },
        "reference_scope": (
            "Only molecules inside the three colored example regions are scored. "
            "Domains and detections elsewhere in the frame are intentionally ignored."
        ),
        "ambiguous_overlap_point_count": len(ambiguous),
        "baseline_validation": baseline_report.__dict__,
        "baseline_region_diagnostics": diagnostics,
        "best_variant": best_row,
        "best_settings": best_settings.to_dict(),
        "variant_count": len(rows),
        "caveat": (
            "This is a one-frame candidate without an independent holdout. "
            "It must not be promoted to a validated TTMAPP preset."
        ),
    }
    (args.output_dir / f"frame_{args.frame}_{args.centroid_mode}_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    print("Baseline:", json.dumps(baseline_report.__dict__, indent=2), flush=True)
    print("Best:", json.dumps(best_row, indent=2), flush=True)
    print(f"Output: {args.output_dir.resolve()}", flush=True)


if __name__ == "__main__":
    main()
