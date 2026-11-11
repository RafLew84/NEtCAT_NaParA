"""E3 photometric interventions preserve pairing and expose excursions."""
import numpy as np
import pytest

from stmdomains.experiments.e3_transforms import CONDITIONS, fit_gradient, pixel_stats, transform


def test_identity_independent_conditions_and_no_reclipping():
    base = np.stack((np.zeros((64, 64)), np.ones((64, 64)))).astype(np.float32)
    saved = base.copy()
    ids = ["window-a", "window-b"]
    identity = transform(base, "identity", .05, ids)
    assert identity.dtype == np.float32 and identity.tobytes() == base.tobytes()
    assert not np.shares_memory(identity, base)
    gain = transform(base, "gain_plus", .05, ids)
    offset = transform(base, "offset_minus", .05, ids)
    np.testing.assert_array_equal(base, saved)
    np.testing.assert_allclose(gain[1], 1.1)
    np.testing.assert_allclose(offset[0], -.1)
    assert gain.max() > 1 and offset.min() < 0
    stats = pixel_stats(base, gain)
    np.testing.assert_array_equal(stats["baseline_saturation_fraction"], [1., 1.])
    np.testing.assert_array_equal(stats["post_outside_fraction"], [0., 1.])
    np.testing.assert_allclose(stats["input_rmse"], [0., .1], atol=1e-7)


def test_noise_is_stable_by_window_and_independent_of_order_chunking_resolution():
    base = np.zeros((3, 64, 64), dtype=np.float32)
    ids = ["one", "two", "three"]
    actual = transform(base, "noise", .02, ids)
    np.testing.assert_array_equal(actual, transform(base, "noise", .1, ids))
    order = np.array([2, 0, 1])
    np.testing.assert_array_equal(actual[order], transform(base[order], "noise", .02, [ids[i] for i in order]))
    chunked = np.concatenate([transform(base[i:i+1], "noise", .02, ids[i:i+1]) for i in range(3)])
    np.testing.assert_array_equal(actual, chunked)
    assert not np.array_equal(actual[0], actual[1])
    native = transform(np.zeros((1, 48, 48), np.float32), "noise", .02, [ids[0]])
    assert not np.array_equal(actual[0, :48, :48], native[0])


def test_gradient_axes_sign_span_and_training_plane_calibration():
    axis = np.linspace(-1., 1., 64)
    plane = (.5 + .03*axis[None, :] - .04*axis[:, None]).astype(np.float32)
    fit = fit_gradient(plane[None])
    assert fit["count"] == 1
    assert fit["value"] == pytest.approx(.07, abs=1e-8)
    assert fit["quantiles"]["q50"] == pytest.approx(.07, abs=1e-8)
    assert fit_gradient(np.ones((2, 64, 64), np.float32))["value"] == .02
    assert fit_gradient((5*plane)[None])["value"] == .1
    base = np.zeros((1, 48, 48), np.float32)
    gx = transform(base, "gradient_x_plus", .07, ["one"])
    gy = transform(base, "gradient_y_minus", .07, ["one"])
    np.testing.assert_allclose(gx[0, :, 0], -.07)
    np.testing.assert_allclose(gx[0, :, -1], .07)
    np.testing.assert_array_equal(gy, -gx.transpose(0, 2, 1))
    assert float(gx.mean()) == pytest.approx(0., abs=1e-8)


def test_empty_inputs_and_invalid_measurements():
    base = np.empty((0, 64, 64), np.float32)
    for condition in CONDITIONS:
        changed = transform(base, condition, .02, [])
        assert changed.shape == base.shape
        assert all(value.shape == (0,) for value in pixel_stats(base, changed).values())
    with pytest.raises(ValueError, match="training"):
        fit_gradient(base)
    with pytest.raises(ValueError, match="finite"):
        transform(np.full((1, 64, 64), np.nan), "identity", .02, ["one"])
    with pytest.raises(ValueError, match="condition"):
        transform(base, "offset_and_gain", .02, [])
    with pytest.raises(ValueError, match="window ID"):
        transform(np.zeros((1, 64, 64)), "identity", .02, [])
