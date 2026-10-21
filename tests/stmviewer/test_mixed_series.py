"""STP and S94 share one transactional import and natural filename order."""

from pathlib import Path

from stmviewer.series import open_frame_series

FIXTURES = Path(__file__).parent / "fixtures" / "s94"


def test_mixed_series_has_one_order_and_per_frame_calibration():
    frames = open_frame_series([FIXTURES / name for name in (
        "frame10.S94", "frame2.s94", "frame1.stp"
    )])
    assert [frame.source.name for frame in frames] == ["frame1.stp", "frame2.s94", "frame10.S94"]
    assert [frame.signal_unit for frame in frames] == ["nm", "nm", "nA"]
    assert [frame.channel for frame in frames] == ["Topo", "Topography", "Current"]
    assert [frame.size_x_nm for frame in frames] == [8, 8, 16]
    assert [frame.size_y_nm for frame in frames] == [9, 9, 12]
    assert [frame.data[0, 0] for frame in frames] == [5.5, 5.5, 5]


def test_compatibility_uses_dimensions_after_s94_transposition(tmp_path):
    import struct
    import pytest

    with pytest.raises(ValueError, match='swapped.s94.*3.*4.*4.*3'):
        open_frame_series([FIXTURES / 'frame1.stp', FIXTURES / 'swapped.s94'])
    payload = bytearray((FIXTURES / 'swapped.s94').read_bytes())
    struct.pack_into('<hh', payload, 0, 3, 4)
    path = tmp_path / 'swapped-compatible.s94'
    path.write_bytes(payload)
    frames = open_frame_series([FIXTURES / 'frame1.stp', path])
    assert [frame.data.shape for frame in frames] == [(3, 4), (3, 4)]
    assert (frames[1].size_x_nm, frames[1].size_y_nm) == (9, 8)


def test_unsupported_format_is_rejected_with_source():
    import pytest

    with pytest.raises(ValueError, match='movie.mpp.*STP.*S94'):
        open_frame_series([FIXTURES / 'movie.mpp'])
