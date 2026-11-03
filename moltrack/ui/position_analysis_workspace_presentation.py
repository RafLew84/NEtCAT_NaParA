from __future__ import annotations

from dataclasses import dataclass

from moltrack.analysis.domain_analysis import (
    ABC_ORIENTATION_CLASSIFIER_ID,
    DomainAnalysisWorkspaceSnapshot,
    M6FrameGate,
)


@dataclass(frozen=True)
class PositionAnalysisAdvancedTabText:
    range_trends: str
    sixfold_bond_order: str
    domain_types: str
    classifier: str
    order_hierarchy: str


def position_analysis_advanced_tab_text(
    snapshot: DomainAnalysisWorkspaceSnapshot,
) -> PositionAnalysisAdvancedTabText:
    """Project one immutable workspace snapshot into advanced read views."""

    publication = snapshot.published
    if publication is None:
        empty = "No published Domain Analysis result."
        return PositionAnalysisAdvancedTabText(empty, empty, empty, empty, empty)
    gate = publication.result.m6_gate
    if gate is None:
        raise ValueError("A Domain Analysis publication must contain an M6 gate.")
    active_frame = next(
        (
            frame
            for frame in gate.frames
            if frame.physical_frame_id == snapshot.active_physical_frame_id
        ),
        None,
    )
    return PositionAnalysisAdvancedTabText(
        range_trends="\n".join(_range_frame_line(frame) for frame in gate.frames),
        sixfold_bond_order=_m6_gate_text(active_frame),
        domain_types=_domain_types_text(active_frame),
        classifier=_classifier_text(snapshot),
        order_hierarchy=_order_hierarchy_text(active_frame),
    )


def _range_frame_line(frame: M6FrameGate) -> str:
    return (
        f"Frame {frame.frame_index + 1} ({frame.physical_frame_id}): "
        f"{len(frame.full_domains)} full domains, "
        f"{len(frame.small_ordered_islands)} small ordered islands, "
        f"{len(frame.outside_members)} molecules outside M6."
    )


def _m6_gate_text(frame: M6FrameGate | None) -> str:
    if frame is None:
        return "No published M6 gate for the current frame."
    return "\n".join(
        (
            f"Frame {frame.frame_index + 1} ({frame.physical_frame_id})",
            f"Algorithm: {frame.backend_identity.algorithm_version}",
            f"Gate fingerprint: {frame.m6_gate_fingerprint}",
            f"Analyzed molecules: {frame.analyzed_molecule_count}",
            f"Full-domain area: {frame.full_domain_area_nm2:.6g} nm²",
            f"Small-island area: {frame.small_ordered_island_area_nm2:.6g} nm²",
            f"Outside area: {frame.outside_area_nm2:.6g} nm²",
        )
    )


def _domain_types_text(frame: M6FrameGate | None) -> str:
    if frame is None:
        return "No published domain types for the current frame."
    lines = []
    for component in frame.full_domains + frame.small_ordered_islands:
        label = component.component_type.replace("_", " ").title()
        qc = ", ".join(component.qc_flags) or "none"
        lines.append(
            f"{component.lattice_domain_id}: {label}; "
            f"molecules={len(component.members)}; "
            f"area={component.footprint_area_nm2:.6g} nm²; QC={qc}."
        )
    return "\n".join(lines) or "No M6 domains or small ordered islands."


def _classifier_text(snapshot: DomainAnalysisWorkspaceSnapshot) -> str:
    publication = snapshot.published
    if publication is None:
        return "M6-Gated A/B/C was not requested."
    outcome = next(
        (
            value
            for value in publication.result.classifier_outcomes or ()
            if value.classifier_id == ABC_ORIENTATION_CLASSIFIER_ID
        ),
        None,
    )
    if outcome is None:
        return "M6-Gated A/B/C was not requested."
    if outcome.status == "failed":
        frame_index = outcome.failure_frame_index
        if frame_index is None:
            raise ValueError("A failed classifier must identify its failure frame.")
        return f"Failed on frame {frame_index + 1}: {outcome.error_message}"
    if outcome.status != "completed":
        return f"M6-Gated A/B/C status: {outcome.status.replace('_', ' ')}."
    summaries = tuple(
        summary
        for summary in outcome.domain_summaries
        if summary.physical_frame_id == snapshot.active_physical_frame_id
    )
    return (
        "\n".join(
            f"{summary.lattice_domain_id}: {summary.label}; "
            f"resolved={summary.resolved_fraction:.1%}; reason={summary.reason}."
            for summary in summaries
        )
        or "No full-domain A/B/C summaries for the current frame."
    )


def _order_hierarchy_text(frame: M6FrameGate | None) -> str:
    if frame is None:
        return "No published order hierarchy for the current frame."
    lines = [f"Frame {frame.frame_index + 1} ({frame.physical_frame_id})"]
    for component in frame.full_domains + frame.small_ordered_islands:
        label = component.component_type.replace("_", " ").title()
        lines.append(f"{label}: {component.lattice_domain_id}")
        lines.append(f"  Core: {', '.join(component.core_source_ids) or 'none'}")
        lines.append(f"  Halo: {', '.join(component.halo_source_ids) or 'none'}")
    lines.append(f"Outside M6: {', '.join(frame.outside_source_ids) or 'none'}")
    return "\n".join(lines)
