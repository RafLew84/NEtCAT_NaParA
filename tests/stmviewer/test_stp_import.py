"""Real files through the public import boundary; no reader mocks."""

from pathlib import Path

import numpy as np
import pytest

from stmviewer.io import open_stp

FIXTURES = Path(__file__).parent / "fixtures"


def test_open_stp_preserves_values_orientation_and_source_metadata():
    frame = open_stp(FIXTURES / "asymmetric.stp")

    np.testing.assert_array_equal(
        frame.data, [[12, 0, 0, 3], [12, 0, 6, 0], [12, 12, 12, 1.5]]
    )
    assert frame.data.dtype == np.dtype("float64")
    assert frame.source == (FIXTURES / "asymmetric.stp").resolve()
    assert frame.channel == "Topo"
    assert frame.signal_unit == "nm"
    assert frame.size_x_nm == pytest.approx(8)
    assert frame.size_y_nm == pytest.approx(9)
    assert frame.offset_x_nm == pytest.approx(2)
    assert frame.offset_y_nm == pytest.approx(-1)
    assert frame.bias_v == 0
    assert frame.setpoint_a == pytest.approx(2.5e-10)
    assert frame.scan_angle_deg == 0
    assert frame.raw_header["Z Amplitude"] == "99 nm"


@pytest.mark.parametrize("damage", ["truncated", "header", "unsupported"])
def test_bad_stp_reports_the_source_instead_of_returning_an_image(tmp_path, damage):
    data = (FIXTURES / "asymmetric.stp").read_bytes()
    if damage == "truncated":
        data = data[:-8]
    elif damage == "header":
        data = b"not an STP file"
    else:
        data = data.replace(b"Image Data Type: double", b"Image Data Type: short")
    source = tmp_path / "damaged.stp"
    source.write_bytes(data)
    with pytest.raises(ValueError, match="damaged.stp"):
        open_stp(source)


def test_missing_metadata_remains_unknown():
    frame = open_stp(FIXTURES / "unknown.stp")
    np.testing.assert_array_equal(frame.data, [[0, 3, 3, 3], [0, 0, 3, 0], [0, 0, 0, 0]])
    for value in (frame.channel, frame.signal_unit, frame.size_x_nm, frame.size_y_nm,
                  frame.offset_x_nm, frame.offset_y_nm, frame.bias_v,
                  frame.setpoint_a, frame.scan_angle_deg):
        assert value is None


@pytest.mark.parametrize("x_amplitude", [b"0 nm", b"-8 nm", b"8", b"8 bananas", b"nan nm"])
def test_invalid_spatial_calibration_is_unknown(tmp_path, x_amplitude):
    path = tmp_path / "uncalibrated.stp"
    path.write_bytes((FIXTURES / "asymmetric.stp").read_bytes().replace(b"8 nm", x_amplitude))
    frame = open_stp(path)
    assert frame.size_x_nm is None
    assert frame.size_y_nm == pytest.approx(9)


def test_aliases_and_units_do_not_change_signal_samples(tmp_path):
    path = tmp_path / "current.stp"
    data = (FIXTURES / "asymmetric.stp").read_bytes()
    for before, after in [(b"Acquisition channel: Topo", b"Channel: Current forward"),
                          (b"8 nm", "2 µm".encode()), (b"X-Offset", b"X Offset"),
                          (b"Z Amplitude: 99 nm", b"Z Amplitude: 99 nA")]:
        data = data.replace(before, after)
    path.write_bytes(data)
    frame = open_stp(path)
    assert frame.channel == "Current forward"
    assert frame.signal_unit == "nA"
    assert frame.size_x_nm == pytest.approx(2000)
    assert frame.offset_x_nm == pytest.approx(2)
    np.testing.assert_array_equal(frame.data, [[12, 0, 0, 3], [12, 0, 6, 0], [12, 12, 12, 1.5]])


def test_legacy_header_encoding_keeps_micro_units(tmp_path):
    path = tmp_path / "legacy.stp"
    data = (FIXTURES / "asymmetric.stp").read_bytes().replace(b"8 nm", "2 µm".encode("latin1"))
    path.write_bytes(data)
    frame = open_stp(path)
    assert frame.size_x_nm == pytest.approx(2000)
    assert frame.raw_header["X Amplitude"] == "2 µm"
