"""Paired E3 changes with explicit support and no label-number comparisons."""

from __future__ import annotations

import numpy as np
from scipy.stats import rankdata

from .results import pair_scores
from .training.evaluate import _edges
from .training.partition import relation_weights


def _ratio(numerator, denominator):
    return float(numerator / denominator) if denominator else None


def feature_change(base, changed, mask) -> dict:
    """Return node-aligned Euclidean changes; relative change uses ||base||.

    Zero input vectors are retained for absolute/norm diagnostics. Their
    relative change is unavailable, without adding an arbitrary denominator.
    NaN outputs mark out-of-scope/nonfinite nodes; counts retain those losses.
    This accepts any declared feature space but never mixes spaces in a fit.
    """
    base, changed = np.asarray(base, float), np.asarray(changed, float)
    mask = np.asarray(mask, bool)
    if base.ndim != 2 or not base.shape[1] or changed.shape != base.shape or mask.shape != base.shape[:1]:
        raise ValueError("Feature matrices and node mask must align")
    finite = np.isfinite(base).all(1) & np.isfinite(changed).all(1)
    valid = mask & finite
    arrays = {name: np.full(len(base), np.nan) for name in
              ("absolute_l2", "relative_l2", "base_norm", "changed_norm", "norm_change")}
    arrays["base_norm"][valid] = np.linalg.norm(base[valid], axis=1)
    arrays["changed_norm"][valid] = np.linalg.norm(changed[valid], axis=1)
    arrays["absolute_l2"][valid] = np.linalg.norm(changed[valid] - base[valid], axis=1)
    arrays["norm_change"][valid] = arrays["changed_norm"][valid] - arrays["base_norm"][valid]
    relative_valid = valid & (arrays["base_norm"] > 0)
    arrays["relative_l2"][relative_valid] = arrays["absolute_l2"][relative_valid] / arrays["base_norm"][relative_valid]
    return dict(**arrays, valid=valid, relative_valid=relative_valid, counts=dict(
        planned_nodes=len(base), eligible_nodes=int(mask.sum()), compared_nodes=int(valid.sum()),
        excluded_scope_nodes=int((~mask).sum()), excluded_nonfinite_nodes=int((mask & ~finite).sum()),
        relative_nodes=int(relative_valid.sum()), zero_base_norm_nodes=int((valid & ~relative_valid).sum())))


def distance_change(base, changed, edges, eligible, q25=None, q75=None) -> dict:
    """Compare fixed edge distances, and optionally fixed calibrated relations.

    ``eligible`` is an E-vector shared by both conditions. Spearman uses
    average ranks for ties; constant or fewer than two distances give None.
    Pass E2 q25/q75 only for adapted distances. None/None leaves relation
    changes unavailable in uncalibrated native/L2 spaces. No threshold fit is
    performed. Transition rows are base, columns changed, in the given order.
    """
    base, changed = np.asarray(base, float), np.asarray(changed, float)
    eligible = np.asarray(eligible, bool)
    pairs = np.asarray(edges)
    if pairs.size == 0:
        pairs = np.empty((0, 2), int)
    if pairs.ndim != 2 or pairs.shape[1] != 2 or pairs.dtype.kind not in "iu":
        raise ValueError("Edges must be an integer E-by-2 array")
    _edges(pairs, int(pairs.max()) + 1 if len(pairs) else 0)
    if base.shape != (len(pairs),) or changed.shape != base.shape or eligible.shape != base.shape:
        raise ValueError("Distance vectors, edges and pair eligibility must align")
    finite = np.isfinite(base) & np.isfinite(changed)
    valid = eligible & finite
    if np.any(base[valid] < 0) or np.any(changed[valid] < 0):
        raise ValueError("Distances must be nonnegative")
    delta = changed[valid] - base[valid]
    count = len(delta)
    reason = "fewer_than_two_pairs" if count < 2 else (
        "constant_base_distances" if np.ptp(base[valid]) == 0 else
        "constant_changed_distances" if np.ptp(changed[valid]) == 0 else None)
    rho = None
    if reason is None:
        left, right = rankdata(base[valid]), rankdata(changed[valid])
        rho = float(np.corrcoef(left, right)[0, 1])
    result = dict(
        counts=dict(planned_pairs=len(base), eligible_pairs=int(eligible.sum()), compared_pairs=count,
                    excluded_scope_pairs=int((~eligible).sum()), excluded_nonfinite_pairs=int((eligible & ~finite).sum())),
        rmse=float(np.sqrt(np.mean(delta ** 2))) if count else None,
        median_absolute_change=float(np.median(np.abs(delta))) if count else None,
        spearman=rho, spearman_unavailable_reason=reason,
        relation_order=["attractive", "neutral", "repulsive"], relation_transitions=None,
        relation_changed_pairs=None, relation_change_fraction=None,
        relation_unavailable_reason="no_calibrated_thresholds",
    )
    if q25 is None and q75 is None:
        return result
    if q25 is None or q75 is None:
        raise ValueError("Supply both frozen relation thresholds or neither")
    before, _ = relation_weights(base[valid], q25, q75)
    after, _ = relation_weights(changed[valid], q25, q75)
    names = ("attractive", "none", "repulsive")
    transitions = [[int(((before == a) & (after == b)).sum()) for b in names] for a in names]
    changed_count = int((before != after).sum())
    result.update(relation_transitions=transitions, relation_changed_pairs=changed_count,
                  relation_change_fraction=_ratio(changed_count, count),
                  relation_unavailable_reason=None if count else "no_compared_pairs")
    return result


def assignment_stability(base_labels, new_labels, edges, scope) -> dict:
    """Compare assignment status on all scope, partition only where both assign.

    Positive integers denote components; nonpositive values are refusals. A
    bijective relabeling therefore has zero disagreement. Pair disagreement
    covers ALL unordered pairs of jointly assigned nodes within this sample.
    Boundary Jaccard covers only existing graph edges whose endpoints are
    jointly assigned in both conditions, not pixel contours or unseen gaps.
    Empty unions return None, never perfect stability of two empty results.
    """
    base, changed = np.asarray(base_labels), np.asarray(new_labels)
    scope = np.asarray(scope, bool)
    if (base.ndim != 1 or base.dtype.kind not in "iu" or changed.dtype.kind not in "iu"
            or changed.shape != base.shape or scope.shape != base.shape):
        raise ValueError("Integer assignment vectors and node scope must align")
    pairs = _edges(edges, len(base))
    before, after = scope & (base > 0), scope & (changed > 0)
    both, either = before & after, before | after
    status_changed = scope & ((base > 0) != (changed > 0))
    scores = pair_scores(base[both], changed[both])
    n_both = int(both.sum())
    n_pairs = n_both * (n_both - 1) // 2
    disagreed = scores["split_pairs"] + scores["merged_pairs"]
    u, v = pairs.T
    in_scope = scope[u] & scope[v]
    comparable = both[u] & both[v]
    boundary_before = comparable & (base[u] != base[v])
    boundary_after = comparable & (changed[u] != changed[v])
    boundary_union = int((boundary_before | boundary_after).sum())
    boundary_intersection = int((boundary_before & boundary_after).sum())
    return dict(
        counts=dict(planned_nodes=len(base), scope_nodes=int(scope.sum()),
                    base_assigned_nodes=int(before.sum()), changed_assigned_nodes=int(after.sum()),
                    assigned_intersection_nodes=n_both, assigned_union_nodes=int(either.sum()),
                    lost_assignment_nodes=int((before & ~after).sum()),
                    gained_assignment_nodes=int((after & ~before).sum()),
                    assignment_status_changed_nodes=int(status_changed.sum()),
                    compared_pairs=n_pairs, partition_disagreed_pairs=disagreed,
                    split_pairs=scores["split_pairs"], merged_pairs=scores["merged_pairs"],
                    planned_edges=len(pairs), scope_edges=int(in_scope.sum()),
                    compared_boundary_edges=int(comparable.sum()),
                    excluded_unassigned_edges=int((in_scope & ~comparable).sum()),
                    base_boundary_edges=int(boundary_before.sum()), changed_boundary_edges=int(boundary_after.sum()),
                    boundary_intersection_edges=boundary_intersection, boundary_union_edges=boundary_union),
        assignment_jaccard=_ratio(n_both, int(either.sum())),
        assignment_status_change_fraction=_ratio(int(status_changed.sum()), int(scope.sum())),
        pairwise_partition_disagreement=_ratio(disagreed, n_pairs),
        boundary_edge_jaccard=_ratio(boundary_intersection, boundary_union),
        assignment_unavailable_reason="empty_assignment_union" if not either.any() else None,
        partition_unavailable_reason="fewer_than_two_jointly_assigned_nodes" if not n_pairs else None,
        boundary_unavailable_reason="no_comparable_edges" if not comparable.any() else
                                    "empty_boundary_union" if not boundary_union else None,
    )
