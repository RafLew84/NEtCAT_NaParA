"""Encode-only E3 contract and exact historical rVAE feature packing."""
import numpy as np
import pytest
import torch

from stmdomains.experiments.e3_inference import encode_readouts


class EncoderOnly(torch.nn.Module):
    latent_dim = 32

    def __init__(self, family="rvae", zero=False):
        super().__init__()
        self.family, self.zero, self.calls = family, zero, []

    def encode(self, images):
        assert not self.training and torch.is_inference_mode_enabled()
        assert images.dtype == torch.float32
        self.calls.append(len(images))
        mean = images.mean((1, 2, 3))
        content = torch.arange(1., 33.)[None].expand(len(images), -1) + mean[:, None]
        if self.zero:
            content = torch.zeros_like(content)
        return dict(content=content,
                    angle_radians=mean if self.family == "rvae" else None,
                    translation_normalized_xy=torch.stack((mean, -mean), 1) if self.family == "rvae" else None)

    def forward(self, *_args, **_kwargs):
        raise AssertionError("The decoder/forward path must never run")


def test_rvae_encodes_once_per_batch_and_preserves_historical_blocks():
    patches = np.stack([np.full((64, 64), x, np.float32) for x in [0., .5, 1.]])
    patches.setflags(write=False)
    model = EncoderOnly()
    result = encode_readouts(model, patches, batch_size=2)
    assert model.calls == [2, 1]
    content, theta = result["rvae_content"], result["_angle"]
    expected = np.concatenate((content/np.linalg.norm(content, axis=1, keepdims=True),
                               np.cos(theta)[:, None], np.sin(theta)[:, None]), axis=1)/np.sqrt(2)
    assert result["rvae_full"].dtype == expected.dtype
    assert result["rvae_full"].tobytes() == expected.tobytes()
    np.testing.assert_allclose(np.linalg.norm(result["rvae_full"][:, :32], axis=1), 1/np.sqrt(2), rtol=1e-6)
    np.testing.assert_allclose(np.linalg.norm(result["rvae_full"][:, 32:], axis=1), 1/np.sqrt(2), rtol=1e-6)
    np.testing.assert_array_equal(result["rvae_angle"], np.column_stack((np.cos(theta), np.sin(theta))))
    np.testing.assert_array_equal(result["_translation"], np.column_stack((theta, -theta)))


def test_ae_and_empty_inputs_do_not_invent_pose_or_run_encoder():
    model = EncoderOnly("ae")
    actual = encode_readouts(model, np.zeros((1, 64, 64), np.float32))
    assert actual["ae"].shape == (1, 32)
    assert np.isnan(actual["_angle"]).all() and np.isnan(actual["_translation"]).all()
    for family in ("ae", "rvae"):
        model = EncoderOnly(family)
        result = encode_readouts(model, np.empty((0, 64, 64), np.float32))
        assert model.calls == []
        assert all(array.shape[0] == 0 for array in result.values())
        assert result["_translation"].shape == (0, 2)


def test_zero_content_keeps_historical_unavailable_full_readout():
    result = encode_readouts(EncoderOnly(zero=True), np.zeros((1, 64, 64), np.float32))
    assert np.isnan(result["rvae_full"][:, :32]).all()
    np.testing.assert_array_equal(result["rvae_angle"], [[1., 0.]])


def test_invalid_shape_dtype_finiteness_and_batch_are_rejected():
    model = EncoderOnly()
    for patches in (np.zeros((1, 48, 48), np.float32), np.zeros((1, 64, 64), np.float64),
                    np.full((1, 64, 64), np.nan, np.float32)):
        with pytest.raises(ValueError):
            encode_readouts(model, patches)
    with pytest.raises(ValueError, match="Batch"):
        encode_readouts(model, np.zeros((1, 64, 64), np.float32), batch_size=0)
    assert model.calls == []
