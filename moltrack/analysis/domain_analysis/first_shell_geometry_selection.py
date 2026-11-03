from __future__ import annotations

from dataclasses import dataclass

from ._m6_preset_values import mapping, sequence, text


FIRST_SHELL_GEOMETRY_SELECTION_SCHEMA_VERSION = (
    "frozen-first-shell-geometry-selection-v1"
)


@dataclass(frozen=True)
class FirstShellGeometrySelectionRecord:
    """Persisted Calibration evidence anchoring an operator-selected policy."""

    dataset_version_id: str
    dataset_version_fingerprint: str
    validation_epoch_id: str
    experiment_fingerprint: str
    geometry_fingerprint: str
    policy_fingerprint: str
    policy_result_fingerprint: str
    evidence_fingerprints: tuple[tuple[str, str, str], ...]
    schema_version: str = FIRST_SHELL_GEOMETRY_SELECTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for field_name in (
            "dataset_version_id",
            "dataset_version_fingerprint",
            "validation_epoch_id",
            "experiment_fingerprint",
            "geometry_fingerprint",
            "policy_fingerprint",
            "policy_result_fingerprint",
        ):
            object.__setattr__(
                self,
                field_name,
                text(getattr(self, field_name), field_name),
            )
        evidence = tuple(sorted(
            (
                text(group_id, "measurement_group_id"),
                text(symmetry, "symmetry_class"),
                text(fingerprint, "evidence_fingerprint"),
            )
            for group_id, symmetry, fingerprint in self.evidence_fingerprints
        ))
        if not evidence or any(
            value[1] not in {"trifold", "sixfold"} for value in evidence
        ):
            raise ValueError("evidence_fingerprints require trifold/sixfold evidence.")
        if len({value[:2] for value in evidence}) != len(evidence):
            raise ValueError("evidence_fingerprints identities must be unique.")
        if self.schema_version != FIRST_SHELL_GEOMETRY_SELECTION_SCHEMA_VERSION:
            raise ValueError("Unsupported first-shell geometry selection schema.")
        object.__setattr__(self, "evidence_fingerprints", evidence)

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "dataset_version_id": self.dataset_version_id,
            "dataset_version_fingerprint": self.dataset_version_fingerprint,
            "validation_epoch_id": self.validation_epoch_id,
            "experiment_fingerprint": self.experiment_fingerprint,
            "geometry_fingerprint": self.geometry_fingerprint,
            "policy_fingerprint": self.policy_fingerprint,
            "policy_result_fingerprint": self.policy_result_fingerprint,
            "evidence_fingerprints": [
                list(value) for value in self.evidence_fingerprints
            ],
        }

    @classmethod
    def from_payload(cls, payload: object) -> FirstShellGeometrySelectionRecord:
        saved = mapping(payload, "first_shell_geometry_selection")
        evidence: list[tuple[str, str, str]] = []
        for value in sequence(saved.get("evidence_fingerprints")):
            fields = sequence(value)
            if len(fields) != 3:
                raise ValueError("Each evidence fingerprint requires three fields.")
            evidence.append((
                text(fields[0], "measurement_group_id"),
                text(fields[1], "symmetry_class"),
                text(fields[2], "evidence_fingerprint"),
            ))
        return cls(
            dataset_version_id=text(
                saved.get("dataset_version_id"), "dataset_version_id"
            ),
            dataset_version_fingerprint=text(
                saved.get("dataset_version_fingerprint"),
                "dataset_version_fingerprint",
            ),
            validation_epoch_id=text(
                saved.get("validation_epoch_id"), "validation_epoch_id"
            ),
            experiment_fingerprint=text(
                saved.get("experiment_fingerprint"), "experiment_fingerprint"
            ),
            geometry_fingerprint=text(
                saved.get("geometry_fingerprint"), "geometry_fingerprint"
            ),
            policy_fingerprint=text(
                saved.get("policy_fingerprint"), "policy_fingerprint"
            ),
            policy_result_fingerprint=text(
                saved.get("policy_result_fingerprint"),
                "policy_result_fingerprint",
            ),
            evidence_fingerprints=tuple(evidence),
            schema_version=text(saved.get("schema_version"), "schema_version"),
        )
