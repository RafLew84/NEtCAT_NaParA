"""Versioned settings and results for local directional-symmetry evidence."""

from __future__ import annotations

from dataclasses import dataclass, fields
from math import isfinite
from typing import Literal, Mapping, get_args


LOCAL_SYMMETRY_EVIDENCE_SCHEMA_VERSION = 1

LocalSymmetryModel = Literal[
    "trifold",
    "sixfold",
    "mixed",
    "disordered",
    "ambiguous",
    "unavailable",
]
LocalSymmetryClassificationReason = Literal[
    "classified_trifold",
    "classified_sixfold",
    "classified_mixed",
    "classified_disordered",
    "below_minimum_model_score",
    "below_minimum_margin",
    "insufficient_direction_coverage",
    "order_amplitudes_below_threshold",
    "local_order_unavailable",
]

_MODELS = set(get_args(LocalSymmetryModel))
_REASONS = set(get_args(LocalSymmetryClassificationReason))


@dataclass(frozen=True)
class LocalSymmetryEvidenceSettings:
    base_angular_tolerance_deg: float = 8.0
    direction_merge_tolerance_deg: float = 12.0
    inlier_sigma_multiplier: float = 2.0
    coverage_weight: float = 0.5
    edge_missing_coverage_relief: float = 0.5
    edge_confidence_factor: float = 0.85
    mixed_complexity_penalty: float = 0.15
    mixed_minimum_improvement: float = 0.08
    minimum_model_score: float = 0.5
    minimum_second_best_margin: float = 0.08
    confident_margin: float = 0.2
    minimum_expected_direction_coverage: float = 0.45
    minimum_relative_bond_weight: float = 0.05
    minimum_observed_directions: int = 3
    disordered_reference_direction_count: int = 6
    disordered_periodic_rejection_power: float = 4.0

    def __post_init__(self) -> None:
        positive_fields = (
            "base_angular_tolerance_deg",
            "direction_merge_tolerance_deg",
            "inlier_sigma_multiplier",
            "confident_margin",
            "disordered_periodic_rejection_power",
        )
        unit_fields = (
            "coverage_weight",
            "edge_missing_coverage_relief",
            "edge_confidence_factor",
            "mixed_complexity_penalty",
            "mixed_minimum_improvement",
            "minimum_model_score",
            "minimum_second_best_margin",
            "minimum_expected_direction_coverage",
            "minimum_relative_bond_weight",
        )
        for field_name in positive_fields:
            value = _finite_float(getattr(self, field_name), field_name)
            if value <= 0.0:
                raise ValueError(f"{field_name} must be positive.")
            object.__setattr__(self, field_name, value)
        for field_name in unit_fields:
            value = _finite_float(getattr(self, field_name), field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must lie between 0 and 1.")
            object.__setattr__(self, field_name, value)
        for field_name in (
            "minimum_observed_directions",
            "disordered_reference_direction_count",
        ):
            value = _positive_integer(getattr(self, field_name), field_name)
            object.__setattr__(self, field_name, value)
        if self.base_angular_tolerance_deg > 60.0:
            raise ValueError("base_angular_tolerance_deg must not exceed 60 degrees.")
        if self.direction_merge_tolerance_deg > 60.0:
            raise ValueError("direction_merge_tolerance_deg must not exceed 60 degrees.")
        if self.disordered_periodic_rejection_power > 16.0:
            raise ValueError(
                "disordered_periodic_rejection_power must not exceed 16."
            )

    def to_dict(self) -> dict[str, int | float]:
        return {field.name: getattr(self, field.name) for field in fields(self)}

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "LocalSymmetryEvidenceSettings":
        if not isinstance(payload, Mapping):
            raise TypeError("Local symmetry evidence settings must be a mapping.")
        names = {field.name for field in fields(cls)}
        if set(payload) != names:
            raise ValueError("Local symmetry evidence settings fields must match the schema.")
        return cls(**dict(payload))


@dataclass(frozen=True)
class LocalSymmetryEvidenceField:
    source_ids: tuple[str, ...]
    point_count: int
    trifold_model_score: tuple[float | None, ...]
    sixfold_model_score: tuple[float | None, ...]
    mixed_model_score: tuple[float | None, ...]
    disordered_model_score: tuple[float | None, ...]
    best_model: tuple[LocalSymmetryModel, ...]
    second_best_margin: tuple[float | None, ...]
    observed_direction_count: tuple[int, ...]
    expected_direction_coverage: tuple[float | None, ...]
    classification_confidence: tuple[float | None, ...]
    classification_reason: tuple[LocalSymmetryClassificationReason, ...]
    winning_model_orientation_deg: tuple[float | None, ...]
    edge_truncated_neighborhood: tuple[bool, ...]
    first_shell_graph_fingerprint: str
    local_order_analysis_fingerprint: str
    settings_fingerprint: str
    bond_evidence_fingerprint: str
    schema_version: int = LOCAL_SYMMETRY_EVIDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        point_count = _non_negative_integer(self.point_count, "point_count")
        source_ids = tuple(self.source_ids)
        if len(source_ids) != point_count:
            raise ValueError("source_ids must contain one value per point.")
        if any(not isinstance(value, str) or not value for value in source_ids):
            raise TypeError("source_ids must contain non-empty strings.")
        if len(set(source_ids)) != point_count:
            raise ValueError("source_ids must be unique.")
        if self.schema_version != LOCAL_SYMMETRY_EVIDENCE_SCHEMA_VERSION:
            raise ValueError(f"Unsupported schema_version: {self.schema_version!r}.")

        per_point_fields = (
            "trifold_model_score",
            "sixfold_model_score",
            "mixed_model_score",
            "disordered_model_score",
            "best_model",
            "second_best_margin",
            "observed_direction_count",
            "expected_direction_coverage",
            "classification_confidence",
            "classification_reason",
            "winning_model_orientation_deg",
            "edge_truncated_neighborhood",
        )
        for field_name in per_point_fields:
            values = tuple(getattr(self, field_name))
            if len(values) != point_count:
                raise ValueError(f"{field_name} must contain one value per point.")
            object.__setattr__(self, field_name, values)

        for field_name in (
            "trifold_model_score",
            "sixfold_model_score",
            "mixed_model_score",
            "disordered_model_score",
            "second_best_margin",
            "expected_direction_coverage",
            "classification_confidence",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_unit_tuple(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "winning_model_orientation_deg",
            _optional_angle_tuple(self.winning_model_orientation_deg),
        )
        object.__setattr__(
            self,
            "observed_direction_count",
            tuple(
                _non_negative_integer(value, f"observed_direction_count[{index}]")
                for index, value in enumerate(self.observed_direction_count)
            ),
        )
        if any(value not in _MODELS for value in self.best_model):
            raise ValueError("best_model contains an unsupported model.")
        if any(value not in _REASONS for value in self.classification_reason):
            raise ValueError("classification_reason contains an unsupported reason.")
        if any(not isinstance(value, bool) for value in self.edge_truncated_neighborhood):
            raise TypeError("edge_truncated_neighborhood must contain booleans.")
        for field_name in (
            "first_shell_graph_fingerprint",
            "local_order_analysis_fingerprint",
            "settings_fingerprint",
            "bond_evidence_fingerprint",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise TypeError(f"{field_name} must be a non-empty string.")
        self._validate_point_states()
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "point_count", point_count)

    def _validate_point_states(self) -> None:
        expected_classified_reason = {
            "trifold": "classified_trifold",
            "sixfold": "classified_sixfold",
            "mixed": "classified_mixed",
            "disordered": "classified_disordered",
        }
        ambiguous_reasons = {
            "below_minimum_model_score",
            "below_minimum_margin",
            "insufficient_direction_coverage",
            "order_amplitudes_below_threshold",
        }
        score_fields = (
            self.trifold_model_score,
            self.sixfold_model_score,
            self.mixed_model_score,
            self.disordered_model_score,
        )
        for index, model in enumerate(self.best_model):
            scores = tuple(values[index] for values in score_fields)
            confidence = self.classification_confidence[index]
            margin = self.second_best_margin[index]
            coverage = self.expected_direction_coverage[index]
            reason = self.classification_reason[index]
            orientation = self.winning_model_orientation_deg[index]
            if model == "unavailable":
                if any(value is not None for value in scores):
                    raise ValueError("Unavailable classification cannot contain model scores.")
                if any(value is not None for value in (confidence, margin, coverage)):
                    raise ValueError("Unavailable classification cannot contain evidence values.")
                if reason != "local_order_unavailable":
                    raise ValueError("Unavailable classification requires its explicit reason.")
                if orientation is not None:
                    raise ValueError("Unavailable classification cannot contain an orientation.")
            else:
                if any(value is None for value in scores):
                    raise ValueError("Available classification requires every model score.")
                if confidence is None or margin is None or coverage is None:
                    raise ValueError("Available classification requires evidence values.")
                if model == "ambiguous" and confidence != 0.0:
                    raise ValueError("Ambiguous classification requires zero confidence.")
                if model == "ambiguous":
                    if reason not in ambiguous_reasons:
                        raise ValueError("Ambiguous classification requires an ambiguity reason.")
                    if orientation is not None:
                        raise ValueError("Ambiguous classification cannot contain an orientation.")
                elif reason != expected_classified_reason[model]:
                    raise ValueError("Classified model and classification reason must agree.")
                if model in {"trifold", "sixfold"} and orientation is None:
                    raise ValueError("Periodic classification requires a model orientation.")
                if model in {"mixed", "disordered"} and orientation is not None:
                    raise ValueError(
                        "Mixed and disordered classifications have no single orientation."
                    )

    def index_for_source_id(self, source_id: str) -> int:
        try:
            return self.source_ids.index(source_id)
        except ValueError as exc:
            raise KeyError(f"Unknown source_id: {source_id!r}.") from exc


def _optional_unit_tuple(values: tuple[object, ...], field_name: str) -> tuple[float | None, ...]:
    normalized: list[float | None] = []
    for index, value in enumerate(values):
        if value is None:
            normalized.append(None)
            continue
        number = _finite_float(value, f"{field_name}[{index}]")
        if not 0.0 <= number <= 1.0:
            raise ValueError(f"{field_name} values must lie between 0 and 1.")
        normalized.append(number)
    return tuple(normalized)


def _optional_angle_tuple(values: tuple[object, ...]) -> tuple[float | None, ...]:
    normalized: list[float | None] = []
    for index, value in enumerate(values):
        if value is None:
            normalized.append(None)
        else:
            normalized.append(
                _finite_float(
                    value,
                    f"winning_model_orientation_deg[{index}]",
                )
                % 120.0
            )
    return tuple(normalized)


def _finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a number.")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be a number.") from exc
    if not isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return number


def _non_negative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return value


def _positive_integer(value: object, field_name: str) -> int:
    normalized = _non_negative_integer(value, field_name)
    if normalized == 0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized
