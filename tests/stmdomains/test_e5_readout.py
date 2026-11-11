import copy
import csv
import gzip
import json

import numpy as np
import pytest

from stmdomains.experiments.e5_metrics import locality_metrics
from stmdomains.experiments.e5_readout import paired_deltas, seed_summary, summarize
from stmdomains.experiments.training.evaluate import aggregate_samples, evaluate_sample


def _write_jsonl(path, rows, compressed=False):
    opener = gzip.open if compressed else open
    with opener(path, "wt") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")


def test_readout_requires_completed_before_accessing_any_metrics(tmp_path):
    (tmp_path / "manifest.json").write_text('{"status":"running"}')
    with pytest.raises(ValueError, match="completed"):
        summarize(tmp_path)
    assert not list(tmp_path.glob("readout*"))


def test_common_deltas_reject_denominator_changes_but_own_is_not_a_paired_effect():
    base = dict(condition="scale_base", context="common", run_id="x", seed=1, n=3, coverage=.5)
    changed = dict(base, condition="scale32", n=4, coverage=1.)
    with pytest.raises(ValueError, match="denominator"):
        paired_deltas([base, changed], ("condition", "context"), ("coverage",), ("n",))
    rows = [dict(r, context="own") for r in (base, changed)]
    result = paired_deltas(rows, ("condition", "context"), ("coverage",), ("n",))
    assert all(r["delta_coverage"] is None for r in result)
    assert all(r["unavailable_reason"] for r in result)


def test_seed_summary_preserves_null_counts_and_deterministic_baseline():
    rows = [dict(family="fft", seed=None, rate=None)]
    summary = seed_summary(rows, ("family",), ("rate",))[0]
    assert summary["n_runs"] == 1
    assert summary["n_model_seeds"] == 0
    assert summary["metrics"]["rate"] == dict(n=0, median=None, min=None, max=None)
    with pytest.raises(ValueError, match="Repeated seed"):
        seed_summary(rows + rows, ("family",), ("rate",))


def test_completed_readout_pools_frame_counts_then_summarizes_seeds(tmp_path):
    (tmp_path / "manifest.json").write_text('{"status":"completed"}')
    (tmp_path / "prediction-freeze.json").write_text('{"files":{}}')
    aggregates, samples, supports = [], [], []
    for seed in (1, 2):
        for condition in ("map_base", "map_full"):
            metadata = dict(run_id=f"ae/{seed}", regime="transductive", family="ae", seed=seed,
                            sampler="centers", case="measurement", condition=condition, contrast="map",
                            context="common", partition="fh4", variant="H_M1")
            collected = []
            for frame, n in enumerate((2, 10)):
                rows = [dict(element_id=str(i), raw_edge_xy=[i + .5, .5], available=True,
                             transfer_split="test") for i in range(n)]
                labels = np.arange(n) % 2 + 1
                edges = np.column_stack((np.arange(n - 1), np.arange(1, n)))
                prediction = labels.copy()
                if seed == 1:
                    if condition == "map_base":
                        prediction[-1] = 0  # 1/2 + 9/10 => 10/12, not mean(.5,.9)
                    elif n == 10:
                        prediction[-2:] = 0  # 2/2 + 8/10 => also 10/12
                elif condition == "map_base":
                    prediction[:] = 0
                truth = dict(region_instances=labels)
                metric = evaluate_sample(rows, labels, prediction, prediction, edges, kind="measurement")
                locality = locality_metrics(rows, edges, truth, prediction, np.ones(n, bool),
                                             "measurement", "transductive", "centers")
                collected.append(metric)
                samples.append(dict(metadata, sample_id=str(frame), metrics=metric, locality=locality))
                smeta = {k: v for k, v in metadata.items() if k not in ("partition", "variant")}
                supports.append(dict(smeta, sample_id=str(frame), counts=dict(planned_nodes=n,
                    scope_nodes=n, available_nodes=n, feature_valid_nodes=n,
                    missing_baseline48_gate_nodes=0, common_lost_nodes=0)))
            aggregates.append(dict(metadata, metrics=aggregate_samples(collected)))
    with gzip.open(tmp_path / "domain-summary.json.gz", "wt") as stream:
        json.dump(dict(records=aggregates), stream)
    _write_jsonl(tmp_path / "metrics.jsonl.gz", samples, compressed=True)
    _write_jsonl(tmp_path / "support-summary.jsonl", supports)
    originals = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = summarize(tmp_path)
    assert result["rows"]["domain-seeds"] == 4
    with (tmp_path / "readout-domain-seeds.csv").open() as stream:
        per_seed = list(csv.DictReader(stream))
    first = next(r for r in per_seed if r["seed"] == "1" and r["condition"] == "map_base")
    assert float(first["after_positive_reference_coverage"]) == pytest.approx(10 / 12)
    assert first["after_raster_boundary_f1"] == ""
    with (tmp_path / "readout-delta-summary.csv").open() as stream:
        delta = next(r for r in csv.DictReader(stream) if r["condition"] == "map_full")
    assert float(delta["metrics.delta_after_positive_reference_coverage.median"]) == .5
    with (tmp_path / "readout-domain-summary.csv").open() as stream:
        summary = next(r for r in csv.DictReader(stream) if r["condition"] == "map_base")
    assert float(summary["metrics.after_positive_reference_coverage.median"]) == pytest.approx(5 / 12)
    assert summary["metrics.after_raster_boundary_f1.n"] == "0"
    for name, content in originals.items():
        assert (tmp_path / name).read_bytes() == content
    assert json.loads((tmp_path / "readout-manifest.json").read_text())["prediction_changes"] is False
