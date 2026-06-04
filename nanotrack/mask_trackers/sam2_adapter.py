"""Adapter exposing the existing SAM2 backend through the mask-tracker contract."""

from __future__ import annotations

from pathlib import Path

from nanotrack.sam2 import Sam2BackendConfig, Sam2RunInput, Sam2RunOutput, Sam2SubprocessBackend

from .config import MaskTrackerBackendConfig, MaskTrackerKind, default_mask_tracker_config
from .contract import MaskTrackerRunInput, MaskTrackerRunOutput


def sam2_backend_config_from_mask_config(config: MaskTrackerBackendConfig) -> Sam2BackendConfig:
    """Build the legacy SAM2 backend config from the shared mask-tracker config."""

    if config.kind is not MaskTrackerKind.SAM2:
        raise ValueError("SAM2 adapter requires a MaskTrackerBackendConfig with kind='sam2'.")
    return Sam2BackendConfig(
        python_executable=config.python_executable,
        worker_script=config.worker_script,
        checkpoint_path=config.checkpoint_path,
        repo_path=config.repo_path,
        config_path=config.config_identifier,
        device=config.device,
        timeout_sec=config.timeout_sec,
        working_directory=config.working_directory,
    )


def sam2_run_input_from_mask_input(run_input: MaskTrackerRunInput) -> Sam2RunInput:
    """Convert the shared mask-tracker input into the existing SAM2 input contract."""

    if run_input.tracker_kind is not MaskTrackerKind.SAM2:
        raise ValueError("SAM2 adapter can only run inputs with tracker_kind='sam2'.")
    return Sam2RunInput(
        track_id=run_input.track_id,
        frame_index_offset=run_input.frame_index_offset,
        frames=run_input.frames,
        query_box_xyxy=run_input.query_box_xyxy,
        query_point_tyx=run_input.query_point_tyx,
        initial_mask=run_input.initial_mask,
        source_view=run_input.source_view,
        mask_probability_threshold=run_input.mask_probability_threshold,
    )


def mask_output_from_sam2_run_output(
    run_output: Sam2RunOutput,
    *,
    checkpoint_name: str | None = None,
) -> MaskTrackerRunOutput:
    """Convert the existing SAM2 output contract into the shared mask-tracker output."""

    return MaskTrackerRunOutput(
        tracker_kind=MaskTrackerKind.SAM2,
        track_id=run_output.track_id,
        frame_index_offset=run_output.frame_index_offset,
        masks=run_output.masks,
        visible_mask=run_output.visible_mask,
        mask_areas=run_output.mask_areas,
        mask_bboxes_xyxy=run_output.mask_bboxes_xyxy,
        mask_scores=run_output.mask_scores,
        mask_component_counts=run_output.mask_component_counts,
        model_name="sam2",
        checkpoint_name=checkpoint_name,
    )


class Sam2MaskTrackerBackend:
    """Common mask-tracker facade backed by the existing `Sam2SubprocessBackend`."""

    def __init__(
        self,
        config: MaskTrackerBackendConfig | Sam2BackendConfig | None = None,
        backend: Sam2SubprocessBackend | None = None,
    ):
        if backend is not None:
            self.backend = backend
        else:
            self.backend = Sam2SubprocessBackend(self._coerce_sam2_config(config))

    def run(self, run_input: MaskTrackerRunInput) -> MaskTrackerRunOutput:
        sam2_input = sam2_run_input_from_mask_input(run_input)
        sam2_output = self.backend.run(sam2_input)
        return mask_output_from_sam2_run_output(
            sam2_output,
            checkpoint_name=self._checkpoint_name(),
        )

    def cancel(self) -> None:
        cancel = getattr(self.backend, "cancel", None)
        if callable(cancel):
            cancel()

    def _coerce_sam2_config(
        self,
        config: MaskTrackerBackendConfig | Sam2BackendConfig | None,
    ) -> Sam2BackendConfig:
        if config is None:
            config = default_mask_tracker_config(MaskTrackerKind.SAM2)
        if isinstance(config, Sam2BackendConfig):
            return config
        return sam2_backend_config_from_mask_config(config)

    def _checkpoint_name(self) -> str | None:
        backend_config = getattr(self.backend, "config", None)
        checkpoint_path = getattr(backend_config, "checkpoint_path", None)
        if checkpoint_path is None:
            return None
        return Path(checkpoint_path).name
