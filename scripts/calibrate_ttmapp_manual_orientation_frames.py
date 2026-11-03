"""Calibrate TTMAPP molecular-orientation classes from manual frame regions."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass
from math import atan2, cos, degrees, pi, sin
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from moltrack.analysis import estimate_series_molecular_orientations  # noqa: E402
from moltrack.core import build_moltrack_expanded_aligned_stack  # noqa: E402
from moltrack.persistence import (  # noqa: E402
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
)


CLASS_COLORS = {
    "BLACK": (25, 25, 25),
    "RED": (240, 45, 40),
    "YELLOW": (245, 205, 0),
}
PERIOD_DEG = 180.0


@dataclass(frozen=True)
class ReviewFrame:
    frame_number: int
    clean_path: Path
    manual_path: Path

    @property
    def frame_index(self) -> int:
        return self.frame_number - 1


@dataclass(frozen=True)
class RegionInstance:
    frame_number: int
    class_name: str
    component_index: int
    source_ids: tuple[str, ...]
    available_source_ids: tuple[str, ...]
    mean_axis_deg: float | None
    median_spread_deg: float | None
    median_confidence: float | None
    texture_axis_deg: float | None
    texture_confidence: float | None
    texture_descriptor: tuple[float, ...]

    @property
    def instance_id(self) -> str:
        return (
            f"frame_{self.frame_number}:{self.class_name}:"
            f"{self.component_index}"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("review_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument(
        "--extra-review-dir",
        action="append",
        type=Path,
        default=[],
    )
    parser.add_argument(
        "--validation-start-frame",
        type=int,
        default=263,
    )
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def _discover_review_frames(
    review_dirs: tuple[Path, ...],
) -> tuple[ReviewFrame, ...]:
    frames: dict[int, ReviewFrame] = {}
    suffix = "_clean_registered_manual_domain.png"
    for directory in review_dirs:
        for manual_path in sorted(directory.glob(f"frame_*{suffix}")):
            prefix = manual_path.name[: -len(suffix)]
            try:
                frame_number = int(prefix.removeprefix("frame_"))
            except ValueError as exc:
                raise ValueError(
                    f"Cannot parse frame number from {manual_path.name!r}."
                ) from exc
            clean_path = directory / (
                f"frame_{frame_number}_clean_registered.png"
            )
            if not clean_path.is_file():
                raise FileNotFoundError(
                    f"Missing clean image for frame {frame_number}: {clean_path}"
                )
            value = ReviewFrame(
                frame_number=frame_number,
                clean_path=clean_path,
                manual_path=manual_path,
            )
            previous = frames.get(frame_number)
            if previous is not None and previous != value:
                raise ValueError(
                    f"Frame {frame_number} occurs in more than one review directory."
                )
            frames[frame_number] = value
    if not frames:
        raise ValueError("No manually annotated review frames were found.")
    return tuple(frames[number] for number in sorted(frames))


def _outline_masks(
    clean_path: Path,
    manual_path: Path,
) -> dict[str, np.ndarray]:
    clean = np.asarray(Image.open(clean_path).convert("RGB"), dtype=np.int16)
    manual = np.asarray(Image.open(manual_path).convert("RGB"), dtype=np.int16)
    if clean.shape != manual.shape:
        raise ValueError(
            f"Clean/manual dimensions differ for {manual_path.name}."
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
        & (
            np.abs(
                manual[:, :, 0].astype(np.int32)
                - manual[:, :, 1].astype(np.int32)
            )
            < 130
        )
    )
    clean_gray = np.mean(clean, axis=2)
    manual_gray = np.mean(manual, axis=2)
    black = (
        (np.max(manual, axis=2) < 100)
        & ((clean_gray - manual_gray) > 3)
    )
    return {
        "BLACK": black,
        "RED": red,
        "YELLOW": yellow,
    }


def _filled_regions(
    outline: np.ndarray,
    *,
    closing_iterations: int = 6,
) -> tuple[np.ndarray, ...]:
    if not np.any(outline):
        return ()
    closed = ndimage.binary_closing(
        ndimage.binary_dilation(outline, iterations=2),
        iterations=closing_iterations,
    )
    filled = ndimage.binary_fill_holes(closed)
    labels, count = ndimage.label(filled)
    regions: list[np.ndarray] = []
    for label in range(1, count + 1):
        region = labels == label
        area = int(np.count_nonzero(region))
        if area < 800:
            continue
        interior_area = int(np.count_nonzero(region & ~closed))
        if interior_area < 300:
            continue
        regions.append(region)
    regions.sort(
        key=lambda value: (
            float(np.mean(np.nonzero(value)[1])),
            float(np.mean(np.nonzero(value)[0])),
        )
    )
    return tuple(regions)


def _valid_fov_from_clean_image(clean_path: Path) -> np.ndarray:
    clean = np.asarray(Image.open(clean_path).convert("L"))
    foreground = ndimage.binary_fill_holes(
        ndimage.binary_closing(
            ndimage.binary_dilation(clean > 0, iterations=2),
            iterations=8,
        )
    )
    labels, count = ndimage.label(foreground)
    if count == 0:
        raise ValueError(f"Cannot infer valid FOV from {clean_path.name}.")
    sizes = ndimage.sum(foreground, labels, range(1, count + 1))
    return labels == (int(np.argmax(sizes)) + 1)


def _fallback_black_region(
    clean_path: Path,
    outlines: dict[str, np.ndarray],
) -> tuple[np.ndarray, ...]:
    """Recover a black region that shares boundaries with other colors/FOV."""

    valid_fov = _valid_fov_from_clean_image(clean_path)
    barrier = ndimage.binary_dilation(
        np.logical_or.reduce(tuple(outlines.values())),
        iterations=12,
    )
    labels, count = ndimage.label(valid_fov & ~barrier)
    if count <= 1:
        return ()
    components = [
        labels == label
        for label in range(1, count + 1)
        if int(np.count_nonzero(labels == label)) >= 20_000
    ]
    if len(components) <= 1:
        return ()
    largest = max(components, key=np.count_nonzero)
    black_dilated = ndimage.binary_dilation(
        outlines["BLACK"],
        iterations=12,
    )
    candidates = []
    for component in components:
        if component is largest:
            continue
        adjacency = ndimage.binary_dilation(component, iterations=14) & barrier
        black_support = int(np.count_nonzero(adjacency & black_dilated))
        total_support = int(np.count_nonzero(adjacency))
        purity = (
            0.0 if total_support == 0 else black_support / total_support
        )
        candidates.append((black_support, purity, component))
    if not candidates:
        return ()
    black_support, purity, selected = max(
        candidates,
        key=lambda value: (value[0], value[1]),
    )
    if black_support < 2_000 or purity < 0.45:
        return ()
    return (selected,)


def _extract_regions(
    frame: ReviewFrame,
) -> dict[str, tuple[np.ndarray, ...]]:
    outlines = _outline_masks(
        frame.clean_path,
        frame.manual_path,
    )
    regions = {
        class_name: _filled_regions(
            outline,
            closing_iterations=10 if class_name == "BLACK" else 6,
        )
        for class_name, outline in outlines.items()
    }
    if not regions["BLACK"] and np.any(outlines["BLACK"]):
        regions["BLACK"] = _fallback_black_region(
            frame.clean_path,
            outlines,
        )
    return regions


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _render_annotation_qc(
    frame: ReviewFrame,
    regions: dict[str, tuple[np.ndarray, ...]],
    destination: Path,
) -> None:
    base = Image.open(frame.clean_path).convert("RGB")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    for class_name, values in regions.items():
        color = CLASS_COLORS[class_name]
        for component_index, region in enumerate(values, start=1):
            alpha = np.zeros((*region.shape, 4), dtype=np.uint8)
            alpha[region, :3] = color
            alpha[region, 3] = 42
            component = Image.fromarray(alpha, mode="RGBA")
            layer = Image.alpha_composite(layer, component)
            rows, columns = np.nonzero(region)
            if rows.size:
                draw = ImageDraw.Draw(layer)
                draw.text(
                    (float(np.mean(columns)), float(np.mean(rows))),
                    f"{class_name[0]}{component_index}",
                    fill=(*color, 255),
                    stroke_width=2,
                    stroke_fill=(255, 255, 255, 255),
                    font=_font(18),
                    anchor="mm",
                )
    output = Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB")
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.save(destination)


def _build_subset_session(
    source: Path,
    destination: Path,
    *,
    frame_indices: set[int],
) -> Path:
    payload = json.loads(source.read_text(encoding="utf-8"))
    relative_source = payload["source"].get("path_relative_to_session")
    if relative_source:
        payload["source"]["path"] = str(
            (source.parent / str(relative_source)).resolve()
        )
        payload["source"]["path_relative_to_session"] = None
    for key, values_key in (
        ("molecular_detections", "detections"),
        ("molecular_segmentations", "segmentations"),
    ):
        block = payload.get(key)
        if block is None:
            continue
        block[values_key] = [
            item
            for item in block.get(values_key, [])
            if int(item["frame_index"]) in frame_indices
        ]
    payload["molecular_orientations"] = None
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, separators=(",", ":")),
        encoding="utf-8",
    )
    return destination


def _periodic_mean(
    angles_deg: list[float],
    weights: list[float] | None = None,
) -> float | None:
    if not angles_deg:
        return None
    if weights is None:
        weights = [1.0] * len(angles_deg)
    phases = [2.0 * pi * value / PERIOD_DEG for value in angles_deg]
    x = sum(weight * cos(phase) for weight, phase in zip(weights, phases))
    y = sum(weight * sin(phase) for weight, phase in zip(weights, phases))
    if abs(x) + abs(y) <= 1e-12:
        return None
    return (degrees(atan2(y, x)) % 360.0) * PERIOD_DEG / 360.0


def _axis_distance(left: float, right: float) -> float:
    difference = abs(float(left) - float(right)) % PERIOD_DEG
    return min(difference, PERIOD_DEG - difference)


def _domain_texture_features(
    clean_path: Path,
    region: np.ndarray,
) -> tuple[float | None, float | None, tuple[float, ...]]:
    """Estimate the dominant row/texture axis over a complete manual domain."""

    image = np.asarray(Image.open(clean_path).convert("L"), dtype=np.float64)
    support = ndimage.binary_erosion(region, iterations=8)
    if int(np.count_nonzero(support)) < 500:
        return None, None, ()
    high_pass = image - ndimage.gaussian_filter(image, sigma=12.0)
    gradient_rows, gradient_columns = np.gradient(high_pass)
    gradient_x = gradient_columns[support]
    gradient_y = -gradient_rows[support]
    total_energy = float(
        np.sum(gradient_x * gradient_x + gradient_y * gradient_y)
    )
    if not np.isfinite(total_energy) or total_energy <= 0.0:
        return None, None, ()
    gradient_angles = (
        np.degrees(np.arctan2(gradient_y, gradient_x)) % PERIOD_DEG
    )
    gradient_energy = gradient_x * gradient_x + gradient_y * gradient_y
    histogram, _edges = np.histogram(
        gradient_angles,
        bins=90,
        range=(0.0, PERIOD_DEG),
        weights=gradient_energy,
    )
    histogram = ndimage.gaussian_filter1d(
        histogram.astype(np.float64),
        sigma=1.5,
        mode="wrap",
    )
    histogram_sum = float(np.sum(histogram))
    if not np.isfinite(histogram_sum) or histogram_sum <= 0.0:
        return None, None, ()
    histogram /= histogram_sum
    angles = np.arange(0.0, PERIOD_DEG, 2.0, dtype=np.float64)
    angles_rad = np.deg2rad(angles)
    normal_x = -np.sin(angles_rad)
    normal_y = np.cos(angles_rad)
    projections = (
        gradient_x[:, np.newaxis] * normal_x[np.newaxis, :]
        + gradient_y[:, np.newaxis] * normal_y[np.newaxis, :]
    )
    scores = np.sum(projections * projections, axis=0) / total_energy
    best_index = int(np.argmax(scores))
    best_angle = float(angles[best_index])
    distances = np.minimum(
        np.abs(angles - best_angle),
        PERIOD_DEG - np.abs(angles - best_angle),
    )
    competitor_scores = scores[distances >= 25.0]
    if not competitor_scores.size:
        return None, None, tuple(float(value) for value in histogram)
    best_score = float(scores[best_index])
    competitor = float(np.max(competitor_scores))
    confidence = (
        0.0 if best_score <= 0.0 else max(0.0, best_score - competitor) / best_score
    )
    return (
        best_angle,
        confidence,
        tuple(float(value) for value in histogram),
    )


def _segmentation_centroid(segmentation: object) -> tuple[float, float] | None:
    mask = np.asarray(getattr(segmentation, "mask"), dtype=bool)
    rows, columns = np.nonzero(mask)
    if not rows.size:
        return None
    return float(np.mean(columns)), float(np.mean(rows))


def _region_memberships(
    segmentations: tuple[object, ...],
    regions: dict[str, tuple[np.ndarray, ...]],
    *,
    source_shape: tuple[int, int],
) -> tuple[
    dict[tuple[str, int], list[str]],
    tuple[str, ...],
]:
    manual_shape = next(
        region.shape
        for values in regions.values()
        for region in values
    )
    scale_x = manual_shape[1] / float(source_shape[1])
    scale_y = manual_shape[0] / float(source_shape[0])
    memberships = {
        (class_name, component_index): []
        for class_name, values in regions.items()
        for component_index, _region in enumerate(values, start=1)
    }
    ambiguous: list[str] = []
    for segmentation in segmentations:
        centroid = _segmentation_centroid(segmentation)
        if centroid is None:
            continue
        x = int(np.clip(round(centroid[0] * scale_x), 0, manual_shape[1] - 1))
        y = int(np.clip(round(centroid[1] * scale_y), 0, manual_shape[0] - 1))
        matches = [
            (class_name, component_index)
            for class_name, values in regions.items()
            for component_index, region in enumerate(values, start=1)
            if bool(region[y, x])
        ]
        source_id = str(getattr(segmentation, "segmentation_id"))
        if len(matches) == 1:
            memberships[matches[0]].append(source_id)
        elif len(matches) > 1:
            ambiguous.append(source_id)
    return memberships, tuple(ambiguous)


def _build_instances(
    review_frames: tuple[ReviewFrame, ...],
    regions_by_frame: dict[int, dict[str, tuple[np.ndarray, ...]]],
    series: object,
    measurements_by_source_id: dict[str, object],
) -> tuple[tuple[RegionInstance, ...], tuple[dict[str, object], ...]]:
    instances: list[RegionInstance] = []
    molecule_rows: list[dict[str, object]] = []
    frames = series.expanded_aligned_stack.frames
    for frame in review_frames:
        segmentations = tuple(
            series.molecular_segmentations.get_segmentations(
                frame.frame_index,
                source_view="expanded_aligned",
            )
        )
        memberships, ambiguous = _region_memberships(
            segmentations,
            regions_by_frame[frame.frame_number],
            source_shape=frames[frame.frame_index].shape[:2],
        )
        ambiguous_set = set(ambiguous)
        for segmentation in segmentations:
            source_id = str(segmentation.segmentation_id)
            if source_id in ambiguous_set:
                molecule_rows.append(
                    {
                        "frame_number": frame.frame_number,
                        "class_name": "",
                        "component_index": "",
                        "source_id": source_id,
                        "status": "ambiguous_manual_overlap",
                        "angle_deg": "",
                        "confidence": "",
                        "method": "",
                    }
                )
        for (class_name, component_index), source_ids in memberships.items():
            (
                texture_axis,
                texture_confidence,
                texture_descriptor,
            ) = _domain_texture_features(
                frame.clean_path,
                regions_by_frame[frame.frame_number][class_name][
                    component_index - 1
                ],
            )
            measurements = [
                measurements_by_source_id[source_id]
                for source_id in source_ids
                if source_id in measurements_by_source_id
            ]
            available = [
                value
                for value in measurements
                if value.status == "available" and value.angle_deg is not None
            ]
            angles = [float(value.angle_deg) for value in available]
            confidences = [float(value.confidence) for value in available]
            mean = _periodic_mean(
                angles,
                [max(0.01, value) for value in confidences],
            )
            spread = (
                None
                if mean is None
                else float(
                    np.median(
                        [_axis_distance(value, mean) for value in angles]
                    )
                )
            )
            instances.append(
                RegionInstance(
                    frame_number=frame.frame_number,
                    class_name=class_name,
                    component_index=component_index,
                    source_ids=tuple(source_ids),
                    available_source_ids=tuple(
                        value.provenance.source_id for value in available
                    ),
                    mean_axis_deg=mean,
                    median_spread_deg=spread,
                    median_confidence=(
                        None
                        if not confidences
                        else float(np.median(confidences))
                    ),
                    texture_axis_deg=texture_axis,
                    texture_confidence=texture_confidence,
                    texture_descriptor=texture_descriptor,
                )
            )
            measurements_by_id = {
                value.provenance.source_id: value for value in measurements
            }
            for source_id in source_ids:
                value = measurements_by_id.get(source_id)
                molecule_rows.append(
                    {
                        "frame_number": frame.frame_number,
                        "class_name": class_name,
                        "component_index": component_index,
                        "source_id": source_id,
                        "status": (
                            "missing" if value is None else value.status
                        ),
                        "angle_deg": (
                            ""
                            if value is None or value.angle_deg is None
                            else float(value.angle_deg)
                        ),
                        "confidence": (
                            ""
                            if value is None or value.confidence is None
                            else float(value.confidence)
                        ),
                        "method": "" if value is None else value.method,
                    }
                )
    return tuple(instances), tuple(molecule_rows)


def _fit_prototypes(
    instances: tuple[RegionInstance, ...],
    *,
    excluded_frames: set[int] | None = None,
    angle_attribute: str = "mean_axis_deg",
) -> dict[str, float]:
    excluded = set() if excluded_frames is None else excluded_frames
    prototypes = {}
    for class_name in CLASS_COLORS:
        angles = [
            float(getattr(instance, angle_attribute))
            for instance in instances
            if (
                instance.class_name == class_name
                and instance.frame_number not in excluded
                and getattr(instance, angle_attribute) is not None
                and (
                    angle_attribute != "mean_axis_deg"
                    or len(instance.available_source_ids) >= 3
                )
            )
        ]
        mean = _periodic_mean(angles)
        if mean is not None:
            prototypes[class_name] = mean
    return prototypes


def _recommended_tolerances(
    instances: tuple[RegionInstance, ...],
    prototypes: dict[str, float],
    *,
    training_frames: set[int],
    angle_attribute: str = "mean_axis_deg",
) -> dict[str, float]:
    tolerances = {}
    for class_name, prototype in prototypes.items():
        distances = [
            _axis_distance(
                float(getattr(instance, angle_attribute)),
                prototype,
            )
            for instance in instances
            if (
                instance.frame_number in training_frames
                and instance.class_name == class_name
                and getattr(instance, angle_attribute) is not None
                and (
                    angle_attribute != "mean_axis_deg"
                    or len(instance.available_source_ids) >= 3
                )
            )
        ]
        other_distances = [
            _axis_distance(prototype, other)
            for other_name, other in prototypes.items()
            if other_name != class_name
        ]
        empirical = (
            8.0
            if not distances
            else max(5.0, float(np.quantile(distances, 0.9)) + 3.0)
        )
        separation_limit = (
            30.0
            if not other_distances
            else max(3.0, 0.45 * min(other_distances))
        )
        tolerances[class_name] = min(empirical, separation_limit)
    return tolerances


def _evaluate(
    instances: tuple[RegionInstance, ...],
    prototypes: dict[str, float],
    tolerances: dict[str, float],
    *,
    frames: set[int],
    reject_unknown: bool,
    angle_attribute: str = "mean_axis_deg",
) -> dict[str, object]:
    class_names = tuple(CLASS_COLORS)
    confusion = {
        expected: {predicted: 0 for predicted in (*class_names, "UNKNOWN")}
        for expected in class_names
    }
    rows = []
    correct = 0
    evaluated = 0
    for instance in instances:
        if (
            instance.frame_number not in frames
            or getattr(instance, angle_attribute) is None
            or (
                angle_attribute == "mean_axis_deg"
                and len(instance.available_source_ids) < 3
            )
        ):
            continue
        instance_angle = float(getattr(instance, angle_attribute))
        predicted = min(
            prototypes,
            key=lambda name: (
                _axis_distance(instance_angle, prototypes[name]),
                name,
            ),
        )
        distance = _axis_distance(
            instance_angle,
            prototypes[predicted],
        )
        if reject_unknown and distance > tolerances[predicted]:
            predicted = "UNKNOWN"
        confusion[instance.class_name][predicted] += 1
        evaluated += 1
        correct += int(predicted == instance.class_name)
        rows.append(
            {
                "instance_id": instance.instance_id,
                "expected": instance.class_name,
                "predicted": predicted,
                "angle_deg": instance_angle,
                "distance_to_prediction_deg": distance,
                "available_molecule_count": len(
                    instance.available_source_ids
                ),
            }
        )
    recalls = []
    for class_name in class_names:
        total = sum(confusion[class_name].values())
        if total:
            recalls.append(confusion[class_name][class_name] / total)
    return {
        "evaluated_instance_count": evaluated,
        "correct_instance_count": correct,
        "accuracy": None if not evaluated else correct / evaluated,
        "balanced_accuracy": (
            None if not recalls else float(np.mean(recalls))
        ),
        "confusion": confusion,
        "predictions": rows,
    }


def _leave_one_frame_out(
    instances: tuple[RegionInstance, ...],
    frame_numbers: tuple[int, ...],
    *,
    angle_attribute: str = "mean_axis_deg",
) -> dict[str, object]:
    predictions = []
    for frame_number in frame_numbers:
        prototypes = _fit_prototypes(
            instances,
            excluded_frames={frame_number},
            angle_attribute=angle_attribute,
        )
        if set(prototypes) != set(CLASS_COLORS):
            continue
        tolerances = _recommended_tolerances(
            instances,
            prototypes,
            training_frames=set(frame_numbers) - {frame_number},
            angle_attribute=angle_attribute,
        )
        result = _evaluate(
            instances,
            prototypes,
            tolerances,
            frames={frame_number},
            reject_unknown=False,
            angle_attribute=angle_attribute,
        )
        predictions.extend(result["predictions"])
    correct = sum(
        int(row["expected"] == row["predicted"]) for row in predictions
    )
    return {
        "evaluated_instance_count": len(predictions),
        "correct_instance_count": correct,
        "accuracy": (
            None if not predictions else correct / len(predictions)
        ),
        "predictions": predictions,
    }


def _calibrate_feature(
    instances: tuple[RegionInstance, ...],
    *,
    training_frames: set[int],
    validation_frames: set[int],
    frame_numbers: tuple[int, ...],
    angle_attribute: str,
) -> dict[str, object]:
    training_instances = tuple(
        instance
        for instance in instances
        if instance.frame_number in training_frames
    )
    prototypes = _fit_prototypes(
        training_instances,
        angle_attribute=angle_attribute,
    )
    if set(prototypes) != set(CLASS_COLORS):
        raise RuntimeError(
            f"Training frames do not provide all classes for {angle_attribute}."
        )
    tolerances = _recommended_tolerances(
        instances,
        prototypes,
        training_frames=training_frames,
        angle_attribute=angle_attribute,
    )
    return {
        "angle_attribute": angle_attribute,
        "prototype_angles_deg": prototypes,
        "recommended_tolerances_deg": tolerances,
        "held_out_validation": {
            "nearest": _evaluate(
                instances,
                prototypes,
                tolerances,
                frames=validation_frames,
                reject_unknown=False,
                angle_attribute=angle_attribute,
            ),
            "with_unknown": _evaluate(
                instances,
                prototypes,
                tolerances,
                frames=validation_frames,
                reject_unknown=True,
                angle_attribute=angle_attribute,
            ),
        },
        "leave_one_frame_out": _leave_one_frame_out(
            instances,
            frame_numbers,
            angle_attribute=angle_attribute,
        ),
    }


def _descriptor_distance(
    left: tuple[float, ...] | np.ndarray,
    right: tuple[float, ...] | np.ndarray,
) -> float:
    left_array = np.asarray(left, dtype=np.float64)
    right_array = np.asarray(right, dtype=np.float64)
    denominator = float(
        np.linalg.norm(left_array) * np.linalg.norm(right_array)
    )
    if denominator <= 0.0:
        return 1.0
    return float(
        np.clip(
            1.0 - float(np.dot(left_array, right_array)) / denominator,
            0.0,
            2.0,
        )
    )


def _fit_descriptor_prototypes(
    instances: tuple[RegionInstance, ...],
    *,
    training_frames: set[int],
) -> dict[str, tuple[float, ...]]:
    prototypes = {}
    for class_name in CLASS_COLORS:
        descriptors = [
            np.asarray(instance.texture_descriptor, dtype=np.float64)
            for instance in instances
            if (
                instance.frame_number in training_frames
                and instance.class_name == class_name
                and instance.texture_descriptor
            )
        ]
        if not descriptors:
            continue
        prototype = np.mean(np.stack(descriptors, axis=0), axis=0)
        total = float(np.sum(prototype))
        if total > 0.0:
            prototype /= total
        prototypes[class_name] = tuple(float(value) for value in prototype)
    return prototypes


def _descriptor_tolerances(
    instances: tuple[RegionInstance, ...],
    prototypes: dict[str, tuple[float, ...]],
    *,
    training_frames: set[int],
) -> dict[str, float]:
    tolerances = {}
    for class_name, prototype in prototypes.items():
        distances = [
            _descriptor_distance(instance.texture_descriptor, prototype)
            for instance in instances
            if (
                instance.frame_number in training_frames
                and instance.class_name == class_name
                and instance.texture_descriptor
            )
        ]
        separations = [
            _descriptor_distance(prototype, other)
            for other_name, other in prototypes.items()
            if other_name != class_name
        ]
        empirical = (
            0.1
            if not distances
            else float(np.quantile(distances, 0.9)) + 0.02
        )
        separation_limit = (
            0.5
            if not separations
            else 0.45 * min(separations)
        )
        tolerances[class_name] = min(empirical, separation_limit)
    return tolerances


def _evaluate_descriptor(
    instances: tuple[RegionInstance, ...],
    prototypes: dict[str, tuple[float, ...]],
    tolerances: dict[str, float],
    *,
    frames: set[int],
    reject_unknown: bool,
) -> dict[str, object]:
    class_names = tuple(CLASS_COLORS)
    confusion = {
        expected: {predicted: 0 for predicted in (*class_names, "UNKNOWN")}
        for expected in class_names
    }
    rows = []
    for instance in instances:
        if (
            instance.frame_number not in frames
            or not instance.texture_descriptor
        ):
            continue
        predicted = min(
            prototypes,
            key=lambda name: (
                _descriptor_distance(
                    instance.texture_descriptor,
                    prototypes[name],
                ),
                name,
            ),
        )
        distance = _descriptor_distance(
            instance.texture_descriptor,
            prototypes[predicted],
        )
        if reject_unknown and distance > tolerances[predicted]:
            predicted = "UNKNOWN"
        confusion[instance.class_name][predicted] += 1
        rows.append({
            "instance_id": instance.instance_id,
            "expected": instance.class_name,
            "predicted": predicted,
            "distance_to_prediction": distance,
            "available_molecule_count": len(instance.available_source_ids),
        })
    correct = sum(
        int(row["expected"] == row["predicted"]) for row in rows
    )
    recalls = []
    for class_name in class_names:
        total = sum(confusion[class_name].values())
        if total:
            recalls.append(confusion[class_name][class_name] / total)
    return {
        "evaluated_instance_count": len(rows),
        "correct_instance_count": correct,
        "accuracy": None if not rows else correct / len(rows),
        "balanced_accuracy": (
            None if not recalls else float(np.mean(recalls))
        ),
        "confusion": confusion,
        "predictions": rows,
    }


def _descriptor_leave_one_frame_out(
    instances: tuple[RegionInstance, ...],
    frame_numbers: tuple[int, ...],
) -> dict[str, object]:
    predictions = []
    all_frames = set(frame_numbers)
    for frame_number in frame_numbers:
        training_frames = all_frames - {frame_number}
        prototypes = _fit_descriptor_prototypes(
            instances,
            training_frames=training_frames,
        )
        if set(prototypes) != set(CLASS_COLORS):
            continue
        tolerances = _descriptor_tolerances(
            instances,
            prototypes,
            training_frames=training_frames,
        )
        result = _evaluate_descriptor(
            instances,
            prototypes,
            tolerances,
            frames={frame_number},
            reject_unknown=False,
        )
        predictions.extend(result["predictions"])
    correct = sum(
        int(row["expected"] == row["predicted"]) for row in predictions
    )
    return {
        "evaluated_instance_count": len(predictions),
        "correct_instance_count": correct,
        "accuracy": (
            None if not predictions else correct / len(predictions)
        ),
        "predictions": predictions,
    }


def _calibrate_texture_descriptor(
    instances: tuple[RegionInstance, ...],
    *,
    training_frames: set[int],
    validation_frames: set[int],
    frame_numbers: tuple[int, ...],
) -> dict[str, object]:
    prototypes = _fit_descriptor_prototypes(
        instances,
        training_frames=training_frames,
    )
    if set(prototypes) != set(CLASS_COLORS):
        raise RuntimeError(
            "Training frames do not provide all texture descriptor classes."
        )
    tolerances = _descriptor_tolerances(
        instances,
        prototypes,
        training_frames=training_frames,
    )
    prototype_peak_angles = {
        class_name: [
            float(index * 2)
            for index in np.argsort(np.asarray(prototype))[-3:][::-1]
        ]
        for class_name, prototype in prototypes.items()
    }
    return {
        "descriptor": "normalized_gradient_orientation_histogram_2deg",
        "descriptor_settings": {
            "periodicity_deg": PERIOD_DEG,
            "bin_count": 90,
            "bin_width_deg": 2.0,
            "region_erosion_px": 8,
            "high_pass_gaussian_sigma_px": 12.0,
            "histogram_smoothing_sigma_bins": 1.5,
            "distance": "cosine",
        },
        "prototype_histograms": {
            class_name: list(prototype)
            for class_name, prototype in prototypes.items()
        },
        "prototype_peak_angles_deg": prototype_peak_angles,
        "recommended_distance_tolerances": tolerances,
        "held_out_validation": {
            "nearest": _evaluate_descriptor(
                instances,
                prototypes,
                tolerances,
                frames=validation_frames,
                reject_unknown=False,
            ),
            "with_unknown": _evaluate_descriptor(
                instances,
                prototypes,
                tolerances,
                frames=validation_frames,
                reject_unknown=True,
            ),
        },
        "leave_one_frame_out": _descriptor_leave_one_frame_out(
            instances,
            frame_numbers,
        ),
    }


def _write_csv(path: Path, rows: tuple[dict[str, object], ...] | list) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_summary(report: dict[str, object], destination: Path) -> None:
    lines = [
        "# TTMAPP manual orientation calibration",
        "",
        f"- Frames: {report['frame_numbers']}",
        f"- Training frames: {report['training_frames']}",
        f"- Held-out frames: {report['validation_frames']}",
        f"- Region counts: {report['region_counts']}",
        f"- Molecules in regions: {report['molecule_count_by_class']}",
        f"- Available orientations: {report['available_count_by_class']}",
    ]
    for feature_name, feature in report["feature_results"].items():
        held_out = feature["held_out_validation"]
        loo = feature["leave_one_frame_out"]
        lines.extend(
            [
                "",
                f"## {feature_name}",
                "",
            ]
        )
        if "prototype_angles_deg" in feature:
            for class_name, angle in feature["prototype_angles_deg"].items():
                tolerance = feature["recommended_tolerances_deg"][class_name]
                lines.append(
                    f"- {class_name}: {angle:.2f} deg, "
                    f"candidate tolerance {tolerance:.2f} deg"
                )
        else:
            for class_name, angles in feature[
                "prototype_peak_angles_deg"
            ].items():
                tolerance = feature[
                    "recommended_distance_tolerances"
                ][class_name]
                lines.append(
                    f"- {class_name}: peaks {angles}, "
                    f"candidate distance tolerance {tolerance:.4f}"
                )
        lines.extend(
            [
                (
                    "- Held-out accuracy without forced unknown rejection: "
                    f"{held_out['nearest']['accuracy']}"
                ),
                (
                    "- Held-out balanced accuracy without rejection: "
                    f"{held_out['nearest']['balanced_accuracy']}"
                ),
                (
                    "- Held-out accuracy with unknown rejection: "
                    f"{held_out['with_unknown']['accuracy']}"
                ),
                f"- Leave-one-frame-out accuracy: {loo['accuracy']}",
            ]
        )
    lines.extend([
        "",
        "This is a calibration candidate from one correlated STM sequence. "
        "Promotion to an application preset requires acceptable held-out "
        "performance and manual review of the QC overlays.",
        "",
    ])
    destination.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = _parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    review_frames = _discover_review_frames(
        (args.review_dir, *tuple(args.extra_review_dir))
    )
    regions_by_frame = {}
    annotation_rows = []
    for frame in review_frames:
        regions = _extract_regions(frame)
        regions_by_frame[frame.frame_number] = regions
        _render_annotation_qc(
            frame,
            regions,
            args.output_dir
            / "annotation_qc"
            / f"frame_{frame.frame_number}_regions.png",
        )
        row = {"frame_number": frame.frame_number}
        row.update({
            f"{class_name.lower()}_region_count": len(values)
            for class_name, values in regions.items()
        })
        annotation_rows.append(row)
        print(
            f"Frame {frame.frame_number}: "
            + ", ".join(
                f"{name}={len(values)}"
                for name, values in regions.items()
            ),
            flush=True,
        )
    _write_csv(args.output_dir / "annotation_regions.csv", annotation_rows)
    if args.validate_only:
        return

    frame_indices = {frame.frame_index for frame in review_frames}
    subset_path = _build_subset_session(
        args.session,
        args.output_dir / "calibration_input.moltrack.json",
        frame_indices=frame_indices,
    )
    print(f"Loading subset session: {subset_path}", flush=True)
    session = load_moltrack_session(subset_path)
    series = restore_moltrack_image_series_from_session(session)
    build_moltrack_expanded_aligned_stack(series)
    progress_last = -1

    def progress(value) -> None:
        nonlocal progress_last
        if value.completed_count in {
            0,
            value.total_count,
        } or value.completed_count // 250 != progress_last // 250:
            progress_last = value.completed_count
            print(
                "Orientation "
                f"{value.completed_count}/{value.total_count}",
                flush=True,
            )

    orientation_result = estimate_series_molecular_orientations(
        series,
        frame_indices=sorted(frame_indices),
        source_view="expanded_aligned",
        progress_callback=progress,
    )
    measurements_by_source_id = {
        value.provenance.source_id: value
        for value in orientation_result.measurements
    }
    instances, molecule_rows = _build_instances(
        review_frames,
        regions_by_frame,
        series,
        measurements_by_source_id,
    )
    frame_numbers = tuple(frame.frame_number for frame in review_frames)
    training_frames = {
        value
        for value in frame_numbers
        if value < args.validation_start_frame
    }
    validation_frames = set(frame_numbers) - training_frames
    feature_results = {
        "molecular_axis_mean": _calibrate_feature(
            instances,
            training_frames=training_frames,
            validation_frames=validation_frames,
            frame_numbers=frame_numbers,
            angle_attribute="mean_axis_deg",
        ),
        "domain_texture_axis": _calibrate_feature(
            instances,
            training_frames=training_frames,
            validation_frames=validation_frames,
            frame_numbers=frame_numbers,
            angle_attribute="texture_axis_deg",
        ),
        "domain_texture_histogram": _calibrate_texture_descriptor(
            instances,
            training_frames=training_frames,
            validation_frames=validation_frames,
            frame_numbers=frame_numbers,
        ),
    }

    instance_rows = [
        {
            "instance_id": instance.instance_id,
            "frame_number": instance.frame_number,
            "class_name": instance.class_name,
            "component_index": instance.component_index,
            "molecule_count": len(instance.source_ids),
            "available_orientation_count": len(
                instance.available_source_ids
            ),
            "mean_axis_deg": (
                "" if instance.mean_axis_deg is None else instance.mean_axis_deg
            ),
            "median_spread_deg": (
                ""
                if instance.median_spread_deg is None
                else instance.median_spread_deg
            ),
            "median_confidence": (
                ""
                if instance.median_confidence is None
                else instance.median_confidence
            ),
            "texture_axis_deg": (
                ""
                if instance.texture_axis_deg is None
                else instance.texture_axis_deg
            ),
            "texture_confidence": (
                ""
                if instance.texture_confidence is None
                else instance.texture_confidence
            ),
            "split": (
                "training"
                if instance.frame_number in training_frames
                else "validation"
            ),
        }
        for instance in instances
    ]
    _write_csv(args.output_dir / "domain_instances.csv", instance_rows)
    _write_csv(args.output_dir / "molecule_measurements.csv", molecule_rows)
    region_counts = Counter(instance.class_name for instance in instances)
    molecule_counts = Counter()
    available_counts = Counter()
    for instance in instances:
        molecule_counts[instance.class_name] += len(instance.source_ids)
        available_counts[instance.class_name] += len(
            instance.available_source_ids
        )
    report = {
        "status": "single_sequence_calibration_candidate",
        "frame_numbers": list(frame_numbers),
        "training_frames": sorted(training_frames),
        "validation_frames": sorted(validation_frames),
        "validation_split": "temporal_block",
        "reference_scope": (
            "Only molecules inside manually outlined regions are evaluated. "
            "Unmarked domains and molecules are ignored."
        ),
        "region_counts": dict(region_counts),
        "molecule_count_by_class": dict(molecule_counts),
        "available_count_by_class": dict(available_counts),
        "orientation_measurement_count": len(
            orientation_result.measurements
        ),
        "orientation_failure_count": len(orientation_result.failures),
        "feature_results": feature_results,
        "caveat": (
            "All frames come from one correlated STM sequence. The candidate "
            "must not be treated as a universal TTMAPP preset without data "
            "from an independent acquisition."
        ),
    }
    (args.output_dir / "calibration_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    _write_summary(
        report,
        args.output_dir / "calibration_summary.md",
    )
    print(json.dumps(feature_results, indent=2), flush=True)
    print(f"Output: {args.output_dir.resolve()}", flush=True)


if __name__ == "__main__":
    main()
