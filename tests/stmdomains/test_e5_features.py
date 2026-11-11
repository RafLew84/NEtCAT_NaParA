"""E5 map context, encode parity and fixed multiscale weights."""
import numpy as np
import pytest
import torch

from stmdomains.experiments.e3_inference import encode_readouts
from stmdomains.experiments.e5_features import encode_ae_readouts, equal_blocks, spatial_geometry
from stmdomains.experiments.training.models import Autoencoder, RotationalVAE


def test_map_and_z32_use_one_encoder_and_match_the_existing_readout():
    torch.manual_seed(7)
    torch.set_num_threads(1)
    model = Autoencoder(32)
    images = np.random.default_rng(9).random((3, 64, 64), dtype=np.float32)
    images.setflags(write=False)
    calls = []
    hook = model.encoder.register_forward_hook(lambda module, args, result: calls.append(len(result)))
    result = encode_ae_readouts(model, images, batch_size=2)
    hook.remove()
    assert calls == [2, 1]
    assert not model.training
    assert result["ae_map"].shape == (3, 3136)
    assert all(value.dtype == np.float32 for value in result.values())
    np.testing.assert_array_equal(result["ae"], encode_readouts(model, images, batch_size=2)["ae"])
    with torch.inference_mode():
        expected = model.head(torch.from_numpy(result["ae_map"])).numpy()
    np.testing.assert_allclose(result["ae"], expected, rtol=1e-6, atol=1e-7)


def test_full_map_context_and_first_cell_receptive_field_are_not_a_central_crop():
    model = Autoencoder(32)
    with torch.no_grad():
        for layer in model.encoder:
            if isinstance(layer, torch.nn.Conv2d):
                layer.weight.fill_(.001)
                layer.bias.fill_(.1)
    patches = np.zeros((4, 64, 64), np.float32)
    patches[1, 14, 14] = 1.
    patches[2, 15, 15] = 1.
    patches[3, 63, :] = 100.
    patches[3, :, 63] = 100.
    result = encode_ae_readouts(model, patches)
    maps = result["ae_map"].reshape(4, 64, 7, 7)
    assert np.all(maps[1, :, 0, 0] > maps[0, :, 0, 0])
    np.testing.assert_array_equal(maps[2, :, 0, 0], maps[0, :, 0, 0])
    assert np.any(maps[2] != maps[0])
    np.testing.assert_array_equal(maps[3], maps[0])
    np.testing.assert_array_equal(result["ae"][3], result["ae"][0])
    geometry = spatial_geometry(48)
    assert geometry["receptive_field_raw_px"] == 11.25
    assert geometry["stride_raw_px"] == 6.
    assert geometry["full_context_raw_relative_interval"] == [-24., 23.25]
    assert geometry["axis_bounds_raw_relative_px"][0] == [-24., -12.75]
    assert geometry["axis_bounds_raw_relative_px"][-1] == [12., 23.25]


def test_no_decode_empty_and_input_contract():
    model = Autoencoder(32)
    model.decoder.forward = lambda *_args: pytest.fail("Must not decode")
    result = encode_ae_readouts(model, np.empty((0, 64, 64), np.float32))
    assert result["ae"].shape == (0, 32) and result["ae_map"].shape == (0, 3136)
    encode_ae_readouts(model, np.zeros((1, 64, 64), np.float32))
    for images in (np.zeros((1, 48, 48), np.float32), np.zeros((1, 64, 64), float),
                   np.full((1, 64, 64), np.nan, np.float32)):
        with pytest.raises(ValueError):
            encode_ae_readouts(model, images)
    for batch in (0, True, 1.5):
        with pytest.raises(ValueError, match="Batch"):
            encode_ae_readouts(model, np.empty((0, 64, 64), np.float32), batch)
    for other in (Autoencoder(16), RotationalVAE(32)):
        with pytest.raises(ValueError, match="AE z32"):
            encode_ae_readouts(other, np.empty((0, 64, 64), np.float32))


def test_equal_blocks_keeps_scale_order_weights_and_missingness():
    blocks = {64: np.array([[0., 5.], [1., 2.], [1., 2.], [1e300, 1e300]]),
              32: np.array([[3., 4.], [0., 0.], [1., 2.], [1e-300, 1e-300]]),
              48: np.array([[7.], [1.], [np.nan], [1.]])}
    result = equal_blocks(blocks)
    np.testing.assert_allclose(result[0], np.array([.6, .8, 1., 0., 1.]) / np.sqrt(3))
    assert np.isnan(result[1:3]).all()
    assert np.isfinite(result[3]).all()
    for start, stop in ((0, 2), (2, 3), (3, 5)):
        np.testing.assert_allclose(np.linalg.norm(result[[0, 3], start:stop], axis=1), 1 / np.sqrt(3))
    np.testing.assert_allclose(np.linalg.norm(result[[0, 3]], axis=1), 1.)
    assert equal_blocks({s: np.empty((0, 32)) for s in (32, 48, 64)}).shape == (0, 96)


def test_equal_blocks_refuses_missing_scales_and_misaligned_rows():
    with pytest.raises(ValueError, match="exactly"):
        equal_blocks({32: np.ones((2, 1)), 48: np.ones((2, 1))})
    with pytest.raises(ValueError, match="aligned"):
        equal_blocks({s: np.ones((s, 1)) for s in (32, 48, 64)})
    with pytest.raises(ValueError):
        equal_blocks({s: np.ones((2, 0)) for s in (32, 48, 64)})
