from __future__ import annotations
import numpy as np
from typing import Dict, Any, Tuple, Optional
from dataclasses import asdict
from .pipeline_spec import PipelineSpec

# Reuse helpers if masz je w pliku; jeśli nie, wklej te dwa:
def _apply_rect_roi(img: np.ndarray, rect_nm: Tuple[float, float, float, float],
                    nm_per_px: Tuple[Optional[float], Optional[float]]):
    """Extract rectangular ROI in pixel coords from nm-space rect (x,y,w,h in nm)."""
    sx, sy = nm_per_px
    if not (sx and sy and sx > 0 and sy > 0):
        x, y, w, h = rect_nm
        xs, ys, ws, hs = int(round(x)), int(round(y)), int(round(w)), int(round(h))
    else:
        x, y, w, h = rect_nm
        xs = max(0, int(np.floor(x / sx)))
        ys = max(0, int(np.floor(y / sy)))
        ws = max(1, int(np.round(w / sx)))
        hs = max(1, int(np.round(h / sy)))
    xs2 = min(img.shape[1], xs + ws)
    ys2 = min(img.shape[0], ys + hs)
    return (ys, ys2, xs, xs2), img[ys:ys2, xs:xs2]

def _rect_mask_to_full(mask_roi: np.ndarray, roi_slice, full_shape):
    """Place ROI mask back into full image canvas."""
    out = np.zeros(full_shape, dtype=bool)
    y0, y1, x0, x1 = roi_slice
    out[y0:y1, x0:x1] = mask_roi
    return out

def run_pipeline(
    img: np.ndarray,
    *,
    roi_rect_nm: Optional[Tuple[float, float, float, float]],   # (x,y,w,h) in nm; None -> whole image
    nm_per_px: Tuple[Optional[float], Optional[float]],         # (sx, sy) in nm/px
    spec: PipelineSpec,
) -> Dict[str, Any]:
    """
    NO-OP pipeline: returns an all-false mask and no contours.
    This keeps the interface stable while we iterate on visual testing of steps.
    """
    assert img.ndim == 2, "Expect 2D grayscale image"

    # Determine ROI slice (only for debug preview); whole image if ROI is None
    if roi_rect_nm is not None:
        roi_slice, roi_img = _apply_rect_roi(img, roi_rect_nm, nm_per_px)
    else:
        roi_slice = (0, img.shape[0], 0, img.shape[1])
        roi_img = img

    # Empty mask the size of full image
    empty_roi_mask = np.zeros((roi_slice[1] - roi_slice[0], roi_slice[3] - roi_slice[2]), dtype=bool)
    full_mask = _rect_mask_to_full(empty_roi_mask, roi_slice, img.shape)

    # No contours at this stage
    contours: list[np.ndarray] = []

    # Minimal debug payload to help w/ visual checks
    debug = {
        "roi_slice": np.array(roi_slice, dtype=np.int32),
        "roi_preview": roi_img.copy(),
    }

    return {
        "mask": full_mask,
        "contours": contours,
        "debug": debug,
        "spec": asdict(spec),
    }
