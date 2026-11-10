"""Geometry, anti-collapse and checkpoint contracts of the issue22 prototype."""
from __future__ import annotations

import json

import numpy as np
import pytest
import torch

from stmdomains.experiments.bundle import file_hash, write_json
from stmdomains.experiments.training.checkpoint import load_checkpoint, save_checkpoint
from stmdomains.experiments.training.local_ssl import fit
from stmdomains.experiments.training.local_ssl.models import LocalSSL, aligned_tokens, load_model


def test_known_shift_alignment_preserves_world_position_across_all_scales():
    # Local maps are a linear world-coordinate field sampled by each translated
    # crop. Correct inverse mapping exactly recovers the same canonical field.
    shifts = torch.tensor([[2., -2.], [-1.25, 1.75], [0.5, -1.]])
    scales = torch.tensor([32., 48., 64.])
    yy, xx = torch.meshgrid(torch.arange(7.), torch.arange(7.), indexing="ij")
    base = torch.stack((xx, yy))[None].repeat(3, 1, 1, 1)
    translated = base + shifts[:, :, None, None] * (8 / scales[:, None, None, None])
    aligned = aligned_tokens(translated, shifts, scales)
    expected = base[:, :, 1:6, 1:6].flatten(2).transpose(1, 2)
    torch.testing.assert_close(aligned, expected, atol=1e-6, rtol=0)
    for i in range(3):
        for shift in (-2., 2.):
            aligned_tokens(base[i:i+1], torch.full((1, 2), shift), scales[i:i+1])
    with pytest.raises(ValueError, match="support"):
        aligned_tokens(base, shifts * 2, scales)


def test_local_map_flattening_retains_phase_and_has_no_reconstruction_head():
    model = LocalSSL(16)
    torch.manual_seed(11)
    x = torch.randn(2, 1, 64, 64)
    output = model(x)
    assert output["local_map"].shape == (2, 16, 7, 7)
    assert output["content"].shape == (2, 784)
    assert torch.equal(output["content"], output["local_map"].flatten(1))
    assert not torch.equal(output["content"], model(torch.roll(x, 8, dims=-1))["content"])
    assert output["angle_radians"] is None
    assert "reconstruction" not in output


def test_constant_features_have_large_anti_collapse_loss():
    x = torch.ones(2, 16, 7, 7, requires_grad=True)
    terms = fit.losses(x, x, torch.zeros(2, 2, 2), torch.full((2,), 48.))
    assert terms["invariance"] == 0
    assert terms["covariance"] == 0
    assert terms["std_max"] == 0
    assert float(terms["loss"].detach()) == pytest.approx(24.75, abs=1e-5)


def test_correspondence_loss_backward_reaches_every_learned_layer():
    torch.manual_seed(11)
    model = LocalSSL(32)
    x = torch.randn(4, 1, 64, 64)
    maps = model(x)["local_map"].reshape(2, 2, 32, 7, 7)
    terms = fit.losses(maps[:, 0], maps[:, 1], torch.tensor([[[2., -2.], [-2., 2.]],
                                                          [[.2, .4], [-.1, -.2]]]),
                       torch.tensor([32., 64.]))
    terms["loss"].backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
    assert all(p.grad.abs().sum() > 0 for p in model.parameters() if p.ndim > 1)


def test_identical_views_have_zero_invariance_but_shift_error_is_detected():
    torch.manual_seed(16)
    x = torch.randn(2, 16, 7, 7)
    scales = torch.tensor([32., 64.])
    correct = fit.losses(x, x, torch.zeros(2, 2, 2), scales)
    wrong_shifts = torch.zeros(2, 2, 2)
    wrong_shifts[:, 1, 0] = 2
    incorrect = fit.losses(x, x, wrong_shifts, scales)
    assert correct["invariance"] == 0
    assert incorrect["invariance"] > 0


def test_initial_checkpoint_roundtrip_restores_weights_and_sampling_rng(tmp_path):
    model, optimizer, scheduler, sampler, augmentation = fit.initialize(32, 20261101, "cpu")
    config = {"family": "local_ssl", "latent_dim": 32}
    path = tmp_path / "step-0000.pt"
    before = {name: value.clone() for name, value in model.state_dict().items()}
    save_checkpoint(path, model=model, optimizer=optimizer, scheduler=scheduler,
                    sampler=sampler, np_generator=augmentation, progress={"step": 0}, config=config)
    expected_indices = torch.randint(100, (20,), generator=sampler)
    expected_noise = augmentation.normal(size=20)
    with torch.no_grad():
        next(model.parameters()).add_(1.)
    load_checkpoint(path, model=model, optimizer=optimizer, scheduler=scheduler,
                    sampler=sampler, np_generator=augmentation, config=config)
    assert all(torch.equal(value, before[name]) for name, value in model.state_dict().items())
    assert torch.equal(torch.randint(100, (20,), generator=sampler), expected_indices)
    np.testing.assert_array_equal(augmentation.normal(size=20), expected_noise)
    write_json(tmp_path / "config.json", config)
    write_json(tmp_path / "run.json", {"config_file_sha256": file_hash(tmp_path / "config.json"),
               "initial_checkpoint": path.name, "initial_checkpoint_sha256": file_hash(path),
               "selected_checkpoint": None, "selected_checkpoint_sha256": None})
    loaded = load_model(tmp_path, initial=True)
    assert all(torch.equal(value, before[name]) for name, value in loaded.state_dict().items())


def test_nine_fits_and_three_paired_untrained_z32_initializations():
    specs = fit.run_specs()
    assert len(specs) == 9
    assert len([s for s in specs if s["regime"] == "transfer"]) == 6
    assert len([s for s in specs if s["regime"] == "transductive"]) == 3
    assert {s["seed"] for s in specs} == {20261101, 20261102, 20261103}
    for seed in fit.SEEDS:
        first = fit.initialize(32, seed, "cpu")[0]
        second = fit.initialize(32, seed, "cpu")[0]
        assert all(torch.equal(value, second.state_dict()[name]) for name, value in first.state_dict().items())


def test_fixed_spatial_pattern_is_still_a_collapsed_descriptor():
    torch.manual_seed(19)
    x = torch.randn(1, 16, 7, 7).expand(4, -1, -1, -1)
    terms = fit.losses(x, x, torch.zeros(4, 2, 2), torch.full((4,), 48.))
    assert terms["std_max"] > 0
    assert terms["descriptor_std_max"] == 0
