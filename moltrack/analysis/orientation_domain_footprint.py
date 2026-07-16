from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import fsum, isclose, isfinite, pi
from typing import Literal

import numpy as np

from ._deterministic_affine_rank import (
    deterministic_affine_rank_and_axis,
    deterministic_affine_rank_scale_nm,
)
from ._orientation_footprint_geometry import (
    Polygon,
    Rectangle,
    circle_polygon_intersection_area,
    clip_polygon_halfplane,
    convex_polygon_intersection,
    masked_window,
    point_in_window,
    polygon_area,
    rectangle_polygon,
    rectangular_window,
)
from .orientation_domain_metrics import (
    M6OrientationComponentMetrics,
    M6OrientationDomainMetrics,
)


FootprintConstructionMethod = Literal[
    "empty_partition",
    "single_point_cell",
    "two_point_bisector",
    "rank1_projection_strips",
    "rank2_bounded_voronoi",
]
FootprintCellCategory = Literal[
    "full_domain",
    "small_ordered_island",
    "unassigned",
]


@dataclass(frozen=True)
class M6SupportedFootprintFragment:
    """Exact analytic representation of ``Voronoi cell ∩ W fragment ∩ disk``."""

    window_fragment_index: int
    valid_fov_cell_polygon_xy_nm: Polygon
    support_disk_center_xy_nm: tuple[float, float]
    support_disk_radius_nm: float
    area_nm2: float

    def __post_init__(self) -> None:
        if isinstance(self.window_fragment_index, bool) or self.window_fragment_index < 0:
            raise ValueError("window_fragment_index must be a non-negative integer.")
        polygon = tuple(self.valid_fov_cell_polygon_xy_nm)
        if len(polygon) < 3:
            raise ValueError("valid_fov_cell_polygon_xy_nm must have at least 3 vertices.")
        normalized_polygon = tuple(
            (_finite_float(x, "polygon x"), _finite_float(y, "polygon y"))
            for x, y in polygon
        )
        center = tuple(self.support_disk_center_xy_nm)
        if len(center) != 2:
            raise ValueError("support_disk_center_xy_nm must contain two values.")
        normalized_center = (
            _finite_float(center[0], "support disk center x"),
            _finite_float(center[1], "support disk center y"),
        )
        radius = _positive_float(
            self.support_disk_radius_nm,
            "support_disk_radius_nm",
        )
        area = _non_negative_float(self.area_nm2, "area_nm2")
        if area > polygon_area(normalized_polygon) and not isclose(
            area,
            polygon_area(normalized_polygon),
            rel_tol=1e-10,
            abs_tol=1e-10,
        ):
            raise ValueError("Supported fragment area cannot exceed its cell polygon.")
        object.__setattr__(self, "valid_fov_cell_polygon_xy_nm", normalized_polygon)
        object.__setattr__(self, "support_disk_center_xy_nm", normalized_center)
        object.__setattr__(self, "support_disk_radius_nm", radius)
        object.__setattr__(self, "area_nm2", area)


@dataclass(frozen=True)
class M6OrientationFootprintCell:
    """One generator's globally bounded Voronoi cell and supported footprint."""

    point_index: int
    source_id: str
    category: FootprintCellCategory
    ordered_component_id: int | None
    m6_orientation_domain_id: int | None
    supported_footprint_fragments: tuple[M6SupportedFootprintFragment, ...]
    bounded_cell_area_nm2: float
    supported_area_nm2: float
    edge_truncated: bool
    molecular_mask_area_nm2: float | None

    def __post_init__(self) -> None:
        if isinstance(self.point_index, bool) or self.point_index < 0:
            raise ValueError("point_index must be a non-negative integer.")
        if not isinstance(self.source_id, str) or not self.source_id:
            raise TypeError("source_id must be a non-empty string.")
        if self.category not in {
            "full_domain",
            "small_ordered_island",
            "unassigned",
        }:
            raise ValueError("Unsupported footprint cell category.")
        if self.category == "full_domain":
            if self.ordered_component_id is None or self.m6_orientation_domain_id is None:
                raise ValueError("Full-domain cells require both component identifiers.")
        elif self.category == "small_ordered_island":
            if self.ordered_component_id is None or self.m6_orientation_domain_id is not None:
                raise ValueError("Small-island cells require only ordered_component_id.")
        elif self.ordered_component_id is not None or self.m6_orientation_domain_id is not None:
            raise ValueError("Unassigned cells cannot have component identifiers.")
        fragments = tuple(self.supported_footprint_fragments)
        if any(not isinstance(value, M6SupportedFootprintFragment) for value in fragments):
            raise TypeError(
                "supported_footprint_fragments must contain footprint fragments."
            )
        bounded_area = _non_negative_float(
            self.bounded_cell_area_nm2,
            "bounded_cell_area_nm2",
        )
        supported_area = _non_negative_float(
            self.supported_area_nm2,
            "supported_area_nm2",
        )
        if supported_area > bounded_area and not isclose(
            supported_area,
            bounded_area,
            rel_tol=1e-10,
            abs_tol=1e-10,
        ):
            raise ValueError("supported_area_nm2 cannot exceed bounded_cell_area_nm2.")
        mask_area = _optional_non_negative_float(
            self.molecular_mask_area_nm2,
            "molecular_mask_area_nm2",
        )
        if not isclose(
            bounded_area,
            fsum(
                polygon_area(fragment.valid_fov_cell_polygon_xy_nm)
                for fragment in fragments
            ),
            rel_tol=1e-10,
            abs_tol=1e-10,
        ):
            raise ValueError("bounded_cell_area_nm2 must equal the fragment polygon sum.")
        if not isclose(
            supported_area,
            fsum(fragment.area_nm2 for fragment in fragments),
            rel_tol=1e-10,
            abs_tol=1e-10,
        ):
            raise ValueError("supported_area_nm2 must equal the supported fragment sum.")
        object.__setattr__(self, "supported_footprint_fragments", fragments)
        object.__setattr__(self, "bounded_cell_area_nm2", bounded_area)
        object.__setattr__(self, "supported_area_nm2", min(supported_area, bounded_area))
        object.__setattr__(self, "molecular_mask_area_nm2", mask_area)

    @property
    def valid_fov_cell_polygons_xy_nm(self) -> tuple[Polygon, ...]:
        return tuple(
            fragment.valid_fov_cell_polygon_xy_nm
            for fragment in self.supported_footprint_fragments
        )


@dataclass(frozen=True)
class M6OrientationComponentFootprint:
    """Footprint obtained by summing global cells generated by one component."""

    component_metrics: M6OrientationComponentMetrics
    footprint_area_nm2: float
    footprint_fraction_of_valid_fov: float | None
    edge_truncated: bool
    footprint_disconnected_qc: bool
    molecular_mask_area_nm2: float | None

    def __post_init__(self) -> None:
        if not isinstance(self.component_metrics, M6OrientationComponentMetrics):
            raise TypeError("component_metrics must be M6OrientationComponentMetrics.")
        area = _non_negative_float(self.footprint_area_nm2, "footprint_area_nm2")
        if self.footprint_fraction_of_valid_fov is None:
            fraction = None
        else:
            fraction = _unit_float(
                self.footprint_fraction_of_valid_fov,
                "footprint_fraction_of_valid_fov",
            )
        if not isinstance(self.edge_truncated, bool):
            raise TypeError("edge_truncated must be a boolean.")
        if not isinstance(self.footprint_disconnected_qc, bool):
            raise TypeError("footprint_disconnected_qc must be a boolean.")
        mask_area = _optional_non_negative_float(
            self.molecular_mask_area_nm2,
            "molecular_mask_area_nm2",
        )
        object.__setattr__(self, "footprint_area_nm2", area)
        object.__setattr__(self, "footprint_fraction_of_valid_fov", fraction)
        object.__setattr__(self, "molecular_mask_area_nm2", mask_area)

    @property
    def ordered_component_id(self) -> int:
        return self.component_metrics.ordered_component_id

    @property
    def m6_orientation_domain_id(self) -> int | None:
        return self.component_metrics.m6_orientation_domain_id

    @property
    def component_type(self) -> Literal["full_domain", "small_ordered_island"]:
        return self.component_metrics.component_type

    @property
    def point_indices(self) -> tuple[int, ...]:
        return self.component_metrics.point_indices


@dataclass(frozen=True)
class M6OrientationFootprintPartition:
    """One global, disjoint footprint partition for an M6 point field."""

    domain_metrics: M6OrientationDomainMetrics
    valid_representative_point_indices: tuple[int, ...]
    cells: tuple[M6OrientationFootprintCell, ...]
    components: tuple[M6OrientationComponentFootprint, ...]
    footprint_construction_method: FootprintConstructionMethod
    footprint_support_radius_nm: float
    valid_fov_area_nm2: float
    supported_area_nm2: float
    full_domain_footprint_area_nm2: float
    small_island_footprint_area_nm2: float
    unassigned_supported_footprint_area_nm2: float
    unsupported_background_area_nm2: float
    full_domain_footprint_fraction: float | None
    small_island_footprint_fraction: float | None
    unassigned_supported_footprint_fraction: float | None
    unsupported_background_fraction: float | None
    footprint_overlap_error_nm2: float
    total_molecular_mask_area_nm2: float | None
    unassigned_molecular_mask_area_nm2: float | None
    fewer_than_3_noncollinear_points_qc: bool
    voronoi_degenerate_qc: bool
    footprint_clipped_by_fov_qc: bool
    footprint_disconnected_qc: bool
    footprint_overlap_error_qc: bool

    def __post_init__(self) -> None:
        if not isinstance(self.domain_metrics, M6OrientationDomainMetrics):
            raise TypeError("domain_metrics must be M6OrientationDomainMetrics.")
        valid_indices = tuple(self.valid_representative_point_indices)
        expected_valid_indices = tuple(
            index
            for index, status in enumerate(
                self.domain_metrics.segmentation.assignment_status
            )
            if status not in {"duplicate_excluded", "invalid_position"}
        )
        if valid_indices != expected_valid_indices:
            raise ValueError("valid_representative_point_indices must define V.")
        cells = tuple(self.cells)
        if any(not isinstance(value, M6OrientationFootprintCell) for value in cells):
            raise TypeError("cells must contain M6OrientationFootprintCell values.")
        if tuple(cell.point_index for cell in cells) != valid_indices:
            raise ValueError("cells must contain exactly one cell per point in V.")
        components = tuple(self.components)
        if any(
            not isinstance(value, M6OrientationComponentFootprint)
            for value in components
        ):
            raise TypeError(
                "components must contain M6OrientationComponentFootprint values."
            )
        if tuple(value.component_metrics for value in components) != self.domain_metrics.components:
            raise ValueError("Footprints must describe domain components in order.")

        supported_methods = {
            "empty_partition",
            "single_point_cell",
            "two_point_bisector",
            "rank1_projection_strips",
            "rank2_bounded_voronoi",
        }
        if self.footprint_construction_method not in supported_methods:
            raise ValueError("Unsupported footprint_construction_method.")
        expected_low_count_method = {
            0: "empty_partition",
            1: "single_point_cell",
            2: "two_point_bisector",
        }.get(len(valid_indices))
        if (
            expected_low_count_method is not None
            and self.footprint_construction_method != expected_low_count_method
        ):
            raise ValueError("Footprint method does not match the size of V.")
        if len(valid_indices) >= 3 and self.footprint_construction_method not in {
            "rank1_projection_strips",
            "rank2_bounded_voronoi",
        }:
            raise ValueError("At least three points require a rank-1 or rank-2 method.")

        radius = _positive_float(
            self.footprint_support_radius_nm,
            "footprint_support_radius_nm",
        )
        if radius != self.domain_metrics.settings.footprint_support_radius_nm:
            raise ValueError("Footprint support radius must come from analysis settings.")
        area_names = (
            "valid_fov_area_nm2",
            "supported_area_nm2",
            "full_domain_footprint_area_nm2",
            "small_island_footprint_area_nm2",
            "unassigned_supported_footprint_area_nm2",
            "unsupported_background_area_nm2",
            "footprint_overlap_error_nm2",
        )
        areas = {
            name: _non_negative_float(getattr(self, name), name) for name in area_names
        }
        category_area = (
            areas["full_domain_footprint_area_nm2"]
            + areas["small_island_footprint_area_nm2"]
            + areas["unassigned_supported_footprint_area_nm2"]
        )
        if not isclose(category_area, areas["supported_area_nm2"], abs_tol=1e-10):
            raise ValueError("Supported category areas must sum to supported_area_nm2.")
        if not isclose(
            areas["supported_area_nm2"] + areas["unsupported_background_area_nm2"],
            areas["valid_fov_area_nm2"],
            rel_tol=1e-10,
            abs_tol=1e-10,
        ):
            raise ValueError("Supported area and background must partition valid FOV.")
        if not isclose(
            fsum(cell.supported_area_nm2 for cell in cells),
            areas["supported_area_nm2"],
            rel_tol=1e-10,
            abs_tol=1e-10,
        ):
            raise ValueError("Cell footprints must sum to supported_area_nm2.")

        fraction_names = (
            "full_domain_footprint_fraction",
            "small_island_footprint_fraction",
            "unassigned_supported_footprint_fraction",
            "unsupported_background_fraction",
        )
        fractions = tuple(getattr(self, name) for name in fraction_names)
        if areas["valid_fov_area_nm2"] == 0.0:
            if any(value is not None for value in fractions):
                raise ValueError("Zero-area valid FOV requires undefined fractions.")
        else:
            normalized_fractions = tuple(
                _unit_float(value, name)
                for name, value in zip(fraction_names, fractions)
            )
            if not isclose(fsum(normalized_fractions), 1.0, abs_tol=1e-10):
                raise ValueError("The four footprint fractions must sum to one.")
        for component in components:
            expected_fraction = (
                None
                if areas["valid_fov_area_nm2"] == 0.0
                else component.footprint_area_nm2 / areas["valid_fov_area_nm2"]
            )
            if component.footprint_fraction_of_valid_fov != expected_fraction:
                raise ValueError("Component footprint fraction must use valid FOV area.")
        qc_values = (
            self.fewer_than_3_noncollinear_points_qc,
            self.voronoi_degenerate_qc,
            self.footprint_clipped_by_fov_qc,
            self.footprint_disconnected_qc,
            self.footprint_overlap_error_qc,
        )
        if any(not isinstance(value, bool) for value in qc_values):
            raise TypeError("Footprint QC fields must be boolean values.")
        if self.fewer_than_3_noncollinear_points_qc != (
            self.footprint_construction_method != "rank2_bounded_voronoi"
        ):
            raise ValueError("Noncollinear-point QC must match the construction method.")
        if self.footprint_clipped_by_fov_qc != any(cell.edge_truncated for cell in cells):
            raise ValueError("Clipping QC must summarize cell edge truncation.")
        if self.footprint_disconnected_qc != any(
            component.footprint_disconnected_qc for component in components
        ):
            raise ValueError("Disconnected QC must summarize component footprints.")

        object.__setattr__(self, "valid_representative_point_indices", valid_indices)
        object.__setattr__(self, "cells", cells)
        object.__setattr__(self, "components", components)
        object.__setattr__(self, "footprint_support_radius_nm", radius)
        for name, value in areas.items():
            object.__setattr__(self, name, value)

    def component_for_ordered_id(
        self,
        ordered_component_id: int,
    ) -> M6OrientationComponentFootprint:
        try:
            return self.components[ordered_component_id]
        except (IndexError, TypeError) as exc:
            raise KeyError(f"Unknown ordered_component_id: {ordered_component_id}.") from exc


def compute_m6_orientation_footprint_partition(
    points_xy_nm: object,
    *,
    domain_metrics: M6OrientationDomainMetrics,
    window_geometry: Literal["rectangular", "irregular"],
    window_size_nm: tuple[float, float] | None = None,
    valid_fov_mask: object | None = None,
    valid_fov_pixel_size_nm: tuple[float, float] | None = None,
    window_origin_nm: tuple[float, float] = (0.0, 0.0),
    molecular_mask_area_nm2: Sequence[float | None] | None = None,
) -> M6OrientationFootprintPartition:
    """Build a global bounded Voronoi partition and support-limited footprints."""

    if not isinstance(domain_metrics, M6OrientationDomainMetrics):
        raise TypeError("domain_metrics must be M6OrientationDomainMetrics.")
    points = np.asarray(points_xy_nm, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("points_xy_nm must have shape [N, 2].")
    if len(points) != domain_metrics.point_count:
        raise ValueError("points_xy_nm must match domain_metrics point count.")
    rectangles = _window_rectangles(
        window_geometry,
        window_size_nm=window_size_nm,
        valid_fov_mask=valid_fov_mask,
        valid_fov_pixel_size_nm=valid_fov_pixel_size_nm,
        window_origin_nm=window_origin_nm,
    )
    valid_fov_area = fsum(
        (max_x - min_x) * (max_y - min_y)
        for min_x, min_y, max_x, max_y in rectangles
    )
    settings = domain_metrics.settings
    rank_scale = deterministic_affine_rank_scale_nm(
        points,
        minimum_scale_nm=settings.first_shell_r_max_nm,
    )
    geometry_scale = max(rank_scale, valid_fov_area**0.5)
    tolerance = max(
        settings.geometry_absolute_tolerance_nm,
        settings.geometry_relative_tolerance * geometry_scale,
    )
    valid_indices = tuple(
        index
        for index, status in enumerate(domain_metrics.segmentation.assignment_status)
        if status not in {"duplicate_excluded", "invalid_position"}
    )
    for index in valid_indices:
        if not bool(np.all(np.isfinite(points[index]))):
            raise ValueError("Valid representatives must have finite positions.")
        if not point_in_window(points[index], rectangles, tolerance=tolerance):
            raise ValueError("Valid representatives must lie inside valid FOV W.")
    mask_areas = _normalize_mask_areas(molecular_mask_area_nm2, point_count=len(points))
    method, constraints, voronoi_degenerate = _partition_constraints(
        points,
        valid_indices=valid_indices,
        source_ids=domain_metrics.source_ids,
        relative_tolerance=settings.geometry_relative_tolerance,
        scale=rank_scale,
    )
    radius = settings.footprint_support_radius_nm
    cells = tuple(
        _build_cell(
            point_index,
            points=points,
            domain_metrics=domain_metrics,
            rectangles=rectangles,
            constraints=constraints[position],
            radius=radius,
            tolerance=tolerance,
            mask_area=(None if mask_areas is None else mask_areas[point_index]),
        )
        for position, point_index in enumerate(valid_indices)
    )
    component_footprints = tuple(
        _component_footprint(
            component,
            cells=cells,
            valid_fov_area=valid_fov_area,
            tolerance=tolerance,
        )
        for component in domain_metrics.components
    )
    full_area = fsum(
        cell.supported_area_nm2 for cell in cells if cell.category == "full_domain"
    )
    small_area = fsum(
        cell.supported_area_nm2
        for cell in cells
        if cell.category == "small_ordered_island"
    )
    unassigned_area = fsum(
        cell.supported_area_nm2 for cell in cells if cell.category == "unassigned"
    )
    supported_area = full_area + small_area + unassigned_area
    unsupported_area = max(0.0, valid_fov_area - supported_area)
    overlap_error = _global_cell_overlap_area(cells, tolerance=tolerance)
    area_tolerance = max(
        tolerance * tolerance,
        settings.geometry_relative_tolerance * max(1.0, valid_fov_area),
    )
    fractions = _area_fractions(
        valid_fov_area,
        full_area,
        small_area,
        unassigned_area,
        unsupported_area,
    )
    measured_mask_values = (
        ()
        if mask_areas is None
        else tuple(
            mask_areas[index]
            for index in valid_indices
            if mask_areas[index] is not None
        )
    )
    unassigned_mask_values = tuple(
        cell.molecular_mask_area_nm2
        for cell in cells
        if cell.category == "unassigned" and cell.molecular_mask_area_nm2 is not None
    )
    disconnected = any(value.footprint_disconnected_qc for value in component_footprints)
    clipped = any(cell.edge_truncated for cell in cells)
    return M6OrientationFootprintPartition(
        domain_metrics=domain_metrics,
        valid_representative_point_indices=valid_indices,
        cells=cells,
        components=component_footprints,
        footprint_construction_method=method,
        footprint_support_radius_nm=radius,
        valid_fov_area_nm2=valid_fov_area,
        supported_area_nm2=supported_area,
        full_domain_footprint_area_nm2=full_area,
        small_island_footprint_area_nm2=small_area,
        unassigned_supported_footprint_area_nm2=unassigned_area,
        unsupported_background_area_nm2=unsupported_area,
        full_domain_footprint_fraction=fractions[0],
        small_island_footprint_fraction=fractions[1],
        unassigned_supported_footprint_fraction=fractions[2],
        unsupported_background_fraction=fractions[3],
        footprint_overlap_error_nm2=overlap_error,
        total_molecular_mask_area_nm2=(
            None
            if mask_areas is None or not measured_mask_values
            else fsum(measured_mask_values)
        ),
        unassigned_molecular_mask_area_nm2=(
            None
            if mask_areas is None or not unassigned_mask_values
            else fsum(unassigned_mask_values)
        ),
        fewer_than_3_noncollinear_points_qc=(
            method != "rank2_bounded_voronoi"
        ),
        voronoi_degenerate_qc=voronoi_degenerate,
        footprint_clipped_by_fov_qc=clipped,
        footprint_disconnected_qc=disconnected,
        footprint_overlap_error_qc=overlap_error > area_tolerance,
    )


def _window_rectangles(
    window_geometry: object,
    *,
    window_size_nm: object,
    valid_fov_mask: object,
    valid_fov_pixel_size_nm: object,
    window_origin_nm: object,
) -> tuple[Rectangle, ...]:
    if window_geometry == "rectangular":
        if window_size_nm is None:
            raise ValueError("Rectangular valid FOV requires window_size_nm.")
        return rectangular_window(window_size_nm, window_origin_nm)
    if window_geometry == "irregular":
        if valid_fov_mask is None or valid_fov_pixel_size_nm is None:
            raise ValueError(
                "Irregular valid FOV requires valid_fov_mask and valid_fov_pixel_size_nm."
            )
        return masked_window(valid_fov_mask, valid_fov_pixel_size_nm, window_origin_nm)
    raise ValueError("window_geometry must be 'rectangular' or 'irregular'.")


def _partition_constraints(
    points: np.ndarray,
    *,
    valid_indices: tuple[int, ...],
    source_ids: tuple[str, ...],
    relative_tolerance: float,
    scale: float,
) -> tuple[
    FootprintConstructionMethod,
    tuple[tuple[tuple[np.ndarray, float], ...], ...],
    bool,
]:
    count = len(valid_indices)
    if count == 0:
        return "empty_partition", (), False
    if count == 1:
        return "single_point_cell", ((),), False
    valid_points = points[np.asarray(valid_indices, dtype=np.int64)]
    if count == 2:
        return (
            "two_point_bisector",
            tuple(
                (
                    _bisector_constraint(
                        valid_points[position],
                        valid_points[1 - position],
                    ),
                )
                for position in range(2)
            ),
            False,
        )
    try:
        rank, projection_axis = deterministic_affine_rank_and_axis(
            valid_points,
            scale_nm=scale,
            relative_tolerance=relative_tolerance,
        )
    except np.linalg.LinAlgError:
        return "rank2_bounded_voronoi", _rank2_constraints(valid_points), True
    if rank == 0:
        raise ValueError(
            "Valid representatives contain unresolved coincident positions."
        )
    if rank == 1:
        assert projection_axis is not None
        projections = valid_points @ projection_axis
        order = sorted(
            range(count),
            key=lambda position: (
                float(projections[position]),
                source_ids[valid_indices[position]],
            ),
        )
        neighbors: list[list[int]] = [[] for _ in range(count)]
        for left, right in zip(order, order[1:]):
            neighbors[left].append(right)
            neighbors[right].append(left)
        constraints = tuple(
            tuple(
                _bisector_constraint(valid_points[position], valid_points[other])
                for other in neighbors[position]
            )
            for position in range(count)
        )
        return "rank1_projection_strips", constraints, False
    return "rank2_bounded_voronoi", _rank2_constraints(valid_points), False


def _rank2_constraints(
    valid_points: np.ndarray,
) -> tuple[tuple[tuple[np.ndarray, float], ...], ...]:
    count = len(valid_points)
    return tuple(
        tuple(
            _bisector_constraint(valid_points[position], valid_points[other])
            for other in range(count)
            if other != position
        )
        for position in range(count)
    )


def _bisector_constraint(
    generator: np.ndarray,
    other: np.ndarray,
) -> tuple[np.ndarray, float]:
    normal = 2.0 * (other - generator)
    offset = float(other @ other - generator @ generator)
    return normal, offset


def _build_cell(
    point_index: int,
    *,
    points: np.ndarray,
    domain_metrics: M6OrientationDomainMetrics,
    rectangles: tuple[Rectangle, ...],
    constraints: tuple[tuple[np.ndarray, float], ...],
    radius: float,
    tolerance: float,
    mask_area: float | None,
) -> M6OrientationFootprintCell:
    if rectangles:
        bounding_rectangle = (
            min(value[0] for value in rectangles),
            min(value[1] for value in rectangles),
            max(value[2] for value in rectangles),
            max(value[3] for value in rectangles),
        )
        bounded_cell = rectangle_polygon(bounding_rectangle)
    else:
        bounded_cell = ()
    for normal, offset in constraints:
        bounded_cell = clip_polygon_halfplane(
            bounded_cell,
            normal=normal,
            offset=offset,
            tolerance=tolerance,
        )
        if not bounded_cell:
            break
    fragments: list[M6SupportedFootprintFragment] = []
    for window_fragment_index, rectangle in enumerate(rectangles):
        polygon = _clip_polygon_to_rectangle(
            bounded_cell,
            rectangle=rectangle,
            tolerance=tolerance,
        )
        if polygon_area(polygon) > tolerance * tolerance:
            supported_fragment_area = circle_polygon_intersection_area(
                polygon,
                center=points[point_index],
                radius=radius,
                tolerance=tolerance,
            )
            fragments.append(
                M6SupportedFootprintFragment(
                    window_fragment_index=window_fragment_index,
                    valid_fov_cell_polygon_xy_nm=polygon,
                    support_disk_center_xy_nm=(
                        float(points[point_index, 0]),
                        float(points[point_index, 1]),
                    ),
                    support_disk_radius_nm=radius,
                    area_nm2=supported_fragment_area,
                )
            )
    bounded_area = fsum(
        polygon_area(fragment.valid_fov_cell_polygon_xy_nm)
        for fragment in fragments
    )
    supported_area = fsum(fragment.area_nm2 for fragment in fragments)
    disk_in_window_area = fsum(
        circle_polygon_intersection_area(
            rectangle_polygon(rectangle),
            center=points[point_index],
            radius=radius,
            tolerance=tolerance,
        )
        for rectangle in rectangles
    )
    segmentation = domain_metrics.segmentation
    category = segmentation.component_type[point_index]
    ordered_id = segmentation.ordered_component_id[point_index]
    domain_id = segmentation.m6_orientation_domain_id[point_index]
    return M6OrientationFootprintCell(
        point_index=point_index,
        source_id=segmentation.source_ids[point_index],
        category=category,
        ordered_component_id=None if ordered_id < 0 else ordered_id,
        m6_orientation_domain_id=None if domain_id < 0 else domain_id,
        supported_footprint_fragments=tuple(fragments),
        bounded_cell_area_nm2=bounded_area,
        supported_area_nm2=min(supported_area, bounded_area),
        edge_truncated=(
            disk_in_window_area < pi * max(0.0, radius - tolerance) ** 2
        ),
        molecular_mask_area_nm2=mask_area,
    )


def _clip_polygon_to_rectangle(
    polygon: Polygon,
    *,
    rectangle: Rectangle,
    tolerance: float,
) -> Polygon:
    min_x, min_y, max_x, max_y = rectangle
    constraints = (
        (np.asarray((1.0, 0.0)), max_x),
        (np.asarray((-1.0, 0.0)), -min_x),
        (np.asarray((0.0, 1.0)), max_y),
        (np.asarray((0.0, -1.0)), -min_y),
    )
    clipped = polygon
    for normal, offset in constraints:
        clipped = clip_polygon_halfplane(
            clipped,
            normal=normal,
            offset=offset,
            tolerance=tolerance,
        )
        if not clipped:
            break
    return clipped


def _component_footprint(
    component: M6OrientationComponentMetrics,
    *,
    cells: tuple[M6OrientationFootprintCell, ...],
    valid_fov_area: float,
    tolerance: float,
) -> M6OrientationComponentFootprint:
    member_cells = tuple(
        cell for cell in cells if cell.ordered_component_id == component.ordered_component_id
    )
    area = fsum(cell.supported_area_nm2 for cell in member_cells)
    mask_values = tuple(
        cell.molecular_mask_area_nm2
        for cell in member_cells
        if cell.molecular_mask_area_nm2 is not None
    )
    return M6OrientationComponentFootprint(
        component_metrics=component,
        footprint_area_nm2=area,
        footprint_fraction_of_valid_fov=(
            area / valid_fov_area if valid_fov_area > 0.0 else None
        ),
        edge_truncated=any(cell.edge_truncated for cell in member_cells),
        footprint_disconnected_qc=_component_is_disconnected(
            member_cells,
            tolerance=tolerance,
        ),
        molecular_mask_area_nm2=(
            None
            if all(cell.molecular_mask_area_nm2 is None for cell in member_cells)
            else fsum(mask_values)
        ),
    )


def _component_is_disconnected(
    cells: tuple[M6OrientationFootprintCell, ...],
    *,
    tolerance: float,
) -> bool:
    fragments = tuple(
        fragment
        for cell in cells
        for fragment in cell.supported_footprint_fragments
        if fragment.area_nm2 > tolerance * tolerance
    )
    if len(fragments) < 2:
        return False
    unseen = set(range(len(fragments)))
    stack = [unseen.pop()]
    while stack:
        current = stack.pop()
        connected = {
            other
            for other in unseen
            if _supported_fragments_touch(
                fragments[current],
                fragments[other],
                tolerance=tolerance,
            )
        }
        unseen.difference_update(connected)
        stack.extend(connected)
    return bool(unseen)


def _supported_fragments_touch(
    left: M6SupportedFootprintFragment,
    right: M6SupportedFootprintFragment,
    *,
    tolerance: float,
) -> bool:
    intersection = convex_polygon_intersection(
        left.valid_fov_cell_polygon_xy_nm,
        right.valid_fov_cell_polygon_xy_nm,
        tolerance=tolerance,
    )
    left_center = np.asarray(left.support_disk_center_xy_nm, dtype=np.float64)
    right_center = np.asarray(right.support_disk_center_xy_nm, dtype=np.float64)
    candidates = list(intersection)
    for start, end in zip(intersection, intersection[1:] + intersection[:1]):
        for center in (left_center, right_center):
            candidates.append(_closest_point_on_segment(center, start, end))
    return any(
        float(np.linalg.norm(np.asarray(point) - left_center))
        <= left.support_disk_radius_nm + tolerance
        and float(np.linalg.norm(np.asarray(point) - right_center))
        <= right.support_disk_radius_nm + tolerance
        for point in candidates
    )


def _closest_point_on_segment(
    point: np.ndarray,
    start_value: tuple[float, float],
    end_value: tuple[float, float],
) -> tuple[float, float]:
    start = np.asarray(start_value, dtype=np.float64)
    direction = np.asarray(end_value, dtype=np.float64) - start
    squared_length = float(direction @ direction)
    if squared_length == 0.0:
        return float(start[0]), float(start[1])
    fraction = min(1.0, max(0.0, float((point - start) @ direction) / squared_length))
    closest = start + fraction * direction
    return float(closest[0]), float(closest[1])


def _global_cell_overlap_area(
    cells: tuple[M6OrientationFootprintCell, ...],
    *,
    tolerance: float,
) -> float:
    fragments_by_window: dict[
        int,
        list[tuple[int, M6SupportedFootprintFragment]],
    ] = {}
    for cell in cells:
        for fragment in cell.supported_footprint_fragments:
            fragments_by_window.setdefault(fragment.window_fragment_index, []).append(
                (cell.point_index, fragment)
            )
    overlap_area = 0.0
    for fragments in fragments_by_window.values():
        for left_index, (left_point_index, left) in enumerate(fragments):
            for right_point_index, right in fragments[left_index + 1 :]:
                if left_point_index == right_point_index:
                    continue
                intersection = convex_polygon_intersection(
                    left.valid_fov_cell_polygon_xy_nm,
                    right.valid_fov_cell_polygon_xy_nm,
                    tolerance=0.0,
                )
                overlap_area += min(
                    circle_polygon_intersection_area(
                        intersection,
                        center=np.asarray(left.support_disk_center_xy_nm),
                        radius=left.support_disk_radius_nm,
                        tolerance=tolerance,
                    ),
                    circle_polygon_intersection_area(
                        intersection,
                        center=np.asarray(right.support_disk_center_xy_nm),
                        radius=right.support_disk_radius_nm,
                        tolerance=tolerance,
                    ),
                )
    return overlap_area


def _normalize_mask_areas(
    values: Sequence[float | None] | None,
    *,
    point_count: int,
) -> tuple[float | None, ...] | None:
    if values is None:
        return None
    normalized = tuple(values)
    if len(normalized) != point_count:
        raise ValueError("molecular_mask_area_nm2 must contain one value per point.")
    return tuple(
        _optional_non_negative_float(value, f"molecular_mask_area_nm2[{index}]")
        for index, value in enumerate(normalized)
    )


def _area_fractions(
    valid_fov_area: float,
    full_area: float,
    small_area: float,
    unassigned_area: float,
    unsupported_area: float,
) -> tuple[float | None, float | None, float | None, float | None]:
    if valid_fov_area <= 0.0:
        return None, None, None, None
    return tuple(
        value / valid_fov_area
        for value in (full_area, small_area, unassigned_area, unsupported_area)
    )  # type: ignore[return-value]


def _non_negative_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a number.")
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be a number.") from exc
    if not isfinite(normalized) or normalized < 0.0:
        raise ValueError(f"{field_name} must be a finite non-negative number.")
    return normalized


def _finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a number.")
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be a number.") from exc
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def _positive_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _unit_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must lie between 0 and 1.")
    return normalized


def _optional_non_negative_float(value: object, field_name: str) -> float | None:
    return None if value is None else _non_negative_float(value, field_name)
