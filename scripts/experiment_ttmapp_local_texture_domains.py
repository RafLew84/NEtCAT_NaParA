"""Evaluate local STM texture as a three-class domain-orientation descriptor."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.spatial import cKDTree


CLASS_NAMES = ("BLACK", "RED", "YELLOW")
CLASS_INDEX = {name: index for index, name in enumerate(CLASS_NAMES)}
CLASS_COLORS = {
    "BLACK": (20, 20, 20),
    "RED": (240, 45, 40),
    "YELLOW": (245, 205, 0),
}


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
class DescriptorConfig:
    radius_px: int
    high_pass_sigma_px: float
    histogram_sigma_bins: float
    radial_weighting: str

    @property
    def key(self) -> str:
        return (
            f"r{self.radius_px}_hp{self.high_pass_sigma_px:g}_"
            f"hs{self.histogram_sigma_bins:g}_{self.radial_weighting}"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference_csv", type=Path)
    parser.add_argument("review_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument(
        "--extra-review-dir",
        action="append",
        type=Path,
        default=[],
    )
    parser.add_argument("--render-scale", type=float, default=2.0)
    return parser.parse_args()


def _load_reference(path: Path) -> tuple[ReferencePoint, ...]:
    points: list[ReferencePoint] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            class_name = row["class_name"].strip().upper()
            if class_name not in CLASS_INDEX:
                continue
            points.append(
                ReferencePoint(
                    frame_number=int(row["frame_number"]),
                    split=row["split"].strip(),
                    class_name=class_name,
                    instance_label=row["instance_label"].strip(),
                    source_id=row["source_id"].strip(),
                    x_px=float(row["x_px"]),
                    y_px=float(row["y_px"]),
                )
            )
    if not points:
        raise ValueError(f"No reference points found in {path}.")
    return tuple(points)


def _resolve_clean_images(
    frame_numbers: set[int],
    review_dirs: tuple[Path, ...],
) -> dict[int, Path]:
    paths: dict[int, Path] = {}
    for frame_number in sorted(frame_numbers):
        name = f"frame_{frame_number}_clean_registered.png"
        matches = [directory / name for directory in review_dirs]
        path = next((candidate for candidate in matches if candidate.is_file()), None)
        if path is None:
            raise FileNotFoundError(
                f"Cannot find {name} in: "
                + ", ".join(str(directory) for directory in review_dirs)
            )
        paths[frame_number] = path
    return paths


def _valid_fov(image: np.ndarray) -> np.ndarray:
    foreground = ndimage.binary_fill_holes(
        ndimage.binary_closing(
            ndimage.binary_dilation(image > 0.0, iterations=2),
            iterations=8,
        )
    )
    labels, count = ndimage.label(foreground)
    if count == 0:
        return np.ones(image.shape, dtype=bool)
    sizes = ndimage.sum(foreground, labels, range(1, count + 1))
    return labels == (int(np.argmax(sizes)) + 1)


def _gradient_fields(
    image_path: Path,
    sigma: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    image = np.asarray(Image.open(image_path).convert("L"), dtype=np.float64)
    valid = _valid_fov(image)
    valid_float = valid.astype(np.float64)
    numerator = ndimage.gaussian_filter(
        image * valid_float,
        sigma=sigma,
        mode="nearest",
    )
    denominator = ndimage.gaussian_filter(
        valid_float,
        sigma=sigma,
        mode="nearest",
    )
    smooth = np.divide(
        numerator,
        denominator,
        out=np.zeros_like(numerator),
        where=denominator > 1e-6,
    )
    high_pass = np.where(valid, image - smooth, 0.0)
    gradient_rows, gradient_columns = np.gradient(high_pass)
    angle = np.degrees(np.arctan2(-gradient_rows, gradient_columns)) % 180.0
    energy = gradient_rows * gradient_rows + gradient_columns * gradient_columns
    support = ndimage.binary_erosion(valid, iterations=2)
    return angle, energy, support


def _local_histogram(
    angle: np.ndarray,
    energy: np.ndarray,
    valid: np.ndarray,
    *,
    center_x: float,
    center_y: float,
    radius: int,
    histogram_sigma: float,
    radial_weighting: str,
) -> np.ndarray | None:
    height, width = angle.shape
    left = max(0, int(np.floor(center_x - radius)))
    right = min(width, int(np.ceil(center_x + radius + 1)))
    top = max(0, int(np.floor(center_y - radius)))
    bottom = min(height, int(np.ceil(center_y + radius + 1)))
    if left >= right or top >= bottom:
        return None
    rows, columns = np.ogrid[top:bottom, left:right]
    distance_squared = (
        (columns - center_x) * (columns - center_x)
        + (rows - center_y) * (rows - center_y)
    )
    disk = distance_squared <= float(radius * radius)
    local_valid = valid[top:bottom, left:right] & disk
    expected_area = np.pi * radius * radius
    if np.count_nonzero(local_valid) < max(120, 0.35 * expected_area):
        return None
    local_energy = energy[top:bottom, left:right][local_valid]
    if radial_weighting == "gaussian":
        radial = np.exp(
            -distance_squared[local_valid]
            / (2.0 * (max(radius / 2.0, 1.0) ** 2))
        )
        local_energy = local_energy * radial
    total_energy = float(np.sum(local_energy))
    if not np.isfinite(total_energy) or total_energy <= 1e-12:
        return None
    histogram, _ = np.histogram(
        angle[top:bottom, left:right][local_valid],
        bins=90,
        range=(0.0, 180.0),
        weights=local_energy,
    )
    histogram = ndimage.gaussian_filter1d(
        histogram.astype(np.float64),
        sigma=histogram_sigma,
        mode="wrap",
    )
    total = float(np.sum(histogram))
    if not np.isfinite(total) or total <= 1e-12:
        return None
    return histogram / total


def _descriptor_matrix(
    points: tuple[ReferencePoint, ...],
    image_paths: dict[int, Path],
    config: DescriptorConfig,
    *,
    render_scale: float,
) -> np.ndarray:
    matrix = np.full((len(points), 90), np.nan, dtype=np.float64)
    by_frame: dict[int, list[int]] = defaultdict(list)
    for index, point in enumerate(points):
        by_frame[point.frame_number].append(index)
    for frame_number, indices in sorted(by_frame.items()):
        angle, energy, valid = _gradient_fields(
            image_paths[frame_number],
            config.high_pass_sigma_px,
        )
        for index in indices:
            point = points[index]
            descriptor = _local_histogram(
                angle,
                energy,
                valid,
                center_x=point.x_px * render_scale,
                center_y=point.y_px * render_scale,
                radius=config.radius_px,
                histogram_sigma=config.histogram_sigma_bins,
                radial_weighting=config.radial_weighting,
            )
            if descriptor is not None:
                matrix[index] = descriptor
    return matrix


def _prototypes(
    descriptors: np.ndarray,
    points: tuple[ReferencePoint, ...],
    indices: np.ndarray,
) -> np.ndarray:
    values = np.zeros((len(CLASS_NAMES), descriptors.shape[1]), dtype=np.float64)
    for class_index, class_name in enumerate(CLASS_NAMES):
        selected = np.asarray(
            [
                index
                for index in indices
                if points[int(index)].class_name == class_name
                and np.all(np.isfinite(descriptors[int(index)]))
            ],
            dtype=np.int64,
        )
        if not selected.size:
            raise ValueError(f"No descriptor samples for class {class_name}.")
        values[class_index] = np.mean(descriptors[selected], axis=0)
        values[class_index] /= max(float(np.sum(values[class_index])), 1e-12)
    return values


def _cosine_distances(
    descriptors: np.ndarray,
    prototypes: np.ndarray,
) -> np.ndarray:
    descriptor_norm = np.linalg.norm(descriptors, axis=1, keepdims=True)
    prototype_norm = np.linalg.norm(prototypes, axis=1, keepdims=True).T
    similarities = np.divide(
        descriptors @ prototypes.T,
        descriptor_norm * prototype_norm,
        out=np.zeros((len(descriptors), len(prototypes)), dtype=np.float64),
        where=(descriptor_norm * prototype_norm) > 1e-12,
    )
    distances = 1.0 - similarities
    distances[~np.all(np.isfinite(descriptors), axis=1)] = np.inf
    return distances


def _neighbor_graph(
    points: tuple[ReferencePoint, ...],
    *,
    minimum_distance_px: float = 7.5,
    maximum_distance_px: float = 18.0,
) -> tuple[np.ndarray, ...]:
    neighbors: list[list[int]] = [[] for _ in points]
    by_frame: dict[int, list[int]] = defaultdict(list)
    for index, point in enumerate(points):
        by_frame[point.frame_number].append(index)
    for indices in by_frame.values():
        coordinates = np.asarray(
            [(points[index].x_px, points[index].y_px) for index in indices],
            dtype=np.float64,
        )
        if len(coordinates) < 2:
            continue
        tree = cKDTree(coordinates)
        for local_left, local_right in tree.query_pairs(maximum_distance_px):
            distance = float(
                np.linalg.norm(
                    coordinates[local_left] - coordinates[local_right]
                )
            )
            if distance < minimum_distance_px:
                continue
            left = indices[local_left]
            right = indices[local_right]
            neighbors[left].append(right)
            neighbors[right].append(left)
    return tuple(np.asarray(value, dtype=np.int64) for value in neighbors)


def _spatial_predictions(
    distances: np.ndarray,
    neighbors: tuple[np.ndarray, ...],
    *,
    neighbor_lambda: float,
    rounds: int,
) -> np.ndarray:
    predictions = np.argmin(distances, axis=1)
    invalid = ~np.any(np.isfinite(distances), axis=1)
    predictions[invalid] = -1
    if neighbor_lambda <= 0.0:
        return predictions
    for _ in range(rounds):
        updated = predictions.copy()
        for index, adjacent in enumerate(neighbors):
            if predictions[index] < 0 or not adjacent.size:
                continue
            votes = predictions[adjacent]
            votes = votes[votes >= 0]
            if not votes.size:
                continue
            fractions = (
                np.bincount(votes, minlength=len(CLASS_NAMES)) / len(votes)
            )
            adjusted = distances[index] - neighbor_lambda * fractions
            updated[index] = int(np.argmin(adjusted))
        predictions = updated
    return predictions


def _metrics(
    points: tuple[ReferencePoint, ...],
    indices: np.ndarray,
    predictions: np.ndarray,
) -> dict[str, object]:
    confusion = np.zeros((len(CLASS_NAMES), len(CLASS_NAMES) + 1), dtype=int)
    domain_votes: dict[tuple[int, str, str], list[int]] = defaultdict(list)
    for index in indices:
        point = points[int(index)]
        expected = CLASS_INDEX[point.class_name]
        predicted = int(predictions[int(index)])
        confusion[expected, predicted if predicted >= 0 else len(CLASS_NAMES)] += 1
        domain_votes[
            (point.frame_number, point.instance_label, point.class_name)
        ].append(predicted)
    f1_values: list[float] = []
    recalls: list[float] = []
    for class_index in range(len(CLASS_NAMES)):
        true_positive = int(confusion[class_index, class_index])
        false_positive = int(np.sum(confusion[:, class_index])) - true_positive
        false_negative = int(np.sum(confusion[class_index])) - true_positive
        precision = true_positive / max(true_positive + false_positive, 1)
        recall = true_positive / max(true_positive + false_negative, 1)
        f1_values.append(
            0.0
            if precision + recall <= 0.0
            else 2.0 * precision * recall / (precision + recall)
        )
        recalls.append(recall)
    assigned = int(np.sum(confusion[:, : len(CLASS_NAMES)]))
    correct = int(sum(confusion[index, index] for index in range(len(CLASS_NAMES))))
    domain_correct = 0
    domain_rows = []
    for (frame, instance, expected_name), values in sorted(domain_votes.items()):
        assigned_values = [value for value in values if value >= 0]
        predicted_name = "UNKNOWN"
        if assigned_values:
            counts = Counter(assigned_values)
            best_count = max(counts.values())
            predicted_index = min(
                value for value, count in counts.items() if count == best_count
            )
            predicted_name = CLASS_NAMES[predicted_index]
        domain_correct += int(predicted_name == expected_name)
        domain_rows.append(
            {
                "frame_number": frame,
                "instance_label": instance,
                "expected": expected_name,
                "predicted": predicted_name,
                "point_count": len(values),
                "assigned_count": len(assigned_values),
                "votes": {
                    name: values.count(class_index)
                    for class_index, name in enumerate(CLASS_NAMES)
                },
            }
        )
    return {
        "point_count": int(len(indices)),
        "coverage": assigned / max(len(indices), 1),
        "accuracy": correct / max(len(indices), 1),
        "assigned_accuracy": correct / max(assigned, 1),
        "macro_f1": float(np.mean(f1_values)),
        "balanced_accuracy": float(np.mean(recalls)),
        "domain_count": len(domain_rows),
        "domain_accuracy": domain_correct / max(len(domain_rows), 1),
        "confusion": {
            expected: {
                **{
                    predicted: int(confusion[row, column])
                    for column, predicted in enumerate(CLASS_NAMES)
                },
                "UNKNOWN": int(confusion[row, len(CLASS_NAMES)]),
            }
            for row, expected in enumerate(CLASS_NAMES)
        },
        "domains": domain_rows,
    }


def _leave_one_frame_out_predictions(
    descriptors: np.ndarray,
    points: tuple[ReferencePoint, ...],
    calibration_indices: np.ndarray,
) -> np.ndarray:
    predictions_distances = np.full(
        (len(points), len(CLASS_NAMES)),
        np.inf,
        dtype=np.float64,
    )
    calibration_frames = sorted(
        {points[int(index)].frame_number for index in calibration_indices}
    )
    for held_out_frame in calibration_frames:
        training = np.asarray(
            [
                index
                for index in calibration_indices
                if points[int(index)].frame_number != held_out_frame
            ],
            dtype=np.int64,
        )
        held_out = np.asarray(
            [
                index
                for index in calibration_indices
                if points[int(index)].frame_number == held_out_frame
            ],
            dtype=np.int64,
        )
        prototypes = _prototypes(descriptors, points, training)
        predictions_distances[held_out] = _cosine_distances(
            descriptors[held_out],
            prototypes,
        )
    return predictions_distances


def _thresholds(
    distances: np.ndarray,
    points: tuple[ReferencePoint, ...],
    calibration_indices: np.ndarray,
) -> tuple[np.ndarray, float]:
    per_class = np.zeros(len(CLASS_NAMES), dtype=np.float64)
    correct_margins: list[float] = []
    for class_index, class_name in enumerate(CLASS_NAMES):
        own_distances = []
        for index in calibration_indices:
            if points[int(index)].class_name != class_name:
                continue
            row = distances[int(index)]
            if not np.all(np.isfinite(row)):
                continue
            own_distances.append(float(row[class_index]))
            ordered = np.sort(row)
            if int(np.argmin(row)) == class_index:
                correct_margins.append(float(ordered[1] - ordered[0]))
        per_class[class_index] = (
            float(np.quantile(own_distances, 0.975))
            if own_distances
            else np.inf
        )
    margin = (
        max(0.0, float(np.quantile(correct_margins, 0.025)))
        if correct_margins
        else 0.0
    )
    return per_class, margin


def _apply_unknown(
    predictions: np.ndarray,
    distances: np.ndarray,
    *,
    thresholds: np.ndarray,
    minimum_margin: float,
) -> np.ndarray:
    result = predictions.copy()
    for index, predicted in enumerate(predictions):
        if predicted < 0:
            continue
        ordered = np.sort(distances[index])
        margin = float(ordered[1] - ordered[0])
        if (
            distances[index, predicted] > thresholds[predicted]
            or margin < minimum_margin
        ):
            result[index] = -1
    return result


def _write_predictions(
    path: Path,
    points: tuple[ReferencePoint, ...],
    indices: np.ndarray,
    nearest: np.ndarray,
    with_unknown: np.ndarray,
    distances: np.ndarray,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            (
                "frame_number",
                "instance_label",
                "source_id",
                "expected",
                "predicted_nearest",
                "predicted_with_unknown",
                "distance_black",
                "distance_red",
                "distance_yellow",
            )
        )
        for index in indices:
            point = points[int(index)]
            writer.writerow(
                (
                    point.frame_number,
                    point.instance_label,
                    point.source_id,
                    point.class_name,
                    (
                        CLASS_NAMES[int(nearest[int(index)])]
                        if nearest[int(index)] >= 0
                        else "UNKNOWN"
                    ),
                    (
                        CLASS_NAMES[int(with_unknown[int(index)])]
                        if with_unknown[int(index)] >= 0
                        else "UNKNOWN"
                    ),
                    *(
                        f"{value:.9g}"
                        for value in distances[int(index)]
                    ),
                )
            )


def _write_overlays(
    output_dir: Path,
    image_paths: dict[int, Path],
    points: tuple[ReferencePoint, ...],
    indices: np.ndarray,
    predictions: np.ndarray,
    *,
    render_scale: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    by_frame: dict[int, list[int]] = defaultdict(list)
    for index in indices:
        by_frame[points[int(index)].frame_number].append(int(index))
    for frame_number, frame_indices in sorted(by_frame.items()):
        image = Image.open(image_paths[frame_number]).convert("RGB")
        draw = ImageDraw.Draw(image)
        for index in frame_indices:
            point = points[index]
            predicted = int(predictions[index])
            color = (
                (150, 150, 150)
                if predicted < 0
                else CLASS_COLORS[CLASS_NAMES[predicted]]
            )
            x = point.x_px * render_scale
            y = point.y_px * render_scale
            radius = 5
            expected_color = CLASS_COLORS[point.class_name]
            draw.ellipse(
                (x - radius - 2, y - radius - 2, x + radius + 2, y + radius + 2),
                outline=(255, 255, 255),
                width=2,
            )
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                fill=color,
                outline=expected_color,
                width=2,
            )
        image.save(output_dir / f"frame_{frame_number}_local_predictions.png")


def _write_report(
    output_dir: Path,
    payload: dict[str, object],
) -> None:
    selected = payload["selected_candidate"]
    holdout = payload["holdout"]
    nearest = holdout["local_only"]["nearest"]
    unknown = holdout["local_only"]["with_unknown"]
    smoothed = holdout["reference_graph_smoothed"]["nearest"]
    lines = [
        "# TTMAPP local texture domain experiment",
        "",
        "## Question",
        "",
        (
            "Can BLACK, RED and YELLOW domain orientations be recognized from "
            "a local STM neighborhood around each molecule, without using the "
            "manual domain boundary during prediction?"
        ),
        "",
        "## Split and selection",
        "",
        "- Parameter selection: leave-one-frame-out on frames 250-262.",
        "- Final temporal holdout: frames 263-268.",
        (
            "- Manual outlines are used only to assign reference labels and "
            "score predictions."
        ),
        "",
        "## Selected local descriptor",
        "",
        f"- Radius: {selected['radius_px']} rendered px.",
        f"- High-pass Gaussian sigma: {selected['high_pass_sigma_px']} px.",
        (
            "- Histogram smoothing sigma: "
            f"{selected['histogram_sigma_bins']} bins."
        ),
        f"- Radial weighting: {selected['radial_weighting']}.",
        "- Primary selection uses no neighbor voting.",
        "",
        "## Temporal holdout result",
        "",
        f"- Nearest-class point macro F1: {nearest['macro_f1']:.3f}.",
        f"- Nearest-class point accuracy: {nearest['accuracy']:.3f}.",
        f"- Nearest-class domain accuracy: {nearest['domain_accuracy']:.3f}.",
        f"- With UNKNOWN point macro F1: {unknown['macro_f1']:.3f}.",
        f"- With UNKNOWN point coverage: {unknown['coverage']:.3f}.",
        f"- With UNKNOWN domain accuracy: {unknown['domain_accuracy']:.3f}.",
        (
            "- Diagnostic reference-graph point macro F1: "
            f"{smoothed['macro_f1']:.3f}."
        ),
        (
            "- Diagnostic reference-graph domain accuracy: "
            f"{smoothed['domain_accuracy']:.3f}."
        ),
        "",
        "## Interpretation",
        "",
    ]
    if nearest["domain_accuracy"] >= 0.85 and nearest["macro_f1"] >= 0.65:
        lines.extend(
            [
                (
                    "The local texture signal is sufficiently informative to "
                    "continue with autonomous spatial grouping and boundary "
                    "reconstruction."
                ),
                (
                    "This does not yet prove generalization to another movie; "
                    "all frames come from one correlated sequence."
                ),
            ]
        )
    else:
        lines.extend(
            [
                (
                    "The local descriptor alone is not yet reliable enough for "
                    "automatic three-way domain assignment."
                ),
                (
                    "The next iteration should combine local texture with a "
                    "larger multi-scale context before implementing autonomous "
                    "domain boundaries."
                ),
            ]
        )
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            "- `candidate_sweep.csv`: all calibration candidates.",
            "- `holdout_predictions.csv`: molecule-level holdout predictions.",
            "- `holdout_overlays/`: holdout frames with local-only predictions.",
            "- `experiment_report.json`: complete metrics and parameters.",
            "",
        ]
    )
    (output_dir / "experiment_report.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    args = _parse_args()
    points = _load_reference(args.reference_csv)
    image_paths = _resolve_clean_images(
        {point.frame_number for point in points},
        (args.review_dir, *tuple(args.extra_review_dir)),
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)

    calibration_indices = np.asarray(
        [
            index
            for index, point in enumerate(points)
            if point.split == "calibration"
        ],
        dtype=np.int64,
    )
    holdout_indices = np.asarray(
        [
            index
            for index, point in enumerate(points)
            if point.split != "calibration"
        ],
        dtype=np.int64,
    )
    neighbors = _neighbor_graph(points)
    configs = [
        DescriptorConfig(radius, high_pass, histogram_sigma, radial)
        for radius in (16, 24, 32, 48, 64)
        for high_pass in (4.0, 8.0, 12.0)
        for histogram_sigma in (1.5, 3.0)
        for radial in ("uniform", "gaussian")
    ]
    smoothing_candidates = (
        (0.0, 1),
        (0.01, 1),
        (0.02, 1),
        (0.02, 2),
        (0.05, 1),
        (0.05, 2),
    )

    sweep_rows: list[dict[str, object]] = []
    best: tuple[tuple[float, ...], DescriptorConfig, np.ndarray] | None = None
    for config in configs:
        print(f"Extracting local descriptors: {config.key}", flush=True)
        descriptors = _descriptor_matrix(
            points,
            image_paths,
            config,
            render_scale=args.render_scale,
        )
        lofo_distances = _leave_one_frame_out_predictions(
            descriptors,
            points,
            calibration_indices,
        )
        for neighbor_lambda, rounds in smoothing_candidates:
            predictions = _spatial_predictions(
                lofo_distances,
                neighbors,
                neighbor_lambda=neighbor_lambda,
                rounds=rounds,
            )
            metrics = _metrics(points, calibration_indices, predictions)
            row = {
                "descriptor_key": config.key,
                "radius_px": config.radius_px,
                "high_pass_sigma_px": config.high_pass_sigma_px,
                "histogram_sigma_bins": config.histogram_sigma_bins,
                "radial_weighting": config.radial_weighting,
                "neighbor_lambda": neighbor_lambda,
                "neighbor_rounds": rounds,
                "lofo_macro_f1": metrics["macro_f1"],
                "lofo_accuracy": metrics["accuracy"],
                "lofo_balanced_accuracy": metrics["balanced_accuracy"],
                "lofo_domain_accuracy": metrics["domain_accuracy"],
                "lofo_coverage": metrics["coverage"],
            }
            sweep_rows.append(row)
            rank = (
                float(metrics["macro_f1"]),
                float(metrics["domain_accuracy"]),
                float(metrics["balanced_accuracy"]),
                -float(config.radius_px),
                -float(neighbor_lambda),
            )
            if neighbor_lambda == 0.0 and (best is None or rank > best[0]):
                best = (
                    rank,
                    config,
                    descriptors.copy(),
                )
    if best is None:
        raise RuntimeError("No descriptor candidate was evaluated.")

    _, config, descriptors = best
    prototypes = _prototypes(descriptors, points, calibration_indices)
    all_distances = _cosine_distances(descriptors, prototypes)
    local_nearest = _spatial_predictions(
        all_distances,
        neighbors,
        neighbor_lambda=0.0,
        rounds=1,
    )
    thresholds, minimum_margin = _thresholds(
        all_distances,
        points,
        calibration_indices,
    )
    local_with_unknown = _apply_unknown(
        local_nearest,
        all_distances,
        thresholds=thresholds,
        minimum_margin=minimum_margin,
    )
    selected_sweep = next(
        (
            row
            for row in sweep_rows
            if row["descriptor_key"] == config.key
            and float(row["neighbor_lambda"]) == 0.0
        ),
    )
    smoothed_sweep = max(
        (row for row in sweep_rows if row["descriptor_key"] == config.key),
        key=lambda row: (
            float(row["lofo_macro_f1"]),
            float(row["lofo_domain_accuracy"]),
        ),
    )
    smoothed_nearest = _spatial_predictions(
        all_distances,
        neighbors,
        neighbor_lambda=float(smoothed_sweep["neighbor_lambda"]),
        rounds=int(smoothed_sweep["neighbor_rounds"]),
    )
    smoothed_with_unknown = _apply_unknown(
        smoothed_nearest,
        all_distances,
        thresholds=thresholds,
        minimum_margin=minimum_margin,
    )
    payload: dict[str, object] = {
        "status": "single_sequence_local_texture_experiment",
        "reference_csv": str(args.reference_csv),
        "reference_scope": (
            "Manual regions assign evaluation labels only; descriptors do not "
            "use manual domain boundaries."
        ),
        "calibration_frames": sorted(
            {
                points[int(index)].frame_number
                for index in calibration_indices
            }
        ),
        "holdout_frames": sorted(
            {points[int(index)].frame_number for index in holdout_indices}
        ),
        "selected_candidate": {
            **selected_sweep,
            "prototype_histograms": {
                name: [float(value) for value in prototypes[class_index]]
                for class_index, name in enumerate(CLASS_NAMES)
            },
            "unknown_distance_thresholds": {
                name: float(thresholds[class_index])
                for class_index, name in enumerate(CLASS_NAMES)
            },
            "unknown_minimum_margin": minimum_margin,
        },
        "diagnostic_reference_graph": {
            "scope_warning": (
                "The graph contains only manually labelled reference points, "
                "so this result is diagnostic and not an autonomous inference "
                "metric."
            ),
            "neighbor_lambda": smoothed_sweep["neighbor_lambda"],
            "neighbor_rounds": smoothed_sweep["neighbor_rounds"],
            "lofo_macro_f1": smoothed_sweep["lofo_macro_f1"],
            "lofo_domain_accuracy": smoothed_sweep["lofo_domain_accuracy"],
        },
        "holdout": {
            "local_only": {
                "nearest": _metrics(
                    points,
                    holdout_indices,
                    local_nearest,
                ),
                "with_unknown": _metrics(
                    points,
                    holdout_indices,
                    local_with_unknown,
                ),
            },
            "reference_graph_smoothed": {
                "nearest": _metrics(
                    points,
                    holdout_indices,
                    smoothed_nearest,
                ),
                "with_unknown": _metrics(
                    points,
                    holdout_indices,
                    smoothed_with_unknown,
                ),
            },
        },
    }

    with (args.output_dir / "candidate_sweep.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(sweep_rows[0]))
        writer.writeheader()
        writer.writerows(
            sorted(
                sweep_rows,
                key=lambda row: (
                    -float(row["lofo_macro_f1"]),
                    -float(row["lofo_domain_accuracy"]),
                    -float(row["lofo_balanced_accuracy"]),
                ),
            )
        )
    _write_predictions(
        args.output_dir / "holdout_predictions.csv",
        points,
        holdout_indices,
        local_nearest,
        local_with_unknown,
        all_distances,
    )
    _write_overlays(
        args.output_dir / "holdout_overlays",
        image_paths,
        points,
        holdout_indices,
        local_with_unknown,
        render_scale=args.render_scale,
    )
    (args.output_dir / "experiment_report.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    _write_report(args.output_dir, payload)
    print(f"Report: {args.output_dir / 'experiment_report.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
