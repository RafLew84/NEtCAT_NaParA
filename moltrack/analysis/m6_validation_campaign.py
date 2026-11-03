"""Freeze the Calibration-qualified M6 candidate shortlist."""

from __future__ import annotations

from pathlib import Path

from .domain_analysis import (
    M3_M6_LATTICE_NETWORK_BACKEND_ID,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
)
from .first_shell_geometry_models import FrozenFirstShellGeometrySelection
from .m6_calibration_campaign_models import (
    M6CalibrationBackend,
    M6CalibrationCampaignReport,
    M6CalibrationReferenceGroup,
)
from .m6_calibration_metrics import (
    evaluate_m6_calibration_groups,
    m6_calibration_objective_loss,
    normalize_m6_calibration_prediction,
)
from .m6_validation_campaign_models import (
    M6_CALIBRATION_TIE_BREAK_RULE,
    M6CampaignReportV2,
    M6CampaignReportV2Publication,
    M6CandidateShortlist,
    M6CandidateShortlistEntry,
    M6ValidationBackendResult,
)


_BACKEND_IDS = {
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    M3_M6_LATTICE_NETWORK_BACKEND_ID,
}


def freeze_m6_candidate_shortlist(
    campaign: M6CalibrationCampaignReport,
    geometry: FrozenFirstShellGeometrySelection,
) -> M6CandidateShortlist:
    """Freeze exactly one eligible Calibration candidate for each backend."""

    if not isinstance(campaign, M6CalibrationCampaignReport):
        raise TypeError("campaign must be an M6CalibrationCampaignReport.")
    if not isinstance(geometry, FrozenFirstShellGeometrySelection):
        raise TypeError("geometry must be a FrozenFirstShellGeometrySelection.")
    results = campaign.backend_results_for(geometry)
    entries = []
    for result in results:
        candidate = result.selected_candidate
        if candidate is None or not candidate.eligible:
            raise ValueError(
                "Each M6 backend requires one eligible Calibration candidate."
            )
        entries.append(M6CandidateShortlistEntry(result.backend_identity, candidate))
    return M6CandidateShortlist(
        dataset_id=campaign.dataset_id,
        dataset_version_id=campaign.dataset_version_id,
        dataset_version_fingerprint=campaign.dataset_version_fingerprint,
        validation_epoch_id=campaign.validation_epoch_id,
        geometry_fingerprint=campaign.geometry_fingerprint,
        objective=campaign.objective,
        tie_break_rule=M6_CALIBRATION_TIE_BREAK_RULE,
        entries=tuple(entries),
    )


def open_m6_validation_and_publish_report(
    campaign: M6CalibrationCampaignReport,
    shortlist: M6CandidateShortlist,
    geometry: FrozenFirstShellGeometrySelection,
    *,
    backends: tuple[M6CalibrationBackend, ...],
    destination: str | Path,
) -> M6CampaignReportV2Publication:
    """Open one bound Validation epoch and publish its complete report."""

    ordered_backends = _require_frozen_context(
        campaign,
        shortlist,
        geometry,
        backends,
    )
    destination_path = Path(destination)
    if destination_path.resolve().is_relative_to(campaign.package_path.resolve()):
        raise ValueError("Validation report destination cannot modify the dataset.")
    from moltrack.persistence.m6_validation_reference import (
        open_m6_validation_reference,
    )

    reference = open_m6_validation_reference(campaign.package_path, shortlist)
    results = tuple(
        _evaluate_backend(
            entry,
            ordered_backends[entry.backend_identity.backend_id],
            reference.groups,
            geometry,
            campaign,
        )
        for entry in shortlist.entries
    )
    report = M6CampaignReportV2(
        dataset_id=shortlist.dataset_id,
        dataset_version_id=shortlist.dataset_version_id,
        dataset_version_fingerprint=shortlist.dataset_version_fingerprint,
        validation_epoch_id=shortlist.validation_epoch_id,
        geometry_fingerprint=shortlist.geometry_fingerprint,
        objective=shortlist.objective,
        sweep=campaign.sweep,
        calibration_shortlist=shortlist,
        receipt=reference.receipt,
        validation_results=results,
    )
    from moltrack.persistence.m6_campaign_report_v2 import (
        publish_m6_campaign_report_v2,
    )

    return publish_m6_campaign_report_v2(report, destination_path)


def _require_frozen_context(
    campaign: M6CalibrationCampaignReport,
    shortlist: M6CandidateShortlist,
    geometry: FrozenFirstShellGeometrySelection,
    backends: tuple[M6CalibrationBackend, ...],
) -> dict[str, M6CalibrationBackend]:
    if not isinstance(campaign, M6CalibrationCampaignReport):
        raise TypeError("campaign must be an M6CalibrationCampaignReport.")
    if not isinstance(shortlist, M6CandidateShortlist):
        raise TypeError("shortlist must be an M6CandidateShortlist.")
    campaign.require_geometry(geometry)
    expected = freeze_m6_candidate_shortlist(campaign, geometry)
    if expected.shortlist_fingerprint != shortlist.shortlist_fingerprint:
        raise ValueError("Frozen shortlist does not match the Calibration campaign.")
    backend_values = tuple(backends)
    if any(not isinstance(value, M6CalibrationBackend) for value in backend_values):
        raise TypeError("backends must contain M6CalibrationBackend values.")
    by_id = {value.backend_identity.backend_id: value for value in backend_values}
    if len(backend_values) != 2 or set(by_id) != _BACKEND_IDS:
        raise ValueError("Validation requires both stable M6 backend IDs.")
    shortlist_identities = {
        value.backend_identity.backend_id: value.backend_identity
        for value in shortlist.entries
    }
    if any(
        backend.backend_identity != shortlist_identities[backend_id]
        for backend_id, backend in by_id.items()
    ):
        raise ValueError("Validation backend identity changed after Calibration.")
    return by_id


def _evaluate_backend(
    entry: M6CandidateShortlistEntry,
    backend: M6CalibrationBackend,
    groups: tuple[M6CalibrationReferenceGroup, ...],
    geometry: FrozenFirstShellGeometrySelection,
    campaign: M6CalibrationCampaignReport,
) -> M6ValidationBackendResult:
    predictions = tuple(
        normalize_m6_calibration_prediction(
            backend.evaluator(group, entry.candidate.variant.settings, geometry)
        )
        for group in groups
    )
    metrics, group_metrics = evaluate_m6_calibration_groups(
        groups,
        predictions,
        explicit_boundary=(
            "explicit_boundary" in backend.backend_identity.capabilities
        ),
    )
    objective_loss = m6_calibration_objective_loss(metrics, campaign.objective)
    failures = []
    precision = metrics.macro_membership_precision
    if precision is None:
        failures.append("precision_unavailable")
    elif precision < campaign.objective.minimum_membership_precision:
        failures.append("precision_below_constraint")
    if objective_loss is None:
        failures.append("membership_recall_unavailable")
    return M6ValidationBackendResult(
        backend_identity=backend.backend_identity,
        candidate_fingerprint=entry.candidate_fingerprint,
        candidate=entry.candidate,
        metrics=metrics,
        group_metrics=group_metrics,
        objective_loss=objective_loss,
        passed_constraints=not failures,
        constraint_failures=tuple(failures),
    )


__all__ = [
    "freeze_m6_candidate_shortlist",
    "open_m6_validation_and_publish_report",
]
