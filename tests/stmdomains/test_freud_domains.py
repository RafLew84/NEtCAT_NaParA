"""Public segmentation boundary: actual EnvironmentCluster and spatial domains."""

from test_frame_analysis import analysis_input
from test_geometry_measurement import rectangular_points
from stmdomains.analysis.geometry import measure_geometry


def test_regular_lattice_is_clustered_without_k_or_a_trained_catalogue():
    from stmdomains.analysis.freud_domains import segment_freud
    data = analysis_input(rectangular_points())
    result = segment_freud(data, measure_geometry(data))
    assert result.domain_count == 1 and result.assigned_count >= 60
    assert result.catalogue is None
    assert len({m.class_id for m in result.assignments.values() if m.domain_local_id}) == 1
    assert result.metadata['environment_clustering']['engine'] == 'freud.EnvironmentCluster'
    assert result.metadata['environment_clustering']['periodic'] is False
    assert result.metadata['environment_clustering']['registration_transform'] == 'none'
    assert result.domain_labels is not None


def test_missing_centers_and_finite_radius_have_explicit_refusals():
    import numpy as np
    from stmdomains.analysis.freud_domains import segment_freud
    from stmdomains.analysis.freud_settings import FreudSettings
    points = rectangular_points(angle=0)
    data = analysis_input(np.delete(points, len(points)//2, axis=0))
    result = segment_freud(data, measure_geometry(data))
    assert any(m.rejection_reason == 'freud_ambiguous_shell' for m in result.assignments.values())
    for item in result.assignments.values():
        env = item.metadata['freud_environment']
        assert all(distance <= 2.000001 for distance in env['distances_nn'])
        if item.provisional_class_id:
            assert not env['reason'] and env['observed_count'] == 4
    short = segment_freud(data, measure_geometry(data), settings=FreudSettings(radius_factor=.8))
    assert short.assigned_count == 0 and not short.classes
    assert {m.rejection_reason for m in short.assignments.values()} == {'freud_incomplete'}


def test_class_view_shows_environments_even_when_domains_are_refused():
    from stmdomains.analysis.freud_domains import segment_freud
    from stmdomains.analysis.domain_settings import DomainSettings
    from stmdomains.ui.result_style import assignment_color, describe_result, UNASSIGNED_COLOR
    from stmdomains.ui.assignment_details import assignment_details
    data = analysis_input(rectangular_points())
    result = segment_freud(data, measure_geometry(data), constraints=DomainSettings(minimum_domain_size=200))
    item = next(m for m in result.assignments.values() if m.provisional_class_id)
    assert result.assigned_count == 0
    assert assignment_color(result, item.detection_id, 'classes') != UNASSIGNED_COLOR
    assert assignment_color(result, item.detection_id, 'domains') == UNASSIGNED_COLOR
    assert 'otoczeń' in describe_result(result, 'classes').summary
    details = assignment_details(result, item.detection_id)
    assert 'Sąsiedzi' in details and 'najbliższy wzorzec' not in details


def test_same_environment_class_can_have_two_disconnected_domains():
    import numpy as np
    from test_geometry_domains import measured_input
    from stmdomains.analysis.freud_domains import segment_freud
    points = np.array([(40+10*x+(30 if x >= 6 else 0), 40+10*y) for y in range(4) for x in range(12)], float)
    data, geometry = measured_input(points=points)
    result = segment_freud(data, geometry)
    assert result.domain_count == 2 and result.assigned_count == 16
    assert len({m.class_id for m in result.assignments.values() if m.domain_local_id}) == 1


def test_order_does_not_change_class_partition_and_stale_measurement_is_rejected():
    from dataclasses import replace
    import numpy as np
    import pytest
    from stmdomains.analysis.freud_domains import segment_freud
    data = analysis_input(rectangular_points())
    original = segment_freud(data, measure_geometry(data))
    shuffled = replace(data, annotations=replace(data.annotations, detections=data.annotations.detections[::-1]))
    second = segment_freud(shuffled, measure_geometry(shuffled))
    assert original.assignments == second.assignments
    assert np.array_equal(original.domain_labels, second.domain_labels)
    with pytest.raises(ValueError, match='bieżącym'):
        segment_freud(data, replace(measure_geometry(data), source_index=5))


def test_field_edges_are_refused_without_wrapping_and_xy_calibration_preserves_classes():
    import numpy as np
    from stmdomains.analysis.freud_domains import segment_freud
    from stmdomains.core.geometry import PixelCalibration
    points = rectangular_points(angle=0)
    physical = analysis_input(points)
    stretched = analysis_input((points-128)/(.6, 1.2)+128)
    a = segment_freud(physical, measure_geometry(physical))
    b = segment_freud(stretched, measure_geometry(stretched, calibration=PixelCalibration(.6, 1.2, 'nm', 'test')))
    assert {k: m.provisional_class_id for k, m in a.assignments.items()} == {
        k: m.provisional_class_id for k, m in b.assignments.items()}
    # Translate two dense groups close to opposite edges. They must not wrap.
    left = np.array([(2+3*x, 80+4*y) for y in range(5) for x in range(3)], float)
    edge_data = analysis_input(np.vstack((left, left+(245, 0))))
    result = segment_freud(edge_data, measure_geometry(edge_data))
    assert any(m.rejection_reason == 'freud_edge' for m in result.assignments.values())
    for item in result.assignments.values():
        assert all(distance <= 2.000001 for distance in item.metadata.get('freud_environment', {}).get('distances_nn', ()))
        assert not item.domain_local_id
