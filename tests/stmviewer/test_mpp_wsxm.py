"""The public MPP pair preserves missing data while WSxM reads finite samples."""
import json
from dataclasses import replace

import numpy as np
import pytest
from napara.io.mpp_reader import read_mpp_file

from stmviewer.mpp_export import save_aligned_mpp, save_original_mpp
from stmviewer.series import open_frame_series
from test_aligned_mpp import subpixel_result


def test_wsxm_aligned_has_finite_pixels_and_pair_restores_exact_missing_data(tmp_path):
    result = subpixel_result().without_frame(0)
    path = save_aligned_mpp(tmp_path / 'compatible.mpp', result, wsxm_compatible=True)
    # Independent reader sees exactly the finite background required by WSxM.
    raw, = read_mpp_file(str(path))
    expected = np.full((4, 5), 1.5)
    expected[1:3, 1:4] = [[1.5, 2.5, 3.5], [5.5, 6.5, 7.5]]
    np.testing.assert_array_equal(np.rot90(raw.data, 2), expected)
    reopened, = open_frame_series([path])
    assert reopened.data.tobytes() == result.frames[0].image.data.tobytes()
    assert reopened.alignment.original_rect == (0.5, 0.75, 4, 3)
    assert reopened.alignment.reference.source_frame_index == 0
    assert reopened.measurement_time_s == 17
    assert 'WSxM' in reopened.metadata_note
    # Reopening and saving as original must preserve the same mask/history.
    copy = save_original_mpp(tmp_path / 'resaved.mpp', (reopened,), wsxm_compatible=True)
    again, = open_frame_series([copy])
    assert again.data.tobytes() == reopened.data.tobytes()
    assert again.alignment == reopened.alignment
    assert np.isfinite(read_mpp_file(str(copy))[0].data).all()


def test_original_preserves_nan_payloads_infinities_and_interior_holes(tmp_path):
    template = subpixel_result().frames[0].original
    values = np.array([[-2., 8., np.nan, -0.], [np.inf, 3., -np.inf, -2.]])
    values.view(np.uint64)[0, 2] = 0xFFF8000000000123
    before = values.tobytes()
    frames = (replace(template, data=values), replace(template, data=np.full((2, 4), np.nan)))
    path = save_original_mpp(tmp_path / 'holes.mpp', frames, wsxm_compatible=True)
    raw = read_mpp_file(str(path))
    np.testing.assert_array_equal(np.rot90(raw[0].data, 2), [[-2, 8, -2, -0.], [-2, 3, -2, -2]])
    np.testing.assert_array_equal(raw[1].data, np.zeros((2, 4)))
    restored = open_frame_series([path])
    for source, loaded in zip(frames, restored, strict=True):
        assert loaded.data.tobytes() == source.data.tobytes()
    assert values.tobytes() == before


@pytest.mark.parametrize('damage', ['overlap', 'bounds', 'boolean', 'finite-bits', 'fill', 'unknown', 'hash', 'missing'])
def test_invalid_wsxm_addon_never_partially_restores_samples(tmp_path, damage):
    path = save_aligned_mpp(tmp_path / 'invalid.mpp', subpixel_result(), wsxm_compatible=True)
    sidecar = path.with_name(path.name + '.stmviewer.json')
    metadata = json.loads(sidecar.read_text())
    missing = metadata['frames'][-1]['missing_samples']
    if damage == 'overlap':
        missing['runs'].append(missing['runs'][0])
    elif damage == 'bounds':
        missing['runs'][0][1] = 10**20
    elif damage == 'boolean':
        missing['runs'][0][0] = True
    elif damage == 'finite-bits':
        missing['runs'][0][2] = '0000000000000000'
    elif damage == 'fill':
        missing['fill_value'] = 1000
    elif damage == 'unknown':
        missing['encoding'] = 'future'
    elif damage == 'hash':
        metadata['movie']['sha256'] = '0' * 64
    if damage == 'missing':
        sidecar.unlink()
    else:
        sidecar.write_text(json.dumps(metadata))
    loaded = open_frame_series([path])
    raw = read_mpp_file(str(path))
    for actual, physical in zip(loaded, raw, strict=True):
        assert actual.data.tobytes() == np.rot90(physical.data, 2).tobytes()
        assert actual.alignment is None and actual.provenance is None
        assert 'nie można odtworzyć braków' in actual.metadata_note


def test_v3_decodes_documented_runs_independently_of_its_writer(tmp_path):
    import hashlib
    template = subpixel_result().frames[0].original
    # Author a V3 record independently; indices are displayed C order, not MPP order.
    frame = replace(template, data=np.array([[0., 2., 0.], [4., 0., 6.]]))
    path = save_original_mpp(tmp_path / 'external.mpp', (frame,))
    sidecar = path.with_name(path.name + '.stmviewer.json')
    metadata = json.loads(sidecar.read_text())
    metadata['version'] = 3
    metadata['frames'][0]['alignment'] = None
    metadata['frames'][0]['missing_samples'] = {
        'encoding': 'runs-f64le-v1', 'fill_value': 0,
        'runs': [[2, 1, '000000000000f87f'], [4, 1, '000000000000f0ff']],
    }
    sidecar.write_text(json.dumps(metadata))
    loaded, = open_frame_series([path])
    np.testing.assert_array_equal(loaded.data, [[0, 2, np.nan], [4, -np.inf, 6]])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == metadata['movie']['sha256']


def test_large_cross_block_mask_keeps_finite_samples_and_exact_bits(tmp_path):
    template = subpixel_result().frames[0].original
    values = np.full((260, 8), np.nan)
    values[100:200, 2:6] = 7
    path = save_original_mpp(tmp_path / 'long-runs.mpp', (replace(template, data=values),), wsxm_compatible=True)
    np.testing.assert_array_equal(read_mpp_file(str(path))[0].data, np.full((260, 8), 7))
    assert open_frame_series([path])[0].data.tobytes() == values.tobytes()
