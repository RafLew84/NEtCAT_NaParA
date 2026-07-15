from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, pi
from typing import Literal


OrientationReference = Literal[
    "+x_sample_axis",
    "scan_x_axis_assumed_sample_x",
]
FirstShellConstructionMethod = Literal[
    "rank0_empty",
    "rank1_adjacent_projection",
    "delaunay_first_shell",
    "rank2_radius_fallback",
]

_ORIENTATION_REFERENCES = {
    "+x_sample_axis",
    "scan_x_axis_assumed_sample_x",
}
_CONSTRUCTION_METHODS = {
    "rank0_empty",
    "rank1_adjacent_projection",
    "delaunay_first_shell",
    "rank2_radius_fallback",
}


@dataclass(frozen=True)
class FirstShellGraph:
    """Immutable first-shell neighbor graph in calibrated sample coordinates."""

    point_ids: tuple[str, ...]
    point_count: int
    edges_ij: tuple[tuple[int, int], ...]
    distances_nm: tuple[float, ...]
    angles_rad: tuple[float, ...]
    degree: tuple[int, ...]
    geometry_collision_epsilon_nm: float
    duplicate_max_distance_nm: float
    first_shell_r_min_nm: float
    first_shell_r_max_nm: float
    coordinate_frame: Literal["sample_nm"]
    orientation_reference: OrientationReference
    spatial_calibration_fingerprint: str
    registration_fingerprint: str
    construction_method: FirstShellConstructionMethod
    qc_status: str
    representative_source_ids: tuple[str, ...] = ()
    duplicate_parent_component_ids: tuple[str | None, ...] = ()
    duplicate_parent_component_diameters_nm: tuple[float | None, ...] = ()
    duplicate_group_ids: tuple[str | None, ...] = ()
    duplicate_group_diameters_nm: tuple[float | None, ...] = ()
    duplicate_chain_qc: tuple[bool, ...] = ()
    physical_duplicate_qc: tuple[bool, ...] = ()
    geometry_duplicate_qc: tuple[bool, ...] = ()

    def __post_init__(self) -> None:
        point_count = _as_integer(self.point_count, "point_count")
        point_ids = tuple(self.point_ids)
        if point_count != len(point_ids):
            raise ValueError("point_count must equal the number of point_ids.")
        if any(not isinstance(point_id, str) or not point_id for point_id in point_ids):
            raise TypeError("point_ids must contain non-empty strings.")
        if len(set(point_ids)) != point_count:
            raise ValueError("point_ids must be unique.")

        geometry_epsilon = _as_positive_float(
            self.geometry_collision_epsilon_nm,
            "geometry_collision_epsilon_nm",
        )
        duplicate_max_distance = _as_positive_float(
            self.duplicate_max_distance_nm,
            "duplicate_max_distance_nm",
        )
        first_shell_r_min = _as_positive_float(self.first_shell_r_min_nm, "first_shell_r_min_nm")
        first_shell_r_max = _as_positive_float(self.first_shell_r_max_nm, "first_shell_r_max_nm")
        if first_shell_r_min >= first_shell_r_max:
            raise ValueError("first_shell_r_min_nm must be less than first_shell_r_max_nm.")

        coordinate_frame = _non_empty_string(self.coordinate_frame, "coordinate_frame")
        if coordinate_frame != "sample_nm":
            raise ValueError("coordinate_frame must be 'sample_nm'.")
        orientation_reference = _non_empty_string(
            self.orientation_reference,
            "orientation_reference",
        )
        if orientation_reference not in _ORIENTATION_REFERENCES:
            raise ValueError(f"Unsupported orientation_reference: {orientation_reference!r}.")
        calibration_fingerprint = _non_empty_string(
            self.spatial_calibration_fingerprint,
            "spatial_calibration_fingerprint",
        )
        registration_fingerprint = _non_empty_string(
            self.registration_fingerprint,
            "registration_fingerprint",
        )
        construction_method = _non_empty_string(
            self.construction_method,
            "construction_method",
        )
        if construction_method not in _CONSTRUCTION_METHODS:
            raise ValueError(f"Unsupported construction_method: {construction_method!r}.")
        qc_status = _non_empty_string(self.qc_status, "qc_status")

        raw_edges = tuple(self.edges_ij)
        raw_distances = tuple(self.distances_nm)
        raw_angles = tuple(self.angles_rad)
        if not len(raw_edges) == len(raw_distances) == len(raw_angles):
            raise ValueError("edges_ij, distances_nm, and angles_rad must have equal lengths.")

        normalized_edges: list[tuple[int, int]] = []
        normalized_distances: list[float] = []
        normalized_angles: list[float] = []
        for edge_index, (raw_edge, raw_distance, raw_angle) in enumerate(
            zip(raw_edges, raw_distances, raw_angles)
        ):
            try:
                edge = tuple(raw_edge)
            except TypeError as exc:
                raise TypeError(f"edges_ij[{edge_index}] must contain two indices.") from exc
            if len(edge) != 2:
                raise ValueError(f"edges_ij[{edge_index}] must contain two indices.")
            i = _as_integer(edge[0], f"edges_ij[{edge_index}][0]")
            j = _as_integer(edge[1], f"edges_ij[{edge_index}][1]")
            if not 0 <= i < j < point_count:
                raise ValueError("Each edge must satisfy 0 <= i < j < point_count.")
            distance = _as_finite_float(raw_distance, f"distances_nm[{edge_index}]")
            if distance <= 0.0:
                raise ValueError("Edge distances must be positive.")
            if not first_shell_r_min <= distance <= first_shell_r_max:
                raise ValueError("Edge distances must lie within the first-shell bounds.")
            angle = _as_finite_float(raw_angle, f"angles_rad[{edge_index}]") % (2.0 * pi)
            normalized_edges.append((i, j))
            normalized_distances.append(distance)
            normalized_angles.append(angle)

        if len(set(normalized_edges)) != len(normalized_edges):
            raise ValueError("edges_ij must not contain duplicate edges.")

        degree = tuple(_as_integer(value, f"degree[{index}]") for index, value in enumerate(self.degree))
        if len(degree) != point_count:
            raise ValueError("degree must contain one value per point.")
        if any(value < 0 for value in degree):
            raise ValueError("degree values must be non-negative.")
        expected_degree = [0] * point_count
        for i, j in normalized_edges:
            expected_degree[i] += 1
            expected_degree[j] += 1
        if degree != tuple(expected_degree):
            raise ValueError("degree values must match edges_ij.")

        representatives = _per_point_tuple(
            self.representative_source_ids,
            point_count=point_count,
            default=point_ids,
            field_name="representative_source_ids",
        )
        if any(
            not isinstance(representative, str) or representative not in point_ids
            for representative in representatives
        ):
            raise ValueError("representative_source_ids must reference existing point_ids.")
        parent_ids = _optional_id_tuple(
            self.duplicate_parent_component_ids,
            point_count=point_count,
            field_name="duplicate_parent_component_ids",
        )
        parent_diameters = _optional_float_tuple(
            self.duplicate_parent_component_diameters_nm,
            point_count=point_count,
            field_name="duplicate_parent_component_diameters_nm",
        )
        group_ids = _optional_id_tuple(
            self.duplicate_group_ids,
            point_count=point_count,
            field_name="duplicate_group_ids",
        )
        group_diameters = _optional_float_tuple(
            self.duplicate_group_diameters_nm,
            point_count=point_count,
            field_name="duplicate_group_diameters_nm",
        )
        chain_qc = _boolean_tuple(
            self.duplicate_chain_qc,
            point_count=point_count,
            field_name="duplicate_chain_qc",
        )
        physical_qc = _boolean_tuple(
            self.physical_duplicate_qc,
            point_count=point_count,
            field_name="physical_duplicate_qc",
        )
        geometry_qc = _boolean_tuple(
            self.geometry_duplicate_qc,
            point_count=point_count,
            field_name="geometry_duplicate_qc",
        )

        _validate_id_diameter_pairs(
            parent_ids,
            parent_diameters,
            field_name="duplicate parent component",
        )
        _validate_id_diameter_pairs(
            group_ids,
            group_diameters,
            field_name="duplicate group",
        )
        _validate_consistent_diameters(parent_ids, parent_diameters, "duplicate parent component")
        _validate_consistent_diameters(group_ids, group_diameters, "duplicate group")
        _validate_duplicate_hierarchy(
            parent_ids=parent_ids,
            parent_diameters_nm=parent_diameters,
            group_ids=group_ids,
            group_diameters_nm=group_diameters,
        )
        _validate_duplicate_groups(
            point_ids=point_ids,
            representative_source_ids=representatives,
            group_ids=group_ids,
            group_diameters_nm=group_diameters,
            duplicate_max_distance_nm=duplicate_max_distance,
        )
        for index in range(point_count):
            is_rejected_duplicate = physical_qc[index] or geometry_qc[index]
            if physical_qc[index] and geometry_qc[index]:
                raise ValueError("A point cannot be both a physical and geometry duplicate.")
            if is_rejected_duplicate and degree[index] != 0:
                raise ValueError("Rejected duplicate points must have degree=0.")
            if is_rejected_duplicate != (representatives[index] != point_ids[index]):
                raise ValueError(
                    "Rejected duplicate points must reference a different representative_source_id."
                )
            if (parent_ids[index] is None) != (group_ids[index] is None):
                raise ValueError(
                    "Duplicate parent component and final group metadata must be present together."
                )
            if is_rejected_duplicate and group_ids[index] is None:
                raise ValueError("Rejected duplicate points must retain complete duplicate metadata.")
            if chain_qc[index]:
                if parent_diameters[index] is None:
                    raise ValueError("duplicate_chain_qc requires parent component metadata.")
                if parent_diameters[index] <= duplicate_max_distance:
                    raise ValueError(
                        "duplicate_chain_qc requires parent component diameter above the duplicate threshold."
                    )
            elif (
                parent_diameters[index] is not None
                and parent_diameters[index] > duplicate_max_distance
            ):
                raise ValueError(
                    "Parent components above the duplicate threshold must set duplicate_chain_qc."
                )

        records = sorted(
            zip(normalized_edges, normalized_distances, normalized_angles),
            key=lambda record: record[0],
        )
        object.__setattr__(self, "point_ids", point_ids)
        object.__setattr__(self, "point_count", point_count)
        object.__setattr__(self, "degree", degree)
        object.__setattr__(self, "geometry_collision_epsilon_nm", geometry_epsilon)
        object.__setattr__(self, "duplicate_max_distance_nm", duplicate_max_distance)
        object.__setattr__(self, "first_shell_r_min_nm", first_shell_r_min)
        object.__setattr__(self, "first_shell_r_max_nm", first_shell_r_max)
        object.__setattr__(self, "coordinate_frame", coordinate_frame)
        object.__setattr__(self, "orientation_reference", orientation_reference)
        object.__setattr__(self, "spatial_calibration_fingerprint", calibration_fingerprint)
        object.__setattr__(self, "registration_fingerprint", registration_fingerprint)
        object.__setattr__(self, "construction_method", construction_method)
        object.__setattr__(self, "qc_status", qc_status)
        object.__setattr__(self, "edges_ij", tuple(tuple(edge) for edge, _, _ in records))
        object.__setattr__(self, "distances_nm", tuple(distance for _, distance, _ in records))
        object.__setattr__(self, "angles_rad", tuple(angle for _, _, angle in records))
        object.__setattr__(self, "representative_source_ids", representatives)
        object.__setattr__(self, "duplicate_parent_component_ids", parent_ids)
        object.__setattr__(self, "duplicate_parent_component_diameters_nm", parent_diameters)
        object.__setattr__(self, "duplicate_group_ids", group_ids)
        object.__setattr__(self, "duplicate_group_diameters_nm", group_diameters)
        object.__setattr__(self, "duplicate_chain_qc", chain_qc)
        object.__setattr__(self, "physical_duplicate_qc", physical_qc)
        object.__setattr__(self, "geometry_duplicate_qc", geometry_qc)

    def neighbors_for_point(self, point: int | str) -> tuple[int, ...]:
        """Return neighboring original point indices in deterministic order."""

        point_index = self._point_index(point)
        neighbors = [
            j if i == point_index else i
            for i, j in self.edges_ij
            if i == point_index or j == point_index
        ]
        return tuple(sorted(neighbors))

    def directed_angle_rad(self, source: int | str, neighbor: int | str) -> float:
        """Return the directed bond angle from source to its neighbor."""

        source_index = self._point_index(source)
        neighbor_index = self._point_index(neighbor)
        for (i, j), angle in zip(self.edges_ij, self.angles_rad):
            if (source_index, neighbor_index) == (i, j):
                return angle
            if (source_index, neighbor_index) == (j, i):
                return (angle + pi) % (2.0 * pi)
        raise ValueError(f"Points {source_index} and {neighbor_index} are not neighbors.")

    def _point_index(self, point: int | str) -> int:
        if isinstance(point, str):
            try:
                return self.point_ids.index(point)
            except ValueError as exc:
                raise KeyError(f"Unknown point_id: {point!r}.") from exc
        point_index = int(point)
        if point_index < 0 or point_index >= self.point_count:
            raise IndexError(f"Point index out of range: {point_index}.")
        return point_index


def _as_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer.")
    try:
        normalized = int(value)
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be an integer.") from exc
    if not isfinite(numeric) or numeric != normalized:
        raise ValueError(f"{field_name} must be an integer.")
    return normalized


def _as_finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be numeric.")
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} must be numeric.") from exc
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def _as_positive_float(value: object, field_name: str) -> float:
    normalized = _as_finite_float(value, field_name)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized


def _per_point_tuple(
    values: tuple[object, ...],
    *,
    point_count: int,
    default: tuple[object, ...],
    field_name: str,
) -> tuple[object, ...]:
    normalized = tuple(values)
    if not normalized and point_count:
        normalized = default
    if len(normalized) != point_count:
        raise ValueError(f"{field_name} must contain one value per point.")
    return normalized


def _optional_id_tuple(
    values: tuple[str | None, ...],
    *,
    point_count: int,
    field_name: str,
) -> tuple[str | None, ...]:
    normalized = _per_point_tuple(
        values,
        point_count=point_count,
        default=(None,) * point_count,
        field_name=field_name,
    )
    if any(value is not None and (not isinstance(value, str) or not value) for value in normalized):
        raise TypeError(f"{field_name} values must be non-empty strings or None.")
    return tuple(normalized)


def _optional_float_tuple(
    values: tuple[float | None, ...],
    *,
    point_count: int,
    field_name: str,
) -> tuple[float | None, ...]:
    normalized = _per_point_tuple(
        values,
        point_count=point_count,
        default=(None,) * point_count,
        field_name=field_name,
    )
    result: list[float | None] = []
    for index, value in enumerate(normalized):
        if value is None:
            result.append(None)
            continue
        numeric = _as_finite_float(value, f"{field_name}[{index}]")
        if numeric < 0.0:
            raise ValueError(f"{field_name} values must be non-negative.")
        result.append(numeric)
    return tuple(result)


def _boolean_tuple(
    values: tuple[bool, ...],
    *,
    point_count: int,
    field_name: str,
) -> tuple[bool, ...]:
    normalized = _per_point_tuple(
        values,
        point_count=point_count,
        default=(False,) * point_count,
        field_name=field_name,
    )
    if any(not isinstance(value, bool) for value in normalized):
        raise TypeError(f"{field_name} values must be booleans.")
    return tuple(normalized)


def _validate_id_diameter_pairs(
    ids: tuple[str | None, ...],
    diameters: tuple[float | None, ...],
    *,
    field_name: str,
) -> None:
    for identifier, diameter in zip(ids, diameters):
        if (identifier is None) != (diameter is None):
            raise ValueError(f"{field_name} id and diameter must be present together.")


def _validate_consistent_diameters(
    ids: tuple[str | None, ...],
    diameters: tuple[float | None, ...],
    field_name: str,
) -> None:
    by_id: dict[str, float] = {}
    for identifier, diameter in zip(ids, diameters):
        if identifier is None or diameter is None:
            continue
        previous = by_id.setdefault(identifier, diameter)
        if previous != diameter:
            raise ValueError(f"{field_name} members must share one diameter.")


def _validate_duplicate_groups(
    *,
    point_ids: tuple[str, ...],
    representative_source_ids: tuple[str, ...],
    group_ids: tuple[str | None, ...],
    group_diameters_nm: tuple[float | None, ...],
    duplicate_max_distance_nm: float,
) -> None:
    group_members: dict[str, list[int]] = {}
    for index, group_id in enumerate(group_ids):
        if group_id is not None:
            group_members.setdefault(group_id, []).append(index)
    for group_id, member_indices in group_members.items():
        representatives = {representative_source_ids[index] for index in member_indices}
        if len(representatives) != 1:
            raise ValueError("Duplicate group members must share one representative_source_id.")
        representative = next(iter(representatives))
        representative_index = point_ids.index(representative)
        if group_ids[representative_index] != group_id:
            raise ValueError("Duplicate group representative must belong to the same final group.")
        diameter = group_diameters_nm[member_indices[0]]
        if diameter is not None and diameter > duplicate_max_distance_nm:
            raise ValueError("Final duplicate group diameter must not exceed duplicate_max_distance_nm.")


def _validate_duplicate_hierarchy(
    *,
    parent_ids: tuple[str | None, ...],
    parent_diameters_nm: tuple[float | None, ...],
    group_ids: tuple[str | None, ...],
    group_diameters_nm: tuple[float | None, ...],
) -> None:
    group_members: dict[str, list[int]] = {}
    for index, group_id in enumerate(group_ids):
        if group_id is not None:
            group_members.setdefault(group_id, []).append(index)
    for member_indices in group_members.values():
        parents = {parent_ids[index] for index in member_indices}
        if len(parents) != 1 or None in parents:
            raise ValueError("Each final duplicate group must belong to one parent component.")
        group_diameter = group_diameters_nm[member_indices[0]]
        parent_diameter = parent_diameters_nm[member_indices[0]]
        if (
            group_diameter is not None
            and parent_diameter is not None
            and group_diameter > parent_diameter
        ):
            raise ValueError("Final duplicate group diameter must not exceed parent diameter.")
