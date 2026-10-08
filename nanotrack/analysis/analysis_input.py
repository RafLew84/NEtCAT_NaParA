"""Frozen numerical input and source-coordinate recovery for analysis models."""
from __future__ import annotations

from copy import deepcopy
import numpy as np
from scipy.ndimage import affine_transform

from nanotrack.core import BBoxXYXY, RegistrationResultSet, STMSequenceMetadata
from nanotrack.core.data_models import AnalysisShapeProvenance
from nanotrack.mask_trackers import MaskTrackerKind, MaskTrackerRunInput
from nanotrack.registration.scalar_frames import ScalarFrame, ScalarFrameProvider


class AnalysisInput:
    """Keep one execution independent of subsequent viewer/cache changes.

    Source arrays belong to an immutable source revision. Registration is copied
    at Start; numerical frames are materialized only for the requested range.
    Invalid pixels are filled solely in the model's finite working copy.
    """

    def __init__(
        self, frames: np.ndarray, metadata: STMSequenceMetadata, *, source_view: str,
        source_revision: str, registration: RegistrationResultSet | None = None,
        aligned: bool = False, expanded: bool = False,
        source_path: str = "", source_description: str = "",
    ):
        self._frames = frames
        self._provider = ScalarFrameProvider(frames, deepcopy(metadata), source_revision=source_revision)
        self._registration = deepcopy(registration)
        self._aligned = aligned
        self._expanded = expanded
        self._source_path = source_path
        self._source_description = source_description
        self.source_view = source_view + ("+expanded_registration" if expanded else "+registration" if aligned else "")

    def frame(self, frame_index: int) -> ScalarFrame:
        return self._provider.get_frame(
            frame_index, aligned=self._aligned, expanded=self._expanded, registration=self._registration,
        )

    def model_frame(self, frame_index: int) -> np.ndarray:
        scalar = self.frame(frame_index)
        finite = scalar.values[scalar.valid_mask]
        filled = np.where(scalar.valid_mask, scalar.values, np.median(finite) if finite.size else 0.)
        with np.errstate(over="ignore"):
            working = filled.astype(np.float32)
        if not np.isfinite(working).all():
            raise ValueError("Analysis model input exceeds the finite float32 range.")
        return working

    def tracker_input(
        self, tracker_kind: MaskTrackerKind | str, track_id: int, frame_index: int,
        bbox: BBoxXYXY, *, frame_limit: int | None, probability_threshold: float,
    ) -> MaskTrackerRunInput:
        if frame_limit is not None and frame_limit < 1:
            raise ValueError("frame_limit must be positive or None.")
        end = len(self._frames) if frame_limit is None else min(len(self._frames), frame_index + frame_limit)
        first = self.frame(frame_index)
        # Bound the unavoidable legacy model payload before allocating a stack.
        if (end-frame_index) * first.values.size * 4 > 512 * 1024 * 1024:
            raise MemoryError("Wejście trackera przekracza 512 MiB. Wybierz krótszy zakres Frames.")
        frames = np.empty((end-frame_index, *first.values.shape), dtype=np.float32)
        for local, index in enumerate(range(frame_index, end)):
            frames[local] = self.model_frame(index)
        points = first.geometry.source_to_display(np.array(bbox.as_tuple()).reshape(2, 2))
        center_x, center_y = points.mean(axis=0)
        return MaskTrackerRunInput(
            tracker_kind, track_id, frame_index, frames,
            query_box_xyxy=points.reshape(4), query_point_tyx=np.array([0., center_y, center_x]),
            source_view=self.source_view, mask_probability_threshold=probability_threshold,
        )

    def source_mask(self, frame_index: int, mask: np.ndarray) -> np.ndarray:
        scalar = self.frame(frame_index)
        if mask.shape != scalar.values.shape:
            raise ValueError("Analysis mask shape differs from its execution canvas.")
        dx, dy = scalar.geometry.offset_xy
        recovered = affine_transform(
            np.asarray(mask, dtype=bool) & scalar.valid_mask,
            matrix=np.eye(2), offset=(dy, dx), output_shape=self._frames.shape[1:],
            order=0, mode="grid-constant", cval=0, prefilter=False,
        )
        return recovered & np.isfinite(self._frames[frame_index])

    def provenance(self, frame_index: int, *, model_name: str, checkpoint_name: str | None = None) -> AnalysisShapeProvenance:
        scalar = self.frame(frame_index)
        height, width = scalar.values.shape
        return AnalysisShapeProvenance(
            self.source_view, scalar.source_revision, self._source_path, self._source_description,
            scalar.geometry.offset_xy, (height, width), scalar.registration_status, model_name, checkpoint_name,
        )

    def source_box(self, frame_index: int, bbox: BBoxXYXY) -> BBoxXYXY | None:
        """Clip a proposal to measured support, preserving subpixel box edges."""
        scalar = self.frame(frame_index)
        height, width = scalar.values.shape
        x0, y0 = max(0, int(np.floor(bbox.x0))), max(0, int(np.floor(bbox.y0)))
        x1, y1 = min(width, int(np.ceil(bbox.x1))), min(height, int(np.ceil(bbox.y1)))
        if x1 <= x0 or y1 <= y0:
            return None
        support = mask_bbox(scalar.valid_mask[y0:y1, x0:x1])
        if support is None:
            return None
        points = scalar.geometry.display_to_source([
            [max(bbox.x0, x0+support.x0), max(bbox.y0, y0+support.y0)],
            [min(bbox.x1, x0+support.x1), min(bbox.y1, y0+support.y1)],
        ])
        source_height, source_width = self._frames.shape[1:]
        points = np.clip(points, [0., 0.], [source_width, source_height])
        if np.any(points[1] <= points[0]):
            return None
        return BBoxXYXY(*points.reshape(4).tolist())


def mask_bbox(mask: np.ndarray) -> BBoxXYXY | None:
    ys, xs = np.nonzero(mask)
    if not xs.size:
        return None
    return BBoxXYXY(float(xs.min()), float(ys.min()), float(xs.max()+1), float(ys.max()+1))
