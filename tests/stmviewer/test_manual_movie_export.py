"""Applied operator corrections survive the public movie export/import boundary."""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from nanotrack.core import RegistrationFrameResult

from stmviewer.manual_pair import ManualPairDraft
from stmviewer.manual_movie import apply_movie_correction, movie_pair_trial
from stmviewer.mpp_export import save_aligned_mpp
from stmviewer.registration import register_series
from stmviewer.series import open_frame_series

FIXTURES = Path(__file__).parent / 'fixtures'


class HalfPixelBackend:
    def estimate(self, reference_frame, moving_frame, *, moving_frame_index):
        return RegistrationFrameResult(moving_frame_index, (0.5, -0.25), 'controlled')


def corrected_ramp():
    template = open_frame_series([FIXTURES / 'asymmetric.stp'])[0]
    frames = tuple(replace(template, data=np.arange(12, dtype=np.float64).reshape(3, 4),
                           size_x_nm=8, size_y_nm=9, source_frame_index=i,
                           measurement_time_s=10 + i * 7)
                   for i in range(2))
    result = register_series(frames, backend=HalfPixelBackend())
    draft = ManualPairDraft(frames[0], frames[1], movie_pair_trial(result, 1))
    draft.nudge(1, 0)
    return apply_movie_correction(result, draft.apply())


@pytest.mark.parametrize('finite_fill', [False, True])
def test_corrected_subpixel_mpp_restores_samples_geometry_and_manual_history(tmp_path, finite_fill):
    import json
    from stmviewer.mpp_metadata import mpp_sidecar_path

    result = corrected_ramp()
    path = save_aligned_mpp(tmp_path / 'manual.mpp', result, wsxm_compatible=finite_fill)
    restored = open_frame_series([path])
    expected = np.full((4, 6), np.nan)
    expected[1:3, 2:5] = [[1.5, 2.5, 3.5], [5.5, 6.5, 7.5]]
    np.testing.assert_array_equal(restored[1].data, expected)
    assert restored[1].data.tobytes() == result.frames[1].image.data.tobytes()
    assert (restored[1].size_x_nm, restored[1].size_y_nm) == (12, 12)
    assert restored[1].measurement_time_s == 17
    history = restored[1].alignment
    assert history.shift_xy == (1.5, -0.25)
    assert history.original_rect == (1.5, 0.75, 4, 3)
    assert history.quality_score is None and history.status == 'manual_review'
    assert history.method == result.method
    assert history.manual_frame_index == 1
    manual = history.manual_movie
    assert manual is not None
    assert manual.baseline[1].shift_xy == (0.5, -0.25)
    assert manual.settings_version == result.settings_version
    assert manual.revision == result.revision
    correction, = manual.corrections
    assert correction.reference.source == str(result.frames[0].original.source)
    assert correction.reference.source_frame_index == 0
    assert correction.moving.source_frame_index == 1
    assert correction.baseline_xy == (0.5, -0.25)
    assert correction.start_xy == (0.5, -0.25)
    assert correction.correction_xy == (1, 0)
    assert correction.shift_xy == (1.5, -0.25)
    assert correction.source_label
    assert correction.settings_version == 1
    assert restored[0].alignment.manual_movie is manual
    metadata = json.loads(mpp_sidecar_path(path).read_text())
    assert metadata['version'] == 4
    assert len(metadata['manual_results']) == 1
    assert metadata['sample_encoding'] == ('finite-fill' if finite_fill else 'native-f64')


def test_deleted_correction_source_keeps_history_and_original_resave(tmp_path):
    from stmviewer.mpp_export import save_original_mpp

    corrected = corrected_ramp()
    surviving = corrected.without_frame(0)
    path = save_aligned_mpp(tmp_path / 'surviving.mpp', surviving)
    reopened, = open_frame_series([path])
    assert reopened.alignment.manual_frame_index == 1
    assert [f.source.source_frame_index for f in reopened.alignment.manual_movie.baseline] == [0, 1]
    assert reopened.alignment.manual_movie.corrections[0].reference.source_frame_index == 0
    copy = save_original_mpp(tmp_path / 'copy.mpp', (reopened,), wsxm_compatible=True)
    copied, = open_frame_series([copy])
    assert copied.data.tobytes() == reopened.data.tobytes()
    assert copied.alignment == reopened.alignment
    assert copied.provenance == reopened.provenance
    originals = tuple(frame.original for frame in corrected.frames)
    restored = open_frame_series([save_original_mpp(tmp_path / 'source.mpp', originals)])
    for actual, expected in zip(restored, originals, strict=True):
        np.testing.assert_array_equal(actual.data, expected.data)
        assert actual.alignment is None


def test_avi_contains_corrected_samples_with_same_order_fps_and_canvas(tmp_path):
    import cv2
    from stmviewer.avi_export import prepare_avi, save_avi
    from stmviewer.avi_raster import MoviePresentation
    from stmviewer.avi_sources import aligned_movie_frames

    corrected = corrected_ramp()
    before = [frame.image.data.tobytes() for frame in corrected.frames]
    originals = tuple(frame.original for frame in corrected.frames)
    plan = prepare_avi(aligned_movie_frames(originals, corrected), fps=7, codec='FFV1',
                       presentation=MoviePresentation(pixel_proportions=True, background=128))
    path = save_avi(tmp_path / 'corrected.avi', plan)
    reader = cv2.VideoCapture(str(path))
    try:
        assert reader.isOpened()
        assert reader.get(cv2.CAP_PROP_FPS) == 7
        ok, first = reader.read()
        assert ok and first.shape == (4, 6, 3)
        ok, moving = reader.read()
        assert ok
        assert not reader.read()[0]
    finally:
        reader.release()
    expected = np.full((4, 6), 128, dtype=np.uint8)
    expected[1, 2:5] = [0, 42, 85]
    expected[2, 2:5] = [170, 212, 255]
    for channel in range(3):
        # Preview normalization can differ by one quantization level at fractions.
        assert np.abs(moving[:, :, channel].astype(int) - expected).max() <= 1
        np.testing.assert_array_equal(moving[:, :, channel][expected == 128], 128)
    assert [frame.image.data.tobytes() for frame in corrected.frames] == before


def test_corrupt_shared_manual_history_rejects_entire_sidecar(tmp_path):
    import copy
    import json
    from stmviewer.mpp_metadata import mpp_sidecar_path

    result = corrected_ramp()
    path = save_aligned_mpp(tmp_path / 'malformed.mpp', result, wsxm_compatible=True)
    sidecar = mpp_sidecar_path(path)
    original = json.loads(sidecar.read_text())
    for field, value in [('manual_result', 99), ('manual_frame_index', True)]:
        metadata = copy.deepcopy(original)
        metadata['frames'][-1]['alignment'][field] = value
        sidecar.write_text(json.dumps(metadata))
        reopened = open_frame_series([path])
        assert all(frame.alignment is None and frame.provenance is None for frame in reopened)
        assert all('pominięto' in frame.metadata_note for frame in reopened)
        assert all(np.isfinite(frame.data).all() for frame in reopened)
    metadata = copy.deepcopy(original)
    metadata['manual_results'][0]['corrections'][0]['shift_xy'] = [200, -0.25]
    sidecar.write_text(json.dumps(metadata))
    reopened = open_frame_series([path])
    assert all(frame.alignment is None and 'pominięto' in frame.metadata_note for frame in reopened)


def test_two_overrides_and_deleted_moving_frame_remain_in_export_history(tmp_path):
    source = corrected_ramp().frames[0].original
    originals = tuple(replace(source, source_frame_index=i) for i in range(3))
    result = register_series(originals, backend=HalfPixelBackend())
    first = ManualPairDraft(originals[0], originals[1], movie_pair_trial(result, 1))
    first.nudge(1, 0)
    result = apply_movie_correction(result, first.apply())
    second = ManualPairDraft(originals[1], originals[2], movie_pair_trial(result, 2))
    second.nudge(0, 1)
    result = apply_movie_correction(result, second.apply())
    surviving = result.without_frame(1)
    restored = open_frame_series([save_aligned_mpp(tmp_path / 'two.mpp', surviving)])
    assert restored[-1].alignment.shift_xy == (2, 0.5)
    history = restored[-1].alignment.manual_movie
    assert len(history.corrections) == 2
    assert [c.moving.source_frame_index for c in history.corrections] == [1, 2]
    assert [c.shift_xy for c in history.corrections] == [(1.5, -0.25), (0.5, 0.75)]
    assert [b.source.source_frame_index for b in history.baseline] == [0, 1, 2]
    assert restored[-1].alignment.manual_frame_index == 2
    assert restored[-1].data.tobytes() == result.frames[-1].image.data.tobytes()


@pytest.mark.parametrize('damage', ['absent_moving', 'absent_reference', 'reversed_pair',
                                    'wrong_baseline_xy', 'wrong_frame_index',
                                    'wrong_cumulative_xy', 'false_confidence'])
def test_inconsistent_manual_provenance_discards_whole_metadata(tmp_path, damage):
    import json
    from stmviewer.mpp_metadata import mpp_sidecar_path

    path = save_aligned_mpp(tmp_path / 'inconsistent.mpp', corrected_ramp(), wsxm_compatible=True)
    sidecar = mpp_sidecar_path(path)
    metadata = json.loads(sidecar.read_text())
    correction = metadata['manual_results'][0]['corrections'][0]
    history = metadata['frames'][1]['alignment']
    if damage == 'absent_moving':
        correction['moving']['source_frame_index'] = 99
    elif damage == 'absent_reference':
        correction['reference']['source_frame_index'] = 99
    elif damage == 'reversed_pair':
        correction['reference'], correction['moving'] = correction['moving'], correction['reference']
    elif damage == 'wrong_baseline_xy':
        correction['baseline_xy'] = [0.25, -0.25]
    elif damage == 'wrong_frame_index':
        history['manual_frame_index'] = 0
    elif damage == 'wrong_cumulative_xy':
        history['shift_xy'] = [1.25, -0.25]
        history['origin_xy'] = [1.25, 0.75]
        history['original_rect'] = [1.25, 0.75, 4, 3]
    else:
        history['status'] = 'ok'
        history['quality_score'] = 1
    sidecar.write_text(json.dumps(metadata))
    reopened = open_frame_series([path])
    assert all(frame.alignment is None and frame.provenance is None for frame in reopened)
    assert all('pominięto' in frame.metadata_note and np.isfinite(frame.data).all()
               for frame in reopened)
