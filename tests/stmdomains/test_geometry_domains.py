"""Domains from the public measurement/segmentation boundary, without class fitting."""

import numpy as np

from test_frame_analysis import analysis_input
from test_geometry_measurement import rectangular_points
from stmdomains.analysis.geometry import measure_geometry


def test_measured_regular_lattice_forms_connected_domain_without_classes():
    from stmdomains.analysis.geometry_domains import segment_geometry
    data = analysis_input(rectangular_points())
    measured = measure_geometry(data)
    result = segment_geometry(data, measured)
    assert result.domain_count == 1
    assert result.assigned_count >= 60
    assert not result.classes and result.catalogue is None
    assert all(not item.class_id for item in result.assignments.values())
    assert result.domain_labels is not None
    assert set(np.unique(result.domain_labels)) == {0, 1}
    assert result.metadata['phase_boundary_tested'] is False
    assert result.metadata['input_sha256'] == measured.metadata['input_sha256']


def measured_input(*, angles=None, periods=None, quality=.95, local_count=20, points=None):
    """Analytic measurements at the public segmentation input, not an estimator mock."""
    from stmdomains.analysis.provenance import input_fingerprint
    from stmdomains.core.geometry import FrameGeometry, MoleculeGeometry, PixelCalibration, RowAxis
    if points is None:
        points = np.array([(40+10*x, 40+10*y) for y in range(4) for x in range(12)], float)
    data = analysis_input(points)
    records = {}
    for i, detection in enumerate(data.annotations.detections):
        angle = angles[i] if angles is not None else 0.
        period = periods[i] if periods is not None else 10.
        axes = tuple(RowAxis((angle+offset)%180, (angle+offset+90)%180, period, quality) for offset in (0, 90))
        records[detection.detection_id] = MoleculeGeometry(detection.detection_id, detection.center_xy,
            'lattice_2d', axes=axes, local_count=local_count, effective_count=12.)
    geometry = FrameGeometry(data.series_id, 3, 19, PixelCalibration(), records, {},
                              {'input_sha256': input_fingerprint(data), 'spacing': 10.})
    return data, geometry


def test_gradual_rotation_cannot_chain_beyond_whole_region_tolerance():
    from stmdomains.analysis.geometry_domains import segment_geometry
    data, geometry = measured_input(angles=np.tile(np.arange(12)*3., 4))
    result = segment_geometry(data, geometry)
    assert result.domain_count > 1
    for domain in {m.domain_local_id for m in result.assignments.values()} - {0}:
        angles = [geometry.molecules[m.detection_id].axes[0].row_angle_deg
                  for m in result.assignments.values() if m.domain_local_id == domain]
        assert max(angles)-min(angles) <= 12.
    assert result.metadata['domain_construction']['region_rejected_merges'] > 0


def test_each_tolerance_changes_decisions_and_is_attached_to_result():
    from stmdomains.analysis.geometry_domains import segment_geometry
    from stmdomains.analysis.geometry_domain_settings import GeometryDomainSettings
    angle = np.tile([0.]*6+[10.]*6, 4)
    period = np.tile([10.]*6+[11.]*6, 4)
    data, geometry = measured_input(angles=angle, periods=period, quality=.8, local_count=11)
    loose = segment_geometry(data, geometry)
    assert loose.domain_count == 1 and loose.assigned_count == 48
    for name, value in [('angle_degrees', 5.), ('spacing_percent', 5.),
                         ('minimum_coherence', .9), ('minimum_local_count', 12)]:
        settings = GeometryDomainSettings(**{name: value})
        strict = segment_geometry(data, geometry, settings=settings)
        assert strict.parameters['geometry_tolerances'][name] == value
        if name in ('angle_degrees', 'spacing_percent'):
            assert strict.domain_count == 2 and strict.assigned_count == 48
        else:
            assert strict.assigned_count == 0
            expected = 'geometry_low_quality' if name == 'minimum_coherence' else 'geometry_low_support'
            assert {m.rejection_reason for m in strict.assignments.values()} == {expected}


def test_axial_symmetry_family_swap_and_repeatability():
    from dataclasses import replace
    from stmdomains.analysis.geometry_domains import segment_geometry
    data, geometry = measured_input(angles=np.tile([179.]*6+[1.]*6, 4))
    geometry = replace(geometry, molecules={key: replace(m, axes=m.axes[::-1]) if i%2 else m
                                           for i, (key, m) in enumerate(geometry.molecules.items())})
    first, second = segment_geometry(data, geometry), segment_geometry(data, geometry)
    assert first.domain_count == 1 and first.assigned_count == 48
    assert first.assignments == second.assignments
    assert np.array_equal(first.domain_labels, second.domain_labels)


def test_gap_splits_but_missing_center_is_not_automatically_a_boundary():
    from stmdomains.analysis.geometry_domains import segment_geometry
    original = np.array([(40+10*x, 40+10*y) for y in range(4) for x in range(12)], float)
    data, geometry = measured_input(points=np.delete(original, 17, axis=0))
    assert segment_geometry(data, geometry).domain_count == 1
    separated = original.copy()
    separated[separated[:, 0] >= 100, 0] += 30
    data, geometry = measured_input(points=separated)
    assert segment_geometry(data, geometry).domain_count == 2


def test_phase_jump_is_not_claimed_as_a_detected_boundary():
    from stmdomains.analysis.geometry_domains import segment_geometry
    points = np.array([(40+10*x, 40+10*y+(5 if x>=6 else 0)) for y in range(4) for x in range(12)], float)
    data, geometry = measured_input(points=points)
    result = segment_geometry(data, geometry)
    # Known failure: equal measured angle/period cannot establish phase agreement.
    assert result.domain_count == 1
    assert not result.metadata['phase_boundary_tested']


def test_cancellation_and_stale_measurement_refuse_without_mutation():
    import pytest
    from dataclasses import replace
    from stmdomains.analysis.geometry_domains import segment_geometry
    from stmdomains.core.analysis_result import AnalysisCancelled
    data, geometry = measured_input()
    with pytest.raises(AnalysisCancelled):
        segment_geometry(data, geometry, cancelled=lambda: True)
    with pytest.raises(ValueError, match='bieżącym'):
        segment_geometry(data, replace(geometry, source_index=4))


def test_image_barrier_is_kept_in_domains_and_raster():
    from dataclasses import replace
    from stmdomains.analysis.geometry_domains import segment_geometry
    from stmdomains.analysis.provenance import input_fingerprint
    data, geometry = measured_input()
    image = np.zeros_like(data.frame.image)
    image[55:] = 100.
    data = replace(data, frame=replace(data.frame, image=image))
    geometry = replace(geometry, metadata={**geometry.metadata, 'input_sha256': input_fingerprint(data)})
    result = segment_geometry(data, geometry)
    assert result.barrier_mask.any()
    assert result.domain_count == 2
    assert not np.any(result.domain_labels[result.barrier_mask])
    assert result.metadata['domain_construction']['barrier_cut_edges'] > 0


def test_spatial_constraints_change_links_size_and_mask():
    from stmdomains.analysis.geometry_domains import segment_geometry
    from stmdomains.analysis.domain_settings import DomainSettings
    data, geometry = measured_input()
    original = segment_geometry(data, geometry)
    assert segment_geometry(data, geometry, constraints=DomainSettings(edge_distance_factor=.9)).assigned_count == 0
    assert segment_geometry(data, geometry, constraints=DomainSettings(minimum_domain_size=49)).assigned_count == 0
    smaller = segment_geometry(data, geometry, constraints=DomainSettings(raster_radius_factor=.7))
    assert smaller.assigned_count == original.assigned_count
    assert np.count_nonzero(smaller.domain_labels) < np.count_nonzero(original.domain_labels)


def test_unavailable_annotations_are_a_result_not_an_identity_error():
    from stmdomains.analysis.geometry_domains import segment_geometry
    data = analysis_input(np.zeros((0, 2)), state='missing')
    result = segment_geometry(data, measure_geometry(data))
    assert result.status == 'no_annotations' and result.assigned_count == 0
