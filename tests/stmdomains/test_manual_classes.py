"""Manual class edits through the same preview/apply/history boundary as domains."""

from dataclasses import replace
import numpy as np
import pytest

from test_manual_partition import partition_input
from stmdomains.core.manual_domains import ManualDomains
from stmdomains.core.manual_classes import ManualClass, ManualClassList
from stmdomains.core.result_names import class_letter


def test_empty_class_has_stable_identity_metadata_and_one_step_history():
    data, original = partition_input()
    edits = ManualDomains(data, original)
    labels = ManualClassList.from_result(original, 'source-one')
    created = edits.preview_classes(labels, 'create', name='Moja klasa A', color='#123456')
    label = created.class_list.classes[-1]
    assert label.origin == 'manual' and label.name == 'Moja klasa A'
    assert label.color == '#123456' and label.class_id not in ('A', 'B')
    assert not any(a.class_id == label.class_id for a in created.assignments.values())
    assert created.class_list.identifier == labels.identifier
    assert created.class_list.version != labels.version
    assert edits.current is original
    edits.apply(created)
    renamed = edits.preview_classes(created.class_list, 'update', target=label.class_id,
                                    name='Nowa nazwa', color='#abcdef')
    assert renamed.class_list.classes[-1].class_id == label.class_id
    assert created.class_list.classes[-1].name == 'Moja klasa A'
    edits.apply(renamed)
    edits.undo()
    assert edits.current is created
    edits.redo()
    assert edits.current is renamed
    assert original.classes[0].color == '#ff0000'


def test_new_class_and_partial_assignment_split_atomically_without_touching_others():
    data, original = partition_input()
    edits = ManualDomains(data, original)
    labels = ManualClassList.from_result(original, 'source-one')
    preview = edits.preview_classes(labels, 'create_assign', name='Fragment', color='#123456',
                                    selection=('m-0000', 'm-0001'))
    target = preview.class_list.classes[-1].class_id
    assert preview.assignments['m-0000'].class_id == target
    assert preview.assignments['m-0001'].domain_local_id == 12
    assert preview.assignments['m-0002'] == original.assignments['m-0002']
    assert preview.assignments['m-0008'] == original.assignments['m-0008']
    assert preview.domain_count == 3 and preview.assigned_count == 12
    assert np.array_equal(preview.domain_labels > 0, original.domain_labels > 0)
    assert preview.metadata['manual_edit']['splits'][0]['source_domain'] == 7
    edits.apply(preview)
    edits.undo()
    assert edits.current is original
    edits.redo()
    assert edits.current is preview


def test_whole_domains_keep_separate_ids_and_class_only_points_never_form_a_domain():
    data, original = partition_input()
    assignments = dict(original.assignments)
    assignments['m-0008'] = replace(assignments['m-0008'], domain_local_id=0, class_id='', status='unassigned')
    original = replace(original, assignments=assignments)
    edits = ManualDomains(data, original)
    labels = ManualClassList.from_result(original, 'source-one')
    created = edits.preview_classes(labels, 'create', name='Wspólna', color='#123456')
    edits.apply(created)
    labels = created.class_list
    target = labels.classes[-1].class_id
    whole = edits.preview_classes(labels, 'assign', target=target,
                                  selection=('m-0000', 'm-0009'), whole_domains=True)
    assert whole.domain_count == 2 and whole.assigned_count == 11
    assert whole.assignments['m-0007'].class_id == whole.assignments['m-0011'].class_id == target
    assert whole.assignments['m-0007'].domain_local_id == 7
    assert whole.assignments['m-0011'].domain_local_id == 11
    edits.apply(whole)
    single = edits.preview_classes(labels, 'assign', target=target, selection=('m-0008',))
    assert single.assignments['m-0008'].domain_local_id == 0
    assert single.assignments['m-0008'].class_id == target
    assert single.domain_count == 2 and single.assigned_count == 11
    edits.apply(single)
    cleared = edits.preview_classes(labels, 'assign', target='', selection=('m-0008',))
    assert cleared.assignments['m-0008'].class_id == ''
    assert len(cleared.assignments) == 12


def test_only_empty_manual_classes_can_be_deleted_and_invalid_inputs_leave_history_intact():
    data, original = partition_input()
    edits = ManualDomains(data, original)
    labels = ManualClassList.from_result(original, 'source-one')
    for operation, kwargs in [('delete', {'target': 'A'}),
                              ('create', {'name': 'A' * 81, 'color': '#123456'}),
                              ('create', {'name': 'Test', 'color': 'invalid'}),
                              ('assign', {'target': 'foreign', 'selection': ('m-0000',)})]:
        with pytest.raises(ValueError):
            edits.preview_classes(labels, operation, **kwargs)
        assert edits.current is original
    created = edits.preview_classes(labels, 'create', name='Pusta', color='#123456')
    edits.apply(created)
    target = created.class_list.classes[-1].class_id
    with pytest.raises(ValueError, match='członk'):
        edits.preview_classes(created.class_list, 'delete', target=target, occupied={target})
    deleted = edits.preview_classes(created.class_list, 'delete', target=target)
    assert len(deleted.class_list.classes) == 2
    edits.apply(deleted)
    edits.undo()
    assert edits.current is created


def test_domain_operations_preserve_manual_classes_and_latest_list_metadata():
    data, original = partition_input()
    edits = ManualDomains(data, original)
    labels = ManualClassList.from_result(original, 'source-one')
    classified = edits.preview_classes(labels, 'create_assign', name='Ręczna', color='#123456',
        selection=('m-0000',), whole_domains=True)
    edits.apply(classified)
    target = classified.class_list.classes[-1].class_id
    latest = classified.class_list.edit('update', target, name='Nowa nazwa', color='#abcdef')
    split = edits.preview('split', ('m-0000',), class_list=latest)
    assert split.class_list is latest and split.assignments['m-0000'].class_id == target
    edits.apply(split)
    merged = edits.preview('merge', ('m-0000', 'm-0001'), 7, class_list=latest)
    edits.apply(merged)
    removed = edits.preview('remove', ('m-0000',), class_list=latest)
    assert removed.assignments['m-0000'].class_id == target
    assert removed.assignments['m-0000'].domain_local_id == 0
    assert removed.assignments['m-0001'].class_id == target


@pytest.mark.parametrize('existing, expected', [(0, 'A'), (5, 'F'), (26, 'AA')])
def test_unnamed_class_reserves_names_of_empty_classes(existing, expected):
    labels = ManualClassList('source', '', tuple(
        ManualClass(str(i), class_letter(i), '#123456', 'manual') for i in range(existing)))
    revised = labels.edit('create', color='#abcdef')
    assert revised.classes[-1].name == expected
    assert len(labels.classes) == existing
    with pytest.raises(ValueError, match='Nazwa'):
        revised.edit('update', revised.classes[-1].class_id, name=' ', color='#abcdef')
