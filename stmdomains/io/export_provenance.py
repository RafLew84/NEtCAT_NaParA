"""Human decisions and their source, separate from fitted model predictions."""

import json
from dataclasses import asdict
from typing import Any

from stmdomains.core.analysis_result import FrameAnalysis, analysis_identifier
from stmdomains.core.export_snapshot import ExportSource, ExportSnapshot, original_result
from stmdomains.core.immutable import plain_metadata
from stmdomains.core.result_names import class_name, domain_name

PROVENANCE_FIELDS = ('result_variant', 'frame_state', 'result_id', 'base_analysis_id', 'automatic_available',
                     'correction_variant_id', 'correction_revision', 'class_list_id', 'class_list_revision')
MEMBER_FIELDS = ('base_class_id', 'base_class_name', 'base_class_color', 'base_domain_local_id', 'base_domain_name',
                 'base_assignment_status', 'class_name', 'class_color', 'class_origin', 'domain_name',
                 'assignment_origin', 'change_type', 'change_operations')
COUNT_FIELDS = ('class_assigned_count', 'class_only_count', 'manual_assigned_count', 'automatic_assigned_count',
                'manual_class_assigned_count', 'automatic_class_assigned_count')


def provenance(snapshot: ExportSource, index: int, result: FrameAnalysis | None) -> dict[str, Any]:
    original = original_result(snapshot, index)
    correction = snapshot.corrections.get(index) if isinstance(snapshot, ExportSnapshot) else None
    variant = snapshot.variant if isinstance(snapshot, ExportSnapshot) else 'automatic'
    changed = (correction is not None and result is not original) or bool(result and result.class_list and result.class_list.generation)
    labels = result.class_list if result else None
    revision = result.metadata.get('manual_edit', {}).get('revision', 0) if result else None
    base_id = analysis_identifier(original)
    result_id = (f'{correction.variant_id if correction else base_id}:{revision}:{labels.version if labels else ""}'
                 if changed else base_id)
    return {'result_variant': variant,
        'frame_state': 'manual_only' if changed and original is None else 'corrected' if changed else 'automatic' if result else 'unanalysed',
        'result_id': result_id, 'base_analysis_id': base_id, 'automatic_available': int(original is not None),
        'correction_variant_id': correction.variant_id if correction and variant == 'after_corrections' else '',
        'correction_revision': revision if variant == 'after_corrections' and (correction or changed) else None,
        'class_list_id': labels.identifier if labels else '', 'class_list_revision': labels.version if labels else ''}


def class_fields(result: FrameAnalysis | None, class_id: str) -> dict[str, str]:
    labels = result.class_list.classes if result and result.class_list else result.classes if result else ()
    label = next((c for c in labels if c.class_id == class_id), None)
    return {'class_name': class_name(result, class_id) if result and class_id else '',
            'class_color': label.color if label else '',
            'class_origin': getattr(label, 'origin', 'automatic') if label else ''}


def operations(snapshot: ExportSource, index: int) -> list[dict[str, Any]]:
    correction = snapshot.corrections.get(index) if isinstance(snapshot, ExportSnapshot) else None
    return [plain_metadata(frame.metadata['manual_edit']) for frame in correction.history[1:]
            if 'manual_edit' in frame.metadata] if correction else []


def member_changes(snapshot: ExportSource, index: int, result: FrameAnalysis | None) -> dict[str, dict[str, Any]]:
    original = original_result(snapshot, index)
    correction = snapshot.corrections.get(index) if isinstance(snapshot, ExportSnapshot) else None
    history = correction.history if correction else ()
    affected: dict[str, list[dict]] = {}
    for before, after in zip(history, history[1:]):
        edit = after.metadata.get('manual_edit', {})
        for key, member in after.assignments.items():
            previous = before.assignments[key]
            if (previous.class_id, previous.domain_local_id) != (member.class_id, member.domain_local_id):
                affected.setdefault(key, []).append({k: plain_metadata(edit[k]) for k in (
                    'operation', 'revision', 'class_operation', 'transaction_id', 'transaction_frames', 'class_sources',
                    'class_target') if k in edit})
    output = {}
    for key, member in (result.assignments.items() if result else ()):
        base = original.assignments.get(key) if original else None
        labels = class_fields(original, base.class_id) if base else {}
        changes = []
        if member.class_id != (base.class_id if base else ''):
            changes.append('class')
        if member.domain_local_id != (base.domain_local_id if base else 0):
            changes.append('domain')
        final_labels = class_fields(result, member.class_id)
        if base and member.class_id == base.class_id and final_labels != labels:
            changes.append('class_metadata')
        output[key] = {'base_class_id': base.class_id if base else '',
            'base_class_name': labels.get('class_name', ''), 'base_class_color': labels.get('class_color', ''),
            'base_domain_local_id': base.domain_local_id if base else None,
            'base_domain_name': domain_name(original, base.domain_local_id) if original and base and base.domain_local_id else '',
            'base_assignment_status': base.status if base else 'unavailable', **final_labels,
            'domain_name': domain_name(result, member.domain_local_id) if result and member.domain_local_id else '',
            'assignment_origin': 'manual' if key in affected else 'automatic' if base else 'unassigned',
            'change_type': '+'.join(changes) or 'unchanged',
            'change_operations': json.dumps(affected.get(key, []), ensure_ascii=False, separators=(',', ':'))}
    return output


def correction_metadata(snapshot: ExportSource, index: int, result: FrameAnalysis | None) -> dict[str, Any]:
    original = original_result(snapshot, index)
    return {'applied_operations': operations(snapshot, index),
        'manual_classes': [asdict(c) for c in result.class_list.classes] if result and result.class_list else [],
        'base_parameters': plain_metadata(original.parameters) if original else None,
        'base_execution_metadata': plain_metadata(original.metadata) if original else None}
