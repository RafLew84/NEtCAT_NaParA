"""Helpers for selecting edge component candidates from an edge map."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from skimage import measure
from skimage.morphology import skeletonize


@dataclass(frozen=True)
class EdgeComponentCandidate:
    """Quality-ranked connected component inside the polygon ROI."""

    edge_mask: np.ndarray
    label_id: int
    score: float
    sum_probability: float
    mean_probability: float
    median_probability: float
    pixel_count: int
    skeleton_length_px: float
    branch_count: int
    bbox: tuple[int, int, int, int]
    continuity_score: float
    thickness_penalty: float
    fragmentation_penalty: float
    prior_overlap: float
    reason: str

    def __post_init__(self) -> None:
        edge_mask = np.asarray(self.edge_mask, dtype=bool)
        if edge_mask.ndim != 2:
            raise ValueError("edge_mask must have shape [H, W].")
        object.__setattr__(self, "edge_mask", edge_mask)
        object.__setattr__(self, "label_id", int(self.label_id))
        object.__setattr__(self, "score", float(self.score))
        object.__setattr__(self, "sum_probability", float(self.sum_probability))
        object.__setattr__(self, "mean_probability", float(self.mean_probability))
        object.__setattr__(self, "median_probability", float(self.median_probability))
        object.__setattr__(self, "pixel_count", int(self.pixel_count))
        object.__setattr__(self, "skeleton_length_px", float(self.skeleton_length_px))
        object.__setattr__(self, "branch_count", int(self.branch_count))
        object.__setattr__(self, "bbox", tuple(int(value) for value in self.bbox))
        object.__setattr__(self, "continuity_score", float(self.continuity_score))
        object.__setattr__(self, "thickness_penalty", float(self.thickness_penalty))
        object.__setattr__(self, "fragmentation_penalty", float(self.fragmentation_penalty))
        object.__setattr__(self, "prior_overlap", float(self.prior_overlap))
        object.__setattr__(self, "reason", str(self.reason))


@dataclass(frozen=True)
class DominantEdgeSelection:
    """One selected edge component inside the polygon ROI."""

    edge_mask: np.ndarray
    score: float
    pixel_count: int
    mean_probability: float
    selection_mode: str
    candidates: tuple[EdgeComponentCandidate, ...] = ()
    selected_candidates: tuple[EdgeComponentCandidate, ...] = ()
    quality_score: float = 0.0

    def __post_init__(self) -> None:
        edge_mask = np.asarray(self.edge_mask, dtype=bool)
        if edge_mask.ndim != 2:
            raise ValueError("edge_mask must have shape [H, W].")
        object.__setattr__(self, "edge_mask", edge_mask)
        object.__setattr__(self, "score", float(self.score))
        object.__setattr__(self, "pixel_count", int(self.pixel_count))
        object.__setattr__(self, "mean_probability", float(self.mean_probability))
        object.__setattr__(self, "selection_mode", str(self.selection_mode))
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "selected_candidates", tuple(self.selected_candidates))
        object.__setattr__(self, "quality_score", float(self.quality_score))


def _validate_edge_inputs(
    edge_prob: np.ndarray,
    polygon_mask: np.ndarray,
    *,
    threshold: float,
    prior_mask: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    edge_prob_f32 = np.asarray(edge_prob, dtype=np.float32)
    polygon_mask_bool = np.asarray(polygon_mask, dtype=bool)
    if edge_prob_f32.ndim != 2:
        raise ValueError("edge_prob must have shape [H, W].")
    if polygon_mask_bool.shape != edge_prob_f32.shape:
        raise ValueError("polygon_mask must match edge_prob shape.")
    if not np.any(polygon_mask_bool):
        raise ValueError("polygon_mask must contain at least one True pixel.")
    if not 0.0 <= float(threshold) <= 1.0:
        raise ValueError("threshold must be within [0, 1].")

    prior_mask_bool = None
    if prior_mask is not None:
        prior_mask_bool = np.asarray(prior_mask, dtype=bool)
        if prior_mask_bool.shape != edge_prob_f32.shape:
            raise ValueError("prior_mask must match edge_prob shape.")
    return edge_prob_f32, polygon_mask_bool, prior_mask_bool


def _bbox_from_mask(mask: np.ndarray) -> tuple[int, int, int, int]:
    rows, cols = np.nonzero(mask)
    if rows.size == 0:
        return (0, 0, 0, 0)
    return (int(rows.min()), int(cols.min()), int(rows.max()) + 1, int(cols.max()) + 1)


def _neighbor_count(mask: np.ndarray) -> np.ndarray:
    padded = np.pad(mask.astype(np.uint8, copy=False), 1, mode="constant")
    neighbors = np.zeros(mask.shape, dtype=np.uint8)
    for row_offset in range(3):
        for col_offset in range(3):
            if row_offset == 1 and col_offset == 1:
                continue
            neighbors += padded[row_offset : row_offset + mask.shape[0], col_offset : col_offset + mask.shape[1]]
    return neighbors


def _skeleton_quality_metrics(component_mask: np.ndarray) -> tuple[float, int, float, float, float]:
    skeleton = skeletonize(component_mask)
    skeleton_length = float(np.count_nonzero(skeleton))
    if skeleton_length <= 0.0:
        return 0.0, 0, 0.0, float(np.count_nonzero(component_mask)), 1.0

    neighbor_count = _neighbor_count(skeleton)
    branch_count = int(np.count_nonzero(skeleton & (neighbor_count > 2)))

    skeleton_labels = measure.label(skeleton, connectivity=2)
    fragment_count = int(skeleton_labels.max())
    if fragment_count <= 0:
        continuity_score = 0.0
        fragmentation_penalty = 1.0
    else:
        fragment_sizes = np.bincount(skeleton_labels[skeleton].ravel())
        largest_fragment = int(fragment_sizes[1:].max()) if fragment_sizes.size > 1 else 0
        continuity_score = float(largest_fragment / max(skeleton_length, 1.0))
        fragmentation_penalty = float(max(0, fragment_count - 1))

    pixel_count = float(np.count_nonzero(component_mask))
    thickness_penalty = max(0.0, pixel_count / max(skeleton_length, 1.0) - 1.0)
    return skeleton_length, branch_count, continuity_score, thickness_penalty, fragmentation_penalty


def rank_edge_component_candidates(
    edge_prob: np.ndarray,
    polygon_mask: np.ndarray,
    *,
    threshold: float = 0.5,
    prior_mask: np.ndarray | None = None,
) -> list[EdgeComponentCandidate]:
    """Return quality-ranked connected component candidates inside the ROI."""

    edge_prob_f32, polygon_mask_bool, prior_mask_bool = _validate_edge_inputs(
        edge_prob,
        polygon_mask,
        threshold=threshold,
        prior_mask=prior_mask,
    )
    candidate_mask = (edge_prob_f32 >= float(threshold)) & polygon_mask_bool
    if not np.any(candidate_mask):
        return []

    labels = measure.label(candidate_mask, connectivity=2)
    candidates: list[EdgeComponentCandidate] = []
    for label_id in range(1, int(labels.max()) + 1):
        component_mask = labels == label_id
        pixel_count = int(np.count_nonzero(component_mask))
        if pixel_count == 0:
            continue
        component_prob = edge_prob_f32[component_mask]
        sum_probability = float(np.sum(component_prob))
        mean_probability = float(np.mean(component_prob))
        median_probability = float(np.median(component_prob))
        (
            skeleton_length,
            branch_count,
            continuity_score,
            thickness_penalty,
            fragmentation_penalty,
        ) = _skeleton_quality_metrics(component_mask)
        prior_overlap = 0.0
        if prior_mask_bool is not None:
            prior_overlap = float(np.count_nonzero(component_mask & prior_mask_bool) / max(pixel_count, 1))

        score = (
            0.45 * sum_probability
            + 6.0 * mean_probability
            + 2.0 * median_probability
            + 0.25 * skeleton_length
            + 2.0 * continuity_score
            + 2.0 * prior_overlap
            - 1.2 * thickness_penalty
            - 1.5 * float(branch_count)
            - 2.0 * fragmentation_penalty
        )
        reason = (
            f"sum={sum_probability:.3f}; mean={mean_probability:.3f}; median={median_probability:.3f}; "
            f"len={skeleton_length:.1f}; continuity={continuity_score:.3f}; branches={branch_count}; "
            f"thickness_penalty={thickness_penalty:.3f}; fragmentation_penalty={fragmentation_penalty:.3f}; "
            f"prior_overlap={prior_overlap:.3f}"
        )
        candidates.append(
            EdgeComponentCandidate(
                edge_mask=component_mask,
                label_id=label_id,
                score=score,
                sum_probability=sum_probability,
                mean_probability=mean_probability,
                median_probability=median_probability,
                pixel_count=pixel_count,
                skeleton_length_px=skeleton_length,
                branch_count=branch_count,
                bbox=_bbox_from_mask(component_mask),
                continuity_score=continuity_score,
                thickness_penalty=thickness_penalty,
                fragmentation_penalty=fragmentation_penalty,
                prior_overlap=prior_overlap,
                reason=reason,
            )
        )

    candidates.sort(
        key=lambda candidate: (
            candidate.score,
            candidate.skeleton_length_px,
            candidate.mean_probability,
            candidate.sum_probability,
        ),
        reverse=True,
    )
    return candidates


def select_dominant_edge(
    edge_prob: np.ndarray,
    polygon_mask: np.ndarray,
    *,
    threshold: float = 0.5,
    max_components: int = 1,
    prior_mask: np.ndarray | None = None,
) -> DominantEdgeSelection:
    """Pick one dominant connected edge component inside the ROI.

    The main path ranks thresholded connected components by probability,
    skeleton length, continuity, branch count, thickness/blob penalties,
    fragmentation, and optional prior overlap. If no thresholded component exists,
    the function falls back to the single highest-probability pixel inside the ROI.
    """

    edge_prob_f32, polygon_mask_bool, _prior_mask_bool = _validate_edge_inputs(
        edge_prob,
        polygon_mask,
        threshold=threshold,
        prior_mask=prior_mask,
    )
    if int(max_components) <= 0:
        raise ValueError("max_components must be positive.")

    candidates = rank_edge_component_candidates(
        edge_prob_f32,
        polygon_mask_bool,
        threshold=threshold,
        prior_mask=prior_mask,
    )
    if candidates:
        selected_components = candidates[: int(max_components)]
        combined_mask = np.zeros_like(polygon_mask_bool, dtype=bool)
        for candidate in selected_components:
            combined_mask |= candidate.edge_mask
        total_score = float(sum(candidate.sum_probability for candidate in selected_components))
        total_pixels = int(np.count_nonzero(combined_mask))
        mean_probability = 0.0 if total_pixels == 0 else float(np.mean(edge_prob_f32[combined_mask]))
        selection_mode = "component"
        if len(selected_components) > 1:
            selection_mode = f"top_{len(selected_components)}_components"
        return DominantEdgeSelection(
            edge_mask=combined_mask,
            score=total_score,
            pixel_count=total_pixels,
            mean_probability=mean_probability,
            selection_mode=selection_mode,
            candidates=tuple(candidates),
            selected_candidates=tuple(selected_components),
            quality_score=float(sum(candidate.score for candidate in selected_components)),
        )

    masked_prob = np.where(polygon_mask_bool, edge_prob_f32, -np.inf)
    flat_index = int(np.argmax(masked_prob))
    peak_probability = float(masked_prob.flat[flat_index])
    peak_mask = np.zeros_like(polygon_mask_bool, dtype=bool)
    peak_mask.flat[flat_index] = True
    return DominantEdgeSelection(
        edge_mask=peak_mask,
        score=peak_probability,
        pixel_count=1,
        mean_probability=peak_probability,
        selection_mode="peak",
        quality_score=peak_probability,
    )
