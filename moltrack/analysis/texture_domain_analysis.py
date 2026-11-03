from __future__ import annotations

import base64
import hashlib
import json
import zlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.spatial import cKDTree



TEXTURE_DOMAIN_ANALYSIS_SCHEMA_VERSION = 1
TEXTURE_DOMAIN_ANALYSIS_ALGORITHM_VERSION = "local-gradient-histogram-v1"
TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY = "unknown"
_MASK_CENTROID_X_METADATA_KEY = "_moltrack_loaded_mask_centroid_x_px"
_MASK_CENTROID_Y_METADATA_KEY = "_moltrack_loaded_mask_centroid_y_px"

_TTMAPP_PROTOTYPES_ZLIB_BASE64 = (
    "eNoNzo07FAYcB/A7zrmhshFlYdzioeWJlJffl9lseZuXZvI2du5aXsJDD888pKeW"
    "7NYhE8aSt7zk6J5hKU7ZIyrDmow8NHtSacgdJ5c7su3zF3ym1SXk6XaRLokL6XZ"
    "2AcXP5VGfSkTiRBHx3pyn6eHzdNJeRMmueRRTn08y+wskeVJItptFlCIvodyqcmp"
    "PvkzbzWro4HodRTg1UVf9NRLpttFoSQcFjEmp9kAvdbQNUMOHD2l+fIqOLz6n1n"
    "/llPSjmpbTNCHV1IXDHkMIBswQfdcWC87OWEjxQibCUfwsGbyBHExlFaN3tg7Ff"
    "7ZhVkeKHu4tbEqlkL/diZ6y6yhvb0VtsAQ/yJsxkiyG+1ATjJaacD9BjOL7Ysyox"
    "DDc2wxb42bETzbBUNWAcyO1uKa8DI+8MtQJitDuL8I9z7NYZaSDM8eHwugwnHd7"
    "wKZ7H46BC2NHY3xgqYduaOCteytkr3xOPJNJcgp6QJ3cftrokVLypXa6c7OF/Fo"
    "baMi3hiIaK8hFWUZW2SsIce+HXX4+tEv8MB1rCQlHH10P2eiMZyDVUUl70mW0vW"
    "WeOjjz9HR8nrq9XlJI0SKZv1gkUaKM/CRLFBG8QiNvVuigUkF1txUkSV0l6zk1O"
    "f/GgA2HhQAeG1n7tfH9IzYEBmzwmVr42k0Ta18wkS5mYDOHiWC1Bv4IZKFTwkJh"
    "qCbOhjNheIEJcQEb3SH6qLz6Lu6Yvo9+pRUid+1GmbslhGEWEG7hoj3YCltlNjg"
    "1tRe9rg5ImT6A/cNOGP/bGa/vumJwxg3fPPWAsvVjRM97Qm51CKsnfPHdSBBmos"
    "Iw8DgaW7z5uBEnwAD3KN4THYXnIwHsDPiYnPwKvwxF4cvHkSjlhcPw0yNwXvoc"
    "LpmB4Lp8Bsd2H/DnvPBPnBcWY/wwOBsB+U+nUfJrHUr5Y8gIVSEkUR95RXo4Ec1"
    "GfSgTjdUbBG8V1RxboxxLFR1OWqOljFfk+kxObh4yUpTKKddnmSZMlmnwiJyCWm"
    "RUEbRMjc1KOkcbxE9gQE+hAeuf2ZhT6yLmk3dQ3b0Da0XmOH3DGldi7JHzFyHV7"
    "hAy/n9ODYeiictDaUI8LIRpGDU9A9aYEK5VhYg8WQbxYDUm85swcbwNZ9SdSEq7"
    "hYW+LvQWtMG7qhGZMxUY7LuIDEEeQm/mYuDUtxDGZsMsKA0RevG4Eh4F313BqPT"
    "3hcHaR6gPdMEGax9ezljBfJs5HlTsQA3HAKOeW2FUrwN+HAcBO7WhHNYCcycLSR"
    "Ya8LFm4PfKDSq3U9G6qZJGn6yQa7OC/N0VNB6moOsyBQ37vyKhyWvKil2nF0YMt"
    "Ig0MDGjBYerOijx3ob/AAjH2fo="
)


def _canonical_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _finite_float(value: Any, name: str) -> float:
    normalized = float(value)
    if not np.isfinite(normalized):
        raise ValueError(f"{name} must be finite.")
    return normalized


@dataclass(frozen=True)
class TextureDomainClassDefinition:
    key: str
    short_label: str
    display_name: str
    reference_name: str
    color_rgb: tuple[int, int, int]

    def __post_init__(self) -> None:
        key = str(self.key).strip()
        short_label = str(self.short_label).strip()
        display_name = str(self.display_name).strip()
        reference_name = str(self.reference_name).strip()
        if not key or key == TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY:
            raise ValueError("Texture-domain class key is invalid.")
        if not short_label or not display_name or not reference_name:
            raise ValueError("Texture-domain class labels must not be empty.")
        color = tuple(int(value) for value in self.color_rgb)
        if len(color) != 3 or any(value < 0 or value > 255 for value in color):
            raise ValueError("color_rgb must contain three channels from 0 to 255.")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "short_label", short_label)
        object.__setattr__(self, "display_name", display_name)
        object.__setattr__(self, "reference_name", reference_name)
        object.__setattr__(self, "color_rgb", color)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "short_label": self.short_label,
            "display_name": self.display_name,
            "reference_name": self.reference_name,
            "color_rgb": list(self.color_rgb),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TextureDomainClassDefinition":
        return cls(
            key=payload["key"],
            short_label=payload["short_label"],
            display_name=payload["display_name"],
            reference_name=payload["reference_name"],
            color_rgb=tuple(payload["color_rgb"]),
        )


@dataclass(frozen=True)
class TextureDomainAnalysisSettings:
    preset_id: str
    classes: tuple[TextureDomainClassDefinition, ...]
    prototype_histograms: tuple[tuple[float, ...], ...]
    distance_thresholds: tuple[float, ...]
    minimum_margin: float
    render_scale: int
    local_radius_rendered_px: int
    high_pass_sigma_rendered_px: float
    histogram_sigma_bins: float
    neighbor_min_distance_source_px: float
    neighbor_max_distance_source_px: float
    neighbor_weight: float
    smoothing_rounds: int
    minimum_component_size: int
    experimental: bool = True
    calibration_note: str = ""

    def __post_init__(self) -> None:
        preset_id = str(self.preset_id).strip()
        classes = tuple(self.classes)
        prototypes = tuple(
            tuple(_finite_float(item, "prototype value") for item in row)
            for row in self.prototype_histograms
        )
        thresholds = tuple(
            _finite_float(value, "distance threshold")
            for value in self.distance_thresholds
        )
        if not preset_id:
            raise ValueError("preset_id must not be empty.")
        if not classes or not all(
            isinstance(value, TextureDomainClassDefinition)
            for value in classes
        ):
            raise TypeError("classes must contain class definitions.")
        if len({value.key for value in classes}) != len(classes):
            raise ValueError("Texture-domain class keys must be unique.")
        if len(prototypes) != len(classes) or len(thresholds) != len(classes):
            raise ValueError("Classes, prototypes and thresholds must have equal length.")
        histogram_lengths = {len(row) for row in prototypes}
        if len(histogram_lengths) != 1 or next(iter(histogram_lengths)) < 2:
            raise ValueError("Prototype histograms must have one common length.")
        for row in prototypes:
            if any(value < 0.0 for value in row) or sum(row) <= 0.0:
                raise ValueError("Prototype histogram must be non-negative and non-empty.")
        if any(value < 0.0 for value in thresholds):
            raise ValueError("distance_thresholds must be non-negative.")
        minimum_margin = _finite_float(self.minimum_margin, "minimum_margin")
        render_scale = int(self.render_scale)
        radius = int(self.local_radius_rendered_px)
        high_pass_sigma = _finite_float(
            self.high_pass_sigma_rendered_px,
            "high_pass_sigma_rendered_px",
        )
        histogram_sigma = _finite_float(
            self.histogram_sigma_bins,
            "histogram_sigma_bins",
        )
        minimum_distance = _finite_float(
            self.neighbor_min_distance_source_px,
            "neighbor_min_distance_source_px",
        )
        maximum_distance = _finite_float(
            self.neighbor_max_distance_source_px,
            "neighbor_max_distance_source_px",
        )
        neighbor_weight = _finite_float(self.neighbor_weight, "neighbor_weight")
        rounds = int(self.smoothing_rounds)
        minimum_size = int(self.minimum_component_size)
        if (
            minimum_margin < 0.0
            or render_scale <= 0
            or radius <= 0
            or high_pass_sigma <= 0.0
            or histogram_sigma < 0.0
            or minimum_distance < 0.0
            or maximum_distance <= minimum_distance
            or neighbor_weight < 0.0
            or rounds <= 0
            or minimum_size <= 0
        ):
            raise ValueError("Texture-domain numerical settings are invalid.")
        object.__setattr__(self, "preset_id", preset_id)
        object.__setattr__(self, "classes", classes)
        object.__setattr__(self, "prototype_histograms", prototypes)
        object.__setattr__(self, "distance_thresholds", thresholds)
        object.__setattr__(self, "minimum_margin", minimum_margin)
        object.__setattr__(self, "render_scale", render_scale)
        object.__setattr__(self, "local_radius_rendered_px", radius)
        object.__setattr__(self, "high_pass_sigma_rendered_px", high_pass_sigma)
        object.__setattr__(self, "histogram_sigma_bins", histogram_sigma)
        object.__setattr__(self, "neighbor_min_distance_source_px", minimum_distance)
        object.__setattr__(self, "neighbor_max_distance_source_px", maximum_distance)
        object.__setattr__(self, "neighbor_weight", neighbor_weight)
        object.__setattr__(self, "smoothing_rounds", rounds)
        object.__setattr__(self, "minimum_component_size", minimum_size)
        object.__setattr__(self, "experimental", bool(self.experimental))
        object.__setattr__(self, "calibration_note", str(self.calibration_note).strip())

    @property
    def histogram_bin_count(self) -> int:
        return len(self.prototype_histograms[0])

    @property
    def fingerprint(self) -> str:
        return _canonical_fingerprint(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "preset_id": self.preset_id,
            "classes": [value.to_dict() for value in self.classes],
            "prototype_histograms": [
                list(value) for value in self.prototype_histograms
            ],
            "distance_thresholds": list(self.distance_thresholds),
            "minimum_margin": self.minimum_margin,
            "render_scale": self.render_scale,
            "local_radius_rendered_px": self.local_radius_rendered_px,
            "high_pass_sigma_rendered_px": self.high_pass_sigma_rendered_px,
            "histogram_sigma_bins": self.histogram_sigma_bins,
            "neighbor_min_distance_source_px": (
                self.neighbor_min_distance_source_px
            ),
            "neighbor_max_distance_source_px": (
                self.neighbor_max_distance_source_px
            ),
            "neighbor_weight": self.neighbor_weight,
            "smoothing_rounds": self.smoothing_rounds,
            "minimum_component_size": self.minimum_component_size,
            "experimental": self.experimental,
            "calibration_note": self.calibration_note,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TextureDomainAnalysisSettings":
        return cls(
            preset_id=payload["preset_id"],
            classes=tuple(
                TextureDomainClassDefinition.from_dict(value)
                for value in payload["classes"]
            ),
            prototype_histograms=tuple(
                tuple(value) for value in payload["prototype_histograms"]
            ),
            distance_thresholds=tuple(payload["distance_thresholds"]),
            minimum_margin=payload["minimum_margin"],
            render_scale=payload["render_scale"],
            local_radius_rendered_px=payload["local_radius_rendered_px"],
            high_pass_sigma_rendered_px=payload[
                "high_pass_sigma_rendered_px"
            ],
            histogram_sigma_bins=payload["histogram_sigma_bins"],
            neighbor_min_distance_source_px=payload[
                "neighbor_min_distance_source_px"
            ],
            neighbor_max_distance_source_px=payload[
                "neighbor_max_distance_source_px"
            ],
            neighbor_weight=payload["neighbor_weight"],
            smoothing_rounds=payload["smoothing_rounds"],
            minimum_component_size=payload["minimum_component_size"],
            experimental=payload.get("experimental", True),
            calibration_note=payload.get("calibration_note", ""),
        )


@dataclass(frozen=True)
class TextureDomainPointInput:
    source_id: str
    x_px: float
    y_px: float

    def __post_init__(self) -> None:
        source_id = str(self.source_id).strip()
        x_px = _finite_float(self.x_px, "x_px")
        y_px = _finite_float(self.y_px, "y_px")
        if not source_id:
            raise ValueError("source_id must not be empty.")
        if x_px < 0.0 or y_px < 0.0:
            raise ValueError("Texture-domain point coordinates must be non-negative.")
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "x_px", x_px)
        object.__setattr__(self, "y_px", y_px)


@dataclass(frozen=True)
class TextureDomainPointResult:
    source_id: str
    x_px: float
    y_px: float
    class_key: str
    nearest_class_key: str
    threshold_candidate_class_key: str
    threshold_candidate_distance: float | None
    threshold_reason: str
    component_id: str
    nearest_distance: float | None
    margin: float | None

    def __post_init__(self) -> None:
        source_id = str(self.source_id).strip()
        class_key = str(self.class_key).strip()
        nearest_class_key = str(self.nearest_class_key).strip()
        threshold_candidate_class_key = str(self.threshold_candidate_class_key).strip()
        threshold_reason = str(self.threshold_reason).strip()
        component_id = str(self.component_id).strip()
        if not source_id or not class_key or not nearest_class_key or not threshold_candidate_class_key or not threshold_reason:
            raise ValueError("Texture-domain point labels must not be empty.")
        x_px = _finite_float(self.x_px, "x_px")
        y_px = _finite_float(self.y_px, "y_px")
        if x_px < 0.0 or y_px < 0.0:
            raise ValueError("Texture-domain point coordinates must be non-negative.")
        nearest_distance = None if self.nearest_distance is None else _finite_float(self.nearest_distance, "nearest_distance")
        candidate_distance = None if self.threshold_candidate_distance is None else _finite_float(self.threshold_candidate_distance, "threshold_candidate_distance")
        margin = None if self.margin is None else _finite_float(self.margin, "margin")
        if any(value is not None and value < 0.0 for value in (nearest_distance, candidate_distance)):
            raise ValueError("Texture-domain distances must be non-negative.")
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "x_px", x_px)
        object.__setattr__(self, "y_px", y_px)
        object.__setattr__(self, "class_key", class_key)
        object.__setattr__(self, "nearest_class_key", nearest_class_key)
        object.__setattr__(self, "threshold_candidate_class_key", threshold_candidate_class_key)
        object.__setattr__(self, "threshold_candidate_distance", candidate_distance)
        object.__setattr__(self, "threshold_reason", threshold_reason)
        object.__setattr__(self, "component_id", component_id)
        object.__setattr__(self, "nearest_distance", nearest_distance)
        object.__setattr__(self, "margin", margin)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "x_px": self.x_px,
            "y_px": self.y_px,
            "class_key": self.class_key,
            "nearest_class_key": self.nearest_class_key,
            "threshold_candidate_class_key": self.threshold_candidate_class_key,
            "threshold_candidate_distance": self.threshold_candidate_distance,
            "threshold_reason": self.threshold_reason,
            "component_id": self.component_id,
            "nearest_distance": self.nearest_distance,
            "margin": self.margin,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TextureDomainPointResult":
        return cls(
            source_id=str(payload["source_id"]),
            x_px=float(payload["x_px"]),
            y_px=float(payload["y_px"]),
            class_key=str(payload["class_key"]),
            nearest_class_key=str(payload["nearest_class_key"]),
            threshold_candidate_class_key=str(payload.get("threshold_candidate_class_key", payload["nearest_class_key"])),
            threshold_candidate_distance=(
                None
                if payload.get("threshold_candidate_distance", payload.get("nearest_distance")) is None
                else float(payload.get("threshold_candidate_distance", payload["nearest_distance"]))
            ),
            threshold_reason=str(payload.get("threshold_reason", "legacy_rejection_reason_unavailable")),
            component_id=str(payload.get("component_id", "")),
            nearest_distance=None if payload.get("nearest_distance") is None else float(payload["nearest_distance"]),
            margin=None if payload.get("margin") is None else float(payload["margin"]),
        )


@dataclass(frozen=True)
class TextureDomainComponent:
    component_id: str
    class_key: str
    source_ids: tuple[str, ...]
    centroid_x_px: float
    centroid_y_px: float

    def __post_init__(self) -> None:
        component_id = str(self.component_id).strip()
        class_key = str(self.class_key).strip()
        source_ids = tuple(str(value).strip() for value in self.source_ids)
        if not component_id or not class_key or not source_ids:
            raise ValueError("Texture-domain component must not be empty.")
        if any(not value for value in source_ids) or len(set(source_ids)) != len(
            source_ids
        ):
            raise ValueError("Texture-domain component source IDs are invalid.")
        object.__setattr__(self, "component_id", component_id)
        object.__setattr__(self, "class_key", class_key)
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(
            self,
            "centroid_x_px",
            _finite_float(self.centroid_x_px, "centroid_x_px"),
        )
        object.__setattr__(
            self,
            "centroid_y_px",
            _finite_float(self.centroid_y_px, "centroid_y_px"),
        )

    @property
    def molecule_count(self) -> int:
        return len(self.source_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "class_key": self.class_key,
            "source_ids": list(self.source_ids),
            "centroid_x_px": self.centroid_x_px,
            "centroid_y_px": self.centroid_y_px,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TextureDomainComponent":
        return cls(
            component_id=str(payload["component_id"]),
            class_key=str(payload["class_key"]),
            source_ids=tuple(str(value) for value in payload["source_ids"]),
            centroid_x_px=float(payload["centroid_x_px"]),
            centroid_y_px=float(payload["centroid_y_px"]),
        )


@dataclass(frozen=True)
class TextureDomainFrameResult:
    frame_index: int
    source_view: str
    points: tuple[TextureDomainPointResult, ...]
    components: tuple[TextureDomainComponent, ...]
    settings_fingerprint: str
    input_fingerprint: str
    frame_fingerprint: str = ""

    def __post_init__(self) -> None:
        frame_index = int(self.frame_index)
        if frame_index < 0:
            raise ValueError("frame_index must be non-negative.")
        source_view = str(self.source_view).strip()
        if source_view not in ("raw", "expanded_aligned"):
            raise ValueError("Unsupported texture-domain source_view.")
        points = tuple(self.points)
        components = tuple(self.components)
        if not all(isinstance(value, TextureDomainPointResult) for value in points):
            raise TypeError("Texture-domain points have an invalid type.")
        if not all(
            isinstance(value, TextureDomainComponent) for value in components
        ):
            raise TypeError("Texture-domain components have an invalid type.")
        source_ids = tuple(value.source_id for value in self.points)
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("Texture-domain point source IDs must be unique.")
        component_ids = tuple(value.component_id for value in components)
        if len(set(component_ids)) != len(component_ids):
            raise ValueError("Texture-domain component IDs must be unique.")
        component_id_set = set(component_ids)
        if any(
            value.component_id and value.component_id not in component_id_set
            for value in points
        ):
            raise ValueError("Point references an unavailable component.")
        point_by_id = {value.source_id: value for value in points}
        for component in components:
            if any(source_id not in point_by_id for source_id in component.source_ids):
                raise ValueError("Component references an unavailable point.")
            if any(
                point_by_id[source_id].component_id != component.component_id
                or point_by_id[source_id].class_key != component.class_key
                for source_id in component.source_ids
            ):
                raise ValueError("Component membership is inconsistent.")
        assigned_ids = {
            point.source_id for point in points if point.component_id
        }
        component_member_ids = {
            source_id
            for component in components
            for source_id in component.source_ids
        }
        if assigned_ids != component_member_ids:
            raise ValueError("Texture-domain component membership is incomplete.")
        settings_fingerprint = str(self.settings_fingerprint).strip()
        input_fingerprint = str(self.input_fingerprint).strip()
        frame_fingerprint = str(self.frame_fingerprint).strip()
        if not settings_fingerprint or not input_fingerprint:
            raise ValueError("Texture-domain fingerprints must not be empty.")
        expected_input_fingerprint = texture_domain_input_fingerprint(
            frame_index=frame_index,
            source_view=source_view,
            points=tuple(
                TextureDomainPointInput(
                    point.source_id,
                    point.x_px,
                    point.y_px,
                )
                for point in points
            ),
        )
        if input_fingerprint != expected_input_fingerprint:
            raise ValueError("Texture-domain point fingerprint is invalid.")
        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(self, "points", points)
        object.__setattr__(self, "components", components)
        object.__setattr__(self, "settings_fingerprint", settings_fingerprint)
        object.__setattr__(self, "input_fingerprint", input_fingerprint)
        object.__setattr__(self, "frame_fingerprint", frame_fingerprint)

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "source_view": self.source_view,
            "points": [value.to_dict() for value in self.points],
            "components": [value.to_dict() for value in self.components],
            "settings_fingerprint": self.settings_fingerprint,
            "input_fingerprint": self.input_fingerprint,
            "frame_fingerprint": self.frame_fingerprint,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TextureDomainFrameResult":
        return cls(
            frame_index=int(payload["frame_index"]),
            source_view=str(payload["source_view"]),
            points=tuple(
                TextureDomainPointResult.from_dict(value)
                for value in payload["points"]
            ),
            components=tuple(
                TextureDomainComponent.from_dict(value)
                for value in payload["components"]
            ),
            settings_fingerprint=str(payload["settings_fingerprint"]),
            input_fingerprint=str(payload["input_fingerprint"]),
            frame_fingerprint=str(payload.get("frame_fingerprint", "")),
        )


@dataclass(frozen=True)
class TextureDomainViewSettings:
    show_overlay: bool = True
    opacity_percent: int = 80
    show_unknown: bool = False

    def __post_init__(self) -> None:
        opacity = int(self.opacity_percent)
        if not 0 <= opacity <= 100:
            raise ValueError("opacity_percent must be between 0 and 100.")
        object.__setattr__(self, "show_overlay", bool(self.show_overlay))
        object.__setattr__(self, "opacity_percent", opacity)
        object.__setattr__(self, "show_unknown", bool(self.show_unknown))

    def to_dict(self) -> dict[str, Any]:
        return {
            "show_overlay": self.show_overlay,
            "opacity_percent": self.opacity_percent,
            "show_unknown": self.show_unknown,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TextureDomainViewSettings":
        return cls(
            show_overlay=payload.get("show_overlay", True),
            opacity_percent=payload.get("opacity_percent", 80),
            show_unknown=payload.get("show_unknown", False),
        )


@dataclass(frozen=True)
class TextureDomainPointOverlay:
    source_ids: tuple[str, ...]
    points_xy_px: tuple[tuple[float, float], ...]
    colors_rgba: tuple[tuple[int, int, int, int], ...]

    @property
    def point_count(self) -> int:
        return len(self.source_ids)


def texture_domain_input_fingerprint(
    *,
    frame_index: int,
    source_view: str,
    points: tuple[TextureDomainPointInput, ...],
) -> str:
    return _canonical_fingerprint(
        {
            "frame_index": int(frame_index),
            "source_view": str(source_view),
            "points": [
                [value.source_id, value.x_px, value.y_px]
                for value in points
            ],
        }
    )


def texture_domain_frame_fingerprint(frame: np.ndarray) -> str:
    values = np.ascontiguousarray(np.asarray(frame))
    digest = hashlib.sha256()
    digest.update(str(values.dtype).encode("ascii"))
    digest.update(b"\0")
    digest.update(
        ",".join(str(int(value)) for value in values.shape).encode("ascii")
    )
    digest.update(b"\0")
    digest.update(values.tobytes(order="C"))
    return digest.hexdigest()


def _decode_ttmapp_prototypes() -> tuple[tuple[float, ...], ...]:
    packed = zlib.decompress(base64.b64decode(_TTMAPP_PROTOTYPES_ZLIB_BASE64))
    values = np.frombuffer(packed, dtype="<f4").reshape((3, 90))
    return tuple(tuple(float(value) for value in row) for row in values)


TTMAPP_TEXTURE_DOMAIN_PRESET = TextureDomainAnalysisSettings(
    preset_id="ttmapp-local-texture-v1",
    classes=(
        TextureDomainClassDefinition(
            key="orientation_a",
            short_label="A",
            display_name="Orientation A",
            reference_name="BLACK",
            color_rgb=(0, 180, 255),
        ),
        TextureDomainClassDefinition(
            key="orientation_b",
            short_label="B",
            display_name="Orientation B",
            reference_name="RED",
            color_rgb=(240, 45, 40),
        ),
        TextureDomainClassDefinition(
            key="orientation_c",
            short_label="C",
            display_name="Orientation C",
            reference_name="YELLOW",
            color_rgb=(245, 205, 0),
        ),
    ),
    prototype_histograms=_decode_ttmapp_prototypes(),
    distance_thresholds=(
        0.18923221347398997,
        0.4369675474773993,
        0.36018191818648526,
    ),
    minimum_margin=0.007084592877296226,
    render_scale=2,
    local_radius_rendered_px=24,
    high_pass_sigma_rendered_px=12.0,
    histogram_sigma_bins=1.5,
    neighbor_min_distance_source_px=7.5,
    neighbor_max_distance_source_px=18.0,
    neighbor_weight=0.05,
    smoothing_rounds=2,
    minimum_component_size=5,
    experimental=True,
    calibration_note=(
        "Calibrated on TTMAPP frames 250-262 and temporally validated on "
        "frames 263-268 from one acquisition."
    ),
)


def _neighbor_graph(
    points: tuple[TextureDomainPointInput, ...],
    settings: TextureDomainAnalysisSettings,
) -> tuple[np.ndarray, ...]:
    neighbors: list[list[int]] = [[] for _ in points]
    if len(points) < 2:
        return tuple(np.asarray(value, dtype=np.int64) for value in neighbors)
    coordinates = np.asarray(
        [(value.x_px, value.y_px) for value in points],
        dtype=np.float64,
    )
    tree = cKDTree(coordinates)
    for left, right in tree.query_pairs(settings.neighbor_max_distance_source_px):
        distance = float(np.linalg.norm(coordinates[left] - coordinates[right]))
        if distance < settings.neighbor_min_distance_source_px:
            continue
        neighbors[left].append(right)
        neighbors[right].append(left)
    return tuple(np.asarray(value, dtype=np.int64) for value in neighbors)


def _cosine_distances(
    descriptors: np.ndarray,
    settings: TextureDomainAnalysisSettings,
) -> np.ndarray:
    prototypes = np.asarray(settings.prototype_histograms, dtype=np.float64)
    descriptor_norm = np.linalg.norm(descriptors, axis=1, keepdims=True)
    prototype_norm = np.linalg.norm(prototypes, axis=1, keepdims=True).T
    divisor = descriptor_norm * prototype_norm
    similarities = np.divide(
        descriptors @ prototypes.T,
        divisor,
        out=np.zeros((len(descriptors), len(prototypes)), dtype=np.float64),
        where=divisor > 1e-12,
    )
    distances = 1.0 - similarities
    distances[~np.all(np.isfinite(descriptors), axis=1)] = np.inf
    return distances


def _smoothed_predictions(
    distances: np.ndarray,
    neighbors: tuple[np.ndarray, ...],
    settings: TextureDomainAnalysisSettings,
) -> np.ndarray:
    if not len(distances):
        return np.empty(0, dtype=np.int64)
    predictions = np.argmin(distances, axis=1)
    predictions[~np.any(np.isfinite(distances), axis=1)] = -1
    for _ in range(settings.smoothing_rounds):
        updated = predictions.copy()
        for index, adjacent in enumerate(neighbors):
            if predictions[index] < 0 or not adjacent.size:
                continue
            votes = predictions[adjacent]
            votes = votes[votes >= 0]
            if not votes.size:
                continue
            fractions = (
                np.bincount(votes, minlength=len(settings.classes))
                / len(votes)
            )
            adjusted = distances[index] - settings.neighbor_weight * fractions
            updated[index] = int(np.argmin(adjusted))
        predictions = updated
    return predictions


def _apply_unknown(
    predictions: np.ndarray,
    distances: np.ndarray,
    settings: TextureDomainAnalysisSettings,
) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    result = predictions.copy()
    margins = np.full(len(predictions), np.nan, dtype=np.float64)
    reasons = []
    for index, predicted in enumerate(predictions):
        if predicted < 0:
            reasons.append("insufficient_descriptor_evidence")
            continue
        ordered = np.sort(distances[index])
        margin = float(ordered[1] - ordered[0])
        margins[index] = margin
        if distances[index, predicted] > settings.distance_thresholds[predicted]:
            result[index] = -1
            reasons.append("below_distance_threshold")
        elif margin < settings.minimum_margin:
            result[index] = -1
            reasons.append("below_minimum_margin")
        else:
            reasons.append("accepted_result")
    return result, margins, tuple(reasons)


def _component_assignments(
    points: tuple[TextureDomainPointInput, ...],
    predictions: np.ndarray,
    neighbors: tuple[np.ndarray, ...],
    settings: TextureDomainAnalysisSettings,
) -> tuple[np.ndarray, tuple[str, ...], tuple[TextureDomainComponent, ...]]:
    filtered = predictions.copy()
    assignments = [""] * len(points)
    groups_by_class: dict[int, list[tuple[int, ...]]] = defaultdict(list)
    visited: set[int] = set()
    for start, class_index_value in enumerate(predictions):
        class_index = int(class_index_value)
        if class_index < 0 or start in visited:
            continue
        stack = [start]
        visited.add(start)
        members = []
        while stack:
            current = stack.pop()
            members.append(current)
            for adjacent_value in neighbors[current]:
                adjacent = int(adjacent_value)
                if adjacent in visited or int(predictions[adjacent]) != class_index:
                    continue
                visited.add(adjacent)
                stack.append(adjacent)
        groups_by_class[class_index].append(tuple(sorted(members)))

    components = []
    for class_index, groups in sorted(groups_by_class.items()):
        retained = []
        for group in groups:
            if len(group) < settings.minimum_component_size:
                filtered[np.asarray(group, dtype=np.int64)] = -1
            else:
                retained.append(group)
        retained.sort(
            key=lambda group: (
                -len(group),
                float(np.mean([points[index].y_px for index in group])),
                float(np.mean([points[index].x_px for index in group])),
            )
        )
        definition = settings.classes[class_index]
        for component_index, group in enumerate(retained, start=1):
            component_id = f"{definition.short_label}{component_index:02d}"
            for point_index in group:
                assignments[point_index] = component_id
            components.append(
                TextureDomainComponent(
                    component_id=component_id,
                    class_key=definition.key,
                    source_ids=tuple(points[index].source_id for index in group),
                    centroid_x_px=float(
                        np.mean([points[index].x_px for index in group])
                    ),
                    centroid_y_px=float(
                        np.mean([points[index].y_px for index in group])
                    ),
                )
            )
    return filtered, tuple(assignments), tuple(components)


def analyze_texture_domain_descriptors(
    *,
    frame_index: int,
    source_view: str,
    points: tuple[TextureDomainPointInput, ...],
    descriptors: np.ndarray,
    settings: TextureDomainAnalysisSettings,
    frame_fingerprint: str = "",
) -> TextureDomainFrameResult:
    points = tuple(points)
    if len({value.source_id for value in points}) != len(points):
        raise ValueError("Texture-domain input source IDs must be unique.")
    descriptor_array = np.asarray(descriptors, dtype=np.float64)
    expected_shape = (len(points), settings.histogram_bin_count)
    if descriptor_array.shape != expected_shape:
        raise ValueError(
            f"descriptors must have shape {expected_shape}, "
            f"received {descriptor_array.shape}."
        )
    distances = _cosine_distances(descriptor_array, settings)
    neighbors = _neighbor_graph(points, settings)
    nearest = np.argmin(distances, axis=1) if len(points) else np.empty(0, dtype=np.int64)
    if len(points):
        nearest[~np.any(np.isfinite(distances), axis=1)] = -1
    smoothed = _smoothed_predictions(distances, neighbors, settings)
    with_unknown, margins, threshold_reasons = _apply_unknown(smoothed, distances, settings)
    filtered, assignments, components = _component_assignments(
        points,
        with_unknown,
        neighbors,
        settings,
    )
    class_keys = tuple(value.key for value in settings.classes)
    point_results = []
    for index, point in enumerate(points):
        nearest_index = int(nearest[index])
        threshold_index = int(smoothed[index])
        final_index = int(filtered[index])
        nearest_distance = None if nearest_index < 0 else float(distances[index, nearest_index])
        threshold_distance = None if threshold_index < 0 else float(distances[index, threshold_index])
        margin = None if not np.isfinite(margins[index]) else float(margins[index])
        point_results.append(
            TextureDomainPointResult(
                source_id=point.source_id,
                x_px=point.x_px,
                y_px=point.y_px,
                class_key=TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY if final_index < 0 else class_keys[final_index],
                nearest_class_key=TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY if nearest_index < 0 else class_keys[nearest_index],
                threshold_candidate_class_key=TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY if threshold_index < 0 else class_keys[threshold_index],
                threshold_candidate_distance=threshold_distance,
                threshold_reason=threshold_reasons[index],
                component_id=assignments[index],
                nearest_distance=nearest_distance,
                margin=margin,
            )
        )
    input_fingerprint = texture_domain_input_fingerprint(
        frame_index=frame_index,
        source_view=source_view,
        points=points,
    )
    return TextureDomainFrameResult(
        frame_index=int(frame_index),
        source_view=str(source_view),
        points=tuple(point_results),
        components=components,
        settings_fingerprint=settings.fingerprint,
        input_fingerprint=input_fingerprint,
        frame_fingerprint=str(frame_fingerprint),
    )


def _normalized_rendered_frame(
    frame: np.ndarray,
    settings: TextureDomainAnalysisSettings,
) -> np.ndarray:
    values = np.asarray(frame, dtype=np.float64)
    finite = np.isfinite(values)
    normalized = np.zeros(values.shape, dtype=np.float64)
    if np.any(finite):
        low, high = np.percentile(values[finite], (1.0, 99.0))
        normalized[finite] = np.clip(
            (values[finite] - low) / max(float(high - low), 1e-12),
            0.0,
            1.0,
        )
    image = Image.fromarray(np.uint8(normalized * 255.0), mode="L")
    image = image.resize(
        (
            image.width * settings.render_scale,
            image.height * settings.render_scale,
        ),
        Image.Resampling.LANCZOS,
    )
    return np.asarray(image, dtype=np.float64)


def _gradient_fields(
    image: np.ndarray,
    settings: TextureDomainAnalysisSettings,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    foreground = ndimage.binary_fill_holes(
        ndimage.binary_closing(
            ndimage.binary_dilation(image > 0.0, iterations=2),
            iterations=8,
        )
    )
    labels, count = ndimage.label(foreground)
    if count:
        sizes = ndimage.sum(foreground, labels, range(1, count + 1))
        valid = labels == (int(np.argmax(sizes)) + 1)
    else:
        valid = np.ones(image.shape, dtype=bool)
    valid_float = valid.astype(np.float64)
    numerator = ndimage.gaussian_filter(
        image * valid_float,
        sigma=settings.high_pass_sigma_rendered_px,
        mode="nearest",
    )
    denominator = ndimage.gaussian_filter(
        valid_float,
        sigma=settings.high_pass_sigma_rendered_px,
        mode="nearest",
    )
    smooth = np.divide(
        numerator,
        denominator,
        out=np.zeros_like(numerator),
        where=denominator > 1e-6,
    )
    high_pass = np.where(valid, image - smooth, 0.0)
    gradient_rows, gradient_columns = np.gradient(high_pass)
    angle = np.degrees(np.arctan2(-gradient_rows, gradient_columns)) % 180.0
    energy = gradient_rows * gradient_rows + gradient_columns * gradient_columns
    return angle, energy, ndimage.binary_erosion(valid, iterations=2)


def _local_histogram(
    angle: np.ndarray,
    energy: np.ndarray,
    valid: np.ndarray,
    *,
    center_x: float,
    center_y: float,
    settings: TextureDomainAnalysisSettings,
) -> np.ndarray | None:
    radius = settings.local_radius_rendered_px
    height, width = angle.shape
    left = max(0, int(np.floor(center_x - radius)))
    right = min(width, int(np.ceil(center_x + radius + 1)))
    top = max(0, int(np.floor(center_y - radius)))
    bottom = min(height, int(np.ceil(center_y + radius + 1)))
    rows, columns = np.ogrid[top:bottom, left:right]
    distance_squared = (
        (columns - center_x) ** 2 + (rows - center_y) ** 2
    )
    local_valid = (
        valid[top:bottom, left:right]
        & (distance_squared <= float(radius * radius))
    )
    if np.count_nonzero(local_valid) < max(120, 0.35 * np.pi * radius * radius):
        return None
    local_energy = energy[top:bottom, left:right][local_valid]
    if float(np.sum(local_energy)) <= 1e-12:
        return None
    histogram, _ = np.histogram(
        angle[top:bottom, left:right][local_valid],
        bins=settings.histogram_bin_count,
        range=(0.0, 180.0),
        weights=local_energy,
    )
    histogram = ndimage.gaussian_filter1d(
        histogram.astype(np.float64),
        sigma=settings.histogram_sigma_bins,
        mode="wrap",
    )
    total = float(np.sum(histogram))
    return None if total <= 1e-12 else histogram / total


def extract_texture_domain_descriptors(
    frame: np.ndarray,
    points: tuple[TextureDomainPointInput, ...],
    settings: TextureDomainAnalysisSettings,
) -> np.ndarray:
    rendered = _normalized_rendered_frame(frame, settings)
    angle, energy, valid = _gradient_fields(rendered, settings)
    descriptors = np.full(
        (len(points), settings.histogram_bin_count),
        np.nan,
        dtype=np.float64,
    )
    for index, point in enumerate(points):
        histogram = _local_histogram(
            angle,
            energy,
            valid,
            center_x=point.x_px * settings.render_scale,
            center_y=point.y_px * settings.render_scale,
            settings=settings,
        )
        if histogram is not None:
            descriptors[index] = histogram
    return descriptors


def analyze_texture_domain_frame(
    *,
    frame_index: int,
    source_view: str,
    frame: np.ndarray,
    points: tuple[TextureDomainPointInput, ...],
    settings: TextureDomainAnalysisSettings,
) -> TextureDomainFrameResult:
    descriptors = extract_texture_domain_descriptors(frame, points, settings)
    return analyze_texture_domain_descriptors(
        frame_index=frame_index,
        source_view=source_view,
        points=points,
        descriptors=descriptors,
        settings=settings,
        frame_fingerprint=texture_domain_frame_fingerprint(frame),
    )


def build_texture_domain_point_overlay(
    frame_result: TextureDomainFrameResult,
    *,
    settings: TextureDomainAnalysisSettings,
    view_settings: TextureDomainViewSettings,
) -> TextureDomainPointOverlay:
    if frame_result.settings_fingerprint != settings.fingerprint:
        raise ValueError("Texture-domain frame result uses different settings.")
    if not view_settings.show_overlay:
        return TextureDomainPointOverlay((), (), ())
    color_by_key = {
        value.key: value.color_rgb for value in settings.classes
    }
    alpha = round(255 * view_settings.opacity_percent / 100.0)
    selected = [
        value
        for value in frame_result.points
        if value.class_key != TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY
        or view_settings.show_unknown
    ]
    return TextureDomainPointOverlay(
        source_ids=tuple(value.source_id for value in selected),
        points_xy_px=tuple((value.x_px, value.y_px) for value in selected),
        colors_rgba=tuple(
            (
                *color_by_key.get(value.class_key, (145, 150, 155)),
                alpha,
            )
            for value in selected
        ),
    )
