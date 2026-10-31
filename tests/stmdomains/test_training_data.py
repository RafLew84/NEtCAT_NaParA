"""Independent geometry, leakage and data-isolation checks for issue 20."""

import copy
import json

import numpy as np
import pytest

from stmdomains.experiments.bundle import INPUT_KEYS, load_sample, write_arrays, write_json
from stmdomains.experiments.real_input import PILOT_NUMBERS
from stmdomains.experiments.training.data import (
    augmented_pair, extract_patch, fit_normalizers, synthetic_in_normalizer_units,
    verify_split, window_records,
)
from stmdomains.experiments.training.prepare import prepare


def test_synthetic_units_preserve_contrast_and_inversion_under_real_normalizers():
    from stmdomains.experiments.controls import make_control
    positive, _, _ = make_control("single", 1701)
    negative, _, _ = make_control("inverted", 1701)
    before = positive["image"].copy()
    mapped = []
    for normalizer in ({"low": -239.486, "high": 219.362}, {"low": 1000., "high": 1001.}):
        pair = []
        for arrays in (positive, negative):
            bridge = synthetic_in_normalizer_units(arrays, normalizer)
            pair.append(np.clip((bridge["image"] - normalizer["low"]) /
                                (normalizer["high"] - normalizer["low"]), 0, 1))
        np.testing.assert_allclose(pair[1], 1 - pair[0], rtol=0, atol=1e-12)
        assert pair[0].std() > .03  # renderer units must not become a nearly flat STM patch
        mapped.append(pair[0])
    np.testing.assert_allclose(mapped[0], mapped[1], rtol=0, atol=1e-12)
    np.testing.assert_array_equal(positive["image"], before)


def sample(number=1, *, origin=(224., 139.), centers=((128.125, 128.875), (1., 1.))):
    yy, xx = np.indices((256, 256), dtype=float)
    points = np.asarray(centers, dtype=float).reshape(-1, 2)
    arrays = dict(
        image=2 * (xx + .5) + 3 * (yy + .5) + 7 + number / 100,
        measured=np.ones((256, 256), bool), centers_xy=points,
        boxes_xyxy=np.column_stack((points - 2.5, points + 2.5)),
        object_ids=np.array([f"m{i}" for i in range(len(points))], dtype="U64"),
    )
    record = dict(
        sample_id=f"ttmapp-{number:03}", kind="measurement", frame_number=number,
        coordinate_system="raw_edge_xy", position_unit="px", shape_hw=[256, 256],
        origin_in_expanded_xy=list(origin), expanded_shape_hw=[408, 480],
        pixel_spacing_xy=[1., 1.], annotation_count=len(points),
    )
    return record, arrays


@pytest.mark.parametrize("scale", [32, 48, 64])
@pytest.mark.parametrize("shift", [(0., 0.), (1.75, -2.), (-2., 1.125)])
def test_fractional_center_and_translation_recover_analytical_linear_field(scale, shift):
    record, arrays = sample()
    row = next(r for r in window_records(record, arrays)
               if r["sampler"] == "centers" and r["element_id"] == "m0" and r["scale_raw_px"] == scale)
    patch = extract_patch(arrays, row, shift_xy=shift)
    # Pixel-edge coordinates: the input at index (y,x) represents (x+.5,y+.5).
    offsets = (np.arange(64) + .5) * scale / 64 - scale / 2
    x = 128.125 + shift[0] + offsets[None, :]
    y = 128.875 + shift[1] + offsets[:, None]
    np.testing.assert_allclose(patch, 2 * x + 3 * y + 7.01, rtol=0, atol=1e-4)


def test_all_centers_are_retained_and_unavailable_support_is_not_padded():
    record, arrays = sample()
    rows = window_records(record, arrays)
    centers = [r for r in rows if r["sampler"] == "centers"]
    assert len(centers) == 6
    assert {r["element_id"] for r in centers} == {"m0", "m1"}
    for row in centers:
        if row["element_id"] == "m1":
            assert not row["available"]
            assert row["unavailable_reason"] == "incomplete_measured_support"
            assert row["transfer_split"] is None
            with pytest.raises(ValueError, match="incomplete"):
                extract_patch(arrays, row)
    row = next(r for r in centers if r["element_id"] == "m0")
    with pytest.raises(ValueError, match="Translation"):
        extract_patch(arrays, row, shift_xy=(2.001, 0))


def test_hole_in_augmentation_support_invalidates_window_even_outside_nominal_crop():
    record, arrays = sample(centers=((128., 128.),))
    # The nominal 32px crop ends at x=144. A maximal translated view and its
    # interpolation stencil may approach this missing column, so exclude it.
    arrays["measured"][128, 145] = False
    row = next(r for r in window_records(record, arrays)
               if r["sampler"] == "centers" and r["scale_raw_px"] == 32)
    assert not row["available"]
    with pytest.raises(ValueError, match="incomplete"):
        extract_patch(arrays, row)


def test_transfer_normalizer_ignores_other_times_and_other_registered_regions():
    train = sample(1)
    validation = sample(150, origin=(0., 0.))
    test = sample(250, origin=(0., 0.))
    source = [train, validation, test]
    before = fit_normalizers(source)
    modified = copy.deepcopy(source)
    modified[1][1]["image"][:] = -1e8
    modified[2][1]["image"][:] = 1e8
    # Train image origin224; columns0..103 have registered x<328 and are outside
    # the guarded training band. They must not influence transfer statistics.
    modified[0][1]["image"][:, :104] = 5e8
    after = fit_normalizers(modified)
    assert after["transfer"] == before["transfer"]
    assert after["transductive"] != before["transductive"]
    assert before["transfer"]["pixel_count"] == 152 * 256


def test_registered_supports_are_disjoint_across_frames_and_time_embargo_is_explicit():
    examples = [sample(1), sample(150, origin=(0., 0.)), sample(250, origin=(0., 0.))]
    rows = [row for record, arrays in examples for row in window_records(record, arrays)]
    proof = verify_split(rows)
    assert proof["cross_frame_overlap"] is False
    boxes = {name: np.asarray([row["expanded_support_xyxy"] for row in rows
                              if row["transfer_split"] == name])
             for name in ("train", "validation", "test")}
    # Compare actual endpoint intervals, independently of verify_split's envelope.
    for left, right in (("test", "validation"), ("validation", "train"), ("test", "train")):
        assert np.all(boxes[left][:, 2, None] <= boxes[right][None, :, 0] - 16)
    record, arrays = sample(125)
    embargo = [r for r in window_records(record, arrays) if r["available"]]
    assert embargo
    assert all(r["transfer_split"] is None and r["transfer_exclusion_reason"] == "temporal_embargo"
               for r in embargo)
    tampered = copy.deepcopy(rows)
    wrong = next(row for row in tampered if row["transfer_split"] == "train")
    wrong["expanded_support_xyxy"][0] = 100.
    with pytest.raises(ValueError, match="Leaking"):
        verify_split(tampered)


def test_removing_centers_keeps_grid_geometry_pixels_and_normalization_identical():
    record, arrays = sample()
    without = dict(arrays, centers_xy=np.empty((0, 2)), boxes_xyxy=np.empty((0, 4)),
                   object_ids=np.array([], dtype="U64"))
    rows = [r for r in window_records(record, arrays) if r["sampler"] == "grid"]
    empty_rows = window_records(record, without)
    assert rows == empty_rows
    assert fit_normalizers([(record, arrays)]) == fit_normalizers([(record, without)])
    for row in rows:
        if row["available"]:
            assert np.array_equal(extract_patch(arrays, row), extract_patch(without, row))


class GeometryOnlyAugmentation:
    """Use real extraction with deterministic shifts and neutral photometry."""

    def __init__(self):
        self.shifts = iter([(2., -1.), (-2., 1.)])

    def uniform(self, low, high, size=None):
        if size is not None:
            return np.array(next(self.shifts))
        return 1. if low == .9 else 0.

    def normal(self, mean, sigma, shape):
        return np.zeros(shape)


def test_local_ssl_view_metadata_preserves_raw_correspondence():
    record, arrays = sample()
    row = next(r for r in window_records(record, arrays)
               if r["sampler"] == "centers" and r["element_id"] == "m0" and r["scale_raw_px"] == 64)
    normalizer = {"low": 0., "high": 2000.}
    views, metadata = augmented_pair(arrays, row, normalizer, GeometryOnlyAugmentation())
    assert views.shape == (2, 1, 64, 64)
    assert metadata["transforms"][0]["translation_raw_xy"] == [2., -1.]
    assert metadata["transforms"][1]["translation_raw_xy"] == [-2., 1.]
    assert metadata["pixels_per_output_pixel"] == 1
    # View0[j,i] and view1[j-2,i+4] are the same raw position. Matching equal
    # output indices would incorrectly enforce invariance across different places.
    np.testing.assert_allclose(views[0, 0, 2:, :-4], views[1, 0, :-2, 4:], rtol=0, atol=1e-7)


def make_analysis(directory, *, malformed=None):
    records = []
    for number in PILOT_NUMBERS:
        record, arrays = sample(number, origin=(224., 139.) if number <= 100 else (0., 0.), centers=())
        if malformed == "image_shape" and number == 1:
            arrays["image"] = arrays["image"][:-1]
            arrays["measured"] = arrays["measured"][:-1]
        if malformed == "origin_bounds" and number == 1:
            record["origin_in_expanded_xy"] = [225., 139.]
        relative = f"samples/{record['sample_id']}.npz"
        records.append(dict(record, file=relative, **write_arrays(directory / relative, arrays)))
    write_json(directory / "manifest.json", dict(schema="stmdomains-input-v1", samples=records))


@pytest.mark.parametrize("malformed", ["image_shape", "origin_bounds"])
def test_prepare_rejects_inconsistent_declared_geometry(tmp_path, malformed):
    directory = tmp_path / "analysis"
    make_analysis(directory, malformed=malformed)
    expected = "Image shape" if malformed == "image_shape" else "Registered field"
    with pytest.raises(ValueError, match=expected):
        prepare(directory, tmp_path / "prepared")
    assert not (tmp_path / "prepared").exists()


def test_prepare_rejects_absolute_sample_path_even_when_source_hash_is_valid(tmp_path):
    directory = tmp_path / "analysis"
    make_analysis(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    record = manifest["samples"][0]
    source_file = (directory / record["file"]).resolve()
    source_before = source_file.read_bytes()
    record["file"] = str(source_file)
    write_json(directory / "manifest.json", manifest)
    # This input is readable and hash-valid within the analysis tree, but its
    # absolute path must never be reused as a publication destination.
    loaded, _ = load_sample(directory, record["sample_id"])
    assert loaded["file"] == str(source_file)
    with pytest.raises(ValueError, match="sample identity or relative path"):
        prepare(directory, tmp_path / "prepared")
    assert not (tmp_path / "prepared").exists()
    assert source_file.read_bytes() == source_before


def test_prepare_is_unchanged_when_external_evaluation_is_replaced(tmp_path):
    directory = tmp_path / "analysis"
    make_analysis(directory)
    write_json(tmp_path / "evaluation/manifest.json", {"domain_labels": [1, 2, 3]})
    first = prepare(directory, tmp_path / "first")
    (tmp_path / "evaluation/manifest.json").unlink()
    write_json(tmp_path / "evaluation/other.json", {"domain_labels": [999]})
    second = prepare(directory, tmp_path / "second")
    assert first == second
    assert first["sample_count"] == 24
    for name in ("windows.jsonl", "normalization.json", "split.json", "analysis/manifest.json", "gpu-batch.npz"):
        assert (tmp_path / "first" / name).read_bytes() == (tmp_path / "second" / name).read_bytes()
    assert not (tmp_path / "first/evaluation").exists()
    with np.load(tmp_path / "first/gpu-batch.npz", allow_pickle=False) as batch:
        assert batch["patches"].shape[1:] == (1, 64, 64)
        assert np.isfinite(batch["patches"]).all()
    output = json.loads((tmp_path / "first/analysis/manifest.json").read_text())
    for record in output["samples"]:
        with np.load(tmp_path / "first/analysis" / record["file"], allow_pickle=False) as arrays:
            assert set(arrays.files) == INPUT_KEYS
