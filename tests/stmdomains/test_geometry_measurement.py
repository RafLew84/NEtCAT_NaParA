"""Known row geometry is observable through the standalone measurement API."""

import numpy as np
import pytest

from test_frame_analysis import analysis_input


def rectangular_points(angle=17., pixel_size=(1., 1.)):
    # Physical coordinates: 10 between points along rows, 14 between rows.
    points = np.array([(10*x, 14*y) for y in range(-4, 5) for x in range(-5, 6)], float)
    angle = np.deg2rad(angle)
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    physical = points @ rotation.T
    return physical * (1., -1.) / pixel_size + (128., 128.)


def test_rectangular_lattice_reports_row_direction_not_frequency_normal():
    from stmdomains.analysis.geometry import measure_geometry
    data = analysis_input(rectangular_points())
    result = measure_geometry(data)
    center = result.molecules['m-0049']
    assert center.status == 'lattice_2d', center.reason
    assert center.axes[0].row_angle_deg == pytest.approx(17., abs=1.)
    assert center.axes[0].period == pytest.approx(14., abs=.3)
    assert center.axes[1].row_angle_deg == pytest.approx(107., abs=1.)
    assert center.axes[1].period == pytest.approx(10., abs=.3)
    assert center.axes[0].normal_angle_deg == pytest.approx(107., abs=1.)
    assert center.local_count >= 10 and center.effective_count >= 8
    assert center.angle_stability_deg < 2
    assert result.calibration.unit == 'px'
    assert result.working_index == 3 and result.source_index == 19
    assert result.metadata['input_sha256']


@pytest.mark.parametrize('angle', [47., 173.])
def test_rotation_and_anisotropic_scale_preserve_physical_measurements(angle):
    from stmdomains.analysis.geometry import measure_geometry
    from stmdomains.analysis.geometry_spectrum import axial_difference
    from stmdomains.core.geometry import PixelCalibration
    result = measure_geometry(analysis_input(rectangular_points(angle, (.6, 1.2))),
                              calibration=PixelCalibration(.6, 1.2, 'nm', 'test'))
    center = result.molecules['m-0049']
    assert center.status == 'lattice_2d'
    assert axial_difference(center.axes[0].row_angle_deg, angle) < 1
    assert center.axes[0].period == pytest.approx(14., abs=.3)
    assert center.axes[1].period == pytest.approx(10., abs=.3)
    assert result.calibration.unit == 'nm'


def test_rows_are_not_a_two_dimensional_lattice():
    from stmdomains.analysis.geometry import measure_geometry
    rng = np.random.default_rng(20261104)
    points = np.array([(x, y) for y in np.arange(25, 240, 14)
                       for x in rng.uniform(15, 240, 23)])
    result = measure_geometry(analysis_input(points))
    valid = [m for m in result.molecules.values() if m.axes]
    assert len(valid) > 20
    assert sum(m.status == 'rows_1d' for m in valid) / len(valid) > .95
    assert np.median([m.axes[0].period for m in valid]) == pytest.approx(14., abs=.5)


def test_sparse_and_random_points_do_not_draw_confident_axes():
    from stmdomains.analysis.geometry import measure_geometry
    sparse = measure_geometry(analysis_input(np.array([(20, 20), (30, 30), (40, 40)])))
    assert all(m.status == 'insufficient' and not m.axes for m in sparse.molecules.values())
    noise = measure_geometry(analysis_input(np.random.default_rng(42).uniform(5, 250, (120, 2))))
    assert sum(bool(m.axes) for m in noise.molecules.values()) <= 2


def test_cancellation_is_cooperative_and_does_not_modify_input():
    from stmdomains.analysis.geometry import measure_geometry
    from stmdomains.core.analysis_result import AnalysisCancelled
    data = analysis_input(rectangular_points())
    image = data.frame.image.copy()
    calls = []
    with pytest.raises(AnalysisCancelled):
        measure_geometry(data, progress=calls.append, cancelled=lambda: len(calls) > 2)
    assert np.array_equal(data.frame.image, image)


def test_measurement_does_not_scan_native_libraries_in_worker(monkeypatch):
    # Regression for a native Qt deadlock in dl_iterate_phdr / threadpoolctl
    # while the GUI loads platform libraries. Guard the external library boundary.
    import threadpoolctl
    from stmdomains.analysis.geometry import measure_geometry
    def forbid_scan(*args, **kwargs):
        raise AssertionError('Geometry worker must not scan loaded native libraries')
    monkeypatch.setattr(threadpoolctl.ThreadpoolController, '__init__', forbid_scan)
    result = measure_geometry(analysis_input(rectangular_points()))
    assert result.molecules['m-0049'].status == 'lattice_2d'
