from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from moltrack.analysis.domain_analysis import (
    DetectionIdentity,
    DomainAnalysisPublication,
    DomainCorrectionWorkspace,
    EffectiveDomainProjection,
    EffectiveMoleculeOrientation,
)
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256

from .domain_analysis_payload_validation import json_compatible_value


@dataclass(frozen=True)
class OrientationReferenceStateIdentity:
    automatic_snapshot_fingerprint: str
    effective_projection_fingerprint: str
    correction_revision: int


def orientation_reference_state_identity(
    publication: DomainAnalysisPublication,
    corrections: DomainCorrectionWorkspace,
    projection: EffectiveDomainProjection,
) -> OrientationReferenceStateIdentity:
    gate = publication.result.m6_gate
    if gate is None:
        raise ValueError("Orientation reference identity requires analyzed frames.")
    automatic_fingerprint = canonical_sha256({
        "schema_version": "orientation-reference-automatic-snapshot-v1",
        "classifier_status": publication.result.classifier_status,
        "classifier_outcomes": [
            json_compatible_value(asdict(value))
            for value in (publication.result.classifier_outcomes or ())
        ],
    })
    correction_revision = corrections.review_revision("orientation")
    effective_fingerprint = canonical_sha256({
        "schema_version": "orientation-reference-effective-projection-v1",
        "automatic_snapshot_fingerprint": automatic_fingerprint,
        "orientation_correction_revision": correction_revision,
        "molecules": [
            _effective_orientation_state(value)
            for value in sorted(
                projection.molecules,
                key=lambda item: DetectionIdentity(
                    physical_frame_id=item.physical_frame_id,
                    source_id=item.source_id,
                ),
            )
        ],
    })
    return OrientationReferenceStateIdentity(
        automatic_fingerprint,
        effective_fingerprint,
        correction_revision,
    )


def _effective_orientation_state(
    molecule: EffectiveMoleculeOrientation,
) -> dict[str, Any]:
    return {
        "physical_frame_id": molecule.physical_frame_id,
        "source_id": molecule.source_id,
        "manual_decision": (
            None
            if molecule.manual_decision is None
            else asdict(molecule.manual_decision)
        ),
        "effective_orientation": molecule.effective_orientation,
        "effective_orientation_source": molecule.effective_orientation_source,
        "effective_confidence": molecule.effective_confidence,
    }


__all__ = [
    "OrientationReferenceStateIdentity",
    "orientation_reference_state_identity",
]
