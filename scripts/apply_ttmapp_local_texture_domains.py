"""Apply the calibrated TTMAPP texture classifier to all molecular centroids."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from moltrack.persistence import load_moltrack_session  # noqa: E402
from scripts.experiment_ttmapp_local_texture_domains import (  # noqa: E402
    CLASS_COLORS,
    CLASS_INDEX,
    CLASS_NAMES,
    DescriptorConfig,
    ReferencePoint,
    _apply_unknown,
    _cosine_distances,
    _descriptor_matrix,
    _load_reference,
    _metrics,
    _neighbor_graph,
    _resolve_clean_images,
    _spatial_predictions,
)


@dataclass(frozen=True)
class InferencePoint:
    frame_number: int
    source_id: str
    x_px: float
    y_px: float
    source_kind: str = "segmentation"


@dataclass(frozen=True)
class DetectedDomainComponent:
    frame_number: int
    class_name: str
    component_id: str
    member_indices: tuple[int, ...]
    centroid_x_px: float
    centroid_y_px: float


@dataclass(frozen=True)
class GraphCandidate:
    neighbor_lambda: float
    neighbor_rounds: int
    minimum_component_size: int


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("reference_csv", type=Path)
    parser.add_argument("experiment_report", type=Path)
    parser.add_argument("review_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument(
        "--extra-review-dir",
        action="append",
        type=Path,
        default=[],
    )
    parser.add_argument("--render-scale", type=float, default=2.0)
    parser.add_argument("--first-frame", type=int, default=250)
    parser.add_argument("--last-frame", type=int, default=268)
    parser.add_argument("--holdout-start", type=int, default=263)
    parser.add_argument("--minimum-neighbor-distance-px", type=float, default=7.5)
    parser.add_argument("--maximum-neighbor-distance-px", type=float, default=18.0)
    return parser.parse_args()


def _segmentation_centroid(segmentation) -> tuple[float, float] | None:
    if segmentation.mask is not None:
        mask = np.asarray(segmentation.mask, dtype=bool)
        rows, columns = np.nonzero(mask)
        if columns.size:
            x = float(np.mean(columns, dtype=np.float64) + 0.5)
            y = float(np.mean(rows, dtype=np.float64) + 0.5)
            if segmentation.bbox_xyxy is not None:
                left, top, right, bottom = segmentation.bbox_xyxy
                crop_width = float(right - left)
                crop_height = float(bottom - top)
                if (
                    abs(crop_width - mask.shape[1]) <= 1e-6
                    and abs(crop_height - mask.shape[0]) <= 1e-6
                ):
                    x += float(left)
                    y += float(top)
            return x, y
    if segmentation.bbox_xyxy is not None:
        left, top, right, bottom = segmentation.bbox_xyxy
        return (float((left + right) / 2.0), float((top + bottom) / 2.0))
    return None


def _validate_unique_segmentation_prompts(
    segmentations,
    *,
    frame_number: int,
) -> None:
    owner_by_detection: dict[str, str] = {}
    for segmentation in segmentations:
        for detection_id in segmentation.prompt_detection_ids:
            previous = owner_by_detection.get(detection_id)
            if previous is not None:
                raise ValueError(
                    f"Detection {detection_id!r} in frame {frame_number} "
                    f"belongs to both segmentations {previous!r} and "
                    f"{segmentation.segmentation_id!r}. Select one mask before "
                    "autonomous domain analysis."
                )
            owner_by_detection[detection_id] = segmentation.segmentation_id


def _load_inference_points(
    session_path: Path,
    *,
    frame_numbers: tuple[int, ...],
    source_view: str,
) -> tuple[InferencePoint, ...]:
    session = load_moltrack_session(session_path)
    segmentation_set = session.molecular_segmentations
    detection_set = session.molecular_detections
    points: list[InferencePoint] = []
    for frame_number in frame_numbers:
        frame_index = frame_number - 1
        linked_detection_ids: set[str] = set()
        if segmentation_set is not None:
            segmentations = segmentation_set.get_segmentations(
                frame_index,
                source_view=source_view,
            )
            _validate_unique_segmentation_prompts(
                segmentations,
                frame_number=frame_number,
            )
            for segmentation in segmentations:
                center = _segmentation_centroid(segmentation)
                if center is None:
                    continue
                linked_detection_ids.update(segmentation.prompt_detection_ids)
                points.append(
                    InferencePoint(
                        frame_number=frame_number,
                        source_id=segmentation.segmentation_id,
                        x_px=center[0],
                        y_px=center[1],
                        source_kind="segmentation",
                    )
                )
        if detection_set is not None:
            for detection in detection_set.get_detections(
                frame_index,
                source_view=source_view,
            ):
                if detection.detection_id in linked_detection_ids:
                    continue
                left, top, right, bottom = detection.bbox_xyxy
                points.append(
                    InferencePoint(
                        frame_number=frame_number,
                        source_id=detection.detection_id,
                        x_px=float((left + right) / 2.0),
                        y_px=float((top + bottom) / 2.0),
                        source_kind="bbox_center",
                    )
                )
    if not points:
        raise ValueError(
            f"No {source_view!r} molecular centroids found in {session_path}."
        )
    return tuple(
        sorted(
            points,
            key=lambda point: (
                point.frame_number,
                point.y_px,
                point.x_px,
                point.source_id,
            ),
        )
    )


def _reference_point_indices(
    reference: tuple[ReferencePoint, ...],
    points: tuple[InferencePoint, ...],
) -> np.ndarray:
    index_by_key = {
        (point.frame_number, point.source_id): index
        for index, point in enumerate(points)
    }
    result = []
    missing = []
    for value in reference:
        key = (value.frame_number, value.source_id)
        index = index_by_key.get(key)
        if index is None:
            missing.append(key)
        else:
            result.append(index)
    if missing:
        preview = ", ".join(f"{frame}:{source}" for frame, source in missing[:5])
        raise ValueError(
            f"{len(missing)} reference molecules are absent from the session: "
            f"{preview}."
        )
    return np.asarray(result, dtype=np.int64)


def _validate_reference_scope(
    reference: tuple[ReferencePoint, ...],
    experiment_report: dict[str, object],
    *,
    first_frame: int,
    last_frame: int,
    holdout_start: int,
) -> None:
    first_frame = int(first_frame)
    last_frame = int(last_frame)
    holdout_start = int(holdout_start)
    if not first_frame <= holdout_start <= last_frame:
        raise ValueError(
            "Expected first_frame <= holdout_start <= last_frame."
        )
    calibration_frames = list(range(first_frame, holdout_start))
    holdout_frames = list(range(holdout_start, last_frame + 1))
    if experiment_report.get("calibration_frames") != calibration_frames:
        raise ValueError(
            "Experiment calibration_frames do not match the requested split."
        )
    if experiment_report.get("holdout_frames") != holdout_frames:
        raise ValueError(
            "Experiment holdout_frames do not match the requested split."
        )
    for value in reference:
        if not first_frame <= value.frame_number <= last_frame:
            raise ValueError(
                f"Reference frame {value.frame_number} lies outside the "
                "requested analysis range."
            )
        expected_split = (
            "calibration"
            if value.frame_number < holdout_start
            else "holdout"
        )
        if value.split != expected_split:
            raise ValueError(
                f"Reference split mismatch for frame {value.frame_number}: "
                f"expected {expected_split!r}, found {value.split!r}."
            )


def _validate_prototype_provenance(
    stored_prototypes: np.ndarray,
    recomputed_prototypes: np.ndarray,
    *,
    absolute_tolerance: float = 1e-12,
) -> float:
    stored = np.asarray(stored_prototypes, dtype=np.float64)
    recomputed = np.asarray(recomputed_prototypes, dtype=np.float64)
    if stored.shape != recomputed.shape:
        raise ValueError(
            "Stored and recomputed prototype shapes do not match."
        )
    difference = float(np.max(np.abs(stored - recomputed)))
    if not np.isfinite(difference) or difference > float(absolute_tolerance):
        raise ValueError(
            "Stored texture prototype does not match the current calibration "
            f"data (maximum absolute difference {difference:.9g})."
        )
    return difference


def _reference_prototypes(
    descriptors: np.ndarray,
    reference: tuple[ReferencePoint, ...],
    reference_point_indices: np.ndarray,
    selected_reference_indices: np.ndarray,
) -> np.ndarray:
    prototypes = np.zeros(
        (len(CLASS_NAMES), descriptors.shape[1]),
        dtype=np.float64,
    )
    for class_index, class_name in enumerate(CLASS_NAMES):
        inference_indices = [
            int(reference_point_indices[int(reference_index)])
            for reference_index in selected_reference_indices
            if reference[int(reference_index)].class_name == class_name
            and np.all(
                np.isfinite(
                    descriptors[
                        int(reference_point_indices[int(reference_index)])
                    ]
                )
            )
        ]
        if not inference_indices:
            raise ValueError(f"No finite calibration samples for {class_name}.")
        prototypes[class_index] = np.mean(
            descriptors[np.asarray(inference_indices, dtype=np.int64)],
            axis=0,
        )
        prototypes[class_index] /= max(
            float(np.sum(prototypes[class_index])),
            1e-12,
        )
    return prototypes


def _leave_one_frame_out_inference_distances(
    descriptors: np.ndarray,
    points: tuple[InferencePoint, ...],
    reference: tuple[ReferencePoint, ...],
    reference_point_indices: np.ndarray,
) -> np.ndarray:
    distances = np.full(
        (len(points), len(CLASS_NAMES)),
        np.inf,
        dtype=np.float64,
    )
    calibration_reference_indices = np.asarray(
        [
            index
            for index, value in enumerate(reference)
            if value.split == "calibration"
        ],
        dtype=np.int64,
    )
    calibration_frames = sorted(
        {
            reference[int(index)].frame_number
            for index in calibration_reference_indices
        }
    )
    for held_out_frame in calibration_frames:
        training = np.asarray(
            [
                index
                for index in calibration_reference_indices
                if reference[int(index)].frame_number != held_out_frame
            ],
            dtype=np.int64,
        )
        prototypes = _reference_prototypes(
            descriptors,
            reference,
            reference_point_indices,
            training,
        )
        frame_indices = np.asarray(
            [
                index
                for index, point in enumerate(points)
                if point.frame_number == held_out_frame
            ],
            dtype=np.int64,
        )
        distances[frame_indices] = _cosine_distances(
            descriptors[frame_indices],
            prototypes,
        )
    return distances


def _calibration_unknown_thresholds(
    distances: np.ndarray,
    reference: tuple[ReferencePoint, ...],
    reference_point_indices: np.ndarray,
) -> tuple[np.ndarray, float]:
    thresholds = np.full(len(CLASS_NAMES), np.inf, dtype=np.float64)
    correct_margins: list[float] = []
    for class_index, class_name in enumerate(CLASS_NAMES):
        own_distances = []
        for reference_index, value in enumerate(reference):
            if value.split != "calibration" or value.class_name != class_name:
                continue
            row = distances[int(reference_point_indices[reference_index])]
            if not np.all(np.isfinite(row)):
                continue
            own_distances.append(float(row[class_index]))
            ordered = np.sort(row)
            if int(np.argmin(row)) == class_index:
                correct_margins.append(float(ordered[1] - ordered[0]))
        if own_distances:
            thresholds[class_index] = float(np.quantile(own_distances, 0.975))
    minimum_margin = (
        max(0.0, float(np.quantile(correct_margins, 0.025)))
        if correct_margins
        else 0.0
    )
    return thresholds, minimum_margin


def _build_domain_components(
    points: tuple[InferencePoint, ...],
    predictions: np.ndarray,
    neighbors: tuple[np.ndarray, ...],
    *,
    minimum_component_size: int,
) -> tuple[
    np.ndarray,
    tuple[str, ...],
    tuple[DetectedDomainComponent, ...],
]:
    if len(predictions) != len(points) or len(neighbors) != len(points):
        raise ValueError("Predictions, neighbors and points must have equal length.")
    minimum_component_size = int(minimum_component_size)
    if minimum_component_size <= 0:
        raise ValueError("minimum_component_size must be positive.")

    raw_components: dict[tuple[int, int], list[tuple[int, ...]]] = defaultdict(list)
    visited: set[int] = set()
    for start, prediction in enumerate(predictions):
        class_index = int(prediction)
        if class_index < 0 or start in visited:
            continue
        frame_number = points[start].frame_number
        stack = [start]
        visited.add(start)
        members = []
        while stack:
            current = stack.pop()
            members.append(current)
            for adjacent in neighbors[current]:
                adjacent_index = int(adjacent)
                if adjacent_index in visited:
                    continue
                if points[adjacent_index].frame_number != frame_number:
                    continue
                if int(predictions[adjacent_index]) != class_index:
                    continue
                visited.add(adjacent_index)
                stack.append(adjacent_index)
        raw_components[(frame_number, class_index)].append(
            tuple(sorted(members))
        )

    filtered = np.asarray(predictions, dtype=np.int64).copy()
    assignments = [""] * len(points)
    accepted: list[DetectedDomainComponent] = []
    for (frame_number, class_index), groups in sorted(raw_components.items()):
        retained = [
            group for group in groups if len(group) >= minimum_component_size
        ]
        rejected = [
            index
            for group in groups
            if len(group) < minimum_component_size
            for index in group
        ]
        if rejected:
            filtered[np.asarray(rejected, dtype=np.int64)] = -1
        retained.sort(
            key=lambda group: (
                -len(group),
                float(np.mean([points[index].y_px for index in group])),
                float(np.mean([points[index].x_px for index in group])),
                min(points[index].source_id for index in group),
            )
        )
        for component_index, group in enumerate(retained, start=1):
            class_name = CLASS_NAMES[class_index]
            component_id = f"{class_name}_{component_index:02d}"
            for point_index in group:
                assignments[point_index] = component_id
            accepted.append(
                DetectedDomainComponent(
                    frame_number=frame_number,
                    class_name=class_name,
                    component_id=component_id,
                    member_indices=group,
                    centroid_x_px=float(
                        np.mean([points[index].x_px for index in group])
                    ),
                    centroid_y_px=float(
                        np.mean([points[index].y_px for index in group])
                    ),
                )
            )
    accepted.sort(
        key=lambda value: (
            value.frame_number,
            CLASS_INDEX[value.class_name],
            value.component_id,
        )
    )
    return filtered, tuple(assignments), tuple(accepted)


def _project_reference_predictions(
    reference_point_indices: np.ndarray,
    predictions: np.ndarray,
) -> np.ndarray:
    return np.asarray(
        [int(predictions[int(index)]) for index in reference_point_indices],
        dtype=np.int64,
    )


def _classification_metrics(
    reference: tuple[ReferencePoint, ...],
    reference_point_indices: np.ndarray,
    predictions: np.ndarray,
) -> dict[str, object]:
    projected = _project_reference_predictions(
        reference_point_indices,
        predictions,
    )
    return _metrics(
        reference,
        np.arange(len(reference), dtype=np.int64),
        projected,
    )


def _partition_metrics(
    reference: tuple[ReferencePoint, ...],
    points: tuple[InferencePoint, ...],
    predictions: np.ndarray,
    assignments: tuple[str, ...],
) -> dict[str, object]:
    reference_point_indices = _reference_point_indices(reference, points)
    manual_groups: dict[tuple[int, str, str], list[int]] = defaultdict(list)
    for reference_index, value in enumerate(reference):
        manual_groups[
            (value.frame_number, value.instance_label, value.class_name)
        ].append(int(reference_point_indices[reference_index]))

    instance_rows = []
    for (frame, instance, class_name), indices in sorted(manual_groups.items()):
        expected_index = CLASS_INDEX[class_name]
        component_counts = Counter(
            (frame, assignments[index])
            for index in indices
            if int(predictions[index]) == expected_index
            and assignments[index]
        )
        recovered = max(component_counts.values(), default=0)
        recovery = recovered / max(len(indices), 1)
        instance_rows.append(
            {
                "frame_number": frame,
                "instance_label": instance,
                "class_name": class_name,
                "point_count": len(indices),
                "recovered_point_count": recovered,
                "recovery": recovery,
                "component_count": len(component_counts),
            }
        )

    component_labels: dict[tuple[int, str], list[tuple[str, str]]] = (
        defaultdict(list)
    )
    for reference_index, value in enumerate(reference):
        point_index = int(reference_point_indices[reference_index])
        component_id = assignments[point_index]
        if component_id:
            component_labels[(value.frame_number, component_id)].append(
                (value.instance_label, value.class_name)
            )
    component_rows = []
    for (frame, component_id), labels in sorted(component_labels.items()):
        counts = Counter(labels)
        dominant_count = max(counts.values())
        component_rows.append(
            {
                "frame_number": frame,
                "component_id": component_id,
                "labelled_point_count": len(labels),
                "manual_instance_count": len(counts),
                "purity": dominant_count / len(labels),
            }
        )

    return {
        "manual_instance_count": len(instance_rows),
        "predicted_component_count": len(component_rows),
        "recovered_manual_instance_count": sum(
            value["recovery"] >= 0.5 for value in instance_rows
        ),
        "mean_manual_instance_recovery": (
            float(np.mean([value["recovery"] for value in instance_rows]))
            if instance_rows
            else 0.0
        ),
        "mean_predicted_component_purity": (
            float(np.mean([value["purity"] for value in component_rows]))
            if component_rows
            else 0.0
        ),
        "split_manual_instance_count": sum(
            value["component_count"] > 1 for value in instance_rows
        ),
        "merged_component_count": sum(
            value["manual_instance_count"] > 1 for value in component_rows
        ),
        "instances": instance_rows,
        "components": component_rows,
    }


def _subset_reference(
    reference: tuple[ReferencePoint, ...],
    split: str,
) -> tuple[ReferencePoint, ...]:
    return tuple(value for value in reference if value.split == split)


def _select_graph_candidate(
    points: tuple[InferencePoint, ...],
    reference: tuple[ReferencePoint, ...],
    lofo_distances: np.ndarray,
    neighbors: tuple[np.ndarray, ...],
    *,
    thresholds: np.ndarray,
    minimum_margin: float,
) -> tuple[GraphCandidate, list[dict[str, object]]]:
    calibration_reference = _subset_reference(reference, "calibration")
    calibration_point_indices = _reference_point_indices(
        calibration_reference,
        points,
    )
    candidates = [
        GraphCandidate(neighbor_lambda, rounds, minimum_size)
        for neighbor_lambda, rounds in (
            (0.0, 1),
            (0.01, 1),
            (0.02, 1),
            (0.02, 2),
            (0.05, 1),
            (0.05, 2),
        )
        for minimum_size in (3, 5, 8, 12)
    ]
    rows: list[dict[str, object]] = []
    best: tuple[tuple[float, ...], GraphCandidate] | None = None
    for candidate in candidates:
        nearest = _spatial_predictions(
            lofo_distances,
            neighbors,
            neighbor_lambda=candidate.neighbor_lambda,
            rounds=candidate.neighbor_rounds,
        )
        with_unknown = _apply_unknown(
            nearest,
            lofo_distances,
            thresholds=thresholds,
            minimum_margin=minimum_margin,
        )
        filtered, assignments, components = _build_domain_components(
            points,
            with_unknown,
            neighbors,
            minimum_component_size=candidate.minimum_component_size,
        )
        classification = _classification_metrics(
            calibration_reference,
            calibration_point_indices,
            filtered,
        )
        partition = _partition_metrics(
            calibration_reference,
            points,
            filtered,
            assignments,
        )
        row = {
            "neighbor_lambda": candidate.neighbor_lambda,
            "neighbor_rounds": candidate.neighbor_rounds,
            "minimum_component_size": candidate.minimum_component_size,
            "macro_f1": classification["macro_f1"],
            "accuracy": classification["accuracy"],
            "balanced_accuracy": classification["balanced_accuracy"],
            "coverage": classification["coverage"],
            "domain_accuracy": classification["domain_accuracy"],
            "mean_manual_instance_recovery": partition[
                "mean_manual_instance_recovery"
            ],
            "mean_predicted_component_purity": partition[
                "mean_predicted_component_purity"
            ],
            "recovered_manual_instance_count": partition[
                "recovered_manual_instance_count"
            ],
            "manual_instance_count": partition["manual_instance_count"],
            "accepted_component_count": len(components),
        }
        rows.append(row)
        rank = (
            float(classification["domain_accuracy"]),
            float(classification["macro_f1"]),
            float(partition["mean_manual_instance_recovery"]),
            float(partition["mean_predicted_component_purity"]),
            float(classification["coverage"]),
            float(candidate.minimum_component_size),
            -candidate.neighbor_lambda,
            -float(candidate.neighbor_rounds),
        )
        if best is None or rank > best[0]:
            best = (rank, candidate)
    if best is None:
        raise RuntimeError("No autonomous graph candidate was evaluated.")
    rows.sort(
        key=lambda row: (
            -float(row["domain_accuracy"]),
            -float(row["macro_f1"]),
            -float(row["mean_manual_instance_recovery"]),
            -float(row["mean_predicted_component_purity"]),
        )
    )
    return best[1], rows


def _write_sweep(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _expected_by_point(
    reference: tuple[ReferencePoint, ...],
) -> dict[tuple[int, str], ReferencePoint]:
    return {
        (value.frame_number, value.source_id): value
        for value in reference
    }


def _write_predictions(
    path: Path,
    points: tuple[InferencePoint, ...],
    reference: tuple[ReferencePoint, ...],
    distances: np.ndarray,
    local_predictions: np.ndarray,
    final_predictions: np.ndarray,
    assignments: tuple[str, ...],
) -> None:
    expected = _expected_by_point(reference)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            (
                "frame_number",
                "source_id",
                "source_kind",
                "x_px",
                "y_px",
                "is_manual_reference",
                "expected_class",
                "expected_instance",
                "predicted_local",
                "predicted_final",
                "component_id",
                "distance_black",
                "distance_red",
                "distance_yellow",
                "classification_margin",
            )
        )
        for index, point in enumerate(points):
            expected_value = expected.get((point.frame_number, point.source_id))
            ordered = np.sort(distances[index])
            margin = (
                float(ordered[1] - ordered[0])
                if np.all(np.isfinite(ordered[:2]))
                else float("nan")
            )
            writer.writerow(
                (
                    point.frame_number,
                    point.source_id,
                    point.source_kind,
                    f"{point.x_px:.9g}",
                    f"{point.y_px:.9g}",
                    int(expected_value is not None),
                    "" if expected_value is None else expected_value.class_name,
                    "" if expected_value is None else expected_value.instance_label,
                    (
                        CLASS_NAMES[int(local_predictions[index])]
                        if local_predictions[index] >= 0
                        else "UNKNOWN"
                    ),
                    (
                        CLASS_NAMES[int(final_predictions[index])]
                        if final_predictions[index] >= 0
                        else "UNKNOWN"
                    ),
                    assignments[index],
                    *(f"{value:.9g}" for value in distances[index]),
                    f"{margin:.9g}",
                )
            )


def _write_components(
    path: Path,
    components: tuple[DetectedDomainComponent, ...],
    points: tuple[InferencePoint, ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            (
                "frame_number",
                "component_id",
                "class_name",
                "molecule_count",
                "centroid_x_px",
                "centroid_y_px",
                "source_ids",
            )
        )
        for component in components:
            writer.writerow(
                (
                    component.frame_number,
                    component.component_id,
                    component.class_name,
                    len(component.member_indices),
                    f"{component.centroid_x_px:.9g}",
                    f"{component.centroid_y_px:.9g}",
                    ";".join(
                        points[index].source_id
                        for index in component.member_indices
                    ),
                )
            )


def _font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _write_overlays(
    output_dir: Path,
    image_paths: dict[int, Path],
    points: tuple[InferencePoint, ...],
    predictions: np.ndarray,
    neighbors: tuple[np.ndarray, ...],
    components: tuple[DetectedDomainComponent, ...],
    *,
    render_scale: float,
    maximum_neighbor_distance_px: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    point_indices_by_frame: dict[int, list[int]] = defaultdict(list)
    components_by_frame: dict[int, list[DetectedDomainComponent]] = defaultdict(
        list
    )
    rendered_frames = set(image_paths)
    for index, point in enumerate(points):
        if point.frame_number in rendered_frames:
            point_indices_by_frame[point.frame_number].append(index)
    for component in components:
        if component.frame_number in rendered_frames:
            components_by_frame[component.frame_number].append(component)

    for frame_number, frame_indices in sorted(point_indices_by_frame.items()):
        image = Image.open(image_paths[frame_number]).convert("RGBA")
        footprint_radius = max(
            4,
            int(
                round(
                    render_scale * maximum_neighbor_distance_px * 0.22
                )
            ),
        )
        for component in components_by_frame[frame_number]:
            member_set = set(component.member_indices)
            footprint_image = Image.new("L", image.size, 0)
            footprint_draw = ImageDraw.Draw(footprint_image)
            for left in component.member_indices:
                left_xy = (
                    points[left].x_px * render_scale,
                    points[left].y_px * render_scale,
                )
                for right_value in neighbors[left]:
                    right = int(right_value)
                    if right <= left or right not in member_set:
                        continue
                    right_xy = (
                        points[right].x_px * render_scale,
                        points[right].y_px * render_scale,
                    )
                    footprint_draw.line(
                        (left_xy, right_xy),
                        fill=255,
                        width=2 * footprint_radius,
                    )
                x, y = left_xy
                footprint_draw.ellipse(
                    (
                        x - footprint_radius,
                        y - footprint_radius,
                        x + footprint_radius,
                        y + footprint_radius,
                    ),
                    fill=255,
                )
            footprint = np.asarray(footprint_image, dtype=np.uint8) > 0
            footprint = ndimage.binary_closing(footprint, iterations=2)
            boundary = ndimage.binary_dilation(
                footprint,
                iterations=2,
            ) & ~ndimage.binary_erosion(footprint, iterations=2)
            color = CLASS_COLORS[component.class_name]
            domain_layer = np.zeros(
                (image.height, image.width, 4),
                dtype=np.uint8,
            )
            domain_layer[footprint, :3] = color
            domain_layer[footprint, 3] = 34
            domain_layer[boundary, :3] = color
            domain_layer[boundary, 3] = 235
            image = Image.alpha_composite(
                image,
                Image.fromarray(domain_layer, mode="RGBA"),
            )
        draw = ImageDraw.Draw(image)
        for index in frame_indices:
            point = points[index]
            prediction = int(predictions[index])
            color = (
                (145, 145, 145)
                if prediction < 0
                else CLASS_COLORS[CLASS_NAMES[prediction]]
            )
            x = point.x_px * render_scale
            y = point.y_px * render_scale
            radius = 4
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                fill=color,
                outline=(255, 255, 255),
                width=1,
            )
        for component in components_by_frame[frame_number]:
            color = CLASS_COLORS[component.class_name]
            x = component.centroid_x_px * render_scale
            y = component.centroid_y_px * render_scale
            label = f"{component.component_id} ({len(component.member_indices)})"
            draw.text(
                (x + 5, y + 5),
                label,
                fill=color,
                stroke_width=2,
                stroke_fill=(255, 255, 255),
                font=_font(14),
            )
        counts = Counter(
            CLASS_NAMES[int(predictions[index])]
            for index in frame_indices
            if predictions[index] >= 0
        )
        component_counts = Counter(
            value.class_name for value in components_by_frame[frame_number]
        )
        legend = " | ".join(
            f"{name}: {counts[name]} pts/{component_counts[name]} domains"
            for name in CLASS_NAMES
        )
        draw.text(
            (12, 12),
            legend,
            fill=(255, 255, 255),
            stroke_width=2,
            stroke_fill=(0, 0, 0),
            font=_font(16),
        )
        image.convert("RGB").save(
            output_dir / f"frame_{frame_number}_autonomous_domains.png"
        )


def _component_summary(
    components: tuple[DetectedDomainComponent, ...],
    frame_numbers: tuple[int, ...],
) -> dict[str, object]:
    rows = {}
    for frame_number in frame_numbers:
        selected = [
            value for value in components if value.frame_number == frame_number
        ]
        rows[str(frame_number)] = {
            "component_count": len(selected),
            "molecule_count": sum(len(value.member_indices) for value in selected),
            "by_class": {
                class_name: {
                    "component_count": sum(
                        value.class_name == class_name for value in selected
                    ),
                    "molecule_count": sum(
                        len(value.member_indices)
                        for value in selected
                        if value.class_name == class_name
                    ),
                }
                for class_name in CLASS_NAMES
            },
        }
    return rows


def _write_report(output_dir: Path, payload: dict[str, object]) -> None:
    selected = payload["selected_graph_candidate"]
    calibration = payload["calibration_selection_lofo"]
    holdout = payload["holdout"]
    lines = [
        "# TTMAPP autonomous local-texture domains",
        "",
        "## Scope",
        "",
        (
            "All molecular centroids in every evaluated frame are classified. "
            "Manual outlines are used only for calibration scoring and final "
            "holdout validation; they are not used to build the prediction graph."
        ),
        "",
        "## Selected graph",
        "",
        f"- Neighbor weight: {selected['neighbor_lambda']}.",
        f"- Smoothing rounds: {selected['neighbor_rounds']}.",
        (
            "- Minimum connected component size: "
            f"{selected['minimum_component_size']} molecules."
        ),
        (
            "- First-shell point distance: "
            f"{payload['minimum_neighbor_distance_px']}-"
            f"{payload['maximum_neighbor_distance_px']} source px."
        ),
        "",
        "## Calibration",
        "",
        (
            "- Leave-one-frame-out point macro F1 used for selection: "
            f"{calibration['macro_f1']:.3f}."
        ),
        (
            "- Leave-one-frame-out manual-domain majority accuracy: "
            f"{calibration['domain_accuracy']:.3f}."
        ),
        (
            "- Leave-one-frame-out mean manual-instance recovery: "
            f"{calibration['mean_manual_instance_recovery']:.3f}."
        ),
        "",
        "## Temporal holdout: frames 263-268",
        "",
        f"- Point macro F1: {holdout['classification']['macro_f1']:.3f}.",
        f"- Point coverage: {holdout['classification']['coverage']:.3f}.",
        (
            "- Manual-domain majority accuracy: "
            f"{holdout['classification']['domain_accuracy']:.3f}."
        ),
        (
            "- Mean manual-instance recovery: "
            f"{holdout['partition']['mean_manual_instance_recovery']:.3f}."
        ),
        (
            "- Mean labelled-component purity: "
            f"{holdout['partition']['mean_predicted_component_purity']:.3f}."
        ),
        "",
        "## Interpretation",
        "",
        (
            "The overlays are autonomous predictions for this movie. Areas "
            "outside the manual outlines are intentionally not counted as "
            "false positives because they were not exhaustively annotated."
        ),
        (
            "This remains a single-sequence calibration. Before promoting the "
            "classifier to an application preset, inspect the holdout overlays "
            "and validate it on at least one independent acquisition."
        ),
        "",
        "## Artifacts",
        "",
        "- `autonomous_predictions.csv`: every molecule and its prediction.",
        "- `autonomous_components.csv`: accepted spatial domain components.",
        "- `graph_candidate_sweep.csv`: calibration-only graph selection.",
        "- `holdout_overlays/`: autonomous domain overlays for frames 263-268.",
        "- `autonomous_report.json`: full parameters, metrics and counts.",
        "",
    ]
    (output_dir / "autonomous_report.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    args = _parse_args()
    reference = _load_reference(args.reference_csv)
    report = json.loads(args.experiment_report.read_text(encoding="utf-8"))
    _validate_reference_scope(
        reference,
        report,
        first_frame=args.first_frame,
        last_frame=args.last_frame,
        holdout_start=args.holdout_start,
    )
    selected = report["selected_candidate"]
    config = DescriptorConfig(
        radius_px=int(selected["radius_px"]),
        high_pass_sigma_px=float(selected["high_pass_sigma_px"]),
        histogram_sigma_bins=float(selected["histogram_sigma_bins"]),
        radial_weighting=str(selected["radial_weighting"]),
    )
    frame_numbers = tuple(range(args.first_frame, args.last_frame + 1))
    image_paths = _resolve_clean_images(
        set(frame_numbers),
        (args.review_dir, *tuple(args.extra_review_dir)),
    )
    source_view = str(report.get("source_view", "expanded_aligned"))
    points = _load_inference_points(
        args.session,
        frame_numbers=frame_numbers,
        source_view=source_view,
    )
    reference_point_indices = _reference_point_indices(reference, points)
    print(
        f"Extracting {config.key} for {len(points)} molecular centroids...",
        flush=True,
    )
    descriptors = _descriptor_matrix(
        points,
        image_paths,
        config,
        render_scale=args.render_scale,
    )
    finite_count = int(np.count_nonzero(np.all(np.isfinite(descriptors), axis=1)))
    if finite_count == 0:
        raise RuntimeError("No finite local texture descriptor was extracted.")

    stored_prototypes = np.asarray(
        [
            selected["prototype_histograms"][class_name]
            for class_name in CLASS_NAMES
        ],
        dtype=np.float64,
    )
    calibration_reference_indices = np.asarray(
        [
            index
            for index, value in enumerate(reference)
            if value.split == "calibration"
        ],
        dtype=np.int64,
    )
    recomputed_prototypes = _reference_prototypes(
        descriptors,
        reference,
        reference_point_indices,
        calibration_reference_indices,
    )
    prototype_max_abs_difference = _validate_prototype_provenance(
        stored_prototypes,
        recomputed_prototypes,
    )
    final_distances = _cosine_distances(descriptors, stored_prototypes)
    lofo_distances = _leave_one_frame_out_inference_distances(
        descriptors,
        points,
        reference,
        reference_point_indices,
    )
    thresholds, minimum_margin = _calibration_unknown_thresholds(
        lofo_distances,
        reference,
        reference_point_indices,
    )
    neighbors = _neighbor_graph(
        points,
        minimum_distance_px=args.minimum_neighbor_distance_px,
        maximum_distance_px=args.maximum_neighbor_distance_px,
    )
    print("Selecting graph settings on calibration frames 250-262...", flush=True)
    graph_candidate, sweep_rows = _select_graph_candidate(
        points,
        reference,
        lofo_distances,
        neighbors,
        thresholds=thresholds,
        minimum_margin=minimum_margin,
    )
    selected_graph_row = next(
        row
        for row in sweep_rows
        if float(row["neighbor_lambda"]) == graph_candidate.neighbor_lambda
        and int(row["neighbor_rounds"]) == graph_candidate.neighbor_rounds
        and int(row["minimum_component_size"])
        == graph_candidate.minimum_component_size
    )

    local_nearest = _spatial_predictions(
        final_distances,
        neighbors,
        neighbor_lambda=0.0,
        rounds=1,
    )
    local_with_unknown = _apply_unknown(
        local_nearest,
        final_distances,
        thresholds=thresholds,
        minimum_margin=minimum_margin,
    )
    smoothed = _spatial_predictions(
        final_distances,
        neighbors,
        neighbor_lambda=graph_candidate.neighbor_lambda,
        rounds=graph_candidate.neighbor_rounds,
    )
    smoothed_with_unknown = _apply_unknown(
        smoothed,
        final_distances,
        thresholds=thresholds,
        minimum_margin=minimum_margin,
    )
    final_predictions, assignments, components = _build_domain_components(
        points,
        smoothed_with_unknown,
        neighbors,
        minimum_component_size=graph_candidate.minimum_component_size,
    )

    calibration_reference = _subset_reference(reference, "calibration")
    holdout_reference = tuple(
        value for value in reference if value.split != "calibration"
    )
    calibration_point_indices = _reference_point_indices(
        calibration_reference,
        points,
    )
    holdout_point_indices = _reference_point_indices(
        holdout_reference,
        points,
    )
    payload: dict[str, object] = {
        "status": "single_sequence_autonomous_local_texture_domains",
        "session": str(args.session),
        "reference_csv": str(args.reference_csv),
        "source_view": source_view,
        "descriptor": {
            "key": config.key,
            "radius_px": config.radius_px,
            "high_pass_sigma_px": config.high_pass_sigma_px,
            "histogram_sigma_bins": config.histogram_sigma_bins,
            "radial_weighting": config.radial_weighting,
            "render_scale": args.render_scale,
        },
        "prototype_max_abs_difference_from_experiment": (
            prototype_max_abs_difference
        ),
        "unknown_distance_thresholds_lofo": {
            class_name: float(thresholds[class_index])
            for class_index, class_name in enumerate(CLASS_NAMES)
        },
        "unknown_minimum_margin_lofo": minimum_margin,
        "minimum_neighbor_distance_px": args.minimum_neighbor_distance_px,
        "maximum_neighbor_distance_px": args.maximum_neighbor_distance_px,
        "selected_graph_candidate": {
            "neighbor_lambda": graph_candidate.neighbor_lambda,
            "neighbor_rounds": graph_candidate.neighbor_rounds,
            "minimum_component_size": graph_candidate.minimum_component_size,
        },
        "molecule_count": len(points),
        "finite_descriptor_count": finite_count,
        "accepted_component_count": len(components),
        "accepted_molecule_count": int(np.count_nonzero(final_predictions >= 0)),
        "calibration_frames": sorted(
            {value.frame_number for value in calibration_reference}
        ),
        "holdout_frames": sorted(
            {value.frame_number for value in holdout_reference}
        ),
        "calibration_selection_lofo": selected_graph_row,
        "calibration": {
            "metric_scope": (
                "Diagnostic refit on all calibration frames; model selection "
                "uses calibration_selection_lofo."
            ),
            "classification": _classification_metrics(
                calibration_reference,
                calibration_point_indices,
                final_predictions,
            ),
            "partition": _partition_metrics(
                calibration_reference,
                points,
                final_predictions,
                assignments,
            ),
        },
        "holdout": {
            "local_only": _classification_metrics(
                holdout_reference,
                holdout_point_indices,
                local_with_unknown,
            ),
            "classification": _classification_metrics(
                holdout_reference,
                holdout_point_indices,
                final_predictions,
            ),
            "partition": _partition_metrics(
                holdout_reference,
                points,
                final_predictions,
                assignments,
            ),
        },
        "components_by_frame": _component_summary(
            components,
            frame_numbers,
        ),
        "validation_scope": (
            "Manual labels score only annotated molecules. Unlabelled regions "
            "are not treated as negatives."
        ),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_sweep(args.output_dir / "graph_candidate_sweep.csv", sweep_rows)
    _write_predictions(
        args.output_dir / "autonomous_predictions.csv",
        points,
        reference,
        final_distances,
        local_with_unknown,
        final_predictions,
        assignments,
    )
    _write_components(
        args.output_dir / "autonomous_components.csv",
        components,
        points,
    )
    holdout_frames = {
        value.frame_number for value in holdout_reference
    }
    _write_overlays(
        args.output_dir / "holdout_overlays",
        {
            frame: path
            for frame, path in image_paths.items()
            if frame in holdout_frames
        },
        points,
        final_predictions,
        neighbors,
        components,
        render_scale=args.render_scale,
        maximum_neighbor_distance_px=args.maximum_neighbor_distance_px,
    )
    (args.output_dir / "autonomous_report.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    _write_report(args.output_dir, payload)
    print(f"Report: {args.output_dir / 'autonomous_report.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
