"""Fresh control invariants, evaluation isolation and repeatable publication."""

import json

import numpy as np
import pytest

from stmdomains.experiments import controls as original
from stmdomains.experiments.bundle import INPUT_KEYS, arrays_hash, file_hash, load_sample
from stmdomains.experiments.training.controls import CASES, EXTRA_CASES, FINAL_SEEDS, make_control, prepare


@pytest.mark.parametrize("seed", FINAL_SEEDS)
def test_gap_and_missing_annotations_have_identical_geometry_but_different_signal(seed):
    gap, gap_truth, gap_meta = make_control("empty_gap", seed)
    missing, missing_truth, missing_meta = make_control("missing_band", seed)
    full, full_truth, _ = original.make_control("single", seed)
    for key in ("centers_xy", "boxes_xyxy", "object_ids", "measured"):
        np.testing.assert_array_equal(gap[key], missing[key])
    np.testing.assert_array_equal(missing["image"], full["image"])
    np.testing.assert_array_equal(missing_truth["domain_labels"], full_truth["domain_labels"])
    assert np.max(np.abs(gap["image"] - missing["image"])) > .1
    assert np.all(gap_truth["domain_labels"][:, 78:114] == 0)
    assert gap_meta["expected_domain_count"] == 2
    assert missing_meta["expected_domain_count"] == 1
    assert gap_meta["pair_case"] == "missing_band"
    assert missing_meta["pair_case"] == "empty_gap"


@pytest.mark.parametrize("case", EXTRA_CASES)
def test_extra_controls_repeat_and_keep_truth_separate(case):
    first, truth, meta = make_control(case, FINAL_SEEDS[0])
    repeat, repeat_truth, repeat_meta = make_control(case, FINAL_SEEDS[0])
    changed, _, _ = make_control(case, FINAL_SEEDS[1])
    assert set(first) == INPUT_KEYS
    assert arrays_hash(first) == arrays_hash(repeat)
    assert arrays_hash(truth) == arrays_hash(repeat_truth)
    assert meta == repeat_meta
    assert arrays_hash(changed) != arrays_hash(first)
    assert np.isfinite(first["image"]).all()


def test_insufficient_field_is_not_labeled_as_disordered_or_scored_as_domain_failure():
    arrays, truth, meta = make_control("insufficient_field", FINAL_SEEDS[0])
    assert max(arrays["image"].shape) < meta["minimum_planned_support_reference_px"]
    assert meta["expected_state"] == "insufficient_data"
    assert meta["expected_domain_count"] is None
    assert np.all(truth["domain_labels"] == 1)
    assert not truth["evaluation_valid"].any()
    assert not truth["support_valid"].any()


def test_small_orientation_and_independent_rows_express_distinct_challenges():
    _, truth, meta = make_control("orientation_8deg", FINAL_SEEDS[0])
    assert meta["expected_domain_count"] == 2
    assert np.unique(truth["type_labels"]).tolist() == [1]
    assert np.unique(truth["orientation_deg"]).tolist() == [0., 8.]
    _, truth, meta = make_control("independent_rows", FINAL_SEEDS[0])
    assert not truth["domain_labels"].any()
    assert np.std(meta["row_phases_reference_px"]) > 1


def test_bundle_does_not_expose_evaluation_and_is_immutable(tmp_path):
    output = tmp_path / "first"
    audit = prepare(output)
    assert audit["sample_count"] == len(CASES) * len(FINAL_SEEDS) == 81
    assert audit["used_for_training"] is False
    manifest = json.loads((output / "analysis/manifest.json").read_text())
    forbidden = {"case", "seed", "expected_domain_count", "split", "paired_sample_id", "pair_case"}
    original_hashes = {}
    for record in manifest["samples"]:
        assert not forbidden.intersection(record)
        assert not record["file"].startswith("../")
        loaded_record, arrays = load_sample(output / "analysis", record["sample_id"])
        assert loaded_record == record
        original_hashes[record["sample_id"]] = arrays_hash(arrays)
    # Evaluation-only writes must not change analysis contents or loader output.
    (output / "evaluation/manifest.json").write_text('{"arbitrary_reference_change": true}\n')
    for record in manifest["samples"]:
        _, arrays = load_sample(output / "analysis", record["sample_id"])
        assert arrays_hash(arrays) == original_hashes[record["sample_id"]]
    with pytest.raises(FileExistsError):
        prepare(output)
    repeat = tmp_path / "second"
    repeated = prepare(repeat)
    assert repeated["analysis_manifest_sha256"] == audit["analysis_manifest_sha256"]
    for path in (output / "analysis").rglob("*"):
        if path.is_file():
            assert file_hash(path) == file_hash(repeat / path.relative_to(output))
