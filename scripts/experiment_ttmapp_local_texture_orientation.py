"""Evaluate local STM texture orientation on manual TTMAPP domain labels.

The candidate settings are selected with leave-one-frame-out validation on the
calibration frames. The temporal holdout is evaluated only after selection.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from math import atan2, cos, degrees, pi, sin
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from moltrack.core import build_moltrack_expanded_aligned_stack  # noqa: E402
from moltrack.persistence import (  # noqa: E402
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
)


CLASS_NAMES = ("BLACK", "RED", "YELLOW")
CLASS_INDEX = {name: index for index, name in enumerate(CLASS_NAMES)}
CLASS_COLORS = {
    "BLACK": (30, 30, 30),
    "RED": (240, 45, 40),
    "YELLOW": (245, 205, 0),
    "UNASSIGNED": (255, 255, 255),
}
UNASSIGNED_INDEX = len(CLASS_NAMES)
PERIOD_DEG = 180.0


@dataclass(frozen=True)
class ReferencePoint:
    frame_number: int
    split: str
    class_name: str
    instance_label: str
    source_id: str
    x_px: float
    y_px: float


@dataclass(frozen=True)
class TextureSetting:
    high_pass_sigma_px: float
    image_sigma_px: float
    tensor_sigma_px: float

    @property
    def setting_id(self) -> str:
        return (
            f"hp{self.high_pass_sigma_px:g}_"
            f"im{self.image_sigma_px:g}_"
            f"tensor{self.tensor_sigma_px:g}"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("reference_csv", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--baseline-report", type=Path)
    return parser.parse_args()


def _read_reference(path: Path) -> list[ReferencePoint]:
    points = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            class_name = str(row["class_name"]).strip().upper()
            if class_name not in CLASS_INDEX:
                continue
            points.append(
                ReferencePoint(
                    frame_number=int(row["frame_number"]),
                    split=str(row["split"]).strip(),
                    class_name=class_name,
                    instance_label=str(row["instance_label"]).strip(),
                    source_id=str(row["source_id"]).strip(),
                    x_px=float(row["x_px"]),
                    y_px=float(row["y_px"]),
                )
            )
    if not points:
        raise ValueError("The reference CSV contains no supported labels.")
    return points


def _prepare_image(frame: np.ndarray) -> np.ndarray:
    image = np.asarray(frame, dtype=np.float64)
    finite = np.isfinite(image)
    if not np.any(finite):
        raise ValueError("STM frame contains no finite pixels.")
    values = image[finite]
    lower, upper = np.percentile(values, (1.0, 99.0))
    scale = max(float(upper - lower), np.finfo(np.float64).eps)
    normalized = (image - float(lower)) / scale
    normalized[~finite] = float(np.median(normalized[finite]))
    return normalized


def _texture_fields(
    image: np.ndarray,
    setting: TextureSetting,
) -> tuple[np.ndarray, np.ndarray]:
    work = image
    if setting.high_pass_sigma_px > 0.0:
        work = work - ndimage.gaussian_filter(
            work,
            sigma=setting.high_pass_sigma_px,
            mode="nearest",
        )
    if setting.image_sigma_px > 0.0:
        work = ndimage.gaussian_filter(
            work,
            sigma=setting.image_sigma_px,
            mode="nearest",
        )
    gradient_y, gradient_x = np.gradient(work)
    sigma = setting.tensor_sigma_px
    jxx = ndimage.gaussian_filter(
        gradient_x * gradient_x,
        sigma=sigma,
        mode="nearest",
    )
    jyy = ndimage.gaussian_filter(
        gradient_y * gradient_y,
        sigma=sigma,
        mode="nearest",
    )
    jxy = ndimage.gaussian_filter(
        gradient_x * gradient_y,
        sigma=sigma,
        mode="nearest",
    )
    gradient_axis = 0.5 * np.degrees(np.arctan2(2.0 * jxy, jxx - jyy))
    row_axis = (gradient_axis + 90.0) % PERIOD_DEG
    anisotropy = np.sqrt((jxx - jyy) ** 2 + 4.0 * jxy * jxy)
    coherence = anisotropy / np.maximum(
        jxx + jyy,
        np.finfo(np.float64).eps,
    )
    return row_axis, np.clip(coherence, 0.0, 1.0)


def _measure_setting(
    points: list[ReferencePoint],
    images_by_frame: dict[int, np.ndarray],
    setting: TextureSetting,
) -> tuple[np.ndarray, np.ndarray]:
    angles = np.full(len(points), np.nan, dtype=np.float64)
    coherence = np.zeros(len(points), dtype=np.float64)
    point_indices_by_frame: dict[int, list[int]] = defaultdict(list)
    for point_index, point in enumerate(points):
        point_indices_by_frame[point.frame_number].append(point_index)
    for frame_number, point_indices in point_indices_by_frame.items():
        row_axis, frame_coherence = _texture_fields(
            images_by_frame[frame_number],
            setting,
        )
        height, width = row_axis.shape
        for point_index in point_indices:
            point = points[point_index]
            x = int(np.clip(round(point.x_px), 0, width - 1))
            y = int(np.clip(round(point.y_px), 0, height - 1))
            angles[point_index] = float(row_axis[y, x])
            coherence[point_index] = float(frame_coherence[y, x])
    return angles, coherence


def _periodic_mean(
    values: np.ndarray,
    weights: np.ndarray,
) -> float | None:
    if values.size == 0:
        return None
    phases = 2.0 * pi * values / PERIOD_DEG
    mean_x = float(np.sum(weights * np.cos(phases)))
    mean_y = float(np.sum(weights * np.sin(phases)))
    if abs(mean_x) + abs(mean_y) <= 1e-12:
        return None
    return (degrees(atan2(mean_y, mean_x)) % 360.0) * PERIOD_DEG / 360.0


def _fit_prototypes(
    expected: np.ndarray,
    angles: np.ndarray,
    coherence: np.ndarray,
    fit_mask: np.ndarray,
    *,
    minimum_coherence: float,
    weighting: str,
) -> np.ndarray | None:
    prototypes = np.full(len(CLASS_NAMES), np.nan, dtype=np.float64)
    for class_index in range(len(CLASS_NAMES)):
        selected = (
            fit_mask
            & (expected == class_index)
            & np.isfinite(angles)
            & (coherence >= minimum_coherence)
        )
        weights = (
            np.maximum(coherence[selected], 1e-6)
            if weighting == "coherence"
            else np.ones(int(np.count_nonzero(selected)), dtype=np.float64)
        )
        prototype = _periodic_mean(angles[selected], weights)
        if prototype is None:
            return None
        prototypes[class_index] = prototype
    return prototypes


def _distance_matrix(
    angles: np.ndarray,
    prototypes: np.ndarray,
) -> np.ndarray:
    difference = np.abs(angles[:, np.newaxis] - prototypes[np.newaxis, :])
    difference %= PERIOD_DEG
    return np.minimum(difference, PERIOD_DEG - difference)


def _base_predictions(
    angles: np.ndarray,
    coherence: np.ndarray,
    prototypes: np.ndarray,
    *,
    minimum_coherence: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    distances = _distance_matrix(angles, prototypes)
    order = np.argsort(distances, axis=1)
    rows = np.arange(len(angles))
    predicted = order[:, 0].astype(np.int16)
    best_distance = distances[rows, order[:, 0]]
    margin = distances[rows, order[:, 1]] - best_distance
    unavailable = ~np.isfinite(angles) | (coherence < minimum_coherence)
    predicted[unavailable] = UNASSIGNED_INDEX
    best_distance[unavailable] = np.inf
    margin[unavailable] = -np.inf
    return predicted, best_distance, margin


def _apply_rejection(
    predicted: np.ndarray,
    best_distance: np.ndarray,
    margin: np.ndarray,
    *,
    maximum_distance_deg: float,
    minimum_margin_deg: float,
) -> np.ndarray:
    result = predicted.copy()
    rejected = (
        (best_distance > maximum_distance_deg)
        | (margin < minimum_margin_deg)
    )
    result[rejected] = UNASSIGNED_INDEX
    return result


def _metrics(
    points: list[ReferencePoint],
    indices: np.ndarray,
    expected: np.ndarray,
    predicted: np.ndarray,
) -> dict[str, object]:
    confusion = np.zeros(
        (len(CLASS_NAMES), len(CLASS_NAMES) + 1),
        dtype=np.int64,
    )
    for expected_value, predicted_value in zip(
        expected[indices],
        predicted[indices],
    ):
        confusion[int(expected_value), int(predicted_value)] += 1
    per_class = {}
    for class_index, class_name in enumerate(CLASS_NAMES):
        true_positive = int(confusion[class_index, class_index])
        false_positive = int(
            np.sum(confusion[:, class_index]) - true_positive
        )
        false_negative = int(
            np.sum(confusion[class_index, :]) - true_positive
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
            "support": int(np.sum(confusion[class_index, :])),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    assigned = int(np.sum(confusion[:, : len(CLASS_NAMES)]))
    correct = int(
        sum(confusion[index, index] for index in range(len(CLASS_NAMES)))
    )
    grouped: dict[tuple[int, str], list[int]] = defaultdict(list)
    for local_index, point_index in enumerate(indices):
        point = points[int(point_index)]
        grouped[(point.frame_number, point.instance_label)].append(local_index)
    domain_assigned = 0
    domain_correct = 0
    for local_indices in grouped.values():
        votes = Counter(
            int(predicted[indices[value]])
            for value in local_indices
            if int(predicted[indices[value]]) != UNASSIGNED_INDEX
        )
        if not votes:
            continue
        domain_assigned += 1
        domain_prediction = sorted(
            votes.items(),
            key=lambda item: (-item[1], item[0]),
        )[0][0]
        domain_expected = int(expected[indices[local_indices[0]]])
        domain_correct += int(domain_prediction == domain_expected)
    point_count = int(len(indices))
    return {
        "point_count": point_count,
        "assigned_point_count": assigned,
        "coverage": assigned / point_count if point_count else 0.0,
        "assigned_accuracy": correct / assigned if assigned else 0.0,
        "macro_recall": float(
            np.mean([per_class[name]["recall"] for name in CLASS_NAMES])
        ),
        "macro_f1": float(
            np.mean([per_class[name]["f1"] for name in CLASS_NAMES])
        ),
        "domain_count": len(grouped),
        "assigned_domain_count": domain_assigned,
        "domain_coverage": (
            domain_assigned / len(grouped) if grouped else 0.0
        ),
        "assigned_domain_accuracy": (
            domain_correct / domain_assigned if domain_assigned else 0.0
        ),
        "per_class": per_class,
        "confusion": {
            expected_name: {
                **{
                    predicted_name: int(confusion[expected_index, predicted_index])
                    for predicted_index, predicted_name in enumerate(CLASS_NAMES)
                },
                "UNASSIGNED": int(
                    confusion[expected_index, UNASSIGNED_INDEX]
                ),
            }
            for expected_index, expected_name in enumerate(CLASS_NAMES)
        },
    }


def _cross_validated_base_predictions(
    points: list[ReferencePoint],
    expected: np.ndarray,
    angles: np.ndarray,
    coherence: np.ndarray,
    calibration_mask: np.ndarray,
    *,
    minimum_coherence: float,
    weighting: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    predicted = np.full(len(points), UNASSIGNED_INDEX, dtype=np.int16)
    best_distance = np.full(len(points), np.inf, dtype=np.float64)
    margin = np.full(len(points), -np.inf, dtype=np.float64)
    calibration_frames = sorted(
        {point.frame_number for point in points if point.split == "calibration"}
    )
    for frame_number in calibration_frames:
        validation_mask = np.asarray(
            [
                point.split == "calibration"
                and point.frame_number == frame_number
                for point in points
            ],
            dtype=bool,
        )
        prototypes = _fit_prototypes(
            expected,
            angles,
            coherence,
            calibration_mask & ~validation_mask,
            minimum_coherence=minimum_coherence,
            weighting=weighting,
        )
        if prototypes is None:
            return None
        frame_prediction, frame_distance, frame_margin = _base_predictions(
            angles,
            coherence,
            prototypes,
            minimum_coherence=minimum_coherence,
        )
        predicted[validation_mask] = frame_prediction[validation_mask]
        best_distance[validation_mask] = frame_distance[validation_mask]
        margin[validation_mask] = frame_margin[validation_mask]
    return predicted, best_distance, margin


def _rank(metrics: dict[str, object]) -> tuple[float, ...]:
    return (
        float(metrics["macro_f1"]),
        float(metrics["macro_recall"]),
        float(metrics["assigned_domain_accuracy"]),
        float(metrics["domain_coverage"]),
        float(metrics["coverage"]),
        float(metrics["assigned_accuracy"]),
    )


def _normal_rgb(image: np.ndarray) -> Image.Image:
    finite = np.isfinite(image)
    values = image[finite]
    lower, upper = np.percentile(values, (1.0, 99.0))
    scaled = np.zeros(image.shape, dtype=np.float64)
    if upper > lower:
        scaled[finite] = np.clip(
            (image[finite] - lower) / (upper - lower),
            0.0,
            1.0,
        )
    return Image.fromarray(np.uint8(scaled * 255), mode="L").convert("RGB")


def _render_holdout_overlays(
    points: list[ReferencePoint],
    frames_by_number: dict[int, np.ndarray],
    predictions: np.ndarray,
    destination: Path,
) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
    by_frame: dict[int, list[int]] = defaultdict(list)
    for point_index, point in enumerate(points):
        if point.split == "holdout":
            by_frame[point.frame_number].append(point_index)
    for frame_number, point_indices in sorted(by_frame.items()):
        image = _normal_rgb(frames_by_number[frame_number])
        draw = ImageDraw.Draw(image)
        for point_index in point_indices:
            point = points[point_index]
            predicted_index = int(predictions[point_index])
            predicted_name = (
                CLASS_NAMES[predicted_index]
                if predicted_index < len(CLASS_NAMES)
                else "UNASSIGNED"
            )
            x, y = point.x_px, point.y_px
            draw.ellipse(
                (x - 3, y - 3, x + 3, y + 3),
                fill=CLASS_COLORS[predicted_name],
                outline=CLASS_COLORS[point.class_name],
                width=1,
            )
        draw.rectangle((4, 4, 302, 25), fill=(0, 0, 0))
        draw.text(
            (8, 8),
            "fill=prediction, outline=manual reference",
            fill=(255, 255, 255),
            font=font,
        )
        image.resize(
            (image.width * 2, image.height * 2),
            resample=Image.Resampling.NEAREST,
        ).save(destination / f"frame_{frame_number}_texture_prediction.png")


def _load_baseline(path: Path | None) -> dict[str, object] | None:
    if path is None or not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    hybrid = payload.get("hybrid_calibration")
    if not isinstance(hybrid, dict):
        return None
    metrics = hybrid.get("holdout_metrics")
    return metrics if isinstance(metrics, dict) else None


def _write_markdown(report: dict[str, object], destination: Path) -> None:
    selected = report["selected_candidate"]
    cv = selected["calibration_cross_validation_metrics"]
    holdout = selected["holdout_metrics"]
    red = holdout["per_class"]["RED"]
    baseline = report.get("baseline_hybrid_holdout")
    lines = [
        "# TTMAPP local STM texture orientation experiment",
        "",
        "## Protocol",
        "",
        (
            "- Candidate selection: leave-one-frame-out validation on frames "
            "250-262 only."
        ),
        "- Final holdout: frames 263-268, evaluated after candidate selection.",
        (
            "- Scope: only molecules inside manual BLACK, RED and YELLOW "
            "regions; unmarked areas are ignored."
        ),
        "",
        "## Selected candidate",
        "",
        (
            f"- high-pass sigma: `{selected['high_pass_sigma_px']}` px; "
            f"image sigma: `{selected['image_sigma_px']}` px; "
            f"tensor sigma: `{selected['tensor_sigma_px']}` px"
        ),
        (
            f"- minimum coherence: `{selected['minimum_coherence']}`; "
            f"weighting: `{selected['weighting']}`"
        ),
        (
            f"- maximum distance: `{selected['maximum_distance_deg']}` deg; "
            f"minimum margin: `{selected['minimum_margin_deg']}` deg"
        ),
        f"- prototypes: `{selected['prototypes_deg']}`",
        "",
        "## Results",
        "",
        f"- calibration CV macro F1: `{cv['macro_f1']:.3f}`",
        f"- calibration CV coverage: `{cv['coverage']:.3f}`",
        f"- holdout macro F1: `{holdout['macro_f1']:.3f}`",
        f"- holdout coverage: `{holdout['coverage']:.3f}`",
        (
            "- holdout assigned point accuracy: "
            f"`{holdout['assigned_accuracy']:.3f}`"
        ),
        (
            "- holdout assigned-domain accuracy: "
            f"`{holdout['assigned_domain_accuracy']:.3f}`"
        ),
        (
            f"- holdout RED precision/recall/F1: "
            f"`{red['precision']:.3f}` / `{red['recall']:.3f}` / "
            f"`{red['f1']:.3f}`"
        ),
    ]
    if baseline is not None:
        lines.extend(
            [
                "",
                "## Previous hybrid baseline",
                "",
                f"- holdout macro F1: `{baseline['macro_f1']:.3f}`",
                (
                    "- holdout assigned-domain accuracy: "
                    f"`{baseline['assigned_domain_accuracy']:.3f}`"
                ),
            ]
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            str(report["decision"]),
            "",
        ]
    )
    destination.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = _parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    points = _read_reference(args.reference_csv)
    frame_numbers = sorted({point.frame_number for point in points})
    print(f"Loading session for frames {frame_numbers[0]}-{frame_numbers[-1]}...")
    session = load_moltrack_session(args.session)
    series = restore_moltrack_image_series_from_session(session)
    source_view = session.position_analysis.source_view
    if source_view == "expanded_aligned":
        print("Building expanded aligned STM stack...", flush=True)
        source_frames = build_moltrack_expanded_aligned_stack(series).frames
    else:
        source_frames = series.raw_frames
    raw_frames_by_number = {
        frame_number: np.asarray(source_frames[frame_number - 1])
        for frame_number in frame_numbers
    }
    images_by_frame = {
        frame_number: _prepare_image(frame)
        for frame_number, frame in raw_frames_by_number.items()
    }
    expected = np.asarray(
        [CLASS_INDEX[point.class_name] for point in points],
        dtype=np.int16,
    )
    calibration_mask = np.asarray(
        [point.split == "calibration" for point in points],
        dtype=bool,
    )
    holdout_mask = np.asarray(
        [point.split == "holdout" for point in points],
        dtype=bool,
    )
    calibration_indices = np.flatnonzero(calibration_mask)
    holdout_indices = np.flatnonzero(holdout_mask)
    settings = [
        TextureSetting(high_pass, image_sigma, tensor_sigma)
        for high_pass in (0.0, 6.0, 12.0)
        for image_sigma in (0.5, 1.25, 2.0)
        for tensor_sigma in (3.0, 5.0, 8.0, 12.0, 18.0)
    ]
    measurements: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    best: tuple[
        tuple[float, ...],
        dict[str, object],
        np.ndarray,
        np.ndarray,
        np.ndarray,
    ] | None = None
    sweep_rows = []
    for setting_index, setting in enumerate(settings, start=1):
        print(
            f"Texture fields {setting_index}/{len(settings)}: "
            f"{setting.setting_id}",
            flush=True,
        )
        angles, coherence = _measure_setting(
            points,
            images_by_frame,
            setting,
        )
        measurements[setting.setting_id] = (angles, coherence)
        for minimum_coherence in (0.0, 0.1, 0.2, 0.3, 0.4):
            for weighting in ("uniform", "coherence"):
                base = _cross_validated_base_predictions(
                    points,
                    expected,
                    angles,
                    coherence,
                    calibration_mask,
                    minimum_coherence=minimum_coherence,
                    weighting=weighting,
                )
                if base is None:
                    continue
                base_prediction, base_distance, base_margin = base
                for maximum_distance in (12.0, 20.0, 30.0, 45.0, 90.0):
                    for minimum_margin in (0.0, 5.0, 10.0, 15.0):
                        predictions = _apply_rejection(
                            base_prediction,
                            base_distance,
                            base_margin,
                            maximum_distance_deg=maximum_distance,
                            minimum_margin_deg=minimum_margin,
                        )
                        metrics = _metrics(
                            points,
                            calibration_indices,
                            expected,
                            predictions,
                        )
                        row = {
                            "setting_id": setting.setting_id,
                            "high_pass_sigma_px": setting.high_pass_sigma_px,
                            "image_sigma_px": setting.image_sigma_px,
                            "tensor_sigma_px": setting.tensor_sigma_px,
                            "minimum_coherence": minimum_coherence,
                            "weighting": weighting,
                            "maximum_distance_deg": maximum_distance,
                            "minimum_margin_deg": minimum_margin,
                            "macro_f1": metrics["macro_f1"],
                            "macro_recall": metrics["macro_recall"],
                            "coverage": metrics["coverage"],
                            "assigned_accuracy": metrics["assigned_accuracy"],
                            "domain_coverage": metrics["domain_coverage"],
                            "assigned_domain_accuracy": metrics[
                                "assigned_domain_accuracy"
                            ],
                        }
                        sweep_rows.append(row)
                        candidate = (
                            _rank(metrics),
                            row,
                            predictions,
                            angles,
                            coherence,
                        )
                        if best is None or candidate[0] > best[0]:
                            best = candidate
    if best is None:
        raise RuntimeError("No local-texture candidate could be evaluated.")
    _best_rank, selected_row, calibration_predictions, angles, coherence = best
    selected_setting = next(
        value
        for value in settings
        if value.setting_id == selected_row["setting_id"]
    )
    prototypes = _fit_prototypes(
        expected,
        angles,
        coherence,
        calibration_mask,
        minimum_coherence=float(selected_row["minimum_coherence"]),
        weighting=str(selected_row["weighting"]),
    )
    if prototypes is None:
        raise RuntimeError("Selected candidate has no final prototypes.")
    base_prediction, base_distance, base_margin = _base_predictions(
        angles,
        coherence,
        prototypes,
        minimum_coherence=float(selected_row["minimum_coherence"]),
    )
    holdout_predictions = _apply_rejection(
        base_prediction,
        base_distance,
        base_margin,
        maximum_distance_deg=float(selected_row["maximum_distance_deg"]),
        minimum_margin_deg=float(selected_row["minimum_margin_deg"]),
    )
    final_predictions = calibration_predictions.copy()
    final_predictions[holdout_mask] = holdout_predictions[holdout_mask]
    calibration_metrics = _metrics(
        points,
        calibration_indices,
        expected,
        final_predictions,
    )
    holdout_metrics = _metrics(
        points,
        holdout_indices,
        expected,
        final_predictions,
    )
    sweep_rows.sort(
        key=lambda row: (
            -float(row["macro_f1"]),
            -float(row["macro_recall"]),
            -float(row["assigned_domain_accuracy"]),
            -float(row["domain_coverage"]),
            -float(row["coverage"]),
        )
    )
    with (args.output_dir / "row_texture_sweep.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(sweep_rows[0]))
        writer.writeheader()
        writer.writerows(sweep_rows)
    measurement_rows = []
    for point_index, point in enumerate(points):
        prediction_index = int(final_predictions[point_index])
        measurement_rows.append(
            {
                "frame_number": point.frame_number,
                "split": point.split,
                "class_name": point.class_name,
                "instance_label": point.instance_label,
                "source_id": point.source_id,
                "x_px": point.x_px,
                "y_px": point.y_px,
                "row_texture_axis_deg": float(angles[point_index]),
                "texture_coherence": float(coherence[point_index]),
                "predicted_class": (
                    CLASS_NAMES[prediction_index]
                    if prediction_index < len(CLASS_NAMES)
                    else "UNASSIGNED"
                ),
                "correct": (
                    prediction_index == CLASS_INDEX[point.class_name]
                ),
            }
        )
    with (args.output_dir / "row_texture_measurements.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=tuple(measurement_rows[0]),
        )
        writer.writeheader()
        writer.writerows(measurement_rows)
    baseline = _load_baseline(args.baseline_report)
    baseline_f1 = (
        None if baseline is None else float(baseline["macro_f1"])
    )
    holdout_f1 = float(holdout_metrics["macro_f1"])
    red_f1 = float(holdout_metrics["per_class"]["RED"]["f1"])
    if (
        holdout_f1 >= 0.7
        and red_f1 >= 0.6
        and float(holdout_metrics["domain_coverage"]) >= 0.8
    ):
        decision = (
            "The local texture descriptor is strong enough to integrate as "
            "an experimental domain-orientation feature, followed by "
            "independent-acquisition validation."
        )
    elif baseline_f1 is not None and holdout_f1 > baseline_f1:
        decision = (
            "Local texture improves the previous hybrid baseline but is not "
            "reliable enough for a preset. The next experiment should combine "
            "texture with neighborhood row geometry using calibration-only "
            "selection."
        )
    else:
        decision = (
            "Local structure-tensor orientation does not improve the previous "
            "hybrid baseline sufficiently. Do not add it to the preset; test "
            "a local FFT/Gabor or neighborhood row-geometry descriptor next."
        )
    selected_candidate = {
        **selected_row,
        "prototypes_deg": {
            name: float(prototypes[index])
            for index, name in enumerate(CLASS_NAMES)
        },
        "calibration_cross_validation_metrics": calibration_metrics,
        "holdout_metrics": holdout_metrics,
    }
    report = {
        "status": "completed",
        "experiment": "local_stm_structure_tensor_row_orientation",
        "source_session": str(args.session.resolve()),
        "source_view": source_view,
        "reference_csv": str(args.reference_csv.resolve()),
        "reference_scope": (
            "Only molecules in manual BLACK, RED and YELLOW regions are "
            "evaluated. Unmarked regions are ignored."
        ),
        "protocol": {
            "selection": (
                "Leave-one-frame-out cross-validation on calibration frames."
            ),
            "calibration_frames": sorted(
                {
                    point.frame_number
                    for point in points
                    if point.split == "calibration"
                }
            ),
            "holdout_frames": sorted(
                {
                    point.frame_number
                    for point in points
                    if point.split == "holdout"
                }
            ),
            "holdout_used_for_selection": False,
            "candidate_count": len(sweep_rows),
        },
        "reference_counts": {
            "total": len(points),
            "by_split": dict(Counter(point.split for point in points)),
            "by_class": dict(Counter(point.class_name for point in points)),
        },
        "selected_candidate": selected_candidate,
        "baseline_hybrid_holdout": baseline,
        "decision": decision,
    }
    (args.output_dir / "row_texture_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    _write_markdown(
        report,
        args.output_dir / "row_texture_report.md",
    )
    _render_holdout_overlays(
        points,
        raw_frames_by_number,
        final_predictions,
        args.output_dir / "holdout_overlays",
    )
    print(json.dumps(selected_candidate, indent=2), flush=True)
    print(f"Decision: {decision}", flush=True)
    print(f"Output: {args.output_dir.resolve()}", flush=True)


if __name__ == "__main__":
    main()
