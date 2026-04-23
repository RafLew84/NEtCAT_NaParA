"""Helpers for discovering local YOLO checkpoints."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


_SUPPORTED_MODEL_SUFFIXES = (".pt", ".pth", ".onnx", ".engine")


@dataclass(frozen=True)
class YoloModelInfo:
    """Metadata for one locally available YOLO model checkpoint."""

    name: str
    path: Path

    @property
    def display_name(self) -> str:
        return self.name


def default_yolo_models_dir() -> Path:
    """Return the default local directory with YOLO model checkpoints."""

    return Path(__file__).resolve().parents[1] / "yolo_models"


def discover_yolo_models(models_dir: str | Path | None = None) -> list[YoloModelInfo]:
    """Return a sorted list of locally available YOLO model checkpoints."""

    search_dir = default_yolo_models_dir() if models_dir is None else Path(models_dir)
    if not search_dir.exists() or not search_dir.is_dir():
        return []

    models: list[YoloModelInfo] = []
    for path in sorted(search_dir.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _SUPPORTED_MODEL_SUFFIXES:
            continue
        models.append(
            YoloModelInfo(
                name=path.name,
                path=path.resolve(),
            )
        )
    return models
