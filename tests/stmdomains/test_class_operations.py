"""Scoped class operations preserve spatial domains and commit all frames together."""

from dataclasses import replace
import numpy as np
import pytest

from test_manual_partition import partition_input
from stmdomains.core.class_catalogue import ClassCatalogue
from stmdomains.core.manual_classes import ManualClassList
from stmdomains.core.manual_class_lists import ManualClassLists
from stmdomains.core.manual_domains import ManualDomains
from stmdomains.core.class_operations import ClassTransaction


def variants():
    data, original = partition_input()
    catalogue = ClassCatalogue(data.series_id, 'selected_range', (0, 1), {'k': 2}, {}, {})
    result = []
    for index in (0, 1):
        frame_data = replace(data, frame=replace(data.frame, working_index=index, source_index=index))
        frame_result = replace(original, working_index=index, source_index=index, catalogue=catalogue)
        result.append(ManualDomains(frame_data, frame_result))
    labels = ManualClassList.from_result(result[0].original,
        ManualClassLists.source_key(data.series_id, result[0].original))
    return tuple(result), labels


def test_merge_two_frames_previews_without_mutation_and_preserves_domains():
    frames, labels = variants()
    before = [v.current for v in frames]
    transaction = ClassTransaction.prepare(frames, labels, 'merge', sources=('A', 'B'),
                                           name='C', color='#123456')
    assert all(v.current is old for v, old in zip(frames, before))
    assert len(labels.classes) == 2
    target = transaction.after.classes[-1].class_id
    assert transaction.after.classes[-1].name == 'C'
    for change in transaction.changes:
        assert change.after.class_counts == {'A': 0, 'B': 0, target: 12}
        assert change.after.domain_count == 2
        np.testing.assert_array_equal(change.after.domain_labels, change.before.domain_labels)
    transaction.apply()
    assert all(v.current.class_counts[target] == 12 for v in frames)


def test_split_uses_explicit_selections_per_frame_and_partitions_only_partial_domains():
    frames, labels = variants()
    transaction = ClassTransaction.prepare(frames, labels, 'split', sources=('A',), name='D', color='#abcdef',
        selections={0: tuple(f'm-{i:04}' for i in range(8)), 1: ('m-0000',)})
    target = transaction.after.classes[-1].class_id
    first, second = transaction.changes
    assert first.after.class_counts == {'A': 0, 'B': 4, target: 8}
    assert first.after.domain_count == 2
    np.testing.assert_array_equal(first.after.domain_labels, first.before.domain_labels)
    assert second.after.class_counts == {'A': 7, 'B': 4, target: 1}
    assert second.after.domain_count == 3
    assert second.after.assignments['m-0000'].domain_local_id == 12
    np.testing.assert_array_equal(second.after.domain_labels > 0, second.before.domain_labels > 0)


def test_stale_second_frame_refuses_application_before_changing_the_first():
    frames, labels = variants()
    before = tuple(v.current for v in frames)
    operation = ClassTransaction.prepare(frames, labels, 'merge', sources=('A', 'B'), target='A')
    frames[1].preview_classes(labels, 'update', target='A', name='Zmiana', color='#123456')
    with pytest.raises(ValueError, match='nieaktualny'):
        operation.apply()
    assert all(v.current is original for v, original in zip(frames, before))
    assert not any(v.changed for v in frames)


@pytest.mark.parametrize('operation,sources,selections', [
    ('merge', ('A',), {}), ('merge', ('A', 'missing'), {}),
    ('split', ('A',), {}), ('split', ('A', 'B'), {0: ('m-0000',), 1: ('m-0008',)}),
    ('split', ('A',), {0: tuple(f'm-{i:04}' for i in range(8)), 1: tuple(f'm-{i:04}' for i in range(8))}),
    ('split', ('A',), {0: ('m-0000',), 1: ('m-0008',)}),
])
def test_invalid_choices_leave_every_frame_and_class_list_unchanged(operation, sources, selections):
    frames, labels = variants()
    with pytest.raises(ValueError):
        ClassTransaction.prepare(frames, labels, operation, sources=sources,
                                 selections=selections, name='C', color='#123456')
    assert not any(v.changed for v in frames)
    assert len(labels.classes) == 2


def test_foreign_catalogue_is_refused_even_with_identical_class_names():
    frames, labels = variants()
    catalogue = replace(frames[1].original.catalogue, parameters={'different': True})
    foreign = ManualDomains(frames[1].data, replace(frames[1].original, catalogue=catalogue))
    with pytest.raises(ValueError, match='innego katalogu'):
        ClassTransaction.prepare((frames[0], foreign), labels, 'merge', sources=('A', 'B'), target='A')
    assert not frames[0].changed and not foreign.changed


def test_merge_and_split_without_model_keep_class_only_members_outside_domains():
    automatic, _ = variants()
    frames = tuple(ManualDomains(v.data) for v in automatic)
    labels = ManualClassList.from_result(None, ManualClassLists.source_key(frames[0].data.series_id, None))
    labels = labels.edit('create', name='A', color='#ff0000').edit('create', name='B', color='#00ff00')
    a, b = (c.class_id for c in labels.classes)
    for frame in frames:
        for target, indices in ((a, range(8)), (b, range(8, 12))):
            frame.apply(frame.preview_classes(labels, 'assign', target=target,
                        selection=tuple(f'm-{i:04}' for i in indices)))
    merge = ClassTransaction.prepare(frames, labels, 'merge', sources=(a, b), target=a)
    merge.apply()
    split = ClassTransaction.prepare(frames, labels, 'split', sources=(a,), name='C', color='#abcdef',
                                    selections={0: ('m-0000',), 1: ('m-0001',)})
    for change in split.changes:
        assert change.after.domain_count == 0 and change.after.assigned_count == 0
        assert change.after.catalogue is None and change.after.classes == ()
        assert change.after.class_counts[a] == 11
