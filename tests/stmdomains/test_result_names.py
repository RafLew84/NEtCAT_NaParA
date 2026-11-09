"""Class letters and per-class region names preserve the underlying identities."""

from dataclasses import replace

from stmdomains.core.analysis_result import FrameAnalysis, MoleculeAssignment, ResultClass
from stmdomains.core.manual_classes import ManualClassList
from stmdomains.core.result_names import class_names, domain_names
from stmdomains.ui.result_style import describe_result


def sample():
    return FrameAnalysis('example', 0, 0, 'complete', classes=tuple(
        ResultClass(str(i), '#ff8800') for i in range(1, 29)), assignments={
            'first': MoleculeAssignment('first', 7, '4', '4', 'domain'),
            'second': MoleculeAssignment('second', 19, '4', '4', 'domain'),
            'other': MoleculeAssignment('other', 11, '2', '2', 'domain'),
            'unknown': MoleculeAssignment('unknown', 25, '', '', 'domain'),
        })


def test_class_d_has_d1_d2_and_absent_classes_keep_their_letters():
    result = sample()
    assert domain_names(result, 'classes') == {7: 'D', 11: 'B', 19: 'D', 25: '?'}
    assert domain_names(result) == {7: 'D1', 11: 'B1', 19: 'D2', 25: '?1'}
    assert [class_names(result)[str(i)] for i in (1, 26, 27, 28)] == ['A', 'Z', 'AA', 'AB']
    # Reordering records and navigating to a frame missing class B cannot relabel D.
    another_frame = replace(result, working_index=1, source_index=1,
                            assignments={'second': result.assignments['second']})
    assert domain_names(another_frame, 'classes') == {19: 'D'}
    assert domain_names(another_frame) == {19: 'D1'}
    reordered = replace(result, assignments=dict(reversed(list(result.assignments.items()))))
    assert domain_names(reordered) == domain_names(result)


def test_manual_names_drive_regions_legend_and_list_without_changing_ids():
    result = sample()
    original_assignments = result.assignments
    labels = ManualClassList.from_result(result, 'example')
    assert [c.name for c in labels.classes[:4]] == ['A', 'B', 'C', 'D']
    assert domain_names(replace(result, class_list=labels)) == domain_names(result)
    renamed = labels.edit('update', '4', name='Wyspa', color='#00ff00')
    corrected = replace(result, class_list=renamed)
    assert domain_names(corrected, 'classes')[7] == 'Wyspa'
    assert domain_names(corrected)[19] == 'Wyspa · 2'
    classes = describe_result(corrected, 'classes')
    assert (classes.legend[3].label, classes.legend[3].count) == ('Klasa Wyspa', 2)
    assert [e.label for e in describe_result(corrected, 'domains').legend][:3] == [
        'Domena Wyspa · 1', 'Domena B1', 'Domena Wyspa · 2']
    assert corrected.assignments == original_assignments
    assert [c.class_id for c in renamed.classes] == [c.class_id for c in labels.classes]
    assert domain_names(replace(corrected, class_list=labels))[7] == 'D1'


def test_geometry_without_classes_does_not_claim_a_class_d():
    result = sample()
    result = replace(result, classes=(), assignments={
        key: replace(a, class_id='', provisional_class_id='') for key, a in result.assignments.items()})
    assert domain_names(result) == {7: '?1', 11: '?2', 19: '?3', 25: '?4'}
    assert set(domain_names(result, 'classes').values()) == {'?'}
