"""Real S94 decoding through Viewer's file-import boundary."""

from pathlib import Path

import numpy as np
import pytest

from stmviewer.io import open_stp
from stmviewer.s94 import open_s94

FIXTURES = Path(__file__).parent / "fixtures" / "s94"


def test_known_topography_preserves_values_geometry_and_source():
    frame = open_s94(FIXTURES / "frame2.s94")

    np.testing.assert_array_equal(frame.data, [
        [5.5, 0, 0, 1.375], [5.5, 0, 2.75, 0], [5.5, 5.5, 5.5, 0.6875]
    ])
    np.testing.assert_array_equal(frame.data, open_stp(FIXTURES / "frame1.stp").data)
    assert frame.data.dtype == np.float64
    assert frame.source == (FIXTURES / "frame2.s94").resolve()
    assert (frame.channel, frame.signal_unit) == ("Topography", "nm")
    assert (frame.size_x_nm, frame.size_y_nm) == (8, 9)
    assert (frame.offset_x_nm, frame.offset_y_nm) == (2, -1)
    assert frame.bias_v == pytest.approx(-0.2)
    assert frame.scan_angle_deg == 37
    assert frame.setpoint_a is None  # It has no confirmed current unit in the source contract.
    assert frame.raw_header["Image_Number"] == "42"


@pytest.mark.parametrize("mode,gain,unit,first_value,raw_note", [
    (0, 1, "nm", 1.375, None), (0, 3, "nm", 22.0, None),
    (1, 99, "nA", 5.0, None),
    (0, 99, None, 16384, "wzmocnienie"), (7, 2, None, 16384, "tryb"),
])
def test_calibration_distinguishes_physical_values_from_raw_samples(
    tmp_path, mode, gain, unit, first_value, raw_note
):
    import struct

    payload = bytearray((FIXTURES / "frame2.s94").read_bytes())
    struct.pack_into("<h", payload, 6, mode)
    struct.pack_into("<h", payload, 36, gain)
    path = tmp_path / "calibration.s94"
    path.write_bytes(payload)

    frame = open_s94(path)

    assert frame.signal_unit == unit
    assert frame.data[0, 0] == first_value
    if raw_note is None:
        assert frame.calibration_note is None
    else:
        assert "surowe" in frame.calibration_note.lower()
        assert raw_note in frame.calibration_note
    assert frame.channel == {0: "Topography", 1: "Current"}.get(mode, "Unknown (7)")


def test_swapped_rectangular_frame_transposes_data_and_axis_metadata(tmp_path):
    import struct

    payload = bytearray((FIXTURES / "frame2.s94").read_bytes())
    struct.pack_into("<h", payload, 4, 1)  # Swapped
    path = tmp_path / "swapped.s94"
    path.write_bytes(payload)

    frame = open_s94(path)

    np.testing.assert_array_equal(frame.data, [
        [5.5, 5.5, 5.5], [0, 0, 5.5], [0, 2.75, 5.5], [1.375, 0, 0.6875]
    ])
    assert (frame.size_x_nm, frame.size_y_nm) == (9, 8)
    assert (frame.offset_x_nm, frame.offset_y_nm) == (-1, 2)
    assert frame.scan_angle_deg == 37  # Acquisition setting, not a derived raster angle.
    assert frame.raw_header["x_points"] == "4"
    assert frame.raw_header["x_offset"] == "2.0"


def test_invalid_physical_metadata_remains_unknown_without_losing_real_zeros(tmp_path):
    import struct

    payload = bytearray((FIXTURES / "frame2.s94").read_bytes())
    for offset, value in [(12, float('nan')), (16, -1), (20, float('inf')), (24, 0), (32, 0)]:
        struct.pack_into('<f', payload, offset, value)
    path = tmp_path / 'missing-scale.s94'
    path.write_bytes(payload)
    frame = open_s94(path)
    assert (frame.size_x_nm, frame.size_y_nm, frame.offset_x_nm) == (None, None, None)
    assert frame.offset_y_nm == frame.bias_v == 0


@pytest.mark.parametrize('invalid', ['header', 'payload', 'dimensions', 'swapped'])
def test_invalid_s94_is_rejected_with_its_source(tmp_path, invalid):
    import struct

    payload = bytearray((FIXTURES / 'frame2.s94').read_bytes())
    if invalid == 'header':
        payload = payload[:59]
    elif invalid == 'payload':
        payload = payload[:-1]
    elif invalid == 'dimensions':
        struct.pack_into('<h', payload, 0, 0)
    else:
        struct.pack_into('<h', payload, 4, 2)
    path = tmp_path / f'bad-{invalid}.s94'
    path.write_bytes(payload)
    with pytest.raises(ValueError, match=path.name):
        open_s94(path)


def test_payload_is_signed_little_endian(tmp_path):
    import struct

    payload = bytearray((FIXTURES / 'frame2.s94').read_bytes())
    struct.pack_into('<h', payload, 6, 7)  # Unknown mode: inspect exact raw counts.
    payload[60:64] = b'\x02\x01\xfe\xff'  # 258, -2, not 513, -257.
    path = tmp_path / 'byte-order.s94'
    path.write_bytes(payload)
    frame = open_s94(path)
    assert frame.data[0, :2].tolist() == [258, -2]
