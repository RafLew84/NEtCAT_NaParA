"""Prepare one image and its overlays together, without any Qt objects."""

from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock

import numpy as np

from stmdomains.core.annotations import FrameAnnotations
from stmdomains.core.display import RenderedImage, contrast_limits, render_image
from stmdomains.core.domain_results import DomainResult, FrameResult
from stmdomains.core.registration import parse_registration
from stmdomains.core.series import FrameData, Series
from stmdomains.io.annotations import AnnotationStore


@dataclass(frozen=True)
class PresentedFrame:
    series_id: str
    frame: FrameData
    rendered: RenderedImage
    mode: str
    field_rect: tuple[float, float, float, float]
    annotations: FrameAnnotations
    registration_text: str
    masks: RenderedImage | None
    gamma: float = 1.0
    result: FrameResult | None = None


class FramePresenter:
    """Bound image cache independently from the store's lazy mask cache."""

    def __init__(self, series: Series, *, result: DomainResult | None = None) -> None:
        if result is not None and result.series_id != series.identity:
            raise ValueError("Wynik należy do innej serii.")
        self.series = series
        self.result = result
        self.registration = parse_registration(
            series.raw_payload.get("registration"), series.frame_count, series.frame_shape,
        )
        self.annotations = AnnotationStore(
            series.raw_payload, series.frame_count, self.registration, series.frame_shape,
        )
        self._images: OrderedDict[tuple[int, str, float], RenderedImage] = OrderedDict()
        self._contrast: dict[int, tuple[float, float] | None] = {}
        self._lock = RLock()

    @property
    def image_cache_bytes(self) -> int:
        with self._lock:
            return sum(item.rgba.nbytes for item in self._images.values())

    @property
    def initial_mode(self) -> str:
        ui = self.series.raw_payload.get("ui")
        saved = ui.get("registration_view_mode") if isinstance(ui, dict) else None
        if self.registration.available and saved in ("expanded_aligned", "Show expanded aligned"):
            return "expanded_aligned"
        return "raw"

    def present(self, index: int, mode: str = "raw", gamma: float = 1.0) -> PresentedFrame:
        with self._lock:
            frame = self.series.frame(index)
            key = index, mode, gamma
            rendered = self._images.get(key)
            if rendered is None:
                if index not in self._contrast:
                    self._contrast[index] = contrast_limits(frame.image)
                samples = self.registration.image(frame.image, index, mode)
                rendered = render_image(samples, reference=frame.image, gamma=gamma,
                                        limits=self._contrast[index])
                if rendered.rgba.nbytes <= 32 * 1024**2:
                    self._images[key] = rendered
            if key in self._images:
                self._images.move_to_end(key)
            while len(self._images) > 3 or self.image_cache_bytes > 32 * 1024**2:
                self._images.popitem(last=False)
            annotations = self.annotations.frame(index, mode)
            union = np.zeros(rendered.rgba.shape[:2], dtype=bool)
            has_mask = False
            for segmentation in annotations.segmentations:
                if segmentation.mask is not None:
                    union |= segmentation.mask
                    has_mask = True
            masks = None
            if has_mask:
                rgba = np.zeros_like(rendered.rgba)
                rgba[union] = (80, 220, 170, 255)
                masks = RenderedImage(rgba, bool(union.any()))
            return PresentedFrame(
                self.series.identity, frame, rendered, mode,
                self.registration.field_rect(index, mode), annotations,
                self.registration.describe(index), masks, gamma,
                None if self.result is None else self.result.frame(index),
            )
