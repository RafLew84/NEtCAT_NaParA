"""Public segmentation contract for the experimental level-set method."""

import numpy as np

from test_geometry_domains import measured_input


def test_regular_measurements_form_one_domain_without_inventing_classes():
    from stmdomains.analysis.levelset_domains import segment_levelset
    data, measured = measured_input()
    result = segment_levelset(data, measured)
    assert result.domain_count == 1 and result.assigned_count == 48
    assert result.catalogue is None and not result.classes
    assert not result.metadata['phase_boundary_tested']
    assert result.parameters['domain_method'] == 'gibou_fedkiw_features_v1'
    assert result.metadata['levelset']['stopping_reason'] == 'single_region'
    assert set(np.unique(result.domain_labels)) == {0, 1}
    for detection in data.annotations.detections:
        x, y = np.rint(detection.center_xy).astype(int)
        assert result.domain_labels[y, x] == result.assignments[detection.detection_id].domain_local_id


def test_two_orientations_are_separate_and_parameters_change_only_new_result():
    from stmdomains.analysis.levelset_domains import segment_levelset
    from stmdomains.analysis.levelset_settings import LevelSetSettings
    angles = np.tile([0.]*6+[30.]*6, 4)
    data, measured = measured_input(angles=angles)
    first = segment_levelset(data, measured)
    limited = segment_levelset(data, measured, settings=LevelSetSettings(1., 1))
    assert first.domain_count == limited.domain_count == 2
    assert first.assigned_count == limited.assigned_count == 48
    assert first.metadata['levelset']['stopping_reason'] == 'stable_partition'
    assert limited.metadata['levelset']['stopping_reason'] == 'iteration_limit'
    assert limited.metadata['levelset']['iterations'] == 1
    assert first.parameters['levelset_settings']['regularization'] == .25
    assert limited.parameters['levelset_settings']['regularization'] == 1.
    for result in (first, limited):
        for d in data.annotations.detections:
            x, y = np.rint(d.center_xy).astype(int)
            assert result.assignments[d.detection_id].domain_local_id == result.domain_labels[y, x]


def test_axial_periodicity_and_joint_family_swap_preserve_domains():
    from dataclasses import replace
    from stmdomains.analysis.levelset_domains import segment_levelset
    data, measured = measured_input(angles=np.tile([179.]*6+[1.]*6, 4))
    swapped = replace(measured, molecules={k: replace(m, axes=m.axes[::-1]) if i%2 else m
        for i, (k, m) in enumerate(measured.molecules.items())})
    result = segment_levelset(data, measured)
    other = segment_levelset(data, swapped)
    assert result.domain_count == other.domain_count == 1
    assert result.assigned_count == other.assigned_count == 48
    assert np.array_equal(result.domain_labels, other.domain_labels)


def test_gap_is_not_filled_but_missing_centre_does_not_split_regular_lattice():
    from stmdomains.analysis.levelset_domains import segment_levelset
    points = np.array([(40+10*x, 40+10*y) for y in range(4) for x in range(12)], float)
    data, measured = measured_input(points=np.delete(points, 17, axis=0))
    assert segment_levelset(data, measured).domain_count == 1
    points[points[:, 0] >= 100, 0] += 30
    data, measured = measured_input(points=points)
    result = segment_levelset(data, measured)
    assert result.domain_count == 2 and result.assigned_count == 48
    assert not result.domain_labels[:, 100:120].any()


def test_unknown_measurement_and_barrier_have_no_domain_pixels():
    from dataclasses import replace
    from stmdomains.analysis.levelset_domains import segment_levelset
    from stmdomains.analysis.provenance import input_fingerprint
    data, measured = measured_input()
    record = list(measured.molecules.values())[16]
    measured = replace(measured, molecules={**measured.molecules,
        record.detection_id: replace(record, status='unknown', axes=())})
    image = np.zeros_like(data.frame.image)
    image[55:] = 100
    data = replace(data, frame=replace(data.frame, image=image))
    measured = replace(measured, metadata={**measured.metadata, 'input_sha256': input_fingerprint(data)})
    result = segment_levelset(data, measured)
    assert result.barrier_mask.any()
    assert not result.domain_labels[result.barrier_mask].any()
    x, y = np.rint(record.center_xy).astype(int)
    assert result.domain_labels[y, x] == 0
    assert result.assignments[record.detection_id].rejection_reason == 'geometry_not_2d'


def test_phase_jump_is_known_failure_and_low_quality_is_not_angle_zero():
    from stmdomains.analysis.levelset_domains import segment_levelset
    points = np.array([(40+10*x, 40+10*y+(5 if x >= 6 else 0)) for y in range(4) for x in range(12)], float)
    data, measured = measured_input(points=points)
    assert segment_levelset(data, measured).domain_count == 1  # Reference has two; known omission.
    data, measured = measured_input(quality=.5)
    result = segment_levelset(data, measured)
    assert result.domain_count == 0 and result.status == 'complete'
    assert result.metadata['levelset']['stopping_reason'] == 'no_support'
    assert {m.rejection_reason for m in result.assignments.values()} == {'geometry_low_quality'}


def test_calibrated_metric_preserves_mask_under_common_unit_change():
    from dataclasses import replace
    from stmdomains.analysis.levelset_domains import segment_levelset
    from stmdomains.core.geometry import PixelCalibration
    data, measured = measured_input(angles=np.tile([0.]*6+[30.]*6, 4))
    scaled = replace(measured, calibration=PixelCalibration(2., 2., 'nm', 'test'),
        metadata={**measured.metadata, 'spacing': 20.}, molecules={k: replace(m,
            axes=tuple(replace(a, period=a.period*2) for a in m.axes)) for k, m in measured.molecules.items()})
    assert np.array_equal(segment_levelset(data, measured).domain_labels,
                          segment_levelset(data, scaled).domain_labels)


def test_cancel_during_iteration_and_stale_measurement_do_not_publish():
    import pytest
    from dataclasses import replace
    from stmdomains.analysis.levelset_domains import segment_levelset
    from stmdomains.core.analysis_result import AnalysisCancelled
    data, measured = measured_input(angles=np.tile([0.]*6+[30.]*6, 4))
    state = {'cancel': False}
    def progress(text):
        if 'iteracja' in text:
            state['cancel'] = True
    with pytest.raises(AnalysisCancelled):
        segment_levelset(data, measured, cancelled=lambda: state['cancel'], progress=progress)
    with pytest.raises(ValueError, match='bieżącym'):
        segment_levelset(data, replace(measured, source_index=4))


def test_invalid_parameters_are_rejected():
    import pytest
    from stmdomains.analysis.levelset_settings import LevelSetSettings
    for kwargs in ({'regularization': float('nan')}, {'regularization': 3}, {'iterations': True}, {'iterations': 0}):
        with pytest.raises(ValueError):
            LevelSetSettings(**kwargs)


def test_curvature_changes_computed_mask_and_remains_repeatable():
    from stmdomains.analysis.levelset_domains import segment_levelset
    from stmdomains.analysis.levelset_settings import LevelSetSettings
    angles = np.zeros((10, 10))
    angles[3:6, 3:6] = 15
    points = np.array([(40+10*x, 40+10*y) for y in range(10) for x in range(10)], float)
    data, measured = measured_input(points=points, angles=angles.ravel())
    original = segment_levelset(data, measured, settings=LevelSetSettings(0.))
    smoothed = segment_levelset(data, measured, settings=LevelSetSettings(1.))
    repeated = segment_levelset(data, measured, settings=LevelSetSettings(1.))
    assert original.domain_count == smoothed.domain_count == 2
    assert not np.array_equal(original.domain_labels, smoothed.domain_labels)
    assert np.array_equal(smoothed.domain_labels, repeated.domain_labels)
    assert smoothed.metadata['levelset']['changed_pixels'] > 0
    for d in data.annotations.detections:
        x, y = np.rint(d.center_xy).astype(int)
        assert smoothed.domain_labels[y, x] == smoothed.assignments[d.detection_id].domain_local_id


def test_periods_cannot_be_swapped_independently_from_directions():
    from dataclasses import replace
    from stmdomains.analysis.levelset_domains import segment_levelset
    data, measured = measured_input()
    records = {}
    for key, m in measured.molecules.items():
        a, b = (10., 20.) if m.center_xy[0] < 100 else (20., 10.)
        records[key] = replace(m, axes=(replace(m.axes[0], period=a), replace(m.axes[1], period=b)))
    result = segment_levelset(data, replace(measured, molecules=records))
    assert result.domain_count == 2 and result.assigned_count == 48


def test_anisotropic_calibration_controls_real_gap_support():
    from dataclasses import replace
    from stmdomains.analysis.levelset_domains import segment_levelset
    from stmdomains.core.geometry import PixelCalibration
    data, measured = measured_input()
    # Horizontal neighbours 10 nm apart, vertical 20 nm: 17 nm support diameters
    # cannot bridge rows. Each of four rows has twelve supported centres.
    measured = replace(measured, calibration=PixelCalibration(1., 2., 'nm', 'test'))
    result = segment_levelset(data, measured)
    assert result.domain_count == 4 and result.assigned_count == 48


def test_empty_annotations_have_explicit_state():
    from test_frame_analysis import analysis_input
    from stmdomains.analysis.geometry import measure_geometry
    from stmdomains.analysis.levelset_domains import segment_levelset
    data = analysis_input(np.zeros((0, 2)), state='missing')
    result = segment_levelset(data, measure_geometry(data))
    assert result.status == 'no_annotations' and result.assigned_count == 0


def test_both_compared_methods_reject_nonfinite_image_without_filling_pixels():
    import pytest
    from dataclasses import replace
    from stmdomains.analysis.geometry_domains import segment_geometry
    from stmdomains.analysis.levelset_domains import segment_levelset
    from stmdomains.analysis.provenance import input_fingerprint
    data, measured = measured_input()
    image = data.frame.image.copy()
    image[50, 60] = np.nan
    data = replace(data, frame=replace(data.frame, image=image))
    measured = replace(measured, metadata={**measured.metadata, 'input_sha256': input_fingerprint(data)})
    for calculate in (segment_geometry, segment_levelset):
        with pytest.raises(ValueError, match='finite'):
            calculate(data, measured)
