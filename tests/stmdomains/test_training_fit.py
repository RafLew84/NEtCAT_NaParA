"""Data boundary and continuation checks without accessing real references."""
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from stmdomains.experiments.bundle import file_hash, write_arrays, write_json
from stmdomains.experiments.training.checkpoint import load_checkpoint, save_checkpoint
from stmdomains.experiments.training.data import window_records
from stmdomains.experiments.training.fit import TrainingData, initialize, train_step, validate
from stmdomains.experiments.training.gpu_probe import compare_states


@pytest.fixture
def preparation(tmp_path):
    analysis = tmp_path / "analysis"
    records, rows = [], []
    for name, frame, origin in (("train", 1, [224., 0.]), ("val", 150, [100., 0.]),
                                ("test", 250, [0., 0.])):
        image = np.random.default_rng(frame).normal(size=(256, 256))
        arrays = dict(image=image, measured=np.ones(image.shape, bool), centers_xy=np.empty((0, 2)),
                      boxes_xyxy=np.empty((0, 4)), object_ids=np.array([], dtype="U16"))
        relative = f"samples/{name}.npz"
        (analysis / "samples").mkdir(parents=True, exist_ok=True)
        record = {"sample_id": name, "frame_number": frame, "file": relative,
                  "origin_in_expanded_xy": origin, **write_arrays(analysis / relative, arrays)}
        records.append(record)
        rows.extend(window_records(record, arrays))
    write_json(analysis / "manifest.json", {"schema": "stmdomains-input-v1", "samples": records})
    write_json(tmp_path / "normalization.json", {regime: {"low": -2., "high": 2.}
                                                for regime in ("transfer", "transductive")})
    write_json(tmp_path / "split.json", {"test": "fixture"})
    (tmp_path / "windows.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    manifest = {"schema": "stmdomains-training-preparation-v1",
                "analysis_manifest_sha256": file_hash(analysis / "manifest.json")}
    for name, path in (("split", "split.json"), ("windows", "windows.jsonl"), ("normalization", "normalization.json")):
        manifest[f"{name}_file"] = path
        manifest[f"{name}_sha256"] = file_hash(tmp_path / path)
    write_json(tmp_path / "manifest.json", manifest)
    return tmp_path


def test_transfer_never_opens_test_pixels_and_sampler_balances_scales(preparation):
    # Destroying the test sample cannot affect loading or training on train/val.
    (preparation / "analysis/samples/test.npz").unlink()
    data = TrainingData(preparation, "transfer")
    assert set(data.arrays) == {"train", "val"}
    indices = data.sample_indices(torch.Generator().manual_seed(1), 3000)
    counts = {scale: sum(data.train[i]["scale_raw_px"] == scale for i in indices) for scale in (32, 48, 64)}
    assert all(900 < value < 1100 for value in counts.values())
    first = data.validation_batches()
    second = data.validation_batches()
    assert all(torch.equal(a, b) for aa, bb in zip(first, second) for a, b in zip(aa, bb))


@pytest.mark.parametrize("family", ["ae", "rvae"])
def test_checkpoint_continuation_preserves_actual_training_and_validation(preparation, family):
    data = TrainingData(preparation, "transfer")
    model, opt, sched, sampler, rng = initialize(family, 16, 71, "cpu")
    train_step(model, opt, sched, sampler, rng, data, 1, "cpu", batch_size=2)
    path = preparation / "checkpoint.pt"
    config = {"family": family}
    save_checkpoint(path, model=model, optimizer=opt, scheduler=sched, sampler=sampler,
                    np_generator=rng, progress={"step": 1}, config=config)
    expected = train_step(model, opt, sched, sampler, rng, data, 2, "cpu", batch_size=2)
    expected_weights = {k: v.clone() for k, v in model.state_dict().items()}
    new_model, new_opt, new_sched, new_sampler, new_rng = initialize(family, 16, 999, "cpu")
    progress = load_checkpoint(path, model=new_model, optimizer=new_opt, scheduler=new_sched,
                               sampler=new_sampler, np_generator=new_rng, config=config)
    assert progress["step"] == 1
    actual = train_step(new_model, new_opt, new_sched, new_sampler, new_rng, data, 2, "cpu", batch_size=2)
    assert compare_states(expected, actual)["exact"]
    assert compare_states(expected_weights, new_model.state_dict())["exact"]
    before = torch.get_rng_state().clone()
    inputs, targets = data.batch([0, 1], np.random.default_rng(98), validation=True)
    validate(new_model, [(inputs, targets)], "cpu")
    assert torch.equal(before, torch.get_rng_state())
