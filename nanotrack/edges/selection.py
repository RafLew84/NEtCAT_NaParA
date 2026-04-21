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
    max_components: int = 1,
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
    if int(max_components) <= 0:
        raise ValueError("max_components must be positive.")

    candidate_mask = (edge_prob_f32 >= float(threshold)) & polygon_mask_bool
    if np.any(candidate_mask):
        labels = measure.label(candidate_mask, connectivity=2)
        component_stats: list[tuple[float, int, float, int]] = []
        for label_id in range(1, int(labels.max()) + 1):
            component_mask = labels == label_id
            pixel_count = int(np.count_nonzero(component_mask))
            if pixel_count == 0:
                continue
            component_prob = edge_prob_f32[component_mask]
            score = float(np.sum(component_prob))
            mean_probability = float(np.mean(component_prob))
            component_stats.append((score, pixel_count, mean_probability, label_id))
        if component_stats:
            component_stats.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
            selected_components = component_stats[: int(max_components)]
            selected_labels = {label_id for _score, _count, _mean, label_id in selected_components}
            combined_mask = np.isin(labels, list(selected_labels))
            total_score = float(sum(score for score, _count, _mean, _label_id in selected_components))
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
