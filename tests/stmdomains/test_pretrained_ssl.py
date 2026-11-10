"""Finite mechanics tests, no pretrained fitting or quality interpretation."""
import pytest
import torch
import json

from stmdomains.experiments.training.pretrained_ssl.models import aligned_tokens, entropy_statistics, transform


def test_input_transform_keeps_constant_measured_values():
    value = torch.full((2, 1, 64, 64), .5)
    result = transform(value)
    expected = (.5-torch.tensor([.485, .456, .406]))/torch.tensor([.229, .224, .225])
    assert result.shape == (2, 3, 112, 112)
    assert torch.allclose(result, expected[None, :, None, None])


def test_input_transform_rejects_unmeasured_nonfinite_values():
    image = torch.zeros(1, 1, 64, 64)
    image[0, 0, 0, 0] = float("nan")
    with pytest.raises(ValueError, match="Non-finite"):
        transform(image)


def test_correspondence_maps_the_same_raw_affine_field():
    axis = torch.arange(8, dtype=torch.float32)
    yy, xx = torch.meshgrid(axis, axis, indexing="ij")
    shifts = torch.tensor([[2., -2.], [-2., 2.]])
    scales = torch.tensor([32., 64.])
    fields = torch.stack([xx+2*yy+(s[0]+2*s[1])*8/scale for s, scale in zip(shifts, scales)])[:, None]
    aligned = aligned_tokens(fields, shifts, scales)
    expected = (xx[1:7, 1:7]+2*yy[1:7, 1:7]).flatten()
    assert torch.equal(aligned[:, :, 0], expected.expand(2, -1))


def test_correspondence_weights_do_not_pad_and_have_finite_gradients():
    maps = torch.ones(2, 3, 8, 8, requires_grad=True)
    output = aligned_tokens(maps, torch.tensor([[2., 2.], [-2., -2.]]), torch.tensor([32., 32.]))
    assert torch.equal(output, torch.ones_like(output))
    output.sum().backward()
    assert torch.isfinite(maps.grad).all()
    assert torch.all(maps.grad >= 0)
    assert torch.equal(maps.grad.sum((2, 3)), torch.full((2, 3), 36.))


def test_correspondence_rejects_outside_declared_support():
    with pytest.raises(ValueError, match="support"):
        aligned_tokens(torch.zeros(1, 3, 8, 8), torch.tensor([[2.01, 0.]]), torch.tensor([32.]))


def test_entropy_does_not_mistake_position_diversity_for_image_diversity():
    uniform = torch.full((4, 2, 36, 256), 1/256)
    stats = entropy_statistics(uniform)
    assert abs(float(stats["head_mutual_information"])) < 1e-6
    positional = torch.zeros_like(uniform)
    for position in range(36):
        positional[:, :, position, position] = 1
    stats = entropy_statistics(positional)
    assert stats["head_mutual_information"] > 3
    assert stats["head_position_conditional_information"] == 0


def test_external_termination_preserves_unknown_optimizer_steps(tmp_path):
    from stmdomains.experiments.bundle import file_hash
    from stmdomains.experiments.training.pretrained_ssl.fit import external_failures
    (tmp_path / "training").mkdir()
    (tmp_path / "plan.json").write_text("{}")
    log = tmp_path / "training/worker.log"
    log.write_text("worker terminated without final run.json")
    ident = "transfer/dino_adapted/seed-20261101"
    outcome = dict(run_id=ident, directory=str(tmp_path / "training" / ident), status="failed",
                   external_termination=True, returncode=-15, completed_optimizer_steps=None,
                   wall_seconds=42., cpu_seconds=13., peak_rss_bytes=1024,
                   log_file="training/worker.log", log_sha256=file_hash(log))
    registry = dict(plan_sha256=file_hash(tmp_path / "plan.json"), outcomes=[outcome])
    path = tmp_path / "training/registry.json"
    path.write_text(json.dumps(registry))
    assert external_failures(tmp_path)[ident]["completed_optimizer_steps"] is None
    outcome["completed_optimizer_steps"] = 0
    path.write_text(json.dumps(registry))
    with pytest.raises(ValueError, match="fabricated"):
        external_failures(tmp_path)


def test_external_termination_requires_authenticated_log(tmp_path):
    from stmdomains.experiments.bundle import file_hash
    from stmdomains.experiments.training.pretrained_ssl.fit import external_failures
    (tmp_path / "training").mkdir()
    (tmp_path / "plan.json").write_text("{}")
    ident = "transfer/dino_adapted/seed-20261101"
    outcome = dict(run_id=ident, directory=str(tmp_path / "training" / ident), status="failed",
                   external_termination=True, returncode=-15, completed_optimizer_steps=None,
                   wall_seconds=42., cpu_seconds=13., peak_rss_bytes=1024,
                   log_file="training/worker.log", log_sha256="incorrect")
    (tmp_path / "training/worker.log").write_text("changed log")
    (tmp_path / "training/registry.json").write_text(json.dumps(dict(
        plan_sha256=file_hash(tmp_path / "plan.json"), outcomes=[outcome])))
    with pytest.raises(ValueError, match="process log"):
        external_failures(tmp_path)
