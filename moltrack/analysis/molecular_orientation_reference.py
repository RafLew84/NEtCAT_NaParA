"""Manual reference labels for per-molecule orientation estimators."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Literal, Mapping

from ._molecular_orientation_contract import (
    non_empty_string as _non_empty_string,
    optional_non_empty_string as _optional_non_empty_string,
    optional_strict_string as _optional_string,
    require_exact_fields as _require_exact_fields,
    sha256_digest as _sha256,
    strict_boolean as _boolean,
    strict_integer as _integer,
    strict_string as _string,
    supported_string as _supported_string,
)
from .molecular_orientation_models import (
    MOLECULAR_ORIENTATION_SCHEMA_VERSION,
    MolecularOrientationMeasurement,
)


MolecularOrientationReferenceSplit = Literal["development", "holdout"]
MolecularOrientationLatticeSymmetry = Literal[
    "trifold",
    "sixfold",
    "mixed",
    "unknown",
]
MolecularOrientationLatticeRotation = Literal[
    "reference",
    "rotated",
    "unknown",
]
MolecularOrientationStacking = Literal[
    "abab",
    "uniform",
    "mixed",
    "unknown",
]

_SPLITS = {"development", "holdout"}
_LATTICE_SYMMETRIES = {"trifold", "sixfold", "mixed", "unknown"}
_LATTICE_ROTATIONS = {"reference", "rotated", "unknown"}
_STACKING_LABELS = {"abab", "uniform", "mixed", "unknown"}


@dataclass(frozen=True)
class MolecularOrientationDomainContext:
    """Domain labels kept independent from the molecule's orientation angle."""

    domain_id: str | None
    lattice_symmetry: MolecularOrientationLatticeSymmetry
    lattice_rotation: MolecularOrientationLatticeRotation
    stacking: MolecularOrientationStacking

    def __post_init__(self) -> None:
        domain_id = _optional_non_empty_string(self.domain_id, "domain_id")
        lattice_symmetry = _supported_string(
            self.lattice_symmetry,
            _LATTICE_SYMMETRIES,
            "lattice_symmetry",
        )
        lattice_rotation = _supported_string(
            self.lattice_rotation,
            _LATTICE_ROTATIONS,
            "lattice_rotation",
        )
        stacking = _supported_string(
            self.stacking,
            _STACKING_LABELS,
            "stacking",
        )
        object.__setattr__(self, "domain_id", domain_id)
        object.__setattr__(self, "lattice_symmetry", lattice_symmetry)
        object.__setattr__(self, "lattice_rotation", lattice_rotation)
        object.__setattr__(self, "stacking", stacking)

    def to_dict(self) -> dict[str, object]:
        return {
            "domain_id": self.domain_id,
            "lattice_symmetry": self.lattice_symmetry,
            "lattice_rotation": self.lattice_rotation,
            "stacking": self.stacking,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "MolecularOrientationDomainContext":
        _require_exact_fields(
            payload,
            {
                "domain_id",
                "lattice_symmetry",
                "lattice_rotation",
                "stacking",
            },
            "molecular orientation domain context",
        )
        return cls(
            domain_id=_optional_string(payload["domain_id"], "domain_id"),
            lattice_symmetry=_string(
                payload["lattice_symmetry"],
                "lattice_symmetry",
            ),
            lattice_rotation=_string(
                payload["lattice_rotation"],
                "lattice_rotation",
            ),
            stacking=_string(payload["stacking"], "stacking"),
        )


@dataclass(frozen=True)
class MolecularOrientationReferenceSample:
    """One manually labelled molecule and its independent domain context."""

    sample_id: str
    split: MolecularOrientationReferenceSplit
    measurement: MolecularOrientationMeasurement
    domain_context: MolecularOrientationDomainContext

    def __post_init__(self) -> None:
        sample_id = _non_empty_string(self.sample_id, "sample_id")
        split = _supported_string(self.split, _SPLITS, "split")
        if not isinstance(self.measurement, MolecularOrientationMeasurement):
            raise TypeError("measurement must be MolecularOrientationMeasurement.")
        if not isinstance(
            self.domain_context,
            MolecularOrientationDomainContext,
        ):
            raise TypeError(
                "domain_context must be MolecularOrientationDomainContext."
            )
        object.__setattr__(self, "sample_id", sample_id)
        object.__setattr__(self, "split", split)

    def to_dict(self) -> dict[str, object]:
        return {
            "sample_id": self.sample_id,
            "split": self.split,
            "measurement": self.measurement.to_dict(),
            "domain_context": self.domain_context.to_dict(),
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "MolecularOrientationReferenceSample":
        _require_exact_fields(
            payload,
            {"sample_id", "split", "measurement", "domain_context"},
            "molecular orientation reference sample",
        )
        measurement = payload["measurement"]
        domain_context = payload["domain_context"]
        if not isinstance(measurement, Mapping):
            raise TypeError("measurement must be an object.")
        if not isinstance(domain_context, Mapping):
            raise TypeError("domain_context must be an object.")
        return cls(
            sample_id=_string(payload["sample_id"], "sample_id"),
            split=_string(payload["split"], "split"),
            measurement=MolecularOrientationMeasurement.from_dict(measurement),
            domain_context=MolecularOrientationDomainContext.from_dict(
                domain_context
            ),
        )


@dataclass(frozen=True)
class MolecularOrientationReferenceDataset:
    """Versioned manual ground truth with a fixed development/holdout split."""

    dataset_id: str
    source_file_name: str
    source_file_sha256: str
    source_session_file_name: str | None
    source_session_sha256: str | None
    reviewed: bool
    reviewed_by: str | None
    samples: tuple[MolecularOrientationReferenceSample, ...]
    schema_version: int = MOLECULAR_ORIENTATION_SCHEMA_VERSION
    uses_tracking: bool = False

    def __post_init__(self) -> None:
        dataset_id = _non_empty_string(self.dataset_id, "dataset_id")
        source_file_name = _non_empty_string(
            self.source_file_name,
            "source_file_name",
        )
        source_file_sha256 = _sha256(
            self.source_file_sha256,
            "source_file_sha256",
        )
        source_session_file_name = _optional_non_empty_string(
            self.source_session_file_name,
            "source_session_file_name",
        )
        source_session_sha256 = (
            None
            if self.source_session_sha256 is None
            else _sha256(
                self.source_session_sha256,
                "source_session_sha256",
            )
        )
        if (source_session_file_name is None) != (
            source_session_sha256 is None
        ):
            raise ValueError(
                "source_session_file_name and source_session_sha256 must be "
                "provided together."
            )
        if not isinstance(self.reviewed, bool):
            raise TypeError("reviewed must be a boolean.")
        reviewed_by = _optional_non_empty_string(
            self.reviewed_by,
            "reviewed_by",
        )
        if self.reviewed != (reviewed_by is not None):
            raise ValueError(
                "reviewed_by must be present exactly when reviewed is true."
            )
        samples = tuple(self.samples)
        if not samples or any(
            not isinstance(value, MolecularOrientationReferenceSample)
            for value in samples
        ):
            raise ValueError("samples must contain reference samples.")
        if len({value.sample_id for value in samples}) != len(samples):
            raise ValueError("Reference sample_id values must be unique.")
        if len(
            {value.measurement.measurement_id for value in samples}
        ) != len(samples):
            raise ValueError("Reference measurement_id values must be unique.")
        source_keys = tuple(
            (
                value.measurement.provenance.frame_index,
                value.measurement.provenance.source_view,
                value.measurement.provenance.source_kind,
                value.measurement.provenance.source_id,
            )
            for value in samples
        )
        if len(set(source_keys)) != len(source_keys):
            raise ValueError("Reference samples must identify unique molecules.")
        if {value.split for value in samples} != {"development", "holdout"}:
            raise ValueError(
                "Reference dataset requires development and holdout samples."
            )
        for sample in samples:
            provenance = sample.measurement.provenance
            if (
                provenance.source_file_name != source_file_name
                or provenance.source_file_sha256 != source_file_sha256
                or provenance.source_session_file_name
                != source_session_file_name
                or provenance.source_session_sha256
                != source_session_sha256
            ):
                raise ValueError(
                    "Sample provenance must match reference dataset sources."
                )
            if self.reviewed and sample.measurement.method not in {
                "manual",
                "manual_correction",
            }:
                raise ValueError(
                    "Reviewed ground truth must contain manual measurements."
                )
        schema_version = _integer(self.schema_version, "schema_version")
        if schema_version != MOLECULAR_ORIENTATION_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported molecular orientation reference schema version."
            )
        if self.uses_tracking is not False:
            raise ValueError("Molecular orientation reference must not use tracking.")
        object.__setattr__(self, "dataset_id", dataset_id)
        object.__setattr__(self, "source_file_name", source_file_name)
        object.__setattr__(self, "source_file_sha256", source_file_sha256)
        object.__setattr__(
            self,
            "source_session_file_name",
            source_session_file_name,
        )
        object.__setattr__(
            self,
            "source_session_sha256",
            source_session_sha256,
        )
        object.__setattr__(self, "reviewed_by", reviewed_by)
        object.__setattr__(self, "samples", samples)
        object.__setattr__(self, "schema_version", schema_version)

    @property
    def has_required_ttmapp_contexts(self) -> bool:
        return (
            any(
                value.domain_context.lattice_symmetry == "trifold"
                for value in self.samples
            )
            and any(
                value.domain_context.lattice_rotation == "rotated"
                for value in self.samples
            )
            and any(
                value.domain_context.stacking == "abab"
                for value in self.samples
            )
        )

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
            "source_file_sha256": self.source_file_sha256,
            "source_session_file_name": self.source_session_file_name,
            "source_session_sha256": self.source_session_sha256,
            "reviewed": self.reviewed,
            "reviewed_by": self.reviewed_by,
            "uses_tracking": self.uses_tracking,
            "samples": [value.to_dict() for value in self.samples],
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "MolecularOrientationReferenceDataset":
        _require_exact_fields(
            payload,
            {
                "schema_version",
                "dataset_id",
                "source_file_name",
                "source_file_sha256",
                "source_session_file_name",
                "source_session_sha256",
                "reviewed",
                "reviewed_by",
                "uses_tracking",
                "samples",
            },
            "molecular orientation reference dataset",
        )
        raw_samples = payload["samples"]
        if not isinstance(raw_samples, (list, tuple)):
            raise TypeError("samples must be an array.")
        samples = []
        for value in raw_samples:
            if not isinstance(value, Mapping):
                raise TypeError("Every reference sample must be an object.")
            samples.append(MolecularOrientationReferenceSample.from_dict(value))
        return cls(
            schema_version=_integer(payload["schema_version"], "schema_version"),
            dataset_id=_string(payload["dataset_id"], "dataset_id"),
            source_file_name=_string(
                payload["source_file_name"],
                "source_file_name",
            ),
            source_file_sha256=_string(
                payload["source_file_sha256"],
                "source_file_sha256",
            ),
            source_session_file_name=_optional_string(
                payload["source_session_file_name"],
                "source_session_file_name",
            ),
            source_session_sha256=_optional_string(
                payload["source_session_sha256"],
                "source_session_sha256",
            ),
            reviewed=_boolean(payload["reviewed"], "reviewed"),
            reviewed_by=_optional_string(
                payload["reviewed_by"],
                "reviewed_by",
            ),
            uses_tracking=_boolean(payload["uses_tracking"], "uses_tracking"),
            samples=tuple(samples),
        )


def save_molecular_orientation_reference(
    reference: MolecularOrientationReferenceDataset,
    path: str | Path,
) -> Path:
    if not isinstance(reference, MolecularOrientationReferenceDataset):
        raise TypeError("reference must be a molecular orientation dataset.")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            reference.to_dict(),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination


def load_molecular_orientation_reference(
    path: str | Path,
) -> MolecularOrientationReferenceDataset:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise TypeError("Molecular orientation reference root must be an object.")
    return MolecularOrientationReferenceDataset.from_dict(payload)
