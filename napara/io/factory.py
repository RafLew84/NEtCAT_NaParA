# napara/io/factory.py
"""
Factory to load STM images from supported formats. Always returns a list[STMImage].
"""

import os
import logging
from typing import Callable, Dict, List, Optional
from napara.core.data_models import STMImage
from .stp_reader import read_stp_file
from .s94_reader import read_s94_file
from .mpp_reader import read_mpp_file

logger = logging.getLogger(__name__)

ReaderFn = Callable[[str], Optional[List[STMImage]]]

SUPPORTED_FORMATS: Dict[str, ReaderFn] = {
    ".stp": read_stp_file,
    ".s94": read_s94_file,
    ".mpp": read_mpp_file,
}

def load_stm_path(path: str) -> List[STMImage]:
    """
    Load a single path. For STP/S94 returns [STMImage], for MPP returns multiple frames.
    """
    ext = os.path.splitext(path)[1].lower()
    reader = SUPPORTED_FORMATS.get(ext)
    if not reader:
        raise ValueError(f"Unsupported extension: {ext}")
    imgs = reader(path)
    return imgs or []

def load_from_paths(paths: List[str]) -> List[STMImage]:
    """
    Load many paths. For .mpp, expand into frames. For .stp/.s94, add single frames.
    """
    out: List[STMImage] = []
    for p in paths:
        try:
            out.extend(load_stm_path(p))
        except Exception as e:
            logger.exception(f"Failed to load '{p}': {e}")
    return out
