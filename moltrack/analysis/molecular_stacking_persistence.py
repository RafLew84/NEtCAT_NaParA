"""Versioned, dependency-checked persistence for molecular stacking."""

from __future__ import annotations

import types
from dataclasses import MISSING, asdict, dataclass, fields, is_dataclass
from typing import Literal, Mapping, Union, get_args, get_origin, get_type_hints

from .lattice_row_models import (
    LatticeDomainRowAssignment,
    LatticeRow,
    LatticeRowAssignmentAnalysis,
    LatticeRowAssignmentSettings,
    LatticeRowAxisCandidate,
    LatticeRowMemberAssignment,
    lattice_row_assignment_analysis_fingerprint,
)
from .molecular_orientation_models import MolecularOrientationMeasurement
from .molecular_orientation_prototype_models import (
    MolecularOrientationAxisEvidence,
    MolecularOrientationFrameData,
    MolecularOrientationPatternHypothesis,
    MolecularOrientationPrototype,
    MolecularOrientationPrototypeAnalysis,
    MolecularOrientationPrototypeSettings,
    MolecularOrientationRangeAxisEvidence,
    MolecularOrientationStateAssignment,
)
from .molecular_stacking_models import (
    MolecularStackingAnalysis,
    MolecularStackingSettings,
    OrientationalSubdomain,
    StackingOrder,
    molecular_stacking_analysis_fingerprint,
)
from .molecular_stacking_overlay import MolecularStackingDisplayResult


MOLECULAR_STACKING_SESSION_SCHEMA_VERSION = 1
MolecularStackingSessionStatus = Literal["not_computed", "computed"]

_SERIALIZABLE_DATACLASSES = frozenset(
    {
        LatticeRowAssignmentSettings,
        LatticeRowMemberAssignment,
        LatticeRow,
        LatticeRowAxisCandidate,
        LatticeDomainRowAssignment,
        LatticeRowAssignmentAnalysis,
        MolecularOrientationPrototypeSettings,
        MolecularOrientationPrototype,
        MolecularOrientationStateAssignment,
        MolecularOrientationPatternHypothesis,
        MolecularOrientationAxisEvidence,
        MolecularOrientationRangeAxisEvidence,
        MolecularOrientationPrototypeAnalysis,
        MolecularStackingSettings,
        OrientationalSubdomain,
        StackingOrder,
        MolecularStackingAnalysis,
    }
)


@dataclass(frozen=True)
class MolecularStackingSessionState:
    """Optional reproducible cache for one completed stacking analysis."""

    status: MolecularStackingSessionStatus = "not_computed"
    row_assignments: tuple[LatticeRowAssignmentAnalysis, ...] = ()
    prototype_analysis: MolecularOrientationPrototypeAnalysis | None = None
    stacking_analysis: MolecularStackingAnalysis | None = None
    stacking_analysis_fingerprint: str | None = None
    schema_version: int = MOLECULAR_STACKING_SESSION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status not in ("not_computed", "computed"):
            raise ValueError("Unsupported molecular stacking session status.")
        rows = tuple(self.row_assignments)
        if any(not isinstance(row, LatticeRowAssignmentAnalysis) for row in rows):
            raise TypeError("row_assignments must contain row analyses.")
        if self.schema_version != MOLECULAR_STACKING_SESSION_SCHEMA_VERSION:
            raise ValueError("Unsupported molecular stacking session schema.")
        if self.status == "not_computed":
            if (
                rows
                or self.prototype_analysis is not None
                or self.stacking_analysis is not None
                or self.stacking_analysis_fingerprint is not None
            ):
                raise ValueError("not_computed stacking state cannot contain results.")
            return
        if (
            not rows
            or not isinstance(
                self.prototype_analysis,
                MolecularOrientationPrototypeAnalysis,
            )
            or not isinstance(self.stacking_analysis, MolecularStackingAnalysis)
        ):
            raise ValueError("computed stacking state requires complete analyses.")
        frame_indices = self.prototype_analysis.input_frame_indices
        if len(rows) != len(frame_indices):
            raise ValueError("Persisted rows must cover every stacking frame.")
        row_fingerprints = tuple(
            (
                frame_index,
                lattice_row_assignment_analysis_fingerprint(row),
            )
            for frame_index, row in zip(frame_indices, rows, strict=True)
        )
        if (
            row_fingerprints != self.prototype_analysis.row_assignment_fingerprints
            or row_fingerprints != self.stacking_analysis.row_assignment_fingerprints
        ):
            raise ValueError("Persisted row assignments do not match analyses.")
        expected_fingerprint = molecular_stacking_analysis_fingerprint(
            self.stacking_analysis
        )
        if self.stacking_analysis_fingerprint != expected_fingerprint:
            raise ValueError("Persisted stacking fingerprint does not match result.")
        object.__setattr__(self, "row_assignments", rows)

    @classmethod
    def from_display_result(
        cls,
        result: MolecularStackingDisplayResult,
    ) -> "MolecularStackingSessionState":
        if not isinstance(result, MolecularStackingDisplayResult):
            raise TypeError("result must be MolecularStackingDisplayResult.")
        return cls(
            status="computed",
            row_assignments=tuple(frame.row_assignment for frame in result.frames),
            prototype_analysis=result.prototype_analysis,
            stacking_analysis=result.stacking_analysis,
            stacking_analysis_fingerprint=molecular_stacking_analysis_fingerprint(
                result.stacking_analysis
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "session_schema_version": self.schema_version,
            "status": self.status,
            "row_assignments": [
                asdict(row_assignment)
                for row_assignment in self.row_assignments
            ],
            "prototype_analysis": (
                None
                if self.prototype_analysis is None
                else asdict(self.prototype_analysis)
            ),
            "stacking_analysis": (
                None
                if self.stacking_analysis is None
                else asdict(self.stacking_analysis)
            ),
            "stacking_analysis_fingerprint": self.stacking_analysis_fingerprint,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "MolecularStackingSessionState":
        if not isinstance(payload, Mapping):
            raise TypeError("Molecular stacking session payload must be a mapping.")
        expected = {
            "session_schema_version",
            "status",
            "row_assignments",
            "prototype_analysis",
            "stacking_analysis",
            "stacking_analysis_fingerprint",
        }
        if set(payload) != expected:
            raise ValueError("Molecular stacking session fields must match schema.")
        raw_rows = payload["row_assignments"]
        if not isinstance(raw_rows, (list, tuple)):
            raise TypeError("row_assignments must be a sequence.")
        return cls(
            status=payload["status"],
            row_assignments=tuple(
                _decode_dataclass(LatticeRowAssignmentAnalysis, row)
                for row in raw_rows
            ),
            prototype_analysis=(
                None
                if payload["prototype_analysis"] is None
                else _decode_dataclass(
                    MolecularOrientationPrototypeAnalysis,
                    payload["prototype_analysis"],
                )
            ),
            stacking_analysis=(
                None
                if payload["stacking_analysis"] is None
                else _decode_dataclass(
                    MolecularStackingAnalysis,
                    payload["stacking_analysis"],
                )
            ),
            stacking_analysis_fingerprint=payload[
                "stacking_analysis_fingerprint"
            ],
            schema_version=payload["session_schema_version"],
        )


def restore_molecular_stacking_display_result(
    state: MolecularStackingSessionState,
    measurements: tuple[MolecularOrientationMeasurement, ...],
) -> MolecularStackingDisplayResult | None:
    """Restore an exact display result or reject a stale dependency cache."""

    if not isinstance(state, MolecularStackingSessionState):
        raise TypeError("state must be MolecularStackingSessionState.")
    if state.status != "computed":
        return None
    normalized_measurements = tuple(measurements)
    if any(
        not isinstance(value, MolecularOrientationMeasurement)
        for value in normalized_measurements
    ):
        raise TypeError("measurements must contain orientation measurements.")
    prototype = state.prototype_analysis
    stacking = state.stacking_analysis
    assert prototype is not None
    assert stacking is not None
    frames = tuple(
        MolecularOrientationFrameData(
            frame_index=frame_index,
            row_assignment=row_assignment,
            measurements=tuple(
                measurement
                for measurement in normalized_measurements
                if (
                    measurement.provenance.frame_index == frame_index
                    and measurement.provenance.orientation_reference
                    == "sample_x_axis_counterclockwise"
                    and (
                        prototype.source_view is None
                        or measurement.provenance.source_view
                        == prototype.source_view
                    )
                )
            ),
        )
        for frame_index, row_assignment in zip(
            prototype.input_frame_indices,
            state.row_assignments,
            strict=True,
        )
    )
    try:
        return MolecularStackingDisplayResult(
            frames=frames,
            prototype_analysis=prototype,
            stacking_analysis=stacking,
        )
    except ValueError:
        return None


def _decode_dataclass(cls, payload):
    if cls not in _SERIALIZABLE_DATACLASSES or not is_dataclass(cls):
        raise TypeError(f"Unsupported persisted dataclass: {cls!r}.")
    if not isinstance(payload, Mapping):
        raise TypeError(f"{cls.__name__} payload must be a mapping.")
    dataclass_fields = fields(cls)
    expected = {field.name for field in dataclass_fields}
    if set(payload) != expected:
        raise ValueError(f"{cls.__name__} fields must match schema.")
    hints = get_type_hints(cls)
    values = {}
    for field in dataclass_fields:
        if field.name not in payload:
            if field.default is not MISSING or field.default_factory is not MISSING:
                continue
            raise ValueError(f"Missing {cls.__name__}.{field.name}.")
        values[field.name] = _decode_value(
            hints[field.name],
            payload[field.name],
        )
    return cls(**values)


def _decode_value(expected_type, value):
    origin = get_origin(expected_type)
    arguments = get_args(expected_type)
    if expected_type is type(None):
        if value is not None:
            raise TypeError("Expected null.")
        return None
    if origin in (Union, types.UnionType):
        if value is None and type(None) in arguments:
            return None
        errors = []
        for argument in arguments:
            if argument is type(None):
                continue
            try:
                return _decode_value(argument, value)
            except (TypeError, ValueError) as exc:
                errors.append(exc)
        raise TypeError("Value does not match persisted union.") from errors[-1]
    if origin is Literal:
        if value not in arguments:
            raise ValueError(f"Unsupported literal value: {value!r}.")
        return value
    if origin is tuple:
        if not isinstance(value, (list, tuple)):
            raise TypeError("Expected a tuple-compatible sequence.")
        if len(arguments) == 2 and arguments[1] is Ellipsis:
            return tuple(_decode_value(arguments[0], item) for item in value)
        if len(arguments) != len(value):
            raise ValueError("Persisted tuple length does not match schema.")
        return tuple(
            _decode_value(argument, item)
            for argument, item in zip(arguments, value, strict=True)
        )
    if expected_type in _SERIALIZABLE_DATACLASSES:
        return _decode_dataclass(expected_type, value)
    if expected_type is bool:
        if not isinstance(value, bool):
            raise TypeError("Expected a boolean.")
        return value
    if expected_type is int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("Expected an integer.")
        return value
    if expected_type is float:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("Expected a number.")
        return float(value)
    if expected_type is str:
        if not isinstance(value, str):
            raise TypeError("Expected a string.")
        return value
    raise TypeError(f"Unsupported persisted field type: {expected_type!r}.")


__all__ = [
    "MOLECULAR_STACKING_SESSION_SCHEMA_VERSION",
    "MolecularStackingSessionState",
    "MolecularStackingSessionStatus",
    "restore_molecular_stacking_display_result",
]
