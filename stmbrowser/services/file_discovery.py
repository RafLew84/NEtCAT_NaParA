from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

SUPPORTED_EXTENSIONS = {".stp", ".s94"}


def _is_supported(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def collect_supported_from_files(file_paths: Iterable[str]) -> list[str]:
    """Return absolute paths for supported files from explicit file selection."""
    out: list[str] = []
    for raw in file_paths:
        p = os.path.abspath(raw)
        if os.path.isfile(p) and _is_supported(p):
            out.append(p)
    return out


def collect_supported_from_directory(directory: str, *, recursive: bool = True) -> list[str]:
    """Scan directory for .stp/.s94 files and return sorted absolute paths."""
    root = os.path.abspath(directory)
    if not os.path.isdir(root):
        return []

    out: list[str] = []
    if recursive:
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                p = os.path.join(dirpath, name)
                if _is_supported(p):
                    out.append(os.path.abspath(p))
    else:
        for name in os.listdir(root):
            p = os.path.join(root, name)
            if os.path.isfile(p) and _is_supported(p):
                out.append(os.path.abspath(p))

    out.sort(key=lambda x: x.lower())
    return out
