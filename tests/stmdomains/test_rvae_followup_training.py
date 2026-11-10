"""Meaningful21a model/loss/checkpoint checks without optimization runs."""
import json
import math

import numpy as np
import pytest
import torch

from stmdomains.experiments.bundle import file_hash
from stmdomains.experiments.training import models as original
from stmdomains.experiments.training.checkpoint import config_hash, save_checkpoint
from stmdomains.experiments.training.rvae_followup import fit, models

torch.set_num_threads(1)


def test_lowkl_changes_loss_only_and_fourier_keeps_shared_initialization():
    torch.manual_seed(31)
    base = original.make_model("rvae", 32)
    next_base = torch.randn(8)
    for family in models.FAMILIES:
        torch.manual_seed(31)
        candidate = models.make_model(family, 32)
        assert torch.equal(torch.randn(8), next_base)
        for name, value in base.state_dict().items():
            if "fourier" in family and name.startswith("decoder.0."):
                continue
            assert torch.equal(candidate.state_dict()[name], value), name
    images = torch.randn(2, 1, 64, 64)
    torch.manual_seed(31)
    low = models.make_model("rvae_lowkl", 32)
    assert torch.equal(base.predict(images), low.predict(images))


def test_fourier_is_encoded_after_pose_and_is_differentiable():
    model = models.make_model("rvae_fourier", 32)
    latent = torch.zeros(1, 35, requires_grad=True)
    with torch.no_grad():
        latent[:, 32] = math.pi/2
        latent[:, 33:] = torch.tensor([.5, -.25])
    observed = []
    handle = model.decoder[0].register_forward_pre_hook(lambda _m, args: observed.append(args[0].detach()))
    prediction = model.decode(latent)
    handle.remove()
    raw = model.coordinates
    expected_xy = torch.stack((raw[..., 1]+.05, -raw[..., 0]-.025), dim=-1)
    torch.testing.assert_close(observed[0][..., :2], expected_xy)
    expected_sin = (math.pi*expected_xy[..., :, None]*torch.tensor([1., 2., 4., 8., 16.])).sin().flatten(-2)/math.sqrt(5)
    torch.testing.assert_close(observed[0][..., 2:12], expected_sin)
    assert observed[0].shape == (1, 4096, 54)
    prediction.square().mean().backward()
    assert torch.isfinite(latent.grad).all()
    assert latent.grad[0, 32].abs() > 0


def test_beta_loss_reductions_and_warmup_are_explicit():
    reconstructed = torch.ones(2, 1, 64, 64, requires_grad=True)
    output = {"reconstruction": reconstructed, "kl_per_sample": torch.tensor([2., 4.])}
    target = torch.zeros_like(reconstructed)
    train = fit.losses(output, target, 100, beta=.0001)
    valid = fit.losses(output, target, 0, beta=.0001, validation=True)
    diagnostic = fit.losses(output, target, 1, beta=.001, diagnostic=True)
    assert train["beta"] == .00005
    assert valid["beta"] == .0001
    assert diagnostic["beta"] == .001
    assert float(train["mse"].detach()) == 1.
    assert float(train["kl"]) == 3.
    assert float(valid["loss"].detach()) == pytest.approx(1.0003)
    assert float(diagnostic["loss"].detach()) == pytest.approx(1.003)
    fit.losses(output, target, 1, beta=0, diagnostic=True)["loss"].backward()
    assert reconstructed.grad.sum().item() == pytest.approx(2.)


def test_loader_roundtrip_selected_fixed_step_and_changed_hash(tmp_path):
    model = models.make_model("rvae_fourier_lowkl", 32)
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001)
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda _: 1.)
    sampler = torch.Generator().manual_seed(101)
    config = {"family": "rvae_fourier_lowkl", "latent_dim": 32}
    path = tmp_path/"step-2000.pt"
    # A state-only checkpoint check: no optimizer.step, no extra training budget.
    save_checkpoint(path, model=model, optimizer=optimizer, scheduler=scheduler,
                    sampler=sampler, progress={"step": 2000}, config=config,
                    np_generator=np.random.default_rng(1))
    digest = file_hash(path)
    result = dict(status="completed", selected_checkpoint=path.name,
                  selected_checkpoint_sha256=digest, config_hash=config_hash(config),
                  checkpoints=[dict(step=2000, file=path.name, sha256=digest)])
    (tmp_path/"run.json").write_text(json.dumps(result))
    images = torch.randn(1, 1, 64, 64)
    for step in (None, 2000):
        loaded = models.load_model(tmp_path, step=step)
        assert torch.equal(loaded.predict(images), model.predict(images))
    with pytest.raises(ValueError, match="unavailable"):
        models.load_model(tmp_path, step=100)
    result["selected_checkpoint_sha256"] = "0"*64
    (tmp_path/"run.json").write_text(json.dumps(result))
    with pytest.raises(ValueError, match="hash mismatch"):
        models.load_model(tmp_path)


def test_closed_run_matrix_cannot_silently_add_fits():
    runs = fit.run_specs()
    assert len(runs) == len({r["run_id"] for r in runs}) == 11
    assert sum(r["diagnostic"] for r in runs) == 2
    assert sum(r["steps"] for r in runs) == 22000
    assert sum(r["seconds_cap"] for r in runs) == 8700
    assert {r["seed"] for r in runs} == {20261101, 20261102, 20261103}
    assert {r["family"] for r in runs if not r["diagnostic"]} == set(models.FAMILIES)
    with pytest.raises(ValueError):
        models.make_model("rvae_fourier", 16)
