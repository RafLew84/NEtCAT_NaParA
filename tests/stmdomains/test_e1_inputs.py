"""E1 native reconstruction and source-integrity boundary checks."""
import json

import numpy as np
import pytest

from stmdomains.experiments.bundle import file_hash
from stmdomains.experiments.e1_inputs import Inputs, native_descriptor
from stmdomains.experiments.training.texture import describe_patches, order_mask


def native_fixture():
    yy, xx = np.indices((96, 96))
    image = (.5 + .2 * np.cos(2 * np.pi * xx / 12)
             + .15 * np.cos(2 * np.pi * yy / 15)).astype(np.float32)
    arrays = {"image": image, "measured": np.ones(image.shape, bool),
              "object_ids": np.array([], dtype="U1"),
              "centers_xy": np.empty((0, 2)), "boxes_xyxy": np.empty((0, 4))}
    rows = [
        {"available": True, "raw_edge_xy": [48., 48.], "scale_raw_px": 48,
         "support_xyxy": [21., 21., 75., 75.]},
        {"available": False, "raw_edge_xy": [8., 8.], "scale_raw_px": 48,
         "support_xyxy": [-19., -19., 35., 35.]},
    ]
    # An integer raw window is a direct original-image slice. The cached64
    # tensor is deliberately unrelated, detecting accidental downsampling.
    local = describe_patches(image[None, 24:72, 24:72])
    threshold = .1
    cache = {"available_indices": np.array([0]), "patches": np.zeros((1, 64, 64)),
             "acf_score": np.r_[local["acf_score"], np.nan],
             "fft": np.vstack([local["features"], np.full((1, 216), np.nan)]),
             "order_pass": np.r_[order_mask(local, threshold), False]}
    return arrays, rows, cache, threshold


def test_native_reconstruction_uses_raw48_and_preserves_unavailable_rows():
    arrays, rows, cache, threshold = native_fixture()
    result, audit = native_descriptor(arrays, rows, {"low": 0., "high": 1.},
                                      cache, threshold, synthetic=False)
    assert result["available"].tolist() == result["valid"].tolist() == [True, False]
    assert np.isnan(result["energy"][1])
    assert np.isnan(result["second_direction_ratio"][1])
    assert result["energy"][0] > 0
    assert audit["acf_max_abs_difference"] == audit["fft_max_abs_difference"] == 0
    assert audit["order_pass_exact"]


def test_changed_baseline_gate_is_rejected_even_when_acf_and_fft_match():
    arrays, rows, cache, threshold = native_fixture()
    cache["order_pass"][0] = not cache["order_pass"][0]
    with pytest.raises(ValueError, match="order_pass"):
        native_descriptor(arrays, rows, {"low": 0., "high": 1.}, cache, threshold,
                          synthetic=False)


def test_missing_support_cannot_be_promoted_by_a_cached_available_index():
    arrays, rows, cache, threshold = native_fixture()
    cache["available_indices"] = np.array([0, 1])
    with pytest.raises(ValueError, match="availability"):
        native_descriptor(arrays, rows, {"low": 0., "high": 1.}, cache, threshold,
                          synthetic=False)


def write_miniature_source(root):
    contents = {"predictions/index.json": [], "cache/index.json": [],
                "cache/order-thresholds.json": {"scales": {"48": {"threshold": .379}}}}
    hashes = {}
    for relative, value in contents.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        hashes[relative] = file_hash(path)
    (root / "frozen-predictions.json").write_text(json.dumps({
        "schema": "stmdomains-frozen-predictions-v1", "evaluation_opened": False,
        "files": hashes,
    }))


def test_verified_source_detects_later_change_and_audit_is_outside_source(tmp_path):
    source, output = tmp_path / "old", tmp_path / "new"
    write_miniature_source(source)
    inputs = Inputs(source, output, strict=False)
    audit = inputs.save_audit()
    assert audit["source_hashes"]["cache/index.json"] == file_hash(source / "cache/index.json")
    assert (output / "input-audit.json").exists()
    assert not (source / "input-audit.json").exists()
    (source / "cache/index.json").write_text('[{"changed": true}]')
    with pytest.raises(ValueError, match="changed"):
        inputs.read_json("cache/index.json")
    with pytest.raises(ValueError, match="not in the prediction freeze"):
        inputs.read_json("../outside.json")


def test_output_cannot_overlap_original_artifacts(tmp_path):
    source = tmp_path / "old"
    write_miniature_source(source)
    with pytest.raises(ValueError, match="separate"):
        Inputs(source, source / "new", strict=False)
    with pytest.raises(ValueError, match="separate"):
        Inputs(source, tmp_path, strict=False)
