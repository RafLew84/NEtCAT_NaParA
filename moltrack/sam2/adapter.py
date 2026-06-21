from __future__ import annotations

from pathlib import Path

import numpy as np

from moltrack.core import MolecularSegmentation
from nanotrack.sam2 import Sam2RunInput, Sam2SubprocessBackend


class MolTrackSam2SegmentationError(RuntimeError):
    """Raised when SAM2 does not return a usable single-frame segmentation."""


class MolTrackSam2Segmenter:
    """Adapter that uses NanoTrack SAM2 as single-frame MolTrack segmentation."""

    def __init__(self, backend=None, *, model_name: str | None = None):
        self._backend = backend if backend is not None else Sam2SubprocessBackend()
        self._model_name = model_name

    def segment_detection(
        self,
        frame,
        detection,
        *,
        mask_probability_threshold: float = 0.5,
    ) -> MolecularSegmentation:
        run_input = self._build_run_input(
            frame,
            detection,
            mask_probability_threshold=mask_probability_threshold,
        )
        output = self._backend.run(run_input)
        masks = np.asarray(output.masks, dtype=bool)
        if masks.shape[0] != 1:
            raise MolTrackSam2SegmentationError("SAM2 single-frame segmentation must return exactly one mask.")
        if not bool(np.asarray(output.visible_mask, dtype=bool)[0]):
            raise MolTrackSam2SegmentationError("SAM2 did not return a visible mask for the selected BBox.")

        return MolecularSegmentation(
            frame_index=detection.frame_index,
            source_view=detection.source_view,
            bbox_xyxy=self._output_bbox_or_detection_bbox(output, detection),
            mask=masks[0],
            score=self._optional_first_float(output.mask_scores),
            origin="sam2",
            prompt_detection_ids=(detection.detection_id,),
            model_name=self._model_name_or_backend_checkpoint(),
            metadata=self._metadata_from_output(output),
        )

    def _build_run_input(
        self,
        frame,
        detection,
        *,
        mask_probability_threshold: float,
    ) -> Sam2RunInput:
        frame_array = np.asarray(frame, dtype=np.float32)
        if frame_array.ndim not in (2, 3):
            raise ValueError("SAM2 segmentation frame must have shape [H, W] or [H, W, C].")
        frames = frame_array[np.newaxis, ...]
        return Sam2RunInput(
            track_id=0,
            frame_index_offset=int(detection.frame_index),
            frames=frames,
            query_box_xyxy=np.asarray(detection.bbox_xyxy, dtype=np.float32),
            source_view=detection.source_view,
            mask_probability_threshold=mask_probability_threshold,
        )

    def _output_bbox_or_detection_bbox(self, output, detection) -> tuple[float, float, float, float]:
        mask_bboxes = output.mask_bboxes_xyxy
        if mask_bboxes is None:
            return detection.bbox_xyxy
        bbox = np.asarray(mask_bboxes, dtype=np.float32)[0]
        if bbox.shape != (4,) or not bool(np.all(np.isfinite(bbox))):
            return detection.bbox_xyxy
        x0, y0, x1, y1 = (float(value) for value in bbox)
        if x1 <= x0 or y1 <= y0:
            return detection.bbox_xyxy
        return x0, y0, x1, y1

    def _model_name_or_backend_checkpoint(self) -> str:
        if self._model_name:
            return str(self._model_name)
        config = getattr(self._backend, "config", None)
        checkpoint_path = getattr(config, "checkpoint_path", None)
        if checkpoint_path is None:
            return "sam2"
        return Path(checkpoint_path).name

    def _metadata_from_output(self, output) -> dict[str, float | int]:
        metadata: dict[str, float | int] = {}
        mask_area = self._optional_first_float(output.mask_areas)
        if mask_area is not None:
            metadata["mask_area_px"] = mask_area
        component_count = self._optional_first_int(output.mask_component_counts)
        if component_count is not None:
            metadata["mask_component_count"] = component_count
        return metadata

    def _optional_first_float(self, values) -> float | None:
        if values is None:
            return None
        array = np.asarray(values)
        if array.shape[0] == 0:
            return None
        return float(array[0])

    def _optional_first_int(self, values) -> int | None:
        if values is None:
            return None
        array = np.asarray(values)
        if array.shape[0] == 0:
            return None
        return int(array[0])
