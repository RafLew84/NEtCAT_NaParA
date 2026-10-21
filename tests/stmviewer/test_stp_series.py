"""File selections become complete, naturally ordered measurement series."""

from pathlib import Path

import numpy as np
import pytest

from stmviewer.series import ImportCancelled, open_stp_series

FIXTURES = Path(__file__).parent / "fixtures"


def test_natural_order_preserves_each_frames_values_and_metadata(tmp_path):
    for name, source in [("klatka10.STP", "unknown.stp"),
                         ("klatka2.stp", "asymmetric.stp"),
                         ("klatka1.stp", "unknown.stp")]:
        (tmp_path / name).write_bytes((FIXTURES / source).read_bytes())

    series = open_stp_series(list(tmp_path.iterdir()))

    assert [frame.source.name for frame in series] == [
        "klatka1.stp", "klatka2.stp", "klatka10.STP"
    ]
    np.testing.assert_array_equal(series[1].data, [
        [12, 0, 0, 3], [12, 0, 6, 0], [12, 12, 12, 1.5]
    ])
    assert series[0].size_x_nm is None
    assert series[1].size_x_nm == 8
    assert series[1].size_y_nm == 9
    assert series[1].channel == "Topo"
    assert series[2].channel is None


def test_mismatched_dimensions_reject_the_selection_and_identify_source(tmp_path):
    other = tmp_path / "smaller.stp"
    payload = (FIXTURES / "unknown.stp").read_bytes()
    other.write_bytes(payload.replace(b"Number of columns: 4", b"Number of columns: 2")[:-48])

    with pytest.raises(ValueError, match=r"smaller.stp.*2.*3.*4.*3"):
        open_stp_series([FIXTURES / "asymmetric.stp", other])


def test_cancel_during_import_never_returns_a_partial_series():
    progress = []
    with pytest.raises(ImportCancelled):
        open_stp_series(
            [FIXTURES / "asymmetric.stp", FIXTURES / "unknown.stp"],
            progress=lambda done, total, source: progress.append((done, total, source.name)),
            cancelled=lambda: bool(progress),
        )
    assert progress == [(1, 2, "asymmetric.stp")]


def test_empty_selection_and_bad_payload_raise_source_errors():
    with pytest.raises(ValueError, match="wybrano"):
        open_stp_series([])
    with pytest.raises(ValueError, match="truncated.stp"):
        open_stp_series([FIXTURES / "asymmetric.stp", FIXTURES / "truncated.stp"])


def test_different_known_scales_channels_and_units_are_allowed():
    frames = open_stp_series(list((FIXTURES / "series").glob("*.stp")))
    assert [(frame.size_x_nm, frame.size_y_nm, frame.channel, frame.signal_unit)
            for frame in frames] == [
        (None, None, None, None), (8, 9, "Topo", "nm"), (16, 12, "Current", "pA")
    ]
    np.testing.assert_array_equal(frames[2].data, [[1, 0, 0, 5], [0, 0, 0, 5], [0, 5, 5, 5]])


def test_cancellation_after_the_final_read_still_discards_the_result():
    done = []
    with pytest.raises(ImportCancelled):
        open_stp_series([FIXTURES / "unknown.stp"],
                        progress=lambda *args: done.append(True), cancelled=lambda: bool(done))
