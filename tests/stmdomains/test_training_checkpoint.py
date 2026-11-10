"""Continuation must preserve the optimization trajectory and random streams."""
import os
import random
import subprocess
import sys

import numpy as np
import pytest
import torch

from stmdomains.experiments.training.checkpoint import (
    capture_rng, config_hash, load_checkpoint, read_checkpoint, restore_rng, save_checkpoint,
)
from stmdomains.experiments.training.gpu_probe import (
    compare_states, initialize, operation_probe,
)


def test_rng_restore_preserves_next_draws():
    _, _, _, sampler = initialize(37, "cpu")
    state = capture_rng(sampler)
    def draws():
        return (random.random(), np.random.random(5), torch.rand(5),
                torch.randint(100, (5,), generator=sampler))
    expected = draws()
    draws()
    restore_rng(state, sampler)
    assert compare_states(expected, draws())["exact"]


def test_augmentation_generator_resumes_and_requires_matching_presence_and_type():
    _, _, _, sampler = initialize(37, "cpu")
    augmentation = np.random.default_rng(72)
    state = capture_rng(sampler, np_generator=augmentation)
    expected = augmentation.uniform(size=(4, 6))
    augmentation.uniform(size=(10, 9))
    restore_rng(state, sampler, np_generator=augmentation)
    np.testing.assert_array_equal(expected, augmentation.uniform(size=(4, 6)))
    with pytest.raises(ValueError, match="presence"):
        restore_rng(state, sampler)
    with pytest.raises(ValueError, match="presence"):
        restore_rng(capture_rng(sampler), sampler, np_generator=augmentation)
    with pytest.raises(ValueError, match="bit-generator type"):
        restore_rng(state, sampler, np_generator=np.random.Generator(np.random.Philox(72)))


def test_changed_config_rejected_before_weights_are_loaded(tmp_path):
    model, optimizer, scheduler, sampler = initialize(31, "cpu")
    path = tmp_path / "own.pt"
    config = {"dataset_hash": "abc", "precision": "float32"}
    save_checkpoint(path, model=model, optimizer=optimizer, scheduler=scheduler,
                    sampler=sampler, progress={"step": 0}, config=config)
    before = {key: value.clone() for key, value in model.state_dict().items()}
    with pytest.raises(ValueError, match="configuration does not match"):
        load_checkpoint(path, model=model, optimizer=optimizer, scheduler=scheduler,
                        sampler=sampler, config={**config, "dataset_hash": "changed"})
    assert compare_states(before, model.state_dict())["exact"]
    assert config_hash(config) == config_hash(dict(reversed(list(config.items()))))


def test_checkpoint_resume_in_fresh_process(tmp_path):
    patches = np.random.default_rng(91).normal(size=(4, 1, 64, 64)).astype(np.float32)
    batch = tmp_path / "patches.npz"
    np.savez(batch, patches=patches)
    env = dict(os.environ, CUBLAS_WORKSPACE_CONFIG=":4096:8")
    for phase in ("full", "first", "resume"):
        subprocess.run([sys.executable, "-m", "stmdomains.experiments.training.gpu_probe",
                        "--batch", str(batch), "--out", str(tmp_path), "--device", "cpu",
                        "--worker", phase, "--seed", "19"],
                       env=env, check=True, capture_output=True, text=True)
    full, resumed = (read_checkpoint(tmp_path / f"{name}.pt") for name in ("full", "resume"))
    for key in ("model", "optimizer", "scheduler", "rng", "progress"):
        assert compare_states(full[key], resumed[key])["exact"], key
    assert full["progress"]["step"] == 6
    assert len(full["progress"]["history"]) == 6
    assert full["scheduler"]["last_epoch"] == 6
    assert full["rng"]["numpy_generator"]["bit_generator"] == "PCG64"
    assert len({tuple(row["batch_ids"]) for row in full["progress"]["history"]}) > 1


def test_rvae_and_ssl_proxy_operations_have_finite_gradients():
    patches = torch.from_numpy(np.random.default_rng(2).normal(size=(3, 1, 64, 64)).astype(np.float32))
    result = operation_probe(patches, "cpu")
    assert result["grid_sample_backward"]["strict"]["passed"]
    assert result["coordinate_decoder_backward"]["passed"]
    assert result["local_variance_covariance_backward"]["passed"]
    assert result["reparameterization_backward"]["passed"]


def test_comparison_detects_rng_and_optimizer_changes():
    assert not compare_states({"rng": torch.tensor([1, 2])}, {"rng": torch.tensor([1, 3])})["passed"]
    assert not compare_states({"step": 3}, {"step": 4})["passed"]
    result = compare_states(torch.tensor([1.0]), torch.tensor([1.001]))
    assert not result["passed"]
