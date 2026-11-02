"""Opt-in smoke tests with both pinned local checkpoints (separate from GUI acceptance)."""
from dataclasses import replace
import os
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.skipif(not os.environ.get('STMVIEWER_TEST_LIGHTGLUE_ROOT'),
                               reason='Requires explicitly prepared local LightGlue resources')


def options(device='cpu'):
    from stmviewer.lightglue_matcher import default_lightglue_options
    root = Path(os.environ['STMVIEWER_TEST_LIGHTGLUE_ROOT'])
    return replace(default_lightglue_options(), source=root/'source',
                   weights=root/'weights/superpoint_lightglue.pth',
                   extractor_weights=root/'weights/superpoint_v1.pth', device=device)


def images(shape=(137, 219)):
    import cv2
    rng = np.random.default_rng(20261102)
    image = cv2.GaussianBlur(rng.normal(0, 1, shape), (0, 0), 1.2)
    for _ in range(45):
        x, y = int(rng.integers(15, shape[1]-15)), int(rng.integers(15, shape[0]-15))
        cv2.circle(image, (x, y), int(rng.integers(3, 10)), float(rng.uniform(-1, 1)), -1)
    moving = cv2.warpAffine(image, np.array([[1, 0, 7], [0, 1, -5]], np.float32), (shape[1], shape[0]))
    return image, moving


@pytest.mark.parametrize('device', ['cpu', 'cuda'])
def test_real_local_model_reuses_worker_and_recovers_original_pixel_xy(device):
    import torch
    from stmviewer.lightglue_matcher import load_lightglue_backend
    if device == 'cuda' and not torch.cuda.is_available():
        pytest.skip('CUDA unavailable')
    # Worker isolation must not alter parent Torch settings or online loaders.
    original_determinism = torch.backends.cudnn.deterministic
    original_loader = torch.hub.load_state_dict_from_url
    backend = load_lightglue_backend(options(device))
    try:
        reference, moving = images()
        forward = backend.estimate(reference, moving, moving_frame_index=1)
        reverse = backend.estimate(moving, reference, moving_frame_index=2)
        np.testing.assert_allclose(forward.shift_xy, (-7, 5), atol=1.)
        np.testing.assert_allclose(reverse.shift_xy, (7, -5), atol=1.)
        assert backend.last_diagnostics.preparation[0].model_shape == reference.shape
        assert backend.last_metrics['matching_s'] > 0
        assert backend.device.startswith(device.upper())
        assert dict(backend.provenance)['extractor_weights_variant'] == 'superpoint_v1.pth'
    finally:
        backend.close()
    assert torch.backends.cudnn.deterministic == original_determinism
    assert torch.hub.load_state_dict_from_url is original_loader


def test_real_featureless_frame_refuses_without_discarding_loaded_model():
    from stmviewer.correspondence_types import CorrespondenceRefusal
    from stmviewer.lightglue_matcher import load_lightglue_backend
    backend = load_lightglue_backend(options('cpu'))
    try:
        with pytest.raises(CorrespondenceRefusal):
            backend.estimate(np.ones((137, 219)), np.ones((137, 219)), moving_frame_index=1)
        assert backend.last_diagnostics.final_shift_xy is None
        assert backend.last_diagnostics.preparation[0].value_range == (1., 1.)
        reference, moving = images((256, 256))
        result = backend.estimate(reference, moving, moving_frame_index=2)
        np.testing.assert_allclose(result.shift_xy, (-7, 5), atol=1.)
        assert backend.last_diagnostics.preparation[0].original_shape == (256, 256)
    finally:
        backend.close()


@pytest.mark.parametrize('component', ['extractor', 'matcher'])
def test_corrupt_checkpoint_is_rejected_before_loading(component, tmp_path):
    from stmviewer.lightglue_matcher import load_lightglue_backend
    from stmviewer.registration import RegistrationError
    original = options('cpu')
    valid = original.weights if component == 'matcher' else original.extractor_weights
    corrupt = tmp_path / valid.name
    content = bytearray(valid.read_bytes())
    content[-1] ^= 1
    corrupt.write_bytes(content)
    altered = replace(original, **({'weights': corrupt} if component == 'matcher'
                                   else {'extractor_weights': corrupt}))
    label = 'LightGlue' if component == 'matcher' else 'SuperPoint'
    with pytest.raises(RegistrationError, match='SHA-256 wag ' + label):
        load_lightglue_backend(altered)


def test_changed_profile_reaches_real_worker_and_retains_known_xy():
    from stmviewer.lightglue_matcher import load_lightglue_backend
    from stmviewer.method_parameters import LightGlueParameters, ContrastParameters
    from stmviewer.feature_provenance import recorded_profile
    parameters = LightGlueParameters(detection_threshold=.001, nms_radius=2,
        max_keypoints=1024, filter_threshold=.05, full_computation=True, radius=1.5,
        contrast=ContrastParameters(mode='percentiles'))
    backend = load_lightglue_backend(options('cpu'), parameters=parameters)
    try:
        reference, moving = images()
        result = backend.estimate(reference, moving, moving_frame_index=1)
        np.testing.assert_allclose(result.shift_xy, (-7, 5), atol=1.)
        assert recorded_profile('lightglue_superpoint', backend.provenance) == parameters
        metadata = dict(backend.provenance)
        assert 'nms_radius=2' in metadata['extractor_config']
        assert 'depth_confidence=-1' in metadata['model_config']
        assert metadata['max_keypoints'] == '1024'
        assert 'inlier_radius=1.5' in backend.last_diagnostics.settings_text
        assert backend.last_diagnostics.preparation[0].normalization == 'percentiles-float32-v1'
    finally:
        backend.close()
