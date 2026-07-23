from __future__ import annotations

import colorsys
import hashlib
from dataclasses import dataclass
from math import isfinite
from typing import Literal, Sequence

from .molecular_m6_analysis import MolecularM6OrientationAnalysis


M6AnalysisOverlayMode = Literal[
    "none",
    "q6",
    "orientation",
    "q3",
    "m3_orientation",
    "symmetry_evidence",
    "domain_id",
    "lattice_domains",
    "domain_boundaries",
]
M6OverlayMode = Literal[
    "none",
    "q6",
    "orientation",
    "q3",
    "m3_orientation",
    "symmetry_evidence",
    "domain_id",
    "lattice_domains",
    "domain_boundaries",
    "domain_type",
]
M6OverlayPointStatus = Literal[
    "q6",
    "orientation",
    "q3",
    "m3_orientation",
    "symmetry_trifold",
    "symmetry_sixfold",
    "symmetry_mixed",
    "symmetry_disordered",
    "symmetry_ambiguous",
    "symmetry_unavailable",
    "domain",
    "lattice_domain_core",
    "lattice_domain_halo",
    "lattice_boundary",
    "domain_type",
    "unclassified_domain",
    "small_ordered_island",
    "unassigned",
    "undefined_orientation",
    "insufficient_neighbors",
    "duplicate_excluded",
    "invalid_position",
]

M6_ANALYSIS_OVERLAY_MODES: tuple[M6AnalysisOverlayMode, ...] = (
    "none",
    "q6",
    "orientation",
    "q3",
    "m3_orientation",
    "symmetry_evidence",
    "domain_id",
    "lattice_domains",
    "domain_boundaries",
)
M6_OVERLAY_MODES: tuple[M6OverlayMode, ...] = (
    *M6_ANALYSIS_OVERLAY_MODES,
    "domain_type",
)

_UNASSIGNED_COLOR = (145, 155, 165)
_UNDEFINED_ORIENTATION_COLOR = (160, 135, 175)
_SMALL_ISLAND_COLOR = (165, 145, 95)
_LATTICE_BOUNDARY_COLOR = (220, 70, 55)
_QC_COLORS = {
    "insufficient_neighbors": (135, 145, 150),
    "duplicate_excluded": (100, 110, 120),
    "invalid_position": (80, 85, 90),
}
M6_SYMMETRY_EVIDENCE_LEGEND: tuple[
    tuple[str, tuple[int, int, int]], ...
] = (
    ("Trifold", (0, 150, 136)),
    ("Sixfold", (40, 105, 205)),
    ("Mixed", (180, 70, 170)),
    ("Disordered", (220, 135, 35)),
    ("Ambiguous", (135, 125, 150)),
    ("Unavailable", (105, 110, 115)),
)
_SYMMETRY_COLORS = {
    label.lower(): color for label, color in M6_SYMMETRY_EVIDENCE_LEGEND
}
_SYMMETRY_STATUSES: dict[str, M6OverlayPointStatus] = {
    "trifold": "symmetry_trifold",
    "sixfold": "symmetry_sixfold",
    "mixed": "symmetry_mixed",
    "disordered": "symmetry_disordered",
    "ambiguous": "symmetry_ambiguous",
    "unavailable": "symmetry_unavailable",
}
_VIRIDIS_STOPS = (
    (68, 1, 84),
    (59, 82, 139),
    (33, 145, 140),
    (94, 201, 98),
    (253, 231, 37),
)


@dataclass(frozen=True)
class M6OverlayPointState:
    """Render-only projection of one molecule from an M6 analysis result."""

    source_id: str
    source_xy_px: tuple[float, float]
    q6: float | None
    orientation_deg: float | None
    orientation_status: str
    computation_status: str
    assignment_status: str
    m6_orientation_domain_id: int
    ordered_component_id: int
    component_type: str
    q3: float | None = None
    m3_orientation_deg: float | None = None
    m3_orientation_status: str = "unavailable"
    symmetry_model: str | None = None
    symmetry_confidence: float | None = None
    lattice_domain_id: str | None = None
    lattice_point_role: str = "unassigned"
    lattice_boundary_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id:
            raise ValueError("source_id must be a non-empty string.")
        point = tuple(float(value) for value in self.source_xy_px)
        if len(point) != 2 or not all(isfinite(value) for value in point):
            raise ValueError("source_xy_px must contain two finite coordinates.")
        if self.q6 is not None and not 0.0 <= float(self.q6) <= 1.0:
            raise ValueError("q6 must be None or lie between 0 and 1.")
        if self.orientation_deg is not None and not isfinite(float(self.orientation_deg)):
            raise ValueError("orientation_deg must be None or finite.")
        if self.q3 is not None and not 0.0 <= float(self.q3) <= 1.0:
            raise ValueError("q3 must be None or lie between 0 and 1.")
        if self.m3_orientation_deg is not None and not isfinite(
            float(self.m3_orientation_deg)
        ):
            raise ValueError("m3_orientation_deg must be None or finite.")
        if self.symmetry_model is not None and self.symmetry_model not in {
            "trifold",
            "sixfold",
            "mixed",
            "disordered",
            "ambiguous",
            "unavailable",
        }:
            raise ValueError("symmetry_model is unsupported.")
        if self.symmetry_confidence is not None and not 0.0 <= float(
            self.symmetry_confidence
        ) <= 1.0:
            raise ValueError("symmetry_confidence must lie between 0 and 1.")
        if self.lattice_domain_id is not None and (
            not isinstance(self.lattice_domain_id, str) or not self.lattice_domain_id
        ):
            raise ValueError("lattice_domain_id must be None or a non-empty string.")
        if self.lattice_point_role not in {"core", "halo", "boundary", "unassigned"}:
            raise ValueError("lattice_point_role is unsupported.")
        if (self.lattice_point_role == "boundary") != (
            self.lattice_boundary_reason is not None
        ):
            raise ValueError("Only lattice boundary points require a boundary reason.")
        object.__setattr__(self, "source_xy_px", point)


@dataclass(frozen=True)
class M6PointOverlay:
    """One batched, immutable point overlay aligned with source-image pixels."""

    mode: M6OverlayMode
    source_ids: tuple[str, ...]
    points_xy_px: tuple[tuple[float, float], ...]
    colors_rgba: tuple[tuple[int, int, int, int], ...]
    point_statuses: tuple[M6OverlayPointStatus, ...]

    def __post_init__(self) -> None:
        if self.mode not in M6_OVERLAY_MODES:
            raise ValueError(f"Unsupported M6 overlay mode: {self.mode!r}.")
        count = len(self.source_ids)
        if not (
            len(self.points_xy_px)
            == len(self.colors_rgba)
            == len(self.point_statuses)
            == count
        ):
            raise ValueError("M6 overlay point arrays must have equal lengths.")
        if len(set(self.source_ids)) != count:
            raise ValueError("M6 overlay source_ids must be unique.")
        for color in self.colors_rgba:
            if len(color) != 4 or any(not 0 <= int(channel) <= 255 for channel in color):
                raise ValueError("M6 overlay colors must be RGBA bytes.")

    @property
    def point_count(self) -> int:
        return len(self.source_ids)


def build_m6_point_overlay(
    point_states: Sequence[M6OverlayPointState],
    *,
    mode: M6AnalysisOverlayMode,
    opacity_percent: int,
    show_unassigned_points: bool = True,
) -> M6PointOverlay:
    """Map immutable M6 point states to one deterministic render batch."""

    if mode not in M6_ANALYSIS_OVERLAY_MODES:
        raise ValueError(f"Unsupported M6 overlay mode: {mode!r}.")
    opacity = int(opacity_percent)
    if not 0 <= opacity <= 100:
        raise ValueError("opacity_percent must be between 0 and 100.")
    states = tuple(point_states)
    if any(not isinstance(point, M6OverlayPointState) for point in states):
        raise TypeError("point_states must contain M6OverlayPointState values.")
    if mode == "none":
        return M6PointOverlay(mode, (), (), (), ())

    source_ids: list[str] = []
    points_xy_px: list[tuple[float, float]] = []
    colors_rgba: list[tuple[int, int, int, int]] = []
    statuses: list[M6OverlayPointStatus] = []
    base_alpha = round(255 * opacity / 100.0)
    for point in states:
        if not show_unassigned_points and not _is_available_for_mode(point, mode):
            continue
        rgb, status, alpha_scale = _point_color(point, mode=mode)
        source_ids.append(point.source_id)
        points_xy_px.append(point.source_xy_px)
        colors_rgba.append((*rgb, round(base_alpha * alpha_scale)))
        statuses.append(status)
    return M6PointOverlay(
        mode=mode,
        source_ids=tuple(source_ids),
        points_xy_px=tuple(points_xy_px),
        colors_rgba=tuple(colors_rgba),
        point_statuses=tuple(statuses),
    )


def _is_available_for_mode(
    point: M6OverlayPointState,
    mode: M6AnalysisOverlayMode,
) -> bool:
    if point.computation_status != "valid_order":
        return False
    if mode == "q3":
        return point.q3 is not None
    if mode == "m3_orientation":
        return (
            point.m3_orientation_status == "defined"
            and point.m3_orientation_deg is not None
        )
    if mode == "symmetry_evidence":
        return point.symmetry_model not in {None, "unavailable"}
    if mode == "lattice_domains":
        return point.lattice_domain_id is not None
    if mode == "domain_boundaries":
        return point.lattice_point_role == "boundary"
    return point.assignment_status == "assigned"


def build_m6_point_overlay_from_analysis(
    analysis: MolecularM6OrientationAnalysis,
    *,
    mode: M6AnalysisOverlayMode,
    opacity_percent: int,
    show_unassigned_points: bool = True,
) -> M6PointOverlay:
    """Project a complete M6 result back onto its source-image coordinates."""

    if not isinstance(analysis, MolecularM6OrientationAnalysis):
        raise TypeError("analysis must be MolecularM6OrientationAnalysis.")
    sample = analysis.sample_coordinates
    local = analysis.local_order
    multisymmetry = analysis.local_multisymmetry_order
    evidence = analysis.local_symmetry_evidence
    segmentation = analysis.segmentation
    lattice = analysis.lattice_domain_analysis
    states = tuple(
        M6OverlayPointState(
            source_id=source_id,
            source_xy_px=source_xy_px,
            q6=local.q6[index],
            orientation_deg=local.lattice_orientation_deg[index],
            orientation_status=local.orientation_status[index],
            computation_status=local.computation_status[index],
            assignment_status=segmentation.assignment_status[index],
            m6_orientation_domain_id=segmentation.m6_orientation_domain_id[index],
            ordered_component_id=segmentation.ordered_component_id[index],
            component_type=segmentation.component_type[index],
            q3=None if multisymmetry is None else multisymmetry.q3[index],
            m3_orientation_deg=(
                None
                if multisymmetry is None
                else multisymmetry.theta3_lattice_deg[index]
            ),
            m3_orientation_status=(
                "unavailable"
                if multisymmetry is None
                else multisymmetry.m3_orientation_status[index]
            ),
            symmetry_model=None if evidence is None else evidence.best_model[index],
            symmetry_confidence=(
                None if evidence is None else evidence.classification_confidence[index]
            ),
            lattice_domain_id=(
                None if lattice is None else lattice.point_lattice_domain_id[index]
            ),
            lattice_point_role=(
                "unassigned" if lattice is None else lattice.point_role[index]
            ),
            lattice_boundary_reason=(
                None if lattice is None else lattice.boundary_reason[index]
            ),
        )
        for index, (source_id, source_xy_px) in enumerate(
            zip(sample.point_source_ids, sample.source_points_xy_px)
        )
    )
    return build_m6_point_overlay(
        states,
        mode=mode,
        opacity_percent=opacity_percent,
        show_unassigned_points=show_unassigned_points,
    )


def _point_color(
    point: M6OverlayPointState,
    *,
    mode: M6AnalysisOverlayMode,
) -> tuple[tuple[int, int, int], M6OverlayPointStatus, float]:
    if point.computation_status != "valid_order":
        status = point.computation_status
        color = _QC_COLORS.get(status, _UNASSIGNED_COLOR)
        return color, status, 1.0
    if mode == "q3":
        if point.q3 is None:
            return _UNASSIGNED_COLOR, "unassigned", 1.0
        return _interpolate_viridis(float(point.q3)), "q3", 1.0
    if mode == "m3_orientation":
        if (
            point.m3_orientation_status != "defined"
            or point.m3_orientation_deg is None
        ):
            return _UNDEFINED_ORIENTATION_COLOR, "undefined_orientation", 1.0
        q3 = 0.0 if point.q3 is None else float(point.q3)
        return (
            _orientation_color(float(point.m3_orientation_deg)),
            "m3_orientation",
            0.35 + 0.65 * q3,
        )
    if mode == "symmetry_evidence":
        model = point.symmetry_model or "unavailable"
        confidence = (
            0.0
            if point.symmetry_confidence is None
            else float(point.symmetry_confidence)
        )
        return (
            _SYMMETRY_COLORS[model],
            _SYMMETRY_STATUSES[model],
            0.3 + 0.7 * confidence,
        )
    if mode == "lattice_domains":
        if point.lattice_domain_id is None:
            if point.lattice_point_role == "boundary":
                return _LATTICE_BOUNDARY_COLOR, "lattice_boundary", 0.8
            return _UNASSIGNED_COLOR, "unassigned", 0.35
        status: M6OverlayPointStatus = (
            "lattice_domain_core"
            if point.lattice_point_role == "core"
            else "lattice_domain_halo"
        )
        alpha_scale = 1.0 if point.lattice_point_role == "core" else 0.55
        return _lattice_domain_color(point.lattice_domain_id), status, alpha_scale
    if mode == "domain_boundaries":
        if point.lattice_point_role == "boundary":
            return _LATTICE_BOUNDARY_COLOR, "lattice_boundary", 1.0
        return _UNASSIGNED_COLOR, "unassigned", 0.15
    if point.assignment_status != "assigned":
        return _UNASSIGNED_COLOR, "unassigned", 1.0
    if mode == "q6":
        if point.q6 is None:
            return _UNASSIGNED_COLOR, "unassigned", 1.0
        return _interpolate_viridis(float(point.q6)), "q6", 1.0
    if mode == "orientation":
        if point.orientation_status != "defined" or point.orientation_deg is None:
            return _UNDEFINED_ORIENTATION_COLOR, "undefined_orientation", 1.0
        q6 = 0.0 if point.q6 is None else float(point.q6)
        return _orientation_color(float(point.orientation_deg)), "orientation", 0.35 + 0.65 * q6
    if point.component_type == "full_domain" and point.m6_orientation_domain_id >= 0:
        return _domain_color(point.m6_orientation_domain_id), "domain", 1.0
    if point.component_type == "small_ordered_island":
        return _SMALL_ISLAND_COLOR, "small_ordered_island", 1.0
    return _UNASSIGNED_COLOR, "unassigned", 1.0


def _interpolate_viridis(value: float) -> tuple[int, int, int]:
    scaled = min(1.0, max(0.0, value)) * (len(_VIRIDIS_STOPS) - 1)
    left_index = min(int(scaled), len(_VIRIDIS_STOPS) - 2)
    fraction = scaled - left_index
    left = _VIRIDIS_STOPS[left_index]
    right = _VIRIDIS_STOPS[left_index + 1]
    return tuple(
        round(left[channel] + fraction * (right[channel] - left[channel]))
        for channel in range(3)
    )


def _orientation_color(orientation_deg: float) -> tuple[int, int, int]:
    hue = (orientation_deg % 60.0) / 60.0
    return tuple(round(255 * value) for value in colorsys.hsv_to_rgb(hue, 0.72, 0.95))


def _domain_color(domain_id: int) -> tuple[int, int, int]:
    hue = (0.08 + int(domain_id) * 0.6180339887498949) % 1.0
    return tuple(round(255 * value) for value in colorsys.hsv_to_rgb(hue, 0.62, 0.88))


def _lattice_domain_color(domain_id: str) -> tuple[int, int, int]:
    digest = hashlib.sha256(domain_id.encode("utf-8")).digest()
    hue = int.from_bytes(digest[:4], "big") / float(2**32)
    return tuple(round(255 * value) for value in colorsys.hsv_to_rgb(hue, 0.66, 0.9))
