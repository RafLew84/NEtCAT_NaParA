from __future__ import annotations

from pathlib import Path

import numpy as np

from moltrack.core import MolecularDetection
from nanotrack.yolo import YoloRuntime, YoloRuntimeError


class MolTrackYoloError(RuntimeError):
    """Base error for MolTrack YOLO adapter failures."""


class MolTrackYoloDetector:
    """Thin adapter from NanoTrack YOLO runtime to MolTrack molecular detections."""

    def __init__(self, runtime=None):
        self._runtime = runtime if runtime is not None else YoloRuntime()

    def detect_frame(
        self,
        frame: np.ndarray,
        *,
        frame_index: int,
        checkpoint_path: str | Path,
        confidence_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        source_view: str = "raw",
    ) -> list[MolecularDetection]:
        frame_array = np.asarray(frame)
        try:
            runtime_detections = self._runtime.predict_frame(
                frame_array,
                model_path=checkpoint_path,
                conf_threshold=confidence_threshold,
                iou_threshold=iou_threshold,
            )
        except YoloRuntimeError as exc:
            raise MolTrackYoloError(str(exc) or exc.__class__.__name__) from exc
        return self._map_runtime_detections(
            runtime_detections,
            frame_shape=frame_array.shape[:2],
            frame_index=frame_index,
            checkpoint_path=checkpoint_path,
            source_view=source_view,
        )

    def detect_frames(
        self,
        frames: np.ndarray,
        *,
        frame_indices: list[int] | tuple[int, ...],
        checkpoint_path: str | Path,
        confidence_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        source_view: str = "raw",
    ) -> list[list[MolecularDetection]]:
        frames_array = np.asarray(frames)
        if frames_array.ndim < 3:
            raise ValueError("frames must have shape [T, H, W] or [T, H, W, C].")
        frame_indices = [int(index) for index in frame_indices]
        if len(frame_indices) != int(frames_array.shape[0]):
            raise ValueError("frame_indices length must match frames count.")
        try:
            runtime_detections_by_frame = self._runtime.predict_frames(
                frames_array,
                model_path=checkpoint_path,
                conf_threshold=confidence_threshold,
                iou_threshold=iou_threshold,
            )
        except YoloRuntimeError as exc:
            raise MolTrackYoloError(str(exc) or exc.__class__.__name__) from exc
        if len(runtime_detections_by_frame) != len(frame_indices):
            raise MolTrackYoloError("YOLO runtime returned a different number of frame results than requested.")

        detections_by_frame: list[list[MolecularDetection]] = []
        for frame, frame_index, runtime_detections in zip(frames_array, frame_indices, runtime_detections_by_frame):
            detections_by_frame.append(
                self._map_runtime_detections(
                    runtime_detections,
                    frame_shape=np.asarray(frame).shape[:2],
                    frame_index=frame_index,
                    checkpoint_path=checkpoint_path,
                    source_view=source_view,
                )
            )
        return detections_by_frame

    def _map_runtime_detections(
        self,
        runtime_detections,
        *,
        frame_shape: tuple[int, int],
        frame_index: int,
        checkpoint_path: str | Path,
        source_view: str,
    ) -> list[MolecularDetection]:
        checkpoint_text = str(checkpoint_path)
        detections: list[MolecularDetection] = []
        for runtime_detection in runtime_detections:
            bbox = runtime_detection.bbox
            detection = MolecularDetection(
                frame_index=frame_index,
                bbox_xyxy=bbox.as_tuple(),
                confidence=runtime_detection.confidence,
                selected=True,
                model_name=runtime_detection.model_name or Path(checkpoint_path).name,
                checkpoint_path=checkpoint_text,
                source_view=source_view,
            )
            detection.validate_within_frame(frame_shape)
            detections.append(detection)
        return detections
