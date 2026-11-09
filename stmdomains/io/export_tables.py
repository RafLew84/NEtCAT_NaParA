"""Whole-frame counts and explicitly approximate raster areas, never series totals."""

from collections import Counter
from typing import Any

import numpy as np

from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.core.annotations import FrameAnnotations
from stmdomains.core.export_snapshot import ExportSource
from stmdomains.core.result_names import domain_name
from stmdomains.io.export_provenance import (
    PROVENANCE_FIELDS, MEMBER_FIELDS, COUNT_FIELDS, provenance, member_changes, class_fields,
)

IDENTITY = ('analysis_id', 'catalogue_id', 'frame_key', 'working_index', 'working_number',
            'source_index', 'source_number', 'analysis_status', *PROVENANCE_FIELDS)
FRAME_FIELDS = (*IDENTITY, 'time_s', 'time_status', 'status_reason', 'annotation_status', 'input_count', 'active_count',
                'excluded_duplicates', 'excluded_outside', 'assigned_count', 'unassigned_count', 'domain_count',
                'counts_status', 'assigned_percent', 'percentage_status', 'field_area_px2',
                'approx_area_px2', 'approx_area_status', 'physical_area_nm2', 'physical_area_status',
                'coverage_area_px2', 'coverage_status', *COUNT_FIELDS)
MOLECULE_FIELDS = (*IDENTITY, 'detection_id', 'origin', 'source_view', 'center_x_raw_px', 'center_y_raw_px',
                   'confidence', 'included_in_analysis_denominator', 'domain_local_id', 'class_id',
                   'provisional_class_id', 'assignment_status', 'rejection_reason', *MEMBER_FIELDS)
GROUP_FIELDS = (*IDENTITY, 'class_id', 'domain_local_id', 'assigned_count', 'active_denominator',
                'assigned_percent', 'percentage_status', 'approx_area_px2', 'approx_area_status',
                'approx_area_percent_field', 'field_area_px2', 'touches_field_edge',
                'physical_area_nm2', 'physical_area_status', 'class_name', 'class_color', 'class_origin',
                'domain_name', 'class_only_count')


def identity(snapshot: ExportSource, index: int, result: FrameAnalysis | None) -> dict[str, Any]:
    analysis, series = snapshot.analysis, snapshot.series
    status = (result.status if result else analysis.statuses[index]['status'] if analysis and index in analysis.statuses
              else 'not_in_analysis' if analysis else 'unanalysed')
    return {'analysis_id': analysis.identifier if analysis else '',
            'catalogue_id': result.catalogue.identifier if result and result.catalogue else '',
            'frame_key': f'{series.source_sha256}:{series.source_frame_indices[index]}',
            'working_index': index, 'working_number': index + 1,
            'source_index': series.source_frame_indices[index], 'source_number': series.source_frame_indices[index] + 1,
            'analysis_status': status, **provenance(snapshot, index, result)}


def percent(numerator: int | None, denominator: int | None) -> float | None:
    return 100 * numerator / denominator if numerator is not None and denominator else None


def table_rows(snapshot: ExportSource, index: int, result: FrameAnalysis | None,
               annotations: FrameAnnotations) -> dict[str, list[dict[str, Any]]]:
    base = identity(snapshot, index, result)
    complete = result is not None and result.status == 'complete'
    count_state = 'complete' if complete and annotations.detection_state == 'available' else 'partial' if complete else 'unavailable'
    active = result.active_count if result else None
    assigned = result.assigned_count if complete and result else None
    field_area = int(np.prod(snapshot.series.frame_shape))
    labels = result.domain_labels if complete and result else None
    area_state = 'approximate' if labels is not None else 'unavailable'
    area = int(np.count_nonzero(labels)) if labels is not None else None
    unsupported = result.metadata.get('manual_edit', {}).get('unsupported_domains', ()) if result else ()
    if unsupported:
        area_state = 'partial' if area else 'unavailable'
        area = area or None
    percentage_state = 'unavailable' if assigned is None else 'undefined' if not active else count_state
    reason = (result.message if result else str(snapshot.analysis.statuses.get(index, {}).get('message', ''))
              if snapshot.analysis else 'Nie wykonano analizy.')
    time_s = snapshot.series.frame(index).time_s
    frame = {**base, 'time_s': time_s, 'time_status': 'available' if time_s is not None else 'unavailable',
             'status_reason': reason, 'annotation_status': annotations.detection_state,
             'input_count': len(annotations.detections) if annotations.detection_state not in ('missing', 'invalid') else None, 'active_count': active,
             'excluded_duplicates': result.suppressed_count if result else None,
             'excluded_outside': result.outside_count if result else None,
             'assigned_count': assigned, 'unassigned_count': result.unassigned_count if complete and result else None,
             'domain_count': result.domain_count if complete and result else None, 'counts_status': count_state,
             'assigned_percent': percent(assigned, active), 'percentage_status': percentage_state,
             'field_area_px2': field_area, 'approx_area_px2': area,
             'approx_area_status': area_state, 'physical_area_nm2': None, 'physical_area_status': 'unavailable',
             'coverage_area_px2': None, 'coverage_status': 'unavailable'}
    molecules = []
    changes = member_changes(snapshot, index, result)
    for detection in annotations.detections:
        member = result.assignments.get(detection.detection_id) if result else None
        molecules.append({**base, 'detection_id': detection.detection_id, 'origin': detection.metadata.get('origin', ''),
            'source_view': detection.source_view, 'center_x_raw_px': detection.center_xy[0], 'center_y_raw_px': detection.center_xy[1],
            'confidence': detection.metadata.get('confidence'),
            'included_in_analysis_denominator': int(member.status not in ('outside_field', 'suppressed_duplicate')) if member else None,
            'domain_local_id': member.domain_local_id if member else None, 'class_id': member.class_id if member else '',
            'provisional_class_id': member.provisional_class_id if member else '',
            'assignment_status': member.status if member else 'unavailable',
            'rejection_reason': member.rejection_reason if member else 'Brak wyniku wybranego przebiegu.',
            **changes.get(detection.detection_id, {})})
    members = [r for r in molecules if r['included_in_analysis_denominator'] == 1]
    frame.update({key: None for key in COUNT_FIELDS})
    if complete:
        frame.update(class_assigned_count=sum(bool(r['class_id']) for r in members),
                     class_only_count=sum(bool(r['class_id']) and not r['domain_local_id'] for r in members))
        for origin in ('manual', 'automatic'):
            frame[origin + '_assigned_count'] = sum(bool(r['domain_local_id']) and r['assignment_origin'] == origin for r in members)
            frame[origin + '_class_assigned_count'] = sum(bool(r['class_id']) and r['assignment_origin'] == origin for r in members)
    domains, classes = [], []
    if complete and result is not None:
        domain_classes = {item.domain_local_id: item.class_id for item in result.assignments.values() if item.domain_local_id}
        domain_counts = Counter(item.domain_local_id for item in result.assignments.values() if item.domain_local_id)
        for domain, class_id in sorted(domain_classes.items()):
            mask = labels == domain if labels is not None and domain not in unsupported else None
            area = int(np.count_nonzero(mask)) if mask is not None else None
            edge = int(any(np.any(a) for a in (mask[0], mask[-1], mask[:, 0], mask[:, -1]))) if mask is not None else None
            domains.append({**base, 'class_id': class_id, 'domain_local_id': domain, **class_fields(result, class_id),
                'domain_name': domain_name(result, domain), 'class_only_count': 0,
                'assigned_count': domain_counts[domain], 'active_denominator': active,
                'assigned_percent': percent(domain_counts[domain], active), 'percentage_status': percentage_state,
                'approx_area_px2': area, 'approx_area_status': 'approximate' if area is not None else 'unavailable', 'approx_area_percent_field': percent(area, field_area),
                'field_area_px2': field_area, 'touches_field_edge': edge, 'physical_area_nm2': None,
                'physical_area_status': 'unavailable'})
        for item in result.class_list.classes if result.class_list else result.classes:
            selected = [row for row in domains if row['class_id'] == item.class_id]
            count = result.class_counts[item.class_id]
            area = sum(row['approx_area_px2'] for row in selected) if labels is not None and all(row['approx_area_px2'] is not None for row in selected) else None
            classes.append({**base, 'class_id': item.class_id, 'domain_local_id': None, **class_fields(result, item.class_id),
                'domain_name': '', 'class_only_count': sum(r['class_id'] == item.class_id and not r['domain_local_id'] for r in members),
                'assigned_count': count, 'active_denominator': active, 'assigned_percent': percent(count, active),
                'percentage_status': percentage_state, 'approx_area_px2': area, 'approx_area_status': 'approximate' if area is not None else 'unavailable',
                'approx_area_percent_field': percent(area, field_area), 'field_area_px2': field_area,
                'touches_field_edge': int(any(row['touches_field_edge'] for row in selected)) if labels is not None else None,
                'physical_area_nm2': None, 'physical_area_status': 'unavailable'})
    return {'frames': [frame], 'molecules': molecules, 'domains': domains, 'classes': classes}


TABLE_FIELDS = {'frames': FRAME_FIELDS, 'molecules': MOLECULE_FIELDS, 'domains': GROUP_FIELDS, 'classes': GROUP_FIELDS}
