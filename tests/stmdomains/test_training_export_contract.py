"""Export metadata preserves predictions and raw/reference-pixel geometry."""
import copy

import numpy as np
import pytest

from stmdomains.experiments.bundle import file_hash, write_json
from stmdomains.experiments.training.export_contract import finalize, normalize_element
from stmdomains.experiments.training.predict import read_json, write_gzip


def element(factor=1., available=True):
    return dict(element_id="g-40-40", raw_edge_xy=[40 / factor, 40 / factor],
                feature_support_xyxy=[16 / factor, 16 / factor, 64 / factor, 64 / factor],
                support_xyxy=[13 / factor, 13 / factor, 67 / factor, 67 / factor],
                pixel_spacing_xy=[factor, factor], position_unit="raw_px",
                scale_px=48, scale_raw_px=48 / factor, available=available)


@pytest.mark.parametrize("kind,factor,unit", [("measurement", 1., "px"),
                                            ("synthetic", .5, "reference_px")])
def test_supports_keep_raw_geometry_and_explicit_scale_units(kind, factor, unit):
    old = element(factor, available=False)
    before = copy.deepcopy(old)
    result = normalize_element(old, kind=kind)
    assert old == before
    assert result["support_xyxy"] == old["feature_support_xyxy"]
    assert result["effective_support_xyxy"] == old["support_xyxy"]
    assert result["availability"] == "unavailable"
    assert result["units"]["scale_px"] == unit
    assert result["units"]["effective_support_xyxy"] == "raw_px"
    assert normalize_element(result, kind=kind) == result
    np.testing.assert_allclose(np.array(result["effective_support_xyxy"]) * factor,
                               [13, 13, 67, 67])


def test_finalize_changes_only_element_metadata_and_is_idempotent(tmp_path):
    folder = tmp_path / "predictions/transfer/ae/grid/s48/sample/fh4"
    row = element()
    payload = dict(schema="stmdomains-result-v1", sample_id="sample", input_content_sha256="a" * 64,
                   run_id="run", catalogue_id=None,
                   assignments=[dict(element_id=row["element_id"], xy=row["raw_edge_xy"],
                       support_xyxy=row["feature_support_xyxy"], state="ordered_untyped", reason=None,
                       type_id=None, domain_id="domain-1", orientation_deg=None)],
                   extensions=dict(training_v1=dict(elements=[row],
                       proposals=[dict(element_id=row["element_id"], component_id="proposal-1")],
                       relations_artifact=dict(path="relations.json.gz"))))
    write_gzip(folder / "result.json.gz", payload)
    write_gzip(folder / "heldout-result.json.gz", payload)
    write_gzip(folder / "relations.json.gz", [dict(u="a", v="b", strength=.7)])
    write_gzip(folder / "heldout-relations.json.gz", [])
    np.savez(folder / "metrics-input.npz", before=np.array([1]), after=np.array([1]))
    np.savez(folder / "heldout-metrics-input.npz", before=np.array([1]), after=np.array([1]))
    write_json(tmp_path / "predictions/index.json", [dict(directory=str(folder.relative_to(tmp_path)),
               kind="measurement", evaluation_input="heldout-metrics-input.npz")])
    report = finalize(tmp_path)
    assert report["passed"] and report["results_updated"] == 2
    assert report["protected_files_checked"] == 4
    saved = read_json(folder / "result.json.gz")
    assert saved["assignments"] == payload["assignments"]
    assert saved["extensions"]["training_v1"]["proposals"] == payload["extensions"]["training_v1"]["proposals"]
    assert saved["extensions"]["training_v1"]["elements"][0]["units"]["scale_px"] == "px"
    previous_hash = file_hash(folder / "result.json.gz")
    second = finalize(tmp_path)
    assert second["results_updated"] == 0
    assert file_hash(folder / "result.json.gz") == previous_hash
    assert report["non_element_payload_before_sha256"] == second["non_element_payload_after_sha256"]
    write_json(tmp_path / "frozen-predictions.json", {})
    with pytest.raises(ValueError, match="already frozen"):
        finalize(tmp_path)


def test_finalize_rejects_incomplete_partition(tmp_path):
    with pytest.raises(ValueError, match="Completed partition index"):
        finalize(tmp_path)
