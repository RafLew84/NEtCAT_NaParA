"""Qt-free orchestration of production first-shell Calibration evidence."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from moltrack.analysis import (
    FirstShellGeometryExperimentSettings,
    FirstShellGraphSettings,
    FirstShellPairCorrelationEvidence,
    AggregatedPairCorrelationResult,
    MolecularFrameRange,
    PairCorrelationResult,
    aggregate_pair_correlation_results,
    run_first_shell_geometry_experiment,
)
from moltrack.analysis.domain_analysis import (
    DomainAnalysisSeries,
    FirstShellGeometrySelectionRecord,
    M6Preset,
    M6PresetLibrary,
    M6RunConfiguration,
)
from moltrack.analysis.first_shell_geometry_models import (
    FirstShellGeometryExperimentReport,
    FirstShellPolicyMode,
    FirstShellSymmetry,
    FrozenFirstShellGeometrySelection,
)
from moltrack.persistence.m6_first_shell_reference import (
    load_m6_first_shell_calibration_reference,
)

from .domain_backend_adapters import (
    MolTrackLatticeNetworkAdapter,
    MolTrackOrientationComponentsAdapter,
)


@dataclass(frozen=True)
class FirstShellCalibrationGroup:
    """Production inputs for one Calibration measurement group."""

    measurement_group_id: str
    analysis_series: DomainAnalysisSeries
    frame_symmetries: tuple[tuple[str, FirstShellSymmetry], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.measurement_group_id, str) or not (
            group_id := self.measurement_group_id.strip()
        ):
            raise ValueError("measurement_group_id must be non-empty text.")
        if not isinstance(self.analysis_series, DomainAnalysisSeries):
            raise TypeError("analysis_series must be DomainAnalysisSeries.")
        mappings = tuple(self.frame_symmetries)
        physical_ids = tuple(value.geometry.physical_frame_id for value in self.analysis_series.frames)
        mapped_ids = tuple(value[0] for value in mappings)
        if len(set(mapped_ids)) != len(mapped_ids) or set(mapped_ids) != set(physical_ids):
            raise ValueError(
                "frame_symmetries must map every analysis frame exactly once."
            )
        object.__setattr__(self, "measurement_group_id", group_id)
        object.__setattr__(self, "frame_symmetries", mappings)


@dataclass(frozen=True)
class FirstShellBackendEvidence:
    """Normalized evidence supplied by one production Adapter."""

    backend_id: str
    pair_correlations: tuple[FirstShellPairCorrelationEvidence, ...]


@dataclass(frozen=True)
class FirstShellCalibrationSelection:
    """Frozen geometry and the executable configuration selected by the operator."""

    geometry: FrozenFirstShellGeometrySelection
    configuration: M6RunConfiguration


@dataclass(frozen=True)
class FirstShellCalibrationComparison:
    """Fixed/adaptive report plus auditable production evidence provenance."""

    report: FirstShellGeometryExperimentReport
    backend_evidence: tuple[FirstShellBackendEvidence, ...]

    @property
    def evidence_backend_ids(self) -> tuple[str, ...]:
        return tuple(value.backend_id for value in self.backend_evidence)

    def freeze(
        self,
        mode: FirstShellPolicyMode,
        configuration: M6RunConfiguration,
    ) -> FirstShellCalibrationSelection:
        geometry = self.report.freeze(mode)
        selection_record = FirstShellGeometrySelectionRecord(
            dataset_version_id=geometry.dataset_version_id,
            dataset_version_fingerprint=geometry.dataset_version_fingerprint,
            validation_epoch_id=geometry.validation_epoch_id,
            experiment_fingerprint=self.report.experiment_fingerprint,
            geometry_fingerprint=geometry.geometry_fingerprint,
            policy_fingerprint=geometry.policy.policy_fingerprint,
            policy_result_fingerprint=geometry.policy_result.result_fingerprint,
            evidence_fingerprints=tuple(
                (
                    decision.measurement_group_id,
                    decision.symmetry_class,
                    decision.evidence_fingerprint,
                )
                for decision in geometry.policy_result.decisions
            ),
        )
        return FirstShellCalibrationSelection(
            geometry,
            replace(
                configuration,
                first_shell_geometry=geometry.policy,
                first_shell_geometry_selection=selection_record,
            ),
        )

    def operator_summary(self) -> str:
        rows: list[str] = []
        for result in self.report.policy_results:
            for metric in result.metrics:
                rows.append(
                    f"{result.policy.mode} {metric.measurement_group_id}/"
                    f"{metric.symmetry_class}: P={_score(metric.precision)} "
                    f"R={_score(metric.recall)} F1={_score(metric.f1_score)}"
                )
        for decision in self.report.result("adaptive").decisions:
            rows.append(
                f"adaptive {decision.measurement_group_id}/"
                f"{decision.symmetry_class}: resolution={decision.resolution} "
                f"range={decision.resolved_r_min_nm:.3f}-"
                f"{decision.resolved_r_max_nm:.3f} nm "
                f"reason={decision.fallback_reason or 'none'} "
                f"evidence={decision.evidence_fingerprint}"
            )
        for backend in self.backend_evidence:
            rows.extend(
                f"g(r) {backend.backend_id} {evidence.measurement_group_id}/"
                f"{evidence.symmetry_class}: {_evidence_status(evidence)}"
                for evidence in backend.pair_correlations
            )
        return "\n".join(rows)


class FirstShellCalibrationApplication:
    """Deep module comparing production geometry evidence before any sweep."""

    @staticmethod
    def compare(
        package_path: str | Path,
        configuration: M6RunConfiguration,
        groups: tuple[FirstShellCalibrationGroup, ...],
    ) -> FirstShellCalibrationComparison:
        reference = load_m6_first_shell_calibration_reference(package_path)
        backend_evidence = _backend_evidence(
            reference.version_id,
            configuration,
            groups,
        )
        active = next(
            value
            for value in backend_evidence
            if value.backend_id == configuration.backend_id
        )
        report = run_first_shell_geometry_experiment(
            package_path,
            _experiment_settings(configuration),
            pair_correlations=active.pair_correlations,
        )
        return FirstShellCalibrationComparison(report, backend_evidence)

    @staticmethod
    def save_as_active(
        selection: FirstShellCalibrationSelection,
        library: M6PresetLibrary,
        preset_name: str,
    ) -> M6Preset:
        """Persist one explicit operator Save As before classification search."""

        return library.save_as_active(
            preset_name,
            selection.configuration,
            description="Operator-selected Calibration geometry",
        )


def _backend_evidence(
    dataset_version_id: str,
    configuration: M6RunConfiguration,
    groups: tuple[FirstShellCalibrationGroup, ...],
) -> tuple[FirstShellBackendEvidence, ...]:
    if not groups:
        raise ValueError("At least one Calibration group is required.")
    by_backend: dict[str, list[FirstShellPairCorrelationEvidence]] = {}
    for group in groups:
        adapters = (
            MolTrackOrientationComponentsAdapter(
                group.analysis_series, settings=configuration.settings
            ),
            MolTrackLatticeNetworkAdapter(
                group.analysis_series, settings=configuration.settings
            ),
        )
        frame_symmetries = dict(group.frame_symmetries)
        for adapter in adapters:
            results = adapter.first_shell_pair_correlations()
            if len(results) != len(group.analysis_series.frames):
                raise ValueError(
                    "Backend pair-correlation evidence must cover every frame."
                )
            by_symmetry: dict[FirstShellSymmetry, list[PairCorrelationResult]] = {}
            for frame, result in zip(group.analysis_series.frames, results):
                symmetry = frame_symmetries[frame.geometry.physical_frame_id]
                by_symmetry.setdefault(symmetry, []).append(result)
            target = by_backend.setdefault(adapter.backend_identity.backend_id, [])
            for symmetry, values in sorted(by_symmetry.items()):
                target.append(_evidence(
                    dataset_version_id,
                    group.measurement_group_id,
                    symmetry,
                    tuple(values),
                    configuration,
                ))
    return tuple(
        FirstShellBackendEvidence(backend_id, tuple(by_backend[backend_id]))
        for backend_id in sorted(by_backend)
    )


def _evidence(
    dataset_version_id: str,
    group_id: str,
    symmetry: FirstShellSymmetry,
    values: tuple[PairCorrelationResult, ...],
    configuration: M6RunConfiguration,
) -> FirstShellPairCorrelationEvidence:
    result: PairCorrelationResult | AggregatedPairCorrelationResult
    if len(values) == 1:
        result = values[0]
    else:
        frame_indices = tuple(value.frame_index for value in values)
        if frame_indices != tuple(range(frame_indices[0], frame_indices[-1] + 1)):
            return FirstShellPairCorrelationEvidence.unavailable(
                dataset_version_id,
                group_id,
                symmetry,
                "non_contiguous_symmetry_frames_cannot_be_aggregated",
            )
        result = aggregate_pair_correlation_results(
            values,
            frame_range=MolecularFrameRange(
                f"{group_id}-{symmetry}", frame_indices[0], frame_indices[-1]
            ),
            settings=configuration.settings,
        )
    return FirstShellPairCorrelationEvidence.available(
        dataset_version_id, group_id, symmetry, result
    )


def _experiment_settings(
    configuration: M6RunConfiguration,
) -> FirstShellGeometryExperimentSettings:
    settings = configuration.settings
    return FirstShellGeometryExperimentSettings(
        graph_settings=FirstShellGraphSettings(
            duplicate_detection_enabled=settings.duplicate_detection_enabled,
            duplicate_max_distance_nm=settings.duplicate_max_distance_nm,
            geometry_absolute_tolerance_nm=settings.geometry_absolute_tolerance_nm,
            geometry_relative_tolerance=settings.geometry_relative_tolerance,
        ),
        fixed_r_min_nm=settings.first_shell_r_min_nm,
        fixed_r_max_nm=settings.first_shell_r_max_nm,
        gr_bin_width_nm=settings.gr_bin_width_nm,
        gr_max_nm=settings.gr_max_nm,
        gr_min_expected_pair_exposure=settings.gr_min_expected_pair_exposure,
        gr_min_contributing_frames=settings.gr_min_contributing_frames,
        gr_smoothing_width=settings.gr_smoothing_width,
        gr_peak_prominence=settings.gr_peak_prominence,
        gr_smoothing_method=settings.gr_smoothing_method,
    )


def _score(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _evidence_status(evidence: FirstShellPairCorrelationEvidence) -> str:
    result = evidence.pair_correlation
    if result is None:
        return f"unavailable reason={evidence.unavailable_reason}"
    point_count = (
        result.point_count
        if isinstance(result, PairCorrelationResult)
        else result.total_point_count
    )
    return (
        f"available window={result.window_geometry_status} "
        f"points={point_count}"
    )


__all__ = [
    "FirstShellCalibrationApplication",
    "FirstShellCalibrationComparison",
    "FirstShellCalibrationGroup",
    "FirstShellCalibrationSelection",
]
