"""Render review overlays for one TTMAPP frame from a saved MolTrack session."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.spatial import ConvexHull, QhullError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from moltrack.analysis import (  # noqa: E402
    MolecularFrameRange,
    TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET,
    analyze_molecular_frame_range,
    build_m6_point_overlay_from_analysis,
)
from moltrack.core import build_moltrack_expanded_aligned_stack  # noqa: E402
from moltrack.persistence import (  # noqa: E402
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
)


def _frame_local_session(
    source: Path,
    destination: Path,
    *,
    frame_index: int,
) -> Path:
    """Keep one frame's annotations while preserving registration for all frames."""

    payload = json.loads(source.read_text(encoding="utf-8"))
    frame_count = len(payload["working_series"]["source_frame_indices"])
    if not 0 <= frame_index < frame_count:
        raise ValueError("Requested frame lies outside the working series.")
    relative_source = payload["source"].get("path_relative_to_session")
    if relative_source:
        payload["source"]["path"] = str(
            (source.parent / str(relative_source)).resolve()
        )
    payload["molecular_detections"]["detections"] = [
        item
        for item in payload["molecular_detections"]["detections"]
        if int(item["frame_index"]) == frame_index
    ]
    payload["molecular_segmentations"]["segmentations"] = [
        item
        for item in payload["molecular_segmentations"]["segmentations"]
        if int(item["frame_index"]) == frame_index
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, separators=(",", ":")),
        encoding="utf-8",
    )
    return destination


def _normalize_image(image: np.ndarray) -> np.ndarray:
    values = np.asarray(image, dtype=np.float64)
    finite = np.isfinite(values)
    normalized = np.zeros(values.shape, dtype=np.float64)
    if np.any(finite):
        low, high = np.percentile(values[finite], (1.0, 99.0))
        normalized[finite] = np.clip(
            (values[finite] - low) / max(float(high - low), 1e-12),
            0.0,
            1.0,
        )
    return np.uint8(normalized * 255.0)


def _save_clean_image(image: np.ndarray, destination: Path) -> None:
    clean = Image.fromarray(_normalize_image(image), mode="L")
    clean = clean.resize(
        (clean.width * 2, clean.height * 2),
        Image.Resampling.LANCZOS,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    clean.save(destination)


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _scale_point(
    point: tuple[float, float],
    scale: int,
) -> tuple[float, float]:
    return float(point[0]) * scale, float(point[1]) * scale


def _component_color(component, colors) -> tuple[int, int, int]:
    for source_id in component.source_ids:
        if source_id in colors:
            return tuple(colors[source_id][:3])
    return 235, 190, 55


def _component_orientation(component) -> float | None:
    if component.orientation_reference_channel == "m3_lattice":
        return component.theta3_lattice_prototype_deg
    if component.orientation_reference_channel == "m6":
        return component.theta6_prototype_deg
    return None


def _render(
    image: np.ndarray,
    analysis,
    destination: Path,
    *,
    frame_number: int,
    centroid_label: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    scale = 2
    base = Image.fromarray(_normalize_image(image), mode="L").convert("RGB")
    base = base.resize(
        (base.width * scale, base.height * scale),
        Image.Resampling.LANCZOS,
    )
    sidebar_width = 500 * scale
    canvas = Image.new("RGB", (base.width + sidebar_width, base.height), "white")
    canvas.paste(base, (0, 0))
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)

    lattice = analysis.lattice_domain_analysis
    if lattice is None:
        raise RuntimeError("The analysis did not produce final lattice domains.")
    source_points = dict(
        zip(
            analysis.sample_coordinates.point_source_ids,
            analysis.sample_coordinates.source_points_xy_px,
        )
    )
    point_overlay = build_m6_point_overlay_from_analysis(
        analysis,
        mode="lattice_domains",
        opacity_percent=100,
        show_unassigned_points=True,
    )
    colors = dict(zip(point_overlay.source_ids, point_overlay.colors_rgba))
    statuses = dict(zip(point_overlay.source_ids, point_overlay.point_statuses))
    domains = tuple(lattice.domains)
    islands = tuple(lattice.small_ordered_islands)
    labels = {
        domain.lattice_domain_id: f"D{index:02d}"
        for index, domain in enumerate(domains, start=1)
    }
    labels.update({
        island.lattice_domain_id: f"I{index:02d}"
        for index, island in enumerate(islands, start=1)
    })

    for component in (*domains, *islands):
        points = np.asarray(
            [source_points[source_id] for source_id in component.source_ids],
            dtype=np.float64,
        )
        color = _component_color(component, colors)
        if len(points) >= 3:
            try:
                hull = ConvexHull(points)
                polygon = [
                    _scale_point(tuple(points[index]), scale)
                    for index in hull.vertices
                ]
                layer_draw.polygon(
                    polygon,
                    fill=(*color, 52 if component in domains else 28),
                    outline=(*color, 240),
                    width=3 * scale,
                )
            except QhullError:
                pass
        for bond in component.geometry.internal_first_shell_bonds:
            left = _scale_point(source_points[bond.source_ids[0]], scale)
            right = _scale_point(source_points[bond.source_ids[1]], scale)
            layer_draw.line((left, right), fill=(*color, 100), width=scale)

    for source_id, point in source_points.items():
        x, y = _scale_point(point, scale)
        status = statuses.get(source_id, "unassigned")
        rgba = colors.get(source_id, (145, 155, 165, 120))
        if status == "lattice_boundary":
            radius = 5 * scale
            layer_draw.line(
                (x - radius, y - radius, x + radius, y + radius),
                fill=(235, 55, 45, 255),
                width=2 * scale,
            )
            layer_draw.line(
                (x - radius, y + radius, x + radius, y - radius),
                fill=(235, 55, 45, 255),
                width=2 * scale,
            )
            continue
        radius = 4 * scale if status.startswith("lattice_domain") else 2 * scale
        layer_draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=tuple(rgba),
            outline=(
                (255, 255, 255, 235)
                if status.startswith("lattice_domain")
                else None
            ),
            width=scale,
        )

    label_font = _font(17 * scale)
    for component in (*domains, *islands):
        points = np.asarray(
            [source_points[source_id] for source_id in component.source_ids],
            dtype=np.float64,
        )
        x, y = _scale_point(tuple(np.mean(points, axis=0)), scale)
        text = (
            f"{labels[component.lattice_domain_id]} "
            f"{component.dominant_symmetry} n={component.molecule_count}"
        )
        box = layer_draw.textbbox((x, y), text, font=label_font, anchor="mm")
        layer_draw.rectangle(
            (box[0] - 5, box[1] - 3, box[2] + 5, box[3] + 3),
            fill=(0, 0, 0, 190),
        )
        layer_draw.text(
            (x, y),
            text,
            fill=(255, 255, 255, 255),
            font=label_font,
            anchor="mm",
        )

    canvas = Image.alpha_composite(canvas.convert("RGBA"), layer).convert("RGB")
    draw = ImageDraw.Draw(canvas)
    title_font = _font(22 * scale)
    text_font = _font(15 * scale)
    small_font = _font(13 * scale)
    left = base.width + 24 * scale
    y = 20 * scale
    draw.text(
        (left, y),
        f"TTMAPP - frame {frame_number}",
        fill="black",
        font=title_font,
    )
    y += 40 * scale
    lines = (
        f"Centroids: {centroid_label}",
        "First shell: 30-70 nm | TTMAPP manual preset",
        f"Points: {lattice.point_count} | domains: {len(domains)} | islands: {len(islands)}",
        (
            f"Assigned: {lattice.classified_molecule_count} "
            f"({100.0 * lattice.classified_molecule_fraction:.1f}%) | "
            f"boundary: {lattice.boundary_point_count}"
        ),
    )
    for line in lines:
        draw.text((left, y), line, fill="black", font=text_font)
        y += 28 * scale
    y += 12 * scale

    rows: list[dict[str, object]] = []
    for component in (*domains, *islands):
        label = labels[component.lattice_domain_id]
        row = {
            "review_label": label,
            "lattice_domain_id": component.lattice_domain_id,
            "component_type": component.component_type,
            "dominant_symmetry": component.dominant_symmetry,
            "molecule_count": component.molecule_count,
            "core_size": component.core_size,
            "halo_size": component.halo_size,
            "confidence": component.confidence,
            "orientation_reference_channel": component.orientation_reference_channel,
            "orientation_deg": _component_orientation(component),
            "theta3_lattice_deg": component.theta3_lattice_prototype_deg,
            "theta6_deg": component.theta6_prototype_deg,
            "median_bond_length_nm": component.geometry.median_bond_length_nm,
            "source_ids": ";".join(component.source_ids),
        }
        rows.append(row)
        color = _component_color(component, colors)
        draw.rectangle(
            (left, y + 3 * scale, left + 14 * scale, y + 17 * scale),
            fill=color,
            outline="black",
        )
        draw.text(
            (left + 22 * scale, y),
            (
                f"{label}: {component.dominant_symmetry}, "
                f"n={component.molecule_count}, conf={component.confidence:.2f}"
            ),
            fill="black",
            font=small_font,
        )
        y += 23 * scale
        if y > canvas.height - 80 * scale:
            break
    draw.text(
        (left, canvas.height - 58 * scale),
        "Red X: boundary | gray: unassigned | I: small island",
        fill=(75, 75, 75),
        font=small_font,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination)
    summary = {
        "frame_number_1_based": frame_number,
        "working_frame_index": frame_number - 1,
        "source_view": analysis.source_view,
        "centroid_mode": centroid_label,
        "point_count": lattice.point_count,
        "full_domain_count": len(domains),
        "small_ordered_island_count": len(islands),
        "classified_molecule_count": lattice.classified_molecule_count,
        "classified_molecule_fraction": lattice.classified_molecule_fraction,
        "boundary_point_count": lattice.boundary_point_count,
        "dominant_symmetry_counts": dict(
            Counter(domain.dominant_symmetry for domain in domains)
        ),
    }
    return rows, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--frame", type=int, default=255)
    args = parser.parse_args()
    frame_index = args.frame - 1
    args.output_dir.mkdir(parents=True, exist_ok=True)
    snapshot = _frame_local_session(
        args.session,
        args.output_dir / f"frame_{args.frame}_input_snapshot.moltrack.json",
        frame_index=frame_index,
    )
    print(f"Loading frame-local snapshot: {snapshot}", flush=True)
    session = load_moltrack_session(snapshot)
    print(
        f"Snapshot: {session.molecular_detections.detection_count} detections, "
        f"{session.molecular_segmentations.segmentation_count} segmentations.",
        flush=True,
    )
    series = restore_moltrack_image_series_from_session(session)
    source_view = (
        session.position_analysis.source_view
        if session.position_analysis is not None
        else "raw"
    )
    if source_view == "expanded_aligned":
        print("Building expanded aligned stack...", flush=True)
        build_moltrack_expanded_aligned_stack(series)
        image = series.expanded_aligned_stack.frames[frame_index]
    else:
        image = series.raw_frames[frame_index]
    _save_clean_image(
        image,
        args.output_dir / f"frame_{args.frame}_clean_registered.png",
    )

    summaries = {}
    for use_masks, slug, label in (
        (False, "bbox_centers", "bbox centers"),
        (True, "mask_centroids", "SAM mask centroids"),
    ):
        print(f"Analyzing frame {args.frame} with {label}...", flush=True)
        frame_result = analyze_molecular_frame_range(
            series,
            MolecularFrameRange(f"frame {args.frame}", frame_index, frame_index),
            source_view=source_view,
            use_segmentation_centroids=use_masks,
            m6_orientation_settings=TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET,
        ).frame_results[0]
        analysis = frame_result.m6_orientation_analysis
        if analysis is None:
            raise RuntimeError(
                "M3/M6 analysis unavailable: "
                f"{frame_result.m6_orientation_unavailability_reason}"
            )
        rows, summary = _render(
            image,
            analysis,
            args.output_dir / f"frame_{args.frame}_{slug}_domains.png",
            frame_number=args.frame,
            centroid_label=label,
        )
        csv_path = args.output_dir / f"frame_{args.frame}_{slug}_domains.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            if rows:
                writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        summaries[slug] = summary
        print(json.dumps(summary, indent=2), flush=True)

    (args.output_dir / "summary.json").write_text(
        json.dumps(
            {
                "source_session": str(args.session.resolve()),
                "source_mpp": session.source_path,
                "settings": TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET.to_dict(),
                "results": summaries,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Output: {args.output_dir.resolve()}", flush=True)


if __name__ == "__main__":
    main()
