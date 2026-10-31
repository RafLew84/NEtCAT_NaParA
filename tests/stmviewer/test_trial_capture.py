"""Observable registration attempts preserve computed evidence without pixels."""
import json
from threading import Event

import numpy as np
import pytest

from deep_ecc_fixture import controlled_loftr as model_fixture, textured_pair
from make_registration_fixtures import frames_with_data
from stmviewer.registration import RegistrationCancelled, RegistrationError, register_series
from stmviewer.trial_capture import AttemptCapture, from_registration, pair_from_document


controlled_loftr = model_fixture


def test_failed_series_retains_successful_pair_and_no_invented_missing_xy():
    first = np.random.default_rng(51).normal(size=(32, 48))
    frames = frames_with_data(first, np.roll(first, (2, -3), (0, 1)), np.ones_like(first))
    capture = AttemptCapture(frames, 'phase_correlation')
    with pytest.raises(RegistrationError):
        register_series(frames, capture=capture)
    payload = capture.payload
    assert payload['outcome'] == 'failed'
    assert payload['records'][1]['shift_xy'] == [3.0, -2.0]
    assert payload['records'][1]['cumulative_xy'] == [3.0, -2.0]
    assert payload['records'][2]['shift_xy'] is None
    assert payload['records'][2]['cumulative_xy'] is None
    assert payload['error']
    assert 'upsample_factor' in payload['settings']['config']
    json.dumps(payload, allow_nan=False)


def test_complete_snapshot_and_reopened_pair_keep_exact_scalar_settings():
    first = np.random.default_rng(15).normal(size=(32, 48))
    frames = frames_with_data(first, np.roll(first, (2, -3), (0, 1)))
    capture = AttemptCapture(frames, 'phase_correlation')
    result = register_series(frames, capture=capture)
    document = from_registration(result)
    assert capture.payload == document.payload
    assert document.payload['outcome'] == 'complete'
    assert document.payload['records'][1]['cumulative_xy'] == [3.0, -2.0]
    reopened = pair_from_document(document, frames, 1)
    assert reopened.shift_xy == (3.0, -2.0)
    assert reopened.settings['config']['upsample_factor'] == 20
    assert reopened.hybrid is None and reopened.local is None
    assert document.payload['manual_movie'] is None
    json.dumps(document.payload, allow_nan=False)


def test_cancelled_render_preserves_computed_xy_without_becoming_complete():
    image = np.random.default_rng(15).normal(size=(32, 48))
    frames = frames_with_data(image, np.roll(image, (2, -3), (0, 1)))
    capture = AttemptCapture(frames, 'phase_correlation')
    stop = Event()
    with pytest.raises(RegistrationCancelled):
        register_series(frames, capture=capture, cancelled=stop.is_set,
                        progress=lambda done, total, text: stop.set() if done == 3 else None)
    assert capture.payload['outcome'] == 'cancelled'
    assert capture.payload['records'][1]['cumulative_xy'] == [3.0, -2.0]
    assert capture.payload['error'] == 'Anulowano próbę.'


def test_manual_pair_reopens_without_backend_quality_or_movie_promotion():
    from stmviewer.manual_pair import ManualPairDraft
    from stmviewer.pair_comparison import estimate_pair
    from stmviewer.trial_capture import from_pair
    image = np.random.default_rng(15).normal(size=(32, 48))
    frames = frames_with_data(image, np.roll(image, (2, -3), (0, 1)))
    start = estimate_pair(*frames)
    draft = ManualPairDraft(*frames, start=start)
    draft.nudge(1, 0)
    approved = draft.apply()
    document = from_pair(approved, frames)
    reopened = pair_from_document(document, frames)
    assert reopened.shift_xy == (4.0, -2.0)
    assert reopened.manual.start_xy == (3.0, -2.0)
    assert reopened.manual.correction_xy == (1, 0)
    assert reopened.manual.source_label == approved.manual.source_label
    assert reopened.quality_score is None and reopened.status == 'manual'
    assert reopened.movie_revision is None
    assert document.payload['kind'] == 'pair'


def test_two_applied_manual_corrections_preserve_baseline_and_full_settings():
    from stmviewer.manual_movie import apply_movie_correction, movie_pair_trial
    from stmviewer.manual_pair import ManualPairDraft
    image = np.random.default_rng(15).normal(size=(32, 48))
    frames = frames_with_data(image, np.roll(image, (2, -3), (0, 1)), np.roll(image, (1, 2), (0, 1)))
    automatic = register_series(frames)
    result = automatic
    for index, nudge in [(1, (1, 0)), (2, (0, -1))]:
        draft = ManualPairDraft(frames[index - 1], frames[index], movie_pair_trial(result, index))
        draft.nudge(*nudge)
        result = apply_movie_correction(result, draft.apply())
    document = from_registration(result)
    assert document.payload['settings'] == from_registration(automatic).payload['settings']
    assert document.payload['records'][2]['cumulative_xy'] == [-1.0, -2.0]
    assert len(document.payload['manual_movie']['corrections']) == 2
    assert document.payload['manual_movie']['baseline'][2]['shift_xy'] == [-2.0, -1.0]
    reopened = pair_from_document(document, frames, 2)
    assert reopened.shift_xy == (-5.0, 0.0)
    assert reopened.manual.correction_xy == (0, -1)
    assert reopened.quality_score is None


def test_ecc_failure_records_exact_deep_start_without_complete_pair(controlled_loftr, monkeypatch):
    import cv2
    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.pair_comparison import estimate_pair
    control, weights = controlled_loftr
    frames = textured_pair()
    capture = AttemptCapture(frames, 'deep_matcher_ecc', kind='pair')

    def refusal(*args):
        raise cv2.error('controlled ECC refusal')

    monkeypatch.setattr(cv2, 'findTransformECC', refusal)
    with pytest.raises(RegistrationError, match='ECC'):
        estimate_pair(*frames, method='deep_matcher_ecc',
                      deep_options=DeepMatcherOptions(weights, 'cpu'), capture=capture)
    payload = capture.payload
    assert payload['outcome'] == 'failed'
    record = payload['records'][0]
    assert record['shift_xy'] is None and record['cumulative_xy'] is None
    assert record['hybrid']['stage'] == 'ECC'
    assert record['hybrid']['deep_shift_xy'] == [19.0, -12.0]
    assert record['hybrid']['final_shift_xy'] is None
    assert payload['settings']['ecc']['max_iterations'] == 100
    assert payload['settings']['deep']['min_matches'] > 0
    with pytest.raises(ValueError, match='Brak zatwierdzonego'):
        pair_from_document(capture.document, frames)
    json.dumps(payload, allow_nan=False)


def test_deep_failure_never_records_invented_initial_shift(controlled_loftr):
    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.pair_comparison import estimate_pair
    control, weights = controlled_loftr
    control.error = 'controlled Deep refusal'
    frames = textured_pair()
    capture = AttemptCapture(frames, 'deep_matcher_ecc', kind='pair')
    with pytest.raises(RegistrationError, match='Deep Matcher'):
        estimate_pair(*frames, method='deep_matcher_ecc',
                      deep_options=DeepMatcherOptions(weights, 'cpu'), capture=capture)
    record = capture.payload['records'][0]
    assert record['hybrid']['stage'] == 'Deep Matcher'
    assert record['hybrid']['deep_shift_xy'] is None
    assert record['hybrid']['deep_quality_score'] is None
    assert record['shift_xy'] is None


def test_saved_ecc_refusal_can_preview_start_but_never_complete_hybrid(controlled_loftr, monkeypatch):
    import cv2
    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.pair_comparison import estimate_pair
    from stmviewer.trial_capture import diagnostic_start_from_document
    _, weights = controlled_loftr
    frames = textured_pair()
    capture = AttemptCapture(frames, 'deep_matcher_ecc', kind='pair')

    def refusal(*args):
        raise cv2.error('controlled ECC refusal')

    monkeypatch.setattr(cv2, 'findTransformECC', refusal)
    with pytest.raises(RegistrationError):
        estimate_pair(*frames, method='deep_matcher_ecc',
                      deep_options=DeepMatcherOptions(weights, 'cpu'), capture=capture)
    start = diagnostic_start_from_document(capture.document, frames)
    assert start.shift_xy == (19.0, -12.0)
    assert start.method == 'deep_matcher_translation'
    assert start.quality_score is None and start.status == 'manual_review'
    assert 'Start Deep' in start.label and 'ECC' in start.label
    assert start.hybrid is None
    assert capture.document.payload['outcome'] == 'failed'


def test_deleting_neighbor_keeps_history_but_does_not_reassign_manual_pair():
    from stmviewer.manual_movie import apply_movie_correction, movie_pair_trial
    from stmviewer.manual_pair import ManualPairDraft
    image = np.random.default_rng(19).normal(size=(32, 48))
    frames = frames_with_data(image, np.roll(image, (2, -3), (0, 1)), np.roll(image, (1, 2), (0, 1)))
    result = register_series(frames)
    draft = ManualPairDraft(frames[1], frames[2], movie_pair_trial(result, 2))
    draft.nudge(1, 0)
    corrected = apply_movie_correction(result, draft.apply())
    surviving = corrected.without_frame(1)
    document = from_registration(surviving)
    assert len(document.payload['manual_movie']['corrections']) == 1
    assert document.payload['records'][1]['manual'] is None
    assert document.payload['records'][1]['cumulative_xy'] == [-1.0, -1.0]
    pair = pair_from_document(document, (frames[0], frames[2]), 1)
    assert pair.shift_xy == (-1.0, -1.0)
    assert pair.manual is None


def test_full_trial_preserves_pair_quality_separately_from_cumulative_uncertainty():
    from nanotrack.core import RegistrationFrameResult
    from stmviewer.manual_movie import apply_movie_correction, movie_pair_trial
    from stmviewer.manual_pair import ManualPairDraft

    class MeasuredPairs:
        def estimate(self, reference_frame, moving_frame, *, moving_frame_index):
            return RegistrationFrameResult(
                moving_frame_index, (1.0, 0.0), 'controlled',
                quality_score=0.2 if moving_frame_index == 1 else 0.9,
                status='low_confidence' if moving_frame_index == 1 else 'ok',
            )

    image = np.arange(32 * 48, dtype=np.float64).reshape(32, 48)
    frames = frames_with_data(image, image, image)
    capture = AttemptCapture(frames, 'phase_correlation')
    result = register_series(frames, backend=MeasuredPairs(), capture=capture)
    row = capture.payload['records'][2]
    assert row['quality_score'] == 0.2 and row['status'] == 'low_confidence'
    assert row['pair_quality_score'] == 0.9 and row['pair_status'] == 'ok'
    reopened = pair_from_document(capture.document, frames, 2)
    assert reopened.quality_score == 0.9 and reopened.status == 'ok'

    draft = ManualPairDraft(frames[0], frames[1], movie_pair_trial(result, 1))
    draft.nudge(1, 0)
    corrected = from_registration(apply_movie_correction(result, draft.apply()))
    manual = pair_from_document(corrected, frames, 1)
    untouched = pair_from_document(corrected, frames, 2)
    assert manual.quality_score is None and manual.status == 'manual'
    assert untouched.quality_score == 0.9 and untouched.status == 'ok'
    assert corrected.payload['records'][2]['quality_score'] is None
