"""Post-freeze E2 pair diagnostics; no fitting, label creation or graph changes."""

from __future__ import annotations

import numpy as np

from .training.evaluate import _edges, _positions, _sample


def edge_reference(rows, edges, truth, kind, regime) -> dict:
    """Label existing pairs using positive domain instances at their endpoints.

    ``truth`` is an evaluation bundle dict. Its arrays may be rasters or node
    vectors. Measurement transfer scores only old test rows. Unknown real zero
    and known synthetic no-domain zero are both outside this two-domain task;
    neither creates a negative pair. Uncertain boundary pixels stay unscored.
    No requirement is imposed on the intervening line or entire patch: this
    tests endpoint relations, not exact localization of a physical boundary.

    The caller must freeze features, adapters and graph predictions before
    accessing truth, then intersect ``valid`` with feature availability. The
    same helper accepts all unordered within-frame pairs for a separately
    named interior-separability diagnostic; never combine IDs across frames.
    """
    if kind not in {"measurement", "synthetic"} or regime not in {"transfer", "transductive"}:
        raise ValueError("Unknown reference kind or regime")
    xy = _positions(rows)
    pairs = _edges(edges, len(rows))
    a, b = pairs.T
    key = "region_instances" if kind == "measurement" else "domain_labels"
    values = truth.get(key)
    labels = _sample(values, xy, name=key, fill=0, dtype_kind="iu")
    if np.any(labels < 0):
        raise ValueError("Reference labels must be nonnegative")
    reference_valid = _sample(truth.get("evaluation_valid"), xy, name="evaluation_valid",
                              fill=values is not None, dtype_kind="b")
    uncertain = np.zeros(len(rows), bool)
    for name in ("boundary_uncertain", "boundary_unscored"):
        uncertain |= _sample(truth.get(name), xy, name=name, fill=False, dtype_kind="b")
    if values is None:
        reference_valid = np.zeros(len(rows), bool)
    reference_valid = reference_valid & ~uncertain
    scope = np.asarray([kind != "measurement" or regime != "transfer"
                        or row.get("transfer_split") == "test" for row in rows], bool)
    available = np.asarray([bool(row["available"]) for row in rows], bool)
    full = scope & available
    evaluated = full & reference_valid
    positive = labels > 0
    node_valid = evaluated & positive
    scope_pairs = scope[a] & scope[b]
    full_pairs = full[a] & full[b]
    evaluated_pairs = evaluated[a] & evaluated[b]
    valid = node_valid[a] & node_valid[b]
    same = valid & (labels[a] == labels[b])
    different = valid & ~same
    counts = dict(
        planned_nodes=len(rows), scope_nodes=int(scope.sum()), full_support_nodes=int(full.sum()),
        evaluated_nodes=int(evaluated.sum()), positive_reference_nodes=int(node_valid.sum()),
        uncertain_full_support_nodes=int((full & uncertain).sum()),
        unscored_full_support_nodes=int((full & ~reference_valid).sum()),
        known_zero_nodes=int((evaluated & ~positive).sum()) if kind == "synthetic" else 0,
        planned_pairs=len(pairs), scope_pairs=int(scope_pairs.sum()),
        full_support_pairs=int(full_pairs.sum()), evaluated_pairs=int(evaluated_pairs.sum()),
        positive_reference_pairs=int(valid.sum()), same_pairs=int(same.sum()),
        different_pairs=int(different.sum()),
        excluded_out_of_scope_pairs=int((~scope_pairs).sum()),
        excluded_support_pairs=int((scope_pairs & ~full_pairs).sum()),
        excluded_reference_pairs=int((full_pairs & ~evaluated_pairs).sum()),
        excluded_nonpositive_pairs=int((evaluated_pairs & ~valid).sum()),
    )
    reason = "missing_reference" if values is None else (
        "no_positive_reference_pairs" if not valid.any() else None)
    return dict(valid=valid, same=same, different=different, node_valid=node_valid,
                labels=labels, counts=counts, unavailable_reason=reason,
                reference_scope="conservative_interiors" if kind == "measurement" else "generator_domains")


def _quantiles(values) -> dict | None:
    if not len(values):
        return None
    return dict(zip(("min", "q05", "q25", "median", "q75", "q95", "max"),
                    np.quantile(values, (0., .05, .25, .5, .75, .95, 1.)).tolist()))


def pair_summary(distance, same, eligible, *, max_curve_points=512) -> dict:
    """Summarize fixed pairs; high distance predicts DIFFERENT positive domains.

    ``eligible`` must already combine reference and chosen feature masks. Use
    their intersection across compared representations for the primary paired
    comparison, and each representation's own mask as a secondary denominator.
    NaN/inf distances are explicitly counted and excluded, never imputed.

    ROC-AUC uses the full tie-grouped ROC; average precision is the sum of
    recall increments times precision at each tied score threshold, not a
    trapezoidal PR area. Both require both classes for this discrimination
    diagnostic. No weights, threshold selection, balancing or significance
    tests are performed: graph edges share nodes and are not independent.

    Curves use descending thresholds and predict distance >= threshold. Their
    first threshold is None (no positive predictions). Metric calculations use
    every distinct score; at most ``max_curve_points`` evenly indexed curve
    points are stored, including both endpoints. None keeps complete curves.
    """
    distances = np.asarray(distance, float)
    same = np.asarray(same, bool)
    eligible = np.asarray(eligible, bool)
    if distances.ndim != 1 or same.shape != distances.shape or eligible.shape != distances.shape:
        raise ValueError("Distances, same and eligible must be equally sized vectors")
    if max_curve_points is not None and (isinstance(max_curve_points, bool)
            or not isinstance(max_curve_points, (int, np.integer)) or max_curve_points < 2):
        raise ValueError("Curve limit must be an integer >=2 or None")
    finite = np.isfinite(distances)
    selected = eligible & finite
    if np.any(distances[selected] < 0):
        raise ValueError("Pair distances must be nonnegative")
    values = distances[selected]
    positive = ~same[selected]
    n_positive = int(positive.sum())
    n_negative = int((~positive).sum())
    reason = ("no_eligible_pairs" if not eligible.any() else "no_finite_distances" if not len(values)
              else "no_different_pairs" if not n_positive else "no_same_pairs" if not n_negative else None)
    result = dict(
        counts=dict(planned_pairs=len(distances), eligible_pairs=int(eligible.sum()),
                    excluded_ineligible_pairs=int((~eligible).sum()),
                    excluded_nonfinite_pairs=int((eligible & ~finite).sum()),
                    scored_pairs=len(values), same_pairs=n_negative, different_pairs=n_positive),
        boundary_prevalence=float(n_positive / len(values)) if len(values) else None,
        roc_auc=None, average_precision=None, unavailable_reason=reason,
        quantiles=dict(same=_quantiles(values[~positive]), different=_quantiles(values[positive])),
        roc=None, pr=None,
    )
    if reason is not None:
        return result

    order = np.argsort(-values, kind="stable")
    scores, target = values[order], positive[order]
    group_end = np.r_[np.flatnonzero(np.diff(scores) != 0), len(scores) - 1]
    tp = np.r_[0, np.cumsum(target, dtype=np.int64)[group_end]]
    fp = np.r_[0, (group_end + 1) - tp[1:]]
    tpr, fpr = tp / n_positive, fp / n_negative
    precision = np.ones(len(tp), float)
    np.divide(tp[1:], tp[1:] + fp[1:], out=precision[1:])
    result["roc_auc"] = float(np.sum(np.diff(fpr) * (tpr[1:] + tpr[:-1]) / 2))
    result["average_precision"] = float(np.sum(np.diff(tpr) * precision[1:]))
    thresholds = [None] + scores[group_end].tolist()
    n_points = len(thresholds)
    keep = (np.arange(n_points) if max_curve_points is None or n_points <= max_curve_points
            else np.linspace(0, n_points - 1, max_curve_points, dtype=int))
    metadata = dict(thresholds=[thresholds[i] for i in keep], full_points=n_points,
                    stored_points=len(keep), decimated=len(keep) < n_points)
    result["roc"] = dict(fpr=fpr[keep].tolist(), tpr=tpr[keep].tolist(), **metadata)
    result["pr"] = dict(precision=precision[keep].tolist(), recall=tpr[keep].tolist(), **metadata)
    return result
