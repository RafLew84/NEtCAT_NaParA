"""Aligned persistence through registration, pair writer and public importer."""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from nanotrack.core import RegistrationFrameResult

from stmviewer.mpp_export import save_aligned_mpp
from stmviewer.registration import register_series
from stmviewer.series import open_frame_series

FIXTURES = Path(__file__).parent / 'fixtures'


class HalfPixelBackend:
    def estimate(self, reference_frame, moving_frame, *, moving_frame_index):
        return RegistrationFrameResult(moving_frame_index, (0.5, -0.25), 'controlled')


def subpixel_result():
    template = open_frame_series([FIXTURES / 'asymmetric.stp'])[0]
    frames = tuple(replace(template, data=np.arange(12, dtype=np.float64).reshape(3, 4),
                           size_x_nm=8, size_y_nm=9, offset_x_nm=13, offset_y_nm=-7,
                           source_frame_index=i, measurement_time_s=10 + i * 7)
                   for i in range(2))
    return register_series(frames, backend=HalfPixelBackend())


def test_subpixel_export_after_reference_deletion_preserves_values_and_geometry(tmp_path):
    result = subpixel_result().without_frame(0)
    assert result is not None
    path = save_aligned_mpp(tmp_path / 'aligned.mpp', result)
    restored, = open_frame_series([path])
    expected = np.full((4, 5), np.nan)
    expected[1:3, 1:4] = [[1.5, 2.5, 3.5], [5.5, 6.5, 7.5]]
    np.testing.assert_array_equal(restored.data, expected)
    assert restored.data.tobytes() == result.frames[0].image.data.tobytes()
    np.testing.assert_array_equal(np.isfinite(restored.data), result.frames[0].valid_mask)
    assert (restored.size_x_nm, restored.size_y_nm) == (10, 12)
    assert (restored.offset_x_nm, restored.offset_y_nm) == (None, None)
    assert restored.measurement_time_s == 17
    assert restored.provenance.source_frame_index == 1
    assert restored.source == path and restored.source_frame_index == 0
    history = restored.alignment
    assert history.canvas_shape == (4, 5)
    assert history.padding_ltrb == (0, 1, 1, 0)
    assert history.pixel_size_nm == (2, 3)
    assert history.original_shape == (3, 4)
    assert history.original_rect == (0.5, 0.75, 4, 3)
    assert history.shift_xy == (0.5, -0.25)
    assert history.original_size_nm == (8, 9)
    assert history.original_offset_nm == (13, -7)
    assert history.reference.source == str(result.reference.source)
    assert history.reference.source_frame_index == 0
    assert history.previous is None


def test_resave_retains_history_and_new_registration_uses_loaded_pixels(tmp_path):
    from stmviewer.mpp_export import save_original_mpp
    from stmviewer.registration import RegistrationError

    path = save_aligned_mpp(tmp_path / 'padded.mpp', subpixel_result())
    loaded = open_frame_series([path])
    copy = save_original_mpp(tmp_path / 'input.mpp', loaded)
    reopened = open_frame_series([copy])
    for actual, expected in zip(reopened, loaded, strict=True):
        assert actual.data.tobytes() == expected.data.tobytes()
        assert actual.alignment == expected.alignment
    with pytest.raises(RegistrationError, match='NaN/Inf'):
        register_series(reopened)
    # Zero-shift aligned has only finite pixels: its label must not block registration.
    source = tuple(aligned.original for aligned in subpixel_result().frames[:1])
    first = register_series(source)
    loaded = open_frame_series([save_aligned_mpp(tmp_path / 'finite.mpp', first)])
    second = register_series(loaded)
    assert second.frames[0].original is loaded[0]
    assert second.frames[0].image.alignment is None  # no stale geometry on the new result
    final = open_frame_series([save_aligned_mpp(tmp_path / 'twice.mpp', second)])[0]
    np.testing.assert_array_equal(final.data, loaded[0].data)
    assert final.alignment.previous == loaded[0].alignment
    assert final.alignment.reference.source == str(tmp_path / 'finite.mpp')
    assert final.alignment.original_shape == (3, 4)


def test_extreme_frame_removal_keeps_canvas_and_mixed_source_calibration(tmp_path):
    frames = tuple(a.original for a in subpixel_result().frames)
    frames = (frames[0], replace(frames[1], size_x_nm=80, size_y_nm=None,
                                channel='Current', signal_unit='nA', offset_x_nm=-100))
    result = register_series(frames, backend=HalfPixelBackend())
    path = save_aligned_mpp(tmp_path / 'mixed.mpp', result)
    restored = open_frame_series([path])
    assert all(f.size_x_nm is None and f.size_y_nm is None for f in restored)
    assert restored[0].alignment.original_size_nm == (8, 9)
    assert restored[1].alignment.original_size_nm == (80, None)
    assert restored[1].alignment.original_offset_nm == (-100, -7)
    assert restored[1].channel == 'Current' and restored[1].signal_unit == 'nA'
    assert restored[1].raw_header == frames[1].raw_header
    surviving = result.without_frame(1)
    saved, = open_frame_series([save_aligned_mpp(tmp_path / 'without-extreme.mpp', surviving)])
    assert saved.data.shape == (4, 5)
    assert saved.alignment.padding_ltrb == (0, 1, 1, 0)
    assert saved.alignment.original_rect == (0, 1, 4, 3)
    assert saved.data.tobytes() == result.frames[0].image.data.tobytes()


def test_inconsistent_geometry_in_last_record_discards_whole_addon(tmp_path):
    import copy
    import json
    from stmviewer.mpp_metadata import mpp_sidecar_path

    path = save_aligned_mpp(tmp_path / 'broken-history.mpp', subpixel_result())
    sidecar = mpp_sidecar_path(path)
    metadata = json.loads(sidecar.read_text())
    for key, value in [('origin_xy', [0, 0]), ('canvas_shape', [3, 4]),
                       ('original_rect', [0.5, 0.75, 3, 3]), ('validity', 'inside-rectangle'),
                       ('pixel_size_nm', [1, 1]), ('reference', {'source': 'other', 'source_frame_index': 0})]:
        modified = copy.deepcopy(metadata)
        modified['frames'][-1]['alignment'][key] = value
        sidecar.write_text(json.dumps(modified))
        loaded = open_frame_series([path])
        assert all(f.alignment is None and f.provenance is None for f in loaded), key
        assert all('pominięto' in f.metadata_note for f in loaded), key
        for frame, aligned in zip(loaded, subpixel_result().frames, strict=True):
            assert frame.data.tobytes() == aligned.image.data.tobytes()


def test_history_chain_requires_matching_physical_input(tmp_path):
    import json
    from stmviewer.mpp_metadata import mpp_sidecar_path

    source = (subpixel_result().frames[0].original,)
    first = open_frame_series([save_aligned_mpp(tmp_path / 'first.mpp', register_series(source))])
    path = save_aligned_mpp(tmp_path / 'second.mpp', register_series(first))
    sidecar = mpp_sidecar_path(path)
    metadata = json.loads(sidecar.read_text())
    # Valid in isolation, but incompatible with the next registration's declared input scale.
    previous = metadata['frames'][0]['alignment']['previous']
    previous['pixel_size_nm'] = [20, 30]
    previous['original_size_nm'] = [80, 90]
    sidecar.write_text(json.dumps(metadata))
    loaded, = open_frame_series([path])
    assert loaded.alignment is None and 'pominięto' in loaded.metadata_note


def test_existing_readers_receive_full_aligned_values_and_nan(tmp_path):
    from napara.io.mpp_reader import read_mpp_file
    from nanotrack.io.mpp_loader import load_mpp_sequence
    from moltrack.io.sequence_loader import load_moltrack_image_series

    result = subpixel_result()
    path = save_aligned_mpp(tmp_path / 'legacy-aligned.mpp', result)
    for actual, expected in zip(read_mpp_file(str(path)), result.frames, strict=True):
        np.testing.assert_array_equal(actual.data, np.rot90(expected.image.data, 2))
        assert actual.size_nm_x == 10 and actual.size_nm_y == pytest.approx(12, rel=1e-14)
    expected = np.stack([f.image.data for f in result.frames])
    np.testing.assert_array_equal(load_mpp_sequence(str(path)).raw_frames, expected)
    np.testing.assert_array_equal(load_moltrack_image_series(path).raw_frames, expected)
