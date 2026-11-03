"""AKAZE's public image-to-translation contract, using real OpenCV."""
import numpy as np
import pytest
from scipy.ndimage import gaussian_filter

from stmviewer.akaze_matcher import AkazeBackend
from stmviewer.correspondence_types import CorrespondenceRefusal


def texture(shape=(192, 288)):
    rng = np.random.default_rng(1401)
    return gaussian_filter(rng.normal(size=shape), 1.0)


def test_real_akaze_recovers_known_xy_on_nonsquare_original():
    original = texture()
    moving = np.roll(original, (-5, 7), axis=(0, 1))
    backend = AkazeBackend()
    try:
        result = backend.estimate(original, moving, moving_frame_index=1)
        np.testing.assert_allclose(result.shift_xy, (-7, 5), atol=0.3)
        assert result.method == 'akaze'
        assert backend.device == 'CPU'
        detail = backend.last_diagnostics
        assert detail is not None
        assert detail.inlier_count >= 8
        assert detail.preparation[0].original_shape == (192, 288)
        assert detail.preparation[0].model_shape == (192, 288)
        assert detail.preparation[0].scale_xy == (1., 1.)
        assert dict(detail.model_provenance)['matcher'] == 'BFMatcher; NORM_HAMMING; crossCheck=True'
    finally:
        backend.close()


@pytest.mark.parametrize('shape', [(1, 1), (192, 288)])
def test_constant_input_refuses_locally_and_task_can_process_next_pair(shape):
    backend = AkazeBackend()
    try:
        with pytest.raises(CorrespondenceRefusal) as caught:
            backend.estimate(np.ones(shape), np.ones(shape), moving_frame_index=1)
        assert caught.value.diagnostics.final_shift_xy is None
        assert caught.value.diagnostics.valid_count == 0
        assert caught.value.diagnostics.preparation[0].value_range == (1., 1.)
        image = texture()
        result = backend.estimate(image, np.roll(image, 3, axis=1), moving_frame_index=2)
        np.testing.assert_allclose(result.shift_xy, (-3, 0), atol=0.3)
    finally:
        backend.close()

def test_binary_mldb_and_mutual_hamming_are_used_at_opencv_boundary(monkeypatch):
    import cv2
    factory, matcher_factory = cv2.AKAZE_create, cv2.BFMatcher
    observed = {}

    def detector(*args, **kwargs):
        observed['detector'] = kwargs
        return factory(*args, **kwargs)

    class Matcher:
        def __init__(self, norm, *, crossCheck):
            observed['matcher'] = (norm, crossCheck)
            self.delegate = matcher_factory(norm, crossCheck=crossCheck)

        def match(self, a, b):
            assert a.dtype == b.dtype == np.uint8
            forward = self.delegate.match(a, b)
            reverse = self.delegate.match(b, a)
            assert {(m.queryIdx, m.trainIdx) for m in forward} == {(m.trainIdx, m.queryIdx) for m in reverse}
            observed['matched'] = len(forward)
            return forward

    monkeypatch.setattr(cv2, 'AKAZE_create', detector)
    monkeypatch.setattr(cv2, 'BFMatcher', Matcher)
    backend = AkazeBackend()
    try:
        base = texture()
        backend.estimate(base, np.roll(base, 7, 1), moving_frame_index=1)
        assert observed['detector']['descriptor_type'] == cv2.AKAZE_DESCRIPTOR_MLDB
        assert observed['matcher'] == (cv2.NORM_HAMMING, True)
        assert observed['matched'] >= 8
    finally:
        backend.close()



@pytest.mark.parametrize('shape', [(1, 64), (64, 1)])
def test_single_line_nonconstant_image_is_a_local_refusal(shape):
    original = np.arange(64, dtype=float).reshape(shape)
    backend = AkazeBackend()
    try:
        with pytest.raises(CorrespondenceRefusal) as caught:
            backend.estimate(original, original.copy(), moving_frame_index=1)
        assert caught.value.diagnostics.valid_count == 0
        assert caught.value.diagnostics.preparation[0].original_shape == shape
        image = texture()
        result = backend.estimate(image, np.roll(image, 3, axis=1), moving_frame_index=2)
        np.testing.assert_allclose(result.shift_xy, (-3, 0), atol=0.3)
    finally:
        backend.close()
