from __future__ import annotations

import os
from pathlib import Path

from napara.core.data_models import STMImage
from napara.io.factory import load_stm_path


def load_supported_stm_image(path: str) -> STMImage:
    """Load one .stp/.s94 file and return the first STMImage frame."""
    abs_path = os.path.abspath(path)
    ext = Path(abs_path).suffix.lower()
    if ext not in {".stp", ".s94"}:
        raise ValueError(f"Unsupported extension for STM Browser: {ext}")

    images = load_stm_path(abs_path)
    if not images:
        raise ValueError(f"No image payload found in file: {abs_path}")
    return images[0]
