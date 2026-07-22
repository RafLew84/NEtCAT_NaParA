"""Component-relative M3 sublattice gauge on a qualified trifold subgraph."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from hashlib import sha256
from typing import get_args

from ._local_multisymmetry_validation import (
    normalize_m3_sublattice_gauge,
    validate_m3_gauge_component_qc,
)
from .first_shell_graph import FirstShellGraph
from .local_multisymmetry_bond_order import (
    LocalMultiSymmetryOrientationStatus,
    M3SublatticePhaseStatus,
)


_ORIENTATION_STATUSES = set(get_args(LocalMultiSymmetryOrientationStatus))


@dataclass(frozen=True)
class M3SublatticeGaugeAssignment:
    """Per-point phase labels and QC produced from trifold edge parity."""

    source_ids: tuple[str, ...]
    m3_sublattice_phase: tuple[int | None, ...]
    m3_sublattice_phase_status: tuple[M3SublatticePhaseStatus, ...]
    m3_phase_gauge_anchor: tuple[str | None, ...]
    m3_qualified_trifold: tuple[bool, ...]
    m3_sublattice_assignment_ambiguous: tuple[bool, ...]
    m3_gauge_inconsistent_cycle: tuple[bool, ...]
    m3_gauge_frustration_qc: tuple[bool, ...]
    qualified_trifold_edges_ij: tuple[tuple[int, int], ...] = ()
    qualified_trifold_subgraph_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        source_ids = tuple(self.source_ids)
        point_count = len(source_ids)
        if any(not isinstance(source_id, str) or not source_id for source_id in source_ids):
            raise TypeError("source_ids must contain non-empty strings.")
        if len(set(source_ids)) != point_count:
            raise ValueError("source_ids must be unique.")
        field_names = (
            "m3_sublattice_phase",
            "m3_sublattice_phase_status",
            "m3_phase_gauge_anchor",
            "m3_qualified_trifold",
            "m3_sublattice_assignment_ambiguous",
            "m3_gauge_inconsistent_cycle",
            "m3_gauge_frustration_qc",
        )
        for field_name in field_names:
            values = tuple(getattr(self, field_name))
            if len(values) != point_count:
                raise ValueError(f"{field_name} must contain one value per point.")
            object.__setattr__(self, field_name, values)
        object.__setattr__(self, "source_ids", source_ids)
        normalized_phases, normalized_anchors = normalize_m3_sublattice_gauge(
            source_ids=source_ids,
            phases=self.m3_sublattice_phase,
            statuses=self.m3_sublattice_phase_status,
            anchors=self.m3_phase_gauge_anchor,
        )
        object.__setattr__(self, "m3_sublattice_phase", normalized_phases)
        object.__setattr__(self, "m3_phase_gauge_anchor", normalized_anchors)
        qualified_edges = _normalize_subgraph_edges(
            self.qualified_trifold_edges_ij,
            point_count=point_count,
            qualified=self.m3_qualified_trifold,
        )
        object.__setattr__(self, "qualified_trifold_edges_ij", qualified_edges)
        object.__setattr__(
            self,
            "qualified_trifold_subgraph_fingerprint",
            _qualified_trifold_subgraph_fingerprint(
                source_ids=source_ids,
                qualified=self.m3_qualified_trifold,
                edges_ij=qualified_edges,
            ),
        )

        for index, status in enumerate(self.m3_sublattice_phase_status):
            phase = self.m3_sublattice_phase[index]
            anchor = self.m3_phase_gauge_anchor[index]
            qualified = self.m3_qualified_trifold[index]
            ambiguous = self.m3_sublattice_assignment_ambiguous[index]
            inconsistent = self.m3_gauge_inconsistent_cycle[index]
            frustrated = self.m3_gauge_frustration_qc[index]
            if not all(
                isinstance(value, bool)
                for value in (qualified, ambiguous, inconsistent, frustrated)
            ):
                raise TypeError("M3 gauge QC fields must contain only booleans.")
            if status == "defined":
                if phase not in {0, 1} or not isinstance(anchor, str) or not anchor:
                    raise ValueError("Defined M3 gauge requires phase and anchor.")
                if not qualified or ambiguous or inconsistent or frustrated:
                    raise ValueError("Defined M3 gauge has inconsistent QC flags.")
            elif status == "ambiguous":
                if phase is not None or not isinstance(anchor, str) or not anchor:
                    raise ValueError("Ambiguous M3 gauge requires only an anchor.")
                if not qualified or not ambiguous or inconsistent or frustrated:
                    raise ValueError("Ambiguous M3 gauge has inconsistent QC flags.")
            elif status == "inconsistent":
                if phase is not None or not isinstance(anchor, str) or not anchor:
                    raise ValueError("Inconsistent M3 gauge requires only an anchor.")
                if not qualified or not inconsistent or not frustrated:
                    raise ValueError("Inconsistent M3 gauge has inconsistent QC flags.")
            elif status in {"unavailable", "not_applicable"}:
                if phase is not None or anchor is not None or qualified:
                    raise ValueError(f"{status} M3 gauge cannot contain phase context.")
                if ambiguous or inconsistent or frustrated:
                    raise ValueError(f"{status} M3 gauge cannot contain QC failures.")
            else:
                raise ValueError(f"Unsupported M3 phase status: {status!r}.")
        validate_m3_gauge_component_qc(
            anchors=self.m3_phase_gauge_anchor,
            ambiguity_flags=self.m3_sublattice_assignment_ambiguous,
        )


def build_m3_sublattice_gauge_assignment(
    *,
    first_shell_graph: FirstShellGraph,
    m3_orientation_status: tuple[LocalMultiSymmetryOrientationStatus, ...],
    qualified_trifold_point_indices: tuple[int, ...],
    ambiguous_trifold_point_indices: tuple[int, ...] = (),
    trifold_edge_qualified: tuple[bool, ...] | None = None,
) -> M3SublatticeGaugeAssignment:
    """Two-color the qualified subgraph induced by one first-shell graph."""

    if not isinstance(first_shell_graph, FirstShellGraph):
        raise TypeError("first_shell_graph must be a FirstShellGraph.")
    source_ids = first_shell_graph.point_ids
    statuses = tuple(m3_orientation_status)
    point_count = first_shell_graph.point_count
    if len(statuses) != point_count:
        raise ValueError("m3_orientation_status must contain one value per point.")
    if any(status not in _ORIENTATION_STATUSES for status in statuses):
        raise ValueError("m3_orientation_status contains an unsupported orientation status.")
    qualified = _normalize_point_indices(
        qualified_trifold_point_indices,
        point_count=point_count,
    )
    for index in qualified:
        if statuses[index] != "defined":
            raise ValueError("Qualified trifold points require a defined M3 orientation.")
    ambiguous = _normalize_point_indices(
        ambiguous_trifold_point_indices,
        point_count=point_count,
    )
    if not ambiguous.issubset(qualified):
        raise ValueError("Ambiguous trifold points must be qualified trifold points.")
    edge_qualification = _normalize_edge_qualification(
        trifold_edge_qualified,
        edge_count=len(first_shell_graph.edges_ij),
    )
    edges = tuple(
        (i, j)
        for (i, j), edge_is_qualified in zip(
            first_shell_graph.edges_ij,
            edge_qualification,
        )
        if edge_is_qualified and i in qualified and j in qualified
    )

    phases: list[int | None] = [None] * point_count
    phase_statuses: list[M3SublatticePhaseStatus] = [
        "not_applicable" if status == "defined" else "unavailable"
        for status in statuses
    ]
    anchors: list[str | None] = [None] * point_count
    qualified_flags = [index in qualified for index in range(point_count)]
    ambiguous_flags = [False] * point_count
    inconsistent_flags = [False] * point_count
    frustration_flags = [False] * point_count

    adjacency = {index: set() for index in qualified}
    for i, j in edges:
        adjacency[i].add(j)
        adjacency[j].add(i)

    unvisited = set(qualified)
    while unvisited:
        anchor_index = min(unvisited, key=lambda index: source_ids[index])
        colors = {anchor_index: 0}
        component: list[int] = []
        inconsistent = False
        queue = deque([anchor_index])
        while queue:
            index = queue.popleft()
            if index not in unvisited:
                continue
            unvisited.remove(index)
            component.append(index)
            for neighbor in sorted(adjacency[index], key=lambda item: source_ids[item]):
                expected = 1 - colors[index]
                if neighbor in colors:
                    if colors[neighbor] != expected:
                        inconsistent = True
                    continue
                colors[neighbor] = expected
                queue.append(neighbor)

        anchor = source_ids[anchor_index]
        component_is_ambiguous = bool(ambiguous.intersection(component))
        for index in component:
            anchors[index] = anchor
            ambiguous_flags[index] = component_is_ambiguous
            if inconsistent:
                phase_statuses[index] = "inconsistent"
                inconsistent_flags[index] = True
                frustration_flags[index] = True
            elif component_is_ambiguous:
                phase_statuses[index] = "ambiguous"
            else:
                phases[index] = colors[index]
                phase_statuses[index] = "defined"

    return M3SublatticeGaugeAssignment(
        source_ids=source_ids,
        m3_sublattice_phase=tuple(phases),
        m3_sublattice_phase_status=tuple(phase_statuses),
        m3_phase_gauge_anchor=tuple(anchors),
        m3_qualified_trifold=tuple(qualified_flags),
        m3_sublattice_assignment_ambiguous=tuple(ambiguous_flags),
        m3_gauge_inconsistent_cycle=tuple(inconsistent_flags),
        m3_gauge_frustration_qc=tuple(frustration_flags),
        qualified_trifold_edges_ij=edges,
    )


def _normalize_point_indices(
    values: tuple[int, ...],
    *,
    point_count: int,
) -> set[int]:
    normalized: list[int] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("qualified_trifold_point_indices must contain integers.")
        if not 0 <= value < point_count:
            raise ValueError("qualified_trifold_point_indices are out of range.")
        normalized.append(value)
    if len(set(normalized)) != len(normalized):
        raise ValueError("qualified_trifold_point_indices must be unique.")
    return set(normalized)


def _normalize_edge_qualification(
    values: tuple[bool, ...] | None,
    *,
    edge_count: int,
) -> tuple[bool, ...]:
    if values is None:
        return (True,) * edge_count
    normalized = tuple(values)
    if len(normalized) != edge_count:
        raise ValueError("trifold_edge_qualified must contain one value per graph edge.")
    if any(not isinstance(value, bool) for value in normalized):
        raise TypeError("trifold_edge_qualified must contain only booleans.")
    return normalized


def _normalize_subgraph_edges(
    values: tuple[tuple[int, int], ...],
    *,
    point_count: int,
    qualified: tuple[bool, ...],
) -> tuple[tuple[int, int], ...]:
    normalized: list[tuple[int, int]] = []
    for edge in values:
        endpoints = tuple(edge)
        if len(endpoints) != 2:
            raise ValueError("qualified_trifold_edges_ij must contain index pairs.")
        i, j = endpoints
        if any(isinstance(value, bool) or not isinstance(value, int) for value in (i, j)):
            raise TypeError("qualified_trifold_edges_ij must contain integer indices.")
        if not 0 <= i < j < point_count:
            raise ValueError("qualified_trifold_edges_ij contains an invalid edge.")
        if not qualified[i] or not qualified[j]:
            raise ValueError("Qualified trifold edges must join qualified points.")
        normalized.append((i, j))
    if len(set(normalized)) != len(normalized):
        raise ValueError("qualified_trifold_edges_ij must be unique.")
    return tuple(sorted(normalized))


def _qualified_trifold_subgraph_fingerprint(
    *,
    source_ids: tuple[str, ...],
    qualified: tuple[bool, ...],
    edges_ij: tuple[tuple[int, int], ...],
) -> str:
    payload = {
        "schema": "moltrack-qualified-trifold-subgraph-v1",
        "source_ids": source_ids,
        "qualified_point_indices": tuple(
            index for index, is_qualified in enumerate(qualified) if is_qualified
        ),
        "edges_ij": edges_ij,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return sha256(encoded).hexdigest()
