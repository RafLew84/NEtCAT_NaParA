from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from napara.core.data_models import STMImage


@dataclass(frozen=True)
class ExportResult:
    h5_path: str
    png_path: str


def _ensure_h5_suffix(path: str | Path) -> Path:
    p = Path(path)
    if p.suffix.lower() != ".h5":
        p = p.with_suffix(".h5")
    return p


def _save_preview_png(png_path: Path, noisy: np.ndarray, clean: np.ndarray) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
    from matplotlib.figure import Figure

    fig = Figure(figsize=(10, 4), dpi=140)
    FigureCanvas(fig)
    ax_noisy = fig.add_subplot(1, 2, 1)
    ax_clean = fig.add_subplot(1, 2, 2)

    for ax, arr, title in [(ax_noisy, noisy, "Noisy"), (ax_clean, clean, "Clean")]:
        vmin, vmax = np.percentile(arr, (1, 99))
        if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
            vmin, vmax = float(np.min(arr)), float(np.max(arr))
        ax.imshow(arr, cmap="gray", origin="lower", vmin=vmin, vmax=vmax)
        ax.set_title(title)
        ax.axis("off")

    fig.tight_layout()
    fig.savefig(png_path, dpi=140, bbox_inches="tight")


def export_pair_to_h5_and_png(
    output_h5_path: str | Path,
    noisy_image: STMImage,
    clean_image: STMImage,
    *,
    alignment_check_active: bool,
) -> ExportResult:
    """
    Save one pair as:
    - HDF5: /noisy/image and /clean/image (float32) + metadata attrs
    - PNG: side-by-side quick preview
    """
    h5_path = _ensure_h5_suffix(output_h5_path)
    png_path = h5_path.with_suffix(".png")

    noisy = np.asarray(noisy_image.data, dtype=np.float32)
    clean = np.asarray(clean_image.data, dtype=np.float32)

    if noisy.ndim != 2 or clean.ndim != 2:
        raise ValueError("Expected 2D data arrays for both noisy and clean images.")
    if noisy.shape != clean.shape:
        raise ValueError(
            f"Shape mismatch between noisy and clean image: {noisy.shape} vs {clean.shape}."
        )

    try:
        import h5py  # type: ignore
    except Exception as e:
        raise RuntimeError(f"h5py is required for pair export: {e}") from e

    with h5py.File(h5_path, "w") as f:
        g_noisy = f.create_group("noisy")
        g_clean = f.create_group("clean")
        g_noisy.create_dataset("image", data=noisy, dtype="float32")
        g_clean.create_dataset("image", data=clean, dtype="float32")

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        f.attrs["created_at_utc"] = now
        f.attrs["alignment_check_active"] = bool(alignment_check_active)
        f.attrs["noisy_src_path"] = str(noisy_image.file_name)
        f.attrs["clean_src_path"] = str(clean_image.file_name)
        f.attrs["shape_h"] = int(noisy.shape[0])
        f.attrs["shape_w"] = int(noisy.shape[1])

        n_px_x, n_px_y = noisy_image.get_pixel_size_nm()
        c_px_x, c_px_y = clean_image.get_pixel_size_nm()
        f.attrs["noisy_px_size_nm_x"] = float(n_px_x) if n_px_x is not None else np.nan
        f.attrs["noisy_px_size_nm_y"] = float(n_px_y) if n_px_y is not None else np.nan
        f.attrs["clean_px_size_nm_x"] = float(c_px_x) if c_px_x is not None else np.nan
        f.attrs["clean_px_size_nm_y"] = float(c_px_y) if c_px_y is not None else np.nan
        f.attrs["noisy_channel"] = str(noisy_image.image_type)
        f.attrs["clean_channel"] = str(clean_image.image_type)

    _save_preview_png(png_path, noisy=noisy, clean=clean)
    return ExportResult(h5_path=str(h5_path), png_path=str(png_path))
