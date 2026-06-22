from __future__ import annotations

from collections.abc import Iterable

from moltrack.core import MolecularDetection, MolecularDetectionSet

from .contract import MolTrackSam3BoxPrompt


SUPPORTED_SAM3_POSITIVE_BBOX_MODES = ("all_current", "selected_current", "manual_only")


class MolTrackSam3PromptValidationError(ValueError):
    """Raised when a SAM3 concept run would not have valid prompt inputs."""


def build_moltrack_sam3_prompt_batch(
    detections: MolecularDetectionSet,
    *,
    frame_index: int,
    source_view: str,
    positive_bbox_mode: str = "all_current",
    selected_detection_ids: Iterable[str] | None = None,
    manual_positive_bboxes: Iterable[tuple[float, float, float, float]] = (),
    manual_negative_bboxes: Iterable[tuple[float, float, float, float]] = (),
) -> tuple[MolTrackSam3BoxPrompt, ...]:
    if not isinstance(detections, MolecularDetectionSet):
        raise TypeError("detections must be a MolecularDetectionSet instance.")

    positive_bbox_mode = str(positive_bbox_mode).strip()
    if positive_bbox_mode not in SUPPORTED_SAM3_POSITIVE_BBOX_MODES:
        supported = ", ".join(SUPPORTED_SAM3_POSITIVE_BBOX_MODES)
        raise ValueError(f"Unsupported SAM3 positive_bbox_mode: {positive_bbox_mode!r}. Supported: {supported}.")

    current_detections = detections.get_detections(frame_index, source_view=source_view)
    prompts: list[MolTrackSam3BoxPrompt] = []

    for detection in _select_positive_detections(
        current_detections,
        positive_bbox_mode=positive_bbox_mode,
        selected_detection_ids=selected_detection_ids,
    ):
        prompts.append(
            MolTrackSam3BoxPrompt(
                bbox_xyxy=detection.bbox_xyxy,
                label=1,
                detection_id=detection.detection_id,
            )
        )

    for bbox_xyxy in manual_positive_bboxes:
        prompts.append(MolTrackSam3BoxPrompt(bbox_xyxy=bbox_xyxy, label=1))
    for bbox_xyxy in manual_negative_bboxes:
        prompts.append(MolTrackSam3BoxPrompt(bbox_xyxy=bbox_xyxy, label=0))

    if not any(prompt.label == 1 for prompt in prompts):
        raise MolTrackSam3PromptValidationError("SAM3 concept prompts require at least one positive bbox.")
    return tuple(prompts)


def _select_positive_detections(
    current_detections: list[MolecularDetection],
    *,
    positive_bbox_mode: str,
    selected_detection_ids: Iterable[str] | None,
) -> list[MolecularDetection]:
    if positive_bbox_mode == "all_current":
        return list(current_detections)
    if positive_bbox_mode == "manual_only":
        return []

    selected_ids = None if selected_detection_ids is None else {str(detection_id) for detection_id in selected_detection_ids}
    if selected_ids is None:
        return [detection for detection in current_detections if detection.selected]
    return [detection for detection in current_detections if detection.detection_id in selected_ids]
