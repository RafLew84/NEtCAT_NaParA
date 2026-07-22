"""Normalization and invariant checks for local M3/M6 result models."""

from __future__ import annotations

from cmath import phase
from math import degrees, isclose, isfinite


def per_point_tuple(
    values: object,
    *,
    point_count: int,
    field_name: str,
) -> tuple:
    try:
        normalized = tuple(values)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError(f"{field_name} must be an iterable.") from exc
    if len(normalized) != point_count:
        raise ValueError(f"{field_name} must contain one value per point.")
    return normalized


def normalized_optional_angles(
    values: tuple[object, ...],
    *,
    period_deg: float,
) -> tuple[float | None, ...]:
    normalized: list[float | None] = []
    for value in values:
        if value is None:
            normalized.append(None)
            continue
        if isinstance(value, bool):
            raise TypeError("Angles must be numbers or None.")
        try:
            angle = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise TypeError("Angles must be numbers or None.") from exc
        if not isfinite(angle):
            raise ValueError("Angles must be finite.")
        normalized.append(angle % period_deg)
    return tuple(normalized)


def optional_complex_tuple(
    values: tuple[object, ...],
    *,
    field_name: str,
) -> tuple[complex | None, ...]:
    normalized: list[complex | None] = []
    for index, value in enumerate(values):
        if value is None:
            normalized.append(None)
            continue
        if isinstance(value, bool):
            raise TypeError(f"{field_name}[{index}] must be a complex number or None.")
        try:
            number = complex(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise TypeError(
                f"{field_name}[{index}] must be a complex number or None."
            ) from exc
        if not isfinite(number.real) or not isfinite(number.imag):
            raise ValueError(f"{field_name}[{index}] must be finite.")
        normalized.append(number)
    return tuple(normalized)


def optional_float_tuple(
    values: tuple[object, ...],
    *,
    field_name: str,
) -> tuple[float | None, ...]:
    normalized: list[float | None] = []
    for index, value in enumerate(values):
        if value is None:
            normalized.append(None)
            continue
        if isinstance(value, bool):
            raise TypeError(f"{field_name}[{index}] must be a number or None.")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise TypeError(f"{field_name}[{index}] must be a number or None.") from exc
        if not isfinite(number):
            raise ValueError(f"{field_name}[{index}] must be finite.")
        normalized.append(number)
    return tuple(normalized)


def status_tuple(
    values: tuple[object, ...],
    *,
    field_name: str,
    supported: set[str],
) -> tuple:
    if any(value not in supported for value in values):
        raise ValueError(f"{field_name} contains an unsupported status.")
    return values


def boolean_tuple(
    values: tuple[object, ...],
    *,
    field_name: str,
) -> tuple[bool, ...]:
    if any(not isinstance(value, bool) for value in values):
        raise TypeError(f"{field_name} must contain only booleans.")
    return tuple(values)  # type: ignore[return-value]


def validate_order_channel(
    *,
    channel_name: str,
    psi: tuple[complex | None, ...],
    magnitude: tuple[float | None, ...],
    angles: tuple[tuple[float | None, ...], ...],
    statuses: tuple[str, ...],
    confidence: tuple[float | None, ...],
    orientation_zero_tolerance: float,
) -> None:
    for index, status in enumerate(statuses):
        point_psi = psi[index]
        point_magnitude = magnitude[index]
        point_angles = tuple(values[index] for values in angles)
        point_confidence = confidence[index]
        if status in {"defined", "undefined_low_amplitude"}:
            if point_psi is None or point_magnitude is None:
                raise ValueError(f"{channel_name} {status} requires psi and q values.")
        elif status == "invalid_geometry":
            if (point_psi is None) != (point_magnitude is None):
                raise ValueError(
                    f"{channel_name} invalid_geometry requires both psi and q or neither."
                )
        elif point_psi is not None or point_magnitude is not None:
            raise ValueError(f"{channel_name} {status} cannot contain psi or q values.")

        if point_psi is not None and point_magnitude is not None:
            if not 0.0 <= point_magnitude <= 1.0:
                raise ValueError(f"{channel_name} q values must lie between 0 and 1.")
            if not isclose(
                point_magnitude,
                abs(point_psi),
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError(f"{channel_name} q must equal abs(psi).")
            if (
                status == "invalid_geometry"
                and point_magnitude <= orientation_zero_tolerance
            ):
                raise ValueError(
                    f"{channel_name} invalid_geometry with retained psi/q requires q "
                    "above its orientation tolerance."
                )

        if status == "defined":
            if point_magnitude is None or point_magnitude <= 0.0:
                raise ValueError(f"{channel_name} defined requires positive q.")
            if point_magnitude <= orientation_zero_tolerance:
                raise ValueError(
                    f"{channel_name} defined requires q above its orientation tolerance."
                )
            if any(angle is None for angle in point_angles):
                raise ValueError(f"{channel_name} defined requires all orientation angles.")
            if point_confidence is None or not 0.0 <= point_confidence <= 1.0:
                raise ValueError(
                    f"{channel_name} defined requires confidence between 0 and 1."
                )
        elif status == "undefined_low_amplitude":
            if point_magnitude is None or point_magnitude > orientation_zero_tolerance:
                raise ValueError(
                    f"{channel_name} undefined_low_amplitude requires q at or below "
                    "its orientation tolerance."
                )
            if any(angle is not None for angle in point_angles):
                raise ValueError(
                    f"{channel_name} undefined_low_amplitude cannot contain "
                    "orientation angles."
                )
            if point_confidence is not None:
                raise ValueError(
                    f"{channel_name} undefined_low_amplitude cannot contain confidence."
                )
        else:
            if any(angle is not None for angle in point_angles):
                raise ValueError(f"{channel_name} {status} cannot contain orientation angles.")
            if point_confidence is not None:
                raise ValueError(f"{channel_name} {status} cannot contain confidence.")


def normalize_m3_sublattice_gauge(
    *,
    source_ids: tuple[str, ...],
    phases: tuple[object, ...],
    statuses: tuple[str, ...],
    anchors: tuple[object, ...],
) -> tuple[tuple[int | None, ...], tuple[str | None, ...]]:
    normalized_phases: list[int | None] = []
    normalized_anchors: list[str | None] = []
    source_id_set = set(source_ids)
    for index, (phase_value, status, anchor) in enumerate(
        zip(phases, statuses, anchors)
    ):
        if phase_value is None:
            normalized_phase = None
        else:
            if isinstance(phase_value, bool) or phase_value not in {0, 1}:
                raise ValueError(f"m3_sublattice_phase[{index}] must be 0, 1, or None.")
            normalized_phase = int(phase_value)
        if anchor is None:
            normalized_anchor = None
        elif not isinstance(anchor, str) or not anchor:
            raise TypeError(
                f"m3_phase_gauge_anchor[{index}] must be a source ID or None."
            )
        elif anchor not in source_id_set:
            raise ValueError(
                f"m3_phase_gauge_anchor[{index}] must reference a source_id."
            )
        else:
            normalized_anchor = anchor

        if status == "defined":
            if normalized_phase is None or normalized_anchor is None:
                raise ValueError("Defined M3 sublattice phase requires phase and gauge anchor.")
        elif status in {"ambiguous", "inconsistent"}:
            if normalized_phase is not None or normalized_anchor is None:
                raise ValueError(
                    f"{status} M3 sublattice phase requires an anchor and no phase."
                )
        elif normalized_phase is not None or normalized_anchor is not None:
            raise ValueError(
                f"{status} M3 sublattice phase cannot contain phase or gauge anchor."
            )
        normalized_phases.append(normalized_phase)
        normalized_anchors.append(normalized_anchor)

    groups: dict[str, list[int]] = {}
    for index, anchor in enumerate(normalized_anchors):
        if anchor is not None:
            groups.setdefault(anchor, []).append(index)
    source_id_to_index = {
        source_id: index for index, source_id in enumerate(source_ids)
    }
    for anchor, indices in groups.items():
        component_source_ids = tuple(source_ids[index] for index in indices)
        if anchor not in component_source_ids:
            raise ValueError("M3 phase gauge anchor must belong to its component.")
        if anchor != min(component_source_ids):
            raise ValueError("M3 phase gauge anchor must be the canonical source_id.")
        component_statuses = {statuses[index] for index in indices}
        if len(component_statuses) != 1:
            raise ValueError("An M3 gauge component must use one phase status.")
        anchor_index = source_id_to_index[anchor]
        defined_indices = [index for index in indices if statuses[index] == "defined"]
        if defined_indices and statuses[anchor_index] != "defined":
            raise ValueError("A defined M3 gauge requires a defined canonical anchor.")
        if defined_indices and normalized_phases[anchor_index] == 1:
            for index in defined_indices:
                point_phase = normalized_phases[index]
                if point_phase is None:  # guarded by the status validation above
                    raise RuntimeError("Defined M3 phase is unexpectedly unavailable.")
                normalized_phases[index] = 1 - point_phase

    return tuple(normalized_phases), tuple(normalized_anchors)


def validate_periodic_angle_consistency(
    *,
    field_name: str,
    psi: tuple[complex | None, ...],
    angles: tuple[float | None, ...],
    statuses: tuple[str, ...],
    harmonic: int,
    period_deg: float,
) -> None:
    for index, status in enumerate(statuses):
        if status != "defined":
            continue
        point_psi = psi[index]
        angle = angles[index]
        if point_psi is None or angle is None:  # guarded by channel validation
            raise RuntimeError("Defined orientation is unexpectedly incomplete.")
        expected = degrees(phase(point_psi) / harmonic) % period_deg
        delta = abs((angle - expected + period_deg / 2.0) % period_deg - period_deg / 2.0)
        if delta > 1e-10:
            raise ValueError(f"{field_name}[{index}] must match the phase of psi.")


def validate_point_context(
    *,
    computation_status: tuple[str, ...],
    psi3: tuple[complex | None, ...],
    psi6: tuple[complex | None, ...],
    m3_orientation_status: tuple[str, ...],
    m6_orientation_status: tuple[str, ...],
    m3_sublattice_phase_status: tuple[str, ...],
    m3_qualified_trifold: tuple[bool, ...],
    m3_sublattice_assignment_ambiguous: tuple[bool, ...],
    m3_gauge_inconsistent_cycle: tuple[bool, ...],
    m3_gauge_frustration_qc: tuple[bool, ...],
    symmetry_resolvability_status: tuple[str, ...],
    neighbor_count: tuple[int, ...],
    physical_duplicate_qc: tuple[bool, ...],
    geometry_duplicate_qc: tuple[bool, ...],
    edge_truncated_neighborhood: tuple[bool, ...],
    boundary_distances: tuple[float | None, ...],
    first_shell_r_max_nm: float,
    min_neighbors_for_local_order: int,
) -> None:
    for index, status in enumerate(computation_status):
        neighbors = neighbor_count[index]
        m3_status = m3_orientation_status[index]
        m6_status = m6_orientation_status[index]
        phase_status = m3_sublattice_phase_status[index]
        qualified_trifold = m3_qualified_trifold[index]
        assignment_ambiguous = m3_sublattice_assignment_ambiguous[index]
        inconsistent_cycle = m3_gauge_inconsistent_cycle[index]
        frustration = m3_gauge_frustration_qc[index]
        physical_duplicate = physical_duplicate_qc[index]
        geometry_duplicate = geometry_duplicate_qc[index]
        boundary_distance = boundary_distances[index]

        if physical_duplicate and geometry_duplicate:
            raise ValueError("A point cannot be both a physical and geometry duplicate.")
        is_duplicate = physical_duplicate or geometry_duplicate
        if is_duplicate != (status == "duplicate_excluded"):
            raise ValueError(
                "Duplicate QC flags must correspond exactly to duplicate_excluded status."
            )

        if status == "valid_order":
            if neighbors < min_neighbors_for_local_order:
                raise ValueError(
                    "valid_order requires at least min_neighbors_for_local_order neighbors."
                )
            valid_channel_statuses = {
                "defined",
                "undefined_low_amplitude",
                "invalid_geometry",
            }
            if m3_status not in valid_channel_statuses:
                raise ValueError("valid_order requires a computed M3 orientation status.")
            if m6_status not in valid_channel_statuses:
                raise ValueError("valid_order requires a computed M6 orientation status.")
            if m3_status == "invalid_geometry" and m6_status == "invalid_geometry":
                raise ValueError("valid_order requires at least one usable order channel.")
        elif status == "insufficient_neighbors":
            if neighbors >= min_neighbors_for_local_order:
                raise ValueError(
                    "insufficient_neighbors requires fewer than "
                    "min_neighbors_for_local_order neighbors."
                )
            if m3_status != "insufficient_neighbors" or m6_status != "insufficient_neighbors":
                raise ValueError(
                    "insufficient_neighbors must apply to both M3 and M6 channels."
                )
        else:
            if neighbors != 0:
                raise ValueError(f"{status} requires neighbor_count=0.")
            if m3_status != "invalid_geometry" or m6_status != "invalid_geometry":
                raise ValueError(f"{status} requires invalid_geometry for both channels.")

        if status != "valid_order" and (
            psi3[index] is not None or psi6[index] is not None
        ):
            raise ValueError("Non-valid order cannot retain psi/q values.")

        if status == "invalid_position":
            if boundary_distance is not None:
                raise ValueError(
                    "invalid_position cannot have distance_to_valid_fov_boundary_nm."
                )
        else:
            if boundary_distance is None:
                raise ValueError(
                    "A valid position requires distance_to_valid_fov_boundary_nm."
                )
            if boundary_distance < 0.0:
                raise ValueError(
                    "distance_to_valid_fov_boundary_nm values must be non-negative."
                )
        expected_edge_truncated = (
            boundary_distance is not None and boundary_distance < first_shell_r_max_nm
        )
        if edge_truncated_neighborhood[index] != expected_edge_truncated:
            raise ValueError(
                "edge_truncated_neighborhood must equal "
                "distance_to_valid_fov_boundary_nm < first_shell_r_max_nm."
            )

        if phase_status in {"defined", "ambiguous", "inconsistent"} and m3_status != "defined":
            raise ValueError("M3 sublattice phase requires a defined M3 orientation.")

        if phase_status == "defined":
            valid_gauge_qc = (
                qualified_trifold
                and not assignment_ambiguous
                and not inconsistent_cycle
                and not frustration
            )
        elif phase_status == "ambiguous":
            valid_gauge_qc = (
                qualified_trifold
                and assignment_ambiguous
                and not inconsistent_cycle
                and not frustration
            )
        elif phase_status == "inconsistent":
            valid_gauge_qc = (
                qualified_trifold
                and inconsistent_cycle
                and frustration
            )
        else:
            valid_gauge_qc = (
                not qualified_trifold
                and not assignment_ambiguous
                and not inconsistent_cycle
                and not frustration
            )
        if not valid_gauge_qc:
            raise ValueError(
                f"{phase_status} M3 sublattice phase has inconsistent gauge QC flags."
            )

        if status != "valid_order":
            if phase_status not in {"unavailable", "not_applicable"}:
                raise ValueError("Non-valid order cannot define an M3 sublattice phase.")
            if symmetry_resolvability_status[index] != "unavailable":
                raise ValueError(
                    "Non-valid order requires symmetry_resolvability_status='unavailable'."
                )


def validate_m3_gauge_component_qc(
    *,
    anchors: tuple[str | None, ...],
    ambiguity_flags: tuple[bool, ...],
) -> None:
    ambiguity_by_anchor: dict[str, set[bool]] = {}
    for anchor, ambiguity in zip(anchors, ambiguity_flags):
        if anchor is not None:
            ambiguity_by_anchor.setdefault(anchor, set()).add(ambiguity)
    if any(len(values) != 1 for values in ambiguity_by_anchor.values()):
        raise ValueError("An M3 gauge component must use one ambiguity flag.")


def as_non_negative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer.")
    try:
        normalized = int(value)
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be an integer.") from exc
    if not isfinite(numeric) or numeric != normalized:
        raise ValueError(f"{field_name} must be an integer.")
    if normalized < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized


def as_positive_integer(value: object, field_name: str) -> int:
    normalized = as_non_negative_integer(value, field_name)
    if normalized == 0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def as_positive_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a number.")
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be a number.") from exc
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def as_unit_interval_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a number.")
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be a number.") from exc
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must lie between 0 and 1.")
    return normalized
