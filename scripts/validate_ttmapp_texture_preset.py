"""Build an independent manual-review package for the TTMAPP texture preset."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Mapping

import numpy as np
from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from moltrack.analysis import (  # noqa: E402
    TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY,
    TTMAPP_TEXTURE_DOMAIN_PRESET,
    MolecularFrameRange,
    TextureDomainSessionState,
    analyze_texture_domain_range,
)
from moltrack.core import build_moltrack_expanded_aligned_stack  # noqa: E402
from moltrack.persistence import (  # noqa: E402
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
)


CALIBRATION_FRAME_NUMBERS = tuple(range(250, 269))
VALIDATION_FRAME_NUMBERS = tuple(range(210, 250))
_UNKNOWN_COLOR = (145, 150, 155)


def validate_independent_frame_range(
    first_frame: int,
    last_frame: int,
) -> tuple[int, ...]:
    first = int(first_frame)
    last = int(last_frame)
    if first <= 0 or last < first:
        raise ValueError("Frame range must use positive inclusive frame numbers.")
    selected = tuple(range(first, last + 1))
    if set(selected).intersection(CALIBRATION_FRAME_NUMBERS):
        raise ValueError(
            "Independent validation must not overlap calibration frames 250-268."
        )
    if selected != VALIDATION_FRAME_NUMBERS:
        raise ValueError(
            "This fixed validation protocol requires frames 210-249."
        )
    return selected


def _require_empty_output_directory(output_dir: Path) -> Path:
    destination = Path(output_dir)
    if destination.exists() and not destination.is_dir():
        raise ValueError("Validation output path must be a directory.")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(
            "Validation output directory is not empty; use a new directory "
            "to protect existing manual review data."
        )
    return destination


def _normalized_rgb(frame: np.ndarray) -> Image.Image:
    values = np.asarray(frame, dtype=np.float64)
    finite = np.isfinite(values)
    scaled = np.zeros(values.shape, dtype=np.float64)
    if np.any(finite):
        lower, upper = np.percentile(values[finite], (1.0, 99.0))
        if upper > lower:
            scaled[finite] = np.clip(
                (values[finite] - float(lower)) / float(upper - lower),
                0.0,
                1.0,
            )
    return Image.fromarray(np.uint8(scaled * 255), mode="L").convert("RGB")


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", int(size))
    except OSError:
        return ImageFont.load_default()


def _render_frame_pair(
    *,
    frame: np.ndarray,
    frame_number: int,
    frame_result,
    class_colors: Mapping[str, tuple[int, int, int]],
    class_labels: Mapping[str, str],
    review_indices: Mapping[str, int],
    clean_path: Path,
    overlay_path: Path,
    indexed_path: Path,
) -> Image.Image:
    clean = _normalized_rgb(frame)
    overlay = clean.convert("RGBA")
    draw = ImageDraw.Draw(overlay, mode="RGBA")
    counts = Counter(point.class_key for point in frame_result.points)
    for point in frame_result.points:
        color = class_colors.get(point.class_key, _UNKNOWN_COLOR)
        x = float(point.x_px)
        y = float(point.y_px)
        radius = 3.0
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=(*color, 190),
            outline=(255, 255, 255, 225),
            width=1,
        )
    summary = " ".join(
        [
            f"F{frame_number}",
            *(
                f"{label}:{counts[key]}"
                for key, label in class_labels.items()
            ),
            f"U:{counts[TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY]}",
        ]
    )
    draw.rectangle(
        (0, 0, overlay.width, 22),
        fill=(0, 0, 0, 205),
    )
    draw.text((5, 4), summary, fill=(255, 255, 255, 255), font=_font(11))
    clean_path.parent.mkdir(parents=True, exist_ok=True)
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    clean.resize(
        (clean.width * 2, clean.height * 2),
        resample=Image.Resampling.NEAREST,
    ).save(clean_path)
    rendered = overlay.convert("RGB").resize(
        (overlay.width * 2, overlay.height * 2),
        resample=Image.Resampling.NEAREST,
    )
    rendered.save(overlay_path)
    indexed = overlay.convert("RGB").resize(
        (overlay.width * 4, overlay.height * 4),
        resample=Image.Resampling.NEAREST,
    )
    indexed_draw = ImageDraw.Draw(indexed)
    indexed_font = _font(10)
    for point in frame_result.points:
        review_index = review_indices[point.source_id]
        x = int(round(float(point.x_px) * 4.0)) + 5
        y = int(round(float(point.y_px) * 4.0)) - 6
        label = str(review_index)
        text_box = indexed_draw.textbbox(
            (x, y),
            label,
            font=indexed_font,
        )
        if text_box[0] < 1:
            x += 1 - text_box[0]
        if text_box[1] < 1:
            y += 1 - text_box[1]
        if text_box[2] > indexed.width - 1:
            x -= text_box[2] - (indexed.width - 1)
        if text_box[3] > indexed.height - 1:
            y -= text_box[3] - (indexed.height - 1)
        text_box = indexed_draw.textbbox(
            (x, y),
            label,
            font=indexed_font,
        )
        indexed_draw.rectangle(
            (
                text_box[0] - 1,
                text_box[1] - 1,
                text_box[2] + 1,
                text_box[3] + 1,
            ),
            fill=(0, 0, 0),
        )
        indexed_draw.text(
            (x, y),
            label,
            fill=(255, 255, 255),
            font=indexed_font,
        )
    indexed_path.parent.mkdir(parents=True, exist_ok=True)
    indexed.save(indexed_path)
    return rendered


def _write_csv(
    path: Path,
    *,
    fieldnames: tuple[str, ...],
    rows: list[dict[str, object]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _build_contact_sheet(
    rendered_frames: list[tuple[int, Image.Image]],
    destination: Path,
) -> None:
    columns = min(4, max(1, len(rendered_frames)))
    thumbnail_width = 260
    thumbnail_height = 260
    caption_height = 24
    rows = (len(rendered_frames) + columns - 1) // columns
    sheet = Image.new(
        "RGB",
        (
            columns * thumbnail_width,
            rows * (thumbnail_height + caption_height),
        ),
        color=(245, 245, 245),
    )
    draw = ImageDraw.Draw(sheet)
    font = _font(13)
    for index, (frame_number, image) in enumerate(rendered_frames):
        row, column = divmod(index, columns)
        thumbnail = image.copy()
        thumbnail.thumbnail(
            (thumbnail_width, thumbnail_height),
            resample=Image.Resampling.LANCZOS,
        )
        left = column * thumbnail_width + (thumbnail_width - thumbnail.width) // 2
        top = row * (thumbnail_height + caption_height)
        sheet.paste(thumbnail, (left, top))
        draw.text(
            (column * thumbnail_width + 6, top + thumbnail_height + 3),
            f"Frame {frame_number}",
            fill=(20, 20, 20),
            font=font,
        )
    sheet.save(destination)


def _markdown_report(report: dict[str, object]) -> str:
    counts = report["prediction_counts"]
    lines = [
        "# TTMAPP texture preset independent validation",
        "",
        "## Status",
        "",
        "`awaiting_manual_reference` - predictions were generated without "
        "using these frames for tuning, but accuracy cannot be computed "
        "until the new frames are manually reviewed.",
        "",
        "## Scope",
        "",
        f"- Frames: {report['frame_numbers'][0]}-{report['frame_numbers'][-1]}.",
        f"- Source view: `{report['source_view']}`.",
        f"- Centroids: `{report['centroid_mode']}`.",
        f"- Preset: `{report['preset']['preset_id']}`.",
        "- Calibration frames 250-268 are excluded.",
        "- `tuning_performed=false`.",
        "- `all_points_from_segmentations=true`.",
        "- No parameter fitting or threshold selection was performed.",
        "",
        "## Predictions",
        "",
        f"- Molecules: {counts['total']}.",
        f"- A: {counts.get('orientation_a', 0)}.",
        f"- B: {counts.get('orientation_b', 0)}.",
        f"- C: {counts.get('orientation_c', 0)}.",
        f"- Unknown: {counts.get(TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY, 0)}.",
        f"- Assigned coverage: {report['assigned_coverage']:.3f}.",
        f"- Components: {report['component_count']}.",
        "",
        "## Manual review",
        "",
        "Inspect `review_contact_sheet.png` and the full-resolution files in "
        "`clean/` and `overlays/`. Use the numbered images in `indexed/` to "
        "match each marker to `review_id` in `manual_review.csv`, then enter "
        "`A`, `B`, `C`, `Unknown` or `ignore`. Metrics must be calculated "
        "only after that file contains independent reference labels.",
        "",
    ]
    return "\n".join(lines)


def write_texture_preset_validation_package(
    *,
    state: TextureDomainSessionState,
    frames_by_index: Mapping[int, np.ndarray],
    centroid_source_kinds: Mapping[tuple[int, str], str],
    output_dir: Path,
    source_session: Path,
) -> dict[str, object]:
    output_dir = _require_empty_output_directory(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.",
            dir=output_dir.parent,
        )
    )
    try:
        report = _write_texture_preset_validation_package_contents(
            state=state,
            frames_by_index=frames_by_index,
            centroid_source_kinds=centroid_source_kinds,
            output_dir=staging_dir,
            source_session=source_session,
        )
        if output_dir.exists():
            output_dir.rmdir()
        staging_dir.replace(output_dir)
    except BaseException:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    return report


def _write_texture_preset_validation_package_contents(
    *,
    state: TextureDomainSessionState,
    frames_by_index: Mapping[int, np.ndarray],
    centroid_source_kinds: Mapping[tuple[int, str], str],
    output_dir: Path,
    source_session: Path,
) -> dict[str, object]:
    if not isinstance(state, TextureDomainSessionState) or not state.computed:
        raise ValueError("A computed texture-domain state is required.")
    if state.settings.fingerprint != TTMAPP_TEXTURE_DOMAIN_PRESET.fingerprint:
        raise ValueError("The frozen TTMAPP texture preset is required.")
    if state.source_view != "expanded_aligned":
        raise ValueError("The validation source_view must be expanded_aligned.")
    if not state.use_segmentation_centroids:
        raise ValueError("Segmentation centroids are required for validation.")
    frame_numbers = tuple(
        frame_result.frame_index + 1
        for frame_result in sorted(
            state.frame_results,
            key=lambda value: value.frame_index,
        )
    )
    if frame_numbers != VALIDATION_FRAME_NUMBERS:
        raise ValueError(
            "Validation package requires exactly frames 210-249."
        )
    for frame_result in state.frame_results:
        frame_index = frame_result.frame_index
        frame_number = frame_index + 1
        if frame_index not in frames_by_index:
            raise ValueError(f"Missing image data for frame {frame_number}.")
        for point in frame_result.points:
            source_kind = centroid_source_kinds.get(
                (frame_index, point.source_id)
            )
            if source_kind != "segmentation":
                raise ValueError(
                    "Every validation point must come from a segmentation "
                    f"centroid; frame {frame_number}, source {point.source_id!r} "
                    f"has source kind {source_kind!r}."
                )
    output_dir = _require_empty_output_directory(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    class_labels = {
        class_definition.key: class_definition.short_label
        for class_definition in state.settings.classes
    }
    class_colors = {
        class_definition.key: class_definition.color_rgb
        for class_definition in state.settings.classes
    }
    prediction_rows: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []
    component_rows: list[dict[str, object]] = []
    frame_rows: list[dict[str, object]] = []
    rendered_frames: list[tuple[int, Image.Image]] = []
    total_counts: Counter[str] = Counter()

    for frame_result in sorted(
        state.frame_results,
        key=lambda value: value.frame_index,
    ):
        frame_index = frame_result.frame_index
        frame_number = frame_index + 1
        counts = Counter(point.class_key for point in frame_result.points)
        total_counts.update(counts)
        ordered_points = sorted(
            frame_result.points,
            key=lambda value: (value.y_px, value.x_px, value.source_id),
        )
        review_indices = {
            point.source_id: review_index
            for review_index, point in enumerate(ordered_points, start=1)
        }
        for point in ordered_points:
            source_kind = centroid_source_kinds.get(
                (frame_index, point.source_id)
            )
            review_index = review_indices[point.source_id]
            row = {
                "frame_number": frame_number,
                "working_frame_index": frame_index,
                "source_id": point.source_id,
                "review_id": f"{frame_number}:{review_index}",
                "review_index": review_index,
                "centroid_source_kind": source_kind,
                "x_px": point.x_px,
                "y_px": point.y_px,
                "predicted_class": class_labels.get(
                    point.class_key,
                    "Unknown",
                ),
                "predicted_class_key": point.class_key,
                "nearest_class_key": point.nearest_class_key,
                "nearest_distance": (
                    ""
                    if point.nearest_distance is None
                    else point.nearest_distance
                ),
                "margin": "" if point.margin is None else point.margin,
                "component_id": point.component_id,
            }
            prediction_rows.append(row)
            review_rows.append(
                {
                    **row,
                    "manual_class": "",
                    "manual_domain_id": "",
                    "review_status": "",
                    "notes": "",
                }
            )
        for component in frame_result.components:
            component_rows.append(
                {
                    "frame_number": frame_number,
                    "working_frame_index": frame_index,
                    "component_id": component.component_id,
                    "class_key": component.class_key,
                    "class_label": class_labels[component.class_key],
                    "molecule_count": component.molecule_count,
                    "centroid_x_px": component.centroid_x_px,
                    "centroid_y_px": component.centroid_y_px,
                }
            )
        point_count = len(frame_result.points)
        assigned_count = point_count - counts[
            TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY
        ]
        frame_rows.append(
            {
                "frame_number": frame_number,
                "working_frame_index": frame_index,
                "molecule_count": point_count,
                **{
                    f"{key}_count": counts[key]
                    for key in class_labels
                },
                "unknown_count": counts[
                    TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY
                ],
                "assigned_coverage": (
                    0.0 if point_count == 0 else assigned_count / point_count
                ),
                "component_count": len(frame_result.components),
            }
        )
        rendered = _render_frame_pair(
            frame=np.asarray(frames_by_index[frame_index]),
            frame_number=frame_number,
            frame_result=frame_result,
            class_colors=class_colors,
            class_labels=class_labels,
            review_indices=review_indices,
            clean_path=output_dir / "clean" / f"frame_{frame_number}_clean.png",
            overlay_path=(
                output_dir
                / "overlays"
                / f"frame_{frame_number}_texture_domains.png"
            ),
            indexed_path=(
                output_dir
                / "indexed"
                / f"frame_{frame_number}_review_ids.png"
            ),
        )
        rendered_frames.append((frame_number, rendered))

    prediction_fields = (
        "frame_number",
        "working_frame_index",
        "source_id",
        "review_id",
        "review_index",
        "centroid_source_kind",
        "x_px",
        "y_px",
        "predicted_class",
        "predicted_class_key",
        "nearest_class_key",
        "nearest_distance",
        "margin",
        "component_id",
    )
    _write_csv(
        output_dir / "predictions.csv",
        fieldnames=prediction_fields,
        rows=prediction_rows,
    )
    _write_csv(
        output_dir / "manual_review.csv",
        fieldnames=(
            *prediction_fields,
            "manual_class",
            "manual_domain_id",
            "review_status",
            "notes",
        ),
        rows=review_rows,
    )
    _write_csv(
        output_dir / "components.csv",
        fieldnames=(
            "frame_number",
            "working_frame_index",
            "component_id",
            "class_key",
            "class_label",
            "molecule_count",
            "centroid_x_px",
            "centroid_y_px",
        ),
        rows=component_rows,
    )
    _write_csv(
        output_dir / "frames.csv",
        fieldnames=(
            "frame_number",
            "working_frame_index",
            "molecule_count",
            *(f"{key}_count" for key in class_labels),
            "unknown_count",
            "assigned_coverage",
            "component_count",
        ),
        rows=frame_rows,
    )
    _build_contact_sheet(
        rendered_frames,
        output_dir / "review_contact_sheet.png",
    )
    total_points = sum(total_counts.values())
    unknown_count = total_counts[TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY]
    report: dict[str, object] = {
        "status": "awaiting_manual_reference",
        "analysis": "ttmapp_texture_preset_independent_validation",
        "source_session": str(Path(source_session)),
        "source_view": state.source_view,
        "centroid_mode": "segmentation",
        "centroid_source_counts": {
            "segmentation": total_points,
            "bbox_center": 0,
        },
        "frame_numbers": list(frame_numbers),
        "preset": {
            "preset_id": state.settings.preset_id,
            "settings_fingerprint": state.settings.fingerprint,
            "experimental": state.settings.experimental,
            "calibration_note": state.settings.calibration_note,
        },
        "protocol": {
            "calibration_frames_excluded": list(
                CALIBRATION_FRAME_NUMBERS
            ),
            "tuning_performed": False,
            "ground_truth_available": False,
            "uses_manual_boundaries_for_prediction": False,
            "all_points_from_segmentations": True,
        },
        "prediction_counts": {
            "total": total_points,
            **{
                key: total_counts[key]
                for key in (
                    *class_labels,
                    TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY,
                )
            },
        },
        "assigned_coverage": (
            0.0 if total_points == 0 else (total_points - unknown_count) / total_points
        ),
        "component_count": sum(
            len(frame_result.components)
            for frame_result in state.frame_results
        ),
        "artifacts": [
            "predictions.csv",
            "manual_review.csv",
            "components.csv",
            "frames.csv",
            "review_contact_sheet.png",
            "clean/",
            "overlays/",
            "indexed/",
        ],
    }
    (output_dir / "validation_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    (output_dir / "validation_report.md").write_text(
        _markdown_report(report),
        encoding="utf-8",
    )
    return report


def _collect_centroid_source_kinds(
    series,
    state: TextureDomainSessionState,
) -> dict[tuple[int, str], str]:
    source_kinds: dict[tuple[int, str], str] = {}
    segmentation_set = series.molecular_segmentations
    for frame_result in state.frame_results:
        segmentation_ids = set()
        if segmentation_set is not None:
            segmentation_ids = {
                segmentation.segmentation_id
                for segmentation in segmentation_set.get_segmentations(
                    frame_result.frame_index,
                    source_view=state.source_view,
                )
                if segmentation.mask is not None
            }
        for point in frame_result.points:
            source_kinds[
                (frame_result.frame_index, point.source_id)
            ] = (
                "segmentation"
                if point.source_id in segmentation_ids
                else "bbox_center"
            )
    return source_kinds


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply the fixed TTMAPP texture preset to independent frames and "
            "write a manual-review package."
        )
    )
    parser.add_argument("session", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--first-frame", type=int, default=210)
    parser.add_argument("--last-frame", type=int, default=249)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    output_dir = _require_empty_output_directory(args.output_dir)
    frame_numbers = validate_independent_frame_range(
        args.first_frame,
        args.last_frame,
    )
    print(f"Loading session: {args.session}", flush=True)
    session = load_moltrack_session(args.session)
    series = restore_moltrack_image_series_from_session(session)
    if frame_numbers[-1] > series.frame_count:
        raise ValueError(
            f"Frame {frame_numbers[-1]} exceeds the {series.frame_count}-frame series."
        )
    source_view = "expanded_aligned"
    print("Building expanded aligned stack...", flush=True)
    series.expanded_aligned_stack = build_moltrack_expanded_aligned_stack(
        series
    )
    source_frames = np.asarray(series.expanded_aligned_stack.frames)
    frame_range = MolecularFrameRange(
        name="Independent TTMAPP texture validation",
        start_frame=frame_numbers[0] - 1,
        end_frame=frame_numbers[-1] - 1,
    )

    def progress(completed: int, total: int, frame_index: int) -> None:
        print(
            f"Texture domains: {completed}/{total}, frame {frame_index + 1}",
            flush=True,
        )

    state = analyze_texture_domain_range(
        series,
        frame_range,
        source_view=source_view,
        settings=TTMAPP_TEXTURE_DOMAIN_PRESET,
        use_segmentation_centroids=True,
        progress_callback=progress,
    )
    centroid_source_kinds = _collect_centroid_source_kinds(series, state)
    frames_by_index = {
        frame_index: source_frames[frame_index]
        for frame_index in frame_range.frame_indices
    }
    report = write_texture_preset_validation_package(
        state=state,
        frames_by_index=frames_by_index,
        centroid_source_kinds=centroid_source_kinds,
        output_dir=output_dir,
        source_session=args.session.resolve(),
    )
    print(
        f"Validation package: {output_dir.resolve()} "
        f"({report['prediction_counts']['total']} molecules)",
        flush=True,
    )


if __name__ == "__main__":
    main()
