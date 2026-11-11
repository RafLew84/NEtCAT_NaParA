"""Structural probes retain paired noise, fixed support and known changes."""

import numpy as np

from stmdomains.experiments import e3_structures
from stmdomains.experiments.controls import lattice, render_points


class ZeroNoise:
    def normal(self, mean, sigma, shape):
        return np.zeros(shape)


def test_structure_probe_is_deterministic_has_all9_blocks_and_preserves_support():
    result = e3_structures.make_structure_probe()
    repeated = e3_structures.make_structure_probe()
    assert result["conditions"] == ["identity", "orientation8", "spacing16", "phase4"]
    assert len(result["metadata"]) == 9
    assert len({m["id"] for m in result["metadata"]}) == 9
    assert {tuple(m["baseline_phase_xy"]) for m in result["metadata"]} == {(0., 0.), (2., 1.), (4., 3.)}
    assert {m["noise_seed"] for m in result["metadata"]} == {20261111, 20261112, 20261113}
    for condition in result["conditions"]:
        for key, size in (("native48", 48), ("patches64", 64)):
            array = result[key][condition]
            assert array.shape == (9, size, size) and array.dtype == np.float32
            assert np.isfinite(array).all() and array.min() >= 0. and array.max() <= 1.
            np.testing.assert_array_equal(array, repeated[key][condition])
        if condition != "identity":
            assert not np.array_equal(result["patches64"][condition], result["patches64"]["identity"])
    assert "domain_labels" not in result and "truth" not in result


def test_every_structural_contrast_has_identical_noise_field_and_no_photometric_change():
    result = e3_structures.make_structure_probe()
    for index, metadata in enumerate(result["metadata"]):
        phase = np.array(metadata["baseline_phase_xy"])
        expected_noise = np.random.default_rng(metadata["noise_seed"]).normal(0., .025, (96, 96))
        for condition, change in result["changes"].items():
            points = lattice((96, 96), spacing=change["spacing_px"], angle=change["angle_deg"],
                             phase=phase + change["phase_delta_xy"])
            noiseless = render_points(points, (96, 96), ZeroNoise())
            residual = (result["sources96"][condition][index] - .5) / .4 - noiseless
            np.testing.assert_allclose(residual, expected_noise, rtol=0, atol=1e-14)
            # Native48 is direct central pixel sampling, not a resize of64.
            expected48 = np.clip(result["sources96"][condition][index, 24:72, 24:72].astype(np.float32), 0., 1.)
            np.testing.assert_array_equal(result["native48"][condition][index], expected48)
    assert result["changes"]["phase4"]["phase_delta_xy"] == [0., 4.]
    assert result["changes"]["orientation8"]["angle_deg"] == 8.
