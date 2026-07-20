from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from moltrack.analysis import (
    M6DomainTypeClassificationResult,
    M6PointOverlay,
    MolecularM6OrientationAnalysis,
)

from .m6_domain_type_colors import (
    M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR,
    m6_domain_type_color,
)
from .m6_domain_type_selection import M6DomainTypeSelection


@dataclass(frozen=True)
class _M6DomainTypeComponentProjection:
    ordered_component_id: int
    selection: M6DomainTypeSelection
    color: tuple[int, int, int, int]
    point_status: str


@dataclass(frozen=True)
class M6DomainTypeOverlayIndex:
    """Immutable frame index built once for one classification result."""

    classification: M6DomainTypeClassificationResult
    frame_entries: tuple[
        tuple[int, tuple[_M6DomainTypeComponentProjection, ...]], ...
    ]
    _entries_by_frame: Mapping[
        int, tuple[_M6DomainTypeComponentProjection, ...]
    ] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.classification, M6DomainTypeClassificationResult):
            raise TypeError("classification must be an M6 domain type classification.")
        entries = tuple(self.frame_entries)
        frame_indices = tuple(frame_index for frame_index, _values in entries)
        if frame_indices != tuple(sorted(set(frame_indices))):
            raise ValueError("frame_entries must have unique ordered frame indices.")
        object.__setattr__(self, "frame_entries", entries)
        object.__setattr__(
            self,
            "_entries_by_frame",
            MappingProxyType(dict(entries)),
        )

    def entries_for_frame(
        self,
        frame_index: int,
    ) -> tuple[_M6DomainTypeComponentProjection, ...]:
        return self._entries_by_frame.get(frame_index, ())


@dataclass(frozen=True)
class M6DomainTypeFrameOverlay:
    """Render projection and optional selection for one classified frame."""

    overlay: M6PointOverlay
    highlighted_source_ids: tuple[str, ...]


def build_m6_domain_type_overlay_index(
    classification: M6DomainTypeClassificationResult,
) -> M6DomainTypeOverlayIndex:
    """Index assignments by frame once, independently of viewer navigation."""

    if not isinstance(classification, M6DomainTypeClassificationResult):
        raise TypeError("classification must be an M6 domain type classification.")
    assignment_by_key = {
        assignment.observation_key: assignment
        for assignment in classification.assignments
    }
    frame_components: dict[
        int, dict[int, _M6DomainTypeComponentProjection]
    ] = {}
    for observation in classification.observations:
        assignment = assignment_by_key[observation.stable_key]
        if assignment.status == "classified":
            selection = M6DomainTypeSelection.classified(
                assignment.domain_type_id
            )
            color = m6_domain_type_color(assignment.domain_type_id)
            point_status = "domain_type"
        else:
            selection = M6DomainTypeSelection.unclassified()
            color = M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR
            point_status = "unclassified_domain"
        projection = _M6DomainTypeComponentProjection(
            ordered_component_id=observation.ordered_component_id,
            selection=selection,
            color=color,
            point_status=point_status,
        )
        components = frame_components.setdefault(observation.frame_index, {})
        previous = components.get(observation.ordered_component_id)
        if previous is not None and previous != projection:
            raise ValueError(
                "Overlapping ranges assign conflicting structural types to one component."
            )
        components[observation.ordered_component_id] = projection
    return M6DomainTypeOverlayIndex(
        classification=classification,
        frame_entries=tuple(
            (
                frame_index,
                tuple(components[key] for key in sorted(components)),
            )
            for frame_index, components in sorted(frame_components.items())
        ),
    )


def build_m6_domain_type_frame_overlay(
    analysis: MolecularM6OrientationAnalysis,
    overlay_index: M6DomainTypeOverlayIndex,
    *,
    frame_index: int,
    opacity_percent: int,
    selection: M6DomainTypeSelection | None = None,
) -> M6DomainTypeFrameOverlay:
    """Project frame-local M6 components onto shared structural type colors."""

    if not isinstance(analysis, MolecularM6OrientationAnalysis):
        raise TypeError("analysis must be MolecularM6OrientationAnalysis.")
    if not isinstance(overlay_index, M6DomainTypeOverlayIndex):
        raise TypeError("overlay_index must be an M6 domain type overlay index.")
    frame = _non_negative_int(frame_index, "frame_index")
    opacity = int(opacity_percent)
    if not 0 <= opacity <= 100:
        raise ValueError("opacity_percent must be between 0 and 100.")
    if selection is not None and not isinstance(selection, M6DomainTypeSelection):
        raise TypeError("selection must be an M6 domain type selection or None.")
    entries = overlay_index.entries_for_frame(frame)
    if not entries:
        return M6DomainTypeFrameOverlay(
            overlay=M6PointOverlay("domain_type", (), (), (), ()),
            highlighted_source_ids=(),
        )
    component_by_id = {
        component.ordered_component_id: component
        for component in analysis.frame_aggregates.domain_metrics.components
    }
    point_by_source_id = dict(
        zip(
            analysis.sample_coordinates.point_source_ids,
            analysis.sample_coordinates.source_points_xy_px,
        )
    )
    source_ids = []
    points_xy_px = []
    colors_rgba = []
    statuses = []
    highlighted = []
    alpha = round(255 * opacity / 100.0)
    for projection in entries:
        component_id = projection.ordered_component_id
        try:
            component = component_by_id[component_id]
        except KeyError as exc:
            raise ValueError(
                f"Classification references missing ordered component {component_id}."
            ) from exc
        for source_id in component.source_ids:
            try:
                point = point_by_source_id[source_id]
            except KeyError as exc:
                raise ValueError(
                    f"M6 component references missing source point {source_id!r}."
                ) from exc
            source_ids.append(source_id)
            points_xy_px.append(tuple(float(value) for value in point))
            colors_rgba.append((*projection.color[:3], alpha))
            statuses.append(projection.point_status)
            if selection == projection.selection:
                highlighted.append(source_id)

    return M6DomainTypeFrameOverlay(
        overlay=M6PointOverlay(
            mode="domain_type",
            source_ids=tuple(source_ids),
            points_xy_px=tuple(points_xy_px),
            colors_rgba=tuple(colors_rgba),
            point_statuses=tuple(statuses),
        ),
        highlighted_source_ids=tuple(highlighted),
    )


def _non_negative_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")
    return value


__all__ = [
    "M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR",
    "M6DomainTypeFrameOverlay",
    "M6DomainTypeOverlayIndex",
    "build_m6_domain_type_frame_overlay",
    "build_m6_domain_type_overlay_index",
]
