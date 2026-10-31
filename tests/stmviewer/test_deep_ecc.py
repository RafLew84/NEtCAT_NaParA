"""Hybrid registration through public pair/series APIs and external model boundary."""

import numpy as np

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.pair_comparison import estimate_pair
from deep_ecc_fixture import controlled_loftr as model_fixture, textured_pair

controlled_loftr = model_fixture

METHOD = 'deep_matcher_ecc'


def test_hybrid_refines_exact_deep_start_into_total_subpixel_translation(controlled_loftr):
    control, weights = controlled_loftr
    frames = textured_pair()
    originals = [f.data.copy() for f in frames]

    trial = estimate_pair(*frames, method=METHOD, deep_options=DeepMatcherOptions(weights, 'cpu'))

    np.testing.assert_allclose(trial.shift_xy, (18.25, -12.5), atol=0.12)
    assert trial.label == 'Deep Matcher + ECC (v1)'
    assert trial.hybrid.deep_shift_xy == (19.0, -12.0)
    np.testing.assert_allclose(trial.hybrid.correction_xy, (-0.75, -0.5), atol=0.12)
    assert trial.hybrid.final_shift_xy == trial.shift_xy
    assert trial.status == 'manual_review' and trial.quality_score is None
    assert trial.hybrid.ecc_score > 0.9
    assert control.loaded == 1 and control.calls == 1
    assert 'max_iterations=100' in trial.settings_text
    assert str(weights) in trial.settings_text
    assert trial.hybrid.requested_device == 'cpu' and trial.hybrid.actual_device == 'CPU'
    for frame, original in zip(frames, originals):
        np.testing.assert_array_equal(frame.data, original)


def test_hybrid_series_reuses_model_and_accumulates_only_final_pair_shifts(controlled_loftr):
    from stmviewer.registration import register_series
    from make_registration_fixtures import frames_with_data

    control, weights = controlled_loftr
    first, second = textured_pair()
    _, third = textured_pair((-6.75, 8.5))
    frames = frames_with_data(first.data, second.data, third.data)
    control.shifts = [(19, -12), (-24.5, 21.6)]
    progress = []
    result = register_series(frames, method=METHOD, deep_options=DeepMatcherOptions(weights, 'cpu'),
                             progress=lambda *args: progress.append(args))

    np.testing.assert_allclose([frame.shift_xy for frame in result.frames],
                               [(0, 0), (18.25, -12.5), (-6.75, 8.5)], atol=0.2)
    assert control.loaded == 1 and control.calls == 2
    assert result.method == 'Deep Matcher + ECC (v1)'
    assert result.device == 'CPU'
    assert result.canvas_shape == (150, 218)
    assert [frame.status for frame in result.frames] == ['ok', 'manual_review', 'manual_review']
    assert [frame.quality_score for frame in result.frames] == [1, None, None]
    assert result.pair_diagnostics[0] is None
    assert result.pair_diagnostics[1].deep_shift_xy == (19, -12)
    np.testing.assert_allclose(result.pair_diagnostics[2].deep_shift_xy, (-24.5, 21.6), atol=1e-5)
    assert result.without_frame(1).pair_diagnostics == (None, result.pair_diagnostics[2])
    assert any('Deep Matcher (CPU)' in text for _, _, text in progress)
    assert any('ECC (CPU)' in text for _, _, text in progress)
    assert all(np.isnan(frame.image.data[~frame.valid_mask]).all() for frame in result.frames)

    control.shifts = [(19, -12)]
    pair = estimate_pair(frames[0], frames[1], method=METHOD,
                          deep_options=DeepMatcherOptions(weights, 'cpu'))
    assert pair.shift_xy == result.pair_diagnostics[1].final_shift_xy


def test_hybrid_rejects_missing_measurements_with_pair_and_stage(controlled_loftr):
    import pytest
    from stmviewer.registration import RegistrationError, register_series

    control, weights = controlled_loftr
    frames = textured_pair()
    frames[1].data[8, 11] = np.nan
    options = DeepMatcherOptions(weights, 'cpu')
    for operation in (lambda: estimate_pair(*frames, method=METHOD, deep_options=options),
                      lambda: register_series(frames, method=METHOD, deep_options=options)):
        with pytest.raises(RegistrationError, match='Para 1 → 2.*Deep Matcher.*NaN/Inf'):
            operation()
    assert control.loaded == 0 and control.calls == 0
    assert np.isnan(frames[1].data[8, 11])


def test_ecc_library_receives_deep_translation_on_original_sized_frames(controlled_loftr, monkeypatch):
    import cv2

    control, weights = controlled_loftr
    control.shifts = [(-18, 12)]
    original_ecc = cv2.findTransformECC
    calls = []

    def inspect(reference, moving, warp, motion, criteria, mask, gaussian_filter_size):
        calls.append(warp.copy())
        assert reference.shape == moving.shape == (128, 192)
        assert motion == cv2.MOTION_TRANSLATION
        assert criteria == (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 1e-6)
        assert mask is None and gaussian_filter_size == 5
        np.testing.assert_array_equal(warp, [[1, 0, 18], [0, 1, -12]])
        return original_ecc(reference, moving, warp, motion, criteria, mask, gaussian_filter_size)

    monkeypatch.setattr(cv2, 'findTransformECC', inspect)
    trial = estimate_pair(*textured_pair((-17.6, 11.25)), method=METHOD,
                          deep_options=DeepMatcherOptions(weights, 'cpu'))
    np.testing.assert_allclose(trial.shift_xy, (-17.6, 11.25), atol=0.12)
    assert len(calls) == 1
    np.testing.assert_allclose(trial.hybrid.correction_xy, (0.4, -0.75), atol=0.12)


def test_high_ecc_score_preserves_weak_deep_diagnostic(controlled_loftr):
    control, weights = controlled_loftr
    control.weak = True
    trial = estimate_pair(*textured_pair(), method=METHOD,
                          deep_options=DeepMatcherOptions(weights, 'cpu'))
    assert trial.hybrid.deep_status == 'low_confidence'
    assert trial.hybrid.ecc_status == 'ok' and trial.hybrid.ecc_score > 0.9
    assert trial.status == 'manual_review' and trial.quality_score is None


def test_deep_failure_never_runs_ecc_or_returns_hybrid(controlled_loftr, monkeypatch):
    import cv2
    import pytest
    from stmviewer.registration import RegistrationError, register_series

    control, weights = controlled_loftr
    control.error = 'controlled missing matches'
    monkeypatch.setattr(cv2, 'findTransformECC', lambda *args: pytest.fail('ECC ran after Deep failure'))
    options = DeepMatcherOptions(weights, 'cpu')
    frames = textured_pair()
    for operation in (lambda: estimate_pair(*frames, method=METHOD, deep_options=options),
                      lambda: register_series(frames, method=METHOD, deep_options=options)):
        with pytest.raises(RegistrationError, match='Para 1 → 2.*Deep Matcher.*controlled missing matches'):
            operation()


def test_ecc_failure_discards_valid_deep_instead_of_substituting_it(controlled_loftr, monkeypatch):
    import cv2
    import pytest
    from stmviewer.registration import RegistrationError, register_series

    _, weights = controlled_loftr
    def fail(*args):
        raise cv2.error('controlled nonconvergence')
    monkeypatch.setattr(cv2, 'findTransformECC', fail)
    options = DeepMatcherOptions(weights, 'cpu')
    frames = textured_pair()
    for operation in (lambda: estimate_pair(*frames, method=METHOD, deep_options=options),
                      lambda: register_series(frames, method=METHOD, deep_options=options)):
        with pytest.raises(RegistrationError, match='Para 1 → 2.*ECC.*controlled nonconvergence'):
            operation()


def test_invalid_ecc_translation_is_not_published(controlled_loftr, monkeypatch):
    import cv2
    import pytest
    from stmviewer.registration import RegistrationError

    _, weights = controlled_loftr
    monkeypatch.setattr(cv2, 'findTransformECC', lambda *args: (1, np.array([[1, 0, np.inf], [0, 1, 0]])))
    with pytest.raises(RegistrationError, match='Para 1 → 2.*ECC.*invalid translation'):
        estimate_pair(*textured_pair(), method=METHOD, deep_options=DeepMatcherOptions(weights, 'cpu'))


def test_missing_ecc_library_is_explicit_before_loading_model(controlled_loftr, monkeypatch):
    import builtins
    import pytest
    from stmviewer.deep_ecc import hybrid_unavailable_reason
    from stmviewer.registration import RegistrationError

    control, weights = controlled_loftr
    original_import = builtins.__import__
    def without_cv2(name, *args, **kwargs):
        if name == 'cv2':
            raise ImportError('controlled missing OpenCV')
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', without_cv2)
    options = DeepMatcherOptions(weights, 'cpu')
    assert 'ECC' in hybrid_unavailable_reason(options)
    with pytest.raises(RegistrationError, match='ECC.*controlled missing OpenCV'):
        estimate_pair(*textured_pair(), method=METHOD, deep_options=options)
    assert control.loaded == 0


def test_cancellation_between_stages_and_after_ecc_discards_attempt(controlled_loftr, monkeypatch):
    import cv2
    import pytest
    from threading import Event
    from stmviewer.registration import RegistrationCancelled, register_series

    control, weights = controlled_loftr
    options = DeepMatcherOptions(weights, 'cpu')
    frames = textured_pair()
    original_ecc = cv2.findTransformECC
    for stop_stage in ('Deep Matcher (CPU)', 'ECC (CPU)', 'after ECC'):
        for series in (False, True):
            cancelled = Event()
            calls = []
            control.calls = 0
            def progress(*args):
                if stop_stage in args[-1]:
                    cancelled.set()
            def ecc(*args):
                calls.append(True)
                result = original_ecc(*args)
                if stop_stage == 'after ECC':
                    cancelled.set()
                return result
            monkeypatch.setattr(cv2, 'findTransformECC', ecc)
            with pytest.raises(RegistrationCancelled):
                if series:
                    register_series(frames, method=METHOD, deep_options=options,
                                    progress=progress, cancelled=cancelled.is_set)
                else:
                    estimate_pair(*frames, method=METHOD, deep_options=options,
                                  progress=progress, cancelled=cancelled.is_set)
            assert control.calls == (0 if stop_stage == 'Deep Matcher (CPU)' else 1)
            assert len(calls) == (1 if stop_stage == 'after ECC' else 0)


def test_selected_pair_errors_identify_source_frames_instead_of_first_pair(controlled_loftr):
    from dataclasses import replace
    import pytest
    from stmviewer.registration import RegistrationError

    control, weights = controlled_loftr
    control.error = 'controlled missing matches'
    reference, moving = textured_pair()
    reference = replace(reference, source_frame_index=30)
    moving = replace(moving, source_frame_index=31)
    with pytest.raises(RegistrationError, match='Para 31 → 32.*źródłowe.*Deep Matcher'):
        estimate_pair(reference, moving, method=METHOD, deep_options=DeepMatcherOptions(weights, 'cpu'))


def test_ecc_texture_refusal_keeps_pair_identity_and_stage(controlled_loftr):
    from dataclasses import replace
    import pytest
    from stmviewer.registration import RegistrationError, register_series

    _, weights = controlled_loftr
    reference, moving = textured_pair()
    reference = replace(reference, data=np.ones((128, 192)), source_frame_index=30)
    moving = replace(moving, data=np.ones((128, 192)), source_frame_index=31)
    options = DeepMatcherOptions(weights, 'cpu')
    with pytest.raises(RegistrationError, match='Para 31 → 32.*źródłowe.*— ECC:.*too little texture'):
        estimate_pair(reference, moving, method=METHOD, deep_options=options)
    with pytest.raises(RegistrationError, match='Para 1 → 2.*— ECC:.*too little texture'):
        register_series((reference, moving), method=METHOD, deep_options=options)
