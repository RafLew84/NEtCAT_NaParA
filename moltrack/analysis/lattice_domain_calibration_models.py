"""Versioned contracts for final M3/M6 lattice-domain calibration."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from math import isfinite
from pathlib import Path
from typing import Literal, Mapping

from .lattice_domain_validation import LatticeDomainPartitionLabels
from .m6_settings import MolecularM6OrientationAnalysisSettings


LATTICE_DOMAIN_CALIBRATION_SCHEMA_VERSION = 1
LATTICE_DOMAIN_CALIBRATION_ALGORITHM_VERSION = "1.0"
TTMAPP_FIRST_SHELL_R_MIN_NM = 30.0
TTMAPP_FIRST_SHELL_R_MAX_NM = 70.0
LatticeDomainCalibrationSplit = Literal["calibration", "holdout"]
LatticeDomainCalibrationSymmetry = Literal["trifold", "sixfold", "unknown"]
LatticeDomainCalibrationStatus = Literal[
    "stable",
    "stable_geometry_unverified",
    "no_stable_solution",
]
LatticeDomainCalibrationPhase = Literal[
    "one_at_a_time",
    "multivariate",
    "stability",
    "holdout",
]

LATTICE_DOMAIN_CALIBRATION_QUALITY_TAGS = (
    "incomplete_neighborhood",
    "edge",
    "jitter",
    "missing_molecules",
)


@dataclass(frozen=True)
class LatticeDomainCalibrationParameterSpec:
    """One calibration dimension and its bounded local perturbation."""

    name: str
    step: float
    kind: Literal[
        "unit_interval",
        "angle_deg",
        "nonnegative",
        "positive_log",
        "positive_integer",
    ]
    default_selected: bool = True
    include_in_multivariate: bool = True


# First-shell radii are intentionally absent. They are validated as a separate
# geometry experiment before these classification parameters are calibrated.
LATTICE_DOMAIN_CALIBRATION_PARAMETER_SPECS = (
    LatticeDomainCalibrationParameterSpec(
        "local_symmetry_trifold_minimum_model_score", 0.05, "unit_interval"
    ),
    LatticeDomainCalibrationParameterSpec(
        "local_symmetry_sixfold_minimum_model_score", 0.05, "unit_interval"
    ),
    LatticeDomainCalibrationParameterSpec(
        "local_symmetry_mixed_minimum_model_score", 0.05, "unit_interval"
    ),
    LatticeDomainCalibrationParameterSpec(
        "local_symmetry_minimum_second_best_margin", 0.02, "unit_interval"
    ),
    LatticeDomainCalibrationParameterSpec(
        "local_symmetry_minimum_expected_direction_coverage",
        0.05,
        "unit_interval",
    ),
    LatticeDomainCalibrationParameterSpec(
        "lattice_edge_trifold_orientation_tolerance_deg", 2.0, "angle_deg"
    ),
    LatticeDomainCalibrationParameterSpec(
        "lattice_edge_sixfold_orientation_tolerance_deg", 2.0, "angle_deg"
    ),
    LatticeDomainCalibrationParameterSpec(
        "lattice_edge_mixed_model_profile_tolerance", 0.05, "unit_interval"
    ),
    LatticeDomainCalibrationParameterSpec(
        "lattice_edge_conditional_channel_minimum_score", 0.05, "unit_interval"
    ),
    LatticeDomainCalibrationParameterSpec(
        "lattice_edge_minimum_classification_confidence", 0.05, "unit_interval"
    ),
    LatticeDomainCalibrationParameterSpec(
        "lattice_edge_minimum_orientation_confidence", 0.05, "unit_interval"
    ),
    LatticeDomainCalibrationParameterSpec(
        "lattice_seed_min_model_score", 0.05, "unit_interval"
    ),
    LatticeDomainCalibrationParameterSpec(
        "lattice_halo_min_model_score", 0.05, "unit_interval"
    ),
    LatticeDomainCalibrationParameterSpec("q_seed", 0.05, "unit_interval"),
    LatticeDomainCalibrationParameterSpec("q_grow", 0.05, "unit_interval"),
    LatticeDomainCalibrationParameterSpec(
        "seed_angle_tolerance_deg", 2.0, "angle_deg"
    ),
    LatticeDomainCalibrationParameterSpec(
        "grow_angle_tolerance_deg", 2.0, "angle_deg"
    ),
    LatticeDomainCalibrationParameterSpec(
        "domain_conflict_margin", 0.02, "unit_interval"
    ),
    LatticeDomainCalibrationParameterSpec(
        "orientation_zero_tolerance",
        10.0,
        "positive_log",
        default_selected=False,
        include_in_multivariate=False,
    ),
    LatticeDomainCalibrationParameterSpec(
        "min_neighbors_for_local_order",
        1.0,
        "positive_integer",
        default_selected=False,
        include_in_multivariate=False,
    ),
    LatticeDomainCalibrationParameterSpec(
        "min_neighbors_for_seed",
        1.0,
        "positive_integer",
        default_selected=False,
        include_in_multivariate=False,
    ),
    LatticeDomainCalibrationParameterSpec(
        "min_seed_size", 1.0, "positive_integer"
    ),
    LatticeDomainCalibrationParameterSpec(
        "min_domain_size", 1.0, "positive_integer"
    ),
)
LATTICE_DOMAIN_CALIBRATION_PARAMETER_NAMES = tuple(
    value.name for value in LATTICE_DOMAIN_CALIBRATION_PARAMETER_SPECS
)
LATTICE_DOMAIN_CALIBRATION_PARAMETER_SPEC_BY_NAME = {
    value.name: value for value in LATTICE_DOMAIN_CALIBRATION_PARAMETER_SPECS
}
LATTICE_DOMAIN_CALIBRATION_PRIORITY_INTERACTIONS = (
    ("q_seed", "q_grow"),
    (
        "local_symmetry_trifold_minimum_model_score",
        "lattice_edge_trifold_orientation_tolerance_deg",
    ),
    (
        "local_symmetry_sixfold_minimum_model_score",
        "lattice_edge_sixfold_orientation_tolerance_deg",
    ),
    (
        "local_symmetry_mixed_minimum_model_score",
        "lattice_edge_mixed_model_profile_tolerance",
    ),
    (
        "local_symmetry_minimum_second_best_margin",
        "lattice_edge_minimum_classification_confidence",
    ),
    (
        "local_symmetry_minimum_expected_direction_coverage",
        "lattice_edge_minimum_orientation_confidence",
    ),
    ("lattice_edge_conditional_channel_minimum_score", "domain_conflict_margin"),
    ("lattice_seed_min_model_score", "lattice_halo_min_model_score"),
    ("q_seed", "seed_angle_tolerance_deg"),
    ("q_grow", "grow_angle_tolerance_deg"),
    ("lattice_seed_min_model_score", "q_seed"),
    ("lattice_halo_min_model_score", "q_grow"),
    ("min_seed_size", "q_seed"),
    ("min_domain_size", "lattice_halo_min_model_score"),
    ("domain_conflict_margin", "grow_angle_tolerance_deg"),
)


@dataclass(frozen=True)
class LatticeDomainCalibrationReferenceFrame:
    """Manual final-domain partition for one independently evaluated frame."""

    frame_index: int
    split: LatticeDomainCalibrationSplit
    symmetry_class: LatticeDomainCalibrationSymmetry
    quality_tags: tuple[str, ...]
    labels: LatticeDomainPartitionLabels
    first_shell_neighbor_pairs: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if (
            isinstance(self.frame_index, bool)
            or not isinstance(self.frame_index, int)
            or self.frame_index < 0
        ):
            raise ValueError("frame_index must be a non-negative integer.")
        if self.split not in {"calibration", "holdout"}:
            raise ValueError("split must be calibration or holdout.")
        if self.symmetry_class not in {"trifold", "sixfold", "unknown"}:
            raise ValueError("Unsupported symmetry_class.")
        quality_tags = _normalized_string_tuple(self.quality_tags, "quality_tags")
        if any(not value for value in quality_tags):
            raise ValueError("quality_tags must contain non-empty strings.")
        if len(set(quality_tags)) != len(quality_tags):
            raise ValueError("quality_tags must not contain duplicates.")
        unknown_quality_tags = sorted(
            set(quality_tags).difference(LATTICE_DOMAIN_CALIBRATION_QUALITY_TAGS)
        )
        if unknown_quality_tags:
            raise ValueError(
                "Unsupported calibration quality tag(s): "
                + ", ".join(unknown_quality_tags)
            )
        if not isinstance(self.labels, LatticeDomainPartitionLabels):
            raise TypeError("labels must be LatticeDomainPartitionLabels.")
        pairs = tuple(
            _canonical_neighbor_pair(value, "first_shell_neighbor_pairs")
            for value in self.first_shell_neighbor_pairs
        )
        if len(set(pairs)) != len(pairs):
            raise ValueError("first_shell_neighbor_pairs must not contain duplicates.")
        unknown_source_ids = {
            source_id
            for pair in pairs
            for source_id in pair
            if source_id not in self.labels.source_ids
        }
        if unknown_source_ids:
            raise ValueError(
                "First-shell neighbor pairs contain unknown source IDs: "
                + ", ".join(sorted(unknown_source_ids))
            )
        object.__setattr__(self, "quality_tags", quality_tags)
        object.__setattr__(self, "first_shell_neighbor_pairs", pairs)

    def to_dict(self) -> dict[str, object]:
        return {
            "frame_index": self.frame_index,
            "split": self.split,
            "symmetry_class": self.symmetry_class,
            "quality_tags": list(self.quality_tags),
            "labels": _partition_to_dict(self.labels),
            "first_shell_neighbor_pairs": [
                list(value) for value in self.first_shell_neighbor_pairs
            ],
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "LatticeDomainCalibrationReferenceFrame":
        _require_exact_fields(
            payload,
            {
                "frame_index",
                "split",
                "symmetry_class",
                "quality_tags",
                "labels",
                "first_shell_neighbor_pairs",
            },
            "reference frame",
        )
        labels = payload["labels"]
        if not isinstance(labels, Mapping):
            raise TypeError("Reference frame labels must be an object.")
        return cls(
            frame_index=_integer(payload["frame_index"], "frame_index"),
            split=_string(payload["split"], "split"),
            symmetry_class=_string(payload["symmetry_class"], "symmetry_class"),
            quality_tags=_string_tuple(payload["quality_tags"], "quality_tags"),
            labels=_partition_from_dict(labels),
            first_shell_neighbor_pairs=_neighbor_pairs(
                payload["first_shell_neighbor_pairs"],
                "first_shell_neighbor_pairs",
            ),
        )


@dataclass(frozen=True)
class LatticeDomainCalibrationReferenceDataset:
    """Reviewed manual labels with an immutable calibration/holdout split."""

    dataset_id: str
    source_file_name: str
    source_frame_count: int
    source_sample_fingerprint: str
    source_view: str
    use_segmentation_centroids: bool
    reviewed: bool
    frames: tuple[LatticeDomainCalibrationReferenceFrame, ...]
    schema_version: int = LATTICE_DOMAIN_CALIBRATION_SCHEMA_VERSION
    uses_tracking: bool = False

    def __post_init__(self) -> None:
        dataset_id = _normalized_string(self.dataset_id, "dataset_id")
        source_file_name = _normalized_string(
            self.source_file_name,
            "source_file_name",
        )
        source_sample_fingerprint = _normalized_string(
            self.source_sample_fingerprint,
            "source_sample_fingerprint",
        )
        if (
            len(source_sample_fingerprint) != 64
            or any(
                character not in "0123456789abcdef"
                for character in source_sample_fingerprint.casefold()
            )
        ):
            raise ValueError(
                "source_sample_fingerprint must be a SHA-256 hexadecimal digest."
            )
        source_sample_fingerprint = source_sample_fingerprint.casefold()
        source_view = _normalized_string(self.source_view, "source_view")
        if not dataset_id:
            raise ValueError("dataset_id must not be empty.")
        if not source_file_name:
            raise ValueError("source_file_name must not be empty.")
        if (
            isinstance(self.source_frame_count, bool)
            or not isinstance(self.source_frame_count, int)
            or self.source_frame_count < 1
        ):
            raise ValueError("source_frame_count must be a positive integer.")
        if not source_view:
            raise ValueError("source_view must not be empty.")
        if not isinstance(self.use_segmentation_centroids, bool):
            raise TypeError("use_segmentation_centroids must be a boolean.")
        if not isinstance(self.reviewed, bool):
            raise TypeError("reviewed must be a boolean.")
        if self.schema_version != LATTICE_DOMAIN_CALIBRATION_SCHEMA_VERSION:
            raise ValueError("Unsupported lattice-domain calibration schema version.")
        if self.uses_tracking is not False:
            raise ValueError("Lattice-domain calibration must not use tracking.")
        frames = tuple(self.frames)
        if not frames or any(
            not isinstance(value, LatticeDomainCalibrationReferenceFrame)
            for value in frames
        ):
            raise ValueError("frames must contain reference frames.")
        frame_indices = tuple(value.frame_index for value in frames)
        if len(set(frame_indices)) != len(frame_indices):
            raise ValueError("Reference frame indices must be unique.")
        splits = {value.split for value in frames}
        if splits != {"calibration", "holdout"}:
            raise ValueError(
                "Reference dataset requires explicit calibration and holdout frames."
            )
        object.__setattr__(self, "dataset_id", dataset_id)
        object.__setattr__(self, "source_file_name", source_file_name)
        object.__setattr__(
            self,
            "source_sample_fingerprint",
            source_sample_fingerprint,
        )
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(self, "frames", frames)

    @property
    def calibration_frames(self) -> tuple[LatticeDomainCalibrationReferenceFrame, ...]:
        return tuple(value for value in self.frames if value.split == "calibration")

    @property
    def holdout_frames(self) -> tuple[LatticeDomainCalibrationReferenceFrame, ...]:
        return tuple(value for value in self.frames if value.split == "holdout")

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "dataset_id": self.dataset_id,
            "source_file_name": self.source_file_name,
            "source_frame_count": self.source_frame_count,
            "source_sample_fingerprint": self.source_sample_fingerprint,
            "source_view": self.source_view,
            "use_segmentation_centroids": self.use_segmentation_centroids,
            "reviewed": self.reviewed,
            "uses_tracking": self.uses_tracking,
            "frames": [value.to_dict() for value in self.frames],
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "LatticeDomainCalibrationReferenceDataset":
        _require_exact_fields(
            payload,
            {
                "schema_version",
                "dataset_id",
                "source_file_name",
                "source_frame_count",
                "source_sample_fingerprint",
                "source_view",
                "use_segmentation_centroids",
                "reviewed",
                "uses_tracking",
                "frames",
            },
            "reference dataset",
        )
        raw_frames = payload["frames"]
        if not isinstance(raw_frames, (list, tuple)):
            raise TypeError("Reference frames must be an array.")
        frames = []
        for value in raw_frames:
            if not isinstance(value, Mapping):
                raise TypeError("Every reference frame must be an object.")
            frames.append(LatticeDomainCalibrationReferenceFrame.from_dict(value))
        return cls(
            schema_version=_integer(payload["schema_version"], "schema_version"),
            dataset_id=_string(payload["dataset_id"], "dataset_id"),
            source_file_name=_string(
                payload["source_file_name"],
                "source_file_name",
            ),
            source_frame_count=_integer(
                payload["source_frame_count"],
                "source_frame_count",
            ),
            source_sample_fingerprint=_string(
                payload["source_sample_fingerprint"],
                "source_sample_fingerprint",
            ),
            source_view=_string(payload["source_view"], "source_view"),
            use_segmentation_centroids=_boolean(
                payload["use_segmentation_centroids"],
                "use_segmentation_centroids",
            ),
            reviewed=_boolean(payload["reviewed"], "reviewed"),
            uses_tracking=_boolean(payload["uses_tracking"], "uses_tracking"),
            frames=tuple(frames),
        )


@dataclass(frozen=True)
class LatticeDomainCalibrationSweepSettings:
    """Bounded sweep definition; first-shell geometry is intentionally absent."""

    baseline_settings: MolecularM6OrientationAnalysisSettings
    parameter_names: tuple[str, ...]
    max_multivariate_variants: int = 24
    max_stability_candidates: int = 5
    minimum_stability_ari: float = 0.8
    minimum_holdout_ari: float | None = None
    minimum_first_shell_f1: float = 0.8

    def __post_init__(self) -> None:
        if not isinstance(
            self.baseline_settings,
            MolecularM6OrientationAnalysisSettings,
        ):
            raise TypeError("baseline_settings must be M6 settings.")
        parameter_names = _normalized_string_tuple(
            self.parameter_names,
            "parameter_names",
        )
        if any(not value for value in parameter_names):
            raise ValueError("parameter_names must contain non-empty names.")
        if len(set(parameter_names)) != len(parameter_names):
            raise ValueError("parameter_names must not contain duplicates.")
        unknown = sorted(
            set(parameter_names).difference(LATTICE_DOMAIN_CALIBRATION_PARAMETER_NAMES)
        )
        if unknown:
            raise ValueError(f"Unsupported calibration parameters: {', '.join(unknown)}")
        if (
            isinstance(self.max_multivariate_variants, bool)
            or not isinstance(self.max_multivariate_variants, int)
            or self.max_multivariate_variants < 0
        ):
            raise ValueError("max_multivariate_variants must be non-negative.")
        if (
            isinstance(self.max_stability_candidates, bool)
            or not isinstance(self.max_stability_candidates, int)
            or self.max_stability_candidates < 1
        ):
            raise ValueError("max_stability_candidates must be a positive integer.")
        minimum_stability_ari = _unit_float(
            self.minimum_stability_ari,
            "minimum_stability_ari",
        )
        minimum_holdout_ari = (
            minimum_stability_ari
            if self.minimum_holdout_ari is None
            else _unit_float(self.minimum_holdout_ari, "minimum_holdout_ari")
        )
        minimum_first_shell_f1 = _unit_float(
            self.minimum_first_shell_f1,
            "minimum_first_shell_f1",
        )
        object.__setattr__(self, "parameter_names", parameter_names)
        object.__setattr__(self, "minimum_stability_ari", minimum_stability_ari)
        object.__setattr__(self, "minimum_holdout_ari", minimum_holdout_ari)
        object.__setattr__(
            self,
            "minimum_first_shell_f1",
            minimum_first_shell_f1,
        )


@dataclass(frozen=True)
class LatticeDomainCalibrationVariant:
    variant_id: str
    phase: Literal["baseline", "one_at_a_time", "multivariate", "stability"]
    settings: MolecularM6OrientationAnalysisSettings
    changed_parameters: tuple[str, ...]

    def __post_init__(self) -> None:
        variant_id = _normalized_string(self.variant_id, "variant_id")
        if self.phase not in {
            "baseline",
            "one_at_a_time",
            "multivariate",
            "stability",
        }:
            raise ValueError("Unsupported calibration variant phase.")
        if not isinstance(self.settings, MolecularM6OrientationAnalysisSettings):
            raise TypeError("settings must be M6 settings.")
        changed = _normalized_string_tuple(
            self.changed_parameters,
            "changed_parameters",
        )
        if any(value not in LATTICE_DOMAIN_CALIBRATION_PARAMETER_NAMES for value in changed):
            raise ValueError("changed_parameters contains an unsupported parameter.")
        object.__setattr__(self, "variant_id", variant_id)
        object.__setattr__(self, "changed_parameters", changed)


@dataclass(frozen=True)
class LatticeDomainCalibrationAggregateMetrics:
    frame_count: int
    evaluated_molecule_count: int
    mean_adjusted_rand_index: float
    mean_variation_of_information_nats: float
    mean_absolute_domain_count_error: float
    mean_correctly_assigned_molecule_fraction: float
    boundary_precision: float | None
    boundary_recall: float | None
    mean_confidence_brier_score: float | None
    mean_confidence_expected_calibration_error: float | None
    mean_partition_stability_ari: float | None
    over_segmentation_count: int
    under_segmentation_count: int


@dataclass(frozen=True)
class LatticeDomainCalibrationVariantResult:
    variant: LatticeDomainCalibrationVariant
    metrics: LatticeDomainCalibrationAggregateMetrics
    score: float


@dataclass(frozen=True)
class LatticeDomainCalibrationQualityImpact:
    quality_tag: str
    split: LatticeDomainCalibrationSplit
    tagged_metrics: LatticeDomainCalibrationAggregateMetrics | None
    control_metrics: LatticeDomainCalibrationAggregateMetrics | None
    mean_adjusted_rand_index_delta: float | None


@dataclass(frozen=True)
class LatticeDomainCalibrationFirstShellValidation:
    symmetry_class: Literal["trifold", "sixfold"]
    split: Literal["calibration", "holdout", "all"]
    first_shell_r_min_nm: float
    first_shell_r_max_nm: float
    status: Literal["available", "missing_manual_neighbors"]
    reference_edge_count: int
    predicted_edge_count: int
    true_positive_edge_count: int
    precision: float | None
    recall: float | None
    f1_score: float | None


@dataclass(frozen=True)
class LatticeDomainCalibrationPrediction:
    labels: LatticeDomainPartitionLabels
    first_shell_neighbor_pairs: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.labels, LatticeDomainPartitionLabels):
            raise TypeError("labels must be LatticeDomainPartitionLabels.")
        pairs = tuple(
            _canonical_neighbor_pair(value, "first_shell_neighbor_pairs")
            for value in self.first_shell_neighbor_pairs
        )
        if len(set(pairs)) != len(pairs):
            raise ValueError("first_shell_neighbor_pairs must not contain duplicates.")
        unknown_source_ids = {
            source_id
            for pair in pairs
            for source_id in pair
            if source_id not in self.labels.source_ids
        }
        if unknown_source_ids:
            raise ValueError(
                "Predicted first-shell pairs contain unknown source IDs: "
                + ", ".join(sorted(unknown_source_ids))
            )
        object.__setattr__(self, "first_shell_neighbor_pairs", pairs)


@dataclass(frozen=True)
class LatticeDomainCalibrationSkippedVariant:
    variant_id: str
    changed_parameters: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "variant_id",
            _normalized_string(self.variant_id, "variant_id"),
        )
        object.__setattr__(
            self,
            "changed_parameters",
            _normalized_string_tuple(
                self.changed_parameters,
                "changed_parameters",
            ),
        )
        object.__setattr__(
            self,
            "reason",
            _normalized_string(self.reason, "reason"),
        )


@dataclass(frozen=True)
class LatticeDomainCalibrationStableRange:
    parameter_name: str
    minimum_value: float | int
    maximum_value: float | int
    accepted_variant_ids: tuple[str, ...]


@dataclass(frozen=True)
class LatticeDomainCalibrationProgress:
    phase: LatticeDomainCalibrationPhase
    completed_evaluations: int
    total_evaluations: int
    variant_id: str
    frame_index: int


@dataclass(frozen=True)
class LatticeDomainCalibrationReport:
    status: LatticeDomainCalibrationStatus
    reference_dataset_id: str
    reference_dataset_fingerprint: str
    source_file_name: str
    source_frame_count: int
    source_sample_fingerprint: str
    source_view: str
    use_segmentation_centroids: bool
    baseline_settings: MolecularM6OrientationAnalysisSettings
    selected_settings: MolecularM6OrientationAnalysisSettings | None
    best_variant_id: str | None
    calibration_frame_indices: tuple[int, ...]
    holdout_frame_indices: tuple[int, ...]
    variant_results: tuple[LatticeDomainCalibrationVariantResult, ...]
    skipped_variants: tuple[LatticeDomainCalibrationSkippedVariant, ...]
    holdout_metrics: LatticeDomainCalibrationAggregateMetrics | None
    holdout_passed: bool | None
    quality_impacts: tuple[LatticeDomainCalibrationQualityImpact, ...]
    first_shell_validation: tuple[LatticeDomainCalibrationFirstShellValidation, ...]
    first_shell_validation_passed: bool
    stable_ranges: tuple[LatticeDomainCalibrationStableRange, ...]
    indeterminate_parameters: tuple[str, ...]
    algorithm_versions: tuple[tuple[str, str], ...]
    preset_modified: bool = False
    uses_tracking: bool = False
    schema_version: int = LATTICE_DOMAIN_CALIBRATION_SCHEMA_VERSION


def save_lattice_domain_calibration_reference(
    reference: LatticeDomainCalibrationReferenceDataset,
    path: str | Path,
) -> Path:
    if not isinstance(reference, LatticeDomainCalibrationReferenceDataset):
        raise TypeError("reference must be a calibration reference dataset.")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(reference.to_dict(), indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    return destination


def load_lattice_domain_calibration_reference(
    path: str | Path,
) -> LatticeDomainCalibrationReferenceDataset:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise TypeError("Calibration reference root must be an object.")
    return LatticeDomainCalibrationReferenceDataset.from_dict(payload)


def _partition_to_dict(labels: LatticeDomainPartitionLabels) -> dict[str, object]:
    return {
        "source_ids": list(labels.source_ids),
        "domain_labels": list(labels.domain_labels),
        "boundary": list(labels.boundary),
        "confidence": list(labels.confidence),
    }


def _partition_from_dict(payload: Mapping[str, object]) -> LatticeDomainPartitionLabels:
    _require_exact_fields(
        payload,
        {"source_ids", "domain_labels", "boundary", "confidence"},
        "partition labels",
    )
    source_ids = _string_tuple(payload["source_ids"], "source_ids")
    raw_labels = payload["domain_labels"]
    raw_boundary = payload["boundary"]
    raw_confidence = payload["confidence"]
    if not isinstance(raw_labels, (list, tuple)):
        raise TypeError("domain_labels must be an array.")
    if not isinstance(raw_boundary, (list, tuple)):
        raise TypeError("boundary must be an array.")
    if not isinstance(raw_confidence, (list, tuple)):
        raise TypeError("confidence must be an array.")
    return LatticeDomainPartitionLabels(
        source_ids=source_ids,
        domain_labels=tuple(
            None if value is None else _string(value, "domain label")
            for value in raw_labels
        ),
        boundary=tuple(_boolean(value, "boundary value") for value in raw_boundary),
        confidence=tuple(
            None if value is None else _unit_float(value, "confidence value")
            for value in raw_confidence
        ),
    )


def _require_exact_fields(
    payload: Mapping[str, object],
    expected: set[str],
    label: str,
) -> None:
    actual = set(payload)
    if actual != expected:
        missing = sorted(expected.difference(actual))
        extra = sorted(actual.difference(expected))
        detail = []
        if missing:
            detail.append(f"missing {', '.join(missing)}")
        if extra:
            detail.append(f"unknown {', '.join(extra)}")
        raise ValueError(f"Invalid {label} fields: {'; '.join(detail)}.")


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{field_name} must be an array.")
    return tuple(_string(item, f"{field_name} value") for item in value)


def _neighbor_pairs(
    value: object,
    field_name: str,
) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{field_name} must be an array.")
    return tuple(_canonical_neighbor_pair(item, field_name) for item in value)


def _canonical_neighbor_pair(value: object, field_name: str) -> tuple[str, str]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise TypeError(f"Every {field_name} value must contain two source IDs.")
    left = _normalized_string(value[0], f"{field_name} source ID")
    right = _normalized_string(value[1], f"{field_name} source ID")
    if left == right:
        raise ValueError(f"{field_name} must not contain self-edges.")
    return tuple(sorted((left, right)))


def _string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    return value


def _normalized_string(value: object, field_name: str) -> str:
    normalized = _string(value, field_name).strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized


def _normalized_string_tuple(
    value: object,
    field_name: str,
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{field_name} must be an array.")
    return tuple(
        _normalized_string(item, f"{field_name} value")
        for item in value
    )


def _boolean(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} must be a boolean.")
    return value


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    return value


def _unit_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric.")
    normalized = float(value)
    if not isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must lie between 0 and 1.")
    return normalized
