"""CPU method selection -> complete aligned originals, using NanoTrack defaults."""

import numpy as np
import pytest

from make_cpu_registration_fixtures import cpu_frames
from test_registration import frames_with_data
from stmviewer.registration import register_series


@pytest.mark.parametrize('method,label', [
    ('tile_correlation_ransac', 'Tile+RANSAC'),
    ('ecc_translation', 'ECC'),
    ('optical_flow_median', 'Optical Flow'),
])
def test_cpu_method_matches_nanotrack_defaults_and_known_translation(method, label):
    from nanotrack.core import RegistrationSettings
    from nanotrack.registration import run_adjacent_phase_registration

    originals = frames_with_data(*cpu_frames())
    before = [f.data.copy() for f in originals]
    progress = []
    result = register_series(originals, method=method, progress=lambda *args: progress.append(args))

    assert result.method == label
    np.testing.assert_allclose([f.shift_xy for f in result.frames], [(0, 0), (2, -1), (-1, 1)], atol=0.3)
    baseline = run_adjacent_phase_registration(
        np.stack(before), settings=RegistrationSettings(backend=method, registration_view='raw'),
    )
    for index, aligned in enumerate(result.frames):
        expected = baseline.get_result(index)
        assert aligned.shift_xy == expected.shift_xy
        assert aligned.status == expected.status
        assert aligned.quality_score == expected.quality_score
        assert aligned.original is originals[index]
        assert aligned.original_rect[2:] == (80, 80)
        np.testing.assert_array_equal(originals[index].data, before[index])
        assert aligned.image.data.shape == result.canvas_shape
        assert np.isnan(aligned.image.data[~aligned.valid_mask]).all()
        assert aligned.valid_mask.any()
        assert not aligned.image.data.flags.writeable
    assert [p[:2] for p in progress] == [(i, 6) for i in range(1, 7)]
    assert label in progress[1][2]
    remaining = result.without_frame(0)
    assert remaining.method == label and remaining.reference == result.reference
    assert remaining.canvas_shape == result.canvas_shape
    assert remaining.frames[0] is result.frames[1]


@pytest.mark.parametrize('method', ['tile_correlation_ransac', 'ecc_translation', 'optical_flow_median'])
def test_cpu_low_confidence_is_complete_and_inherited(method):
    from dataclasses import replace
    from nanotrack.core import RegistrationSettings
    from nanotrack.registration import build_registration_backend_from_settings

    real = build_registration_backend_from_settings(RegistrationSettings(backend=method))

    class UncertainBackend:
        def estimate(self, *args, **kwargs):
            result = real.estimate(*args, **kwargs)
            return replace(result, status='low_confidence', quality_score=0.2) if result.frame_index == 1 else result

    result = register_series(frames_with_data(*cpu_frames()), method=method, backend=UncertainBackend())
    assert [f.status for f in result.frames] == ['ok', 'low_confidence', 'low_confidence']
    assert [f.quality_score for f in result.frames] == [1, 0.2, 0.2]
    assert result.frames[2].inherited_uncertainty
    assert all(f.valid_mask.any() for f in result.frames)


def test_unknown_method_and_missing_dependency_never_fall_back_to_phase(monkeypatch):
    import builtins
    from stmviewer.registration import RegistrationError

    frames = frames_with_data(*cpu_frames())
    with pytest.raises(RegistrationError, match='Nieznana metoda'):
        register_series(frames, method='not-a-method')
    original_import = builtins.__import__

    def without_cv2(name, *args, **kwargs):
        if name == 'cv2':
            raise ModuleNotFoundError("No module named 'cv2'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', without_cv2)
    with pytest.raises(ModuleNotFoundError, match='cv2'):
        register_series(frames, method='ecc_translation')
    assert register_series(frames).method == 'Phase'
