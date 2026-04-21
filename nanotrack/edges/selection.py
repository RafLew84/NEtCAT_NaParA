"""Helpers for selecting a single dominant edge from a DexiNed response."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from skimage import measure


@dataclass(frozen=True)
class DominantEdgeSelection:
    """One selected edge component inside the polygon ROI."""

    edge_mask: np.ndarray
    score: float
    pixel_count: int
    mean_probability: float
    selection_mode: str

    def __post_init__(self) -> None:
        edge_mask = np.asarray(self.edge_mask, dtype=bool)
        if edge_mask.ndim != 2:
            raise ValueError("edge_mask must have shape [H, W].")
        object.__setattr__(self, "edge_mask", edge_mask)
        object.__setattr__(self, "score", float(self.score))
        object.__setattr__(self, "pixel_count", int(self.pixel_count))
        object.__setattr__(self, "mean_probability", float(self.mean_probability))
        object.__setattr__(self, "selection_mode", str(self.selection_mode))


def select_dominant_edge(
    edge_prob: np.ndarray,
    polygon_mask: np.ndarray,
    *,
    threshold: float = 0.5,
) -> DominantEdgeSelection:
    """Pick one dominant connected edge component inside the ROI.

    The main path uses thresholded connected components and picks the component
    with the highest summed edge probability. If no thresholded component exists,
    the function falls back to the single highest-probability pixel inside the ROI.
    """

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

    candidate_mask = (edge_prob_f32 >= float(threshold)) & polygon_mask_bool
    if np.any(candidate_mask):
        labels = measure.label(candidate_mask, connectivity=2)
        best_label = None
        best_score = -np.inf
        best_count = -1
        best_mean = -np.inf
        for label_id in range(1, int(labels.max()) + 1):
            component_mask = labels == label_id
            pixel_count = int(np.count_nonzero(component_mask))
            if pixel_count == 0:
                continue
            component_prob = edge_prob_f32[component_mask]
            score = float(np.sum(component_prob))
            mean_probability = float(np.mean(component_prob))
            if (
                score > best_score
                or (score == best_score and pixel_count > best_count)
                or (score == best_score and pixel_count == best_count and mean_probability > best_mean)
            ):
                best_label = label_id
                best_score = score
                best_count = pixel_count
                best_mean = mean_probability
        if best_label is not None:
            return DominantEdgeSelection(
                edge_mask=labels == best_label,
                score=best_score,
                pixel_count=best_count,
                mean_probability=best_mean,
                selection_mode="component",
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
    )
