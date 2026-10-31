"""Frozen train-only feature geometry and deterministic frame-local partitions.

The module accepts no reference labels. Component IDs describe proposals, not
validated structural types or material contours. The only fit entry point takes
explicit training descriptors and their within-frame edges.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np
from scipy.spatial import cKDTree


def _ids(element_ids, n: int) -> list[str]:
    ids = list(element_ids)
    if len(ids) != n or any(not isinstance(item, str) or not item for item in ids):
        raise ValueError("Element IDs must be nonempty strings, one per descriptor")
    if len(set(ids)) != n:
        raise ValueError("Element IDs must be unique within the supplied graph")
    return ids


def _edges(edges, n: int) -> np.ndarray:
    values = np.asarray(edges)
    if values.size == 0:
        return np.empty((0, 2), dtype=np.int64)
    if values.ndim != 2 or values.shape[1] != 2 or values.dtype.kind not in "iu":
        raise ValueError("Edges must be an integer E-by-2 array")
    if np.any(values < 0) or np.any(values >= n) or np.any(values[:, 0] == values[:, 1]):
        raise ValueError("Edge endpoint outside graph or self-edge")
    canonical = np.sort(values, axis=1)
    if len(np.unique(canonical, axis=0)) != len(values):
        raise ValueError("Duplicate undirected edge")
    return values.astype(np.int64, copy=False)


def _unit_features(features) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(features, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] == 0:
        raise ValueError("Features must have shape N-by-D with D positive")
    finite = np.isfinite(values).all(axis=1)
    # Scale first to avoid overflow while preserving exact zero-vector refusal.
    maxima = np.max(np.abs(np.where(np.isfinite(values), values, 0.)), axis=1)
    valid = finite & (maxima > 0)
    normalized = np.zeros_like(values)
    if valid.any():
        scaled = values[valid] / maxima[valid, None]
        normalized[valid] = scaled / np.linalg.norm(scaled, axis=1, keepdims=True)
    return normalized, valid


def neighbor_edges(xy, element_ids, *, mode: str = "grid", stride: float = 16.) -> np.ndarray:
    """Edges for ONE frame, canonical by IDs and independent of row order.

    Pass coordinates in reference pixels for technically resampled controls.
    Geometry includes all finite sites; descriptor availability is applied later.
    """
    positions = np.asarray(xy, dtype=np.float64)
    if positions.ndim != 2 or positions.shape[1] != 2 or not np.isfinite(positions).all():
        raise ValueError("Positions must be finite N-by-2 coordinates")
    ids = _ids(element_ids, len(positions))
    if mode not in {"grid", "centers"} or not np.isfinite(stride) or stride <= 0:
        raise ValueError("Unknown sampler or invalid grid stride")
    if len(positions) < 2:
        return np.empty((0, 2), dtype=np.int64)
    tree = cKDTree(positions)
    limit = stride * np.sqrt(2)
    if mode == "centers":
        nearest = tree.query(positions, k=2)[0][:, 1]
        limit = min(24., 1.65 * float(np.median(nearest)))
    pairs = tree.query_pairs(limit + 1e-10, output_type="ndarray")
    ordered = [(int(a), int(b)) if ids[a] < ids[b] else (int(b), int(a)) for a, b in pairs]
    ordered.sort(key=lambda pair: (ids[pair[0]], ids[pair[1]]))
    return np.asarray(ordered, dtype=np.int64).reshape(-1, 2)


def fit_feature_adapter(train_features, train_edges, element_ids, *, scope: dict) -> dict:
    """Fit L2/PCA, positive-edge median and q25/q75 on training data only.

    ``scope`` identifies regime, scale_px, sampler and feature_id; do not reuse an
    adapter across those scopes. Degenerate fits are explicit unavailable records.
    The JSON-compatible record contains everything needed for frozen inference.
    """
    required = {"regime", "scale_px", "sampler", "feature_id"}
    if not required <= scope.keys():
        raise ValueError("Adapter scope requires regime, scale_px, sampler and feature_id")
    normalized, valid = _unit_features(train_features)
    ids = _ids(element_ids, len(normalized))
    pairs = _edges(train_edges, len(normalized))
    selected = sorted(np.flatnonzero(valid), key=lambda index: ids[index])
    result = dict(
        schema="stmdomains-feature-adapter-v1", scope=dict(scope), available=False,
        reason=None, input_dimension=normalized.shape[1],
        training_elements=len(normalized), valid_training_elements=len(selected),
        training_ids_sha256=hashlib.sha256(json.dumps(sorted(ids)).encode()).hexdigest(),
        mean=None, components=None, edge_median=None, q25=None, q75=None,
        valid_training_edges=0, positive_training_edges=0,
    )
    if len(selected) < 2:
        result["reason"] = "insufficient_training_descriptors"
        return result
    x = normalized[selected]
    mean = x.mean(axis=0)
    count = min(24, x.shape[1], len(x) - 1)
    _, singular_values, components = np.linalg.svd(x - mean, full_matrices=False)
    components = components[:count]
    # The largest-magnitude loading has positive sign; zero loadings stay positive.
    for vector in components:
        if vector[np.argmax(np.abs(vector))] < 0:
            vector *= -1
    result.update(mean=mean.tolist(), components=components.tolist(),
                  singular_values=singular_values[:count].tolist())
    projected = (normalized - mean) @ components.T
    usable = pairs[valid[pairs].all(axis=1)]
    result["valid_training_edges"] = len(usable)
    if not len(usable):
        result["reason"] = "no_valid_training_edges"
        return result
    distances = np.linalg.norm(projected[usable[:, 0]] - projected[usable[:, 1]], axis=1)
    positive = distances[distances > 0]
    result["positive_training_edges"] = len(positive)
    if not len(positive):
        result["reason"] = "degenerate_training_edge_distances"
        return result
    median = max(float(np.median(positive)), 1e-10)
    q25, q75 = np.quantile(distances / median, [.25, .75], method="linear")
    result.update(available=True, reason=None, edge_median=median,
                  q25=float(q25), q75=float(q75))
    return result


def transform_features(features, adapter: dict) -> tuple[np.ndarray, np.ndarray]:
    """Apply a frozen fit; returns PCA coordinates and explicit row availability."""
    normalized, valid = _unit_features(features)
    if normalized.shape[1] != adapter["input_dimension"]:
        raise ValueError("Descriptor dimension differs from frozen adapter")
    count = len(adapter["components"] or [])
    projected = np.full((len(normalized), count), np.nan)
    if not adapter["available"]:
        return projected, np.zeros(len(normalized), dtype=bool)
    components = np.asarray(adapter["components"], dtype=float)
    projected[valid] = (normalized[valid] - np.asarray(adapter["mean"])) @ components.T
    return projected, valid


class _Components:
    def __init__(self, ids: list[str]):
        self.ids = ids
        self.parent = np.arange(len(ids))
        self.size = np.ones(len(ids), dtype=np.int64)

    def root(self, node: int) -> int:
        node = int(node)
        while self.parent[node] != node:
            self.parent[node] = self.parent[self.parent[node]]
            node = int(self.parent[node])
        return node

    def merge(self, a: int, b: int) -> tuple[int, int]:
        a, b = self.root(a), self.root(b)
        if self.ids[b] < self.ids[a]:
            a, b = b, a
        if a != b:
            self.parent[b] = a
            self.size[a] += self.size[b]
        return a, b

    def labels(self, valid: np.ndarray) -> list[str | None]:
        return [self.ids[self.root(i)] if valid[i] else None for i in range(len(self.ids))]


def _graph_inputs(element_ids, edges, values, valid):
    ids = _ids(element_ids, len(element_ids))
    pairs = _edges(edges, len(ids))
    weights = np.asarray(values, dtype=float)
    available = np.ones(len(ids), dtype=bool) if valid is None else np.asarray(valid, dtype=bool)
    if weights.shape != (len(pairs),) or available.shape != (len(ids),):
        raise ValueError("Inconsistent graph weights or availability")
    usable = available[pairs].all(axis=1)
    if not np.isfinite(weights[usable]).all() or np.any(weights[usable] < 0):
        raise ValueError("Usable edge weights must be finite and nonnegative")
    keys = [tuple(sorted((ids[a], ids[b]))) for a, b in pairs]
    return ids, pairs, weights, available, usable, keys


def fh_partition(element_ids, edges, distances, *, valid=None, k: float = 4.) -> list[str | None]:
    """FH algorithm1; no forced post-merge, canonical IDs also for ties."""
    ids, pairs, weights, available, usable, keys = _graph_inputs(element_ids, edges, distances, valid)
    if not np.isfinite(k) or k <= 0:
        raise ValueError("FH k must be finite and positive")
    groups = _Components(ids)
    internal = np.zeros(len(ids))
    for index in sorted(np.flatnonzero(usable), key=lambda i: (weights[i], *keys[i])):
        a, b = (groups.root(v) for v in pairs[index])
        value = weights[index]
        if a != b and value <= min(internal[a] + k / groups.size[a],
                                   internal[b] + k / groups.size[b]):
            merged_internal = max(value, internal[a], internal[b])
            kept, _ = groups.merge(a, b)
            internal[kept] = merged_internal
    return groups.labels(available)


def relation_weights(distances, q25: float, q75: float) -> tuple[np.ndarray, np.ndarray]:
    """One signed relation per edge; NaN is unavailable, equal quantiles neutral."""
    if not np.isfinite([q25, q75]).all() or q25 < 0 or q75 < q25:
        raise ValueError("Invalid frozen relation quantiles")
    distances = np.asarray(distances, dtype=float)
    if distances.ndim != 1 or np.any(distances[np.isfinite(distances)] < 0):
        raise ValueError("Distances must be a nonnegative vector or NaN")
    kinds = np.full(len(distances), "none", dtype="U11")
    strengths = np.zeros(len(distances))
    kinds[~np.isfinite(distances)] = "unavailable"
    strengths[~np.isfinite(distances)] = np.nan
    attractive = np.isfinite(distances) & (distances < q25)
    repulsive = np.isfinite(distances) & (distances > q75)
    kinds[attractive], kinds[repulsive] = "attractive", "repulsive"
    strengths[attractive] = np.clip((q25 - distances[attractive]) / max(q25, 1e-10), 0, 1)
    strengths[repulsive] = np.clip((distances[repulsive] - q75) / max(q75, 1e-10), 0, 1)
    return kinds, strengths


def mws_partition(element_ids, edges, kinds, strengths, *, valid=None) -> dict:
    """Mutex partition with carried constraints and explicit late conflicts."""
    ids, pairs, weights, available, usable, keys = _graph_inputs(element_ids, edges, strengths, valid)
    kinds = np.asarray(kinds)
    if kinds.shape != (len(pairs),) or not set(kinds.tolist()) <= {"attractive", "repulsive", "none", "unavailable"}:
        raise ValueError("Unknown or incomplete relation kinds")
    if np.any(weights[usable] > 1) or np.any(usable & (kinds == "unavailable")):
        raise ValueError("Invalid usable relation strength/availability")
    groups = _Components(ids)
    mutex = [set() for _ in ids]
    stats = dict(merges=0, mutex_constraints=0, blocked_attractions=0, late_repulsive_conflicts=0)
    active = np.flatnonzero(usable & np.isin(kinds, ["attractive", "repulsive"]))
    order = sorted(active, key=lambda i: (-weights[i], 0 if kinds[i] == "repulsive" else 1, *keys[i]))
    for index in order:
        a, b = (groups.root(v) for v in pairs[index])
        if kinds[index] == "repulsive":
            if a == b:
                stats["late_repulsive_conflicts"] += 1
            elif b not in mutex[a]:
                mutex[a].add(b)
                mutex[b].add(a)
                stats["mutex_constraints"] += 1
        elif a != b:
            if b in mutex[a]:
                stats["blocked_attractions"] += 1
                continue
            neighbors = (mutex[a] | mutex[b]) - {a, b}
            kept, removed = groups.merge(a, b)
            for other in neighbors:
                mutex[other].difference_update({a, b})
                mutex[other].add(kept)
            mutex[kept] = neighbors
            mutex[removed] = set()
            stats["merges"] += 1
    return dict(component_ids=groups.labels(available), stats=stats)


def apply_refusals(element_ids, edges, proposals, passed, *, min_size: int = 4) -> tuple[list, list]:
    """Recompute connected components after removals, preserving proposal borders."""
    ids = _ids(element_ids, len(element_ids))
    pairs = _edges(edges, len(ids))
    proposed = list(proposals)
    accepted = np.asarray(passed, dtype=bool)
    if len(proposed) != len(ids) or accepted.shape != (len(ids),) or min_size < 1:
        raise ValueError("Invalid proposal, refusal mask or minimum component size")
    accepted = accepted & np.array([value is not None for value in proposed], dtype=bool)
    groups = _Components(ids)
    for a, b in pairs:
        if accepted[a] and accepted[b] and proposed[a] == proposed[b]:
            groups.merge(a, b)
    final, reasons = [], []
    for i in range(len(ids)):
        if proposed[i] is None:
            final.append(None)
            reasons.append("feature_unavailable")
        elif not accepted[i]:
            final.append(None)
            reasons.append("order_evidence_below_threshold")
        elif groups.size[groups.root(i)] < min_size:
            final.append(None)
            reasons.append("component_below_minimum_size")
        else:
            final.append(ids[groups.root(i)])
            reasons.append(None)
    return final, reasons


def partition_graph(element_ids, edges, features, adapter: dict, *, method: str = "fh4",
                    order_pass=None, min_size: int = 4) -> dict:
    """Inference on ONE frame/subset using a separately fitted immutable adapter."""
    ids = _ids(element_ids, len(features))
    pairs = _edges(edges, len(ids))
    projected, valid = transform_features(features, adapter)
    distances = np.full(len(pairs), np.nan)
    usable = valid[pairs].all(axis=1)
    if adapter["available"]:
        distances[usable] = np.linalg.norm(projected[pairs[usable, 0]] - projected[pairs[usable, 1]], axis=1) / adapter["edge_median"]
        kinds, strengths = relation_weights(distances, adapter["q25"], adapter["q75"])
    else:
        kinds = np.full(len(pairs), "unavailable", dtype="U11")
        strengths = np.full(len(pairs), np.nan)
    if method == "fh4":
        proposals = fh_partition(ids, pairs, distances, valid=valid)
        stats = {}
    elif method == "mws":
        result = mws_partition(ids, pairs, kinds, strengths, valid=valid)
        proposals, stats = result["component_ids"], result["stats"]
    else:
        raise ValueError("Unknown partition method")
    passed = np.ones(len(ids), dtype=bool) if order_pass is None else np.asarray(order_pass, dtype=bool)
    final, reasons = apply_refusals(ids, pairs, proposals, passed & valid, min_size=min_size)
    if not adapter["available"]:
        reasons = [adapter["reason"]] * len(ids)
    return dict(proposal_component_ids=proposals, final_component_ids=final, reasons=reasons,
                available=valid, edge_distances=distances, relation_kinds=kinds,
                relation_strengths=strengths, stats=stats)
