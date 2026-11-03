"""Portable evidence from matching original-image points, independent of a model runtime."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ImagePreparation:
    original_shape: tuple[int, int]
    model_shape: tuple[int, int]
    scale_xy: tuple[float, float]
    padding_ltrb: tuple[int, int, int, int]
    value_range: tuple[float, float]
    normalization: str = 'minmax-float32-v1'
    channels: int = 1


@dataclass(frozen=True)
class CorrespondenceDiagnostics:
    final_shift_xy: tuple[float, float] | None
    input_count: int
    valid_count: int
    inlier_count: int
    inlier_fraction: float
    reference_support: tuple[int, ...]
    moving_support: tuple[int, ...]
    reference_span_xy: tuple[float, float]
    moving_span_xy: tuple[float, float]
    median_residual_px: float | None
    status: str
    reason: str
    settings_text: str
    preparation: tuple[ImagePreparation, ...] = ()
    model_provenance: tuple[tuple[str, str], ...] = ()
    settings_version: int = 1


class CorrespondenceRefusal(ValueError):
    """An explicit lack of global support, distinct from runtime/weight failures."""

    def __init__(self, diagnostics: CorrespondenceDiagnostics) -> None:
        super().__init__(diagnostics.reason)
        self.diagnostics = diagnostics
