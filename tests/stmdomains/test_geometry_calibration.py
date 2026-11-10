import pytest
from stmdomains.analysis.geometry_calibration import calibration_from_header


def test_explicit_xy_units_and_image_size_are_required():
    header = {'General Info': {'Number of columns': '200', 'Number of rows': '100'},
              'Control': {'X Amplitude': '100 nm', 'Y Amplitude': '0.2 um'}}
    scale = calibration_from_header(header, (100, 200))
    assert (scale.x, scale.y, scale.unit) == (.5, 2., 'nm')
    assert calibration_from_header(header, (100, 201)).unit == 'px'
    header['Control'].pop('Y Amplitude')
    assert calibration_from_header(header, (100, 200)).unit == 'px'


@pytest.mark.parametrize('value', ['100', 'NaN nm', '-1 nm', '5 bananas', '0 nm'])
def test_uncalibrated_or_bad_header_never_invents_nm(value):
    header = {'Control': {'X Amplitude': value, 'Y Amplitude': '100 nm'},
              'General Info': {'Number of columns': '100', 'Number of rows': '100'}}
    assert calibration_from_header(header, (100, 100)).unit == 'px'
