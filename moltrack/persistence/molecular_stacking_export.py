"""CSV tables and manifest data for molecular stacking analyses."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularOrientationStore,
    MolecularStackingSessionState,
    build_molecular_stacking_range_comparison,
    molecular_orientation_prototype_analysis_fingerprint,
    restore_molecular_stacking_display_result,
)
from moltrack.core import MolTrackImageSeries


MOLECULAR_STACKING_TABLE_FILES = (
    "stacking_molecules.csv",
    "stacking_domains.csv",
    "stacking_subdomains.csv",
)

STACKING_MOLECULE_FIELDS = (
    "working_frame_index",
    "working_frame_number",
    "source_frame_index",
    "source_frame_number",
    "source_view",
    "source_id",
    "measurement_id",
    "orientation_status",
    "orientation_angle_deg",
    "orientation_periodicity_deg",
    "orientation_confidence",
    "orientation_method",
    "orientation_manual_corrected",
    "orientation_reviewer",
    "orientation_note",
    "orientation_original_status",
    "orientation_original_angle_deg",
    "orientation_original_confidence",
    "orientation_original_method",
    "orientation_source_file_name",
    "orientation_source_file_sha256",
    "orientation_source_session_file_name",
    "orientation_source_session_sha256",
    "orientation_source_kind",
    "orientation_reference",
    "orientation_patch_bbox_xyxy",
    "lattice_domain_id",
    "row_assignment_status",
    "row_assignment_reason",
    "axis_candidate_index",
    "axis_angle_deg",
    "row_index",
    "row_parity",
    "along_coordinate_nm",
    "normal_coordinate_nm",
    "row_residual_nm",
    "ab_state",
    "prototype_distance_deg",
    "alternative_distance_deg",
    "stacking_pattern",
    "stacking_confidence",
    "stacking_coverage_fraction",
    "stacking_qc",
    "subdomain_id",
    "subdomain_pattern",
    "subdomain_mode",
    "subdomain_phase",
    "subdomain_score",
    "subdomain_confidence",
    "subdomain_qc",
    "row_assignment_fingerprint",
    "prototype_analysis_fingerprint",
    "stacking_analysis_fingerprint",
)

STACKING_DOMAIN_FIELDS = (
    "working_frame_index",
    "working_frame_number",
    "source_frame_index",
    "source_frame_number",
    "source_view",
    "lattice_domain_id",
    "pattern",
    "axis_candidate_index",
    "axis_angle_deg",
    "mode",
    "phase",
    "prototype_a_angle_deg",
    "prototype_b_angle_deg",
    "periodicity_deg",
    "score",
    "confidence",
    "domain_molecule_count",
    "usable_molecule_count",
    "ordered_molecule_count",
    "coverage_fraction",
    "ordered_fraction",
    "subdomain_count",
    "qc",
    "row_assignment_fingerprint",
    "prototype_analysis_fingerprint",
    "stacking_settings_fingerprint",
    "stacking_analysis_fingerprint",
)

STACKING_SUBDOMAIN_FIELDS = (
    "working_frame_index",
    "working_frame_number",
    "source_frame_index",
    "source_frame_number",
    "source_view",
    "subdomain_id",
    "parent_lattice_domain_id",
    "pattern",
    "axis_candidate_index",
    "axis_angle_deg",
    "mode",
    "phase",
    "molecule_count",
    "parent_molecule_count",
    "coverage_fraction",
    "score",
    "confidence",
    "qc",
    "source_ids",
    "prototype_analysis_fingerprint",
    "stacking_settings_fingerprint",
    "stacking_analysis_fingerprint",
)


@dataclass(frozen=True)
class MolecularStackingExportData:
    available: bool
    reason: str | None
    molecule_rows: tuple[dict[str, object], ...]
    domain_rows: tuple[dict[str, object], ...]
    subdomain_rows: tuple[dict[str, object], ...]
    manifest: dict[str, object]


def build_molecular_stacking_export_data(
    series: MolTrackImageSeries,
    state: MolecularStackingSessionState | None,
    *,
    frame_indices: tuple[int, ...],
    comparison_ranges: tuple[MolecularFrameRange, MolecularFrameRange] | None = None,
    expected_source_view: str | None = None,
) -> MolecularStackingExportData:
    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be MolTrackImageSeries.")
    frames = tuple(sorted(set(int(index) for index in frame_indices)))
    if any(index < 0 or index >= series.frame_count for index in frames):
        raise ValueError("Stacking export frame_indices exceed the series.")
    store = getattr(series, "molecular_orientations", None)
    if (
        not isinstance(state, MolecularStackingSessionState)
        or state.status != "computed"
    ):
        return _unavailable("stacking_analysis_not_computed")
    if not isinstance(store, MolecularOrientationStore):
        return _unavailable("molecular_orientations_not_available")
    display = restore_molecular_stacking_display_result(
        state,
        store.measurements,
    )
    if display is None:
        return _unavailable("stacking_dependencies_changed")
    analysis = display.stacking_analysis
    included = set(frames)
    row_fingerprint_by_frame = dict(analysis.row_assignment_fingerprints)
    prototype_fingerprint = molecular_orientation_prototype_analysis_fingerprint(
        display.prototype_analysis
    )
    analysis_fingerprint = state.stacking_analysis_fingerprint
    assert analysis_fingerprint is not None
    source_view = analysis.source_view or display.prototype_analysis.source_view
    if (
        expected_source_view is not None
        and source_view != str(expected_source_view)
    ):
        return _unavailable("stacking_source_view_mismatch")

    domain_rows = tuple(
        _domain_row(
            series,
            order,
            source_view=source_view,
            row_fingerprint=row_fingerprint_by_frame[order.frame_index],
            prototype_fingerprint=prototype_fingerprint,
            analysis_fingerprint=analysis_fingerprint,
            settings_fingerprint=analysis.settings_fingerprint,
        )
        for order in analysis.orders
        if order.frame_index in included
    )
    subdomain_rows = tuple(
        _subdomain_row(
            series,
            subdomain,
            source_view=source_view,
            prototype_fingerprint=prototype_fingerprint,
            analysis_fingerprint=analysis_fingerprint,
            settings_fingerprint=analysis.settings_fingerprint,
        )
        for subdomain in analysis.subdomains
        if subdomain.frame_index in included
    )
    molecule_rows = _molecule_rows(
        series,
        display,
        included,
        source_view=source_view,
        row_fingerprint_by_frame=row_fingerprint_by_frame,
        prototype_fingerprint=prototype_fingerprint,
        analysis_fingerprint=analysis_fingerprint,
    )
    comparison = (
        None
        if comparison_ranges is None
        else build_molecular_stacking_range_comparison(
            analysis,
            comparison_ranges[0],
            comparison_ranges[1],
        )
    )
    qc_counts = Counter(
        reason
        for order in analysis.orders
        if order.frame_index in included
        for reason in order.qc_reasons
    )
    manifest = {
        "available": True,
        "reason": None,
        "uses_tracking": False,
        "source_view": source_view,
        "input_frame_indices": list(analysis.input_frame_indices),
        "exported_frame_indices": list(frames),
        "prototype_status": display.prototype_analysis.status,
        "prototype_reason": display.prototype_analysis.reason,
        "prototype_settings": display.prototype_analysis.settings.to_dict(),
        "stacking_settings": analysis.settings.to_dict(),
        "row_assignment_settings": [
            {
                "frame_index": frame.frame_index,
                "settings": frame.row_assignment.settings.to_dict(),
                "settings_fingerprint": (
                    frame.row_assignment.settings_fingerprint
                ),
            }
            for frame in display.frames
        ],
        "fingerprints": {
            "orientation_measurements": (
                display.prototype_analysis.measurement_fingerprint
            ),
            "row_assignments": [
                {"frame_index": index, "fingerprint": fingerprint}
                for index, fingerprint in analysis.row_assignment_fingerprints
            ],
            "prototype_settings": (
                display.prototype_analysis.settings_fingerprint
            ),
            "prototype_analysis": prototype_fingerprint,
            "stacking_settings": analysis.settings_fingerprint,
            "stacking_analysis": analysis_fingerprint,
        },
        "record_counts": {
            "molecules": len(molecule_rows),
            "domains": len(domain_rows),
            "subdomains": len(subdomain_rows),
        },
        "domain_pattern_counts": dict(
            sorted(
                Counter(row["pattern"] for row in domain_rows).items()
            )
        ),
        "domain_qc_reason_counts": dict(sorted(qc_counts.items())),
        "range_comparison": _comparison_manifest(comparison),
        "tables": list(MOLECULAR_STACKING_TABLE_FILES),
    }
    return MolecularStackingExportData(
        available=True,
        reason=None,
        molecule_rows=molecule_rows,
        domain_rows=domain_rows,
        subdomain_rows=subdomain_rows,
        manifest=manifest,
    )


def write_molecular_stacking_tables(
    destination: str | Path,
    export_data: MolecularStackingExportData,
) -> dict[str, Path]:
    if not isinstance(export_data, MolecularStackingExportData):
        raise TypeError("export_data must be MolecularStackingExportData.")
    if not export_data.available:
        return {}
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    tables = (
        ("stacking_molecules_csv", MOLECULAR_STACKING_TABLE_FILES[0],
         STACKING_MOLECULE_FIELDS, export_data.molecule_rows),
        ("stacking_domains_csv", MOLECULAR_STACKING_TABLE_FILES[1],
         STACKING_DOMAIN_FIELDS, export_data.domain_rows),
        ("stacking_subdomains_csv", MOLECULAR_STACKING_TABLE_FILES[2],
         STACKING_SUBDOMAIN_FIELDS, export_data.subdomain_rows),
    )
    paths = {}
    for key, file_name, fields, rows in tables:
        path = root / file_name
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        paths[key] = path
    return paths


def _molecule_rows(
    series,
    display,
    included,
    *,
    source_view,
    row_fingerprint_by_frame,
    prototype_fingerprint,
    analysis_fingerprint,
):
    analysis = display.stacking_analysis
    order_by_key = {
        (order.frame_index, order.lattice_domain_id): order
        for order in analysis.orders
    }
    subdomain_by_source = {
        (subdomain.frame_index, source_id): subdomain
        for subdomain in analysis.subdomains
        for source_id in subdomain.source_ids
    }
    evidence_by_key = {
        (
            evidence.frame_index,
            evidence.lattice_domain_id,
            evidence.candidate_index,
        ): evidence
        for evidence in display.prototype_analysis.axis_evidence
    }
    measurement_by_key = {
        (frame.frame_index, measurement.provenance.source_id): measurement
        for frame in display.frames
        for measurement in frame.measurements
    }
    rows = []
    for frame in display.frames:
        if frame.frame_index not in included:
            continue
        exported_source_ids = set()
        for domain_rows in frame.row_assignment.domain_assignments:
            order = order_by_key.get(
                (frame.frame_index, domain_rows.lattice_domain_id)
            )
            candidate = (
                None
                if (
                    order is None
                    or order.axis_candidate_index is None
                )
                else domain_rows.candidates[order.axis_candidate_index]
            )
            if (
                candidate is None
                and domain_rows.selected_candidate_index is not None
            ):
                candidate = domain_rows.candidates[
                    domain_rows.selected_candidate_index
                ]
            row_member_by_source = (
                {}
                if candidate is None
                else {
                    member.source_id: member
                    for member in candidate.member_assignments
                }
            )
            evidence = (
                None
                if order is None or order.axis_candidate_index is None
                else evidence_by_key.get(
                    (
                        frame.frame_index,
                        domain_rows.lattice_domain_id,
                        order.axis_candidate_index,
                    )
                )
            )
            state_by_source = (
                {}
                if evidence is None
                else {
                    assignment.source_id: assignment
                    for assignment in evidence.assignments
                }
            )
            for source_id in domain_rows.source_ids:
                exported_source_ids.add(source_id)
                measurement = measurement_by_key.get(
                    (frame.frame_index, source_id)
                )
                row_member = row_member_by_source.get(source_id)
                state_assignment = state_by_source.get(source_id)
                subdomain = subdomain_by_source.get(
                    (frame.frame_index, source_id)
                )
                rows.append(
                    {
                        **_frame_identity(
                            series,
                            frame.frame_index,
                            source_view,
                        ),
                        "source_id": source_id,
                        **_orientation_export_fields(measurement),
                        "lattice_domain_id": domain_rows.lattice_domain_id,
                        "row_assignment_status": domain_rows.status,
                        "row_assignment_reason": domain_rows.reason,
                        "axis_candidate_index": (
                            None if candidate is None else candidate.candidate_index
                        ),
                        "axis_angle_deg": (
                            None if candidate is None else candidate.axis_angle_deg
                        ),
                        "row_index": (
                            None if row_member is None else row_member.row_index
                        ),
                        "row_parity": (
                            None if row_member is None else row_member.row_parity
                        ),
                        "along_coordinate_nm": (
                            None
                            if row_member is None
                            else row_member.along_coordinate_nm
                        ),
                        "normal_coordinate_nm": (
                            None
                            if row_member is None
                            else row_member.normal_coordinate_nm
                        ),
                        "row_residual_nm": (
                            None
                            if row_member is None
                            else row_member.row_residual_nm
                        ),
                        "ab_state": (
                            None
                            if state_assignment is None
                            else state_assignment.state_label
                        ),
                        "prototype_distance_deg": (
                            None
                            if state_assignment is None
                            else state_assignment.prototype_distance_deg
                        ),
                        "alternative_distance_deg": (
                            None
                            if state_assignment is None
                            else state_assignment.alternative_distance_deg
                        ),
                        "stacking_pattern": (
                            None if order is None else order.pattern
                        ),
                        "stacking_confidence": (
                            None if order is None else order.confidence
                        ),
                        "stacking_coverage_fraction": (
                            None if order is None else order.coverage_fraction
                        ),
                        "stacking_qc": (
                            None
                            if order is None
                            else ";".join(order.qc_reasons)
                        ),
                        "subdomain_id": (
                            None if subdomain is None else subdomain.subdomain_id
                        ),
                        "subdomain_pattern": (
                            None if subdomain is None else subdomain.pattern
                        ),
                        "subdomain_mode": (
                            None if subdomain is None else subdomain.mode
                        ),
                        "subdomain_phase": (
                            None if subdomain is None else subdomain.phase
                        ),
                        "subdomain_score": (
                            None if subdomain is None else subdomain.score
                        ),
                        "subdomain_confidence": (
                            None if subdomain is None else subdomain.confidence
                        ),
                        "subdomain_qc": (
                            None
                            if subdomain is None
                            else ";".join(subdomain.qc_reasons)
                        ),
                        "row_assignment_fingerprint": (
                            row_fingerprint_by_frame[frame.frame_index]
                        ),
                        "prototype_analysis_fingerprint": prototype_fingerprint,
                        "stacking_analysis_fingerprint": analysis_fingerprint,
                    }
                )
        measurement_by_source_id = {
            measurement.provenance.source_id: measurement
            for measurement in frame.measurements
        }
        all_source_ids = set(frame.row_assignment.source_ids)
        all_source_ids.update(measurement_by_source_id)
        for source_id in sorted(all_source_ids - exported_source_ids):
            rows.append(
                {
                    **_frame_identity(
                        series,
                        frame.frame_index,
                        source_view,
                    ),
                    "source_id": source_id,
                    **_orientation_export_fields(
                        measurement_by_source_id.get(source_id)
                    ),
                    "lattice_domain_id": None,
                    "row_assignment_status": "unavailable",
                    "row_assignment_reason": "not_in_lattice_domain",
                    "axis_candidate_index": None,
                    "axis_angle_deg": None,
                    "row_index": None,
                    "row_parity": None,
                    "along_coordinate_nm": None,
                    "normal_coordinate_nm": None,
                    "row_residual_nm": None,
                    "ab_state": None,
                    "prototype_distance_deg": None,
                    "alternative_distance_deg": None,
                    "stacking_pattern": None,
                    "stacking_confidence": None,
                    "stacking_coverage_fraction": None,
                    "stacking_qc": "not_in_lattice_domain",
                    "subdomain_id": None,
                    "subdomain_pattern": None,
                    "subdomain_mode": None,
                    "subdomain_phase": None,
                    "subdomain_score": None,
                    "subdomain_confidence": None,
                    "subdomain_qc": "not_in_lattice_domain",
                    "row_assignment_fingerprint": (
                        row_fingerprint_by_frame[frame.frame_index]
                    ),
                    "prototype_analysis_fingerprint": prototype_fingerprint,
                    "stacking_analysis_fingerprint": analysis_fingerprint,
                }
            )
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row["working_frame_index"],
                str(row["lattice_domain_id"] or ""),
                row["source_id"],
            ),
        )
    )


def _orientation_export_fields(measurement):
    if measurement is None:
        return {
            "measurement_id": None,
            "orientation_status": None,
            "orientation_angle_deg": None,
            "orientation_periodicity_deg": None,
            "orientation_confidence": None,
            "orientation_method": None,
            "orientation_manual_corrected": None,
            "orientation_reviewer": None,
            "orientation_note": None,
            "orientation_original_status": None,
            "orientation_original_angle_deg": None,
            "orientation_original_confidence": None,
            "orientation_original_method": None,
            "orientation_source_file_name": None,
            "orientation_source_file_sha256": None,
            "orientation_source_session_file_name": None,
            "orientation_source_session_sha256": None,
            "orientation_source_kind": None,
            "orientation_reference": None,
            "orientation_patch_bbox_xyxy": None,
        }
    correction = measurement.manual_correction
    original = None if correction is None else correction.original_result
    provenance = measurement.provenance
    return {
        "measurement_id": measurement.measurement_id,
        "orientation_status": measurement.status,
        "orientation_angle_deg": measurement.angle_deg,
        "orientation_periodicity_deg": measurement.periodicity_deg,
        "orientation_confidence": measurement.confidence,
        "orientation_method": measurement.method,
        "orientation_manual_corrected": measurement.is_manually_corrected,
        "orientation_reviewer": (
            None if correction is None else correction.reviewer
        ),
        "orientation_note": None if correction is None else correction.note,
        "orientation_original_status": (
            None if original is None else original.status
        ),
        "orientation_original_angle_deg": (
            None if original is None else original.angle_deg
        ),
        "orientation_original_confidence": (
            None if original is None else original.confidence
        ),
        "orientation_original_method": (
            None if original is None else original.method
        ),
        "orientation_source_file_name": provenance.source_file_name,
        "orientation_source_file_sha256": provenance.source_file_sha256,
        "orientation_source_session_file_name": (
            provenance.source_session_file_name
        ),
        "orientation_source_session_sha256": provenance.source_session_sha256,
        "orientation_source_kind": provenance.source_kind,
        "orientation_reference": provenance.orientation_reference,
        "orientation_patch_bbox_xyxy": ";".join(
            str(value) for value in provenance.patch_bbox_xyxy
        ),
    }


def _domain_row(
    series,
    order,
    *,
    source_view,
    row_fingerprint,
    prototype_fingerprint,
    analysis_fingerprint,
    settings_fingerprint,
):
    return {
        **_frame_identity(series, order.frame_index, source_view),
        "lattice_domain_id": order.lattice_domain_id,
        "pattern": order.pattern,
        "axis_candidate_index": order.axis_candidate_index,
        "axis_angle_deg": order.axis_angle_deg,
        "mode": order.mode,
        "phase": order.phase,
        "prototype_a_angle_deg": order.prototype_a_angle_deg,
        "prototype_b_angle_deg": order.prototype_b_angle_deg,
        "periodicity_deg": order.periodicity_deg,
        "score": order.score,
        "confidence": order.confidence,
        "domain_molecule_count": order.domain_molecule_count,
        "usable_molecule_count": order.usable_molecule_count,
        "ordered_molecule_count": order.ordered_molecule_count,
        "coverage_fraction": order.coverage_fraction,
        "ordered_fraction": order.ordered_fraction,
        "subdomain_count": len(order.subdomain_ids),
        "qc": ";".join(order.qc_reasons),
        "row_assignment_fingerprint": row_fingerprint,
        "prototype_analysis_fingerprint": prototype_fingerprint,
        "stacking_settings_fingerprint": settings_fingerprint,
        "stacking_analysis_fingerprint": analysis_fingerprint,
    }


def _subdomain_row(
    series,
    subdomain,
    *,
    source_view,
    prototype_fingerprint,
    analysis_fingerprint,
    settings_fingerprint,
):
    return {
        **_frame_identity(series, subdomain.frame_index, source_view),
        "subdomain_id": subdomain.subdomain_id,
        "parent_lattice_domain_id": subdomain.parent_lattice_domain_id,
        "pattern": subdomain.pattern,
        "axis_candidate_index": subdomain.axis_candidate_index,
        "axis_angle_deg": subdomain.axis_angle_deg,
        "mode": subdomain.mode,
        "phase": subdomain.phase,
        "molecule_count": subdomain.molecule_count,
        "parent_molecule_count": subdomain.parent_molecule_count,
        "coverage_fraction": subdomain.coverage_fraction,
        "score": subdomain.score,
        "confidence": subdomain.confidence,
        "qc": ";".join(subdomain.qc_reasons),
        "source_ids": ";".join(subdomain.source_ids),
        "prototype_analysis_fingerprint": prototype_fingerprint,
        "stacking_settings_fingerprint": settings_fingerprint,
        "stacking_analysis_fingerprint": analysis_fingerprint,
    }


def _frame_identity(series, frame_index, source_view):
    source_index = series.source_frame_indices[frame_index]
    return {
        "working_frame_index": frame_index,
        "working_frame_number": frame_index + 1,
        "source_frame_index": source_index,
        "source_frame_number": source_index + 1,
        "source_view": source_view,
    }


def _comparison_manifest(comparison):
    if comparison is None:
        return None
    return {
        "uses_tracking": False,
        "denominator": comparison.denominator,
        "direction": comparison.direction,
        "ranges": [
            {
                "name": summary.frame_range.name,
                "start_frame": summary.frame_range.start_frame,
                "end_frame": summary.frame_range.end_frame,
                "analyzed_frame_count": summary.analyzed_frame_count,
                "classified_domain_count": summary.classified_domain_count,
                "excluded_domain_count": summary.excluded_domain_count,
                "ambiguous_domain_count": summary.ambiguous_domain_count,
                "unavailable_domain_count": summary.unavailable_domain_count,
            }
            for summary in (comparison.first, comparison.second)
        ],
        "rows": [
            {
                "pattern": row.pattern,
                "first_count": row.first_count,
                "first_share_percent": row.first_share_percent,
                "second_count": row.second_count,
                "second_share_percent": row.second_share_percent,
                "count_delta": row.count_delta,
                "share_delta_percentage_points": (
                    row.share_delta_percentage_points
                ),
            }
            for row in comparison.rows
        ],
    }


def _unavailable(reason: str) -> MolecularStackingExportData:
    return MolecularStackingExportData(
        available=False,
        reason=reason,
        molecule_rows=(),
        domain_rows=(),
        subdomain_rows=(),
        manifest={
            "available": False,
            "reason": reason,
            "uses_tracking": False,
            "tables": [],
            "range_comparison": None,
        },
    )


__all__ = [
    "MOLECULAR_STACKING_TABLE_FILES",
    "MolecularStackingExportData",
    "STACKING_DOMAIN_FIELDS",
    "STACKING_MOLECULE_FIELDS",
    "STACKING_SUBDOMAIN_FIELDS",
    "build_molecular_stacking_export_data",
    "write_molecular_stacking_tables",
]
