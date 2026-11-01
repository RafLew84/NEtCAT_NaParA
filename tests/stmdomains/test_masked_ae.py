"""Masking, measured-support and RNG contracts; no optimizer steps."""
from copy import deepcopy

import numpy as np
import pytest
import torch

from stmdomains.experiments.training.fit import initialize as original_initialize
from stmdomains.experiments.training.masked_ae.fit import (
    initialize, measured_loss_audit, model_digest, restore_state, save_state, state_equal,
)
from stmdomains.experiments.training.masked_ae.models import apply_mask, block_masks, masked_losses


def test_ratios_use_exact_nested_whole_blocks_and_identical_rng_consumption():
    low_rng, high_rng = np.random.default_rng(81), np.random.default_rng(81)
    low, low_order = block_masks(7, .25, low_rng, with_order=True)
    high, high_order = block_masks(7, .5, high_rng, with_order=True)
    assert torch.all(low <= high)
    assert torch.all(low.flatten(1).sum(1) == 1024)
    assert torch.all(high.flatten(1).sum(1) == 2048)
    assert np.array_equal(low_order, high_order)
    assert low_rng.bit_generator.state == high_rng.bit_generator.state
    for mask in (low, high):
        tiles = mask[:, :, ::16, ::16]
        assert torch.equal(mask, tiles.repeat_interleave(16, 2).repeat_interleave(16, 3))


@pytest.mark.parametrize("family", ["mask25", "mask50"])
def test_model_is_exact_AE32_capacity_initialization_and_unmasked_inference(family):
    original = original_initialize("ae", 32, 81, "cpu")[0]
    model = initialize(family, 81, "cpu")[0]
    assert sum(p.numel() for p in model.parameters()) == 250513
    assert model_digest(model) == model_digest(original)
    images = torch.zeros(2, 1, 64, 64)
    with torch.inference_mode():
        assert torch.equal(model.predict(images), original.predict(images))
        assert torch.equal(model.encode(images)["content"], original.encode(images)["content"])
        assert model.encode(images)["content"].shape == (2, 32)


def test_hidden_pixels_have_no_input_value_or_gradient_path():
    mask = block_masks(2, .5, np.random.default_rng(82))
    image = torch.ones(2, 1, 64, 64, requires_grad=True)
    corrupted = apply_mask(image, mask)
    corrupted.sum().backward()
    assert torch.all(corrupted[mask] == 0)
    assert torch.all(image.grad[mask] == 0)
    assert torch.all(image.grad[~mask] == 1)
    changed = image.detach().clone()
    changed[mask] = 2000.
    assert torch.equal(corrupted, apply_mask(changed, mask))


def test_loss_excludes_unmeasured_nan_and_visible_targets_and_rejects_padding():
    assert measured_loss_audit("cpu")["passed"]
    image = torch.zeros(1, 1, 64, 64)
    mask = torch.ones_like(image, dtype=torch.bool)
    with pytest.raises(ValueError, match="No measured masked"):
        masked_losses(image, image, mask, torch.zeros_like(mask))
    with pytest.raises(ValueError, match="no measurement padding"):
        apply_mask(image, mask, torch.zeros_like(mask))


def test_checkpoint_restores_separate_mask_and_augmentation_streams_without_training(tmp_path):
    config = dict(family="mask50", latent_dim=32, purpose="zero_step_rng_contract")
    original = initialize("mask50", 81, "cpu")
    original[4].normal(size=(3, 4))
    block_masks(3, .5, original[5])
    path = tmp_path / "initial.pt"
    save_state(path, original, dict(step=0), config)
    expected = (torch.randint(100, (8,), generator=original[3]), original[4].normal(size=8),
                block_masks(3, .5, original[5]), deepcopy(original[5].bit_generator.state))
    restored = initialize("mask50", 81, "cpu")
    progress = restore_state(path, restored, config)
    actual = (torch.randint(100, (8,), generator=restored[3]), restored[4].normal(size=8),
              block_masks(3, .5, restored[5]), restored[5].bit_generator.state)
    assert progress["step"] == 0
    assert state_equal(expected, actual)
    assert not original[1].state and not restored[1].state
