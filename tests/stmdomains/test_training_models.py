import numpy as np
import pytest
import torch

from stmdomains.experiments.training.models import make_model
from stmdomains.experiments.training.fit import initialize, losses


@pytest.mark.parametrize("family", ["ae", "rvae"])
@pytest.mark.parametrize("dimension", [16, 32])
def test_actual_model_has_finite_gradients_and_deterministic_mean_prediction(family, dimension):
    model, optimizer, _, _, _ = initialize(family, dimension, 31, "cpu")
    inputs = torch.from_numpy(np.random.default_rng(9).normal(size=(2, 1, 64, 64)).astype(np.float32))
    output = model(inputs)
    objective = losses(output, inputs, 1)["loss"]
    objective.backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
    optimizer.step()
    rng = torch.get_rng_state().clone()
    with torch.inference_mode():
        a, b = model.predict(inputs), model.predict(inputs)
        encoded = model.encode(inputs)
    assert a.shape == inputs.shape
    assert torch.equal(a, b)
    assert torch.equal(rng, torch.get_rng_state())
    assert encoded["content"].shape == (2, dimension)
    if family == "rvae":
        assert encoded["angle_radians"].shape == (2,)
        assert encoded["translation_normalized_xy"].shape == (2, 2)


def test_coordinate_decoder_half_turn_rotates_reconstruction_without_resampling():
    model, *_ = initialize("rvae", 16, 31, "cpu")
    latent = torch.zeros(1, 19)
    latent[0, :16] = torch.linspace(-1, 1, 16)
    with torch.inference_mode():
        original = model.decode(latent)
        latent[0, 16] = torch.pi
        rotated = model.decode(latent)
    torch.testing.assert_close(rotated, original.flip((-2, -1)), atol=1e-6, rtol=1e-6)


def test_validation_uses_same_full_kl_weight_at_all_training_steps():
    output = {"reconstruction": torch.zeros(2, 1, 64, 64), "kl_per_sample": torch.ones(2)}
    target = torch.zeros_like(output["reconstruction"])
    assert losses(output, target, 100)["beta"] == .0005
    assert losses(output, target, 200)["beta"] == .001
    assert losses(output, target, 100, validation=True)["beta"] == .001
    assert losses(output, target, 200, validation=True)["beta"] == .001
