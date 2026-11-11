"""E5 extraction-only rows: graph anchors and extraction centers stay explicit."""
from __future__ import annotations

from copy import deepcopy

import numpy as np

from .e5_support import snap_to_grid, window_support
from .training.data import transfer_membership

SCALES = (32, 48, 64)
CENTERINGS = ("exact", "snap", "shifted")


def patch_rows(record: dict, arrays: dict, base_rows: list[dict], *,
               scale: int = 48, centering: str = "exact") -> list[dict]:
    """Create independent rows compatible with historical extract_patch().

    window_id/element_id remain original anchor IDs, even for a different
    extraction scale. extraction_id is the variant-specific ID. raw_edge_xy
    is changed ONLY so extract_patch can read the new center; use base_rows
    or node_raw_edge_xy for graph and reference anchoring. Supports, measured
    availability and guarded transfer membership are recomputed, never copied.
    Scale, margin and the infinite 8+16k/16+16k lattice use reference pixels,
    converted to raw pixels by the saved isotropic pixel_spacing_xy. Ties go
    downward; there is no clipping to the field of view or padded extraction.
    """
    if isinstance(scale, bool) or scale not in SCALES or centering not in CENTERINGS:
        raise ValueError("Unknown E5 extraction scale or centering")
    origin = np.asarray(record.get("origin_in_expanded_xy", [0., 0.]), float)
    if origin.shape != (2,) or not np.isfinite(origin).all():
        raise ValueError("Expanded image origin must be finite xy")
    if any("extraction_id" in row for row in base_rows):
        raise ValueError("Start from original anchor rows, not an earlier extraction variant")
    ids = [row["window_id"] for row in base_rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Original anchor window IDs must be unique")
    if any(row["sample_id"] != record["sample_id"] for row in base_rows):
        raise ValueError("Anchor rows and image record must identify the same sample")
    spacing = np.asarray(record.get("pixel_spacing_xy", [1., 1.]), float)
    if spacing.shape != (2,) or not np.isfinite(spacing).all() or not np.allclose(spacing, spacing[0]) or spacing[0] <= 0:
        raise ValueError("E5 requires finite isotropic reference-pixel calibration")
    factor = float(spacing[0])
    for row in base_rows:
        expected = row.get("scale_px", row["scale_raw_px"]) / factor
        if not np.isclose(row["scale_raw_px"], expected):
            raise ValueError("Source row scale differs from its reference-pixel calibration")
    nodes = np.asarray([row["raw_edge_xy"] for row in base_rows], float).reshape(-1, 2)
    centers = nodes.copy() if centering == "exact" else snap_to_grid(
        nodes * factor, stride=16., origin=8. if centering == "snap" else 16.) / factor
    geometry = window_support(centers, scale / factor, arrays["measured"], margin=3. / factor)
    rows = []
    for i, base in enumerate(base_rows):
        support = geometry["support_boxes"][i]
        available = bool(geometry["available"][i])
        split, reason = (transfer_membership(record, support) if record.get("kind") != "synthetic"
                         else (None, None))
        if not available:
            split, reason = None, "incomplete_measured_support"
        row = deepcopy(base)
        row.update(
            extraction_id=f"{base['window_id']}@{centering}-s{scale}",
            extraction_centering=centering,
            source_scale_raw_px=base["scale_raw_px"],
            node_raw_edge_xy=nodes[i].tolist(),
            extraction_center_xy=centers[i].tolist(),
            displacement_xy=(centers[i] - nodes[i]).tolist(),
            displacement_reference_xy=((centers[i] - nodes[i]) * factor).tolist(),
            raw_edge_xy=centers[i].tolist(), scale_px=int(scale), scale_raw_px=scale / factor,
            pixel_spacing_xy=spacing.tolist(),
            feature_support_xyxy=geometry["nominal_boxes"][i].tolist(),
            support_xyxy=support.tolist(),
            expanded_support_xyxy=(support + np.tile(origin, 2)).tolist(),
            available=available,
            unavailable_reason=None if available else "incomplete_measured_support",
            transductive_split="fit" if available else None,
            transfer_split=split, transfer_exclusion_reason=reason,
        )
        rows.append(row)
    return rows
