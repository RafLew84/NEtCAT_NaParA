"""Cancellation retains evidence returned by native calls and finished local patches."""

from threading import Event

import numpy as np
import pytest

from deep_ecc_fixture import controlled_loftr as model_fixture, textured_pair
from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.pair_comparison import estimate_pair
from stmviewer.registration import RegistrationCancelled
from stmviewer.trial_capture import AttemptCapture

controlled_loftr = model_fixture


def test_cancellation_during_deep_preserves_valid_returned_start(controlled_loftr, monkeypatch):
    import kornia.feature
    _, weights = controlled_loftr
    frames = textured_pair()
    stop = Event()
    original = kornia.feature.LoFTR.forward

    def finishing(self, images):
        result = original(self, images)
        stop.set()
        return result

    monkeypatch.setattr(kornia.feature.LoFTR, 'forward', finishing)
    capture = AttemptCapture(frames, 'deep_matcher_ecc', kind='pair')
    with pytest.raises(RegistrationCancelled):
        estimate_pair(*frames, method='deep_matcher_ecc', capture=capture,
                      deep_options=DeepMatcherOptions(weights, 'cpu'), cancelled=stop.is_set)
    record = capture.payload['records'][0]
    assert capture.payload['outcome'] == 'cancelled'
    assert record['hybrid']['deep_shift_xy'] == [19.0, -12.0]
    assert record['hybrid']['final_shift_xy'] is None
    assert record['shift_xy'] is None


def test_cancellation_during_ecc_preserves_final_estimate_as_cancelled_diagnostic(controlled_loftr, monkeypatch):
    import cv2
    _, weights = controlled_loftr
    frames = textured_pair()
    stop = Event()
    original = cv2.findTransformECC

    def finishing(*args):
        result = original(*args)
        stop.set()
        return result

    monkeypatch.setattr(cv2, 'findTransformECC', finishing)
    capture = AttemptCapture(frames, 'deep_matcher_ecc', kind='pair')
    with pytest.raises(RegistrationCancelled):
        estimate_pair(*frames, method='deep_matcher_ecc', capture=capture,
                      deep_options=DeepMatcherOptions(weights, 'cpu'), cancelled=stop.is_set)
    record = capture.payload['records'][0]
    assert capture.payload['outcome'] == 'cancelled'
    np.testing.assert_allclose(record['hybrid']['final_shift_xy'], [18.25, -12.5], atol=0.12)
    assert record['shift_xy'] == record['hybrid']['final_shift_xy']
    assert record['hybrid']['deep_shift_xy'] == [19.0, -12.0]


def test_cancellation_during_local_deep_preserves_start_without_patches(controlled_loftr, monkeypatch):
    import kornia.feature
    _, weights = controlled_loftr
    frames = textured_pair()
    stop = Event()
    original = kornia.feature.LoFTR.forward

    def finishing(self, images):
        result = original(self, images)
        stop.set()
        return result

    monkeypatch.setattr(kornia.feature.LoFTR, 'forward', finishing)
    capture = AttemptCapture(frames, 'deep_local_consensus', kind='pair')
    with pytest.raises(RegistrationCancelled):
        estimate_pair(*frames, method='deep_local_consensus', capture=capture,
                      deep_options=DeepMatcherOptions(weights, 'cpu'), cancelled=stop.is_set)
    record = capture.payload['records'][0]
    assert record['local']['deep_shift_xy'] == [19.0, -12.0]
    assert record['local']['patches'] == []
    assert record['local']['final_shift_xy'] is None
    assert 'Anulowano' in record['local']['reason']
    assert capture.payload['outcome'] == 'cancelled'


def test_cancellation_after_three_patches_retains_only_measured_evidence(controlled_loftr, tmp_path):
    from stmviewer.trial_document import save_trial, load_trial
    _, weights = controlled_loftr
    frames = textured_pair()
    stop = Event()

    def progress(text):
        if 'Fragmenty: 3/16' in text:
            stop.set()

    capture = AttemptCapture(frames, 'deep_local_consensus', kind='pair')
    with pytest.raises(RegistrationCancelled):
        estimate_pair(*frames, method='deep_local_consensus', capture=capture,
                      deep_options=DeepMatcherOptions(weights, 'cpu'),
                      cancelled=stop.is_set, progress=progress)
    record = capture.payload['records'][0]
    assert capture.payload['outcome'] == 'cancelled'
    assert record['shift_xy'] is None
    local = record['local']
    assert local['deep_shift_xy'] == [19.0, -12.0]
    assert len(local['patches']) == 3
    assert local['final_shift_xy'] is None and local['status'] == 'failed'
    assert any(patch['shift_xy'] is not None for patch in local['patches'])
    assert all(patch['status'] == 'unmatched' for patch in local['patches'])
    assert 'Anulowano' in local['reason']
    saved = tmp_path / 'cancelled-local.stmtrial.json'
    save_trial(saved, capture.document, frames)
    reopened = load_trial(saved, frames)
    assert reopened.payload['records'][0]['local'] == local
