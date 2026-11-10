"""Three predeclared input views of the frozen issue-24 ego graphs.

The source eligibility, roots and support remain those of closed72. Changing
the endpoint convention or removing message passing is a diagnostic input
intervention, not a repaired or retrained encoder. No reference is read here.
"""
from __future__ import annotations

import numpy as np

from ..data import support_available
from ..graph_ssl.data import FEATURE_DIM, MAX_NODES, SUPPORT_SIZE, descriptor


MODES = ("closed72", "halfopen72", "root_only")
EPS = 1e-10
DESCRIPTOR_RADIUS = 24.


def _source(sample):
    """Check the prepared-cache layout without changing the selected roots."""
    eligible = np.asarray(sample["eligible"], dtype=bool)
    count = len(eligible)
    expected = {
        "x": (count, MAX_NODES, FEATURE_DIM),
        "adj": (count, MAX_NODES, MAX_NODES),
        "valid": (count, MAX_NODES),
        "node_indices": (count, MAX_NODES),
        "xyref": (count, 2),
        "adjacency_radius": (count,),
    }
    for name, shape in expected.items():
        if np.asarray(sample[name]).shape != shape:
            raise ValueError(f"Unexpected prepared {name} shape")
    if not np.isfinite(sample["xyref"]).all():
        raise ValueError("Non-finite source coordinates")
    selected = np.flatnonzero(eligible)
    if len(selected):
        if not np.asarray(sample["valid"])[selected, 0].all():
            raise ValueError("Eligible source root is padding")
        if not np.array_equal(np.asarray(sample["node_indices"])[selected, 0], selected):
            raise ValueError("Source root must remain padded-node index zero")
        radius = np.asarray(sample["adjacency_radius"])[selected]
        if not (np.isfinite(radius).all() and ((radius > 0) & (radius <= 24.)).all()):
            raise ValueError("Invalid pinned closed72 adjacency radius")
    return eligible


def _empty(count):
    return dict(
        x=np.zeros((count, MAX_NODES, FEATURE_DIM), dtype=np.float32),
        adj=np.zeros((count, MAX_NODES, MAX_NODES), dtype=bool),
        valid=np.zeros((count, MAX_NODES), dtype=bool),
        node_indices=np.full((count, MAX_NODES), -1, dtype=np.int32),
    )


def build_inputs(sample, mode):
    """Return x/adj/valid/node_indices with the original padded 128-node layout.

    ``sample`` is one item from graph_ssl.data.iter_prepared. Ineligible rows
    stay zero/false/-1 in every mode; no root is newly admitted or dropped.
    Half-open comparisons include the lower endpoint within EPS and exclude
    values within EPS of the upper endpoint. Its graph radius is taken from
    the original closed72 cache, never estimated again after removing nodes.
    """
    if mode not in MODES:
        raise ValueError(f"Unknown context mode: {mode}")
    eligible = _source(sample)
    output = _empty(len(eligible))
    selected = np.flatnonzero(eligible)
    if mode == "closed72":
        for name in output:
            output[name][selected] = np.asarray(sample[name])[selected]
        return output

    xyref = np.asarray(sample["xyref"], dtype=np.float64)
    for index in selected:
        if mode == "root_only":
            output["x"][index, 0] = sample["x"][index, 0]
            output["adj"][index, 0, 0] = True
            output["valid"][index, 0] = True
            output["node_indices"][index, 0] = index
            continue

        original = np.asarray(sample["node_indices"])[index, np.asarray(sample["valid"])[index]]
        if (original < 0).any() or (original >= len(eligible)).any():
            raise ValueError("Source graph refers to an invalid annotation")
        delta = xyref[original] - xyref[index]
        half = SUPPORT_SIZE / 2
        inside = ((delta >= -half - EPS) & (delta < half - EPS)).all(axis=1)
        nodes = original[inside]
        if not len(nodes) or nodes[0] != index or len(nodes) > MAX_NODES:
            raise ValueError("Half-open intervention changed the root or exceeded padding")
        points = xyref[nodes]
        features = descriptor(points)
        # Only nodes at >=36-EPS from the root can be removed; none contributes
        # to its radius24 descriptor. Require exact agreement, not normalization
        # or a corrected feature vector silently substituted after a mismatch.
        if not np.array_equal(features[0], sample["x"][index, 0]):
            raise ValueError("Half-open context changed the root's 57 input features")
        distance = np.linalg.norm(points[None, :, :] - points[:, None, :], axis=2)
        adjacent = distance <= float(sample["adjacency_radius"][index]) + EPS
        count = len(nodes)
        output["x"][index, :count] = features
        output["adj"][index, :count, :count] = adjacent
        output["valid"][index, :count] = True
        output["node_indices"][index, :count] = nodes
    return output


def dependency_audit(sample, inputs):
    """Describe geometric support needed by each fixed two-layer root output.

    Two-hop reachability follows the supplied adjacency, including self loops.
    The required rectangle bounds radius24 disks around those nodes. It is a
    conservative certificate: the entire rectangle must be measured and lie
    inside the half-open ego72 and image field [0,W)x[0,H). False does not prove
    a wrong prediction, and these arrays must never filter prediction roots.

    The audit conditions on the pinned closed72 edge radius. Its original
    whole-crop NN calibration is an additional, unchanged source dependency;
    the rectangle does not claim to erase that calibration dependency.
    """
    eligible = _source(sample)
    count = len(eligible)
    for name, value in _empty(count).items():
        if np.asarray(inputs[name]).shape != value.shape:
            raise ValueError(f"Unexpected intervention {name} shape")
    spacing = np.asarray(sample["record"]["pixel_spacing_xy"], dtype=np.float64)
    if spacing.shape != (2,) or not np.isfinite(spacing).all() or (spacing <= 0).any():
        raise ValueError("Invalid reference-pixel spacing")
    measured = np.asarray(sample["arrays"]["measured"], dtype=bool)
    if measured.ndim != 2:
        raise ValueError("Expected a two-dimensional measured mask")
    height, width = measured.shape
    xyref = np.asarray(sample["xyref"], dtype=np.float64)
    result = dict(
        two_hop_node_count=np.zeros(count, dtype=np.int32),
        required_box_ref=np.full((count, 4), np.nan, dtype=np.float64),
        complete_inside_ego72=np.zeros(count, dtype=bool),
    )
    for index in np.flatnonzero(eligible):
        valid = np.asarray(inputs["valid"])[index].astype(bool)
        adj = np.asarray(inputs["adj"])[index].astype(bool)
        adj = adj & valid[:, None] & valid[None, :]
        if not valid[0] or not adj[0, 0]:
            raise ValueError("Intervention root must retain its self loop")
        first = adj[0]
        second = adj[first].any(axis=0) & valid
        nodes = np.asarray(inputs["node_indices"])[index, second]
        if not len(nodes) or (nodes < 0).any() or (nodes >= count).any():
            raise ValueError("Invalid two-hop source annotation indices")
        points = xyref[nodes]
        box = np.r_[points.min(axis=0) - DESCRIPTOR_RADIUS,
                    points.max(axis=0) + DESCRIPTOR_RADIUS]
        half = SUPPORT_SIZE / 2
        lower, upper = xyref[index] - half, xyref[index] + half
        inside_ego = bool((box[:2] >= lower - EPS).all() and (box[2:] < upper - EPS).all())
        raw = box / np.tile(spacing, 2)
        # A closed radius disk touching the excluded upper field edge is not a
        # complete observed neighborhood. The lower raw-edge endpoint is valid.
        inside_field = bool((box[:2] >= -EPS).all() and
                            (box[2:] < np.array([width, height]) * spacing - EPS).all())
        result["two_hop_node_count"][index] = len(nodes)
        result["required_box_ref"][index] = box
        result["complete_inside_ego72"][index] = (
            inside_ego and inside_field and support_available(raw, measured))
    return result
