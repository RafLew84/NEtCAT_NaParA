from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any

from moltrack.analysis.domain_analysis import (
    DomainAnalysisPublication,
    DomainCorrectionWorkspace,
    EffectiveDomainProjection,
)
from moltrack.analysis.domain_analysis.correction_rebase_models import (
    automatic_candidate_fingerprint,
)
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256
from moltrack.analysis.domain_analysis.diagnostic_funnel import (
    build_molecule_diagnostic_funnels,
)

from .domain_analysis_payload_validation import json_compatible_value


EFFECTIVE_PROJECTION_CHECKPOINT_SCHEMA_VERSION = 1


def effective_projection_checkpoint(
    publication: DomainAnalysisPublication,
    correction_set: DomainCorrectionWorkspace,
    projection: EffectiveDomainProjection,
) -> dict[str, Any]:
    body = {
        "schema_version": EFFECTIVE_PROJECTION_CHECKPOINT_SCHEMA_VERSION,
        "automatic_snapshot_fingerprint": automatic_candidate_fingerprint(
            publication.request,
            replace(
                publication.result,
                molecule_diagnostic_funnels=build_molecule_diagnostic_funnels(
                    publication.result
                ),
            ),
        ),
        "correction_anchor_fingerprint": correction_set.automatic_fingerprint,
        "correction_revision": correction_set.revision,
        "projection": _projection_payload(projection),
    }
    return {**body, "fingerprint": canonical_sha256(body)}


def validate_effective_projection_checkpoint(
    payload: Any,
    publication: DomainAnalysisPublication,
    correction_set: DomainCorrectionWorkspace,
    projection: EffectiveDomainProjection,
) -> None:
    if not isinstance(payload, dict):
        raise ValueError(
            "domain_analysis.correction_workspace.effective_projection_checkpoint "
            "must be an object."
        )
    expected = effective_projection_checkpoint(
        publication,
        correction_set,
        projection,
    )
    if payload != expected:
        raise ValueError(
            "Effective Projection Checkpoint does not match the projection "
            "recomputed from its automatic snapshot and correction history."
        )


def _projection_payload(projection: EffectiveDomainProjection) -> dict[str, Any]:
    return json_compatible_value({
        "molecules": [asdict(value) for value in projection.molecules],
        "orientation_subdomains": [
            asdict(value) for value in projection.orientation_subdomains
        ],
        "domains": [asdict(value) for value in projection.domains],
    })


__all__ = [
    "EFFECTIVE_PROJECTION_CHECKPOINT_SCHEMA_VERSION",
    "effective_projection_checkpoint",
    "validate_effective_projection_checkpoint",
]
