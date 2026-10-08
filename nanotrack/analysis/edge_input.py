"""Per-frame ROI and frozen numerical geometry for existing edge models."""
from __future__ import annotations

import numpy as np
from skimage.draw import polygon2mask

from nanotrack.analysis.analysis_input import AnalysisInput
from nanotrack.core import PolygonROI


class EdgeInput:
    def __init__(self, numerical: AnalysisInput, polygon: PolygonROI):
        self.numerical = numerical
        self.polygon = polygon

    def frames_and_masks(self, frame_indices: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        first = self.numerical.frame(int(frame_indices[0]))
        if len(frame_indices) * first.values.size * 5 > 512 * 1024 * 1024:
            raise MemoryError("Wejście krawędzi przekracza 512 MiB. Wybierz krótszy zakres.")
        frames = np.empty((len(frame_indices), *first.values.shape), dtype=np.float32)
        masks = np.empty(frames.shape, dtype=bool)
        for local, index in enumerate(frame_indices):
            scalar = self.numerical.frame(int(index))
            points = scalar.geometry.source_to_display(self.polygon.as_array())
            masks[local] = polygon2mask(scalar.values.shape, points[:, [1, 0]]) & scalar.valid_mask
            frames[local] = self.numerical.model_frame(int(index))
        return frames, masks

    def source_polyline(self, frame_index: int, points: np.ndarray) -> np.ndarray | None:
        """Keep the longest connected supported segment; never bridge missing data."""
        points = np.asarray(points, dtype=np.float64)
        if len(points) < 2 or not np.isfinite(points).all():
            return None
        counts = np.maximum(1, np.ceil(np.max(np.abs(np.diff(points, axis=0)), axis=1) * 2)).astype(int)
        if counts.sum() > 1_000_000:
            raise ValueError("Polilinia przekracza limit sprawdzania ważności.")
        dense = np.concatenate([np.linspace(a, b, int(count)+1)[:-1]
                                for a, b, count in zip(points[:-1], points[1:], counts)] + [points[-1:]])
        recovered, valid = self.source_points(frame_index, dense)
        if valid.all():
            return self.numerical.frame(frame_index).geometry.display_to_source(points)
        runs = np.split(np.flatnonzero(valid), np.flatnonzero(np.diff(np.flatnonzero(valid)) != 1)+1)
        segments = [recovered[run] for run in runs if len(run) >= 2]
        if not segments:
            return None
        return max(segments, key=lambda segment: float(np.linalg.norm(np.diff(segment, axis=0), axis=1).sum()))

    def clip_source_polyline(self, frame_index: int, points: np.ndarray) -> np.ndarray | None:
        display = self.numerical.frame(frame_index).geometry.source_to_display(points)
        return self.source_polyline(frame_index, display)

    def source_points(self, frame_index: int, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        scalar = self.numerical.frame(frame_index)
        points = np.asarray(points, dtype=np.float64)
        height, width = scalar.values.shape
        valid = np.isfinite(points).all(axis=1)
        valid &= (points >= 0).all(axis=1) & (points <= [width-1, height-1]).all(axis=1)
        safe = np.clip(np.nan_to_num(points), [0, 0], [width-1, height-1])
        lower, upper = np.floor(safe).astype(int), np.ceil(safe).astype(int)
        for xs, ys in [(lower[:,0],lower[:,1]), (lower[:,0],upper[:,1]),
                       (upper[:,0],lower[:,1]), (upper[:,0],upper[:,1])]:
            valid &= scalar.valid_mask[ys, xs]
        return scalar.geometry.display_to_source(points), valid
