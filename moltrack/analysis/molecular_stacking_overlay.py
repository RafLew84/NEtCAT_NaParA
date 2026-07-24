"""Render-only projections for molecular A/B states and stacking domains."""

from __future__ import annotations

from colorsys import hsv_to_rgb
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from typing import Literal

from .lattice_row_models import (
    lattice_row_assignment_analysis_fingerprint,
)
from .molecular_orientation_prototype_models import (
    MolecularOrientationFrameData,
    MolecularOrientationPrototypeAnalysis,
    MolecularOrientationStateLabel,
    molecular_orientation_frames_measurement_fingerprint,
    molecular_orientation_prototype_analysis_fingerprint,
)
from .molecular_stacking_models import (
    MolecularStackingAnalysis,
    OrientationalSubdomain,
    StackingPattern,
    StackingQCReason,
)


MolecularStackingOverlayLayer = Literal[
    "ab_states",
    "stacking_subdomains",
]

_LAYERS = {"ab_states", "stacking_subdomains"}
_AB_STATE_COLORS = {
    "A": (0, 180, 255),
    "B": (240, 80, 150),
}
@dataclass(frozen=True)
class MolecularStackingDisplayResult:
    """Immutable analyses consumed by the UI without recomputation."""

    frames: tuple[MolecularOrientationFrameData, ...]
    prototype_analysis: MolecularOrientationPrototypeAnalysis
    stacking_analysis: MolecularStackingAnalysis

    def __post_init__(self) -> None:
        frames = tuple(self.frames)
        if any(
            not isinstance(value, MolecularOrientationFrameData)
            for value in frames
        ):
            raise TypeError(
                "frames must contain MolecularOrientationFrameData."
            )
        frame_indices = tuple(value.frame_index for value in frames)
        if frame_indices != tuple(sorted(set(frame_indices))):
            raise ValueError("frames must be sorted and unique.")
        if not isinstance(
            self.prototype_analysis,
            MolecularOrientationPrototypeAnalysis,
        ):
            raise TypeError(
                "prototype_analysis has an invalid type."
            )
        if not isinstance(
            self.stacking_analysis,
            MolecularStackingAnalysis,
        ):
            raise TypeError("stacking_analysis has an invalid type.")
        if (
            frame_indices
            != self.prototype_analysis.input_frame_indices
            or frame_indices
            != self.stacking_analysis.input_frame_indices
        ):
            raise ValueError(
                "Display frames must match both stacking analyses."
            )
        if (
            self.stacking_analysis.prototype_analysis_fingerprint
            != molecular_orientation_prototype_analysis_fingerprint(
                self.prototype_analysis
            )
        ):
            raise ValueError(
                "Stacking result must reference prototype_analysis."
            )
        row_fingerprints = tuple(
            (
                frame.frame_index,
                lattice_row_assignment_analysis_fingerprint(
                    frame.row_assignment
                ),
            )
            for frame in frames
        )
        if (
            row_fingerprints
            != self.prototype_analysis.row_assignment_fingerprints
            or row_fingerprints
            != self.stacking_analysis.row_assignment_fingerprints
        ):
            raise ValueError(
                "Display frames must match analyzed row assignments."
            )
        if (
            molecular_orientation_frames_measurement_fingerprint(frames)
            != self.prototype_analysis.measurement_fingerprint
        ):
            raise ValueError(
                "Display frames must match analyzed orientations."
            )
        object.__setattr__(self, "frames", frames)

    def frame_data(
        self,
        frame_index: int,
    ) -> MolecularOrientationFrameData:
        normalized = int(frame_index)
        for frame in self.frames:
            if frame.frame_index == normalized:
                return frame
        raise KeyError(f"Unknown stacking frame index: {normalized}.")


@dataclass(frozen=True)
class MolecularStackingFrameGeometry:
    """Current-frame source coordinates used only for drawing."""

    frame_index: int
    source_ids: tuple[str, ...]
    points_xy_px: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        frame_index = int(self.frame_index)
        if frame_index < 0:
            raise ValueError("frame_index must be non-negative.")
        source_ids = tuple(self.source_ids)
        points = tuple(
            tuple(float(coordinate) for coordinate in point)
            for point in self.points_xy_px
        )
        if len(source_ids) != len(points):
            raise ValueError(
                "source_ids and points_xy_px must have equal lengths."
            )
        if (
            len(set(source_ids)) != len(source_ids)
            or any(not isinstance(value, str) or not value for value in source_ids)
        ):
            raise ValueError("source_ids must be unique non-empty strings.")
        if any(
            len(point) != 2
            or not all(isfinite(coordinate) for coordinate in point)
            for point in points
        ):
            raise ValueError(
                "points_xy_px must contain finite XY coordinates."
            )
        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "points_xy_px", points)


@dataclass(frozen=True)
class MolecularStackingPointOverlay:
    """One batched point layer aligned with source-image pixels."""

    layer: MolecularStackingOverlayLayer
    source_ids: tuple[str, ...]
    points_xy_px: tuple[tuple[float, float], ...]
    colors_rgba: tuple[tuple[int, int, int, int], ...]
    point_statuses: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.layer not in _LAYERS:
            raise ValueError(f"Unsupported stacking layer: {self.layer!r}.")
        count = len(self.source_ids)
        if not (
            len(self.points_xy_px)
            == len(self.colors_rgba)
            == len(self.point_statuses)
            == count
        ):
            raise ValueError(
                "Stacking overlay arrays must have equal lengths."
            )
        if len(set(self.source_ids)) != count:
            raise ValueError("Stacking overlay source_ids must be unique.")
        if any(
            len(color) != 4
            or any(not 0 <= int(channel) <= 255 for channel in color)
            for color in self.colors_rgba
        ):
            raise ValueError("Stacking overlay colors must be RGBA bytes.")

    @property
    def point_count(self) -> int:
        return len(self.source_ids)


@dataclass(frozen=True)
class MolecularStackingInspection:
    """Auditable hierarchy for one selected molecule."""

    frame_index: int
    source_id: str
    parent_lattice_domain_id: str
    subdomain_id: str | None
    state_label: MolecularOrientationStateLabel | None
    pattern: StackingPattern
    mode: str | None
    phase: str | None
    axis_candidate_index: int | None
    axis_angle_deg: float | None
    prototype_a_angle_deg: float | None
    prototype_b_angle_deg: float | None
    score: float | None
    confidence: float
    coverage_fraction: float
    qc_reasons: tuple[StackingQCReason, ...]
    parent_pattern: StackingPattern
    parent_score: float | None
    parent_confidence: float
    parent_coverage_fraction: float
    parent_qc_reasons: tuple[StackingQCReason, ...]


def build_molecular_stacking_point_overlay(
    display: MolecularStackingDisplayResult,
    geometry: MolecularStackingFrameGeometry,
    *,
    layer: MolecularStackingOverlayLayer,
    opacity_percent: int,
) -> MolecularStackingPointOverlay:
    """Project stored A/B or subdomain results to one render batch."""

    _require_display(display)
    if not isinstance(geometry, MolecularStackingFrameGeometry):
        raise TypeError("geometry must be MolecularStackingFrameGeometry.")
    if layer not in _LAYERS:
        raise ValueError(f"Unsupported stacking layer: {layer!r}.")
    opacity = int(opacity_percent)
    if not 0 <= opacity <= 100:
        raise ValueError("opacity_percent must be between 0 and 100.")
    if geometry.frame_index not in display.stacking_analysis.input_frame_indices:
        return MolecularStackingPointOverlay(layer, (), (), (), ())

    if layer == "ab_states":
        statuses = _ab_state_by_source(display, geometry.frame_index)
        colors_by_source = {
            source_id: _AB_STATE_COLORS[state]
            for source_id, state in statuses.items()
        }
    else:
        subdomains = _subdomain_by_source(
            display,
            geometry.frame_index,
        )
        statuses = {
            source_id: _subdomain_status(subdomain)
            for source_id, subdomain in subdomains.items()
        }
        colors_by_source = {
            source_id: _subdomain_color(subdomain)
            for source_id, subdomain in subdomains.items()
        }

    alpha = round(255 * opacity / 100.0)
    source_ids = tuple(
        source_id
        for source_id in geometry.source_ids
        if source_id in statuses
    )
    point_by_id = dict(zip(geometry.source_ids, geometry.points_xy_px))
    return MolecularStackingPointOverlay(
        layer=layer,
        source_ids=source_ids,
        points_xy_px=tuple(point_by_id[value] for value in source_ids),
        colors_rgba=tuple(
            (*colors_by_source[value], alpha) for value in source_ids
        ),
        point_statuses=tuple(statuses[value] for value in source_ids),
    )


def build_molecular_stacking_inspection(
    display: MolecularStackingDisplayResult,
    *,
    frame_index: int,
    source_id: str,
) -> MolecularStackingInspection | None:
    """Find the stored parent, child and A/B evidence for one molecule."""

    _require_display(display)
    source_id = str(source_id)
    try:
        frame = display.frame_data(frame_index)
    except KeyError:
        return None
    domain = next(
        (
            value
            for value in frame.row_assignment.domain_assignments
            if source_id in value.source_ids
        ),
        None,
    )
    if domain is None:
        return None
    order = display.stacking_analysis.order_for_domain(
        frame_index,
        domain.lattice_domain_id,
    )
    subdomain = next(
        (
            value
            for value in display.stacking_analysis.subdomains
            if value.frame_index == frame_index
            and value.parent_lattice_domain_id == domain.lattice_domain_id
            and source_id in value.source_ids
        ),
        None,
    )
    state_label = _ab_state_by_source(
        display,
        frame_index,
    ).get(source_id)
    selected_result = order if subdomain is None else subdomain
    axis_candidate_index = selected_result.axis_candidate_index
    axis_angle_deg = selected_result.axis_angle_deg
    if (
        axis_candidate_index is None
        and domain.selected_candidate_index is not None
    ):
        axis_candidate_index = domain.selected_candidate_index
        axis_angle_deg = domain.candidates[
            axis_candidate_index
        ].axis_angle_deg
    return MolecularStackingInspection(
        frame_index=int(frame_index),
        source_id=source_id,
        parent_lattice_domain_id=domain.lattice_domain_id,
        subdomain_id=(
            None if subdomain is None else subdomain.subdomain_id
        ),
        state_label=state_label,
        pattern=selected_result.pattern,
        mode=selected_result.mode,
        phase=selected_result.phase,
        axis_candidate_index=axis_candidate_index,
        axis_angle_deg=axis_angle_deg,
        prototype_a_angle_deg=order.prototype_a_angle_deg,
        prototype_b_angle_deg=order.prototype_b_angle_deg,
        score=selected_result.score,
        confidence=selected_result.confidence,
        coverage_fraction=selected_result.coverage_fraction,
        qc_reasons=selected_result.qc_reasons,
        parent_pattern=order.pattern,
        parent_score=order.score,
        parent_confidence=order.confidence,
        parent_coverage_fraction=order.coverage_fraction,
        parent_qc_reasons=order.qc_reasons,
    )


def _ab_state_by_source(
    display: MolecularStackingDisplayResult,
    frame_index: int,
) -> dict[str, MolecularOrientationStateLabel]:
    selected_axes = {
        (order.lattice_domain_id, order.axis_candidate_index)
        for order in display.stacking_analysis.orders
        if order.frame_index == frame_index
        and order.axis_candidate_index is not None
    }
    return {
        assignment.source_id: assignment.state_label
        for evidence in display.prototype_analysis.axis_evidence
        if evidence.frame_index == frame_index
        and (
            evidence.lattice_domain_id,
            evidence.candidate_index,
        )
        in selected_axes
        for assignment in evidence.assignments
    }


def _subdomain_by_source(
    display: MolecularStackingDisplayResult,
    frame_index: int,
) -> dict[str, OrientationalSubdomain]:
    result = {}
    for subdomain in display.stacking_analysis.subdomains:
        if subdomain.frame_index != frame_index:
            continue
        for source_id in subdomain.source_ids:
            result[source_id] = subdomain
    return result


def _subdomain_status(subdomain: OrientationalSubdomain) -> str:
    pattern = (
        "uniform"
        if subdomain.pattern == "uniform"
        else f"{subdomain.mode}/{subdomain.phase}"
    )
    return f"{subdomain.subdomain_id} | {pattern}"


def _subdomain_color(
    subdomain: OrientationalSubdomain,
) -> tuple[int, int, int]:
    identity = (
        f"{subdomain.parent_lattice_domain_id}\0"
        f"{subdomain.subdomain_id}"
    ).encode("utf-8")
    digest = sha256(identity).digest()
    hue = int.from_bytes(digest[:4], "big") / float(2**32)
    saturation = 0.60 + 0.20 * digest[4] / 255.0
    value = 0.78 + 0.17 * digest[5] / 255.0
    return tuple(
        round(255 * channel)
        for channel in hsv_to_rgb(hue, saturation, value)
    )


def _require_display(
    value: MolecularStackingDisplayResult,
) -> None:
    if not isinstance(value, MolecularStackingDisplayResult):
        raise TypeError("display must be MolecularStackingDisplayResult.")


__all__ = [
    "MolecularStackingDisplayResult",
    "MolecularStackingFrameGeometry",
    "MolecularStackingInspection",
    "MolecularStackingOverlayLayer",
    "MolecularStackingPointOverlay",
    "build_molecular_stacking_inspection",
    "build_molecular_stacking_point_overlay",
]
