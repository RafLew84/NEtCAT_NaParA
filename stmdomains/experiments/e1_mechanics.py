"""Isolated E1 gate ablations and synthetic oracle mechanics, without fitting."""

from __future__ import annotations

import numpy as np

from .training.partition import apply_refusals, fh_partition, mws_partition
from .training.predict import label_numbers


def gate_masks(available, valid, acf, ratio, energy, threshold) -> dict:
    """Return independent decisions; ``hard`` is applied AFTER partitioning.

    Threshold failures require a finite observation. Missing measurements have
    their own failure flags and remain forbidden even when both gates are off.
    Callers combine hard & optional acf & optional spectral without changing the
    feature-valid graph supplied to the partition algorithm.
    """
    available, valid = np.asarray(available, bool), np.asarray(valid, bool)
    acf, ratio, energy = (np.asarray(values, float) for values in (acf, ratio, energy))
    if available.ndim != 1 or any(values.shape != available.shape for values in (valid, acf, ratio, energy)):
        raise ValueError("Gate inputs must be equally sized vectors")
    if not np.isfinite(threshold) or threshold < 0:
        raise ValueError("ACF threshold must be finite and nonnegative")
    finite_acf, finite_ratio, finite_energy = (np.isfinite(values) for values in (acf, ratio, energy))
    failures = dict(
        incomplete_support=~available,
        invalid_measurement=~valid,
        nonfinite_acf=~finite_acf,
        nonfinite_spectral=~finite_ratio,
        nonfinite_energy=~finite_energy,
        nonpositive_energy=finite_energy & (energy <= 0),
        acf_below_threshold=finite_acf & (acf <= threshold),
        spectral_below_threshold=finite_ratio & (ratio < .25),
    )
    return dict(
        hard=available & valid & finite_acf & finite_ratio & finite_energy & (energy > 0),
        acf=finite_acf & (acf > threshold),
        spectral=finite_ratio & (ratio >= .25),
        failures=failures,
    )


def oracle_proposals(ids, edges, truth, feature_valid, partition) -> list[str | None]:
    """Replace relations, keeping the feature-valid nodes and original edges.

    Only equal POSITIVE truth labels attract. Zero never denotes one shared
    background domain. FH uses 0/5 with k=4; MWS uses unit-strength relations,
    repulsive on every other edge. Feature validity is the original before>0
    mask, not the hard/order/oracle-presence mask applied after partitioning.
    """
    truth = np.asarray(truth)
    feature_valid = np.asarray(feature_valid, bool)
    if truth.shape != (len(ids),) or truth.dtype.kind not in "iu" or np.any(truth < 0):
        raise ValueError("Oracle truth must be a nonnegative integer vector")
    if feature_valid.shape != truth.shape:
        raise ValueError("Feature availability must align with oracle truth")
    pairs = np.asarray(edges)
    if pairs.size == 0:
        pairs = np.empty((0, 2), dtype=np.int64)
    if pairs.ndim != 2 or pairs.shape[1] != 2 or pairs.dtype.kind not in "iu":
        raise ValueError("Edges must be an integer E-by-2 array")
    if np.any(pairs < 0) or np.any(pairs >= len(ids)):
        raise ValueError("Edge endpoint outside oracle graph")
    a, b = pairs.T
    same_positive = (truth[a] > 0) & (truth[a] == truth[b])
    if partition == "fh4":
        return fh_partition(ids, pairs, np.where(same_positive, 0., 5.), valid=feature_valid, k=4.)
    if partition == "mws":
        kinds = np.where(same_positive, "attractive", "repulsive")
        return mws_partition(ids, pairs, kinds, np.ones(len(pairs)), valid=feature_valid)["component_ids"]
    raise ValueError("Unknown partition method")


def truth_at_rows(rows, domain_labels) -> np.ndarray:
    """Sample truth at raw pixel-edge coordinates by floor; never clip."""
    labels = np.asarray(domain_labels)
    if labels.ndim != 2 or labels.dtype.kind not in "iu" or np.any(labels < 0):
        raise ValueError("Domain labels must be a nonnegative integer raster")
    xy = np.asarray([row["raw_edge_xy"] for row in rows], float) if rows else np.empty((0, 2))
    if xy.shape != (len(rows), 2):
        raise ValueError("Truth sampling positions must have shape N-by-2")
    if not np.isfinite(xy).all():
        raise ValueError("Non-finite truth sampling position")
    if np.any(xy < 0) or np.any(xy >= [labels.shape[1], labels.shape[0]]):
        raise ValueError("Truth sampling position outside raster")
    indices = np.floor(xy).astype(np.int64)
    return labels[indices[:, 1], indices[:, 0]]


def apply_variant(ids, edges, proposals, passed, min_size) -> dict:
    """Recompute connectivity after node refusal, then apply the size minimum.

    ``min_size=1`` disables the size decision while retaining recomputation.
    ``passed`` includes hard conditions for every variant, including oracle.
    """
    components, reasons = apply_refusals(ids, edges, proposals, passed, min_size=min_size)
    return dict(after=label_numbers(components), components=components, reasons=reasons)
