"""Public configuration and estimator-input contracts for REG-15."""
from dataclasses import replace

import numpy as np
import pytest

from stmviewer.method_parameters import ContrastParameters
from stmviewer.feature_preparation import prepare_feature_image


def test_percentiles_clip_outliers_without_changing_original_pixels():
    original = np.arange(101, dtype=np.float64).reshape(1, 101)
    original.setflags(write=False)
    prepared, evidence = prepare_feature_image(
        original, ContrastParameters(mode='percentiles', lower=10, upper=90), uint8=True)
    assert prepared.shape == original.shape
    np.testing.assert_array_equal(prepared[0, [0, 10, 50, 90, 100]], [0, 0, 128, 255, 255])
    np.testing.assert_array_equal(original, np.arange(101).reshape(1, 101))
    assert evidence.value_range == (10., 90.)
    assert evidence.scale_xy == (1., 1.)


def test_clahe_uses_same_quantized_contrast_for_both_feature_methods():
    import cv2
    original = np.tile(np.arange(16, dtype=np.float64), (16, 1))
    expected = cv2.createCLAHE(clipLimit=2., tileGridSize=(2, 2)).apply(
        np.tile(np.arange(16, dtype=np.uint8) * 17, (16, 1)))
    contrast = ContrastParameters(mode='clahe', grid_x=2, grid_y=2)
    byte_image, _ = prepare_feature_image(original, contrast, uint8=True)
    float_image, _ = prepare_feature_image(original, contrast, uint8=False)
    np.testing.assert_array_equal(byte_image, expected)
    np.testing.assert_allclose(float_image, expected.astype(np.float32) / 255, rtol=0, atol=0)


def test_profiles_roundtrip_keeps_both_methods_and_rejects_invalid_values():
    from stmviewer.method_parameters import (
        MethodProfiles, AkazeParameters, LightGlueParameters, profiles_record, decode_profiles,
    )
    profiles = MethodProfiles(
        akaze=AkazeParameters(threshold=0.000001, radius=1.5,
                              contrast=ContrastParameters(mode='percentiles')),
        lightglue=LightGlueParameters(detection_threshold=.001, max_keypoints=4096,
                                     nms_radius=2, filter_threshold=.05, full_computation=True))
    record = profiles_record(profiles)
    assert decode_profiles(record) == profiles
    record['akaze']['threshold'] = 0
    with pytest.raises(ValueError):
        decode_profiles(record)
    for changes in ({'max_keypoints': True}, {'filter_threshold': float('nan')},
                    {'nms_radius': -1}, {'detection_threshold': 0},
                    {'radius': float('inf')}, {'full_computation': 1}):
        with pytest.raises(ValueError):
            LightGlueParameters(**changes)
    for changes in ({'lower': 99, 'upper': 1}, {'mode': 'gamma'},
                    {'clip_limit': 0}, {'grid_x': 0}):
        with pytest.raises(ValueError):
            ContrastParameters(**changes)
    record = profiles_record(profiles)
    record['lightglue']['unrecognized'] = 1
    with pytest.raises(ValueError):
        decode_profiles(record)


def test_akaze_applies_profile_at_opencv_boundary_and_recovers_xy(monkeypatch):
    import cv2
    from stmviewer.akaze_matcher import AkazeBackend
    from stmviewer.method_parameters import AkazeParameters
    from test_akaze_backend import texture

    original_factory = cv2.AKAZE_create
    observed = []
    def detector(*args, **kwargs):
        value = original_factory(*args, **kwargs)
        observed.append(value.getThreshold())
        return value
    monkeypatch.setattr(cv2, 'AKAZE_create', detector)
    parameters = AkazeParameters(threshold=.0001, radius=1.5,
                                  contrast=ContrastParameters(mode='percentiles'))
    backend = AkazeBackend(parameters=parameters)
    try:
        original = texture()
        result = backend.estimate(original, np.roll(original, (-5, 7), (0, 1)), moving_frame_index=1)
        np.testing.assert_allclose(result.shift_xy, (-7, 5), atol=.3)
        assert observed == pytest.approx([.0001])
        detail = backend.last_diagnostics
        assert 'inlier_radius=1.5' in detail.settings_text
        assert detail.preparation[0].normalization == 'percentiles-uint8-round-v1'
        assert 'parameter_profile' in dict(detail.model_provenance)
    finally:
        backend.close()
