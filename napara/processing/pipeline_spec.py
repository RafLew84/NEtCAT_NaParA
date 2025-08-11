from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional

DenoiseMode = Literal["off", "nlm", "bm3d", "wavelet"]
ThreshMode  = Literal["sauvola", "otsu", "yen", "isodata", "canny"]

@dataclass
class PipelineSpec:
    """
    Deterministic ROI processing pipeline configuration.
    Steps order is fixed; toggles turn individual steps on/off.
    """
    # Add Gaussian Blur step
    gaussian_blur: bool = True
    gaussian_sigma: float = 1.0

    # 1) Destriping (line-by-line)
    destripe_median_rows: bool = True
    destripe_poly_rows: bool = False
    destripe_poly_deg: int = 1  # 1..3 typically

    # 2) Background leveling / morphology
    plane_leveling: bool = False               # simple plane fit subtraction
    white_tophat: bool = True
    wth_radius_nm: float = 6.0                 # structuring element radius in nm

    # 3) Denoising (pick one)
    denoise: DenoiseMode = "nlm"
    nlm_patch_size: int = 7                    # odd
    nlm_patch_distance: int = 15               # search window
    nlm_h_factor: float = 1.0                  # h ~ factor * sigma

    # (Optional) BM3D params (if available)
    bm3d_sigma_factor: float = 1.0             # sigma ~= factor * MAD

    # 4) Contrast normalization
    clahe: bool = True
    clahe_tile_px: int = 48
    clahe_clip_limit: float = 2.0

    # 5) Segmentation (choose path)
    thresh_mode: ThreshMode = "sauvola"
    sauvola_window_px: int = 31
    sauvola_k: float = 0.25

    canny_low_pct: float = 10.0                # percentiles for Canny thresholds
    canny_high_pct: float = 90.0
    canny_sigma: float = 1.0                   # Gaussian for Canny

    # 6) Morphological cleanup
    morph_open_px: int = 0                     # 0 -> skip
    morph_close_px: int = 1
    remove_small_area_nm2: float = 5.0
    remove_small_holes_px: int = 0

    # 7) Split touching objects (optional)
    watershed: bool = False
    min_peak_dist_px: int = 3

    # Size constraints (nm^2) — final filter
    min_area_nm2: Optional[float] = None
    max_area_nm2: Optional[float] = None
