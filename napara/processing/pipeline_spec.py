from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Literal, Optional, Tuple, List

DenoiseMode = Literal["off", "nlm", "bm3d", "wavelet"]
ThreshMode  = Literal["sauvola", "otsu", "yen", "isodata", "canny"]


@dataclass
class HeavyPreprocSpec:
    order: List[str] = field(default_factory=list)
    # 1) Median + Leveling
    median_filter: bool = False
    median_size: int = 3
    level_enable: bool = False
    level_degree: int = 1  # 0/1/2

    # 2) Destriping
    destripe: bool = False
    destripe_ransac: bool = False
    ransac_axis: Literal['rows','cols'] = 'rows'
    ransac_poly_deg: int = 1
    ransac_residual: float = 3.0
    ransac_trials: int = 200

    # 2b) LOWESS
    destripe_lowess: bool = False
    lowess_axis: Literal['rows','cols'] = 'rows'
    lowess_frac: float = 0.10
    lowess_it: int = 1
    lowess_delta: float = 0.0

    # 2c) Hough-guided streak removal
    hough_streak_enable: bool = False
    hough_canny_sigma: float = 1.0
    hough_angle_center: float = 0.0
    hough_angle_tol: float = 5.0
    hough_threshold: int = 10
    hough_line_length: int = 30
    hough_line_gap: int = 5
    hough_mask_width: int = 3

    # 2d) Kierunkowe usuwanie linii + inpaint
    remove_hlines: bool = False
    hl_Lmin: int = 20
    hl_Lse: int = 61
    hl_Wse: int = 1
    hl_Wmax_keep: int = 3
    hl_angles: Tuple[float, ...] = (0.0,)

    # 3) Deconvolution
    deconv_mode: Literal['none','richardson_lucy','wiener'] = 'none'
    rl_iter: int = 15
    psf_sigma_x: float = 2.0
    psf_sigma_y: float = 0.5

    # 3.5) Wavelet
    wavelet_enable: bool = False
    wavelet_method: Literal['BayesShrink','VisuShrink'] = 'BayesShrink'
    wavelet_mode: Literal['soft','hard'] = 'soft'
    wavelet_name: str = 'db2'
    wavelet_level: int = 0  # 0 = auto
    wavelet_rescale_sigma: bool = True

    # 3.6) NLM
    nlm_enable: bool = False
    nlm_auto_sigma: bool = True
    nlm_h: float = 0.1
    nlm_h_factor: float = 1.0
    nlm_patch_size: int = 7
    nlm_patch_distance: int = 15
    nlm_fast: bool = True

    # 3.7) Perona–Malik
    pm_enable: bool = False
    pm_n_iter: int = 10
    pm_kappa: float = 20.0
    pm_gamma: float = 0.15
    pm_option: int = 1

    # 3.8) Directional TV
    dtv_enable: bool = False
    dtv_angle: float = 0.0
    dtv_lam_along: float = 0.2
    dtv_lam_across: float = 0.05
    dtv_n_iter: int = 50

    # 5) Morph. by reconstruction
    morphrec_bright_enable: bool = False
    morphrec_bright_len_px: int = 31
    morphrec_bright_w_px: int = 1
    morphrec_bright_angle: float = 0.0
    morphrec_dark_enable: bool = False
    morphrec_dark_len_px: int = 31
    morphrec_dark_w_px: int = 1
    morphrec_dark_angle: float = 0.0
    morphrec_protect_min_area_px: int = 0
    morphrec_protect_min_minor_px: int = 0

    # 6) BM3D
    denoise_bm3d: bool = True
    bm3d_sigma_factor: float = 1.0

    # --- walidacja + eksport ---
    def validate(self) -> "HeavyPreprocSpec":
        self.median_size = int(max(1, self.median_size) | 1)  # nieparzyste
        self.level_degree = 0 if self.level_degree <= 0 else 2 if self.level_degree >= 2 else 1
        self.ransac_poly_deg = max(0, min(3, int(self.ransac_poly_deg)))
        self.pm_gamma = float(min(max(self.pm_gamma, 0.01), 0.25))
        self.nlm_patch_size = int(max(1, self.nlm_patch_size) | 1)
        self.morphrec_bright_len_px = int(max(3, self.morphrec_bright_len_px) | 1)
        self.morphrec_dark_len_px   = int(max(3, self.morphrec_dark_len_px) | 1)
        self.hl_angles = tuple(float(a) for a in self.hl_angles)
        return self

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class PipelineSpec:
    # Blur
    gaussian_blur: bool = False
    gaussian_sigma: float = 1.0

    # Median
    median_filter: bool = False
    median_size: int = 3

    # White Top-Hat
    white_top_hat: bool = False
    wth_radius_px: int = 5

    # Thresholding + cleanup
    threshold_enable: bool = False   # Otsu na początek
    threshold_mode: str = "otsu"     # rezerwacja na przyszłość
    min_area_px: int = 20

    # Detekcja konturów/obiektów
    detect_enable: bool = False
