from pathlib import Path

import numpy as np
import pytest

from stmviewer.lightglue_matcher import LightGlueBackend


class PointEngine:
    last_metrics = {'inference_s': 0.1}

    def __init__(self):
        self.closed = False

    def match(self, reference, moving):
        assert reference.dtype == np.float32
        assert reference.shape == (73, 109)
        assert moving.shape == (73, 109)
        assert 0 <= reference.min() <= reference.max() <= 1
        points = np.array([(x, y) for y in (10, 30, 50, 65) for x in (12, 40, 70, 95)], dtype=float)
        return points, points + (7, -5)

    def close(self):
        self.closed = True


def test_original_pixel_correspondences_are_not_scaled_twice():
    backend = LightGlueBackend(PointEngine(), device='CPU', provenance=())
    image = np.arange(73 * 109, dtype=float).reshape(73, 109)
    result = backend.estimate(image, image, moving_frame_index=1)
    assert result.shift_xy == (-7., 5.)
    assert backend.last_diagnostics.preparation[0].model_shape == (73, 109)
    assert backend.last_metrics == {'inference_s': 0.1}
    backend.close()


def test_both_checkpoint_paths_are_required_without_importing_vendor_code(tmp_path):
    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.lightglue_matcher import lightglue_unavailable_reason
    source = tmp_path / 'source'
    (source / 'lightglue').mkdir(parents=True)
    for name in ('lightglue.py', 'superpoint.py'):
        (source / 'lightglue' / name).write_text('raise AssertionError("do not execute")\n')
    matcher = tmp_path / 'matcher.pth'
    matcher.write_bytes(b'bad')
    options = DeepMatcherOptions(matcher, 'cpu', source)
    assert 'SuperPoint' in lightglue_unavailable_reason(options)


def test_local_refusal_keeps_model_available_for_another_graph_edge():
    from stmviewer.correspondence_types import CorrespondenceRefusal
    class EmptyEngine(PointEngine):
        empty = True
        def match(self, reference, moving):
            if self.empty:
                self.empty = False
                return np.empty((0, 2)), np.empty((0, 2))
            return super().match(reference, moving)
    engine = EmptyEngine()
    backend = LightGlueBackend(engine, device='CPU', provenance=(('model', 'LightGlue + SuperPoint'),))
    image = np.arange(73 * 109, dtype=float).reshape(73, 109)
    with pytest.raises(CorrespondenceRefusal):
        backend.estimate(image, image, moving_frame_index=1)
    assert backend.last_diagnostics.final_shift_xy is None
    assert not engine.closed
    assert backend.estimate(image, image, moving_frame_index=2).shift_xy == (-7., 5.)
    backend.close()


def test_cuda_oom_is_a_system_failure_closes_engine_and_clears_previous_evidence():
    from stmviewer.registration import RegistrationError
    class FailingEngine(PointEngine):
        fail = False
        def match(self, reference, moving):
            if self.fail:
                raise RuntimeError('CUDA out of memory')
            return super().match(reference, moving)
    engine = FailingEngine()
    backend = LightGlueBackend(engine, device='CUDA:0 — test', provenance=())
    image = np.arange(73 * 109, dtype=float).reshape(73, 109)
    backend.estimate(image, image, moving_frame_index=1)
    engine.fail = True
    with pytest.raises(RegistrationError, match='CUDA out of memory'):
        backend.estimate(image, image, moving_frame_index=2)
    assert engine.closed and backend.last_diagnostics is None


def test_cancellation_before_matching_releases_model():
    from stmviewer.registration import RegistrationCancelled
    engine = PointEngine()
    backend = LightGlueBackend(engine, device='CPU', provenance=(), cancelled=lambda: True)
    image = np.ones((73, 109))
    with pytest.raises(RegistrationCancelled):
        backend.estimate(image, image, moving_frame_index=1)
    assert engine.closed


@pytest.mark.parametrize('invalid', [np.array([[np.nan] * 16] * 16), np.ones((7, 19))])
def test_invalid_measurement_pixels_are_not_treated_as_features(invalid):
    from stmviewer.registration import RegistrationError
    engine = PointEngine()
    backend = LightGlueBackend(engine, device='CPU', provenance=())
    with pytest.raises(RegistrationError, match='8×8 bez NaN/Inf'):
        backend.estimate(invalid, invalid, moving_frame_index=1)
    assert engine.closed


def test_unverified_source_is_rejected_before_execution(tmp_path):
    from stmviewer.deep_matcher import DeepMatcherOptions
    from stmviewer.lightglue_matcher import load_lightglue_backend
    from stmviewer.lightglue_resources import MATCHER_BYTES, EXTRACTOR_BYTES
    from stmviewer.registration import RegistrationError
    source = tmp_path / 'source'
    (source / 'lightglue').mkdir(parents=True)
    for name in ('lightglue.py', 'superpoint.py'):
        (source / 'lightglue' / name).write_text('raise AssertionError("unverified code executed")\n')
    weights, extractor = tmp_path / 'matcher.pth', tmp_path / 'extractor.pth'
    for path, size in ((weights, MATCHER_BYTES), (extractor, EXTRACTOR_BYTES)):
        with path.open('wb') as stream:
            stream.truncate(size)
    with pytest.raises(RegistrationError, match='Niezgodny kod LightGlue'):
        load_lightglue_backend(DeepMatcherOptions(weights, 'cpu', source, extractor_weights=extractor))
