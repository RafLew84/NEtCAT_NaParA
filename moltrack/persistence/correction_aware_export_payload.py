from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from moltrack.analysis.domain_analysis import (
    DomainAnalysisSessionState,
    EffectiveMoleculeOrientation,
    M6FrameGate,
    ReferenceReviewDecision,
)
from moltrack.analysis.domain_analysis.correction_rebase_models import (
    automatic_candidate_fingerprint,
)
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256

from .correction_aware_export_schema import (
    AUTOMATIC_SNAPSHOT_FILE,
    CORRECTION_OPERATIONS_FILE,
    CORRECTION_REVISIONS_FILE,
    CORRECTION_STATE_FILE,
    DIAGNOSTIC_FUNNELS_FILE,
    EFFECTIVE_PROJECTION_FILE,
    ORIENTATION_CLASS_CATALOG_FILE,
    QUARANTINE_FILE,
    REBASE_DIAGNOSTICS_FILE,
    REFERENCE_REVIEWS_FILE,
    CorrectionAwareActivationStatus,
    CorrectionAwareCorrectionStatus,
    CorrectionAwareExportSettings,
)
from .correction_aware_draft_export import inactive_draft_export_parts
from .domain_analysis_session import domain_analysis_state_to_payload
from .correction_workspace_quarantine_payload import (
    correction_workspace_quarantine_to_payload,
)
from .domain_backend_payload import backend_identity_to_payload
from .package_io import csv_json_cell


@dataclass(frozen=True)
class CorrectionAwarePackagePayload:
    activation_status: CorrectionAwareActivationStatus
    correction_status: CorrectionAwareCorrectionStatus
    readiness: dict[str, Any]
    anchors: dict[str, Any]
    json_documents: dict[str, Any]
    json_lines: dict[str, list[dict[str, Any]]]
    molecule_rows: list[dict[str, Any]]


def correction_aware_package_payload(
    state: DomainAnalysisSessionState,
    settings: CorrectionAwareExportSettings,
) -> CorrectionAwarePackagePayload:
    if not isinstance(state, DomainAnalysisSessionState):
        raise TypeError("snapshot must be a DomainAnalysisSessionState instance.")
    if state.published_result is not None:
        return _active_payload(state, settings)
    if state.correction_workspace_quarantine is not None:
        return _quarantined_payload(state, settings)
    return _inactive_draft_payload(state, settings)


def _active_payload(
    state: DomainAnalysisSessionState,
    settings: CorrectionAwareExportSettings,
) -> CorrectionAwarePackagePayload:
    section = domain_analysis_state_to_payload(state)
    automatic = section["published_result"]
    workspace = section["correction_workspace"]
    correction = workspace["active_correction_set"]
    projection = workspace["effective_projection_checkpoint"]
    assert isinstance(automatic, dict)
    assert isinstance(workspace, dict)
    assert isinstance(correction, dict)
    assert isinstance(projection, dict)
    readiness = _export_readiness(state, workspace["readiness"])
    status = _correction_status(state, readiness)
    _enforce_policy(settings, readiness, status)
    molecule_rows = _effective_molecule_rows(state, projection)
    documents = {
        AUTOMATIC_SNAPSHOT_FILE: automatic,
        ORIENTATION_CLASS_CATALOG_FILE: workspace[
            "orientation_class_catalog"
        ],
        CORRECTION_STATE_FILE: correction,
        EFFECTIVE_PROJECTION_FILE: projection,
        REFERENCE_REVIEWS_FILE: workspace["reviews"],
        DIAGNOSTIC_FUNNELS_FILE: workspace["diagnostic_funnels"],
        REBASE_DIAGNOSTICS_FILE: _rebase_diagnostics(workspace),
    }
    if (
        settings.export_mode == "audit"
        and state.correction_workspace_quarantine is not None
    ):
        documents[QUARANTINE_FILE] = correction_workspace_quarantine_to_payload(
            state.correction_workspace_quarantine
        )
    return CorrectionAwarePackagePayload(
        activation_status="active",
        correction_status=status,
        readiness=readiness,
        anchors=_active_anchors(state, workspace, correction, projection),
        json_documents=documents,
        json_lines={
            CORRECTION_REVISIONS_FILE: _revision_rows(correction),
            CORRECTION_OPERATIONS_FILE: list(correction["atoms"]),
        },
        molecule_rows=molecule_rows,
    )


def _inactive_draft_payload(
    state: DomainAnalysisSessionState,
    settings: CorrectionAwareExportSettings,
) -> CorrectionAwarePackagePayload:
    readiness = {
        "ready": False,
        "blockers": ["no_active_automatic_snapshot"],
    }
    _enforce_policy(settings, readiness, "draft")
    anchors, documents = inactive_draft_export_parts(state)
    return CorrectionAwarePackagePayload(
        activation_status="inactive",
        correction_status="draft",
        readiness=readiness,
        anchors=anchors,
        json_documents=documents,
        json_lines={
            CORRECTION_REVISIONS_FILE: [],
            CORRECTION_OPERATIONS_FILE: [],
        },
        molecule_rows=[],
    )


def _quarantined_payload(
    state: DomainAnalysisSessionState,
    settings: CorrectionAwareExportSettings,
) -> CorrectionAwarePackagePayload:
    quarantine = state.correction_workspace_quarantine
    assert quarantine is not None
    readiness = {
        "ready": False,
        "blockers": [
            "correction_workspace_quarantined",
            quarantine.reason_code,
        ],
    }
    _enforce_policy(settings, readiness, "conflicted")
    automatic = quarantine.automatic_snapshot_payload
    correction = quarantine.correction_workspace_payload
    return CorrectionAwarePackagePayload(
        activation_status="quarantined",
        correction_status="conflicted",
        readiness=readiness,
        anchors=_quarantine_anchors(quarantine, automatic, correction),
        json_documents=_quarantine_documents(quarantine, automatic),
        json_lines={},
        molecule_rows=[],
    )


def _quarantine_anchors(
    quarantine: Any,
    automatic: Any,
    correction: Any,
) -> dict[str, Any]:
    return {
        "backend_identity_fingerprint": _backend_fingerprint(
            quarantine.automatic_snapshot
        ),
        "backend_identities": _backend_identities(quarantine.automatic_snapshot),
        "automatic_snapshot_fingerprint": _automatic_fingerprint(
            quarantine.automatic_snapshot
        ),
        "automatic_snapshot_audit_fingerprint": canonical_sha256(automatic),
        "orientation_class_catalog_fingerprint": None,
        "orientation_class_catalog_revision": None,
        "correction_revision": None,
        "correction_revision_fingerprint": None,
        "correction_workspace_audit_fingerprint": canonical_sha256(correction),
        "effective_projection_fingerprint": None,
    }


def _quarantine_documents(
    quarantine: Any,
    automatic: Any,
) -> dict[str, Any]:
    audit = correction_workspace_quarantine_to_payload(quarantine)
    assert audit is not None
    return {
        AUTOMATIC_SNAPSHOT_FILE: automatic,
        QUARANTINE_FILE: audit,
    }


def _export_readiness(
    state: DomainAnalysisSessionState,
    saved_readiness: Any,
) -> dict[str, Any]:
    blockers = list(saved_readiness["blockers"])
    if state.domain_corrections.prepared is not None:
        blockers.append("prepared_correction")
    return {"ready": not blockers, "blockers": blockers}


def _correction_status(
    state: DomainAnalysisSessionState,
    readiness: dict[str, Any],
) -> CorrectionAwareCorrectionStatus:
    corrections = state.domain_corrections
    if (
        corrections.prepared_rebase is not None
        and not corrections.prepared_rebase.is_ready
    ):
        return "conflicted"
    if corrections.pending_automatic_candidate is not None:
        return "stale"
    return "current" if readiness["ready"] else "draft"


def _enforce_policy(
    settings: CorrectionAwareExportSettings,
    readiness: dict[str, Any],
    correction_status: CorrectionAwareCorrectionStatus,
) -> None:
    if settings.export_mode == "reference" and not readiness["ready"]:
        blockers = ", ".join(readiness["blockers"])
        raise ValueError(
            "Correction-aware reference export requires reference-ready state; "
            f"blockers: {blockers}."
        )
    if settings.export_mode == "reference" and correction_status != "current":
        raise ValueError(
            "Correction-aware reference export requires a current correction state."
        )


def _active_anchors(
    state: DomainAnalysisSessionState,
    workspace: dict[str, Any],
    correction: dict[str, Any],
    projection: dict[str, Any],
) -> dict[str, Any]:
    return {
        "backend_identity_fingerprint": _backend_fingerprint(
            state.published_result
        ),
        "backend_identities": _backend_identities(state.published_result),
        "automatic_snapshot_fingerprint": projection[
            "automatic_snapshot_fingerprint"
        ],
        "orientation_class_catalog_fingerprint": canonical_sha256(
            workspace["orientation_class_catalog"]
        ),
        "orientation_class_catalog_revision": workspace[
            "orientation_class_catalog"
        ]["revision"],
        "correction_revision": correction["revision"],
        "correction_revision_fingerprint": canonical_sha256(correction),
        "effective_projection_fingerprint": projection["fingerprint"],
    }


def _backend_fingerprint(publication: Any) -> str | None:
    identities = _backend_identities(publication)
    if not identities:
        return None
    return canonical_sha256({
        "schema_version": "domain-backend-identities-v1",
        "identities": identities,
    })


def _backend_identities(publication: Any) -> list[dict[str, Any]]:
    if publication is None or publication.result.m6_gate is None:
        return []
    identities = {
        canonical_sha256(payload): payload
        for frame in publication.result.m6_gate.frames
        for payload in (backend_identity_to_payload(frame.backend_identity),)
    }
    return [identities[key] for key in sorted(identities)]


def _automatic_fingerprint(publication: Any) -> str | None:
    if publication is None:
        return None
    return automatic_candidate_fingerprint(
        publication.request,
        publication.result,
    )


def _revision_rows(correction: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"revision": index, **record}
        for index, record in enumerate(correction["history_records"], start=1)
    ]


def _rebase_diagnostics(workspace: dict[str, Any]) -> dict[str, Any]:
    return {
        "pending_rebase": workspace["pending_rebase"],
        "prepared_rebase": workspace["prepared_rebase"],
        "records": workspace["rebase_records"],
    }


def _effective_molecule_rows(
    state: DomainAnalysisSessionState,
    projection_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    publication = state.published_result
    projection = state.domain_corrections.effective_projection
    assert publication is not None and publication.result.m6_gate is not None
    assert projection is not None
    automatic = {
        key: value
        for frame in publication.result.m6_gate.frames
        for key, value in _automatic_assignments(frame).items()
    }
    reviews = _review_decisions(state)
    saved_molecules = {
        (value["physical_frame_id"], value["source_id"]): value
        for value in projection_payload["projection"]["molecules"]
    }
    effective_keys = {
        (value.physical_frame_id, value.source_id)
        for value in projection.molecules
    }
    expected_keys = set(automatic)
    if effective_keys != expected_keys or set(saved_molecules) != expected_keys:
        raise ValueError(
            "Effective projection must contain every frozen source_id exactly once."
        )
    rows = []
    for molecule in sorted(
        projection.molecules,
        key=lambda value: (value.physical_frame_id, value.source_id),
    ):
        key = (molecule.physical_frame_id, molecule.source_id)
        rows.append(_effective_molecule_row(
            molecule,
            automatic[key],
            saved_molecules[key],
            reviews,
        ))
    return rows


def _effective_molecule_row(
    molecule: EffectiveMoleculeOrientation,
    automatic: tuple[str, str | None, bool | None],
    saved: dict[str, Any],
    reviews: dict[tuple[str, str, str], ReferenceReviewDecision],
) -> dict[str, Any]:
    partition, domain_id, boundary = automatic
    classification = molecule.automatic_classification
    key = (molecule.physical_frame_id, molecule.source_id)
    row = {
        "physical_frame_id": key[0],
        "source_id": key[1],
        "automatic_m6_partition": partition,
        "automatic_domain_id": domain_id or "",
        "automatic_boundary": boundary,
        "automatic_orientation_raw": (
            "" if classification is None else classification.orientation_label or ""
        ),
        "automatic_orientation_status": (
            "" if classification is None else classification.classification_status
        ),
        "raw_automatic_evidence": csv_json_cell(saved["raw_orientation_evidence"]),
        "effective_m6_partition": molecule.m6_partition,
        "effective_domain_id": molecule.effective_domain_id or "",
        "effective_boundary": molecule.is_boundary,
        "effective_orientation": molecule.effective_orientation or "",
        "effective_orientation_source": molecule.effective_orientation_source,
        "effective_confidence": (
            "" if molecule.effective_confidence is None
            else molecule.effective_confidence
        ),
    }
    row.update(_review_columns("m6", reviews.get((key[0], "m6", key[1]))))
    row.update(_review_columns(
        "orientation",
        reviews.get((key[0], "orientation", key[1])),
    ))
    return row


def _automatic_assignments(
    frame: M6FrameGate,
) -> dict[tuple[str, str], tuple[str, str | None, bool | None]]:
    values: dict[tuple[str, str], tuple[str, str | None, bool | None]] = {}
    for component in frame.full_domains + frame.small_ordered_islands:
        for member in component.members:
            key = (frame.physical_frame_id, member.source_id)
            if key in values:
                raise ValueError(
                    "Automatic snapshot repeats a frozen source_id."
                )
            values[key] = (
                component.component_type,
                component.lattice_domain_id,
                member.source_id in component.halo_source_ids,
            )
    for member in frame.outside_members:
        key = (frame.physical_frame_id, member.source_id)
        if key in values:
            raise ValueError("Automatic snapshot repeats a frozen source_id.")
        values[key] = (
            "outside",
            None,
            None,
        )
    expected = {
        (frame.physical_frame_id, source_id)
        for source_id in frame.analyzed_source_ids
    }
    if set(values) != expected:
        raise ValueError(
            "Automatic snapshot must contain every frozen source_id exactly once."
        )
    return values


def _review_decisions(
    state: DomainAnalysisSessionState,
) -> dict[tuple[str, str, str], ReferenceReviewDecision]:
    return {
        (frame.scope.physical_frame_id, frame.scope.target, decision.source_id): (
            decision
        )
        for frame in state.reference_reviews.frames
        for decision in frame.decisions
    }


def _review_columns(
    target: str,
    decision: ReferenceReviewDecision | None,
) -> dict[str, Any]:
    return {
        f"{target}_review_eligibility": (
            "unreviewed" if decision is None else decision.eligibility
        ),
        f"{target}_review_disposition": (
            "" if decision is None else decision.disposition or ""
        ),
        f"{target}_review_abstention": (
            "" if decision is None else decision.abstention or ""
        ),
        f"{target}_review_reason_code": (
            "" if decision is None else decision.reason_code or ""
        ),
    }


__all__ = [
    "CorrectionAwarePackagePayload",
    "correction_aware_package_payload",
]
