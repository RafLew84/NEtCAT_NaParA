"""Post-freeze E5 locality diagnostics on unchanged graph nodes and edges."""

from __future__ import annotations

import numpy as np

from .e2_metrics import edge_reference
from .training.evaluate import _edges, _positions, _vector, boundary_scores


def _ratio(numerator, denominator):
    return float(numerator / denominator) if denominator else None


def graph_boundary_metrics(reference, predicted, edges, eligible, *, reference_valid=None) -> dict:
    """Score graph cuts between positive reference instances, not pixel contours.

    Refusal is not a predicted cut. Recall over ALL eligible different-domain
    edges therefore counts refused endpoints as missed evidence. A separately
    named assigned-only recall excludes refusals; edge coverage and every
    denominator are retained. Unknown/zero labels never create a shared
    negative class. Labels may be renumbered without changing the result.
    """
    ref = np.asarray(reference)
    if ref.ndim != 1 or ref.dtype.kind not in "iu" or np.any(ref < 0):
        raise ValueError("Reference must be a nonnegative integer node vector")
    pred = _vector(predicted, len(ref), name="predicted")
    eligible = _vector(eligible, len(ref), name="eligible", dtype_kind="b")
    valid = np.ones(len(ref), bool) if reference_valid is None else _vector(
        reference_valid, len(ref), name="reference_valid", dtype_kind="b")
    pairs = _edges(edges, len(ref))
    a, b = pairs.T
    supported = eligible[a] & eligible[b]
    known = eligible & valid & (ref > 0)
    scored = known[a] & known[b]
    same = scored & (ref[a] == ref[b])
    different = scored & ~same
    assigned = scored & (pred[a] > 0) & (pred[b] > 0)
    cut = assigned & (pred[a] != pred[b])
    joined = assigned & ~cut
    correct_cut = cut & different
    false_cut = cut & same
    merged = joined & different
    n_correct, n_cut = int(correct_cut.sum()), int(cut.sum())
    n_different = int(different.sum())
    precision = _ratio(n_correct, n_cut)
    recall = _ratio(n_correct, n_different)
    f1 = (_ratio(2 * n_correct, n_cut + n_different) if n_different else None)
    counts = dict(planned_nodes=len(ref), eligible_nodes=int(eligible.sum()),
                  positive_reference_nodes=int(known.sum()),
                  assigned_positive_reference_nodes=int((known & (pred > 0)).sum()),
                  planned_edges=len(pairs), eligible_edges=int(supported.sum()),
                  reference_edges=int(scored.sum()), same_reference_edges=int(same.sum()),
                  different_reference_edges=n_different, assigned_reference_edges=int(assigned.sum()),
                  assigned_same_edges=int((assigned & same).sum()),
                  assigned_different_edges=int((assigned & different).sum()),
                  refused_reference_edges=int((scored & ~assigned).sum()),
                  refused_different_edges=int((different & ~assigned).sum()),
                  predicted_cut_edges=n_cut, correct_cut_edges=n_correct,
                  false_cut_edges=int(false_cut.sum()), merged_edges=int(merged.sum()),
                  correctly_joined_edges=int((joined & same).sum()))
    return dict(counts=counts, cut_precision=precision, cut_recall=recall, cut_f1=f1,
                assigned_only_cut_recall=_ratio(n_correct, counts["assigned_different_edges"]),
                assigned_edge_fraction=_ratio(counts["assigned_reference_edges"], counts["reference_edges"]),
                false_cut_rate_assigned_same=_ratio(counts["false_cut_edges"], counts["assigned_same_edges"]),
                merge_rate_assigned_different=_ratio(counts["merged_edges"], counts["assigned_different_edges"]),
                unavailable_reason="no_positive_reference_edges" if not scored.any() else (
                    "no_different_reference_edges" if not n_different else None),
                interpretation="Endpoint-instance graph cuts; not physical boundary localization")


def locality_metrics(rows, edges, truth, prediction, eligible, kind, regime, sampler,
                     *, pixel_spacing_xy=(1., 1.), tolerance=8.) -> dict:
    """Supplement evaluate_sample with graph cuts and the historical grid contour.

    ``rows`` must carry ORIGINAL graph/truth coordinates, but availability and
    split membership appropriate to the declared own/common comparison. Never
    pass extraction rows with snapped coordinates. ``eligible`` can further
    restrict feature availability, but cannot restore excluded reference scope.
    Real partial interiors yield graph relations only. Synthetic irregular
    center graphs also retain graph relations without pretending their edge
    midpoints form a full pixel boundary. Synthetic grids reuse E1/E3's exact
    positive-contact raster metric with its declared tolerance.
    """
    if sampler not in {"grid", "centers"}:
        raise ValueError("Unknown E5 sampler")
    xy = _positions(rows)
    if any("node_raw_edge_xy" in row and not np.array_equal(row["raw_edge_xy"], row["node_raw_edge_xy"])
           for row in rows):
        raise ValueError("Evaluate original graph anchors, not snapped extraction centers")
    pred = _vector(prediction, len(rows), name="prediction")
    eligible = _vector(eligible, len(rows), name="eligible", dtype_kind="b")
    ref = edge_reference(rows, edges, truth, kind, regime)
    scope = np.asarray([kind != "measurement" or regime != "transfer"
                        or row.get("transfer_split") == "test" for row in rows], bool)
    available = np.asarray([bool(row["available"]) for row in rows], bool)
    nodes = eligible & scope & available
    graph = graph_boundary_metrics(ref["labels"], pred, edges, nodes,
                                   reference_valid=ref["node_valid"])
    reason = ("partial_reference_has_no_exact_boundary" if kind == "measurement" else
              "irregular_center_graph_has_no_pixel_boundary" if sampler == "centers" else
              "boundary_raster_not_supplied" if truth.get("domain_labels") is None else None)
    raster = (dict(f1=None, precision=None, recall=None, unavailable_reason=reason)
              if reason else boundary_scores(xy, pred, edges, nodes, truth["domain_labels"],
                  pixel_spacing_xy=pixel_spacing_xy, tolerance=tolerance))
    return dict(graph_cuts=graph, raster_boundary=raster, reference_counts=ref["counts"],
                reference_scope=ref["reference_scope"],
                note="Use coverage and refusal counts alongside conditional split/merge rates")


def context_summary(context, eligible) -> dict:
    """JSON-ready context counts; exploratory rectangles remain separate."""
    labels = np.asarray(context["anchor_labels"])
    keep = _vector(eligible, len(labels), name="eligible", dtype_kind="b")
    known = np.asarray(context["reference_known_fraction"])
    positive = np.asarray(context["positive_instance_count"])
    anchor_valid = np.asarray(context["anchor_reference_valid"])
    inside = np.asarray(context["footprint_inside_reference"])
    if any(v.shape != keep.shape for v in (known, positive, anchor_valid, inside)):
        raise ValueError("Context arrays must align with eligibility")
    finite = np.isfinite(known)
    counts = dict(eligible_nodes=int(keep.sum()),
                  positive_known_anchors=int((keep & anchor_valid & (labels > 0)).sum()),
                  footprint_inside_reference=int((keep & inside).sum()),
                  fully_known_context=int((keep & finite & (known == 1)).sum()),
                  partly_known_context=int((keep & finite & (known > 0) & (known < 1)).sum()),
                  no_known_context=int((keep & (~finite | (known == 0))).sum()),
                  multiple_known_positive_instances=int((keep & (positive > 1)).sum()))
    for name in ("pure_synthetic", "known_interior_contained"):
        value = context[name]
        counts[name] = None if value is None else int((keep & _vector(
            value, len(labels), name=name, dtype_kind="b")).sum())
    rois = {name: dict(anchor_inside=int((keep & context["roi_anchor_inside"][name]).sum()),
                      footprint_contained=int((keep & value).sum()))
            for name, value in context["roi_contained"].items()}
    return dict(counts=counts, exploratory_rois=rois,
                reference_scope=context["reference_scope"],
                unavailable_reason=context["unavailable_reason"])
