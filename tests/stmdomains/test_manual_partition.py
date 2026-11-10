"""Split/merge preserve memberships, classes, raster support and one-step history."""

import numpy as np
import pytest
from dataclasses import replace

from test_frame_analysis import analysis_input
from stmdomains.core.analysis_result import FrameAnalysis, MoleculeAssignment, ResultClass
from stmdomains.core.manual_domains import ManualDomains


def partition_input():
    points = [(x, y) for y in (10, 20) for x in (10, 20, 30, 40)]
    points += [(x, y) for y in (10, 20) for x in (80, 90)]
    data = analysis_input(points)
    assignments = {d.detection_id: MoleculeAssignment(d.detection_id,
        domain_local_id=7 if i < 8 else 11, class_id='A' if i < 8 else 'B', status='domain')
        for i, d in enumerate(data.annotations.detections)}
    labels = np.zeros((256, 256), np.int32)
    labels[5:26, 5:46] = 7
    labels[5:26, 75:96] = 11
    result = FrameAnalysis(data.series_id, 3, 19, 'complete', assignments=assignments,
        classes=(ResultClass('A', '#ff0000'), ResultClass('B', '#00ff00')), domain_labels=labels)
    return data, result


def test_split_preserves_remaining_id_source_class_and_unrelated_domain():
    data, original = partition_input()
    edits = ManualDomains(data, original)
    chosen = ('m-0000', 'm-0001', 'm-0004', 'm-0005')
    preview = edits.preview('split', chosen)
    assert edits.current is original and not edits.changed
    assert preview.domain_count == 3 and preview.assigned_count == 12
    assert {preview.assignments[k].domain_local_id for k in chosen} == {12}
    assert preview.assignments['m-0002'].domain_local_id == 7
    assert {preview.assignments[k].class_id for k in chosen} == {'A'}
    assert preview.assignments['m-0008'] == original.assignments['m-0008']
    assert np.array_equal(preview.domain_labels == 11, original.domain_labels == 11)
    assert np.array_equal(preview.domain_labels > 0, original.domain_labels > 0)
    assert preview.domain_labels[10, 10] == 12 and preview.domain_labels[10, 40] == 7
    edits.apply(preview)
    edits.undo()
    assert edits.current is original
    edits.redo()
    assert edits.current is preview


def test_merge_after_split_restores_membership_and_exact_source_area_in_one_step():
    data, original = partition_input()
    edits = ManualDomains(data, original)
    split = edits.preview('split', ('m-0000', 'm-0001', 'm-0004', 'm-0005'))
    edits.apply(split)
    merged = edits.preview('merge', ('m-0000', 'm-0002'), target=7)
    assert edits.current is split
    assert merged.domain_count == 2 and merged.assigned_count == 12
    assert {key: a.domain_local_id for key, a in merged.assignments.items()} == {
        key: a.domain_local_id for key, a in original.assignments.items()}
    assert np.array_equal(merged.domain_labels, original.domain_labels)
    edit = merged.metadata['manual_edit']
    assert [r['domain_id'] for r in edit['source_domains']] == [7, 12]
    assert len(edit['target_domains'][0]['member_ids']) == 8
    edits.apply(merged)
    edits.undo()
    assert edits.current is split
    edits.redo()
    assert edits.current is merged


def test_merge_different_classes_is_unknown_and_split_does_not_recover_a_source_class():
    data, original = partition_input()
    assignments = dict(original.assignments)
    for key in ('m-0002', 'm-0003', 'm-0006', 'm-0007'):
        assignments[key] = replace(assignments[key], domain_local_id=9, class_id='B')
    labels = original.domain_labels.copy()
    labels[5:26, 26:46] = 9
    original = replace(original, assignments=assignments, domain_labels=labels)
    edits = ManualDomains(data, original)
    merged = edits.preview('merge', ('m-0000', 'm-0002'), target=9)
    assert merged.assigned_count == 12 and merged.domain_count == 2
    assert {a.class_id for a in merged.assignments.values() if a.domain_local_id == 9} == {''}
    assert original.assignments['m-0000'].class_id == 'A'
    assert original.assignments['m-0002'].class_id == 'B'
    edits.apply(merged)
    split = edits.preview('split', ('m-0000', 'm-0001', 'm-0004', 'm-0005'))
    assert split.assignments['m-0000'].class_id == ''
    assert split.assignments['m-0002'].class_id == ''


@pytest.mark.parametrize('selection, explanation', [
    (tuple(f'm-{i:04d}' for i in range(8)), 'całą domenę'),
    (('m-0000', 'm-0008'), 'jednej domeny'),
    ((), 'aktywne molekuły'),
])
def test_invalid_split_keeps_original(selection, explanation):
    data, original = partition_input()
    edits = ManualDomains(data, original)
    with pytest.raises(ValueError, match=explanation):
        edits.preview('split', selection)
    assert edits.current is original and not edits.changed


def test_merge_refuses_gap_single_domain_and_foreign_target_without_changing_area():
    data, original = partition_input()
    edits = ManualDomains(data, original)
    for selection, target, explanation in [
        (('m-0000', 'm-0008'), 7, 'przerwa'),
        (('m-0000', 'm-0001'), 7, 'dwóch domen'),
        (('m-0000', 'm-0008'), 99, 'Docelowe ID'),
    ]:
        with pytest.raises(ValueError, match=explanation):
            edits.preview('merge', selection, target)
        assert edits.current is original and not edits.changed


def test_point_only_split_inherits_no_area_and_cannot_be_merged_as_supported():
    data, original = partition_input()
    original = replace(original, domain_labels=None)
    edits = ManualDomains(data, original)
    split = edits.preview('split', ('m-0000',))
    assert split.domain_labels is None and split.assigned_count == 12
    assert set(split.metadata['manual_edit']['unsupported_domains']) == {7, 11, 12}
    edits.apply(split)
    with pytest.raises(ValueError, match='nie ma obszaru'):
        edits.preview('merge', ('m-0000', 'm-0001'))


def test_single_member_inherits_only_its_part_of_existing_support():
    data, original = partition_input()
    edits = ManualDomains(data, original)
    split = edits.preview('split', ('m-0000',))
    assert split.domain_labels[10, 10] == 12
    assert split.domain_labels[10, 20] == 7
    assert np.array_equal(split.domain_labels > 0, original.domain_labels > 0)
    edits.apply(split)
    merged = edits.preview('merge', ('m-0000', 'm-0001'), target=7)
    assert np.array_equal(merged.domain_labels, original.domain_labels)


def test_empty_gap_pixels_are_not_filled_even_when_union_has_another_connection():
    data, original = partition_input()
    edits = ManualDomains(data, original)
    split = edits.preview('split', ('m-0000', 'm-0001', 'm-0004', 'm-0005'))
    labels = split.domain_labels.copy()
    labels[14:18, 22:29] = 0  # A hole, with support connecting above and below.
    with_hole = replace(split, domain_labels=labels)
    edits = ManualDomains(data, with_hole)
    merged = edits.preview('merge', ('m-0000', 'm-0002'))
    assert not merged.domain_labels[14:18, 22:29].any()
    assert np.array_equal(labels > 0, merged.domain_labels > 0)
