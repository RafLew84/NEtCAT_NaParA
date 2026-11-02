"""Scale, duplicate handling and pair histograms, adapted from the v0.4 method."""

from collections.abc import Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree

from stmdomains.core.annotations import Detection


def prepare_points(
    detections: tuple[Detection, ...], shape: tuple[int, int], check: Callable[[], None],
) -> tuple[list[Detection], NDArray[np.float64], float | None, dict[str, tuple[str, dict[str, Any]]]]:
    """Greedy suppression prefers manual/high-confidence points; ties use stable IDs."""
    height, width = shape
    excluded: dict[str, tuple[str, dict[str, Any]]] = {}
    candidates = []
    for detection in detections:
        x, y = detection.center_xy
        if detection.outside_field or not np.isfinite((x, y)).all() or not (0 <= x < width and 0 <= y < height):
            excluded[detection.detection_id] = ("outside_field", {})
        else:
            candidates.append(detection)
    candidates.sort(key=lambda item: (*item.center_xy[::-1], item.detection_id))
    if len(candidates) < 2:
        return candidates, np.asarray([d.center_xy for d in candidates], float).reshape(-1, 2), None, excluded
    points = np.asarray([d.center_xy for d in candidates], float)
    # The third neighbour gives a coarse scale even when every molecule has one
    # nearby duplicate. The final reported scale is NN median after suppression.
    distances = np.asarray(cKDTree(points).query(points, k=min(4, len(points)))[0])[:, -1]
    positive = distances[distances > 1e-9]
    coarse = float(np.median(positive)) if len(positive) else 0.
    cutoff = .4 * coarse
    neighbors = cKDTree(points).query_ball_point(points, max(cutoff, 1e-9), return_length=False)

    def rank(index: int) -> tuple[int, float, str]:
        record = candidates[index]
        confidence = record.metadata.get("confidence", 0.)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.
        if not np.isfinite(confidence):
            confidence = 0.
        manual = record.metadata.get("origin") == "manual"
        return -int(manual), -confidence, record.detection_id

    kept: set[int] = set()
    removed: set[int] = set()
    for index in sorted(range(len(points)), key=rank):
        check()
        if index in removed:
            continue
        kept.add(index)
        for other in neighbors[index]:
            if other == index or other in kept or other in removed:
                continue
            removed.add(other)
            excluded[candidates[other].detection_id] = (
                "suppressed_duplicate", {"kept_id": candidates[index].detection_id,
                                         "distance_px": float(np.linalg.norm(points[index] - points[other])),
                                         "cutoff_px": cutoff},
            )
    active = [candidates[index] for index in sorted(kept)]
    points = points[sorted(kept)]
    spacing = None
    if len(points) >= 2:
        nearest = np.asarray(cKDTree(points).query(points, k=2)[0])[:, 1]
        spacing = float(np.median(nearest))
    return active, points, spacing, excluded


def pair_features(
    points: NDArray[np.float64], spacing: float, check: Callable[[], None],
) -> tuple[NDArray[np.float64], NDArray[np.bool_], dict[str, NDArray[Any]]]:
    """Translation-invariant, orientation-sensitive square-root pair histograms."""
    n, nr, na = len(points), 14, 36
    tree = cKDTree(points)
    pairs = np.asarray(sorted(tree.query_pairs(2.8 * spacing)), int).reshape(-1, 2)
    vectors = points[pairs[:, 1]] - points[pairs[:, 0]]
    lengths = np.linalg.norm(vectors, axis=1)
    keep = lengths >= .55 * spacing
    pairs, vectors, lengths = pairs[keep], vectors[keep], lengths[keep]
    features = np.zeros((n, nr * na))
    neighbors = np.asarray(tree.query_ball_point(points, 2.5 * spacing, return_length=True)) - 1
    first_shell = np.asarray(tree.query_ball_point(points, 1.5 * spacing, return_length=True)) - 1
    diagnostics = {"neighbors": neighbors, "first_shell": first_shell}
    if not len(pairs):
        return features, np.zeros(n, bool), diagnostics
    midpoints = (points[pairs[:, 0]] + points[pairs[:, 1]]) / 2
    angles = np.mod(np.arctan2(vectors[:, 1], vectors[:, 0]), np.pi)
    rr = np.clip((lengths / spacing - .55) / 2.25 * (nr - 1), 0, nr - 1 - 1e-7)
    aa = angles / np.pi * na
    ri, ai = np.floor(rr).astype(int), np.floor(aa).astype(int)
    rf, af = rr - ri, aa - ai
    targets, values = [], []
    for dr, wr in ((0, 1 - rf), (1, rf)):
        for da, wa in ((0, 1 - af), (1, af)):
            targets.append((ri + dr) * na + (ai + da) % na)
            values.append(wr * wa)
    bins, factors = np.asarray(targets), np.asarray(values)
    sigma = 1.25 * spacing
    neighborhoods = cKDTree(midpoints).query_ball_point(points, 2.8 * sigma, return_length=False)
    for i, neighbors_i in enumerate(neighborhoods):
        check()
        indices = np.asarray(neighbors_i, int)
        if not len(indices):
            continue
        distance2 = np.sum((midpoints[indices] - points[i]) ** 2, axis=1)
        weights = np.exp(-distance2 / (2 * sigma**2) - lengths[indices] ** 2 / (8 * sigma**2))
        weights /= np.maximum(lengths[indices] / spacing, .5)
        features[i] = np.bincount(bins[:, indices].ravel(),
                                  weights=(factors[:, indices] * weights).ravel(), minlength=nr * na)
    histograms = gaussian_filter(features.reshape(n, nr, na), sigma=(0, .65, .95),
                                 mode=("nearest", "nearest", "wrap"))
    histograms /= np.maximum(histograms.sum(axis=(1, 2), keepdims=True), 1e-12)
    features = np.sqrt(histograms).reshape(n, -1)
    valid = np.isfinite(features).all(axis=1) & (np.linalg.norm(features, axis=1) > 0)
    return features, valid, diagnostics
