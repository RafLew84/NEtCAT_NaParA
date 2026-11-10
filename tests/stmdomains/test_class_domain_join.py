"""Optional joining reuses existing support and only touches the assigned class."""

import numpy as np
import pytest
from test_manual_partition import partition_input
from stmdomains.core.manual_domains import ManualDomains
from stmdomains.core.manual_classes import ManualClassList


def test_consecutive_assignments_can_extend_one_domain_without_joining_a_remote_one():
    data, original = partition_input()
    edits = ManualDomains(data, original)
    labels = ManualClassList.from_result(original, 'control')
    first = edits.preview_classes(labels, 'assign', target='B', selection=('m-0000',), join_touching=True)
    edits.apply(first)
    second = edits.preview_classes(labels, 'assign', target='B', selection=('m-0001',), join_touching=True)
    assert second.assignments['m-0000'].domain_local_id == second.assignments['m-0001'].domain_local_id == 12
    assert second.assignments['m-0008'].domain_local_id == 11  # remote B remains separate
    assert second.domain_count == 3 and second.assigned_count == original.assigned_count
    np.testing.assert_array_equal(second.domain_labels > 0, original.domain_labels > 0)
    np.testing.assert_array_equal(second.domain_labels == 11, original.domain_labels == 11)
    edits.apply(second)
    edits.undo()
    assert edits.current is first
    edits.redo()
    assert edits.current is second


def test_existing_same_class_fragments_can_be_repaired_explicitly():
    data, original = partition_input()
    edits = ManualDomains(data, original)
    labels = ManualClassList.from_result(original, 'control')
    for key in ('m-0000', 'm-0001'):
        edits.apply(edits.preview_classes(labels, 'assign', target='B', selection=(key,)))
    split = edits.current
    assert split.domain_count == 4
    repaired = edits.preview_classes(labels, 'assign', target='B', selection=('m-0000',), join_touching=True)
    assert repaired.domain_count == 3
    assert repaired.assignments['m-0000'].domain_local_id == repaired.assignments['m-0001'].domain_local_id
    assert repaired.assignments['m-0008'] == original.assignments['m-0008']
    edits.apply(repaired)
    edits.undo()
    assert edits.current is split
    with pytest.raises(ValueError):
        edits.preview_classes(labels, 'assign', target='B', selection=('m-0008',), join_touching=True)


def test_joining_keeps_class_only_points_without_domain_or_area():
    from dataclasses import replace
    data, original = partition_input()
    assignments = dict(original.assignments)
    assignments['m-0008'] = replace(assignments['m-0008'], domain_local_id=0, class_id='', status='unassigned')
    original = replace(original, assignments=assignments)
    edits = ManualDomains(data, original)
    labels = ManualClassList.from_result(original, 'control')
    result = edits.preview_classes(labels, 'assign', target='A', selection=('m-0008',), join_touching=True)
    assert result.assignments['m-0008'].class_id == 'A'
    assert result.assignments['m-0008'].domain_local_id == 0
    np.testing.assert_array_equal(result.domain_labels, original.domain_labels)


def test_joining_does_not_repair_unselected_components_of_the_same_class():
    data, original = partition_input()
    edits = ManualDomains(data, original)
    labels = ManualClassList.from_result(original, 'control')
    for key in ('m-0000', 'm-0001'):
        edits.apply(edits.preview_classes(labels, 'assign', target='B', selection=(key,)))
    fragmented = edits.current
    # Assign the entire remote domain to A. B fragments were not selected.
    result = edits.preview_classes(labels, 'assign', target='A', selection=('m-0008',),
                                    whole_domains=True, join_touching=True)
    assert result.domain_count == fragmented.domain_count
    assert result.assignments['m-0000'] == fragmented.assignments['m-0000']
    assert result.assignments['m-0001'] == fragmented.assignments['m-0001']
