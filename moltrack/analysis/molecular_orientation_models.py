"""Versioned contracts for per-molecule orientation measurements."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isclose
from typing import Literal, Mapping

from ._molecular_orientation_contract import (
    bbox_xyxy as _bbox_xyxy,
    finite_float as _finite_float,
    non_empty_string as _non_empty_string,
    non_negative_integer as _non_negative_integer,
    optional_non_empty_string as _optional_non_empty_string,
    optional_strict_float as _optional_strict_float,
    optional_strict_string as _optional_strict_string,
    positive_shape as _positive_shape,
    require_exact_fields as _require_exact_fields,
    sha256_digest as _sha256,
    strict_float as _strict_float,
    strict_float_tuple as _strict_float_tuple,
    strict_integer as _strict_integer,
    strict_integer_tuple as _strict_integer_tuple,
    strict_string as _strict_string,
)

MOLECULAR_ORIENTATION_SCHEMA_VERSION = 1

MolecularOrientationStatus = Literal["available", "ambiguous", "unavailable"]
MolecularOrientationMethod = Literal[
    "manual",
    "mask_principal_axis",
    "stm_topography",
    "manual_correction",
]
MolecularOrientationSourceKind = Literal["detection", "segmentation"]

_SUPPORTED_STATUSES = {"available", "ambiguous", "unavailable"}
_SUPPORTED_METHODS = {
    "manual",
    "mask_principal_axis",
    "stm_topography",
    "manual_correction",
}
_SUPPORTED_SOURCE_KINDS = {"detection", "segmentation"}
_SUPPORTED_SOURCE_VIEWS = {"raw", "expanded_aligned"}
_SUPPORTED_ORIENTATION_REFERENCES = {
    "image_x_axis_counterclockwise",
    "sample_x_axis_counterclockwise",
}


@dataclass(frozen=True)
class MolecularOrientationProvenance:
    """Immutable source identity for one molecular image patch."""

    source_file_name: str
    source_file_sha256: str
    source_session_file_name: str | None
    source_session_sha256: str | None
    frame_index: int
    source_view: str
    source_kind: MolecularOrientationSourceKind
    source_id: str
    patch_bbox_xyxy: tuple[float, float, float, float]
    orientation_reference: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_file_name",
            _non_empty_string(self.source_file_name, "source_file_name"),
        )
        object.__setattr__(
            self,
            "source_file_sha256",
            _sha256(self.source_file_sha256, "source_file_sha256"),
        )
        session_name = _optional_non_empty_string(
            self.source_session_file_name,
            "source_session_file_name",
        )
        session_sha256 = (
            None
            if self.source_session_sha256 is None
            else _sha256(self.source_session_sha256, "source_session_sha256")
        )
        if (session_name is None) != (session_sha256 is None):
            raise ValueError(
                "source_session_file_name and source_session_sha256 must be "
                "provided together."
            )
        frame_index = _non_negative_integer(self.frame_index, "frame_index")
        source_view = _non_empty_string(self.source_view, "source_view")
        if source_view not in _SUPPORTED_SOURCE_VIEWS:
            raise ValueError(f"Unsupported source_view: {source_view!r}.")
        source_kind = _non_empty_string(self.source_kind, "source_kind")
        if source_kind not in _SUPPORTED_SOURCE_KINDS:
            raise ValueError(f"Unsupported source_kind: {source_kind!r}.")
        source_id = _non_empty_string(self.source_id, "source_id")
        patch_bbox = _bbox_xyxy(self.patch_bbox_xyxy, "patch_bbox_xyxy")
        orientation_reference = _non_empty_string(
            self.orientation_reference,
            "orientation_reference",
        )
        if orientation_reference not in _SUPPORTED_ORIENTATION_REFERENCES:
            raise ValueError(
                f"Unsupported orientation_reference: {orientation_reference!r}."
            )
        object.__setattr__(self, "source_session_file_name", session_name)
        object.__setattr__(self, "source_session_sha256", session_sha256)
        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(self, "source_kind", source_kind)
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "patch_bbox_xyxy", patch_bbox)
        object.__setattr__(
            self,
            "orientation_reference",
            orientation_reference,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "source_file_name": self.source_file_name,
            "source_file_sha256": self.source_file_sha256,
            "source_session_file_name": self.source_session_file_name,
            "source_session_sha256": self.source_session_sha256,
            "frame_index": self.frame_index,
            "source_view": self.source_view,
            "source_kind": self.source_kind,
            "source_id": self.source_id,
            "patch_bbox_xyxy": list(self.patch_bbox_xyxy),
            "orientation_reference": self.orientation_reference,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "MolecularOrientationProvenance":
        _require_exact_fields(
            payload,
            {
                "source_file_name",
                "source_file_sha256",
                "source_session_file_name",
                "source_session_sha256",
                "frame_index",
                "source_view",
                "source_kind",
                "source_id",
                "patch_bbox_xyxy",
                "orientation_reference",
            },
            "molecular orientation provenance",
        )
        return cls(
            source_file_name=_strict_string(
                payload["source_file_name"],
                "source_file_name",
            ),
            source_file_sha256=_strict_string(
                payload["source_file_sha256"],
                "source_file_sha256",
            ),
            source_session_file_name=_optional_strict_string(
                payload["source_session_file_name"],
                "source_session_file_name",
            ),
            source_session_sha256=_optional_strict_string(
                payload["source_session_sha256"],
                "source_session_sha256",
            ),
            frame_index=_strict_integer(payload["frame_index"], "frame_index"),
            source_view=_strict_string(payload["source_view"], "source_view"),
            source_kind=_strict_string(payload["source_kind"], "source_kind"),
            source_id=_strict_string(payload["source_id"], "source_id"),
            patch_bbox_xyxy=_strict_float_tuple(
                payload["patch_bbox_xyxy"],
                4,
                "patch_bbox_xyxy",
            ),
            orientation_reference=_strict_string(
                payload["orientation_reference"],
                "orientation_reference",
            ),
        )


@dataclass(frozen=True)
class MolecularOrientationMeasurement:
    """One orientation result whose angle is periodic, not directional."""

    measurement_id: str
    status: MolecularOrientationStatus
    angle_deg: float | None
    periodicity_deg: float
    confidence: float | None
    method: MolecularOrientationMethod
    patch_shape_px: tuple[int, int]
    provenance: MolecularOrientationProvenance
    manual_correction: MolecularOrientationManualCorrection | None = None
    schema_version: int = MOLECULAR_ORIENTATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        measurement_id = _non_empty_string(self.measurement_id, "measurement_id")
        status = _non_empty_string(self.status, "status")
        if status not in _SUPPORTED_STATUSES:
            raise ValueError(f"Unsupported molecular orientation status: {status!r}.")
        periodicity_deg = _finite_float(self.periodicity_deg, "periodicity_deg")
        if not 0.0 < periodicity_deg <= 360.0:
            raise ValueError("periodicity_deg must lie in (0, 360].")
        angle_deg = (
            None
            if self.angle_deg is None
            else _finite_float(self.angle_deg, "angle_deg") % periodicity_deg
        )
        confidence = (
            None
            if self.confidence is None
            else _finite_float(self.confidence, "confidence")
        )
        if confidence is not None and not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must lie between 0 and 1.")
        if status == "available" and (angle_deg is None or confidence is None):
            raise ValueError(
                "available orientation requires angle_deg and confidence."
            )
        if status == "unavailable" and (angle_deg is not None or confidence is not None):
            raise ValueError(
                "unavailable orientation must not contain angle_deg or confidence."
            )
        method = _non_empty_string(self.method, "method")
        if method not in _SUPPORTED_METHODS:
            raise ValueError(f"Unsupported molecular orientation method: {method!r}.")
        patch_shape_px = _positive_shape(self.patch_shape_px, "patch_shape_px")
        if not isinstance(self.provenance, MolecularOrientationProvenance):
            raise TypeError("provenance must be MolecularOrientationProvenance.")
        patch_bbox = self.provenance.patch_bbox_xyxy
        bbox_shape_px = (
            patch_bbox[3] - patch_bbox[1],
            patch_bbox[2] - patch_bbox[0],
        )
        if not all(
            isclose(float(shape), bbox_size, rel_tol=0.0, abs_tol=1e-9)
            for shape, bbox_size in zip(patch_shape_px, bbox_shape_px)
        ):
            raise ValueError(
                "patch_shape_px must match the provenance patch_bbox_xyxy size."
            )
        if self.manual_correction is not None:
            if not isinstance(
                self.manual_correction,
                MolecularOrientationManualCorrection,
            ):
                raise TypeError(
                    "manual_correction must be MolecularOrientationManualCorrection."
                )
            if method != "manual_correction":
                raise ValueError(
                    "A corrected measurement must use method='manual_correction'."
                )
            original_angle = self.manual_correction.original_result.angle_deg
            if original_angle is not None and not isclose(
                original_angle,
                original_angle % periodicity_deg,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError(
                    "The original result angle must already be normalized to "
                    "periodicity_deg."
                )
        elif method == "manual_correction":
            raise ValueError(
                "method='manual_correction' requires manual_correction metadata."
            )
        schema_version = _strict_integer(self.schema_version, "schema_version")
        if schema_version != MOLECULAR_ORIENTATION_SCHEMA_VERSION:
            raise ValueError("Unsupported molecular orientation schema version.")
        object.__setattr__(self, "measurement_id", measurement_id)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "angle_deg", angle_deg)
        object.__setattr__(self, "periodicity_deg", periodicity_deg)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "patch_shape_px", patch_shape_px)
        object.__setattr__(self, "schema_version", schema_version)

    @property
    def is_manually_corrected(self) -> bool:
        return self.manual_correction is not None

    def with_manual_correction(
        self,
        *,
        status: MolecularOrientationStatus,
        angle_deg: float | None,
        confidence: float | None,
        reviewer: str,
        note: str = "",
    ) -> "MolecularOrientationMeasurement":
        original_result = (
            self.manual_correction.original_result
            if self.manual_correction is not None
            else MolecularOrientationResultSnapshot(
                status=self.status,
                angle_deg=self.angle_deg,
                confidence=self.confidence,
                method=self.method,
            )
        )
        correction = MolecularOrientationManualCorrection(
            reviewer=reviewer,
            note=note,
            original_result=original_result,
        )
        return replace(
            self,
            status=status,
            angle_deg=angle_deg,
            confidence=confidence,
            method="manual_correction",
            manual_correction=correction,
        )

    def reset_manual_correction(self) -> "MolecularOrientationMeasurement":
        if self.manual_correction is None:
            return self
        original = self.manual_correction.original_result
        return replace(
            self,
            status=original.status,
            angle_deg=original.angle_deg,
            confidence=original.confidence,
            method=original.method,
            manual_correction=None,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "measurement_id": self.measurement_id,
            "status": self.status,
            "angle_deg": self.angle_deg,
            "periodicity_deg": self.periodicity_deg,
            "confidence": self.confidence,
            "method": self.method,
            "patch_shape_px": list(self.patch_shape_px),
            "provenance": self.provenance.to_dict(),
            "manual_correction": (
                None
                if self.manual_correction is None
                else self.manual_correction.to_dict()
            ),
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "MolecularOrientationMeasurement":
        _require_exact_fields(
            payload,
            {
                "schema_version",
                "measurement_id",
                "status",
                "angle_deg",
                "periodicity_deg",
                "confidence",
                "method",
                "patch_shape_px",
                "provenance",
                "manual_correction",
            },
            "molecular orientation measurement",
        )
        provenance = payload["provenance"]
        if not isinstance(provenance, Mapping):
            raise TypeError("provenance must be an object.")
        raw_correction = payload["manual_correction"]
        if raw_correction is not None and not isinstance(raw_correction, Mapping):
            raise TypeError("manual_correction must be an object or null.")
        return cls(
            schema_version=_strict_integer(
                payload["schema_version"],
                "schema_version",
            ),
            measurement_id=_strict_string(
                payload["measurement_id"],
                "measurement_id",
            ),
            status=_strict_string(payload["status"], "status"),
            angle_deg=_optional_strict_float(payload["angle_deg"], "angle_deg"),
            periodicity_deg=_strict_float(
                payload["periodicity_deg"],
                "periodicity_deg",
            ),
            confidence=_optional_strict_float(
                payload["confidence"],
                "confidence",
            ),
            method=_strict_string(payload["method"], "method"),
            patch_shape_px=_strict_integer_tuple(
                payload["patch_shape_px"],
                2,
                "patch_shape_px",
            ),
            provenance=MolecularOrientationProvenance.from_dict(provenance),
            manual_correction=(
                None
                if raw_correction is None
                else MolecularOrientationManualCorrection.from_dict(
                    raw_correction
                )
            ),
        )


@dataclass(frozen=True)
class MolecularOrientationResultSnapshot:
    """Original result retained while a manual correction is active."""

    status: MolecularOrientationStatus
    angle_deg: float | None
    confidence: float | None
    method: MolecularOrientationMethod

    def __post_init__(self) -> None:
        if self.status not in _SUPPORTED_STATUSES:
            raise ValueError("Unsupported original molecular orientation status.")
        if self.angle_deg is not None:
            object.__setattr__(
                self,
                "angle_deg",
                _finite_float(self.angle_deg, "original_result.angle_deg"),
            )
        if self.confidence is not None:
            confidence = _finite_float(
                self.confidence,
                "original_result.confidence",
            )
            if not 0.0 <= confidence <= 1.0:
                raise ValueError(
                    "original_result.confidence must lie between 0 and 1."
                )
            object.__setattr__(self, "confidence", confidence)
        if self.status == "available" and (
            self.angle_deg is None or self.confidence is None
        ):
            raise ValueError(
                "Available original result requires angle_deg and confidence."
            )
        if self.status == "unavailable" and (
            self.angle_deg is not None or self.confidence is not None
        ):
            raise ValueError(
                "Unavailable original result must not contain angle_deg or confidence."
            )
        if self.method not in _SUPPORTED_METHODS.difference({"manual_correction"}):
            raise ValueError("Unsupported original molecular orientation method.")

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "angle_deg": self.angle_deg,
            "confidence": self.confidence,
            "method": self.method,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "MolecularOrientationResultSnapshot":
        _require_exact_fields(
            payload,
            {"status", "angle_deg", "confidence", "method"},
            "molecular orientation original result",
        )
        return cls(
            status=_strict_string(payload["status"], "status"),
            angle_deg=_optional_strict_float(payload["angle_deg"], "angle_deg"),
            confidence=_optional_strict_float(
                payload["confidence"],
                "confidence",
            ),
            method=_strict_string(payload["method"], "method"),
        )


@dataclass(frozen=True)
class MolecularOrientationManualCorrection:
    """Audit metadata and original value for a reversible manual correction."""

    reviewer: str
    note: str
    original_result: MolecularOrientationResultSnapshot

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reviewer",
            _non_empty_string(self.reviewer, "reviewer"),
        )
        if not isinstance(self.note, str):
            raise TypeError("note must be a string.")
        object.__setattr__(self, "note", self.note.strip())
        if not isinstance(
            self.original_result,
            MolecularOrientationResultSnapshot,
        ):
            raise TypeError(
                "original_result must be MolecularOrientationResultSnapshot."
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "reviewer": self.reviewer,
            "note": self.note,
            "original_result": self.original_result.to_dict(),
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "MolecularOrientationManualCorrection":
        _require_exact_fields(
            payload,
            {"reviewer", "note", "original_result"},
            "molecular orientation manual correction",
        )
        original_result = payload["original_result"]
        if not isinstance(original_result, Mapping):
            raise TypeError("original_result must be an object.")
        return cls(
            reviewer=_strict_string(payload["reviewer"], "reviewer"),
            note=_strict_string(payload["note"], "note", allow_empty=True),
            original_result=MolecularOrientationResultSnapshot.from_dict(
                original_result
            ),
        )
