"""Runtime wrapper around local Ultralytics YOLO models."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
from typing import Any

import numpy as np

from nanotrack.core import BBoxXYXY


class YoloRuntimeError(RuntimeError):
    """Base error raised by the NanoTrack YOLO runtime."""


class YoloRuntimeUnavailableError(YoloRuntimeError):
    """Raised when `ultralytics` is not available in the current environment."""


class YoloRuntimeModelLoadError(YoloRuntimeError):
    """Raised when a YOLO checkpoint cannot be loaded."""


@dataclass(frozen=True)
class YoloRuntimeConfig:
    """Runtime configuration for local YOLO inference inside the app env."""

    device: str = "auto"
    default_conf_threshold: float = 0.25
    default_iou_threshold: float = 0.45
    default_imgsz: int | None = None
    verbose: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.default_conf_threshold <= 1.0:
            raise ValueError("default_conf_threshold must be in [0, 1].")
        if not 0.0 <= self.default_iou_threshold <= 1.0:
            raise ValueError("default_iou_threshold must be in [0, 1].")
        if self.default_imgsz is not None and self.default_imgsz <= 0:
            raise ValueError("default_imgsz must be positive when provided.")


@dataclass(frozen=True)
class YoloRuntimeDetection:
    """One raw detection returned by the YOLO runtime."""

    bbox: BBoxXYXY
    confidence: float
    model_name: str


class YoloRuntime:
    """Thin inference wrapper around `ultralytics.YOLO` with model caching."""

    def __init__(self, config: YoloRuntimeConfig | None = None):
        self.config = config or YoloRuntimeConfig()
        self._loaded_model_path: Path | None = None
        self._loaded_model: Any | None = None

    def loaded_model_path(self) -> Path | None:
        return self._loaded_model_path

    def load_model(self, model_path: str | Path):
        resolved_path = Path(model_path).expanduser().resolve()
        if not resolved_path.exists() or not resolved_path.is_file():
            raise YoloRuntimeModelLoadError(f"YOLO checkpoint does not exist: {resolved_path}")
        if self._loaded_model is not None and self._loaded_model_path == resolved_path:
            return self._loaded_model

        try:
            ultralytics = importlib.import_module("ultralytics")
        except ImportError as exc:
            raise YoloRuntimeUnavailableError(
                "Ultralytics is not available in the current environment."
            ) from exc

        try:
            model = ultralytics.YOLO(str(resolved_path))
        except Exception as exc:  # pragma: no cover - depends on external package/runtime
            raise YoloRuntimeModelLoadError(
                f"Cannot load YOLO checkpoint: {resolved_path}\n{exc}"
            ) from exc

        self._loaded_model_path = resolved_path
        self._loaded_model = model
        return model

    def predict_frame(
        self,
        frame: np.ndarray,
        *,
        model_path: str | Path,
        conf_threshold: float | None = None,
        iou_threshold: float | None = None,
        imgsz: int | None = None,
        device: str | None = None,
    ) -> list[YoloRuntimeDetection]:
        model = self.load_model(model_path)
        prepared_frame = self._prepare_frame(frame)
        predict_kwargs = self._build_predict_kwargs(
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            imgsz=imgsz,
            device=device,
        )

        try:
            results = model.predict(source=prepared_frame, **predict_kwargs)
        except Exception as exc:  # pragma: no cover - depends on external package/runtime
            raise YoloRuntimeError(f"YOLO inference failed for frame.\n{exc}") from exc

        return self._parse_results(results, model_name=Path(model_path).name)

    def predict_frames(
        self,
        frames: np.ndarray,
        *,
        model_path: str | Path,
        conf_threshold: float | None = None,
        iou_threshold: float | None = None,
        imgsz: int | None = None,
        device: str | None = None,
    ) -> list[list[YoloRuntimeDetection]]:
        frames_array = np.asarray(frames)
        if frames_array.ndim < 3:
            raise ValueError("frames must have shape [T, H, W] or [T, H, W, C].")

        detections_by_frame: list[list[YoloRuntimeDetection]] = []
        for frame in frames_array:
            detections_by_frame.append(
                self.predict_frame(
                    frame,
                    model_path=model_path,
                    conf_threshold=conf_threshold,
                    iou_threshold=iou_threshold,
                    imgsz=imgsz,
                    device=device,
                )
            )
        return detections_by_frame

    def _build_predict_kwargs(
        self,
        *,
        conf_threshold: float | None,
        iou_threshold: float | None,
        imgsz: int | None,
        device: str | None,
    ) -> dict[str, Any]:
        effective_conf = self.config.default_conf_threshold if conf_threshold is None else float(conf_threshold)
        effective_iou = self.config.default_iou_threshold if iou_threshold is None else float(iou_threshold)
        effective_imgsz = self.config.default_imgsz if imgsz is None else int(imgsz)
        effective_device = self.config.device if device is None else str(device)
        if not 0.0 <= effective_conf <= 1.0:
            raise ValueError("conf_threshold must be in [0, 1].")
        if not 0.0 <= effective_iou <= 1.0:
            raise ValueError("iou_threshold must be in [0, 1].")

        kwargs: dict[str, Any] = {
            "conf": effective_conf,
            "iou": effective_iou,
            "device": effective_device,
            "verbose": bool(self.config.verbose),
        }
        if effective_imgsz is not None:
            kwargs["imgsz"] = effective_imgsz
        return kwargs

    def _prepare_frame(self, frame: np.ndarray) -> np.ndarray:
        frame_array = np.asarray(frame)
        if frame_array.ndim == 2:
            frame_uint8 = self._normalize_to_uint8(frame_array)
            return np.repeat(frame_uint8[..., None], 3, axis=2)
        if frame_array.ndim == 3 and frame_array.shape[2] == 1:
            frame_uint8 = self._normalize_to_uint8(frame_array[..., 0])
            return np.repeat(frame_uint8[..., None], 3, axis=2)
        if frame_array.ndim == 3 and frame_array.shape[2] == 3:
            return self._normalize_to_uint8(frame_array)
        raise ValueError("frame must have shape [H, W], [H, W, 1], or [H, W, 3].")

    def _normalize_to_uint8(self, frame: np.ndarray) -> np.ndarray:
        frame_array = np.asarray(frame)
        if frame_array.dtype == np.uint8:
            return np.asarray(frame_array, dtype=np.uint8)

        frame_f32 = np.asarray(frame_array, dtype=np.float32)
        finite_mask = np.isfinite(frame_f32)
        if not np.any(finite_mask):
            return np.zeros(frame_f32.shape, dtype=np.uint8)

        valid_values = frame_f32[finite_mask]
        min_value = float(np.min(valid_values))
        max_value = float(np.max(valid_values))
        if max_value <= min_value:
            normalized = np.zeros(frame_f32.shape, dtype=np.float32)
        else:
            normalized = (frame_f32 - min_value) / (max_value - min_value)
        normalized = np.clip(normalized, 0.0, 1.0)
        normalized[~finite_mask] = 0.0
        return np.asarray(np.round(normalized * 255.0), dtype=np.uint8)

    def _parse_results(
        self,
        results: Any,
        *,
        model_name: str,
    ) -> list[YoloRuntimeDetection]:
        if results is None:
            return []
        if not isinstance(results, (list, tuple)):
            results = [results]
        if not results:
            return []

        first_result = results[0]
        boxes = getattr(first_result, "boxes", None)
        if boxes is None:
            return []

        xyxy = self._to_numpy(getattr(boxes, "xyxy", None))
        confidence = self._to_numpy(getattr(boxes, "conf", None))
        if xyxy is None or confidence is None:
            return []

        detections: list[YoloRuntimeDetection] = []
        for bbox_values, score_value in zip(xyxy, confidence):
            bbox_array = np.asarray(bbox_values, dtype=np.float32).reshape(-1)
            if bbox_array.shape != (4,):
                continue
            try:
                bbox = BBoxXYXY(
                    float(bbox_array[0]),
                    float(bbox_array[1]),
                    float(bbox_array[2]),
                    float(bbox_array[3]),
                )
            except ValueError:
                continue
            detections.append(
                YoloRuntimeDetection(
                    bbox=bbox,
                    confidence=float(score_value),
                    model_name=model_name,
                )
            )
        return detections

    def _to_numpy(self, value: Any) -> np.ndarray | None:
        if value is None:
            return None
        if hasattr(value, "detach"):
            value = value.detach()
        if hasattr(value, "cpu"):
            value = value.cpu()
        if hasattr(value, "numpy"):
            value = value.numpy()
        return np.asarray(value)
