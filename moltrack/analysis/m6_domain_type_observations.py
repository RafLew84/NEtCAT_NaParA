from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite
from numbers import Real
from typing import Literal

from .m6_domain_type_settings import M6DomainTypeClassificationSettings
from .range_analysis import MolecularFrameRangeAnalysis
from .range_comparison import MolecularFrameRangeComparison


M6DomainTypeQualificationStatus = Literal["qualified", "unclassified"]
M6DomainTypeUnclassifiedReason = Literal[
    "small_ordered_island_excluded",
    "missing_bond_length_statistics",
    "bond_length_heterogeneity_qc",
]

_COMPONENT_TYPES = {"full_domain", "small_ordered_island"}
_UNCLASSIFIED_REASONS = {
    "small_ordered_island_excluded",
    "missing_bond_length_statistics",
    "bond_length_heterogeneity_qc",
}


@dataclass(frozen=True)
class M6DomainTypeObservation:
    """Classification-ready snapshot of one spatial M6 component in one frame."""

    range_name: str
    range_start_frame: int
    range_end_frame: int
    frame_index: int
    source_frame_index: int
    ordered_component_id: int
    m6_orientation_domain_id: int | None
    component_type: Literal["full_domain", "small_ordered_island"]
    qualification_status: M6DomainTypeQualificationStatus
    unclassified_reason: M6DomainTypeUnclassifiedReason | None
    orientation_deg: float
    molecule_count: int
    molecule_fraction_of_valid_representatives: float
    footprint_area_nm2: float
    footprint_fraction_of_valid_fov: float | None
    molecular_mask_area_nm2: float | None
    domain_mean_local_q6: float
    domain_coherent_q6: float
    centroid_x_nm: float
    centroid_y_nm: float
    min_x_nm: float
    min_y_nm: float
    max_x_nm: float
    max_y_nm: float
    internal_first_shell_bond_count: int
    domain_median_bond_length_nm: float | None
    domain_bond_length_mad_nm: float | None
    domain_bond_length_iqr_nm: float | None
    domain_bond_length_robust_cv: float | None
    insufficient_bonds_for_length_stats_qc: bool
    bond_length_heterogeneity_qc: bool
    edge_truncated: bool
    footprint_disconnected_qc: bool

    def __post_init__(self) -> None:
        range_name = _non_empty_string(self.range_name, "range_name")
        range_start_frame = _non_negative_int(
            self.range_start_frame,
            "range_start_frame",
        )
        range_end_frame = _non_negative_int(
            self.range_end_frame,
            "range_end_frame",
        )
        if range_start_frame > range_end_frame:
            raise ValueError("range_start_frame must not exceed range_end_frame.")
        frame_index = _non_negative_int(self.frame_index, "frame_index")
        if not range_start_frame <= frame_index <= range_end_frame:
            raise ValueError("frame_index must lie within the observation range.")
        source_frame_index = _non_negative_int(
            self.source_frame_index,
            "source_frame_index",
        )
        ordered_component_id = _non_negative_int(
            self.ordered_component_id,
            "ordered_component_id",
        )
        if self.m6_orientation_domain_id is None:
            domain_id = None
        else:
            domain_id = _non_negative_int(
                self.m6_orientation_domain_id,
                "m6_orientation_domain_id",
            )
        if self.component_type not in _COMPONENT_TYPES:
            raise ValueError(f"Unsupported component_type: {self.component_type!r}.")
        if self.component_type == "full_domain" and domain_id is None:
            raise ValueError("A full_domain observation requires a domain ID.")
        if self.component_type == "small_ordered_island" and domain_id is not None:
            raise ValueError("A small ordered island cannot have a domain ID.")

        qualification_status = self.qualification_status
        reason = self.unclassified_reason
        if qualification_status not in {"qualified", "unclassified"}:
            raise ValueError("Unsupported qualification_status.")
        if qualification_status == "qualified":
            if reason is not None:
                raise ValueError("A qualified observation cannot have an unclassified reason.")
        elif reason not in _UNCLASSIFIED_REASONS:
            raise ValueError("An unclassified observation requires a supported reason.")

        orientation = _normalize_m6_orientation(self.orientation_deg)
        molecule_count = _positive_int(self.molecule_count, "molecule_count")
        molecule_fraction = _unit_float(
            self.molecule_fraction_of_valid_representatives,
            "molecule_fraction_of_valid_representatives",
        )
        footprint_area = _non_negative_float(
            self.footprint_area_nm2,
            "footprint_area_nm2",
        )
        footprint_fraction = _optional_unit_float(
            self.footprint_fraction_of_valid_fov,
            "footprint_fraction_of_valid_fov",
        )
        molecular_mask_area = _optional_non_negative_float(
            self.molecular_mask_area_nm2,
            "molecular_mask_area_nm2",
        )
        mean_local_q6 = _unit_float(self.domain_mean_local_q6, "domain_mean_local_q6")
        coherent_q6 = _unit_float(self.domain_coherent_q6, "domain_coherent_q6")
        if coherent_q6 > mean_local_q6 and not isclose(
            coherent_q6,
            mean_local_q6,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("domain_coherent_q6 cannot exceed domain_mean_local_q6.")

        centroid_x = _finite_float(self.centroid_x_nm, "centroid_x_nm")
        centroid_y = _finite_float(self.centroid_y_nm, "centroid_y_nm")
        min_x = _finite_float(self.min_x_nm, "min_x_nm")
        min_y = _finite_float(self.min_y_nm, "min_y_nm")
        max_x = _finite_float(self.max_x_nm, "max_x_nm")
        max_y = _finite_float(self.max_y_nm, "max_y_nm")
        if not (min_x <= centroid_x <= max_x and min_y <= centroid_y <= max_y):
            raise ValueError("Observation centroid must lie within its bounds.")

        bond_count = _non_negative_int(
            self.internal_first_shell_bond_count,
            "internal_first_shell_bond_count",
        )
        bond_statistics = _bond_statistics(
            self.domain_median_bond_length_nm,
            self.domain_bond_length_mad_nm,
            self.domain_bond_length_iqr_nm,
            self.domain_bond_length_robust_cv,
        )
        for field_name in (
            "insufficient_bonds_for_length_stats_qc",
            "bond_length_heterogeneity_qc",
            "edge_truncated",
            "footprint_disconnected_qc",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be a boolean.")
        statistics_missing = bond_statistics[0] is None
        if self.insufficient_bonds_for_length_stats_qc != statistics_missing:
            raise ValueError(
                "insufficient_bonds_for_length_stats_qc must indicate missing statistics."
            )
        if statistics_missing and self.bond_length_heterogeneity_qc:
            raise ValueError("Missing bond statistics cannot be heterogeneous.")
        if qualification_status == "qualified" and statistics_missing:
            raise ValueError("A qualified observation requires bond-length statistics.")
        if reason == "small_ordered_island_excluded" and (
            self.component_type != "small_ordered_island"
        ):
            raise ValueError("Small-island exclusion requires a small ordered island.")
        if reason == "missing_bond_length_statistics" and not statistics_missing:
            raise ValueError("Missing-statistics reason requires missing statistics.")
        if reason == "bond_length_heterogeneity_qc" and not (
            self.bond_length_heterogeneity_qc
        ):
            raise ValueError("Heterogeneity reason requires its QC flag.")

        normalized_values = {
            "range_name": range_name,
            "range_start_frame": range_start_frame,
            "range_end_frame": range_end_frame,
            "frame_index": frame_index,
            "source_frame_index": source_frame_index,
            "ordered_component_id": ordered_component_id,
            "m6_orientation_domain_id": domain_id,
            "orientation_deg": orientation,
            "molecule_count": molecule_count,
            "molecule_fraction_of_valid_representatives": molecule_fraction,
            "footprint_area_nm2": footprint_area,
            "footprint_fraction_of_valid_fov": footprint_fraction,
            "molecular_mask_area_nm2": molecular_mask_area,
            "domain_mean_local_q6": mean_local_q6,
            "domain_coherent_q6": coherent_q6,
            "centroid_x_nm": centroid_x,
            "centroid_y_nm": centroid_y,
            "min_x_nm": min_x,
            "min_y_nm": min_y,
            "max_x_nm": max_x,
            "max_y_nm": max_y,
            "internal_first_shell_bond_count": bond_count,
            "domain_median_bond_length_nm": bond_statistics[0],
            "domain_bond_length_mad_nm": bond_statistics[1],
            "domain_bond_length_iqr_nm": bond_statistics[2],
            "domain_bond_length_robust_cv": bond_statistics[3],
        }
        for field_name, value in normalized_values.items():
            object.__setattr__(self, field_name, value)

    @property
    def stable_key(self) -> tuple[str, int, int, int, int, int, int | None]:
        return (
            self.range_name,
            self.range_start_frame,
            self.range_end_frame,
            self.frame_index,
            self.source_frame_index,
            self.ordered_component_id,
            self.m6_orientation_domain_id,
        )

    @property
    def bounds_xyxy_nm(self) -> tuple[float, float, float, float]:
        return self.min_x_nm, self.min_y_nm, self.max_x_nm, self.max_y_nm


def extract_m6_domain_type_observations(
    result: MolecularFrameRangeAnalysis | MolecularFrameRangeComparison,
    *,
    settings: M6DomainTypeClassificationSettings,
) -> tuple[M6DomainTypeObservation, ...]:
    """Snapshot existing M6 range results without repeating structural analysis."""

    if not isinstance(settings, M6DomainTypeClassificationSettings):
        raise TypeError("settings must be M6DomainTypeClassificationSettings.")
    if isinstance(result, MolecularFrameRangeAnalysis):
        range_analyses = (result,)
    elif isinstance(result, MolecularFrameRangeComparison):
        range_analyses = (result.first_analysis, result.second_analysis)
    else:
        raise TypeError("result must contain one or two molecular frame ranges.")

    observations = []
    for range_analysis in range_analyses:
        for frame_result in sorted(
            range_analysis.frame_results,
            key=lambda value: (value.frame_index, value.source_frame_index),
        ):
            m6_analysis = frame_result.m6_orientation_analysis
            if m6_analysis is None:
                continue
            frame_aggregates = m6_analysis.frame_aggregates
            footprint_partition = frame_aggregates.footprint_partition
            for component in sorted(
                frame_aggregates.domain_metrics.components,
                key=lambda value: value.ordered_component_id,
            ):
                footprint = footprint_partition.component_for_ordered_id(
                    component.ordered_component_id
                )
                qualification_status, reason = _qualification(
                    component_type=component.component_type,
                    missing_bond_statistics=(
                        component.domain_median_bond_length_nm is None
                    ),
                    bond_length_heterogeneity_qc=(
                        component.bond_length_heterogeneity_qc
                    ),
                    settings=settings,
                )
                observations.append(
                    M6DomainTypeObservation(
                        range_name=range_analysis.frame_range.name,
                        range_start_frame=range_analysis.frame_range.start_frame,
                        range_end_frame=range_analysis.frame_range.end_frame,
                        frame_index=frame_result.frame_index,
                        source_frame_index=frame_result.source_frame_index,
                        ordered_component_id=component.ordered_component_id,
                        m6_orientation_domain_id=(
                            component.m6_orientation_domain_id
                        ),
                        component_type=component.component_type,
                        qualification_status=qualification_status,
                        unclassified_reason=reason,
                        orientation_deg=component.orientation_deg,
                        molecule_count=component.molecule_count,
                        molecule_fraction_of_valid_representatives=(
                            component.molecule_fraction_of_valid_representatives
                        ),
                        footprint_area_nm2=footprint.footprint_area_nm2,
                        footprint_fraction_of_valid_fov=(
                            footprint.footprint_fraction_of_valid_fov
                        ),
                        molecular_mask_area_nm2=footprint.molecular_mask_area_nm2,
                        domain_mean_local_q6=component.domain_mean_local_q6,
                        domain_coherent_q6=component.domain_coherent_q6,
                        centroid_x_nm=component.centroid_x_nm,
                        centroid_y_nm=component.centroid_y_nm,
                        min_x_nm=component.min_x_nm,
                        min_y_nm=component.min_y_nm,
                        max_x_nm=component.max_x_nm,
                        max_y_nm=component.max_y_nm,
                        internal_first_shell_bond_count=(
                            component.internal_first_shell_bond_count
                        ),
                        domain_median_bond_length_nm=(
                            component.domain_median_bond_length_nm
                        ),
                        domain_bond_length_mad_nm=(
                            component.domain_bond_length_mad_nm
                        ),
                        domain_bond_length_iqr_nm=(
                            component.domain_bond_length_iqr_nm
                        ),
                        domain_bond_length_robust_cv=(
                            component.domain_bond_length_robust_cv
                        ),
                        insufficient_bonds_for_length_stats_qc=(
                            component.insufficient_bonds_for_length_stats_qc
                        ),
                        bond_length_heterogeneity_qc=(
                            component.bond_length_heterogeneity_qc
                        ),
                        edge_truncated=footprint.edge_truncated,
                        footprint_disconnected_qc=(
                            footprint.footprint_disconnected_qc
                        ),
                    )
                )
    return tuple(observations)


def _qualification(
    *,
    component_type: str,
    missing_bond_statistics: bool,
    bond_length_heterogeneity_qc: bool,
    settings: M6DomainTypeClassificationSettings,
) -> tuple[M6DomainTypeQualificationStatus, M6DomainTypeUnclassifiedReason | None]:
    if (
        component_type == "small_ordered_island"
        and not settings.include_small_ordered_islands
    ):
        return "unclassified", "small_ordered_island_excluded"
    if missing_bond_statistics:
        return "unclassified", "missing_bond_length_statistics"
    if (
        bond_length_heterogeneity_qc
        and settings.exclude_bond_length_heterogeneity_qc
    ):
        return "unclassified", "bond_length_heterogeneity_qc"
    return "qualified", None


def _bond_statistics(
    median: object,
    mad: object,
    iqr: object,
    robust_cv: object,
) -> tuple[float | None, float | None, float | None, float | None]:
    values = (median, mad, iqr, robust_cv)
    if all(value is None for value in values):
        return None, None, None, None
    if any(value is None for value in values):
        raise ValueError("Bond-length statistics must be all present or all None.")
    return (
        _positive_float(median, "domain_median_bond_length_nm"),
        _non_negative_float(mad, "domain_bond_length_mad_nm"),
        _non_negative_float(iqr, "domain_bond_length_iqr_nm"),
        _non_negative_float(robust_cv, "domain_bond_length_robust_cv"),
    )


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _non_negative_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return value


def _positive_int(value: object, field_name: str) -> int:
    normalized = _non_negative_int(value, field_name)
    if normalized == 0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number.")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def _normalize_m6_orientation(value: object) -> float:
    orientation = _finite_float(value, "orientation_deg") % 60.0
    if isclose(orientation, 0.0, abs_tol=1e-12) or isclose(
        orientation,
        60.0,
        abs_tol=1e-12,
    ):
        return 0.0
    return orientation


def _positive_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _non_negative_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if normalized < 0.0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized


def _unit_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1.")
    return normalized


def _optional_unit_float(value: object, field_name: str) -> float | None:
    return None if value is None else _unit_float(value, field_name)


def _optional_non_negative_float(value: object, field_name: str) -> float | None:
    return None if value is None else _non_negative_float(value, field_name)
