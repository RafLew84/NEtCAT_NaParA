from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QInputDialog, QWidget

from moltrack.analysis import (
    FirstShellGeometryExperimentSettings,
    FirstShellGraphSettings,
    FirstShellPairCorrelationEvidence,
    FrozenFirstShellGeometrySelection,
    LatticeDomainCalibrationSweepSettings,
    LatticeDomainPartitionLabels,
    MolecularM6OrientationAnalysisSettings,
    freeze_m6_candidate_shortlist,
    open_m6_validation_and_publish_report,
    run_first_shell_geometry_experiment,
    run_lattice_domain_calibration_campaign,
)
from moltrack.analysis.domain_analysis import (
    DomainAnalysisModule,
    DomainAnalysisRequest,
    DomainAnalysisSeries,
    M3M6LatticeNetworkEvidence,
    M6OrientationComponentsEvidence,
    M6RunConfiguration,
    MoleculeDiagnosticStageId,
)
from moltrack.analysis.m6_calibration_campaign_models import (
    M6CalibrationBackend,
    M6CalibrationCampaignReport,
    M6CalibrationGroupPrediction,
    M6CalibrationObjective,
)
from moltrack.analysis.m6_validation_campaign_models import (
    M6CampaignReportV2Publication,
    M6CandidateShortlist,
)
from moltrack.persistence import (
    M6ReferenceDatasetPublication,
    OrientationReferenceDatasetPublication,
)
from moltrack.ui.domain_backend_adapters import (
    MolTrackLatticeNetworkAdapter,
    MolTrackOrientationComponentsAdapter,
)

from .domain_analysis_workflow_sheet import DomainAnalysisWorkflowActions
from .domain_analysis_reference_workflow import (
    CurrentDomainAnalysisWorkspace,
    DomainAnalysisReferenceWorkflow,
)


@dataclass(frozen=True)
class M6ReleaseCampaign:
    """Auditable artifacts produced by one interactive release campaign."""

    geometry: FrozenFirstShellGeometrySelection
    campaign: M6CalibrationCampaignReport
    shortlist: M6CandidateShortlist
    publication: M6CampaignReportV2Publication
    evaluation_trace: tuple[
        tuple[str, tuple[tuple[str, str], ...]], ...
    ]


class DomainAnalysisReleaseWorkflow:
    """Interactive owner of cross-session reference and campaign state."""

    def __init__(self, owner: QWidget) -> None:
        if not isinstance(owner, QWidget):
            raise TypeError("owner must be a QWidget.")
        self._owner = owner
        self._references = DomainAnalysisReferenceWorkflow(owner)
        self._last_campaign: M6ReleaseCampaign | None = None

    @property
    def m6_publication(self) -> M6ReferenceDatasetPublication:
        return self._references.m6_publication

    @property
    def orientation_publication(self) -> OrientationReferenceDatasetPublication:
        return self._references.orientation_publication

    @property
    def last_campaign(self) -> M6ReleaseCampaign:
        campaign = self._last_campaign
        if campaign is None:
            raise RuntimeError("No M6 release campaign was published.")
        return campaign

    def actions(
        self,
        current: CurrentDomainAnalysisWorkspace,
        *,
        save_session: Callable[[], object],
        open_session: Callable[[], object],
    ) -> DomainAnalysisWorkflowActions:
        return DomainAnalysisWorkflowActions(
            save_session=save_session,
            open_session=open_session,
            publish_m6_reference=(
                lambda: self._references.publish_m6_reference(current)
            ),
            publish_orientation_reference=(
                lambda: self._references.publish_orientation_reference(current)
            ),
            run_calibration=lambda: self.run_calibration(current),
        )

    def run_calibration(
        self,
        current: CurrentDomainAnalysisWorkspace,
    ) -> object:
        package = self._references.m6_publication
        _state, _series, _analysis_series, library = current()
        configuration = library.active_run_configuration()
        policy = configuration.first_shell_geometry
        if policy.mode != "fixed":
            raise ValueError(
                "Calibrate requires an explicitly activated fixed first-shell policy."
            )
        objective = self._objective()
        if objective is None:
            return "Calibration cancelled before Validation was opened."
        geometry = self._geometry(configuration)
        groups = self._references.m6_groups
        observed: dict[str, list[tuple[str, str]]] = {}
        adapters = self._campaign_backends(groups, configuration.settings, observed)
        campaign = run_lattice_domain_calibration_campaign(
            package.package_path,
            LatticeDomainCalibrationSweepSettings(
                baseline_settings=configuration.settings,
                parameter_names=("q_grow",),
                max_multivariate_variants=0,
                max_stability_candidates=2,
            ),
            objective,
            geometry=geometry,
            backends=adapters,
        )
        shortlist = freeze_m6_candidate_shortlist(campaign, geometry)
        destination = QFileDialog.getExistingDirectory(
            self._owner,
            "Publish M6 campaign report v2",
        )
        if not destination:
            return "Report publication cancelled before Validation was opened."
        publication = open_m6_validation_and_publish_report(
            campaign,
            shortlist,
            geometry,
            backends=adapters,
            destination=Path(destination) / "m6-campaign-report-v2",
        )
        self._last_campaign = M6ReleaseCampaign(
            geometry=geometry,
            campaign=campaign,
            shortlist=shortlist,
            publication=publication,
            evaluation_trace=tuple(
                (backend_id, tuple(observed[backend_id]))
                for backend_id in sorted(observed)
            ),
        )
        return publication.output_directory

    def _geometry(self, configuration: M6RunConfiguration):
        package = self._references.m6_publication
        policy = configuration.first_shell_geometry
        assert policy.fixed_r_min_nm is not None and policy.fixed_r_max_nm is not None
        groups = self._references.m6_groups
        return run_first_shell_geometry_experiment(
            package.package_path,
            FirstShellGeometryExperimentSettings(
                graph_settings=FirstShellGraphSettings(
                    duplicate_detection_enabled=(
                        configuration.settings.duplicate_detection_enabled
                    ),
                    duplicate_max_distance_nm=(
                        configuration.settings.duplicate_max_distance_nm
                    ),
                    geometry_absolute_tolerance_nm=(
                        configuration.settings.geometry_absolute_tolerance_nm
                    ),
                    geometry_relative_tolerance=(
                        configuration.settings.geometry_relative_tolerance
                    ),
                ),
                fixed_r_min_nm=policy.fixed_r_min_nm,
                fixed_r_max_nm=policy.fixed_r_max_nm,
                gr_bin_width_nm=configuration.settings.gr_bin_width_nm,
                gr_max_nm=configuration.settings.gr_max_nm,
                gr_min_expected_pair_exposure=(
                    configuration.settings.gr_min_expected_pair_exposure
                ),
                gr_min_contributing_frames=(
                    configuration.settings.gr_min_contributing_frames
                ),
                gr_smoothing_width=configuration.settings.gr_smoothing_width,
                gr_peak_prominence=configuration.settings.gr_peak_prominence,
            ),
            pair_correlations=tuple(
                FirstShellPairCorrelationEvidence.unavailable(
                    package.version_id,
                    group.measurement_group_id,
                    symmetry,
                    "operator_selected_fixed_policy",
                )
                for group in groups
                if group.split == "calibration"
                for symmetry in self._references.first_shell_symmetries(
                    group.measurement_group_id
                )
            ),
        ).freeze("fixed")

    def _campaign_backends(self, groups, settings, observed):
        probe = self._production_adapters(groups[0].analysis_series, settings)
        return tuple(
            self._campaign_backend(adapter.backend_identity, groups, observed)
            for adapter in probe
        )

    def _campaign_backend(self, identity, groups, observed):
        groups_by_id = {value.measurement_group_id: value for value in groups}

        def evaluate(group, settings, geometry):
            source = groups_by_id[group.measurement_group_id]
            adapter = next(
                value
                for value in self._production_adapters(source.analysis_series, settings)
                if value.backend_identity.backend_id == identity.backend_id
            )
            observed.setdefault(identity.backend_id, []).append((
                group.dataset_version_id,
                group.measurement_group_id,
            ))
            result = DomainAnalysisModule({identity.backend_id: adapter}, {}).run(
                source.analysis_series,
                DomainAnalysisRequest(
                    frame_range=range(len(source.analysis_series.frames)),
                    backend_id=identity.backend_id,
                    m6_configuration=M6RunConfiguration(
                        backend_identity=adapter.backend_identity,
                        settings=settings,
                        first_shell_geometry=geometry.policy,
                    ),
                ),
            )
            return _campaign_prediction(result, group.reference_labels.source_ids)

        return M6CalibrationBackend(identity, evaluate)

    def _objective(self) -> M6CalibrationObjective | None:
        values = []
        for label, initial in (
            ("Minimum membership precision", 0.9),
            ("Minimum local stability ARI", 0.9),
            ("Split penalty weight", 0.2),
            ("Merge penalty weight", 0.2),
        ):
            value, accepted = QInputDialog.getDouble(
                self._owner,
                "M6 calibration objective",
                label,
                initial,
                0.0,
                1.0,
                3,
            )
            if not accepted:
                return None
            values.append(value)
        return M6CalibrationObjective(*values)

    @staticmethod
    def _production_adapters(
        series: DomainAnalysisSeries,
        settings: MolecularM6OrientationAnalysisSettings,
    ):
        return (
            MolTrackOrientationComponentsAdapter(series, settings=settings),
            MolTrackLatticeNetworkAdapter(series, settings=settings),
        )

def _campaign_prediction(result, source_ids) -> M6CalibrationGroupPrediction:
    gate = result.m6_gate
    assert gate is not None
    predictions = {}
    for frame in gate.frames:
        domain_by_source = {
            source_id: component.lattice_domain_id
            for component in frame.full_domains
            for source_id in component.source_ids
        }
        evidence = frame.native_evidence
        if isinstance(evidence, M3M6LatticeNetworkEvidence):
            boundary_by_source = {
                source_id: role == "boundary"
                for source_id, role in evidence.point_roles
            }
            confidence_by_domain = {
                value.lattice_domain_id: value.confidence
                for value in evidence.domains
            }
            confidence_by_source = {
                source_id: confidence_by_domain.get(domain_id)
                for source_id, domain_id in domain_by_source.items()
            }
        elif isinstance(evidence, M6OrientationComponentsEvidence):
            boundary_by_source = {
                source_id: False for source_id in frame.analyzed_source_ids
            }
            confidence_by_source = dict(evidence.q6)
        else:  # pragma: no cover - the backend contract is a closed union
            raise TypeError("Unsupported Domain Analysis native evidence.")
        predictions.update({
            f"{frame.physical_frame_id}::{source_id}": (
                domain_by_source.get(source_id),
                boundary_by_source.get(source_id, False),
                confidence_by_source.get(source_id),
            )
            for source_id in frame.analyzed_source_ids
        })
    failed_by_source: dict[
        str,
        tuple[MoleculeDiagnosticStageId, ...],
    ] = {
        f"{funnel.physical_frame_id}::{funnel.source_id}": (
            "automatic_result"
            if miss.stage_id == "domain_partition"
            else miss.stage_id,
        )
        for funnel in result.molecule_diagnostic_funnels
        if (miss := funnel.terminal_domain_miss) is not None
    }
    return M6CalibrationGroupPrediction(
        LatticeDomainPartitionLabels(
            source_ids=tuple(source_ids),
            domain_labels=tuple(
                predictions[value][0] for value in source_ids
            ),
            boundary=tuple(
                predictions[value][1] for value in source_ids
            ),
            confidence=tuple(
                predictions[value][2] for value in source_ids
            ),
        ),
        failed_stage_ids=tuple(
            (source_id, failed_by_source[source_id])
            for source_id in source_ids
            if source_id in failed_by_source
        ),
    )


__all__ = ["DomainAnalysisReleaseWorkflow", "M6ReleaseCampaign"]
