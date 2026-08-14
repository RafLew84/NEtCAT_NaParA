from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from moltrack.analysis.domain_analysis import (
    DomainAnalysisPublication,
    DomainCorrectionWorkspace,
    EffectiveDomainProjection,
    EffectiveM6Domain,
    EffectiveMoleculeOrientation,
)
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256


@dataclass(frozen=True)
class M6ReferenceStateIdentity:
    automatic_snapshot_fingerprint: str
    effective_projection_fingerprint: str
    correction_revision: int


def m6_reference_state_identity(
    publication: DomainAnalysisPublication,
    corrections: DomainCorrectionWorkspace,
    projection: EffectiveDomainProjection,
) -> M6ReferenceStateIdentity:
    gate = publication.result.m6_gate
    if gate is None:
        raise ValueError("M6 reference identity requires a published M6 gate.")
    automatic_fingerprint = _automatic_snapshot_fingerprint(publication)
    correction_revision = corrections.review_revision("m6")
    effective_fingerprint = _effective_projection_fingerprint(
        automatic_fingerprint,
        correction_revision,
        projection,
    )
    return M6ReferenceStateIdentity(
        automatic_snapshot_fingerprint=automatic_fingerprint,
        effective_projection_fingerprint=effective_fingerprint,
        correction_revision=correction_revision,
    )


def _automatic_snapshot_fingerprint(
    publication: DomainAnalysisPublication,
) -> str:
    gate = publication.result.m6_gate
    assert gate is not None
    return canonical_sha256({
        "schema_version": "m6-reference-automatic-snapshot-v1",
        "frames": [
            {
                "physical_frame_id": frame.physical_frame_id,
                "m6_gate_fingerprint": frame.m6_gate_fingerprint,
            }
            for frame in gate.frames
        ],
    })


def _effective_projection_fingerprint(
    automatic_fingerprint: str,
    correction_revision: int,
    projection: EffectiveDomainProjection,
) -> str:
    return canonical_sha256({
        "schema_version": "m6-reference-effective-projection-v1",
        "automatic_snapshot_fingerprint": automatic_fingerprint,
        "m6_correction_revision": correction_revision,
        "molecules": [
            _m6_molecule_state(value)
            for value in sorted(
                projection.molecules,
                key=lambda item: (item.physical_frame_id, item.source_id),
            )
        ],
        "domains": [
            _m6_domain_state(value)
            for value in sorted(
                projection.domains,
                key=lambda item: (
                    item.physical_frame_id,
                    item.lattice_domain_id,
                ),
            )
        ],
    })


def _m6_molecule_state(
    molecule: EffectiveMoleculeOrientation,
) -> dict[str, Any]:
    return {
        "physical_frame_id": molecule.physical_frame_id,
        "source_id": molecule.source_id,
        "m6_partition": molecule.m6_partition,
        "effective_domain_id": molecule.effective_domain_id,
        "is_boundary": molecule.is_boundary,
        "footprint_pixels_xy": molecule.footprint_pixels_xy,
    }


def _m6_domain_state(domain: EffectiveM6Domain) -> dict[str, Any]:
    return {
        "physical_frame_id": domain.physical_frame_id,
        "lattice_domain_id": domain.lattice_domain_id,
        "domain_kind": domain.domain_kind,
        "is_tombstone": domain.is_tombstone,
        "source_ids": domain.source_ids,
        "molecule_count": domain.molecule_count,
        "centroid_xy_nm": domain.centroid_xy_nm,
        "bounds_xyxy_nm": domain.bounds_xyxy_nm,
        "footprint_pixels_xy": domain.footprint_pixels_xy,
        "footprint_area_nm2": domain.footprint_area_nm2,
        "boundary_source_ids": domain.boundary_source_ids,
    }


__all__ = ["M6ReferenceStateIdentity", "m6_reference_state_identity"]
