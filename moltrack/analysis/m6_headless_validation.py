from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .first_shell_builder import build_first_shell_graph
from .first_shell_graph import FirstShellGraph
from .m6_settings import MolecularM6OrientationAnalysisSettings
from .m6_headless_validation_manifest import (
    M6HeadlessValidationFrame,
    M6HeadlessValidationManifest,
)
from .m6_headless_validation_results import (
    M6HeadlessValidationFrameResult,
    M6HeadlessValidationReport,
    M6HeadlessValidationWarning,
    _condition_summaries,
    _frame_summary,
)
from .orientation_domain_analysis import (
    analyze_m6_orientation_domains,
)
from .pair_correlation import PairCorrelationResult, compute_pair_correlation


def load_m6_headless_validation_manifest(
    path: str | Path,
) -> M6HeadlessValidationManifest:
    manifest_path = Path(path)
    with manifest_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return M6HeadlessValidationManifest.from_dict(payload)


def run_m6_headless_validation(
    manifest: M6HeadlessValidationManifest,
) -> M6HeadlessValidationReport:
    """Run graph, M6 domains, footprint, and g(r) without UI or session state."""

    if not isinstance(manifest, M6HeadlessValidationManifest):
        raise TypeError("manifest must be M6HeadlessValidationManifest.")
    frame_results = tuple(
        _run_validation_frame(
            frame,
            settings=manifest.accepted_settings,
            unassigned_warning_threshold=(
                manifest.high_unassigned_fraction_warning_threshold
            ),
        )
        for frame in manifest.frames
    )
    return M6HeadlessValidationReport(
        manifest_id=manifest.manifest_id,
        algorithm_version=manifest.algorithm_version,
        accepted_settings=manifest.accepted_settings,
        frame_results=frame_results,
        condition_orientation_summaries=_condition_summaries(frame_results),
    )


def _run_validation_frame(
    frame: M6HeadlessValidationFrame,
    *,
    settings: MolecularM6OrientationAnalysisSettings,
    unassigned_warning_threshold: float,
) -> M6HeadlessValidationFrameResult:
    all_points = np.asarray(frame.points_xy_nm, dtype=np.float64).reshape((-1, 2))
    invalid_ids = set(frame.invalid_position_point_ids)
    core_indices = tuple(
        index
        for index, point_id in enumerate(frame.point_ids)
        if point_id not in invalid_ids
    )
    core_index_set = set(core_indices)
    points = all_points[np.asarray(core_indices, dtype=np.int64)]
    point_ids = tuple(frame.point_ids[index] for index in core_indices)
    boundary_distances = tuple(
        distance
        for index, distance in enumerate(
            frame.distance_to_valid_fov_boundary_nm
        )
        if index in core_index_set
    )
    warnings: list[M6HeadlessValidationWarning] = []
    if not frame.valid_fov_reliable:
        warnings.append(
            M6HeadlessValidationWarning(
                "unreliable_valid_fov",
                "The manifest marks valid FOV geometry as scientifically unreliable.",
            )
        )
    graph = _build_validation_graph(
        frame,
        points=points,
        point_ids=point_ids,
        settings=settings,
    )
    graph_is_blocking = (
        graph.construction_method == "rank2_radius_fallback"
        or graph.qc_status.startswith("blocking_")
    )
    if graph_is_blocking:
        warnings.append(
            M6HeadlessValidationWarning(
                "graph_fallback",
                "Graph construction used a blocking rank-2 radius fallback.",
            )
        )
        pair_correlation = _compute_validation_pair_correlation(
            frame,
            points=points,
            point_ids=point_ids,
            graph=graph,
            settings=settings,
        )
        return M6HeadlessValidationFrameResult(
            frame=frame,
            accepted_settings=settings,
            status="blocked_graph_fallback",
            first_shell_graph=graph,
            analysis=None,
            pair_correlation=pair_correlation,
            summary=None,
            warnings=tuple(warnings),
        )
    analysis = analyze_m6_orientation_domains(
        points,
        point_ids=point_ids,
        distance_to_valid_fov_boundary_nm=boundary_distances,
        settings=settings,
        orientation_reference=frame.orientation_reference,
        spatial_calibration_fingerprint=frame.spatial_calibration_fingerprint,
        registration_fingerprint=frame.registration_fingerprint,
        window_geometry="rectangular",
        window_size_nm=frame.window_size_nm,
        window_origin_nm=frame.window_origin_nm,
    )
    if analysis.first_shell_graph != graph:
        raise RuntimeError("Headless validation graph changed between public core stages.")
    graph = analysis.first_shell_graph
    if graph.delaunay_degeneracy_qc:
        warnings.append(
            M6HeadlessValidationWarning(
                "delaunay_degeneracy",
                "Delaunay ambiguity was detected and ambiguous edges were excluded.",
            )
        )
    pair_correlation = _compute_validation_pair_correlation(
        frame,
        points=points,
        point_ids=point_ids,
        graph=graph,
        settings=settings,
    )
    summary = _frame_summary(frame, analysis)
    if (
        summary.unassigned_molecule_fraction is not None
        and summary.unassigned_molecule_fraction > unassigned_warning_threshold
    ):
        warnings.append(
            M6HeadlessValidationWarning(
                "high_unassigned_fraction",
                "Unassigned molecule fraction exceeds the manifest warning threshold.",
            )
        )
    return M6HeadlessValidationFrameResult(
        frame=frame,
        accepted_settings=settings,
        status="complete",
        first_shell_graph=graph,
        analysis=analysis,
        pair_correlation=pair_correlation,
        summary=summary,
        warnings=tuple(warnings),
    )


def _build_validation_graph(
    frame: M6HeadlessValidationFrame,
    *,
    points: np.ndarray,
    point_ids: tuple[str, ...],
    settings: MolecularM6OrientationAnalysisSettings,
) -> FirstShellGraph:
    return build_first_shell_graph(
        points,
        point_ids=point_ids,
        settings=settings,
        orientation_reference=frame.orientation_reference,
        spatial_calibration_fingerprint=frame.spatial_calibration_fingerprint,
        registration_fingerprint=frame.registration_fingerprint,
    )


def _compute_validation_pair_correlation(
    frame: M6HeadlessValidationFrame,
    *,
    points: np.ndarray,
    point_ids: tuple[str, ...],
    graph: FirstShellGraph,
    settings: MolecularM6OrientationAnalysisSettings,
) -> PairCorrelationResult:
    return compute_pair_correlation(
        points,
        point_ids=point_ids,
        point_frame_indices=(frame.source_frame_index,) * len(points),
        first_shell_graph=graph,
        frame_index=frame.source_frame_index,
        settings=settings,
        window_geometry="rectangular",
        window_size_nm=frame.window_size_nm,
        window_origin_nm=frame.window_origin_nm,
    )
