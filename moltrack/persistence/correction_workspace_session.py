from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from moltrack.analysis.domain_analysis import (
    CorrectionRebaseRecord,
    DomainAnalysisPublication,
    DomainCorrectionModule,
    DomainCorrectionWorkspace,
    OrientationClassCatalog,
    PendingAutomaticCandidate,
    PreparedCorrectionRebase,
    ReferenceReviewPolicy,
    ReferenceReviewWorkspace,
)
from moltrack.analysis.domain_analysis.workspace_correction import (
    DomainCorrectionWorkspaceState,
    initialize_domain_corrections,
)
from moltrack.analysis.domain_analysis.diagnostic_funnel import (
    build_molecule_diagnostic_funnels,
)

from .correction_rebase_payload import (
    pending_candidate_from_payload,
    pending_candidate_to_payload,
    prepared_rebase_from_payload,
    prepared_rebase_to_payload,
    rebase_records_from_payload,
    rebase_records_to_payload,
)
from .diagnostic_funnel_payload import (
    diagnostic_funnels_to_payload,
    validate_diagnostic_funnels_payload,
)
from .domain_analysis_payload_validation import (
    integer_field,
    mapping,
    required,
    text_list_field,
)
from .domain_correction_set_payload import (
    correction_set_from_payload,
    correction_set_to_payload,
)
from .effective_projection_checkpoint import (
    effective_projection_checkpoint,
    validate_effective_projection_checkpoint,
)
from .reference_review_payload import (
    reference_reviews_from_payload,
    reference_reviews_to_payload,
)


CORRECTION_WORKSPACE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class LoadedCorrectionWorkspace:
    orientation_class_catalog: OrientationClassCatalog
    domain_corrections: DomainCorrectionWorkspaceState
    reference_reviews: ReferenceReviewWorkspace
    reinitialized_from_automatic: bool = False


@dataclass(frozen=True)
class _DecodedCorrectionWorkspace:
    catalog: OrientationClassCatalog
    correction_set: DomainCorrectionWorkspace | None
    pending: PendingAutomaticCandidate | None
    prepared_rebase: PreparedCorrectionRebase | None
    rebase_records: tuple[CorrectionRebaseRecord, ...]
    reviews: ReferenceReviewWorkspace


def correction_workspace_to_payload(
    publication: DomainAnalysisPublication | None,
    catalog: OrientationClassCatalog,
    state: DomainCorrectionWorkspaceState,
    reviews: ReferenceReviewWorkspace,
) -> dict[str, Any]:
    state, reviews = _normalized_workspace(publication, state, reviews)
    correction_set = state.correction_set
    projection = state.effective_projection
    checkpoint = None
    if publication is not None and correction_set is not None and projection is not None:
        checkpoint = effective_projection_checkpoint(
            publication,
            correction_set,
            projection,
        )
    return {
        "schema_version": CORRECTION_WORKSPACE_SCHEMA_VERSION,
        "orientation_class_catalog": {
            "revision": catalog.revision,
            "labels": list(catalog.labels),
        },
        "active_correction_set": (
            None
            if correction_set is None
            else correction_set_to_payload(correction_set)
        ),
        "pending_rebase": pending_candidate_to_payload(
            state.pending_automatic_candidate
        ),
        "prepared_rebase": prepared_rebase_to_payload(state.prepared_rebase),
        "rebase_records": rebase_records_to_payload(state.rebase_records),
        "reviews": reference_reviews_to_payload(reviews),
        "diagnostic_funnels": (
            []
            if publication is None
            else diagnostic_funnels_to_payload(
                build_molecule_diagnostic_funnels(publication.result)
            )
        ),
        "effective_projection_checkpoint": checkpoint,
        "readiness": _readiness(publication, state, reviews),
    }


def correction_workspace_from_payload(
    payload: Any,
    publication: DomainAnalysisPublication | None,
    *,
    allow_pristine_reinitialization: bool = False,
) -> LoadedCorrectionWorkspace:
    path = "domain_analysis.correction_workspace"
    saved = mapping(payload, path)
    version = integer_field(saved, "schema_version", path)
    if version != CORRECTION_WORKSPACE_SCHEMA_VERSION:
        raise ValueError(f"Unsupported correction_workspace schema_version: {version}.")
    decoded = _decode_workspace(saved, path)
    state, reviews, reinitialized = _restore_workspace_state(
        decoded,
        publication,
        saved,
        allow_pristine_reinitialization=allow_pristine_reinitialization,
    )
    funnels = () if publication is None else publication.result.molecule_diagnostic_funnels
    if not reinitialized:
        validate_diagnostic_funnels_payload(
            required(saved, "diagnostic_funnels", path),
            funnels,
            path=f"{path}.diagnostic_funnels",
        )
    expected_readiness = _readiness(publication, state, reviews)
    if (
        not reinitialized
        and required(saved, "readiness", path) != expected_readiness
    ):
        raise ValueError("Saved correction-aware readiness is not reproducible.")
    _validate_catalog_assignments(decoded.catalog, state)
    return LoadedCorrectionWorkspace(
        decoded.catalog,
        state,
        reviews,
        reinitialized,
    )


def _decode_workspace(
    saved: Any,
    path: str,
) -> _DecodedCorrectionWorkspace:
    catalog = _catalog(required(saved, "orientation_class_catalog", path))
    correction_payload = required(saved, "active_correction_set", path)
    return _DecodedCorrectionWorkspace(
        catalog=catalog,
        correction_set=(
            None
            if correction_payload is None
            else correction_set_from_payload(correction_payload)
        ),
        pending=pending_candidate_from_payload(
            required(saved, "pending_rebase", path)
        ),
        prepared_rebase=prepared_rebase_from_payload(
            required(saved, "prepared_rebase", path)
        ),
        rebase_records=rebase_records_from_payload(
            required(saved, "rebase_records", path)
        ),
        reviews=reference_reviews_from_payload(required(saved, "reviews", path)),
    )


def _restore_workspace_state(
    decoded: _DecodedCorrectionWorkspace,
    publication: DomainAnalysisPublication | None,
    saved: Any,
    *,
    allow_pristine_reinitialization: bool,
) -> tuple[DomainCorrectionWorkspaceState, ReferenceReviewWorkspace, bool]:
    if publication is None:
        if (
            decoded.correction_set is not None
            or decoded.pending is not None
            or decoded.rebase_records
            or decoded.reviews.frames
        ):
            raise ValueError("Correction workspace data requires an automatic snapshot.")
        return DomainCorrectionWorkspaceState(), decoded.reviews, False
    correction_set = decoded.correction_set
    if correction_set is None:
        raise ValueError("An automatic snapshot requires an active correction set.")
    module = DomainCorrectionModule()
    reinitialized = False
    try:
        projection = module.project(publication.result, correction_set)
    except ValueError:
        if not allow_pristine_reinitialization or not _is_pristine(
            correction_set,
            decoded.pending,
            decoded.prepared_rebase,
            decoded.rebase_records,
            decoded.reviews,
        ):
            raise
        state = initialize_domain_corrections(module, publication.result)
        reviews = ReferenceReviewPolicy().initialize(publication.result, state)
        return state, reviews, True
    state = DomainCorrectionWorkspaceState(
        correction_set=correction_set,
        effective_projection=projection,
        pending_automatic_candidate=decoded.pending,
        prepared_rebase=decoded.prepared_rebase,
        rebase_records=decoded.rebase_records,
    )
    reviews = decoded.reviews
    if ReferenceReviewPolicy().synchronize(
        reviews, publication.result, state
    ) != reviews:
        raise ValueError("Saved Reference Review scopes do not match corrections.")
    validate_effective_projection_checkpoint(
        required(saved, "effective_projection_checkpoint", "domain_analysis.correction_workspace"),
        publication,
        correction_set,
        projection,
    )
    return state, reviews, reinitialized


def _normalized_workspace(
    publication: DomainAnalysisPublication | None,
    state: DomainCorrectionWorkspaceState,
    reviews: ReferenceReviewWorkspace,
) -> tuple[DomainCorrectionWorkspaceState, ReferenceReviewWorkspace]:
    if publication is None:
        return state, reviews
    if state.correction_set is None:
        state = initialize_domain_corrections(
            DomainCorrectionModule(),
            publication.result,
        )
    if not reviews.frames:
        reviews = ReferenceReviewPolicy().initialize(publication.result, state)
    return state, reviews


def _catalog(payload: Any) -> OrientationClassCatalog:
    path = "domain_analysis.correction_workspace.orientation_class_catalog"
    saved = mapping(payload, path)
    return OrientationClassCatalog(
        labels=tuple(text_list_field(saved, "labels", path)),
        revision=integer_field(saved, "revision", path),
    )


def _readiness(
    publication: DomainAnalysisPublication | None,
    state: DomainCorrectionWorkspaceState,
    reviews: ReferenceReviewWorkspace,
) -> dict[str, Any]:
    blockers = []
    if publication is None or state.correction_set is None:
        blockers.append("no_active_automatic_snapshot")
    if state.pending_automatic_candidate is not None:
        blockers.append("pending_rebase")
    policy = ReferenceReviewPolicy()
    for target in ("m6", "orientation"):
        if not policy.readiness(reviews, target).ready:
            blockers.append(f"{target}_review_incomplete")
    return {"ready": not blockers, "blockers": blockers}


def _validate_catalog_assignments(
    catalog: OrientationClassCatalog,
    state: DomainCorrectionWorkspaceState,
) -> None:
    correction_set = state.correction_set
    if correction_set is None:
        return
    catalog.validate_assignments(
        value.orientation_label for value in correction_set.orientation_decisions
    )


def _is_pristine(
    correction_set: Any,
    pending: Any,
    prepared_rebase: Any,
    rebase_records: tuple[Any, ...],
    reviews: ReferenceReviewWorkspace,
) -> bool:
    return (
        correction_set.revision == 0
        and not correction_set.orientation_decisions
        and not correction_set.manual_domains
        and not correction_set.cleared_boundary_source_keys
        and not correction_set.atoms
        and not correction_set.history_records
        and pending is None
        and prepared_rebase is None
        and not rebase_records
        and all(
            not frame.decisions and frame.sign_off is None
            for frame in reviews.frames
        )
    )


__all__ = [
    "CORRECTION_WORKSPACE_SCHEMA_VERSION",
    "LoadedCorrectionWorkspace",
    "correction_workspace_from_payload",
    "correction_workspace_to_payload",
]
