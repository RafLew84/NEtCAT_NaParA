"""Manual membership operations preserve their source and are reversible."""

import numpy as np
import pytest
from dataclasses import replace

from test_frame_analysis import analysis_input
from stmdomains.core.analysis_result import FrameAnalysis, MoleculeAssignment, ResultClass
from stmdomains.core.manual_domains import ManualDomains


def test_preview_then_create_without_analysis_and_undo_the_entire_result():
    data = analysis_input([(10, 10), (20, 10), (10, 20), (20, 20)])
    edits = ManualDomains(data)
    preview = edits.preview('new', ('m-0000', 'm-0001', 'm-0002'))
    assert not edits.changed and edits.current.assigned_count == 0
    assert preview.assigned_count == 3 and preview.domain_count == 1
    edits.apply(preview)
    assert edits.changed and edits.current is preview
    assert edits.current.assignments['m-0003'].domain_local_id == 0
    assert edits.current.domain_labels[20, 20] == 0
    assert edits.original is None and edits.current.classes == ()
    edits.undo()
    assert not edits.changed and edits.current.assigned_count == 0
    edits.redo()
    assert edits.current is preview
    assert np.any(edits.current.domain_labels == 1)


def original_result(data):
    assignments = {d.detection_id: MoleculeAssignment(d.detection_id,
        domain_local_id=1 if i < 3 else 2 if i == 3 else 0,
        class_id='A' if i < 3 else 'B' if i == 3 else '',
        status='domain' if i < 4 else 'unassigned', rejection_reason='low_order' if i == 4 else '')
        for i, d in enumerate(data.annotations.detections)}
    return FrameAnalysis(data.series_id, 3, 19, 'complete', assignments=assignments,
                         classes=(ResultClass('A', '#ff0000'), ResultClass('B', '#00ff00')))


def test_transfer_is_explicit_mixed_class_unknown_and_original_refusal_survives():
    data = analysis_input([(10, 10), (20, 10), (10, 20), (20, 20), (30, 20)])
    original = original_result(data)
    edits = ManualDomains(data, original)
    with pytest.raises(ValueError, match='Przenieś'):
        edits.preview('add', ('m-0003',), 1)
    preview = edits.preview('move', ('m-0003',), 1)
    edits.apply(preview)
    assert edits.current.domain_count == 1
    assert {m.class_id for m in edits.current.assignments.values()} == {''}
    assert edits.current.assignments['m-0003'].metadata['manual_source']['class_id'] == 'B'
    assert original.assignments['m-0003'].domain_local_id == 2
    edits.undo()
    assert edits.current is original and edits.current.domain_count == 2
    edits.apply(edits.preview('add', ('m-0004',), 1))
    assert edits.current.assignments['m-0004'].rejection_reason == 'low_order'
    assert not edits.can_redo


def test_remove_last_member_single_point_has_no_area_and_stale_preview_is_refused():
    edits = ManualDomains(analysis_input([(10, 10)]))
    preview = edits.preview('new', ('m-0000',))
    edits.apply(preview)
    assert edits.current.assigned_count == 1
    assert not edits.current.domain_labels.any()
    assert edits.current.metadata['manual_edit']['unsupported_domains'] == (1,)
    removed = edits.preview('remove', ('m-0000',))
    edits.apply(removed)
    assert edits.current.domain_count == 0
    edits.undo()
    assert edits.current.assigned_count == 1
    with pytest.raises(ValueError, match='nieaktualny'):
        edits.apply(removed)


def test_empty_unknown_duplicate_and_outside_selections_cannot_create_domains():
    data = analysis_input([(10, 10), (20, 10), (10, 20), (20, 20), (10.1, 10), (-1, 0)])
    edits = ManualDomains(data)
    assert edits.current.suppressed_count == edits.current.outside_count == 1
    for selection in ((), ('unknown',), ('m-0004',), ('m-0005',)):
        with pytest.raises(ValueError):
            edits.preview('new', selection)
    assert not edits.changed
    empty = ManualDomains(analysis_input())
    with pytest.raises(ValueError):
        empty.preview('new', ())


def test_source_must_match_annotations_and_field():
    data = analysis_input([(10, 10), (20, 10), (10, 20)])
    original = original_result(data)
    with pytest.raises(ValueError):
        ManualDomains(data, replace(original, working_index=4))
    with pytest.raises(ValueError):
        ManualDomains(data, replace(original, assignments={}))


def test_neighbour_domains_keep_separate_masks_without_changing_membership():
    data = analysis_input([(10, 10), (10, 20), (20, 10), (30, 10), (30, 20), (40, 10)])
    edits = ManualDomains(data)
    edits.apply(edits.preview('new', ('m-0000', 'm-0001', 'm-0002')))
    edits.apply(edits.preview('new', ('m-0003', 'm-0004', 'm-0005')))
    assert edits.current.assigned_count == 6 and edits.current.domain_count == 2
    assert edits.current.domain_labels[10, 20] == 1
    assert edits.current.domain_labels[10, 30] == 2
    assert edits.current.domain_labels[0, 255] == 0
    assert edits.current.domain_labels.shape == (256, 256)
