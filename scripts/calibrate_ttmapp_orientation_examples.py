"""Calibrate TTMAPP molecular-orientation classes from partial frame annotations."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import product
from math import atan2, cos, degrees, pi, sin
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

from calibrate_ttmapp_manual_frame import (  # noqa: E402
    REGION_COLORS,
    _subset_prediction,
)
from moltrack.analysis import (  # noqa: E402
    LatticeDomainPartitionLabels,
    MolecularFrameRange,
    TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET,
    analyze_molecular_frame_range,
    estimate_series_molecular_orientations,
    evaluate_lattice_domain_partition,
)
from moltrack.core import build_moltrack_expanded_aligned_stack  # noqa: E402
from moltrack.persistence import (  # noqa: E402
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
)


CLASS_NAMES = ("BLACK", "RED", "YELLOW")
UNASSIGNED = "UNASSIGNED"


@dataclass(frozen=True)
class ManualRegion:
    class_name: str
    instance_index: int
    mask: np.ndarray

    @property
    def instance_label(self) -> str:
        return f"{self.class_name}_{self.instance_index:02d}"


@dataclass
class ReferencePoint:
    frame_number: int
    split: str
    class_name: str
    instance_label: str
    source_id: str
    x_px: float
    y_px: float
    orientation_status: str = "missing"
    angle_deg: float | None = None
    confidence: float | None = None
    method: str | None = None
    q3: float | None = None
    q6: float | None = None
    theta3_lattice_deg: float | None = None
    theta6_deg: float | None = None
    symmetry_evidence: str | None = None
    symmetry_confidence: float | None = None


def _range_local_session(
    source: Path,
    destination: Path,
    *,
    frame_indices: set[int],
) -> Path:
    payload = json.loads(source.read_text(encoding="utf-8"))
    frame_count = len(payload["working_series"]["source_frame_indices"])
    if not frame_indices or min(frame_indices) < 0 or max(frame_indices) >= frame_count:
        raise ValueError("Requested frames lie outside the working series.")
    relative_source = payload["source"].get("path_relative_to_session")
    if relative_source:
        payload["source"]["path"] = str(
            (source.parent / str(relative_source)).resolve()
        )
    payload["molecular_detections"]["detections"] = [
        item
        for item in payload["molecular_detections"]["detections"]
        if int(item["frame_index"]) in frame_indices
    ]
    payload["molecular_segmentations"]["segmentations"] = [
        item
        for item in payload["molecular_segmentations"]["segmentations"]
        if int(item["frame_index"]) in frame_indices
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, separators=(",", ":")),
        encoding="utf-8",
    )
    return destination


def _color_outlines(
    clean_path: Path,
    manual_path: Path,
) -> dict[str, np.ndarray]:
    clean = np.asarray(Image.open(clean_path).convert("RGB"), dtype=np.int16)
    manual = np.asarray(Image.open(manual_path).convert("RGB"), dtype=np.int16)
    if clean.shape != manual.shape:
        raise ValueError(
            f"Image dimensions differ: {clean_path.name}, {manual_path.name}."
        )
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
    return {"BLACK": black, "RED": red, "YELLOW": yellow}


def _manual_regions(
    clean_path: Path,
    manual_path: Path,
) -> tuple[ManualRegion, ...]:
    outlines = _color_outlines(clean_path, manual_path)
    combined = np.logical_or.reduce(tuple(outlines.values()))
    barrier = ndimage.binary_closing(
        ndimage.binary_dilation(combined, iterations=5),
        iterations=10,
    )
    free_labels, free_count = ndimage.label(~barrier)
    candidates_by_class: dict[str, list[tuple[int, np.ndarray]]] = {
        name: [] for name in CLASS_NAMES
    }
    for label_index in range(1, free_count + 1):
        mask = free_labels == label_index
        area = int(np.count_nonzero(mask))
        if area < 1000:
            continue
        if (
            np.any(mask[0, :])
            or np.any(mask[-1, :])
            or np.any(mask[:, 0])
            or np.any(mask[:, -1])
        ):
            continue
        contact_ring = ndimage.binary_dilation(mask, iterations=10) & ~mask
        contacts = {
            name: int(np.count_nonzero(contact_ring & outline))
            for name, outline in outlines.items()
        }
        class_name, contact_count = sorted(
            contacts.items(),
            key=lambda item: (-item[1], item[0]),
        )[0]
        if contact_count < 10:
            continue
        if class_name == "BLACK" and area < 5000:
            continue
        restored_interior = ndimage.binary_dilation(mask, iterations=5)
        candidates_by_class[class_name].append((area, restored_interior))

    regions = []
    for class_name in CLASS_NAMES:
        candidates = sorted(
            candidates_by_class[class_name],
            key=lambda item: -item[0],
        )
        for instance_index, (_area, mask) in enumerate(candidates, start=1):
            regions.append(
                ManualRegion(
                    class_name=class_name,
                    instance_index=instance_index,
                    mask=mask,
                )
            )
    return tuple(
        sorted(
            regions,
            key=lambda value: (value.class_name, value.instance_index),
        )
    )


def _reference_points(
    sample,
    regions: tuple[ManualRegion, ...],
    *,
    frame_number: int,
    split: str,
    annotation_shape: tuple[int, int],
    source_image_shape: tuple[int, int],
) -> tuple[list[ReferencePoint], int]:
    height, width = annotation_shape
    source_height, source_width = source_image_shape
    scale_x = width / float(source_width)
    scale_y = height / float(source_height)
    points = []
    ambiguous_count = 0
    for source_id, (x, y) in zip(
        sample.point_source_ids,
        sample.source_points_xy_px,
    ):
        px = min(width - 1, max(0, int(round(float(x) * scale_x))))
        py = min(height - 1, max(0, int(round(float(y) * scale_y))))
        membership = [region for region in regions if bool(region.mask[py, px])]
        if len(membership) > 1:
            ambiguous_count += 1
            continue
        if not membership:
            continue
        region = membership[0]
        points.append(
            ReferencePoint(
                frame_number=frame_number,
                split=split,
                class_name=region.class_name,
                instance_label=region.instance_label,
                source_id=source_id,
                x_px=float(x),
                y_px=float(y),
            )
        )
    return points, ambiguous_count


def _render_reference(
    clean_path: Path,
    points: list[ReferencePoint],
    destination: Path,
    *,
    source_image_shape: tuple[int, int],
) -> None:
    image = Image.open(clean_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    source_height, source_width = source_image_shape
    scale_x = image.width / float(source_width)
    scale_y = image.height / float(source_height)
    for point in points:
        x = point.x_px * scale_x
        y = point.y_px * scale_y
        radius = 4
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=REGION_COLORS[point.class_name],
            outline="white",
            width=1,
        )
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    counts = Counter(point.class_name for point in points)
    text = " | ".join(f"{name}: {counts[name]}" for name in CLASS_NAMES)
    draw.text(
        (12, 12),
        text,
        fill="white",
        stroke_width=2,
        stroke_fill="black",
        font=font,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)


def _periodic_distance(left: float, right: float, period: float = 180.0) -> float:
    difference = abs(float(left) - float(right)) % period
    return min(difference, period - difference)


def _periodic_mean(
    values: list[float],
    *,
    weights: list[float],
    period: float = 180.0,
) -> float | None:
    if not values:
        return None
    phases = [2.0 * pi * value / period for value in values]
    mean_x = sum(weight * cos(phase) for weight, phase in zip(weights, phases))
    mean_y = sum(weight * sin(phase) for weight, phase in zip(weights, phases))
    if abs(mean_x) + abs(mean_y) <= 1e-12:
        return None
    return (degrees(atan2(mean_y, mean_x)) % 360.0) * period / 360.0


def _eligible(
    point: ReferencePoint,
    *,
    methods: str,
    minimum_confidence: float,
) -> bool:
    return (
        point.orientation_status == "available"
        and point.angle_deg is not None
        and point.confidence is not None
        and point.confidence >= minimum_confidence
        and (methods == "all" or point.method == "mask_principal_axis")
    )


def _learn_prototypes(
    points: list[ReferencePoint],
    *,
    methods: str,
    minimum_confidence: float,
    weighting: str,
) -> dict[str, float] | None:
    prototypes = {}
    for class_name in CLASS_NAMES:
        selected = [
            point
            for point in points
            if point.class_name == class_name
            and _eligible(
                point,
                methods=methods,
                minimum_confidence=minimum_confidence,
            )
        ]
        if len(selected) < 3:
            return None
        angles = [float(point.angle_deg) for point in selected]
        weights = [
            (
                max(float(point.confidence), 1e-6)
                if weighting == "confidence"
                else 1.0
            )
            for point in selected
        ]
        mean = _periodic_mean(angles, weights=weights)
        if mean is None:
            return None
        prototypes[class_name] = mean
    return prototypes


def _predict(
    point: ReferencePoint,
    prototypes: dict[str, float],
    *,
    methods: str,
    minimum_confidence: float,
    maximum_distance_deg: float,
    minimum_margin_deg: float,
) -> str:
    if not _eligible(
        point,
        methods=methods,
        minimum_confidence=minimum_confidence,
    ):
        return UNASSIGNED
    distances = sorted(
        (
            _periodic_distance(float(point.angle_deg), angle),
            class_name,
        )
        for class_name, angle in prototypes.items()
    )
    best_distance, best_class = distances[0]
    second_distance = distances[1][0]
    if (
        best_distance > maximum_distance_deg
        or second_distance - best_distance < minimum_margin_deg
    ):
        return UNASSIGNED
    return best_class


def _classification_metrics(
    points: list[ReferencePoint],
    predictions: dict[tuple[int, str], str],
) -> dict[str, object]:
    confusion = {
        expected: {predicted: 0 for predicted in (*CLASS_NAMES, UNASSIGNED)}
        for expected in CLASS_NAMES
    }
    for point in points:
        predicted = predictions[(point.frame_number, point.source_id)]
        confusion[point.class_name][predicted] += 1
    per_class = {}
    for class_name in CLASS_NAMES:
        true_positive = confusion[class_name][class_name]
        false_positive = sum(
            confusion[other][class_name]
            for other in CLASS_NAMES
            if other != class_name
        )
        false_negative = sum(
            count
            for predicted, count in confusion[class_name].items()
            if predicted != class_name
        )
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        f1 = (
            2.0 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        per_class[class_name] = {
            "support": sum(confusion[class_name].values()),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    assigned = sum(
        count
        for expected in CLASS_NAMES
        for predicted, count in confusion[expected].items()
        if predicted != UNASSIGNED
    )
    correct = sum(confusion[name][name] for name in CLASS_NAMES)
    grouped: dict[tuple[int, str], list[ReferencePoint]] = defaultdict(list)
    for point in points:
        grouped[(point.frame_number, point.instance_label)].append(point)
    domain_correct = 0
    domain_assigned = 0
    for values in grouped.values():
        votes = Counter(
            predictions[(point.frame_number, point.source_id)]
            for point in values
            if predictions[(point.frame_number, point.source_id)] != UNASSIGNED
        )
        if not votes:
            continue
        domain_assigned += 1
        predicted = sorted(votes.items(), key=lambda item: (-item[1], item[0]))[0][0]
        domain_correct += int(predicted == values[0].class_name)
    return {
        "point_count": len(points),
        "assigned_point_count": assigned,
        "coverage": assigned / len(points) if points else 0.0,
        "assigned_accuracy": correct / assigned if assigned else 0.0,
        "macro_recall": float(
            np.mean([per_class[name]["recall"] for name in CLASS_NAMES])
        ),
        "macro_f1": float(
            np.mean([per_class[name]["f1"] for name in CLASS_NAMES])
        ),
        "domain_count": len(grouped),
        "assigned_domain_count": domain_assigned,
        "domain_coverage": domain_assigned / len(grouped) if grouped else 0.0,
        "assigned_domain_accuracy": (
            domain_correct / domain_assigned if domain_assigned else 0.0
        ),
        "per_class": per_class,
        "confusion": confusion,
    }


def _evaluate_candidate(
    points: list[ReferencePoint],
    prototypes: dict[str, float],
    *,
    methods: str,
    minimum_confidence: float,
    maximum_distance_deg: float,
    minimum_margin_deg: float,
) -> tuple[dict[str, object], dict[tuple[int, str], str]]:
    predictions = {
        (point.frame_number, point.source_id): _predict(
            point,
            prototypes,
            methods=methods,
            minimum_confidence=minimum_confidence,
            maximum_distance_deg=maximum_distance_deg,
            minimum_margin_deg=minimum_margin_deg,
        )
        for point in points
    }
    return _classification_metrics(points, predictions), predictions


def _sweep(calibration_points: list[ReferencePoint]):
    rows = []
    best = None
    for methods, weighting, minimum_confidence in product(
        ("all", "mask_only"),
        ("equal", "confidence"),
        (0.0, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2),
    ):
        prototypes = _learn_prototypes(
            calibration_points,
            methods=methods,
            minimum_confidence=minimum_confidence,
            weighting=weighting,
        )
        if prototypes is None:
            continue
        for maximum_distance_deg, minimum_margin_deg in product(
            (10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 90.0),
            (0.0, 5.0, 10.0, 15.0),
        ):
            metrics, predictions = _evaluate_candidate(
                calibration_points,
                prototypes,
                methods=methods,
                minimum_confidence=minimum_confidence,
                maximum_distance_deg=maximum_distance_deg,
                minimum_margin_deg=minimum_margin_deg,
            )
            row = {
                "methods": methods,
                "weighting": weighting,
                "minimum_confidence": minimum_confidence,
                "maximum_distance_deg": maximum_distance_deg,
                "minimum_margin_deg": minimum_margin_deg,
                "prototype_black_deg": prototypes["BLACK"],
                "prototype_red_deg": prototypes["RED"],
                "prototype_yellow_deg": prototypes["YELLOW"],
                "macro_f1": metrics["macro_f1"],
                "macro_recall": metrics["macro_recall"],
                "coverage": metrics["coverage"],
                "assigned_accuracy": metrics["assigned_accuracy"],
                "domain_coverage": metrics["domain_coverage"],
                "assigned_domain_accuracy": metrics[
                    "assigned_domain_accuracy"
                ],
            }
            rows.append(row)
            rank = (
                float(metrics["macro_f1"]),
                float(metrics["macro_recall"]),
                float(metrics["assigned_domain_accuracy"]),
                float(metrics["domain_coverage"]),
                float(metrics["assigned_accuracy"]),
                float(metrics["coverage"]),
                -minimum_confidence,
                -maximum_distance_deg,
                -minimum_margin_deg,
            )
            if best is None or rank > best[0]:
                best = (rank, row, prototypes, metrics, predictions)
    if best is None:
        raise RuntimeError("No orientation calibration candidate could be evaluated.")
    return rows, best


HYBRID_FEATURE_PERIODS = {
    "axis": 180.0,
    "theta3": 60.0,
    "theta6": 60.0,
}


def _hybrid_feature_value(
    point: ReferencePoint,
    feature_name: str,
) -> float | None:
    if feature_name == "axis":
        return point.angle_deg
    if feature_name == "theta3":
        return point.theta3_lattice_deg
    if feature_name == "theta6":
        return point.theta6_deg
    raise ValueError(f"Unknown hybrid feature: {feature_name}.")


def _hybrid_eligible(
    point: ReferencePoint,
    *,
    features: tuple[str, ...],
    methods: str,
    minimum_confidence: float,
) -> bool:
    if "axis" in features and not _eligible(
        point,
        methods=methods,
        minimum_confidence=minimum_confidence,
    ):
        return False
    return all(
        _hybrid_feature_value(point, feature_name) is not None
        for feature_name in features
    )


def _learn_hybrid_prototypes(
    points: list[ReferencePoint],
    *,
    features: tuple[str, ...],
    methods: str,
    minimum_confidence: float,
    weighting: str,
) -> dict[str, dict[str, float]] | None:
    prototypes = {}
    for class_name in CLASS_NAMES:
        selected = [
            point
            for point in points
            if point.class_name == class_name
            and _hybrid_eligible(
                point,
                features=features,
                methods=methods,
                minimum_confidence=minimum_confidence,
            )
        ]
        if len(selected) < 3:
            return None
        feature_prototypes = {}
        for feature_name in features:
            values = [
                float(_hybrid_feature_value(point, feature_name))
                for point in selected
            ]
            weights = [
                (
                    max(float(point.confidence), 1e-6)
                    if (
                        weighting == "confidence"
                        and "axis" in features
                        and point.confidence is not None
                    )
                    else 1.0
                )
                for point in selected
            ]
            mean = _periodic_mean(
                values,
                weights=weights,
                period=HYBRID_FEATURE_PERIODS[feature_name],
            )
            if mean is None:
                return None
            feature_prototypes[feature_name] = mean
        prototypes[class_name] = feature_prototypes
    return prototypes


def _hybrid_distance(
    point: ReferencePoint,
    prototype: dict[str, float],
    *,
    features: tuple[str, ...],
    lattice_weight: float,
) -> float:
    weighted_squared = 0.0
    total_weight = 0.0
    for feature_name in features:
        period = HYBRID_FEATURE_PERIODS[feature_name]
        value = _hybrid_feature_value(point, feature_name)
        assert value is not None
        weight = 1.0 if feature_name == "axis" else lattice_weight
        normalized = _periodic_distance(
            float(value),
            prototype[feature_name],
            period=period,
        ) / (period / 2.0)
        weighted_squared += weight * normalized * normalized
        total_weight += weight
    return float(np.sqrt(weighted_squared / total_weight))


def _predict_hybrid(
    point: ReferencePoint,
    prototypes: dict[str, dict[str, float]],
    *,
    features: tuple[str, ...],
    methods: str,
    minimum_confidence: float,
    lattice_weight: float,
    maximum_distance: float,
    minimum_margin: float,
) -> str:
    if not _hybrid_eligible(
        point,
        features=features,
        methods=methods,
        minimum_confidence=minimum_confidence,
    ):
        return UNASSIGNED
    distances = sorted(
        (
            _hybrid_distance(
                point,
                prototype,
                features=features,
                lattice_weight=lattice_weight,
            ),
            class_name,
        )
        for class_name, prototype in prototypes.items()
    )
    best_distance, best_class = distances[0]
    if (
        best_distance > maximum_distance
        or distances[1][0] - best_distance < minimum_margin
    ):
        return UNASSIGNED
    return best_class


def _evaluate_hybrid_candidate(
    points: list[ReferencePoint],
    prototypes: dict[str, dict[str, float]],
    *,
    features: tuple[str, ...],
    methods: str,
    minimum_confidence: float,
    lattice_weight: float,
    maximum_distance: float,
    minimum_margin: float,
) -> tuple[dict[str, object], dict[tuple[int, str], str]]:
    predictions = {
        (point.frame_number, point.source_id): _predict_hybrid(
            point,
            prototypes,
            features=features,
            methods=methods,
            minimum_confidence=minimum_confidence,
            lattice_weight=lattice_weight,
            maximum_distance=maximum_distance,
            minimum_margin=minimum_margin,
        )
        for point in points
    }
    return _classification_metrics(points, predictions), predictions


def _sweep_hybrid(calibration_points: list[ReferencePoint]):
    rows = []
    best = None
    feature_modes = (
        ("theta6",),
        ("theta3", "theta6"),
        ("axis", "theta6"),
        ("axis", "theta3"),
        ("axis", "theta3", "theta6"),
    )
    for features in feature_modes:
        uses_axis = "axis" in features
        method_values = ("all", "mask_only") if uses_axis else ("not_used",)
        confidence_values = (
            (0.0, 0.05, 0.1, 0.15) if uses_axis else (0.0,)
        )
        weighting_values = (
            ("equal", "confidence") if uses_axis else ("equal",)
        )
        lattice_weights = (
            (0.25, 0.5, 1.0, 2.0, 4.0) if uses_axis else (1.0,)
        )
        for (
            methods,
            minimum_confidence,
            weighting,
            lattice_weight,
        ) in product(
            method_values,
            confidence_values,
            weighting_values,
            lattice_weights,
        ):
            prototypes = _learn_hybrid_prototypes(
                calibration_points,
                features=features,
                methods=methods,
                minimum_confidence=minimum_confidence,
                weighting=weighting,
            )
            if prototypes is None:
                continue
            for maximum_distance, minimum_margin in product(
                (0.25, 0.5, 0.75, 1.0),
                (0.0, 0.05, 0.1, 0.2),
            ):
                metrics, predictions = _evaluate_hybrid_candidate(
                    calibration_points,
                    prototypes,
                    features=features,
                    methods=methods,
                    minimum_confidence=minimum_confidence,
                    lattice_weight=lattice_weight,
                    maximum_distance=maximum_distance,
                    minimum_margin=minimum_margin,
                )
                row = {
                    "features": "+".join(features),
                    "methods": methods,
                    "weighting": weighting,
                    "minimum_confidence": minimum_confidence,
                    "lattice_weight": lattice_weight,
                    "maximum_distance": maximum_distance,
                    "minimum_margin": minimum_margin,
                    "prototypes_json": json.dumps(
                        prototypes,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "macro_f1": metrics["macro_f1"],
                    "macro_recall": metrics["macro_recall"],
                    "coverage": metrics["coverage"],
                    "assigned_accuracy": metrics["assigned_accuracy"],
                    "domain_coverage": metrics["domain_coverage"],
                    "assigned_domain_accuracy": metrics[
                        "assigned_domain_accuracy"
                    ],
                }
                rows.append(row)
                rank = (
                    float(metrics["macro_f1"]),
                    float(metrics["macro_recall"]),
                    float(metrics["assigned_domain_accuracy"]),
                    float(metrics["domain_coverage"]),
                    float(metrics["assigned_accuracy"]),
                    float(metrics["coverage"]),
                    -maximum_distance,
                    -minimum_margin,
                )
                if best is None or rank > best[0]:
                    best = (rank, row, prototypes, metrics, predictions)
    if best is None:
        raise RuntimeError("No hybrid calibration candidate could be evaluated.")
    return rows, best


def _write_reference_csv(points: list[ReferencePoint], destination: Path) -> None:
    fieldnames = (
        "frame_number",
        "split",
        "class_name",
        "instance_label",
        "source_id",
        "x_px",
        "y_px",
        "orientation_status",
        "angle_deg",
        "confidence",
        "method",
        "q3",
        "q6",
        "theta3_lattice_deg",
        "theta6_deg",
        "symmetry_evidence",
        "symmetry_confidence",
    )
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for point in points:
            writer.writerow({name: getattr(point, name) for name in fieldnames})


def _write_report_markdown(report: dict[str, object], destination: Path) -> None:
    calibration = report["orientation_calibration"]["calibration_metrics"]
    holdout = report["orientation_calibration"]["holdout_metrics"]
    settings = report["orientation_calibration"]["selected_settings"]
    prototypes = report["orientation_calibration"]["prototypes_deg"]
    hybrid = report.get("hybrid_calibration")
    lines = [
        "# TTMAPP orientation calibration, frames 250-268",
        "",
        "## Scope",
        "",
        (
            "Colored outlines are positive examples. Molecules outside the "
            "outlined regions are unlabeled and are never counted as false positives."
        ),
        "",
        (
            f"Calibration frames: {report['splits']['calibration_frames']}; "
            f"holdout frames: {report['splits']['holdout_frames']}."
        ),
        "",
        "## Selected molecular-axis candidate",
        "",
        f"- methods: `{settings['methods']}`",
        f"- weighting: `{settings['weighting']}`",
        f"- minimum confidence: `{settings['minimum_confidence']}`",
        f"- maximum prototype distance: `{settings['maximum_distance_deg']} deg`",
        f"- minimum runner-up margin: `{settings['minimum_margin_deg']} deg`",
        (
            "- prototypes: "
            + ", ".join(
                f"{name}={float(prototypes[name]):.2f} deg"
                for name in CLASS_NAMES
            )
        ),
        "",
        "## Validation",
        "",
        "| Split | Points | Coverage | Macro F1 | Assigned accuracy | Domain accuracy |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        (
            f"| Calibration | {calibration['point_count']} | "
            f"{100.0 * calibration['coverage']:.1f}% | "
            f"{calibration['macro_f1']:.3f} | "
            f"{100.0 * calibration['assigned_accuracy']:.1f}% | "
            f"{100.0 * calibration['assigned_domain_accuracy']:.1f}% |"
        ),
        (
            f"| Holdout | {holdout['point_count']} | "
            f"{100.0 * holdout['coverage']:.1f}% | "
            f"{holdout['macro_f1']:.3f} | "
            f"{100.0 * holdout['assigned_accuracy']:.1f}% | "
            f"{100.0 * holdout['assigned_domain_accuracy']:.1f}% |"
        ),
        "",
        "## Interpretation",
        "",
        (
            "The holdout result tests molecular-axis class separability. It "
            "does not yet validate autonomous spatial boundary discovery. "
            "Sequential frames contain the same field of view, so the holdout "
            "is stricter than training reuse but is not an independent experiment."
        ),
        "",
    ]
    if hybrid is not None:
        hybrid_settings = hybrid["selected_settings"]
        hybrid_calibration = hybrid["calibration_metrics"]
        hybrid_holdout = hybrid["holdout_metrics"]
        lines.extend(
            [
                "## Hybrid M3/M6 candidate",
                "",
                f"- features: `{hybrid_settings['features']}`",
                (
                    "- calibration macro F1: "
                    f"`{hybrid_calibration['macro_f1']:.3f}`"
                ),
                f"- holdout macro F1: `{hybrid_holdout['macro_f1']:.3f}`",
                (
                    "- holdout assigned-domain accuracy: "
                    f"`{100.0 * hybrid_holdout['assigned_domain_accuracy']:.1f}%`"
                ),
                "",
                "## Decision",
                "",
                (
                    "Do not promote this candidate to a TTMAPP preset. The "
                    "annotated set is large enough to show that the current "
                    "mask-axis and modulo-60 lattice features do not reliably "
                    "separate the RED class from BLACK. The next experiment "
                    "must add a local row-orientation or STM-texture descriptor."
                ),
                "",
            ]
        )
    destination.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("annotations_dir", type=Path)
    parser.add_argument("frame_255_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--first-frame", type=int, default=250)
    parser.add_argument("--last-frame", type=int, default=268)
    parser.add_argument("--holdout-start", type=int, default=263)
    parser.add_argument("--source-sha256", required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame_numbers = tuple(range(args.first_frame, args.last_frame + 1))
    frame_indices = {value - 1 for value in frame_numbers}
    snapshot = _range_local_session(
        args.session,
        args.output_dir / "frames_250_268_input_snapshot.moltrack.json",
        frame_indices=frame_indices,
    )
    print(f"Loading range-local snapshot: {snapshot}", flush=True)
    session = load_moltrack_session(snapshot)
    series = restore_moltrack_image_series_from_session(session)
    source_view = session.position_analysis.source_view
    if source_view == "expanded_aligned":
        print("Building expanded aligned stack...", flush=True)
        build_moltrack_expanded_aligned_stack(series)
        source_frames = series.expanded_aligned_stack.frames
    else:
        source_frames = series.raw_frames
    print("Computing TTMAPP M3/M6 baseline for the annotated range...", flush=True)
    range_result = analyze_molecular_frame_range(
        series,
        MolecularFrameRange(
            "manual orientation examples",
            args.first_frame - 1,
            args.last_frame - 1,
        ),
        source_view=source_view,
        use_segmentation_centroids=True,
        m6_orientation_settings=TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET,
        progress_callback=lambda completed, total, frame_index: print(
            f"M3/M6 frame {completed}/{total} "
            f"(working index {frame_index})",
            flush=True,
        ),
    )
    analysis_by_frame = {
        result.frame_index: result.m6_orientation_analysis
        for result in range_result.frame_results
    }
    all_points = []
    ambiguous_by_frame = {}
    regions_by_frame = {}
    m6_metrics_by_frame = {}
    overlays_dir = args.output_dir / "reference_overlays"
    for frame_number in frame_numbers:
        if frame_number == 255:
            clean_path = args.frame_255_dir / "frame_255_clean_registered.png"
            manual_path = (
                args.frame_255_dir
                / "frame_255_clean_registered_manual_domain.png"
            )
        else:
            clean_path = (
                args.annotations_dir
                / f"frame_{frame_number}_clean_registered.png"
            )
            manual_path = (
                args.annotations_dir
                / f"frame_{frame_number}_clean_registered_manual_domain.png"
            )
        if not clean_path.is_file() or not manual_path.is_file():
            raise FileNotFoundError(
                f"Missing clean/manual pair for frame {frame_number}."
            )
        frame_index = frame_number - 1
        analysis = analysis_by_frame[frame_index]
        if analysis is None:
            raise RuntimeError(f"M3/M6 analysis unavailable for frame {frame_number}.")
        regions = _manual_regions(clean_path, manual_path)
        if not regions:
            raise ValueError(f"No manual regions found for frame {frame_number}.")
        split = "holdout" if frame_number >= args.holdout_start else "calibration"
        points, ambiguous_count = _reference_points(
            analysis.sample_coordinates,
            regions,
            frame_number=frame_number,
            split=split,
            annotation_shape=np.asarray(Image.open(manual_path)).shape[:2],
            source_image_shape=np.asarray(source_frames[frame_index]).shape[:2],
        )
        if not points:
            raise ValueError(f"No centroids lie in annotations for frame {frame_number}.")
        local_order = analysis.local_multisymmetry_order
        local_evidence = analysis.local_symmetry_evidence
        point_index_by_source_id = {
            source_id: index
            for index, source_id in enumerate(
                analysis.sample_coordinates.point_source_ids
            )
        }
        for point in points:
            point_index = point_index_by_source_id[point.source_id]
            point.q3 = local_order.q3[point_index]
            point.q6 = local_order.q6[point_index]
            point.theta3_lattice_deg = (
                local_order.theta3_lattice_deg[point_index]
            )
            point.theta6_deg = local_order.theta6_deg[point_index]
            point.symmetry_evidence = local_evidence.best_model[point_index]
            point.symmetry_confidence = (
                local_evidence.classification_confidence[point_index]
            )
        all_points.extend(points)
        ambiguous_by_frame[str(frame_number)] = ambiguous_count
        regions_by_frame[str(frame_number)] = [
            {
                "class_name": region.class_name,
                "instance_label": region.instance_label,
                "area_px": int(np.count_nonzero(region.mask)),
            }
            for region in regions
        ]
        reference = LatticeDomainPartitionLabels(
            source_ids=tuple(point.source_id for point in points),
            domain_labels=tuple(point.instance_label for point in points),
            boundary=(False,) * len(points),
            confidence=(1.0,) * len(points),
        )
        prediction = _subset_prediction(analysis, reference.source_ids)
        m6_report = evaluate_lattice_domain_partition(prediction, reference)
        m6_metrics_by_frame[str(frame_number)] = m6_report.__dict__
        _render_reference(
            clean_path,
            points,
            overlays_dir / f"frame_{frame_number}_reference.png",
            source_image_shape=np.asarray(source_frames[frame_index]).shape[:2],
        )
        counts = Counter(point.class_name for point in points)
        print(
            f"Frame {frame_number}: "
            + ", ".join(f"{name}={counts[name]}" for name in CLASS_NAMES)
            + f", ambiguous={ambiguous_count}",
            flush=True,
        )

    manual_ids = {point.source_id for point in all_points}
    for frame_index in frame_indices:
        current = series.molecular_segmentations.segmentations_by_frame.get(
            frame_index,
            [],
        )
        series.molecular_segmentations.segmentations_by_frame[frame_index] = [
            value for value in current if value.segmentation_id in manual_ids
        ]
    progress_state = {"last": -1}

    def _orientation_progress(progress) -> None:
        if (
            progress.completed_count == progress.total_count
            or progress.completed_count - progress_state["last"] >= 100
        ):
            progress_state["last"] = progress.completed_count
            print(
                "Molecular orientation "
                f"{progress.completed_count}/{progress.total_count}",
                flush=True,
            )

    print("Estimating molecular axes for labeled examples...", flush=True)
    batch = estimate_series_molecular_orientations(
        series,
        frame_indices=tuple(sorted(frame_indices)),
        source_view=source_view,
        source_file_sha256=args.source_sha256,
        progress_callback=_orientation_progress,
    )
    measurements = {
        value.provenance.source_id: value for value in batch.measurements
    }
    for point in all_points:
        measurement = measurements.get(point.source_id)
        if measurement is None:
            continue
        point.orientation_status = measurement.status
        point.angle_deg = measurement.angle_deg
        point.confidence = measurement.confidence
        point.method = measurement.method

    calibration_points = [
        point for point in all_points if point.split == "calibration"
    ]
    holdout_points = [point for point in all_points if point.split == "holdout"]
    print("Sweeping molecular-axis classifier on calibration frames...", flush=True)
    sweep_rows, best = _sweep(calibration_points)
    _rank, best_row, prototypes, calibration_metrics, _predictions = best
    holdout_metrics, holdout_predictions = _evaluate_candidate(
        holdout_points,
        prototypes,
        methods=str(best_row["methods"]),
        minimum_confidence=float(best_row["minimum_confidence"]),
        maximum_distance_deg=float(best_row["maximum_distance_deg"]),
        minimum_margin_deg=float(best_row["minimum_margin_deg"]),
    )
    print("Sweeping hybrid molecular-axis and M3/M6 classifier...", flush=True)
    hybrid_rows, best_hybrid = _sweep_hybrid(calibration_points)
    (
        _hybrid_rank,
        best_hybrid_row,
        hybrid_prototypes,
        hybrid_calibration_metrics,
        _hybrid_calibration_predictions,
    ) = best_hybrid
    hybrid_features = tuple(str(best_hybrid_row["features"]).split("+"))
    hybrid_holdout_metrics, hybrid_holdout_predictions = (
        _evaluate_hybrid_candidate(
            holdout_points,
            hybrid_prototypes,
            features=hybrid_features,
            methods=str(best_hybrid_row["methods"]),
            minimum_confidence=float(
                best_hybrid_row["minimum_confidence"]
            ),
            lattice_weight=float(best_hybrid_row["lattice_weight"]),
            maximum_distance=float(best_hybrid_row["maximum_distance"]),
            minimum_margin=float(best_hybrid_row["minimum_margin"]),
        )
    )
    sweep_rows.sort(
        key=lambda row: (
            -float(row["macro_f1"]),
            -float(row["macro_recall"]),
            -float(row["assigned_domain_accuracy"]),
            -float(row["coverage"]),
        )
    )
    with (args.output_dir / "orientation_classifier_sweep.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(sweep_rows[0]))
        writer.writeheader()
        writer.writerows(sweep_rows)
    hybrid_rows.sort(
        key=lambda row: (
            -float(row["macro_f1"]),
            -float(row["macro_recall"]),
            -float(row["assigned_domain_accuracy"]),
            -float(row["coverage"]),
        )
    )
    with (args.output_dir / "hybrid_classifier_sweep.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(hybrid_rows[0]))
        writer.writeheader()
        writer.writerows(hybrid_rows)
    _write_reference_csv(
        all_points,
        args.output_dir / "manual_reference_molecules.csv",
    )
    m6_ari_values = [
        float(value["adjusted_rand_index"])
        for value in m6_metrics_by_frame.values()
    ]
    report = {
        "status": "multi_frame_partial_annotation_calibration",
        "reference_scope": (
            "Only molecules inside colored regions are labeled and scored. "
            "All detections outside are ignored, not false positives."
        ),
        "source_session": str(args.session.resolve()),
        "source_sha256": args.source_sha256,
        "source_view": source_view,
        "splits": {
            "calibration_frames": [
                value for value in frame_numbers if value < args.holdout_start
            ],
            "holdout_frames": [
                value for value in frame_numbers if value >= args.holdout_start
            ],
        },
        "reference": {
            "point_count": len(all_points),
            "calibration_point_count": len(calibration_points),
            "holdout_point_count": len(holdout_points),
            "class_counts": dict(Counter(point.class_name for point in all_points)),
            "split_class_counts": {
                split: dict(
                    Counter(
                        point.class_name
                        for point in all_points
                        if point.split == split
                    )
                )
                for split in ("calibration", "holdout")
            },
            "regions_by_frame": regions_by_frame,
            "ambiguous_overlap_points_by_frame": ambiguous_by_frame,
        },
        "orientation_estimation": {
            "measurement_count": len(batch.measurements),
            "failure_count": len(batch.failures),
            "status_counts": dict(
                Counter(point.orientation_status for point in all_points)
            ),
            "method_counts": dict(
                Counter(
                    point.method or "missing"
                    for point in all_points
                )
            ),
        },
        "m3_m6_baseline": {
            "per_frame": m6_metrics_by_frame,
            "mean_adjusted_rand_index": float(np.mean(m6_ari_values)),
            "median_adjusted_rand_index": float(np.median(m6_ari_values)),
        },
        "orientation_calibration": {
            "selected_settings": {
                key: best_row[key]
                for key in (
                    "methods",
                    "weighting",
                    "minimum_confidence",
                    "maximum_distance_deg",
                    "minimum_margin_deg",
                )
            },
            "prototypes_deg": prototypes,
            "calibration_metrics": calibration_metrics,
            "holdout_metrics": holdout_metrics,
            "holdout_predictions": {
                f"{frame}:{source_id}": predicted
                for (frame, source_id), predicted in holdout_predictions.items()
            },
            "candidate_count": len(sweep_rows),
            "limitation": (
                "This validates orientation-class separability inside manual "
                "regions, not autonomous spatial boundary discovery."
            ),
        },
        "hybrid_calibration": {
            "selected_settings": {
                key: best_hybrid_row[key]
                for key in (
                    "features",
                    "methods",
                    "weighting",
                    "minimum_confidence",
                    "lattice_weight",
                    "maximum_distance",
                    "minimum_margin",
                )
            },
            "prototypes": hybrid_prototypes,
            "calibration_metrics": hybrid_calibration_metrics,
            "holdout_metrics": hybrid_holdout_metrics,
            "holdout_predictions": {
                f"{frame}:{source_id}": predicted
                for (frame, source_id), predicted
                in hybrid_holdout_predictions.items()
            },
            "candidate_count": len(hybrid_rows),
            "selection_rule": (
                "Selected on calibration macro F1 only; holdout was evaluated "
                "once after selection."
            ),
        },
    }
    report_path = args.output_dir / "calibration_report.json"
    report_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    _write_report_markdown(
        report,
        args.output_dir / "calibration_report.md",
    )
    print(
        json.dumps(
            {
                key: value
                for key, value in report["orientation_calibration"].items()
                if key != "holdout_predictions"
            },
            indent=2,
        ),
        flush=True,
    )
    print(
        json.dumps(
            {
                key: value
                for key, value in report["hybrid_calibration"].items()
                if key != "holdout_predictions"
            },
            indent=2,
        ),
        flush=True,
    )
    print(f"Report: {report_path.resolve()}", flush=True)


if __name__ == "__main__":
    main()
