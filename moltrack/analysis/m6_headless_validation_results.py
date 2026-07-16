from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isclose, isfinite

from ._m6_settings_fingerprint import m6_settings_fingerprint
from ._pair_correlation_binning import pair_correlation_bin_edges
from ._pair_correlation_windows import rectangular_annulus_overlap_integrals
from .first_shell_graph import FirstShellGraph
from .m6_settings import MolecularM6OrientationAnalysisSettings
from .m6_headless_validation_manifest import (
    M6_ORIENTATION_ALGORITHM_VERSION,
    M6HeadlessValidationFrame,
    M6ValidationSourceView,
    M6ValidationStatus,
    M6ValidationWarningCode,
)
from .orientation_domain_analysis import M6OrientationDomainAnalysis
from .pair_correlation import PairCorrelationResult


@dataclass(frozen=True)
class M6HeadlessValidationWarning:
    code: M6ValidationWarningCode
    message: str

    def __post_init__(self) -> None:
        supported = {
            "high_unassigned_fraction",
            "graph_fallback",
            "delaunay_degeneracy",
            "unreliable_valid_fov",
        }
        if self.code not in supported:
            raise ValueError(f"Unsupported validation warning code: {self.code!r}.")
        object.__setattr__(self, "message", _non_empty_string(self.message, "message"))


@dataclass(frozen=True)
class M6HeadlessValidationFrameSummary:
    original_observation_count: int
    valid_representative_count: int
    duplicate_excluded_count: int
    invalid_position_count: int
    valid_fov_area_nm2: float
    supported_area_nm2: float
    full_domain_molecule_fraction: float | None
    small_island_molecule_fraction: float | None
    unassigned_molecule_fraction: float | None
    duplicate_excluded_fraction_of_original: float | None
    invalid_position_fraction_of_original: float | None
    full_domain_footprint_fraction: float | None
    small_island_footprint_fraction: float | None
    unassigned_supported_footprint_fraction: float | None
    unsupported_background_fraction: float | None
    full_domain_orientations_deg: tuple[float, ...]
    dominant_full_domain_orientation_deg: float | None

    def __post_init__(self) -> None:
        counts = tuple(
            _non_negative_int(getattr(self, name), name)
            for name in (
                "original_observation_count",
                "valid_representative_count",
                "duplicate_excluded_count",
                "invalid_position_count",
            )
        )
        if counts[0] != counts[1] + counts[2] + counts[3]:
            raise ValueError("Summary counts must partition original observations O.")
        valid_area = _non_negative_float(self.valid_fov_area_nm2, "valid_fov_area_nm2")
        supported_area = _non_negative_float(self.supported_area_nm2, "supported_area_nm2")
        if supported_area > valid_area and not isclose(supported_area, valid_area):
            raise ValueError("supported_area_nm2 cannot exceed valid_fov_area_nm2.")

        molecule_fractions = (
            self.full_domain_molecule_fraction,
            self.small_island_molecule_fraction,
            self.unassigned_molecule_fraction,
        )
        _validate_partition_fractions(
            molecule_fractions,
            available=counts[1] > 0,
            field_name="molecule fractions",
        )
        expected_rejection_fractions = (
            None if counts[0] == 0 else counts[2] / counts[0],
            None if counts[0] == 0 else counts[3] / counts[0],
        )
        for actual, expected, name in zip(
            (
                self.duplicate_excluded_fraction_of_original,
                self.invalid_position_fraction_of_original,
            ),
            expected_rejection_fractions,
            (
                "duplicate_excluded_fraction_of_original",
                "invalid_position_fraction_of_original",
            ),
        ):
            if not _optional_close(actual, expected):
                raise ValueError(f"{name} must use original observations O.")

        _validate_partition_fractions(
            (
                self.full_domain_footprint_fraction,
                self.small_island_footprint_fraction,
                self.unassigned_supported_footprint_fraction,
                self.unsupported_background_fraction,
            ),
            available=valid_area > 0.0,
            field_name="footprint fractions",
        )
        orientations = tuple(
            _orientation_float(value, "full_domain_orientations_deg")
            for value in self.full_domain_orientations_deg
        )
        dominant = self.dominant_full_domain_orientation_deg
        if dominant is None:
            if orientations:
                raise ValueError("Full domains require a dominant orientation.")
        else:
            dominant = _orientation_float(
                dominant,
                "dominant_full_domain_orientation_deg",
            )
            if not any(isclose(dominant, value, abs_tol=1e-9) for value in orientations):
                raise ValueError("Dominant orientation must belong to a full domain.")
        object.__setattr__(self, "full_domain_orientations_deg", orientations)
        object.__setattr__(self, "dominant_full_domain_orientation_deg", dominant)


@dataclass(frozen=True)
class M6HeadlessValidationFrameResult:
    frame: M6HeadlessValidationFrame
    accepted_settings: MolecularM6OrientationAnalysisSettings
    status: M6ValidationStatus
    first_shell_graph: FirstShellGraph
    analysis: M6OrientationDomainAnalysis | None
    pair_correlation: PairCorrelationResult | None
    summary: M6HeadlessValidationFrameSummary | None
    warnings: tuple[M6HeadlessValidationWarning, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.frame, M6HeadlessValidationFrame):
            raise TypeError("frame must be M6HeadlessValidationFrame.")
        if not isinstance(
            self.accepted_settings,
            MolecularM6OrientationAnalysisSettings,
        ):
            raise TypeError("accepted_settings must be M6 settings.")
        if not isinstance(self.first_shell_graph, FirstShellGraph):
            raise TypeError("first_shell_graph must be FirstShellGraph.")
        if (
            self.first_shell_graph.analysis_settings_fingerprint
            != m6_settings_fingerprint(self.accepted_settings)
        ):
            raise ValueError("Validation graph must use accepted_settings.")
        invalid_position_ids = set(self.frame.invalid_position_point_ids)
        expected_graph_ids = tuple(
            point_id
            for point_id in self.frame.point_ids
            if point_id not in invalid_position_ids
        )
        if self.first_shell_graph.point_ids != expected_graph_ids:
            raise ValueError("Validation graph must use sanitized frame point IDs.")
        _validate_pair_correlation_context(
            self.pair_correlation,
            frame=self.frame,
            graph=self.first_shell_graph,
            settings=self.accepted_settings,
        )
        if self.status == "complete":
            if (
                not isinstance(self.analysis, M6OrientationDomainAnalysis)
                or not isinstance(self.pair_correlation, PairCorrelationResult)
                or not isinstance(self.summary, M6HeadlessValidationFrameSummary)
            ):
                raise ValueError("Complete validation results require every core result.")
            if self.analysis.first_shell_graph != self.first_shell_graph:
                raise ValueError("Complete validation stages must share the graph.")
            if self.analysis.settings != self.accepted_settings:
                raise ValueError("Complete validation analysis must use accepted_settings.")
            if self.summary != _frame_summary(self.frame, self.analysis):
                raise ValueError(
                    "Frame summary must be derived from this frame and analysis."
                )
        elif self.status == "blocked_graph_fallback":
            if self.analysis is not None or self.summary is not None:
                raise ValueError("Blocked graph fallback cannot expose domain results.")
        else:
            raise ValueError(f"Unsupported validation status: {self.status!r}.")
        warnings = tuple(self.warnings)
        if any(not isinstance(item, M6HeadlessValidationWarning) for item in warnings):
            raise TypeError("warnings must contain M6HeadlessValidationWarning values.")
        if len({item.code for item in warnings}) != len(warnings):
            raise ValueError("A validation result cannot repeat a warning code.")
        warning_codes = {item.code for item in warnings}
        if (not self.frame.valid_fov_reliable) != (
            "unreliable_valid_fov" in warning_codes
        ):
            raise ValueError("Valid-FOV reliability must have an explicit warning.")
        if self.first_shell_graph.delaunay_degeneracy_qc != (
            "delaunay_degeneracy" in warning_codes
        ) and self.status == "complete":
            raise ValueError("Delaunay degeneracy must have an explicit warning.")
        if (self.status == "blocked_graph_fallback") != (
            "graph_fallback" in warning_codes
        ):
            raise ValueError("Blocking graph fallback must have an explicit warning.")
        object.__setattr__(self, "warnings", warnings)


def _validate_pair_correlation_context(
    pair_correlation: PairCorrelationResult | None,
    *,
    frame: M6HeadlessValidationFrame,
    graph: FirstShellGraph,
    settings: MolecularM6OrientationAnalysisSettings,
) -> None:
    if not isinstance(pair_correlation, PairCorrelationResult):
        raise ValueError("Validation results require a pair-correlation result.")
    representative_ids = tuple(
        point_id
        for point_id, representative_id in zip(
            graph.point_ids,
            graph.representative_source_ids,
        )
        if point_id == representative_id
    )
    expected_context = (
        frame.source_frame_index,
        representative_ids,
        graph.spatial_calibration_fingerprint,
        graph.registration_fingerprint,
        graph.point_coordinate_fingerprint,
        frame.window_origin_nm,
        frame.window_size_nm,
        frame.window_size_nm[0] * frame.window_size_nm[1],
        "rectangular_translation_correction",
    )
    actual_context = (
        pair_correlation.frame_index,
        pair_correlation.representative_point_ids,
        pair_correlation.spatial_calibration_fingerprint,
        pair_correlation.registration_fingerprint,
        pair_correlation.point_coordinate_fingerprint,
        pair_correlation.window_origin_nm,
        pair_correlation.window_size_nm,
        pair_correlation.window_area_nm2,
        pair_correlation.window_geometry_status,
    )
    if actual_context != expected_context:
        raise ValueError(
            "Pair-correlation result must use this frame, graph, and window context."
        )
    expected_edges = pair_correlation_bin_edges(
        settings.gr_bin_width_nm,
        settings.gr_max_nm,
    )
    width_nm, height_nm = frame.window_size_nm
    area_nm2 = width_nm * height_nm
    density_factor = (
        len(representative_ids) * (len(representative_ids) - 1)
        / (2.0 * area_nm2**2)
    )
    expected_exposure = tuple(
        density_factor * integral
        for integral in rectangular_annulus_overlap_integrals(
            width_nm,
            height_nm,
            expected_edges,
        )
    )
    if (
        pair_correlation.bin_edges_nm != expected_edges
        or not isclose(
            pair_correlation.min_expected_pair_exposure,
            settings.gr_min_expected_pair_exposure,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
        or not _float_sequences_close(
            pair_correlation.expected_pair_exposure,
            expected_exposure,
        )
    ):
        raise ValueError(
            "Pair-correlation result must use accepted settings and window dimensions."
        )


@dataclass(frozen=True)
class M6ConditionOrientationSummary:
    condition: str
    frame_ids: tuple[str, ...]
    source_views: tuple[M6ValidationSourceView, ...]
    dominant_full_domain_orientations_deg: tuple[float | None, ...]
    full_domain_orientations_deg: tuple[tuple[float, ...], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "condition", _non_empty_string(self.condition, "condition"))
        frame_ids = tuple(self.frame_ids)
        source_views = tuple(self.source_views)
        dominant = tuple(self.dominant_full_domain_orientations_deg)
        orientations = tuple(tuple(values) for values in self.full_domain_orientations_deg)
        lengths = {len(frame_ids), len(source_views), len(dominant), len(orientations)}
        if lengths != {len(frame_ids)} or not frame_ids:
            raise ValueError("Condition summary arrays must have one value per frame.")
        if len(set(frame_ids)) != len(frame_ids):
            raise ValueError("Condition summary frame_ids must be unique.")
        if any(view not in {"raw", "expanded_aligned"} for view in source_views):
            raise ValueError("Condition summary contains an unsupported source_view.")
        for dominant_value, values in zip(dominant, orientations):
            normalized = tuple(_orientation_float(value, "orientation") for value in values)
            if dominant_value is None:
                if normalized:
                    raise ValueError("Available domain orientations require a dominant value.")
            else:
                dominant_value = _orientation_float(dominant_value, "dominant orientation")
                if not any(isclose(dominant_value, value, abs_tol=1e-9) for value in normalized):
                    raise ValueError("Dominant orientation must occur in its frame values.")
        object.__setattr__(self, "frame_ids", frame_ids)
        object.__setattr__(self, "source_views", source_views)
        object.__setattr__(self, "dominant_full_domain_orientations_deg", dominant)
        object.__setattr__(self, "full_domain_orientations_deg", orientations)


@dataclass(frozen=True)
class M6HeadlessValidationReport:
    manifest_id: str
    algorithm_version: str
    accepted_settings: MolecularM6OrientationAnalysisSettings
    frame_results: tuple[M6HeadlessValidationFrameResult, ...]
    condition_orientation_summaries: tuple[M6ConditionOrientationSummary, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest_id", _non_empty_string(self.manifest_id, "manifest_id"))
        if self.algorithm_version != M6_ORIENTATION_ALGORITHM_VERSION:
            raise ValueError("Report algorithm_version is unsupported.")
        if not isinstance(self.accepted_settings, MolecularM6OrientationAnalysisSettings):
            raise TypeError("accepted_settings must be M6 settings.")
        results = tuple(self.frame_results)
        if not results or any(
            not isinstance(result, M6HeadlessValidationFrameResult)
            for result in results
        ):
            raise TypeError("frame_results must contain validation frame results.")
        if len({result.frame.frame_id for result in results}) != len(results):
            raise ValueError("Report frame IDs must be unique.")
        for result in results:
            if result.accepted_settings != self.accepted_settings:
                raise ValueError("Frame results must use report accepted_settings.")
            if result.analysis is not None and result.analysis.settings != self.accepted_settings:
                raise ValueError("Report analyses must use accepted_settings.")
        condition_summaries = tuple(self.condition_orientation_summaries)
        if condition_summaries != _condition_summaries(results):
            raise ValueError("Condition summaries must be derived from frame results.")
        object.__setattr__(self, "frame_results", results)
        object.__setattr__(self, "condition_orientation_summaries", condition_summaries)

    def canonical_summary(self) -> tuple[object, ...]:
        """Return a deterministic, source-ID-aware representation for regression tests."""

        return (
            self.manifest_id,
            self.algorithm_version,
            self.accepted_settings,
            tuple(
                _canonical_frame_result(result)
                for result in sorted(
                    self.frame_results,
                    key=lambda item: item.frame.frame_id,
                )
            ),
            self.condition_orientation_summaries,
        )



def _condition_summaries(
    results: tuple[M6HeadlessValidationFrameResult, ...],
) -> tuple[M6ConditionOrientationSummary, ...]:
    conditions = tuple(dict.fromkeys(result.frame.condition for result in results))
    return tuple(
        M6ConditionOrientationSummary(
            condition=condition,
            frame_ids=tuple(
                result.frame.frame_id
                for result in results
                if result.frame.condition == condition
            ),
            source_views=tuple(
                result.frame.source_view
                for result in results
                if result.frame.condition == condition
            ),
            dominant_full_domain_orientations_deg=tuple(
                None
                if result.summary is None
                else result.summary.dominant_full_domain_orientation_deg
                for result in results
                if result.frame.condition == condition
            ),
            full_domain_orientations_deg=tuple(
                ()
                if result.summary is None
                else result.summary.full_domain_orientations_deg
                for result in results
                if result.frame.condition == condition
            ),
        )
        for condition in conditions
    )


def _frame_summary(
    frame: M6HeadlessValidationFrame,
    analysis: M6OrientationDomainAnalysis,
) -> M6HeadlessValidationFrameSummary:
    aggregates = analysis.frame_aggregates
    if aggregates is None:
        raise RuntimeError("Headless validation requires frame aggregates.")
    full_domains = tuple(
        component
        for component in analysis.domain_metrics.components
        if component.component_type == "full_domain"
    )
    orientations = tuple(
        _canonical_orientation(component.orientation_deg) for component in full_domains
    )
    dominant = (
        None
        if not full_domains
        else max(
            full_domains,
            key=lambda component: (
                component.molecule_count,
                -component.ordered_component_id,
            ),
        ).orientation_deg
    )
    original_observation_count = len(frame.point_ids)
    invalid_position_count = len(frame.invalid_position_point_ids)
    return M6HeadlessValidationFrameSummary(
        original_observation_count=original_observation_count,
        valid_representative_count=aggregates.valid_representative_count,
        duplicate_excluded_count=aggregates.duplicate_excluded_count,
        invalid_position_count=invalid_position_count,
        valid_fov_area_nm2=aggregates.valid_fov_area_nm2,
        supported_area_nm2=aggregates.supported_area_nm2,
        full_domain_molecule_fraction=aggregates.full_domain_molecule_fraction,
        small_island_molecule_fraction=aggregates.small_island_molecule_fraction,
        unassigned_molecule_fraction=aggregates.unassigned_molecule_fraction,
        duplicate_excluded_fraction_of_original=(
            aggregates.duplicate_excluded_count / original_observation_count
            if original_observation_count
            else None
        ),
        invalid_position_fraction_of_original=(
            invalid_position_count / original_observation_count
            if original_observation_count
            else None
        ),
        full_domain_footprint_fraction=aggregates.full_domain_footprint_fraction,
        small_island_footprint_fraction=aggregates.small_island_footprint_fraction,
        unassigned_supported_footprint_fraction=(
            aggregates.unassigned_supported_footprint_fraction
        ),
        unsupported_background_fraction=aggregates.unsupported_background_fraction,
        full_domain_orientations_deg=orientations,
        dominant_full_domain_orientation_deg=(
            None if dominant is None else _canonical_orientation(dominant)
        ),
    )



def _canonical_frame_result(
    result: M6HeadlessValidationFrameResult,
) -> tuple[object, ...]:
    graph = result.first_shell_graph
    edge_ids = tuple(
        sorted(
            tuple(sorted((graph.point_ids[left], graph.point_ids[right])))
            for left, right in graph.edges_ij
        )
    )
    point_state: tuple[tuple[object, ...], ...] = ()
    component_memberships: tuple[tuple[str, ...], ...] = ()
    if result.analysis is not None:
        analysis = result.analysis
        point_state = tuple(
            sorted(
                (
                    source_id,
                    analysis.local_order.computation_status[index],
                    _rounded_optional(analysis.local_order.q6[index]),
                    _rounded_optional(
                        None
                        if analysis.local_order.lattice_orientation_deg[index] is None
                        else _canonical_orientation(
                            analysis.local_order.lattice_orientation_deg[index]
                        )
                    ),
                    analysis.segmentation.assignment_status[index],
                    analysis.segmentation.component_type[index],
                )
                for index, source_id in enumerate(graph.point_ids)
            )
        )
        component_memberships = tuple(
            sorted(
                tuple(sorted(component.source_ids))
                for component in analysis.segmentation.components
            )
        )
    pair_values = (
        None
        if result.pair_correlation is None
        else tuple(
            None if not isfinite(value) else round(value, 12)
            for value in result.pair_correlation.g_r
        )
    )
    return (
        result.frame.frame_id,
        result.status,
        edge_ids,
        point_state,
        component_memberships,
        _canonical_frame_summary(result.summary),
        pair_values,
        tuple(warning.code for warning in result.warnings),
    )



def _canonical_frame_summary(
    summary: M6HeadlessValidationFrameSummary | None,
) -> tuple[object, ...] | None:
    if summary is None:
        return None
    return (
        summary.original_observation_count,
        summary.valid_representative_count,
        summary.duplicate_excluded_count,
        summary.invalid_position_count,
        round(summary.valid_fov_area_nm2, 12),
        round(summary.supported_area_nm2, 12),
        _rounded_optional(summary.full_domain_molecule_fraction),
        _rounded_optional(summary.small_island_molecule_fraction),
        _rounded_optional(summary.unassigned_molecule_fraction),
        _rounded_optional(summary.duplicate_excluded_fraction_of_original),
        _rounded_optional(summary.invalid_position_fraction_of_original),
        _rounded_optional(summary.full_domain_footprint_fraction),
        _rounded_optional(summary.small_island_footprint_fraction),
        _rounded_optional(summary.unassigned_supported_footprint_fraction),
        _rounded_optional(summary.unsupported_background_fraction),
        summary.full_domain_orientations_deg,
        summary.dominant_full_domain_orientation_deg,
    )


def _rounded_optional(value: float | None) -> float | None:
    return None if value is None else round(value, 12)


def _canonical_orientation(value: float) -> float:
    normalized = round(float(value) % 60.0, 9)
    return 0.0 if normalized == 60.0 else normalized


def _finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a finite number.")
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} must be a finite number.") from exc
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def _unit_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must lie between 0 and 1.")
    return normalized


def _non_negative_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if normalized < 0.0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized


def _orientation_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if not 0.0 <= normalized < 60.0:
        raise ValueError(f"{field_name} must lie in [0, 60).")
    return normalized


def _optional_close(actual: float | None, expected: float | None) -> bool:
    if actual is None or expected is None:
        return actual is expected
    return isclose(
        _finite_float(actual, "fraction"),
        expected,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def _float_sequences_close(
    actual: tuple[float, ...],
    expected: tuple[float, ...],
) -> bool:
    return len(actual) == len(expected) and all(
        isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)
        for left, right in zip(actual, expected)
    )


def _validate_partition_fractions(
    values: tuple[float | None, ...],
    *,
    available: bool,
    field_name: str,
) -> None:
    if not available:
        if any(value is not None for value in values):
            raise ValueError(f"Unavailable {field_name} must be None.")
        return
    normalized = tuple(_unit_float(value, field_name) for value in values)
    if not isclose(fsum(normalized), 1.0, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(f"Available {field_name} must sum to one.")


def _non_negative_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise TypeError(f"{field_name} must be a non-negative integer.")
    return value


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{field_name} must be a non-empty string.")
    return value.strip()
