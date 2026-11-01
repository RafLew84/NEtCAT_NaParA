"""Frozen issue-15 geometry adapted to the finite ego support of trial 24.

The numeric rules below are copied from the final issue-15 prototype. Only
the selected R36 / tolerance .24 recurrence is computed. ``compute_geometry``
keeps the old full-frame context for a technical reproduction audit;
``compute_sample_geometry`` uses each pivot's own 72 x 72 reference-pixel
crop, exactly the input support supplied to the graph model. That restriction
is an explicit trial-24 adaptation, not the original issue-15 prediction.

No labels, catalogue fitting, image intensity or reference masks enter here.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree


SOURCE_COMMIT = "2b70d0d"
SOURCE_SHA256 = {
    "stmdomains/prototypes/orientation_trial.py":
        "58c036297563bbe8d3b5321a85ab357170e70cf4d33310535da7379a3a5cf8de",
    "stmdomains/prototypes/recurrence_trial.py":
        "48e7c9393dcb439e7106899e4a0c857618c6a63b4dcb03256af6c9f70431622f",
    "stmdomains/prototypes/local_neighborhoods.py":
        "013326d6108a3b5d75ffefb356ae9acca6f9a028d593338526bd5ffa054b6779",
}
RADIUS = 36.0
GATE = dict(radius=36, tolerance=.24, mode=1, threshold=.25)
LEGACY_CONFIGURATION = dict(id="cell-0.65-0.12-0.3-seed", family="cell",
                            fraction=.65, distance=.12, phase=.3, graph="seed")


def integer(x):
    return np.rint(np.round(x, 10))


def reduce_basis(b):
    b = b.copy()
    for _ in range(8):
        if np.dot(b[1], b[1]) < np.dot(b[0], b[0]) - 1e-9:
            b = b[::-1].copy()
        k = integer(np.dot(b[0], b[1]) / max(np.dot(b[0], b[0]), 1e-12))
        if k == 0:
            break
        b[1] -= k * b[0]
    return b


def basis_distance(a, b):
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        return np.inf
    out = []
    for x, y in ((a, b), (b, a)):
        k = integer(x @ np.linalg.inv(y))
        if abs(round(np.linalg.det(k))) != 1:
            return np.inf
        out.append(float(np.max(np.linalg.norm(x - k @ y, axis=1)) /
                         max(np.min(np.linalg.norm(y, axis=1)), 1e-9)))
    return max(out)


def phase_distance(a, b, oa, ob, spacing):
    d = ob - oa
    distances = []
    for basis in (a, b):
        uv = d @ np.linalg.inv(basis)
        distances.append(np.linalg.norm((uv - integer(uv)) @ basis) / spacing)
    return max(distances)


def fit_cell(local, spacing):
    """The selected issue-15 translation-peak cell fit, without retuning."""
    empty = (np.full((2, 2), np.nan), np.full(2, np.nan), 0., np.nan, 0, False)
    if len(local) < 9 or spacing <= 0:
        return empty
    ix, iy = np.triu_indices(len(local), 1)
    diff = local[iy] - local[ix]
    length = np.linalg.norm(diff, axis=1)
    diff = diff[(length >= .6 * spacing - 1e-7) &
                (length <= 2.5 * spacing + 1e-7)]
    if len(diff) < 6:
        return empty
    diff = np.vstack([diff, -diff])
    tree = cKDTree(diff)
    hood = tree.query_ball_point(diff, .22 * spacing + 1e-7)
    counts = np.array([len(x) for x in hood])
    order = np.argsort(-counts, kind="stable")
    peaks = []
    for idx in order:
        if counts[idx] < 3:
            break
        v = diff[hood[idx]].mean(0)
        if any(min(np.linalg.norm(v - w), np.linalg.norm(v + w)) < .4 * spacing
               for w in peaks):
            continue
        peaks.append(v)
        if len(peaks) == 8:
            break
    fits = []
    center = local[0]
    relative = local - center
    for i, a in enumerate(peaks):
        for b in peaks[i + 1:]:
            basis = np.array([a, b])
            if abs(np.linalg.det(basis)) < .3 * np.linalg.norm(a) * np.linalg.norm(b):
                continue
            basis = reduce_basis(basis)
            origin = np.zeros(2)
            for _ in range(2):
                coords = integer((relative - origin) @ np.linalg.inv(basis))
                error = np.linalg.norm(relative - origin - coords @ basis, axis=1)
                mask = error <= .24 * spacing + 1e-7
                x = np.c_[coords[mask], np.ones(mask.sum())]
                if mask.sum() < 8 or np.linalg.matrix_rank(x) < 3:
                    break
                fitted = np.linalg.lstsq(x, relative[mask], rcond=None)[0]
                newbasis = fitted[:2]
                if abs(np.linalg.det(newbasis)) < .3 * spacing ** 2:
                    break
                basis, origin = newbasis, fitted[2]
            coords = integer((relative - origin) @ np.linalg.inv(basis))
            err = np.linalg.norm(relative - origin - coords @ basis, axis=1)
            mask = err <= .24 * spacing + 1e-7
            if (mask.sum() < 8 or not mask[0] or
                    np.linalg.matrix_rank(np.c_[coords[mask], np.ones(mask.sum())]) < 3):
                continue
            rms = float(np.sqrt(np.mean(err[mask] ** 2)) / spacing)
            fraction = float(mask.mean())
            area = abs(np.linalg.det(basis)) / spacing ** 2
            score = (int(mask.sum()), -round(rms, 6), -round(area, 6))
            fits.append((score, basis, origin + center, fraction, rms, int(mask.sum())))
    if not fits:
        return empty
    fits.sort(key=lambda value: value[0], reverse=True)
    best = fits[0]
    ambiguous = any(f[3] >= best[3] - .02 and f[4] <= best[4] + .02 and
                    basis_distance(best[1], f[1]) > .22 for f in fits[1:])
    return best[1], best[2], best[3], best[4], best[5], ambiguous


def _empty(n):
    return dict(score=np.zeros(n), available=np.zeros(n, bool),
                support=np.zeros(n, np.int64), spacing=np.zeros(n),
                gate=np.zeros(n, bool), angular=np.zeros((n, 6), complex),
                basis=np.full((n, 2, 2), np.nan), origin=np.full((n, 2), np.nan),
                cell_fraction=np.zeros(n), cell_rms=np.full(n, np.nan),
                cell_inliers=np.zeros(n, np.int64), cell_ambiguous=np.zeros(n, bool))


def _pivot(p, shape, index, tree, nearest):
    """Compute only one pivot, preserving the original float/cutoff rules."""
    ids = np.asarray(tree.query_ball_point(p[index], RADIUS + 1e-7), dtype=int)
    ids = ids[ids != index]
    support = len(ids)
    if support == 0:
        return None
    spacing = float(np.median(nearest[np.r_[index, ids]]))
    score, available = 0., False
    v = p[ids] - p[index]
    d = np.linalg.norm(v, axis=1)
    vectors = v[(d >= .65 * spacing) & (d <= min(.8 * RADIUS, 1.8 * spacing))]
    local = p[np.r_[index, ids]]
    trials = []
    for vector in vectors:
        # A zero spacing can occur in the explicit duplicate-centre challenge.
        # The old algorithm has no informative translation in that case.
        if np.linalg.norm(vector) == 0:
            continue
        moved = local + vector
        valid = (np.all((moved >= 0) & (moved < shape), axis=1) &
                 (np.linalg.norm(moved - p[index], axis=1) <= RADIUS + 1e-7))
        if valid.sum() < 8:
            continue
        distances = tree.query(moved, k=1)[0] / max(spacing, 1e-12)
        valid[0] = False
        if valid.sum() >= 8:
            trials.append((float(np.mean(distances[valid] <= .24)),
                           vector / np.linalg.norm(vector)))
    for j, (q, u) in enumerate(trials):
        for z, w in trials[j + 1:]:
            if abs(u[0] * w[1] - u[1] * w[0]) >= .3:
                score = max(score, min(q, z))
                available = True
    # Cell and angular descriptions use the original sorted-neighbour ordering.
    local = p[[index] + sorted(ids.tolist())]
    angular = np.zeros(6, complex)
    if spacing > 0:
        ix, iy = np.triu_indices(len(local), 1)
        delta = local[iy] - local[ix]
        length = np.linalg.norm(delta, axis=1)
        keep = ((length >= .6 * spacing - 1e-7) &
                (length <= 1.5 * spacing + 1e-7))
        if keep.any():
            midpoint = (local[ix] + local[iy]) / 2
            weight = np.exp(-.5 * (np.linalg.norm(midpoint - p[index], axis=1) /
                                   (RADIUS * .65)) ** 2)[keep]
            phi = np.arctan2(delta[keep, 1], delta[keep, 0])
            angular = np.average(np.exp(1j * phi[:, None] * np.array([2, 4, 6, 8, 10, 12])),
                                 axis=0, weights=weight)
    basis, origin, fraction, rms, inliers, ambiguous = fit_cell(local, spacing)
    return dict(score=score, available=available, support=support, spacing=spacing,
                gate=support >= 8 and available and score > .25,
                angular=angular, basis=basis, origin=origin, cell_fraction=fraction,
                cell_rms=rms, cell_inliers=inliers, cell_ambiguous=ambiguous)


def compute_geometry(xy_ref, shape):
    """Full-frame issue-15 geometry for audit; shape is [width, height]."""
    p, shape = np.asarray(xy_ref, float), np.asarray(shape, float)
    result = _empty(len(p))
    if len(p) < 2:
        return result
    tree = cKDTree(p)
    nearest = tree.query(p, k=2)[0][:, 1]
    for index in range(len(p)):
        values = _pivot(p, shape, index, tree, nearest)
        if values is not None:
            for key, value in values.items():
                result[key][index] = value
    return result


def compute_sample_geometry(xy_ref, shape, eligible, node_indices=None):
    """R36 geometry from exactly each eligible root's finite 72px ego crop.

    Coordinates and node indices use the same canonical per-sample centre
    order. ``node_indices`` is N-by-M with root at column zero and padding -1.
    It should be the actual graph input selection. If omitted, all centres in
    the square are selected, with the root first and others in index order.
    Unavailable roots keep explicit false gate/availability and NaN cell fits.
    ``shape`` is accepted for the shared API; full support is supplied by the
    caller's eligibility audit and each local geometry is bounded by [72,72].
    """
    p = np.asarray(xy_ref, float)
    eligible = np.asarray(eligible, bool)
    if eligible.shape != (len(p),):
        raise ValueError("One eligibility flag is required per centre")
    result = _empty(len(p))
    for index in np.flatnonzero(eligible):
        if node_indices is None:
            inside = np.flatnonzero(np.all(np.abs(p - p[index]) <= RADIUS + 1e-7, axis=1))
            ids = np.r_[index, inside[inside != index]]
        else:
            ids = np.asarray(node_indices[index], dtype=int)
            ids = ids[ids >= 0]
            if not len(ids) or ids[0] != index or len(np.unique(ids)) != len(ids):
                raise ValueError("Ego indices must start with the unique pivot")
        if len(ids) < 2:
            continue
        lower = p[index] - RADIUS
        local = p[ids] - lower
        if np.any(local < -1e-7) or np.any(local > 2 * RADIUS + 1e-7):
            raise ValueError("Ego context escapes its declared support")
        tree = cKDTree(local)
        nearest = tree.query(local, k=2)[0][:, 1]
        values = _pivot(local, np.array([72., 72.]), 0, tree, nearest)
        if values is not None:
            values["origin"] += lower
            for key, value in values.items():
                result[key][index] = value
    return result


def legacy_join(xy_ref, features, eligible_mask=None):
    """Issue-15 selected cell/phase/seed joining, with unavailable roots removed.

    Inputs must be in canonical object-ID order, as in the issue-15 prototype.
    This is the complete classical reference procedure, not a fitted graph
    feature adapter. Group IDs are arbitrary and type remains unknown.
    """
    p, f = np.asarray(xy_ref, float), features
    n = len(p)
    eligible = (f["gate"] & (f["cell_fraction"] >= .65) & ~f["cell_ambiguous"])
    if eligible_mask is not None:
        eligible &= np.asarray(eligible_mask, bool)
    quality = f["cell_fraction"] - np.nan_to_num(f["cell_rms"], nan=1)

    def compatible(i, j, edge=True):
        if basis_distance(f["basis"][i], f["basis"][j]) > .12:
            return False
        return (not edge or phase_distance(f["basis"][i], f["basis"][j],
                                           f["origin"][i], f["origin"][j],
                                           min(f["spacing"][i], f["spacing"][j])) <= .3)

    adjacency = [[] for _ in range(n)]
    if n and f["spacing"].max() > 0:
        for i, j in sorted(cKDTree(p).query_pairs(1.65 * float(f["spacing"].max()))):
            if not (eligible[i] and eligible[j]):
                continue
            if np.linalg.norm(p[i] - p[j]) > 1.65 * min(f["spacing"][i], f["spacing"][j]) + 1e-7:
                continue
            if compatible(i, j):
                adjacency[i].append(j)
                adjacency[j].append(i)
    domains = np.zeros(n, np.int64)
    for seed in np.argsort(-np.round(quality, 8), kind="stable"):
        if domains[seed] or not eligible[seed]:
            continue
        visited, queue = {int(seed)}, [int(seed)]
        for i in queue:
            for j in adjacency[i]:
                if j in visited or domains[j]:
                    continue
                visited.add(j)
                if compatible(seed, j, edge=False):
                    queue.append(j)
        if len(queue) >= 8:
            domains[queue] = domains.max() + 1
    return domains
