"""Spectral geometry, direct-correlation checks and old-only gate calibration."""

import numpy as np
import pytest

from stmdomains.experiments.training import texture


def lattice_patch(size=48):
    y, x = np.indices((size, size))
    return .5 + .18 * np.cos(2 * np.pi * x / 12) + .18 * np.cos(2 * np.pi * y / 12)


def test_fft_samples_match_independent_bilinear_power_interpolation():
    image = lattice_patch()
    result = texture.describe_patches(image[None])
    centered = image - image.mean()
    tapered = centered * np.outer(np.hanning(48), np.hanning(48))
    spectrum = np.fft.fftshift(abs(np.fft.fft2(tapered, s=(96, 96))) ** 2)
    values = []
    for frequency in np.linspace(1 / 28, 1 / 6, 12):
        for angle in np.arange(18) * np.pi / 18:
            y, x = 48 + 96 * frequency * np.sin(angle), 48 + 96 * frequency * np.cos(angle)
            iy, ix = int(y), int(x)
            dy, dx = y - iy, x - ix
            value = (spectrum[iy, ix] * (1 - dy) * (1 - dx) +
                     spectrum[iy + 1, ix] * dy * (1 - dx) +
                     spectrum[iy, ix + 1] * (1 - dy) * dx + spectrum[iy + 1, ix + 1] * dy * dx)
            values.append(value)
    expected = np.sqrt(np.array(values) / sum(values))
    np.testing.assert_allclose(result["features"][0], expected, rtol=1e-13, atol=1e-15)
    np.testing.assert_allclose(np.linalg.norm(result["features"][0]), 1.)


@pytest.mark.parametrize("size", [32, 48, 64])
def test_windowed_acf_score_agrees_with_direct_overlap_dot_product(size):
    image = lattice_patch(size)
    result = texture.describe_patches(image[None])
    assert result["acf_score"][0] > 0
    windowed = (image - image.mean()) * np.outer(np.hanning(size), np.hanning(size))
    heights = []
    for x, y in result["basis_vectors"][0].astype(int):
        first = windowed[max(0, y):min(size, size + y), max(0, x):min(size, size + x)]
        second = windowed[max(0, -y):min(size, size - y), max(0, -x):min(size, size - x)]
        heights.append(np.sum(first * second) / np.sum(windowed * windowed))
    np.testing.assert_allclose(result["acf_score"][0], min(heights), atol=2e-15, rtol=1e-13)


def test_one_direction_stripes_fail_spectral_gate_while_two_directions_pass():
    y, x = np.indices((48, 48))
    stripe = .5 + .2 * np.cos(2 * np.pi * x / 12)
    result = texture.describe_patches(np.stack([stripe, lattice_patch()]))
    assert result["second_direction_ratio"][0] < .25
    assert result["second_direction_ratio"][1] >= .25
    assert texture.order_mask(result, 0.).tolist() == [False, True]


def test_contrast_offset_and_inversion_leave_spectral_geometry_unchanged():
    image = lattice_patch()
    result = texture.describe_patches(np.stack([image, 2 * image + 4, 1 - image]))
    for key in ["features", "acf_score", "second_direction_ratio"]:
        np.testing.assert_allclose(result[key][1], result[key][0], rtol=1e-12, atol=1e-14)
        np.testing.assert_allclose(result[key][2], result[key][0], rtol=1e-12, atol=1e-14)
    np.testing.assert_allclose(result["energy"][1], 4 * result["energy"][0])


def test_flat_is_valid_measurement_without_order_and_nonfinite_is_unavailable():
    patches = np.stack([np.full((48, 48), .5), np.full((48, 48), np.nan)])
    result = texture.describe_patches(patches)
    assert result["valid"].tolist() == [True, False]
    assert np.all(result["features"][0] == 0)
    assert result["energy"][0] == result["acf_score"][0] == 0
    assert np.isnan(result["features"][1]).all()
    assert np.isnan(result["acf_score"][1])
    assert texture.order_mask(result, 0.).tolist() == [False, False]
    assert texture.describe_patches(np.empty((0, 48, 48)))["features"].shape == (0, 216)


def test_order_threshold_is_strict_and_does_not_invent_order_on_missing_data():
    result = dict(valid=np.array([True, True, True, False]), energy=np.ones(4),
                  acf_score=np.array([.4, .4001, .9, .9]), second_direction_ratio=np.array([1., 1., .2499, 1.]))
    assert texture.order_mask(result, .4).tolist() == [False, True, False, False]


def test_calibration_uses_only_old_negative_sources_and_all_finite_available_grid_scores(monkeypatch):
    calls = []
    image = lattice_patch(64)

    def known_control(case, seed):
        calls.append((case, seed))
        return dict(image=image, measured=np.ones((64, 64), bool)), None, None

    monkeypatch.setattr(texture.old_controls, "make_control", known_control)
    calibration = texture.calibrate_order_thresholds((32,), seeds=(1701, 2701))
    assert calls == [(case, seed) for case in texture.OLD_NEGATIVE_CASES for seed in (1701, 2701)]
    # Full38px support leaves centers24/40 in both axes: four windows/source.
    assert calibration["scales"]["32"]["count"] == 40
    normalized = np.clip(.5 + .4 * image, 0, 1).astype(np.float32)
    patches = np.stack([normalized[y - 16:y + 16, x - 16:x + 16] for y in (24, 40) for x in (24, 40)])
    scores = texture.describe_patches(patches)["acf_score"]
    expected = np.quantile(np.tile(scores, 10), .999, method="linear")
    assert calibration["scales"]["32"]["threshold"] == expected
    assert calibration["applies_to"] == ["grid", "centers"]
    with pytest.raises(ValueError, match="already-viewed"):
        texture.calibrate_order_thresholds((32,), seeds=(920001,))


def test_native_scale_is_explicit_and_arbitrary_tensor_shapes_are_rejected():
    with pytest.raises(ValueError, match="native"):
        texture.describe_patches(np.zeros((1, 48, 64)))
