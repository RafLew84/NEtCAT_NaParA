"""Post-freeze evaluation with explicit denominators and partial-reference scope.

This module never trains, tunes, selects checkpoints or reads references on
import. Callers must freeze predictions before loading truth. Component IDs
are positive integers; zero/negative values represent refusals, never a domain.
"""

from __future__ import annotations

from collections import Counter
import argparse
import csv
import gzip
import itertools
import json
import math
from pathlib import Path
import resource
import tempfile
import time

import numpy as np
from scipy.spatial import cKDTree

from ..bundle import arrays_hash, file_hash, load_sample, write_json
from ..results import pair_scores

BOUNDARY_CASES = {"two_orientations", "different_spacing", "phase_boundary", "orientation_8deg"}
ZERO_CASES = {"random", "random_minsep", "random_gradient", "noise", "stripes", "independent_rows"}
TWO_CASES = BOUNDARY_CASES | {"disjoint", "empty_gap"}
ABLATION_CASES = {"missing_10", "missing_30", "missing_50", "missing_local", "missing_band"}


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    return float(numerator / denominator) if denominator else None


def _vector(value, n: int, *, name: str, dtype_kind="iu") -> np.ndarray:
    result = np.asarray(value)
    if result.shape != (n,) or result.dtype.kind not in dtype_kind:
        raise ValueError(f"{name} must be a length-{n} vector of {dtype_kind}")
    return result


def _positions(rows: list[dict]) -> np.ndarray:
    xy = np.asarray([row["raw_edge_xy"] for row in rows], dtype=float).reshape(-1, 2)
    if not np.isfinite(xy).all():
        raise ValueError("Non-finite evaluation coordinates")
    identifiers = [row["element_id"] for row in rows]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Evaluate one sample/scale/sampler at a time; element IDs must be unique")
    return xy


def _sample(values, xy: np.ndarray, *, name: str, fill, dtype_kind) -> np.ndarray:
    """Sample pixel-edge coordinates by their containing pixel, without clipping."""
    if values is None:
        return np.full(len(xy), fill)
    values = np.asarray(values)
    if values.dtype.kind not in dtype_kind:
        raise ValueError(f"Invalid dtype for {name}")
    if values.ndim == 1:
        return _vector(values, len(xy), name=name, dtype_kind=dtype_kind)
    if values.ndim != 2:
        raise ValueError(f"{name} must be a vector or raster")
    indices = np.floor(xy).astype(int)
    inside = np.all(indices >= 0, axis=1) & (indices[:, 0] < values.shape[1]) & (indices[:, 1] < values.shape[0])
    if not inside.all():
        raise ValueError(f"Coordinates escape {name} raster")
    return values[indices[:, 1], indices[:, 0]]


def _edges(edges, n: int) -> np.ndarray:
    result = np.asarray(edges)
    if result.size == 0:
        return np.empty((0, 2), dtype=np.int64)
    if result.ndim != 2 or result.shape[1] != 2 or result.dtype.kind not in "iu":
        raise ValueError("Edges must be an integer E-by-2 array")
    if (result < 0).any() or (result >= n).any() or (result[:, 0] == result[:, 1]).any():
        raise ValueError("Invalid edge endpoint")
    canonical = np.sort(result, axis=1)
    if len(np.unique(canonical, axis=0)) != len(canonical):
        raise ValueError("Repeated undirected edge would duplicate the denominator")
    return canonical


def local_pair_scores(reference, predicted, edges) -> dict:
    """The pair_scores convention restricted to actual undirected graph edges."""
    ref = np.asarray(reference)
    pred = _vector(predicted, len(ref), name="predicted")
    ref = _vector(ref, len(pred), name="reference")
    edge = _edges(edges, len(ref))
    u, v = edge.T
    reference_pair = (ref[u] > 0) & (ref[v] > 0)
    assigned_pair = reference_pair & (pred[u] > 0) & (pred[v] > 0)
    same = (ref[u] == ref[v]) & assigned_pair
    different = (ref[u] != ref[v]) & assigned_pair
    split = same & (pred[u] != pred[v])
    merged = different & (pred[u] == pred[v])
    return dict(
        graph_edges=len(edge), reference_edges=int(reference_pair.sum()),
        assigned_edges=int(assigned_pair.sum()),
        assigned_edge_fraction=_ratio(assigned_pair.sum(), reference_pair.sum()),
        same_reference_pairs=int(same.sum()), different_reference_pairs=int(different.sum()),
        split_pairs=int(split.sum()), merged_pairs=int(merged.sum()),
        split_rate=_ratio(split.sum(), same.sum()), merge_rate=_ratio(merged.sum(), different.sum()),
    )


def _line_samples(indices: np.ndarray, spacing: float) -> np.ndarray:
    """Merge adjacent raster edge segments before sampling at 1 reference px."""
    pieces = []
    for run in np.split(indices, np.flatnonzero(np.diff(indices) > 1) + 1):
        if not len(run):
            continue
        start, end = float(run[0] * spacing), float((run[-1] + 1) * spacing)
        points = np.arange(start + .5, end, 1.)
        pieces.extend(points.tolist() if len(points) else [(start + end) / 2])
    return np.asarray(pieces)


def positive_boundary_points(truth_raster, pixel_spacing_xy=(1., 1.)) -> np.ndarray:
    """Only contacts between different positive domains, excluding outer/zero edges."""
    truth = np.asarray(truth_raster)
    spacing = np.asarray(pixel_spacing_xy, dtype=float)
    if truth.ndim != 2 or truth.dtype.kind not in "iu" or spacing.shape != (2,) or not np.isfinite(spacing).all() or (spacing <= 0).any():
        raise ValueError("Boundary truth needs an integer raster and finite positive pixel spacing")
    sx, sy = spacing
    vertical = (truth[:, :-1] > 0) & (truth[:, 1:] > 0) & (truth[:, :-1] != truth[:, 1:])
    horizontal = (truth[:-1, :] > 0) & (truth[1:, :] > 0) & (truth[:-1, :] != truth[1:, :])
    points = []
    for col in np.flatnonzero(vertical.any(axis=0)):
        y = _line_samples(np.flatnonzero(vertical[:, col]), sy)
        points.extend(zip(np.full(len(y), (col + 1) * sx), y))
    for row in np.flatnonzero(horizontal.any(axis=1)):
        x = _line_samples(np.flatnonzero(horizontal[row]), sx)
        points.extend(zip(x, np.full(len(x), (row + 1) * sy)))
    return np.unique(np.asarray(points, dtype=float).reshape(-1, 2), axis=0)


def boundary_scores(xy, predicted, edges, eligible, truth_raster, *, pixel_spacing_xy=(1., 1.), tolerance=8.) -> dict:
    xy = np.asarray(xy, dtype=float)
    pred = _vector(predicted, len(xy), name="predicted")
    eligible = _vector(eligible, len(xy), name="eligible", dtype_kind="b")
    edge = _edges(edges, len(xy))
    if not np.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Invalid boundary tolerance")
    delta = np.abs(xy[edge[:, 0]] - xy[edge[:, 1]])
    axial = np.isclose(delta[:, 0], 0, rtol=0, atol=1e-9) ^ np.isclose(delta[:, 1], 0, rtol=0, atol=1e-9)
    u, v = edge.T
    chosen = axial & eligible[u] & eligible[v] & (pred[u] > 0) & (pred[v] > 0) & (pred[u] != pred[v])
    points = (xy[u[chosen]] + xy[v[chosen]]) / 2 * np.asarray(pixel_spacing_xy)
    truth = positive_boundary_points(truth_raster, pixel_spacing_xy)
    matched_prediction = int((cKDTree(truth).query(points)[0] <= tolerance).sum()) if len(truth) and len(points) else 0
    matched_truth = int((cKDTree(points).query(truth)[0] <= tolerance).sum()) if len(truth) and len(points) else 0
    precision = _ratio(matched_prediction, len(points))
    recall = _ratio(matched_truth, len(truth))
    f1 = None if not len(truth) else (2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and precision + recall > 0 else 0.)
    return dict(
        tolerance_reference_px=float(tolerance), predicted_points=len(points), truth_points=len(truth),
        matched_prediction_points=matched_prediction, matched_truth_points=matched_truth,
        false_prediction_points=len(points) - matched_prediction,
        precision=precision, recall=recall, f1=f1,
        unavailable_reason="no_positive_domain_contact" if not len(truth) else None,
    )


def _per_part(labels, evaluated, prediction) -> dict:
    result = {}
    for label in np.unique(labels[labels > 0]):
        selected = evaluated & (labels == label)
        result[str(int(label))] = dict(
            reference_elements=int(selected.sum()), assigned_elements=int((selected & (prediction > 0)).sum()),
            coverage=_ratio((selected & (prediction > 0)).sum(), selected.sum()),
        )
    return result


def evaluate_sample(rows: list[dict], labels, before, after, edges, *, evaluation_valid=None,
                    orientation_labels=None, truth_raster=None, pixel_spacing_xy=(1., 1.),
                    regime="transductive", kind="synthetic", case=None, states=None) -> dict:
    """Evaluate one immutable sample/scale/sampler, with no access to truth files.

    ``labels``, ``evaluation_valid`` and ``orientation_labels`` accept vectors
    or rasters. A missing reference gives null metrics, never a negative sample.
    TTMAPP transfer automatically restricts scoring to ``transfer_split=test``.
    """
    if regime not in {"transfer", "transductive"} or kind not in {"measurement", "synthetic"}:
        raise ValueError("Unknown evaluation regime or input kind")
    n = len(rows)
    xy = _positions(rows)
    before = _vector(before, n, name="before")
    after = _vector(after, n, name="after")
    edge = _edges(edges, n)
    truth = _sample(labels, xy, name="labels", fill=0, dtype_kind="iu")
    available = np.asarray([bool(row["available"]) for row in rows])
    scope = np.asarray([kind != "measurement" or regime != "transfer" or row.get("transfer_split") == "test" for row in rows])
    if not n:
        available, scope = available.astype(bool), scope.astype(bool)
    full = scope & available
    valid = _sample(evaluation_valid, xy, name="evaluation_valid", fill=labels is not None, dtype_kind="b")
    if labels is None:
        valid[:] = False
    if kind == "measurement":
        valid = valid & (truth > 0)
    else:
        valid = valid & (truth >= 0)
    evaluated = full & valid
    positive = evaluated & (truth > 0)
    known_zero = evaluated & (truth == 0) if kind == "synthetic" else np.zeros(n, bool)
    ref = np.where(positive, truth, 0)
    orientation = None if orientation_labels is None else _sample(orientation_labels, xy, name="orientation_labels", fill=0, dtype_kind="iu")
    state_array = None if states is None else _vector(states, n, name="states", dtype_kind="US")
    result = dict(
        schema="stmdomains-training-evaluation-v1", kind=kind, regime=regime, case=case,
        planned_elements=n, scope_elements=int(scope.sum()), full_support_elements=int(full.sum()),
        evaluated_elements=int(evaluated.sum()), positive_reference_elements=int(positive.sum()),
        known_zero_elements=int(known_zero.sum()),
        unavailable_elements=int((scope & ~available).sum()),
        unscored_full_support_elements=int((full & ~valid).sum()),
        unavailable_reason="no_evaluable_reference" if not evaluated.any() else None,
        after_states=None if state_array is None else dict(Counter(state_array[scope].tolist())),
        unsupported_state_violations=None if state_array is None else int((scope & ~available & (state_array != "insufficient_data")).sum()),
    )
    for name, prediction in (("before", before), ("after", after)):
        assigned = prediction > 0
        observed_positive = set(prediction[positive & assigned].tolist())
        observed_zero = set(prediction[known_zero & assigned].tolist())
        stage = dict(
            pairs=pair_scores(ref, prediction), local_pairs=local_pair_scores(ref, prediction, edge),
            coverage=_ratio((evaluated & assigned).sum(), evaluated.sum()),
            positive_reference_coverage=_ratio((positive & assigned).sum(), positive.sum()),
            evaluated_coverage=_ratio((evaluated & assigned).sum(), evaluated.sum()),
            all_scope_assignment_fraction=_ratio((scope & assigned).sum(), scope.sum()),
            full_support_assignment_fraction=_ratio((full & assigned).sum(), full.sum()),
            assigned_evaluated_elements=int((evaluated & assigned).sum()),
            assigned_full_support_elements=int((full & assigned).sum()),
            assigned_without_support=int((scope & ~available & assigned).sum()),
            domain_count_in_scope=len(set(prediction[scope & assigned].tolist())),
            domain_count_in_evaluated=len(set(prediction[evaluated & assigned].tolist())),
            per_region=_per_part(truth, evaluated, prediction),
            false_known_zero_assignments=int((known_zero & assigned).sum()),
            false_known_zero_fraction=_ratio((known_zero & assigned).sum(), known_zero.sum()),
            domains_seen_only_on_known_zero=len(observed_zero - observed_positive) if kind == "synthetic" else None,
        )
        if orientation is not None:
            stage["orientation_pairs"] = pair_scores(np.where(evaluated, orientation, 0), prediction)
            stage["per_orientation_group"] = _per_part(orientation, evaluated, prediction)
        if kind == "measurement":
            groups = stage.setdefault("per_orientation_group", {})
            for group in ("1", "2", "3"):
                groups.setdefault(group, dict(reference_elements=0, assigned_elements=0, coverage=None))
        if kind == "synthetic" and truth_raster is not None:
            stage["boundary"] = boundary_scores(xy, prediction, edge, full, truth_raster, pixel_spacing_xy=pixel_spacing_xy)
        else:
            stage["boundary"] = dict(f1=None, precision=None, recall=None,
                                     unavailable_reason="partial_reference_has_no_exact_boundary" if kind == "measurement" else "boundary_raster_not_supplied")
        result[name] = stage
    result["criteria"] = control_criteria(result, case) if kind == "synthetic" else ttmapp_criteria(result)
    return result


def _check_result(checks: dict, *, applicable=True) -> dict:
    values = list(checks.values())
    passed = False if any(value is False for value in values) else (None if not values or any(value is None for value in values) else True)
    return dict(applicable=applicable, passed=passed, qualified=bool(applicable and passed is True), checks=checks)


def _at_least(value, threshold):
    return None if value is None else bool(value >= threshold)


def _at_most(value, threshold):
    return None if value is None else bool(value <= threshold)


def control_criteria(metrics: dict, case: str | None) -> dict:
    """Fixed continuation gates. Unknown evidence can never qualify a method."""
    stage = metrics["after"]
    checks = {"no_assignment_without_support": stage["assigned_without_support"] == 0}
    if case in ZERO_CASES:
        checks.update(zero_domains=stage["domain_count_in_scope"] == 0,
                      zero_assignments=stage["assigned_evaluated_elements"] == 0,
                      has_scored_negative_elements=metrics["known_zero_elements"] > 0)
    elif case == "single":
        checks.update(one_domain=stage["domain_count_in_scope"] == 1,
                      coverage=_at_least(stage["coverage"], .9),
                      split_rate=_at_most(stage["pairs"]["split_rate"], .02))
    elif case in TWO_CASES:
        region_coverages = [part["coverage"] for part in stage["per_region"].values()]
        checks.update(coverage=_at_least(stage["coverage"], .5),
                      merge_rate=_at_most(stage["pairs"]["merge_rate"], .02),
                      split_rate=_at_most(stage["pairs"]["split_rate"], .1),
                      both_regions_present=len(region_coverages) == 2,
                      each_region_coverage=all(c is not None and c >= .3 for c in region_coverages) if len(region_coverages) == 2 else None)
        if case in BOUNDARY_CASES:
            checks["boundary_f1"] = _at_least(stage["boundary"]["f1"], .7)
    elif case == "insufficient_field":
        checks.update(zero_domains=stage["domain_count_in_scope"] == 0,
                      has_unsupported_elements=metrics["unavailable_elements"] > 0,
                      unsupported_are_insufficient_data=None if metrics["unsupported_state_violations"] is None else metrics["unsupported_state_violations"] == 0)
    elif case in ABLATION_CASES:
        checks["paired_grid_partition_invariance"] = None  # must be filled from ablation_invariance, never guessed
    else:
        return _check_result({}, applicable=False)
    return _check_result(checks)


def ttmapp_criteria(metrics: dict) -> dict:
    stage = metrics["after"]
    groups = stage.get("per_orientation_group", {})
    checks = {"coverage": _at_least(stage["coverage"], .2),
              "no_assignment_without_support": stage["assigned_without_support"] == 0}
    for group in ("1", "2", "3"):
        checks[f"orientation_group_{group}_coverage"] = _at_least(groups.get(group, {}).get("coverage"), .1)
    result = _check_result(checks)
    result["scope_note"] = "Partial references only; missing groups cannot certify full TTMAPP benefit"
    result["represented_groups"] = [group for group, values in groups.items() if values["reference_elements"] > 0]
    result["represented_group_conditions"] = _check_result({
        "coverage": checks["coverage"],
        "no_assignment_without_support": checks["no_assignment_without_support"],
        "has_represented_groups": bool(result["represented_groups"]),
        **{f"group_{group}": _at_least(groups[group]["coverage"], .1) for group in result["represented_groups"]},
    })
    result["scope_conditions"] = (result["represented_group_conditions"] if metrics["regime"] == "transfer"
                                   else _check_result(checks))
    result["full_three_group_conditions"] = _check_result(checks)
    return result


def matched_coverage(reference, baseline, candidate, scores, element_ids, *, levels=(.2, .4, .6, .8, 1.), evaluated_mask=None) -> dict:
    """Comparable subsets of already assigned predictions, never reassign refusals."""
    ref = np.asarray(reference)
    ref = _vector(ref, len(ref), name="reference")
    baseline = _vector(baseline, len(ref), name="baseline")
    candidate = _vector(candidate, len(ref), name="candidate")
    scores = _vector(scores, len(ref), name="scores", dtype_kind="fiu")
    identifiers = np.asarray([str(value) for value in element_ids])
    if identifiers.shape != ref.shape or len(set(identifiers)) != len(ref):
        raise ValueError("Comparison element IDs must be unique and aligned")
    valid = ref > 0
    evaluated = valid if evaluated_mask is None else _vector(evaluated_mask, len(ref), name="evaluated_mask", dtype_kind="b")
    if np.any(valid & ~evaluated):
        raise ValueError("Positive pair references must be included in the evaluation mask")
    common = evaluated & (baseline > 0) & (candidate > 0)
    n = int(valid.sum())
    evaluated_count = int(evaluated.sum())
    common_ref = np.where(common, ref, 0)
    common_a, common_b = pair_scores(common_ref, baseline), pair_scores(common_ref, candidate)
    common_fraction = _ratio(common.sum(), evaluated_count)
    available = common_fraction is not None and common_fraction >= .2 and common_a["same_reference_pairs"] > 0 and common_a["different_reference_pairs"] > 0
    curves = []
    for level in levels:
        if not 0 < level <= 1:
            raise ValueError("Coverage levels must lie in (0,1]")
        count = math.ceil(level * evaluated_count)
        selected = []
        for prediction in (baseline, candidate):
            indices = np.flatnonzero(evaluated & (prediction > 0))
            if not count or len(indices) < count or not np.isfinite(scores[indices]).all():
                break
            order = np.lexsort((identifiers[indices], -scores[indices]))
            mask = np.zeros(len(ref), bool)
            mask[indices[order[:count]]] = True
            selected.append(pair_scores(np.where(mask, ref, 0), prediction))
        if len(selected) == 2:
            curves.append(dict(requested_coverage=float(level), actual_coverage=count / evaluated_count,
                               selected_elements=count, baseline=selected[0], candidate=selected[1]))
    own_a, own_b = pair_scores(ref, baseline), pair_scores(ref, candidate)
    return dict(
        reference_elements=n, common_assigned_elements=int(common.sum()), common_coverage=common_fraction,
        common_positive_reference_elements=int((common & valid).sum()),
        comparable_errors=available, unavailable_reason=None if available else "common_coverage_below_0.2_or_missing_pair_kind",
        common_baseline=common_a, common_candidate=common_b, baseline=own_a, candidate=own_b, curves=curves,
        common_error_improvement=((common_a["merge_rate"] + common_a["split_rate"] - common_b["merge_rate"] - common_b["split_rate"]) / 2 if available else None),
        evaluated_elements=evaluated_count,
        baseline_assigned_evaluated=int((evaluated & (baseline > 0)).sum()),
        candidate_assigned_evaluated=int((evaluated & (candidate > 0)).sum()),
        coverage_gain=_ratio((evaluated & (candidate > 0)).sum() - (evaluated & (baseline > 0)).sum(), evaluated.sum()),
        pair_comparison_denominator="positive-reference elements; conditional pairs",
        common_and_curve_coverage_denominator="all evaluated elements with full support, including known synthetic zero",
        coverage_gain_denominator="all evaluated elements with full support, including known synthetic zero",
    )


def _equivalent(a: np.ndarray, b: np.ndarray) -> bool:
    if not np.array_equal(a > 0, b > 0):
        return False
    assigned = a > 0
    pairs = set(zip(a[assigned].tolist(), b[assigned].tolist()))
    return len(pairs) == len(set(a[assigned].tolist())) == len(set(b[assigned].tolist()))


def ablation_invariance(reference_ids, reference_before, reference_after,
                       ablated_ids, ablated_before, ablated_after) -> dict:
    """Compare grid outputs at exactly the same IDs, modulo component renaming."""
    reference_ids, ablated_ids = list(reference_ids), list(ablated_ids)
    if len(set(reference_ids)) != len(reference_ids) or len(set(ablated_ids)) != len(ablated_ids):
        raise ValueError("Repeated element identity")
    if set(reference_ids) != set(ablated_ids):
        return dict(passed=False, same_element_set=False, before=None, after=None)
    order = {ident: index for index, ident in enumerate(ablated_ids)}
    indices = np.asarray([order[ident] for ident in reference_ids], dtype=int)
    before = _equivalent(np.asarray(reference_before), np.asarray(ablated_before)[indices])
    after = _equivalent(np.asarray(reference_after), np.asarray(ablated_after)[indices])
    return dict(passed=before and after, same_element_set=True, before=before, after=after)


def seed_stability(predictions: dict[str, dict[str, int]], *, eligible_ids: set[str] | None = None,
                   require_pair_evidence=True) -> dict:
    """One sample's partitions keyed by exact element ID; never compare ID order."""
    if eligible_ids is None:
        eligible_ids = set().union(*(set(prediction) for prediction in predictions.values()))
    coverages = {}
    for seed, prediction in predictions.items():
        coverages[str(seed)] = _ratio(sum(prediction.get(ident, 0) > 0 for ident in eligible_ids), len(eligible_ids))
    pairs = []
    for seed_a, seed_b in itertools.combinations(predictions, 2):
        a, b = predictions[seed_a], predictions[seed_b]
        common_ids = sorted(eligible_ids & set(a) & set(b))
        assigned_ids = [ident for ident in common_ids if a[ident] > 0 and b[ident] > 0]
        labels_a = np.asarray([a[ident] for ident in assigned_ids], dtype=int)
        labels_b = np.asarray([b[ident] for ident in assigned_ids], dtype=int)
        metrics = pair_scores(labels_a, labels_b)
        denominator = len(assigned_ids) * (len(assigned_ids) - 1) // 2
        changed = metrics["split_pairs"] + metrics["merged_pairs"]
        pairs.append(dict(
            seed_a=str(seed_a), seed_b=str(seed_b), common_ids=len(common_ids),
            common_assigned_elements=len(assigned_ids), common_assigned_fraction=_ratio(len(assigned_ids), len(eligible_ids)),
            compared_pairs=denominator, changed_pairs=changed, changed_pair_fraction=_ratio(changed, denominator),
        ))
    values = [value for value in coverages.values() if value is not None]
    spread = max(values) - min(values) if len(values) == len(predictions) and values else None
    checks = dict(three_seeds=len(predictions) == 3, coverage_spread=_at_most(spread, .1))
    if require_pair_evidence:
        checks.update(nonempty_common_pairs=all(item["compared_pairs"] > 0 for item in pairs) if pairs else None,
                      changed_pairs=all(item["changed_pair_fraction"] is not None and item["changed_pair_fraction"] <= .1 for item in pairs) if pairs else None)
    return dict(eligible_elements=len(eligible_ids), coverage_by_seed=coverages, coverage_spread=spread,
                pairs=pairs, criteria=_check_result(checks, applicable=bool(eligible_ids)),
                pair_comparison_applicable=bool(require_pair_evidence),
                limitation="Stability alone never qualifies a method; apply case-specific coverage/false-domain gates")


def benefit_across_seeds(comparisons: dict[str, dict]) -> dict:
    """Fixed benefit conditions; caller must also require all domain-control gates."""
    error_gains, coverage_gains = [], []
    errors_safe, own_errors_safe = [], []
    for result in comparisons.values():
        error_gains.append(result["common_error_improvement"])
        coverage_gains.append(result["coverage_gain"])
        for a_key, b_key, collection in (("common_baseline", "common_candidate", errors_safe), ("baseline", "candidate", own_errors_safe)):
            a, b = result[a_key], result[b_key]
            collection.append(all(a[key] is not None and b[key] is not None and b[key] - a[key] <= .02 for key in ("merge_rate", "split_rate")))
    enough = len(comparisons) == 3
    error_complete = enough and all(value is not None for value in error_gains)
    coverage_complete = enough and all(value is not None for value in coverage_gains)
    error_path = error_complete and float(np.median(error_gains)) >= .05 and min(error_gains) >= 0 and all(errors_safe)
    coverage_path = coverage_complete and float(np.median(coverage_gains)) >= .1 and min(coverage_gains) >= 0 and all(own_errors_safe)
    return dict(
        seed_count=len(comparisons), error_gain_median=float(np.median(error_gains)) if error_complete else None,
        coverage_gain_median=float(np.median(coverage_gains)) if coverage_complete else None,
        error_path=bool(error_path), coverage_path=bool(coverage_path), benefit_condition=bool(error_path or coverage_path),
        requires_all_control_and_stability_gates=True,
        interpretation="Benefit condition only; STM claim also requires benefit on evaluable TTMAPP and held-out controls",
    )


def map_current_centers(centers_xy, grid_rows, before, after, *, pixel_spacing_xy=(1., 1.),
                        radius_reference_px=16 * np.sqrt(2) / 2, eligible_grid=None) -> dict:
    """Nearest geometric grid site, then eligibility; never search past a refusal.

    Ties use canonical element ID. Coordinates are converted to reference units
    before distances; unmatched centers retain zero assignments.
    """
    centers = np.asarray(centers_xy, dtype=float)
    if centers.ndim != 2 or centers.shape[1] != 2 or not np.isfinite(centers).all():
        raise ValueError("Invalid current-center coordinates")
    xy = _positions(grid_rows)
    before = _vector(before, len(xy), name="before")
    after = _vector(after, len(xy), name="after")
    eligible = np.asarray([bool(row["available"]) for row in grid_rows], dtype=bool)
    if eligible_grid is not None:
        eligible &= _vector(eligible_grid, len(xy), name="eligible_grid", dtype_kind="b")
    spacing = np.asarray(pixel_spacing_xy, dtype=float)
    if spacing.shape != (2,) or not np.isfinite(spacing).all() or (spacing <= 0).any():
        raise ValueError("Invalid mapping pixel spacing")
    if not np.isfinite(radius_reference_px) or radius_reference_px < 0:
        raise ValueError("Invalid nearest-grid radius")
    nearest = np.full(len(centers), -1, dtype=int)
    mapped = np.zeros(len(centers), bool)
    distances = np.full(len(centers), np.nan)
    for i, center in enumerate(centers):
        if not len(xy):
            break
        distance = np.linalg.norm((xy - center) * spacing, axis=1)
        minimum = float(distance.min())
        ties = np.flatnonzero(np.isclose(distance, minimum, rtol=0, atol=1e-9))
        index = min(ties, key=lambda index: str(grid_rows[index]["element_id"]))
        nearest[i], distances[i] = index, minimum
        mapped[i] = minimum <= radius_reference_px + 1e-9 and eligible[index]
    result_before, result_after = np.zeros(len(centers), dtype=int), np.zeros(len(centers), dtype=int)
    result_before[mapped] = before[nearest[mapped]]
    result_after[mapped] = after[nearest[mapped]]
    return dict(nearest_grid_index=nearest, mapped=mapped, distance_reference_px=distances,
                before=result_before, after=result_after)


def _sum_pair_metrics(values: list[dict], *, local=False) -> dict:
    fields = ["same_reference_pairs", "different_reference_pairs", "split_pairs", "merged_pairs"]
    fields += ["graph_edges", "reference_edges", "assigned_edges"] if local else ["reference_elements", "assigned_elements"]
    result = {field: sum(value[field] for value in values) for field in fields}
    result["merge_rate"] = _ratio(result["merged_pairs"], result["different_reference_pairs"])
    result["split_rate"] = _ratio(result["split_pairs"], result["same_reference_pairs"])
    if local:
        result["assigned_edge_fraction"] = _ratio(result["assigned_edges"], result["reference_edges"])
    else:
        result["assignment_fraction"] = _ratio(result["assigned_elements"], result["reference_elements"])
    return result


def aggregate_samples(metrics_list: list[dict]) -> dict:
    """Pool counts within samples only; never pair domains from different frames."""
    if not metrics_list:
        raise ValueError("Cannot aggregate no samples")
    kinds, regimes, cases = ({item[key] for item in metrics_list} for key in ("kind", "regime", "case"))
    if len(kinds) != 1 or len(regimes) != 1:
        raise ValueError("Cannot mix measurement/synthetic or transfer/transduction")
    result = dict(kind=next(iter(kinds)), regime=next(iter(regimes)), case=next(iter(cases)) if len(cases) == 1 else None,
                  sample_count=len(metrics_list), pair_scope="within each frame/sample; sums of counts")
    for key in ("planned_elements", "scope_elements", "full_support_elements", "evaluated_elements", "positive_reference_elements", "known_zero_elements", "unavailable_elements"):
        result[key] = sum(item[key] for item in metrics_list)
    for stage in ("before", "after"):
        values = [item[stage] for item in metrics_list]
        target = dict(pairs=_sum_pair_metrics([item["pairs"] for item in values]),
                      local_pairs=_sum_pair_metrics([item["local_pairs"] for item in values], local=True))
        for key in ("assigned_evaluated_elements", "assigned_full_support_elements", "assigned_without_support", "false_known_zero_assignments"):
            target[key] = sum(item[key] for item in values)
        target.update(
            domain_count_sum=sum(item["domain_count_in_scope"] for item in values),
            coverage=_ratio(target["assigned_evaluated_elements"], result["evaluated_elements"]),
            positive_reference_coverage=target["pairs"]["assignment_fraction"],
            evaluated_coverage=_ratio(target["assigned_evaluated_elements"], result["evaluated_elements"]),
            full_support_assignment_fraction=_ratio(target["assigned_full_support_elements"], result["full_support_elements"]),
            false_known_zero_fraction=_ratio(target["false_known_zero_assignments"], result["known_zero_elements"]),
        )
        groups = {}
        for item in values:
            for ident, part in item.get("per_orientation_group", {}).items():
                pooled = groups.setdefault(ident, dict(reference_elements=0, assigned_elements=0))
                for key in ("reference_elements", "assigned_elements"):
                    pooled[key] += part[key]
        for pooled in groups.values():
            pooled["coverage"] = _ratio(pooled["assigned_elements"], pooled["reference_elements"])
        target["per_orientation_group"] = groups
        contact = [item["boundary"] for item in values if item["boundary"].get("truth_points", 0) > 0]
        if contact:
            boundary = {key: sum(item[key] for item in contact)
                        for key in ("predicted_points", "truth_points", "matched_prediction_points", "matched_truth_points", "false_prediction_points")}
            precision = _ratio(boundary["matched_prediction_points"], boundary["predicted_points"])
            recall = _ratio(boundary["matched_truth_points"], boundary["truth_points"])
            boundary.update(precision=precision, recall=recall,
                            f1=2 * precision * recall / (precision + recall) if precision is not None and precision + recall else 0.,
                            positive_contact_sample_count=len(contact))
        else:
            boundary = dict(f1=None, precision=None, recall=None, positive_contact_sample_count=0)
        target["boundary"] = boundary
        result[stage] = target
    if result["kind"] == "measurement":
        result["criteria"] = ttmapp_criteria(result)
    else:
        applicable = [item["criteria"] for item in metrics_list if item["criteria"]["applicable"]]
        result["criteria"] = _check_result({f"sample_{i}": item["passed"] for i, item in enumerate(applicable)}, applicable=bool(applicable))
    return result


def aggregate_comparisons(values: list[dict]) -> dict:
    """Pool within-sample pair counts for one candidate seed and one regime."""
    if not values:
        raise ValueError("Cannot aggregate no comparisons")
    result = {key: _sum_pair_metrics([value[key] for value in values])
              for key in ("baseline", "candidate", "common_baseline", "common_candidate")}
    n = sum(value["reference_elements"] for value in values)
    common = sum(value["common_assigned_elements"] for value in values)
    evaluated = sum(value["evaluated_elements"] for value in values)
    fraction = _ratio(common, evaluated)
    a, b = result["common_baseline"], result["common_candidate"]
    available = fraction is not None and fraction >= .2 and a["same_reference_pairs"] > 0 and a["different_reference_pairs"] > 0
    assigned_a = sum(value["baseline_assigned_evaluated"] for value in values)
    assigned_b = sum(value["candidate_assigned_evaluated"] for value in values)
    result.update(reference_elements=n, common_assigned_elements=common, common_coverage=fraction,
                  common_positive_reference_elements=sum(value["common_positive_reference_elements"] for value in values),
                  comparable_errors=available,
                  common_error_improvement=(a["merge_rate"] + a["split_rate"] - b["merge_rate"] - b["split_rate"]) / 2 if available else None,
                  evaluated_elements=evaluated, baseline_assigned_evaluated=assigned_a,
                  candidate_assigned_evaluated=assigned_b,
                  coverage_gain=_ratio(assigned_b - assigned_a, evaluated),
                  coverage_gain_denominator="all evaluated elements with full support, including known synthetic zero",
                  common_coverage_denominator="all evaluated elements with full support, including known synthetic zero",
                  pair_scope="within samples only")
    return result


def write_summary(records: list[dict], out: Path, *, extras=None) -> None:
    """Write complete JSON and rectangular CSV; each record has metadata+metrics."""
    out = Path(out)
    if out.exists():
        raise FileExistsError(f"Use a fresh evaluation output: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".domain-evaluation-", dir=out.parent) as temporary:
        staging = Path(temporary) / "evaluation"
        staging.mkdir()
        write_json(staging / "summary.json", dict(schema="stmdomains-training-summary-v1", records=records, **(extras or {})))
        table, regions = [], []
        for record in records:
            metadata, metrics = record["metadata"], record["metrics"]
            for stage_name in ("before", "after"):
                stage = metrics[stage_name]
                row = dict(metadata, stage=stage_name)
                for key in ("planned_elements", "scope_elements", "full_support_elements", "evaluated_elements", "positive_reference_elements", "known_zero_elements", "unavailable_elements"):
                    row[key] = metrics[key]
                for key in ("coverage", "positive_reference_coverage", "evaluated_coverage", "all_scope_assignment_fraction", "assigned_evaluated_elements", "domain_count_in_scope", "false_known_zero_assignments", "false_known_zero_fraction", "assigned_without_support"):
                    row[key] = stage[key]
                for prefix, key in (("pairs", "pairs"), ("local", "local_pairs"), ("boundary", "boundary")):
                    row.update({f"{prefix}_{field}": value for field, value in stage[key].items()})
                row["continuation_qualified"] = metrics["criteria"]["qualified"] if stage_name == "after" else None
                table.append(row)
                for partition in ("per_region", "per_orientation_group"):
                    for ident, values in stage.get(partition, {}).items():
                        regions.append(dict(metadata, stage=stage_name, reference_partition=partition, reference_id=ident, **values))
        for name, rows in (("metrics.csv", table), ("regions.csv", regions)):
            fields = list(dict.fromkeys(key for row in rows for key in row))
            with (staging / name).open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
        staging.rename(out)


def _read_json(path: Path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt") as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def verify_prediction_freeze(root: Path, *, check_budget=None) -> dict:
    """Verify every frozen artifact before the caller opens any evaluation tree."""
    root = Path(root).resolve()
    frozen = _read_json(root / "frozen-predictions.json")
    if frozen.get("schema") != "stmdomains-frozen-predictions-v1" or frozen.get("evaluation_opened") is not False:
        raise ValueError("Predictions must be frozen before evaluation")
    if "predictions/index.json" not in frozen.get("files", {}):
        raise ValueError("Prediction index is absent from the freeze")
    for index, (relative, expected) in enumerate(frozen["files"].items()):
        if check_budget is not None and index % 100 == 0:
            check_budget()
        path = (root / relative).resolve()
        if Path(relative).is_absolute() or not path.is_relative_to(root):
            raise ValueError("Frozen artifact escapes prediction directory")
        if file_hash(path) != expected:
            raise ValueError(f"Frozen artifact changed: {relative}")
    return frozen


def _frozen_path(root: Path, relative: str, frozen: dict) -> Path:
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()) or relative not in frozen["files"]:
        raise ValueError(f"Attempted to evaluate an unfrozen artifact: {relative}")
    return path


def _truth_bundle(directory: Path, field: str) -> tuple[dict, dict]:
    directory = Path(directory).resolve()
    manifest = _read_json(directory / "manifest.json")
    if manifest.get("schema") != "stmdomains-evaluation-v1":
        raise ValueError("Unsupported evaluation schema")
    records = {}
    for item in manifest[field]:
        ident = item["sample_id"]
        if ident in records:
            raise ValueError("Repeated evaluation sample")
        path = (directory / item["file"]).resolve()
        if not path.is_relative_to(directory):
            raise ValueError("Evaluation sample escapes its directory")
        if file_hash(path) != item["sha256"]:
            raise ValueError("Evaluation file hash mismatch")
        with np.load(path, allow_pickle=False) as archive:
            arrays = {key: archive[key] for key in archive.files}
        if arrays_hash(arrays) != item["content_sha256"]:
            raise ValueError("Evaluation content hash mismatch")
        records[ident] = (item, arrays)
    return manifest, records


def _comparison_reference(rows, labels, validity, *, kind, regime):
    xy = _positions(rows)
    ref = _sample(labels, xy, name="labels", fill=0, dtype_kind="iu")
    valid = _sample(validity, xy, name="validity", fill=labels is not None, dtype_kind="b")
    eligible = np.asarray([bool(row["available"]) and (kind != "measurement" or regime != "transfer" or row.get("transfer_split") == "test") for row in rows], dtype=bool)
    return np.where(valid & eligible & (ref > 0), ref, 0)


def _evaluated_mask(rows, labels, validity, *, kind, regime):
    xy = _positions(rows)
    ref = _sample(labels, xy, name="labels", fill=0, dtype_kind="iu")
    valid = _sample(validity, xy, name="validity", fill=labels is not None, dtype_kind="b")
    eligible = np.asarray([bool(row["available"]) and (kind != "measurement" or regime != "transfer" or row.get("transfer_split") == "test") for row in rows], dtype=bool)
    return valid & eligible & ((ref > 0) if kind == "measurement" else (ref >= 0))


def _group_key(metadata: dict, keys) -> tuple:
    return tuple(metadata.get(key) for key in keys)


def _flat_csv(path: Path, records: list[dict]) -> None:
    def flatten(value, prefix=""):
        result = {}
        for key, item in value.items():
            name = f"{prefix}{key}"
            if isinstance(item, dict):
                result.update(flatten(item, name + "."))
            elif isinstance(item, list):
                result[name] = json.dumps(item, allow_nan=False)
            else:
                result[name] = item
        return result
    rows = [flatten(record) for record in records]
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def continuation_summary(records, stability, benefits) -> list[dict]:
    """All fixed primary-grid cases/seeds, not a favorable average of checks."""
    family_keys = ("regime", "family", "latent", "partition")
    group_records = {}
    for record in records:
        meta = record["metadata"]
        if meta["sampler"] == "grid" and meta["scale_px"] == 48:
            group_records.setdefault(_group_key(meta, family_keys), []).append(record)
    required_cases = ZERO_CASES | TWO_CASES | ABLATION_CASES | {"single", "insufficient_field"}
    output = []
    for key, members in group_records.items():
        meta = dict(zip(family_keys, key))
        model_seeds = [None] if meta["family"] == "fft" else [20261101, 20261102, 20261103]
        by_case = {(record["metadata"]["seed"], record["metadata"]["case"], record["metadata"]["control_seed"]): record
                   for record in members if record["metadata"]["kind"] == "synthetic"}
        checks = {}
        for model_seed, case, control_seed in itertools.product(model_seeds, sorted(required_cases), (920001, 920002, 920003)):
            record = by_case.get((model_seed, case, control_seed))
            checks[f"model_seed={model_seed}/case={case}/control_seed={control_seed}"] = None if record is None else record["metrics"]["criteria"]["passed"]
        controls = _check_result(checks)
        ttmapp = {}
        for seed in model_seeds:
            values = [record["metrics"] for record in members if record["metadata"]["kind"] == "measurement" and record["metadata"]["seed"] == seed]
            ttmapp[str(seed)] = aggregate_samples(values)["criteria"] if values else _check_result({"evaluation_available": None})
        stabilities = [entry for entry in stability if _group_key(entry["metadata"], family_keys) == key
                       and entry["metadata"]["sampler"] == "grid" and entry["metadata"]["scale_px"] == 48
                       and entry["stability"]["criteria"]["applicable"]]
        stable = True if meta["family"] == "fft" else (all(entry["stability"]["criteria"]["passed"] is True for entry in stabilities) if stabilities else None)
        benefit = {"synthetic": None, "measurement": None}
        for entry in benefits:
            item = entry["metadata"]
            if _group_key(item, family_keys) == key and item["sampler"] == "grid" and item["scale_px"] == 48:
                if item["kind"] == "synthetic" and item["case"] == "__all__":
                    benefit["synthetic"] = entry["benefit"]["benefit_condition"]
                if item["kind"] == "measurement":
                    benefit["measurement"] = entry["benefit"]["benefit_condition"]
        qualification = _check_result(dict(
            all_synthetic_control_conditions=controls["passed"], stability=stable,
            ttmapp_coverage_all_seeds=all(value.get("scope_conditions", value)["passed"] is True for value in ttmapp.values()),
            benefit_on_controls=benefit["synthetic"], benefit_on_ttmapp=benefit["measurement"],
        ), applicable=meta["family"] != "fft")
        output.append(dict(metadata=meta, synthetic_controls=controls, ttmapp=ttmapp,
                           stability=stable, benefit=benefit, continuation=qualification,
                           claim_scope="represented transfer-test regions only" if meta["regime"] == "transfer" else "all three partial-reference groups in transduction",
                           full_three_group_ttmapp_benefit=qualification["qualified"] and all(value["passed"] is True for value in ttmapp.values()),
                           note="Primary grid48 only; z16 is diagnostic, z32 primary. Passing is research continuation, never application acceptance or independent-acquisition generalization."))
    return output


class PostprocessBudget:
    """Count prior postprocessing attempts plus this CPU clock, including failures."""

    def __init__(self, root: Path):
        self.cpu_started = time.process_time()
        self.wall_started = time.monotonic()
        self.prior_cpu_seconds = 0.
        self.prior_reports = {}
        for path in sorted(Path(root).glob("*-resources.json")):
            seconds = float(_read_json(path)["cpu_seconds"])
            if not np.isfinite(seconds) or seconds < 0:
                raise ValueError("Invalid prior postprocessing CPU record")
            self.prior_cpu_seconds += seconds
            self.prior_reports[path.name] = file_hash(path)
        self.cpu_limit_seconds = 7200.
        self.rss_limit_bytes = 12 * 1024 ** 3

    def measurements(self) -> dict:
        current = time.process_time() - self.cpu_started
        return dict(cpu_seconds=current, prior_cpu_seconds=self.prior_cpu_seconds,
                    cumulative_postprocess_cpu_seconds=self.prior_cpu_seconds + current,
                    cpu_limit_seconds=self.cpu_limit_seconds,
                    wall_seconds=time.monotonic() - self.wall_started,
                    max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                    rss_limit_bytes=self.rss_limit_bytes, prior_reports_sha256=self.prior_reports)

    def check(self) -> None:
        values = self.measurements()
        if values["cumulative_postprocess_cpu_seconds"] >= self.cpu_limit_seconds:
            raise RuntimeError("Postprocessing CPU budget of 7200 seconds is exhausted")
        if values["max_rss_kib"] * 1024 > self.rss_limit_bytes:
            raise RuntimeError("Postprocessing RSS budget of 12 GiB is exceeded")

    def checked(self, values):
        for index, value in enumerate(values):
            if index % 100 == 0:
                self.check()
            yield value


def evaluate_frozen(predictions_root: Path, controls_evaluation: Path,
                    measurement_evaluation: Path, out: Path) -> dict:
    root, out = Path(predictions_root).resolve(), Path(out)
    if out.exists():
        raise FileExistsError(f"Use a fresh evaluation output: {out}")
    resource_path = root / f"{out.name}-resources.json"
    if resource_path.exists():
        raise FileExistsError(f"Evaluation attempt already has a resource record: {resource_path}")
    budget = PostprocessBudget(root)
    status = "failed"
    try:
        result = _evaluate_frozen(root, controls_evaluation, measurement_evaluation, out, budget)
        status = "completed"
        return result
    finally:
        write_json(resource_path, dict(status=status, **budget.measurements()))


def _evaluate_frozen(predictions_root: Path, controls_evaluation: Path,
                     measurement_evaluation: Path, out: Path, budget: PostprocessBudget) -> dict:
    """Evaluate the predict.py index only after its complete freeze verifies."""
    started, cpu_started = time.monotonic(), time.process_time()
    root, out = Path(predictions_root).resolve(), Path(out)
    if out.exists():
        raise FileExistsError(f"Use a fresh evaluation output: {out}")
    budget.check()
    frozen = verify_prediction_freeze(root, check_budget=budget.check)
    budget.check()
    # No reference path has been opened above this line.
    _, control_truth = _truth_bundle(controls_evaluation, "controls")
    _, measurement_truth = _truth_bundle(measurement_evaluation, "references")
    index = _read_json(_frozen_path(root, "predictions/index.json", frozen))
    cache_index = _read_json(_frozen_path(root, "cache/index.json", frozen))
    groups = {group["group_id"]: group for group in cache_index}
    rows_cache, data, records = {}, {}, []
    for item in index:
        key = _group_key(item, ("run_id", "scale_px", "sampler", "sample_id", "partition"))
        if key in data:
            raise ValueError("Duplicate prediction index entry")
        group = item["cache_group"]
        if group not in rows_cache:
            rows_cache[group] = _read_json(_frozen_path(root, f"cache/{group}/rows.json.gz", frozen))
        rows = rows_cache[group]
        path = _frozen_path(root, f"{item['directory']}/{item['evaluation_input']}", frozen)
        with np.load(path, allow_pickle=False) as archive:
            prediction = {name: archive[name] for name in archive.files}
        if not np.array_equal(prediction["available"], np.asarray([row["available"] for row in rows], dtype=bool)):
            raise ValueError("Prediction availability disagrees with frozen row geometry")
        heldout = item["kind"] == "measurement" and item["regime"] == "transfer"
        if heldout and item["evaluation_input"] != "heldout-metrics-input.npz":
            raise ValueError("Transfer must evaluate the graph containing test nodes only")
        payload_name = "heldout-result.json.gz" if heldout else "result.json.gz"
        payload = _read_json(_frozen_path(root, f"{item['directory']}/{payload_name}", frozen))
        if [assignment["element_id"] for assignment in payload["assignments"]] != [row["element_id"] for row in rows]:
            raise ValueError("Assignment/row order differs")
        assigned = np.asarray([assignment["domain_id"] is not None for assignment in payload["assignments"]], dtype=bool)
        if not np.array_equal(assigned, prediction["after"] > 0):
            raise ValueError("Result envelope and evaluation assignments disagree")
        states = np.asarray([assignment["state"] for assignment in payload["assignments"]], dtype="U64")
        source = control_truth if item["kind"] == "synthetic" else measurement_truth
        if item["kind"] == "synthetic" and item["sample_id"] not in source:
            raise ValueError("Missing truth for a synthetic evaluation sample")
        reference_meta, truth = source.get(item["sample_id"], ({}, {}))
        labels = truth.get("domain_labels" if item["kind"] == "synthetic" else "region_instances")
        case = reference_meta.get("case")
        metrics = evaluate_sample(
            rows, labels, prediction["before"], prediction["after"], prediction["edges"],
            evaluation_valid=truth.get("evaluation_valid"), orientation_labels=truth.get("orientation_groups"),
            truth_raster=truth.get("domain_labels"), pixel_spacing_xy=item["pixel_spacing_xy"],
            regime=item["regime"], kind=item["kind"], case=case, states=states,
        )
        metadata = {key: value for key, value in item.items() if key not in {"directory", "cache_group", "evaluation_input"}}
        metadata.update(case=case, control_seed=reference_meta.get("seed"),
                        assessment="primary_grid" if item["sampler"] == "grid" else "own_center_graph_diagnostic")
        record = dict(metadata=metadata, metrics=metrics)
        records.append(record)
        data[key] = dict(rows=rows, prediction=prediction, record=record,
                         reference=_comparison_reference(rows, labels, truth.get("evaluation_valid"), kind=item["kind"], regime=item["regime"]),
                         evaluated_mask=_evaluated_mask(rows, labels, truth.get("evaluation_valid"), kind=item["kind"], regime=item["regime"]),
                         truth=truth, states=states, source_entry=item)
        if len(records) % 500 == 0:
            print(f"evaluated {len(records)}/{len(index)} frozen predictions", flush=True)
        if len(records) % 100 == 0:
            budget.check()

    # The separate center graph and centers mapped to grid are distinct outputs.
    measurement_arrays = {}
    for index_position, item in enumerate(index):
        if index_position % 100 == 0:
            budget.check()
        if item["kind"] != "measurement" or item["sampler"] != "grid" or item["scale_px"] != 48:
            continue
        key = _group_key(item, ("run_id", "scale_px", "sampler", "sample_id", "partition"))
        source = data[key]
        center_key = (item["run_id"], 48, "centers", item["sample_id"], item["partition"])
        centers = data[center_key]
        if item["sample_id"] not in measurement_arrays:
            group = groups[item["cache_group"]]
            loaded, arrays = load_sample(Path(group["analysis"]), item["sample_id"])
            if loaded["content_sha256"] != group["record"]["content_sha256"]:
                raise ValueError("Current centers differ from the frozen input identity")
            measurement_arrays[item["sample_id"]] = arrays
        arrays = measurement_arrays[item["sample_id"]]
        if [row["element_id"] for row in centers["rows"]] != arrays["object_ids"].tolist() or not np.array_equal(_positions(centers["rows"]), arrays["centers_xy"]):
            raise ValueError("Current centers and cached center geometry disagree")
        grid_eligible = np.asarray([item["regime"] != "transfer" or row.get("transfer_split") == "test" for row in source["rows"]], dtype=bool)
        mapped = map_current_centers(arrays["centers_xy"], source["rows"], source["prediction"]["before"],
                                     source["prediction"]["after"], eligible_grid=grid_eligible)
        center_available = np.asarray([row["available"] for row in centers["rows"]], dtype=bool)
        mapped["before"][~center_available] = 0
        mapped["after"][~center_available] = 0
        states = np.full(len(centers["rows"]), "insufficient_data", dtype="U64")
        effective = mapped["mapped"] & center_available
        states[effective] = source["states"][mapped["nearest_grid_index"][effective]]
        truth = source["truth"]
        metrics = evaluate_sample(centers["rows"], truth.get("region_instances"), mapped["before"], mapped["after"],
                                  centers["prediction"]["edges"], evaluation_valid=truth.get("evaluation_valid"),
                                  orientation_labels=truth.get("orientation_groups"), kind="measurement",
                                  regime=item["regime"], states=states)
        metrics["grid_mapping"] = dict(radius_px=16 * np.sqrt(2) / 2, centers=len(states),
                                       matched_available_grid=int(mapped["mapped"].sum()),
                                       unmatched_count=int((~mapped["mapped"]).sum()),
                                       denominator_policy="Unmapped centers with full center support remain unassigned in coverage")
        metadata = dict(source["record"]["metadata"], sampler="centers_from_grid", assessment="nearest_grid_center_assessment")
        record = dict(metadata=metadata, metrics=metrics)
        records.append(record)
        data[(item["run_id"], 48, "centers_from_grid", item["sample_id"], item["partition"])] = dict(
            rows=centers["rows"], prediction=dict(before=mapped["before"], after=mapped["after"],
                edges=centers["prediction"]["edges"], acf_score=np.where(effective, source["prediction"]["acf_score"][np.maximum(mapped["nearest_grid_index"], 0)], np.nan)),
            record=record, reference=centers["reference"], evaluated_mask=centers["evaluated_mask"], truth=truth, states=states,
        )

    by_control = {(item[0]["seed"], item[0]["case"]): ident for ident, item in control_truth.items()}
    ablations = []
    for index_position, (key, value) in enumerate(data.items()):
        if index_position % 100 == 0:
            budget.check()
        metadata = value["record"]["metadata"]
        if metadata["sampler"] != "grid" or metadata["case"] not in ABLATION_CASES:
            continue
        baseline_id = by_control[metadata["control_seed"], "single"]
        baseline = data[(metadata["run_id"], metadata["scale_px"], "grid", baseline_id, metadata["partition"])]
        invariance = ablation_invariance(
            [row["element_id"] for row in baseline["rows"]], baseline["prediction"]["before"], baseline["prediction"]["after"],
            [row["element_id"] for row in value["rows"]], value["prediction"]["before"], value["prediction"]["after"],
        )
        checks = dict(value["record"]["metrics"]["criteria"]["checks"], paired_grid_partition_invariance=invariance["passed"])
        value["record"]["metrics"]["criteria"] = _check_result(checks)
        ablations.append(dict(metadata=metadata, baseline_sample_id=baseline_id, invariance=invariance))

    aggregates_by_key, comparisons, stability_groups = {}, [], {}
    aggregate_keys = ("run_id", "regime", "family", "latent", "seed", "scale_px", "sampler", "partition", "kind", "case", "assessment")
    for index_position, value in enumerate(data.values()):
        if index_position % 100 == 0:
            budget.check()
        metadata = value["record"]["metadata"]
        aggregates_by_key.setdefault(_group_key(metadata, aggregate_keys), []).append(value["record"]["metrics"])
        baseline_key = (metadata["regime"] + "/fft", metadata["scale_px"], metadata["sampler"], metadata["sample_id"], "fh4")
        if baseline_key in data and not (metadata["family"] == "fft" and metadata["partition"] == "fh4"):
            baseline = data[baseline_key]
            if not np.array_equal(value["reference"], baseline["reference"]):
                raise ValueError("Baseline and candidate evaluated on different reference positions")
            if not np.array_equal(value["prediction"]["acf_score"], baseline["prediction"]["acf_score"], equal_nan=True):
                raise ValueError("Matched-coverage ranking must use the same ACF scores")
            comparisons.append(dict(metadata=metadata, comparison=matched_coverage(
                value["reference"], baseline["prediction"]["after"], value["prediction"]["after"],
                value["prediction"]["acf_score"], [row["element_id"] for row in value["rows"]],
                evaluated_mask=value["evaluated_mask"],
            )))
        if metadata["seed"] is not None:
            keys = ("regime", "family", "latent", "scale_px", "sampler", "sample_id", "partition", "kind", "case")
            group = stability_groups.setdefault(_group_key(metadata, keys), dict(predictions={}, eligible=set(), metadata={key: metadata[key] for key in keys}))
            group["predictions"][str(metadata["seed"])] = {row["element_id"]: int(label) for row, label in zip(value["rows"], value["prediction"]["after"])}
            group["eligible"].update(row["element_id"] for row, eligible in zip(value["rows"], value["evaluated_mask"]) if eligible)
    aggregates = [dict(metadata=dict(zip(aggregate_keys, key)), metrics=aggregate_samples(values))
                  for key, values in budget.checked(aggregates_by_key.items())]
    stability = [dict(metadata=value["metadata"], stability=seed_stability(value["predictions"], eligible_ids=value["eligible"],
                    require_pair_evidence=value["metadata"]["case"] not in ZERO_CASES | {"insufficient_field"}))
                 for value in budget.checked(stability_groups.values())]
    comparison_keys = ("run_id", "regime", "family", "latent", "seed", "scale_px", "sampler", "partition", "kind", "case", "assessment")
    comparison_groups = {}
    for record in budget.checked(comparisons):
        comparison_groups.setdefault(_group_key(record["metadata"], comparison_keys), []).append(record["comparison"])
    pooled_comparisons = [dict(metadata=dict(zip(comparison_keys, key)), comparison=aggregate_comparisons(values))
                          for key, values in budget.checked(comparison_groups.items())]
    synthetic_all = {}
    all_keys = tuple(key for key in comparison_keys if key != "case")
    for record in budget.checked(comparisons):
        if record["metadata"]["kind"] == "synthetic":
            synthetic_all.setdefault(_group_key(record["metadata"], all_keys), []).append(record["comparison"])
    pooled_comparisons.extend(dict(metadata=dict(zip(all_keys, key), case="__all__"), comparison=aggregate_comparisons(values))
                              for key, values in budget.checked(synthetic_all.items()))
    benefit_keys = ("regime", "family", "latent", "scale_px", "sampler", "partition", "kind", "case", "assessment")
    benefit_groups = {}
    for record in budget.checked(pooled_comparisons):
        if record["metadata"]["seed"] is not None:
            benefit_groups.setdefault(_group_key(record["metadata"], benefit_keys), {})[str(record["metadata"]["seed"])] = record["comparison"]
    benefits = [dict(metadata=dict(zip(benefit_keys, key)), benefit=benefit_across_seeds(values))
                for key, values in budget.checked(benefit_groups.items())]
    continuation = continuation_summary(records, stability, benefits)
    budget.check()
    write_summary(records, out, extras=dict(aggregates=aggregates, comparisons=pooled_comparisons,
                  stability=stability, ablations=ablations, benefits=benefits, criteria=continuation))
    for filename, values in (("aggregates", aggregates), ("comparisons", comparisons), ("pooled-comparisons", pooled_comparisons),
                             ("stability", stability), ("ablations", ablations), ("benefits", benefits), ("continuation", continuation)):
        budget.check()
        write_json(out / f"{filename}.json", values)
        _flat_csv(out / f"{filename}.csv", values)
    evidence = dict(
        schema="stmdomains-post-freeze-evaluation-v1", frozen_manifest_sha256=file_hash(root / "frozen-predictions.json"),
        verified_prediction_files=len(frozen["files"]), prediction_entries=len(index), evaluated_records=len(records),
        controls_manifest_sha256=file_hash(Path(controls_evaluation) / "manifest.json"),
        measurement_manifest_sha256=file_hash(Path(measurement_evaluation) / "manifest.json"),
        evaluation_code_sha256=file_hash(Path(__file__)),
        elapsed_seconds=time.monotonic() - started, cpu_seconds=time.process_time() - cpu_started,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        policy="Read-only frozen predictions; no model selection, parameter changes or exact TTMAPP boundary claims",
        postprocessing_budget=budget.measurements(),
    )
    budget.check()
    write_json(out / "evaluation-evidence.json", evidence)
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--controls-evaluation", type=Path, required=True)
    parser.add_argument("--measurement-evaluation", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate_frozen(args.predictions, args.controls_evaluation, args.measurement_evaluation, args.out), indent=2))


if __name__ == "__main__":
    main()
