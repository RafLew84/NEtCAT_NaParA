"""Compare molecular-orientation estimates inside manual TTMAPP regions."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from math import atan2, cos, degrees, radians, sin
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from calibrate_ttmapp_manual_frame import (  # noqa: E402
    _outline_masks,
    _reference_labels,
)
from moltrack.analysis import (  # noqa: E402
    MolecularFrameRange,
    TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET,
    analyze_molecular_frame_range,
    estimate_series_molecular_orientations,
)
from moltrack.core import build_moltrack_expanded_aligned_stack  # noqa: E402
from moltrack.persistence import (  # noqa: E402
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
)


COLORS = {
    "BLACK": (35, 35, 35),
    "RED": (240, 45, 40),
    "YELLOW": (245, 205, 0),
}


def _periodic_mean(values: list[float], period: float = 180.0) -> float | None:
    if not values:
        return None
    angles = [2.0 * np.pi * value / period for value in values]
    mean = degrees(
        atan2(
            sum(sin(value) for value in angles),
            sum(cos(value) for value in angles),
        )
    ) % 360.0
    return mean * period / 360.0


def _distance(left: float, right: float, period: float = 180.0) -> float:
    difference = abs(float(left) - float(right)) % period
    return min(difference, period - difference)


def _summary(values) -> dict[str, object]:
    available = [value for value in values if value.status == "available"]
    angles = [float(value.angle_deg) for value in available]
    mean = _periodic_mean(angles)
    distances = (
        []
        if mean is None
        else [_distance(value, mean) for value in angles]
    )
    spread = (
        None
        if mean is None
        else float(np.median(distances))
    )
    method_summaries = {}
    for method in sorted({value.method for value in values}):
        method_values = [value for value in values if value.method == method]
        method_available = [
            value for value in method_values if value.status == "available"
        ]
        method_angles = [
            float(value.angle_deg) for value in method_available
        ]
        method_mean = _periodic_mean(method_angles)
        method_distances = (
            []
            if method_mean is None
            else [_distance(value, method_mean) for value in method_angles]
        )
        method_summaries[method] = {
            "measurement_count": len(method_values),
            "available_count": len(method_available),
            "mean_axis_deg": method_mean,
            "median_axis_spread_deg": (
                None
                if not method_distances
                else float(np.median(method_distances))
            ),
            "p90_axis_spread_deg": (
                None
                if not method_distances
                else float(np.percentile(method_distances, 90))
            ),
            "median_confidence": (
                None
                if not method_available
                else float(
                    np.median(
                        [value.confidence for value in method_available]
                    )
                )
            ),
        }
    return {
        "measurement_count": len(values),
        "available_count": len(available),
        "available_fraction": len(available) / len(values) if values else 0.0,
        "mean_axis_deg": mean,
        "median_axis_spread_deg": spread,
        "axis_distance_from_mean_deg": {
            "q75": None if not distances else float(np.quantile(distances, 0.75)),
            "q90": None if not distances else float(np.quantile(distances, 0.90)),
            "maximum": None if not distances else float(max(distances)),
        },
        "angles_deg": sorted(angles),
        "median_confidence": (
            None
            if not available
            else float(np.median([value.confidence for value in available]))
        ),
        "method_counts": dict(Counter(value.method for value in values)),
        "method_summaries": method_summaries,
    }


def _prototype_fit(
    region_values,
    *,
    minimum_confidence: float,
    methods: tuple[str, ...] | None = None,
) -> dict[str, object] | None:
    filtered = {
        name: [
            value
            for value in values
            if (
                value.status == "available"
                and float(value.confidence) >= minimum_confidence
                and (methods is None or value.method in methods)
            )
        ]
        for name, values in region_values.items()
    }
    means = {
        name: _periodic_mean(
            [float(value.angle_deg) for value in values]
        )
        for name, values in filtered.items()
    }
    if any(value is None for value in means.values()):
        return None
    confusion = {
        expected: {predicted: 0 for predicted in means}
        for expected in means
    }
    classified_count = 0
    correct_count = 0
    for expected, values in filtered.items():
        for value in values:
            predicted = min(
                means,
                key=lambda name: (
                    _distance(float(value.angle_deg), means[name]),
                    name,
                ),
            )
            confusion[expected][predicted] += 1
            classified_count += 1
            correct_count += int(predicted == expected)
    return {
        "minimum_confidence": minimum_confidence,
        "methods": "all" if methods is None else list(methods),
        "prototype_angles_deg": means,
        "classified_count": classified_count,
        "correct_count": correct_count,
        "correct_fraction": (
            correct_count / classified_count if classified_count else 0.0
        ),
        "confusion": confusion,
    }


def _render(
    clean_path: Path,
    sample,
    indices_by_region,
    measurements_by_source_id,
    destination: Path,
    *,
    source_image_shape: tuple[int, int],
) -> None:
    image = Image.open(clean_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    source_height, source_width = source_image_shape
    scale_x = image.width / float(source_width)
    scale_y = image.height / float(source_height)
    try:
        label_font = ImageFont.truetype("DejaVuSans.ttf", 16)
    except OSError:
        label_font = ImageFont.load_default()
    for name, indices in indices_by_region.items():
        color = COLORS[name]
        for index in indices:
            source_id = sample.point_source_ids[index]
            measurement = measurements_by_source_id.get(source_id)
            x, y = sample.source_points_xy_px[index]
            x, y = float(x) * scale_x, float(y) * scale_y
            radius = 5
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                fill=color if measurement and measurement.status == "available" else (140, 140, 140),
                outline="white",
                width=2,
            )
            if measurement and measurement.status == "available":
                angle = radians(float(measurement.angle_deg))
                length = 10
                dx = cos(angle) * length
                dy = -sin(angle) * length
                draw.line(
                    (x - dx, y - dy, x + dx, y + dy),
                    fill="white",
                    width=2,
                )
    draw.text(
        (12, image.height - 28),
        "White segment: estimated molecular axis; gray: unavailable",
        fill="white",
        stroke_width=2,
        stroke_fill="black",
        font=label_font,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("clean_image", type=Path)
    parser.add_argument("manual_image", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--frame", type=int, default=255)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame_index = args.frame - 1
    session = load_moltrack_session(args.snapshot)
    series = restore_moltrack_image_series_from_session(session)
    source_view = session.position_analysis.source_view
    if source_view == "expanded_aligned":
        build_moltrack_expanded_aligned_stack(series)
        frame_image = series.expanded_aligned_stack.frames[frame_index]
    else:
        frame_image = series.raw_frames[frame_index]
    baseline_result = analyze_molecular_frame_range(
        series,
        MolecularFrameRange(f"frame {args.frame}", frame_index, frame_index),
        source_view=source_view,
        use_segmentation_centroids=True,
        m6_orientation_settings=TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET,
    ).frame_results[0]
    sample = baseline_result.m6_orientation_analysis.sample_coordinates
    _outlines, regions = _outline_masks(args.clean_image, args.manual_image)
    manual_shape = np.asarray(Image.open(args.manual_image)).shape[:2]
    _reference, indices_by_region, ambiguous = _reference_labels(
        sample,
        regions,
        image_shape=manual_shape,
        source_image_shape=frame_image.shape[:2],
    )
    result = estimate_series_molecular_orientations(
        series,
        frame_indices=(frame_index,),
        source_view=source_view,
        source_file_sha256=args.source_sha256,
    )
    by_source_id = {
        value.provenance.source_id: value for value in result.measurements
    }
    region_values = {
        name: [
            by_source_id[sample.point_source_ids[index]]
            for index in indices
            if sample.point_source_ids[index] in by_source_id
        ]
        for name, indices in indices_by_region.items()
    }
    summaries = {
        name: _summary(values) for name, values in region_values.items()
    }
    means = {
        name: value["mean_axis_deg"]
        for name, value in summaries.items()
        if value["mean_axis_deg"] is not None
    }
    pairwise = {
        f"{left}-{right}": _distance(means[left], means[right])
        for left in means
        for right in means
        if left < right
    }
    baseline_fit = _prototype_fit(
        region_values,
        minimum_confidence=0.0,
    )
    confidence_sweep = [
        fit_result
        for methods in (None, ("mask_principal_axis",))
        for threshold in (0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5)
        if (
            fit_result := _prototype_fit(
                region_values,
                minimum_confidence=threshold,
                methods=methods,
            )
        )
        is not None
    ]
    report = {
        "status": "single_frame_orientation_diagnostic",
        "frame_number_1_based": args.frame,
        "centroid_mode": "mask",
        "reference_scope": (
            "Only molecules inside the three manually outlined exemplar "
            "regions are scored. Detections outside them are unlabeled and "
            "are not false positives."
        ),
        "ambiguous_overlap_point_count": len(ambiguous),
        "batch_measurement_count": len(result.measurements),
        "batch_failure_count": len(result.failures),
        "regions": summaries,
        "pairwise_mean_axis_distance_deg": pairwise,
        "apparent_nearest_prototype_fit": {
            "note": (
                "Training-set diagnostic only; prototypes and scores use "
                "the same single annotated frame."
            ),
            "baseline": baseline_fit,
            "confidence_sweep": confidence_sweep,
        },
    }
    (args.output_dir / "molecular_orientation_by_region.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    _render(
        args.clean_image,
        sample,
        indices_by_region,
        by_source_id,
        args.output_dir / "molecular_orientation_by_region.png",
        source_image_shape=frame_image.shape[:2],
    )
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
