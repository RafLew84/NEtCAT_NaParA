import numpy as np
import pytest

from stmdomains.experiments.e5_metrics import (
    context_summary, graph_boundary_metrics, locality_metrics,
)
from stmdomains.experiments.e5_support import footprint_context


def test_graph_cut_denominators_include_refused_boundary_and_ignore_label_numbers():
    truth = np.array([1, 1, 2, 2, 3, 3])
    edges = np.array([[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 0]])
    prediction = np.array([10, 11, 11, 11, 12, 0])
    mask = np.ones(6, bool)
    result = graph_boundary_metrics(truth, prediction, edges, mask)
    assert result["counts"]["different_reference_edges"] == 3
    assert result["counts"]["refused_different_edges"] == 1
    assert result["cut_precision"] == .5
    assert result["cut_recall"] == pytest.approx(1 / 3)
    assert result["assigned_only_cut_recall"] == .5
    assert result["cut_f1"] == .4
    remapped = np.array([7, 100, 100, 100, 3, -1])
    assert graph_boundary_metrics(truth, remapped, edges, mask) == result


def test_missing_class_and_all_refused_are_not_perfect_boundaries():
    edges = [[0, 1]]
    mask = np.ones(2, bool)
    single = graph_boundary_metrics(np.array([1, 1]), [1, 2], edges, mask)
    assert single["cut_f1"] is None
    assert single["cut_recall"] is None
    assert single["false_cut_rate_assigned_same"] == 1
    refused = graph_boundary_metrics(np.array([1, 2]), [0, 0], edges, mask)
    assert refused["cut_precision"] is None
    assert refused["cut_recall"] == 0
    assert refused["cut_f1"] == 0
    unknown = graph_boundary_metrics(np.array([0, 0]), [1, 2], edges, mask)
    assert unknown["counts"]["reference_edges"] == 0
    assert unknown["cut_f1"] is None


def _rows():
    return [dict(element_id=str(i), raw_edge_xy=xy, available=True, transfer_split="test")
            for i, xy in enumerate(([2., 4.], [6., 4.]))]


def test_exact_raster_boundary_only_for_synthetic_grid():
    raster = np.ones((8, 8), int)
    raster[:, 4:] = 2
    args = (_rows(), [[0, 1]], dict(domain_labels=raster), [1, 2], np.ones(2, bool), "synthetic", "transfer")
    grid = locality_metrics(*args, "grid", tolerance=4)
    assert grid["graph_cuts"]["cut_f1"] == 1
    assert grid["raster_boundary"]["f1"] == 1
    centers = locality_metrics(*args, "centers", tolerance=4)
    assert centers["graph_cuts"]["cut_f1"] == 1
    assert centers["raster_boundary"]["f1"] is None


def test_partial_real_scope_and_uncertainty_remain_excluded():
    truth = dict(region_instances=np.array([1, 2]))
    rows = _rows()
    result = locality_metrics(rows, [[0, 1]], truth, [1, 2], np.ones(2, bool),
                              "measurement", "transfer", "grid")
    assert result["graph_cuts"]["cut_f1"] == 1
    assert result["raster_boundary"]["f1"] is None
    rows[0]["transfer_split"] = "train"
    no_pair = locality_metrics(rows, [[0, 1]], truth, [1, 2], np.ones(2, bool),
                               "measurement", "transfer", "centers")
    assert no_pair["graph_cuts"]["counts"]["reference_edges"] == 0
    rows[0]["transfer_split"] = "test"
    truth["boundary_uncertain"] = np.array([False, True])
    uncertain = locality_metrics(rows, [[0, 1]], truth, [1, 2], np.ones(2, bool),
                                 "measurement", "transfer", "centers")
    assert uncertain["graph_cuts"]["counts"]["reference_edges"] == 0


def test_extraction_rows_with_moved_truth_anchors_are_rejected():
    rows = _rows()
    rows[0]["node_raw_edge_xy"] = [1., 4.]
    with pytest.raises(ValueError, match="original graph anchors"):
        locality_metrics(rows, [[0, 1]], {}, [1, 2], np.ones(2, bool),
                         "measurement", "transductive", "centers")


def test_context_summary_preserves_unknown_and_distinguishes_real_from_synthetic():
    context = footprint_context([[3., 3.], [1., 1.]], 4, {}, "measurement",
                                 rois=[dict(id="A", bbox_xyxy=[0, 0, 8, 8])])
    result = context_summary(context, np.ones(2, bool))
    assert result["counts"]["pure_synthetic"] is None
    assert result["counts"]["known_interior_contained"] == 0
    assert result["counts"]["no_known_context"] == 2
    assert result["exploratory_rois"]["A"] == dict(anchor_inside=2, footprint_contained=1)
