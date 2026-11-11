"""E5 window geometry and post-freeze context diagnostics, without inference."""

from __future__ import annotations

import numpy as np

from .training.data import support_available
from .training.evaluate import _edges


def _xy(value, name="positions"):
    array = np.asarray(value, float)
    if array.size == 0:
        array = np.empty((0, 2), float)
    if array.ndim != 2 or array.shape[1] != 2 or not np.isfinite(array).all():
        raise ValueError(f"{name} must be a finite N-by-2 array")
    return array


def _mask(value, count, name):
    array = np.asarray(value)
    if array.shape != (count,) or array.dtype.kind != "b":
        raise ValueError(f"{name} must be a boolean node vector")
    return array


def snap_to_grid(xy, *, stride=16., origin=8.) -> np.ndarray:
    """Nearest point of origin + stride*k, resolving exact ties downward.

    The returned positions are ONLY patch centers. Keep original node IDs,
    coordinates, graph edges and truth anchors, including when several nodes
    snap to the same point. Do not clip positions to fit inside the image.
    """
    xy = _xy(xy)
    if not np.isfinite(stride) or stride <= 0 or not np.isfinite(origin):
        raise ValueError("Grid stride must be positive and origin finite")
    return origin + stride * np.ceil((xy - origin) / stride - .5)


def window_support(xy, scale, measured, *, margin=3.) -> dict:
    """Use the historical conservative raw-pixel support, with no padding."""
    xy = _xy(xy)
    measured = np.asarray(measured)
    if measured.ndim != 2 or measured.dtype.kind != "b":
        raise ValueError("Measured support must be a boolean raster")
    if not np.isfinite(scale) or scale <= 0 or not np.isfinite(margin) or margin < 0:
        raise ValueError("Scale must be positive and margin nonnegative")
    nominal = np.column_stack((xy - scale / 2, xy + scale / 2))
    support = nominal + np.array([-margin, -margin, margin, margin])
    available = np.asarray([support_available(box, measured) for box in support], bool)
    return dict(patch_centers_xy=xy.copy(), nominal_boxes=nominal,
                support_boxes=support, available=available,
                scale_raw_px=float(scale), margin_raw_px=float(margin))


def support_masks(availability: dict, scope, edges) -> dict:
    """Intersect only the caller's explicitly selected comparison group.

    Pass a pair of variants for a paired contrast. A global intersection over
    unrelated families is not imposed. These are scoring masks: this function
    never rebuilds graphs or partitions, and never changes baseline gates.
    """
    scope = np.asarray(scope)
    if scope.ndim != 1 or scope.dtype.kind != "b" or not availability:
        raise ValueError("Supply a boolean scope and at least one variant")
    pairs = _edges(edges, len(scope))
    own = {name: scope & _mask(value, len(scope), str(name))
           for name, value in availability.items()}
    common = np.logical_and.reduce(list(own.values()))
    own_edges = {name: value[pairs].all(1) for name, value in own.items()}
    common_edges = common[pairs].all(1)
    counts = dict(planned_nodes=len(scope), scope_nodes=int(scope.sum()),
                  planned_edges=len(pairs), scope_edges=int(scope[pairs].all(1).sum()),
                  common_nodes=int(common.sum()), common_edges=int(common_edges.sum()),
                  own={name: dict(nodes=int(value.sum()), edges=int(own_edges[name].sum()),
                                  lost_to_common_nodes=int((value & ~common).sum()))
                       for name, value in own.items()})
    return dict(own=own, common=common, own_edges=own_edges,
                common_edges=common_edges, counts=counts)


def footprint_context(xy, scale, truth, kind, *, margin=0., anchor_xy=None, rois=()) -> dict:
    """POST-FREEZE context evidence, separate from window availability.

    Raster pixels intersecting each raw-edge footprint are counted using
    floor/ceil. ``anchor_xy`` remains the original graph location when a patch
    is snapped elsewhere. Synthetic purity requires the whole footprint to
    have the anchor's positive instance and valid reference. On measurements
    the corresponding statement is only containment in a known interior;
    no claim about a complete physical domain or boundary is made.

    Exploratory rectangle containment is returned separately and never turns
    into a label or a purity claim. A footprint outside the reference raster
    has unknown fractions, rather than silently clipped evaluation.
    """
    xy = _xy(xy)
    anchors = xy if anchor_xy is None else _xy(anchor_xy, "truth anchors")
    if anchors.shape != xy.shape or kind not in {"synthetic", "measurement"}:
        raise ValueError("Context anchors and reference kind must match")
    if not np.isfinite(scale) or scale <= 0 or not np.isfinite(margin) or margin < 0:
        raise ValueError("Scale must be positive and margin nonnegative")
    boxes = np.column_stack((xy - scale / 2 - margin, xy + scale / 2 + margin))
    n = len(xy)
    key = "domain_labels" if kind == "synthetic" else "region_instances"
    values = truth.get(key)
    labels = np.zeros(n, np.int64)
    anchor_valid = np.zeros(n, bool)
    inside = np.zeros(n, bool)
    known_fraction, anchor_fraction = np.full(n, np.nan), np.full(n, np.nan)
    instance_count = np.full(n, -1, np.int64)
    contained = np.zeros(n, bool)
    if values is not None:
        raster = np.asarray(values)
        if raster.ndim != 2 or raster.dtype.kind not in "iu" or np.any(raster < 0):
            raise ValueError("Context requires a nonnegative integer reference raster")
        valid = np.asarray(truth.get("evaluation_valid", np.ones(raster.shape, bool)))
        if valid.shape != raster.shape or valid.dtype.kind != "b":
            raise ValueError("Context evaluation validity must be a matching boolean raster")
        valid = valid.copy()
        for name in ("boundary_uncertain", "boundary_unscored"):
            if name in truth:
                uncertain = np.asarray(truth[name])
                if uncertain.shape != raster.shape or uncertain.dtype.kind != "b":
                    raise ValueError("Context uncertainty must be a matching boolean raster")
                valid &= ~uncertain
        if kind == "measurement":
            valid &= raster > 0
        height, width = raster.shape
        anchor_inside = (anchors >= 0).all(1) & (anchors < [width, height]).all(1)
        ii = np.floor(anchors[anchor_inside]).astype(int)
        labels[anchor_inside] = raster[ii[:, 1], ii[:, 0]]
        anchor_valid[anchor_inside] = valid[ii[:, 1], ii[:, 0]]
        inside = (boxes[:, :2] >= 0).all(1) & (boxes[:, 2:] <= [width, height]).all(1)
        for i in np.flatnonzero(inside):
            x0, y0 = np.floor(boxes[i, :2]).astype(int)
            x1, y1 = np.ceil(boxes[i, 2:]).astype(int)
            patch, good = raster[y0:y1, x0:x1], valid[y0:y1, x0:x1]
            known_fraction[i] = float(good.mean())
            instance_count[i] = len(np.unique(patch[good & (patch > 0)]))
            if anchor_valid[i] and labels[i] > 0:
                same = good & (patch == labels[i])
                anchor_fraction[i] = float(same.mean())
                contained[i] = bool(same.all())
    roi_contained, roi_anchor_inside = {}, {}
    for roi in rois:
        ident = str(roi["id"])
        if ident in roi_contained:
            raise ValueError("Exploratory ROI identifiers must be unique")
        bounds = np.asarray(roi.get("bbox_raw_xyxy", roi.get("bbox_xyxy")), float)
        if bounds.shape != (4,) or not np.isfinite(bounds).all() or np.any(bounds[2:] <= bounds[:2]):
            raise ValueError("Exploratory ROI needs a finite positive rectangle")
        roi_contained[ident] = ((boxes[:, :2] >= bounds[:2]).all(1)
                                & (boxes[:, 2:] <= bounds[2:]).all(1))
        roi_anchor_inside[ident] = ((anchors >= bounds[:2]).all(1)
                                    & (anchors < bounds[2:]).all(1))
    return dict(footprint_boxes=boxes, anchor_labels=labels, anchor_reference_valid=anchor_valid,
                footprint_inside_reference=inside, reference_known_fraction=known_fraction,
                anchor_domain_fraction=anchor_fraction, positive_instance_count=instance_count,
                pure_synthetic=contained if kind == "synthetic" else None,
                known_interior_contained=contained if kind == "measurement" else None,
                roi_contained=roi_contained, roi_anchor_inside=roi_anchor_inside,
                reference_scope="generator_domains" if kind == "synthetic" else "partial_interiors",
                unavailable_reason="missing_reference_raster" if values is None else None)
