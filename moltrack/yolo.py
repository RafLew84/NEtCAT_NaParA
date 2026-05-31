"""YOLO model discovery and configuration for MolTrack."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nanotrack.yolo import YoloRuntimeConfig, default_yolo_models_dir, discover_yolo_models


MOLECULE_CLASS_NAMES = ("molecule",)


@dataclass(frozen=True)
class MolTrackYoloModelInfo:
    """Metadata for one local YOLO molecule detector."""

    name: str
    path: Path
    class_names: tuple[str, ...] = MOLECULE_CLASS_NAMES

    def __post_init__(self) -> None:
        name = str(self.name).strip()
        if not name:
            raise ValueError("name must be a non-empty string.")
        class_names = tuple(str(class_name).strip() for class_name in self.class_names)
        if class_names != MOLECULE_CLASS_NAMES:
            raise ValueError("MolTrack YOLO currently supports exactly one class: molecule.")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "path", Path(self.path).expanduser().resolve())
        object.__setattr__(self, "class_names", class_names)

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def class_count(self) -> int:
        return len(self.class_names)


@dataclass(frozen=True)
class MolTrackYoloDetectionConfig:
    """User-configurable YOLO detection settings for MolTrack."""

    confidence_threshold: float = 0.25
    iou_threshold: float = 0.45
    device: str = "auto"
    class_names: tuple[str, ...] = MOLECULE_CLASS_NAMES

    def __post_init__(self) -> None:
        confidence_threshold = float(self.confidence_threshold)
        iou_threshold = float(self.iou_threshold)
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be in [0, 1].")
        if not 0.0 <= iou_threshold <= 1.0:
            raise ValueError("iou_threshold must be in [0, 1].")
        device = str(self.device).strip()
        if not device:
            raise ValueError("device must be a non-empty string.")
        class_names = tuple(str(class_name).strip() for class_name in self.class_names)
        if class_names != MOLECULE_CLASS_NAMES:
            raise ValueError("MolTrack YOLO currently supports exactly one class: molecule.")
        object.__setattr__(self, "confidence_threshold", confidence_threshold)
        object.__setattr__(self, "iou_threshold", iou_threshold)
        object.__setattr__(self, "device", device)
        object.__setattr__(self, "class_names", class_names)

    def to_nanotrack_runtime_config(self) -> YoloRuntimeConfig:
        return YoloRuntimeConfig(
            device=self.device,
            default_conf_threshold=self.confidence_threshold,
            default_iou_threshold=self.iou_threshold,
        )


def default_moltrack_yolo_models_dir() -> Path:
    """Return the shared NanoTrack YOLO models directory."""

    return default_yolo_models_dir()


def discover_moltrack_yolo_models(models_dir: str | Path | None = None) -> list[MolTrackYoloModelInfo]:
    """Return local NanoTrack YOLO checkpoints as MolTrack molecule detectors."""

    return [
        MolTrackYoloModelInfo(name=model.name, path=model.path)
        for model in discover_yolo_models(models_dir)
    ]


__all__ = [
    "MOLECULE_CLASS_NAMES",
    "MolTrackYoloDetectionConfig",
    "MolTrackYoloModelInfo",
    "default_moltrack_yolo_models_dir",
    "discover_moltrack_yolo_models",
]
