from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from moltrack.core import MolecularDetection, MolecularSegmentation, RegisteredFrameTransform
from nanotrack.sam2 import (
    Sam2BackendConfig,
    Sam2ImageBatchBackendConfig,
    Sam2ImageBatchInput,
    Sam2ImageBatchSubprocessBackend,
    Sam2PersistentImageBatchBackend,
    Sam2PersistentImageBatchBackendConfig,
    Sam2RunInput,
    Sam2SubprocessBackend,
    validate_sam2_image_batch_pair,
)


DEFAULT_SAM2_CHECKPOINT_DIR = Path(
    r"C:\Users\rlewa\Documents\PROJEKTY\trackleed\tracking_models\sam2"
)
DEFAULT_SAM2_CHECKPOINT_NAME = "sam2.1_hiera_base_plus.pt"


@dataclass(frozen=True)
class Sam2Checkpoint:
    path: Path

    @property
    def name(self) -> str:
        return self.path.name


def discover_sam2_checkpoints(directory: str | Path = DEFAULT_SAM2_CHECKPOINT_DIR) -> list[Sam2Checkpoint]:
    checkpoint_dir = Path(directory)
    if not checkpoint_dir.is_dir():
        return []
    return [Sam2Checkpoint(path) for path in sorted(checkpoint_dir.glob("sam2*.pt")) if path.is_file()]


def select_default_sam2_checkpoint(checkpoints) -> Sam2Checkpoint | None:
    checkpoint_list = list(checkpoints)
    for checkpoint in checkpoint_list:
        if _checkpoint_path(checkpoint).name == DEFAULT_SAM2_CHECKPOINT_NAME:
            return checkpoint
    if not checkpoint_list:
        return None
    return checkpoint_list[0]


def _checkpoint_path(checkpoint) -> Path:
    return Path(getattr(checkpoint, "path", checkpoint))


class MolTrackSam2SegmentationError(RuntimeError):
    """Raised when SAM2 does not return a usable single-frame segmentation."""


class MolTrackSam2PersistentImageSession:
    """Map one NanoTrack persistent backend session into MolTrack segmentations."""

    def __init__(self, segmenter, backend, checkpoint_path: Path | None) -> None:
        self._segmenter = segmenter
        self._backend = backend
        self._checkpoint_path = checkpoint_path
        self._backend_context = None
        self._backend_session = None

    def __enter__(self) -> "MolTrackSam2PersistentImageSession":
        self._backend_context = self._backend.open_session()
        self._backend_session = self._backend_context.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._backend_context is not None:
            self._backend_context.__exit__(exc_type, exc_value, traceback)
        self._backend_session = None
        self._backend_context = None

    def segment_frame_detections(self, frame, detections, **kwargs):
        if self._backend_session is None:
            raise RuntimeError("SAM2 persistent image session is not open.")
        kwargs.setdefault("chunk_size", 1)
        return self._segmenter._segment_frame_detections_using_backend(
            frame,
            detections,
            backend=self._backend,
            run_batch=self._backend_session.segment_frame,
            selected_checkpoint_path=self._checkpoint_path,
            **kwargs,
        )

    def cancel(self) -> None:
        target = self._backend_session or self._backend_context
        cancel = getattr(target, "cancel", None)
        if callable(cancel):
            cancel()

    @property
    def last_diagnostics(self):
        if self._backend_session is None:
            return None
        return getattr(self._backend_session, "last_diagnostics", None)


class MolTrackSam2Segmenter:
    """Adapter that uses NanoTrack SAM2 as single-frame MolTrack segmentation."""

    def __init__(
        self,
        backend=None,
        *,
        model_name: str | None = None,
        backend_factory=None,
        image_batch_backend=None,
        image_batch_backend_factory=None,
        persistent_image_batch_backend=None,
        persistent_image_batch_backend_factory=None,
    ):
        self._backend = backend if backend is not None else Sam2SubprocessBackend()
        self._model_name = model_name
        self._backend_factory = backend_factory
        self._image_batch_backend = (
            image_batch_backend
            if image_batch_backend is not None
            else Sam2ImageBatchSubprocessBackend()
        )
        self._image_batch_backend_factory = image_batch_backend_factory
        self._persistent_image_batch_backend = (
            persistent_image_batch_backend
            if persistent_image_batch_backend is not None
            else Sam2PersistentImageBatchBackend()
        )
        self._persistent_image_batch_backend_factory = (
            persistent_image_batch_backend_factory
        )

    def segment_frame_detections(
        self,
        frame,
        detections,
        *,
        mask_probability_threshold: float = 0.5,
        checkpoint_path=None,
        keep_largest_component: bool = False,
        min_mask_area_px: int = 0,
        existing_masks_policy: str | None = None,
        registered_transform: RegisteredFrameTransform | None = None,
        chunk_size: int = 32,
    ) -> list[MolecularSegmentation]:
        selected_checkpoint_path = (
            Path(checkpoint_path) if checkpoint_path is not None else None
        )
        backend = self._image_batch_backend_for_checkpoint(selected_checkpoint_path)
        return self._segment_frame_detections_using_backend(
            frame,
            detections,
            backend=backend,
            run_batch=backend.run,
            selected_checkpoint_path=selected_checkpoint_path,
            mask_probability_threshold=mask_probability_threshold,
            keep_largest_component=keep_largest_component,
            min_mask_area_px=min_mask_area_px,
            existing_masks_policy=existing_masks_policy,
            registered_transform=registered_transform,
            chunk_size=chunk_size,
        )

    def open_persistent_image_session(
        self,
        *,
        checkpoint_path=None,
    ) -> MolTrackSam2PersistentImageSession:
        selected_checkpoint_path = (
            Path(checkpoint_path) if checkpoint_path is not None else None
        )
        backend = self._persistent_image_batch_backend_for_checkpoint(
            selected_checkpoint_path
        )
        return MolTrackSam2PersistentImageSession(
            self,
            backend,
            selected_checkpoint_path,
        )

    def _segment_frame_detections_using_backend(
        self,
        frame,
        detections,
        *,
        backend,
        run_batch,
        selected_checkpoint_path: Path | None,
        mask_probability_threshold: float = 0.5,
        keep_largest_component: bool = False,
        min_mask_area_px: int = 0,
        existing_masks_policy: str | None = None,
        registered_transform: RegisteredFrameTransform | None = None,
        chunk_size: int = 32,
    ) -> list[MolecularSegmentation]:
        detections = list(detections)
        if not detections:
            return []
        if any(not isinstance(detection, MolecularDetection) for detection in detections):
            raise TypeError("detections must contain MolecularDetection instances.")
        frame_index = detections[0].frame_index
        source_view = detections[0].source_view
        if any(detection.frame_index != frame_index for detection in detections):
            raise ValueError("SAM2 frame batch detections must use one frame_index.")
        if any(detection.source_view != source_view for detection in detections):
            raise ValueError("SAM2 frame batch detections must use one source_view.")

        inference_detections = detections
        inference_source_view = source_view
        if source_view == "expanded_aligned":
            if registered_transform is None:
                raise ValueError(
                    "registered_transform is required for expanded_aligned SAM2 detections."
                )
            inference_detections = [
                registered_transform.expanded_detection_to_raw_prompt(detection)
                for detection in detections
            ]
            inference_source_view = "raw"

        frame_array = np.asarray(frame, dtype=np.float32)
        if frame_array.ndim not in (2, 3):
            raise ValueError("SAM2 segmentation frame must have shape [H, W] or [H, W, C].")
        run_input = Sam2ImageBatchInput(
            frame=frame_array,
            frame_index=frame_index,
            source_view=inference_source_view,
            boxes_xyxy=np.asarray(
                [detection.bbox_xyxy for detection in inference_detections],
                dtype=np.float32,
            ),
            prompt_detection_ids=tuple(
                detection.detection_id for detection in inference_detections
            ),
            mask_probability_threshold=mask_probability_threshold,
            chunk_size=int(chunk_size),
        )
        output = run_batch(run_input)
        validate_sam2_image_batch_pair(run_input, output)
        masks = np.asarray(output.masks, dtype=bool)
        if masks.shape[0] != len(inference_detections):
            raise MolTrackSam2SegmentationError(
                "SAM2 frame batch mask count does not match the prompt count."
            )

        segmentations = []
        for result_index, detection in enumerate(inference_detections):
            mask = self._postprocess_mask(
                masks[result_index],
                keep_largest_component=bool(keep_largest_component),
                min_mask_area_px=int(min_mask_area_px),
            )
            segmentation = MolecularSegmentation(
                frame_index=detection.frame_index,
                source_view="raw" if source_view == "expanded_aligned" else detection.source_view,
                bbox_xyxy=self._bbox_from_mask(mask),
                mask=mask,
                original_mask=mask.copy(),
                score=self._optional_index_float(output.mask_scores, result_index),
                origin="sam2",
                prompt_detection_ids=(detection.detection_id,),
                model_name=self._model_name_or_backend_checkpoint(
                    backend,
                    selected_checkpoint_path,
                ),
                metadata=self._metadata_from_batch_output(
                    output,
                    result_index,
                    selected_checkpoint_path,
                    mask=mask,
                    mask_probability_threshold=mask_probability_threshold,
                    keep_largest_component=bool(keep_largest_component),
                    min_mask_area_px=int(min_mask_area_px),
                    existing_masks_policy=existing_masks_policy,
                ),
            )
            if source_view == "expanded_aligned":
                segmentation = registered_transform.raw_segmentation_to_expanded(segmentation)
            segmentations.append(segmentation)
        return segmentations

    def segment_detection(
        self,
        frame,
        detection,
        *,
        mask_probability_threshold: float = 0.5,
        checkpoint_path=None,
        keep_largest_component: bool = False,
        min_mask_area_px: int = 0,
        existing_masks_policy: str | None = None,
    ) -> MolecularSegmentation:
        selected_checkpoint_path = Path(checkpoint_path) if checkpoint_path is not None else None
        backend = self._backend_for_checkpoint(selected_checkpoint_path)
        run_input = self._build_run_input(
            frame,
            detection,
            mask_probability_threshold=mask_probability_threshold,
        )
        output = backend.run(run_input)
        masks = np.asarray(output.masks, dtype=bool)
        if masks.shape[0] != 1:
            raise MolTrackSam2SegmentationError("SAM2 single-frame segmentation must return exactly one mask.")
        if not bool(np.asarray(output.visible_mask, dtype=bool)[0]):
            raise MolTrackSam2SegmentationError("SAM2 did not return a visible mask for the selected BBox.")
        mask = self._postprocess_mask(
            masks[0],
            keep_largest_component=bool(keep_largest_component),
            min_mask_area_px=int(min_mask_area_px),
        )
        mask_bbox = self._bbox_from_mask(mask)

        return MolecularSegmentation(
            frame_index=detection.frame_index,
            source_view=detection.source_view,
            bbox_xyxy=mask_bbox if mask_bbox is not None else self._output_bbox_or_detection_bbox(output, detection),
            mask=mask,
            original_mask=mask.copy(),
            score=self._optional_first_float(output.mask_scores),
            origin="sam2",
            prompt_detection_ids=(detection.detection_id,),
            model_name=self._model_name_or_backend_checkpoint(backend, selected_checkpoint_path),
            metadata=self._metadata_from_output(
                output,
                selected_checkpoint_path,
                mask=mask,
                mask_probability_threshold=mask_probability_threshold,
                keep_largest_component=bool(keep_largest_component),
                min_mask_area_px=int(min_mask_area_px),
                existing_masks_policy=existing_masks_policy,
            ),
        )

    def _backend_for_checkpoint(self, checkpoint_path: Path | None):
        if checkpoint_path is None:
            return self._backend
        if self._backend_factory is not None:
            return self._backend_factory(checkpoint_path)
        return Sam2SubprocessBackend(config=Sam2BackendConfig(checkpoint_path=checkpoint_path))

    def _image_batch_backend_for_checkpoint(self, checkpoint_path: Path | None):
        if checkpoint_path is None:
            return self._image_batch_backend
        if self._image_batch_backend_factory is not None:
            return self._image_batch_backend_factory(checkpoint_path)
        return Sam2ImageBatchSubprocessBackend(
            config=Sam2ImageBatchBackendConfig(checkpoint_path=checkpoint_path)
        )

    def _persistent_image_batch_backend_for_checkpoint(
        self,
        checkpoint_path: Path | None,
    ):
        if checkpoint_path is None:
            return self._persistent_image_batch_backend
        if self._persistent_image_batch_backend_factory is not None:
            return self._persistent_image_batch_backend_factory(checkpoint_path)
        return Sam2PersistentImageBatchBackend(
            config=Sam2PersistentImageBatchBackendConfig(
                checkpoint_path=checkpoint_path
            )
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

    def _postprocess_mask(
        self,
        mask,
        *,
        keep_largest_component: bool,
        min_mask_area_px: int,
    ) -> np.ndarray:
        processed = np.asarray(mask, dtype=bool)
        if processed.ndim != 2:
            raise MolTrackSam2SegmentationError("SAM2 mask must be a 2D array.")
        if keep_largest_component:
            processed = self._largest_component_mask(processed)
        area = int(np.count_nonzero(processed))
        if area == 0:
            raise MolTrackSam2SegmentationError("SAM2 returned an empty mask after post-processing.")
        if min_mask_area_px > 0 and area < min_mask_area_px:
            raise MolTrackSam2SegmentationError(
                f"SAM2 mask area {area} px is below Min mask area px {min_mask_area_px}."
            )
        return processed

    def _largest_component_mask(self, mask: np.ndarray) -> np.ndarray:
        height, width = mask.shape
        visited = np.zeros(mask.shape, dtype=bool)
        best_component: list[tuple[int, int]] = []
        for start_y, start_x in np.argwhere(mask):
            start_y = int(start_y)
            start_x = int(start_x)
            if visited[start_y, start_x]:
                continue
            stack = [(start_y, start_x)]
            visited[start_y, start_x] = True
            component: list[tuple[int, int]] = []
            while stack:
                y, x = stack.pop()
                component.append((y, x))
                for next_y, next_x in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if not (0 <= next_y < height and 0 <= next_x < width):
                        continue
                    if visited[next_y, next_x] or not mask[next_y, next_x]:
                        continue
                    visited[next_y, next_x] = True
                    stack.append((next_y, next_x))
            if len(component) > len(best_component):
                best_component = component
        largest = np.zeros(mask.shape, dtype=bool)
        for y, x in best_component:
            largest[y, x] = True
        return largest

    def _bbox_from_mask(self, mask: np.ndarray) -> tuple[float, float, float, float] | None:
        ys, xs = np.nonzero(mask)
        if ys.size == 0 or xs.size == 0:
            return None
        return float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)

    def _model_name_or_backend_checkpoint(self, backend, checkpoint_path: Path | None = None) -> str:
        if self._model_name:
            return str(self._model_name)
        if checkpoint_path is not None:
            return checkpoint_path.name
        config = getattr(backend, "config", None)
        checkpoint_path = getattr(config, "checkpoint_path", None)
        if checkpoint_path is None:
            return "sam2"
        return Path(checkpoint_path).name

    def _metadata_from_output(
        self,
        output,
        checkpoint_path: Path | None = None,
        *,
        mask,
        mask_probability_threshold: float,
        keep_largest_component: bool,
        min_mask_area_px: int,
        existing_masks_policy: str | None,
    ) -> dict[str, float | int | str | bool]:
        return self._build_metadata(
            checkpoint_path,
            mask=mask,
            mask_probability_threshold=mask_probability_threshold,
            keep_largest_component=keep_largest_component,
            min_mask_area_px=min_mask_area_px,
            existing_masks_policy=existing_masks_policy,
            component_count=self._optional_first_int(output.mask_component_counts),
        )

    def _metadata_from_batch_output(
        self,
        output,
        result_index: int,
        checkpoint_path: Path | None = None,
        *,
        mask,
        mask_probability_threshold: float,
        keep_largest_component: bool,
        min_mask_area_px: int,
        existing_masks_policy: str | None,
    ) -> dict[str, float | int | str | bool]:
        return self._build_metadata(
            checkpoint_path,
            mask=mask,
            mask_probability_threshold=mask_probability_threshold,
            keep_largest_component=keep_largest_component,
            min_mask_area_px=min_mask_area_px,
            existing_masks_policy=existing_masks_policy,
            component_count=self._optional_index_int(
                output.mask_component_counts,
                result_index,
            ),
        )

    def _build_metadata(
        self,
        checkpoint_path: Path | None,
        *,
        mask,
        mask_probability_threshold: float,
        keep_largest_component: bool,
        min_mask_area_px: int,
        existing_masks_policy: str | None,
        component_count: int | None,
    ) -> dict[str, float | int | str | bool]:
        metadata: dict[str, float | int | str | bool] = {}
        if checkpoint_path is not None:
            metadata["checkpoint_name"] = checkpoint_path.name
            metadata["checkpoint_path"] = str(checkpoint_path)
        metadata["sam2_threshold"] = float(mask_probability_threshold)
        metadata["keep_largest_component"] = bool(keep_largest_component)
        metadata["min_mask_area_px"] = int(min_mask_area_px)
        if existing_masks_policy is not None:
            metadata["existing_sam2_masks_policy"] = str(existing_masks_policy)
        metadata["mask_area_px"] = float(np.count_nonzero(mask))
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

    def _optional_index_float(self, values, index: int) -> float | None:
        if values is None:
            return None
        array = np.asarray(values)
        if not 0 <= int(index) < array.shape[0]:
            return None
        return float(array[int(index)])

    def _optional_index_int(self, values, index: int) -> int | None:
        if values is None:
            return None
        array = np.asarray(values)
        if not 0 <= int(index) < array.shape[0]:
            return None
        return int(array[int(index)])
