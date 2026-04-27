"""Quality scoring for refined step-edge geometry."""

from __future__ import annotations

import numpy as np

from nanotrack.core import EdgeGeometryQuality

from .polyline import EdgePolylineExtraction
from .refinement import EdgeRefinementResult
from .selection import DominantEdgeSelection


def assess_edge_geometry_quality(
    selection: DominantEdgeSelection,
    coarse_polyline: EdgePolylineExtraction,
    refined_polyline: EdgeRefinementResult,
    *,
    polyline_method: str,
    method_explicit: bool = True,
) -> EdgeGeometryQuality:
    """Build a compact review score for the final edge geometry."""

    coarse_score = float(getattr(selection, "quality_score", 0.0))
    coarse_confidence = _coarse_confidence(selection, coarse_polyline)
    refinement_score = float(np.clip(refined_polyline.mean_score, 0.0, 1.0))
    refinement_stability = float(np.clip(refined_polyline.stability_score, 0.0, 1.0))
    confidence = float(
        np.clip(
            0.45 * coarse_confidence + 0.40 * refinement_score + 0.15 * refinement_stability,
            0.0,
            1.0,
        )
    )

    warnings: list[str] = []
    if coarse_polyline.extraction_mode in {"single_pixel", "degenerate", "endpoints"}:
        warnings.append("degenerate_coarse_geometry")
    if coarse_confidence < 0.35:
        warnings.append("weak_coarse_geometry")
    if refinement_score < 0.35:
        warnings.append("weak_refinement_score")
    if refinement_stability < 0.45:
        warnings.append("unstable_refinement")
    if refined_polyline.search_radius_px > 0 and refined_polyline.mean_shift_px / float(refined_polyline.search_radius_px) > 0.75:
        warnings.append("large_refinement_shift")
    if confidence < 0.45:
        warnings.append("low_confidence")

    warnings = _deduplicate(warnings)
    return EdgeGeometryQuality(
        confidence=confidence,
        review_status="needs_review" if warnings else "ok",
        warnings=tuple(warnings),
        polyline_method=polyline_method,
        extraction_mode=coarse_polyline.extraction_mode,
        method_explicit=method_explicit,
        coarse_score=coarse_score,
        refinement_score=refinement_score,
        refinement_stability=refinement_stability,
        mean_shift_px=refined_polyline.mean_shift_px,
        refinement_mode=refined_polyline.refinement_mode,
    )


def format_edge_geometry_review(quality: EdgeGeometryQuality) -> str:
    """Return a short UI-friendly review summary."""

    method_label = quality.polyline_method or "unknown"
    summary = (
        f"geom {method_label}->{quality.extraction_mode or 'unknown'} | "
        f"conf {quality.confidence:.2f} | review {quality.review_status}"
    )
    if quality.warnings:
        summary += f" ({', '.join(quality.warnings)})"
    return summary


def _coarse_confidence(selection: DominantEdgeSelection, coarse_polyline: EdgePolylineExtraction) -> float:
    mean_probability = float(np.clip(selection.mean_probability, 0.0, 1.0))
    length_confidence = float(np.clip(coarse_polyline.axis_length_px / 12.0, 0.0, 1.0))
    score_confidence = float(1.0 - np.exp(-max(float(selection.quality_score), 0.0) / 10.0))
    return float(np.clip(0.55 * mean_probability + 0.25 * length_confidence + 0.20 * score_confidence, 0.0, 1.0))


def _deduplicate(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
