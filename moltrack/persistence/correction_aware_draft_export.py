from __future__ import annotations

from typing import Any

from moltrack.analysis.domain_analysis import (
    DOMAIN_ANALYSIS_RETRY_REQUIRED_DIAGNOSIS,
    DomainAnalysisSessionState,
)
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256

from .correction_aware_export_schema import (
    AUTOMATIC_SNAPSHOT_FILE,
    DIAGNOSTIC_FUNNELS_FILE,
    DRAFT_STATE_FILE,
    ORIENTATION_CLASS_CATALOG_FILE,
    REBASE_DIAGNOSTICS_FILE,
    REFERENCE_REVIEWS_FILE,
)
from .domain_analysis_classifier_payload import (
    classifier_configuration_to_payload,
)
from .domain_analysis_request_payload import domain_analysis_request_to_payload
from .reference_review_payload import reference_reviews_to_payload


def inactive_draft_export_parts(
    state: DomainAnalysisSessionState,
) -> tuple[dict[str, Any], dict[str, Any]]:
    catalog = _catalog_payload(state)
    return _inactive_anchors(catalog), _inactive_documents(state, catalog)


def _inactive_anchors(catalog: dict[str, Any]) -> dict[str, Any]:
    return {
        "backend_identity_fingerprint": None,
        "backend_identities": [],
        "automatic_snapshot_fingerprint": None,
        "orientation_class_catalog_fingerprint": canonical_sha256(catalog),
        "orientation_class_catalog_revision": catalog["revision"],
        "correction_revision": None,
        "correction_revision_fingerprint": None,
        "effective_projection_fingerprint": None,
    }


def _inactive_documents(
    state: DomainAnalysisSessionState,
    catalog: dict[str, Any],
) -> dict[str, Any]:
    return {
        AUTOMATIC_SNAPSHOT_FILE: None,
        DRAFT_STATE_FILE: _draft_state_payload(state),
        ORIENTATION_CLASS_CATALOG_FILE: catalog,
        REFERENCE_REVIEWS_FILE: reference_reviews_to_payload(
            state.reference_reviews
        ),
        DIAGNOSTIC_FUNNELS_FILE: [],
        REBASE_DIAGNOSTICS_FILE: {
            "pending_rebase": None,
            "prepared_rebase": None,
            "records": [],
        },
    }


def _draft_state_payload(state: DomainAnalysisSessionState) -> dict[str, Any]:
    draft = state.draft
    run_status = state.run_status
    run_diagnosis = state.run_diagnosis
    if run_status == "running":
        run_status = "retry_required"
        run_diagnosis = DOMAIN_ANALYSIS_RETRY_REQUIRED_DIAGNOSIS
    selected = state.selected_component
    return {
        "session_schema_version": state.schema_version,
        "request": (
            None if draft is None else domain_analysis_request_to_payload(draft)
        ),
        "physical_frame_ids": list(state.draft_physical_frame_ids),
        "classifier_configurations": [
            classifier_configuration_to_payload(value)
            for value in state.draft_classifier_configurations
        ],
        "run": {"status": run_status, "diagnosis": run_diagnosis},
        "view_settings": {
            "overlay_visible": state.view_settings.overlay_visible,
            "overlay_opacity_percent": state.view_settings.overlay_opacity_percent,
        },
        "selected_component": (
            None
            if selected is None
            else {
                "physical_frame_id": selected.physical_frame_id,
                "lattice_domain_id": selected.lattice_domain_id,
            }
        ),
    }


def _catalog_payload(state: DomainAnalysisSessionState) -> dict[str, Any]:
    catalog = state.orientation_class_catalog
    return {"revision": catalog.revision, "labels": list(catalog.labels)}


__all__ = ["inactive_draft_export_parts"]
