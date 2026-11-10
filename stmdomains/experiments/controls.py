"""Synthetic point/image pairs and separate, explicit evaluation truth.

These controls define idealized lattice domains, never molecular coverage masks.
They are tests of behavior, not realistic STM simulations or training labels.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

from .bundle import validate_input

CASES = ("random", "random_minsep", "random_gradient", "noise", "stripes",
         "single", "two_orientations", "different_spacing", "oblique", "disjoint",
         "phase_boundary", "single_defect", "disordered_band", "missing_10",
         "missing_30", "missing_50", "missing_local", "contrast", "inverted",
         "crop", "resample_2x", "larger_spacing")
SEEDS = {"development": (1701, 1702, 1703), "evaluation": (2701, 2702, 2703)}


def lattice(shape, spacing=12., angle=0., skew=0., phase=(0., 0.)):
    yy, xx = np.mgrid[-35:36, -35:36]
    points = np.column_stack((xx.ravel(), yy.ravel())).astype(float)
    points = points @ np.array([[spacing, 0.], [skew * spacing, spacing]])
    a = np.deg2rad(angle)
    points = points @ np.array([[np.cos(a), np.sin(a)], [-np.sin(a), np.cos(a)]])
    points += np.array(shape[::-1]) / 2 + phase
    return points[np.all((points >= 0) & (points < shape[::-1]), axis=1)]


def render_points(points, shape, rng):
    """Bilinear splats followed by a Gaussian PSF; noise seed held across ablations."""
    image = np.zeros(shape, float)
    positions = points - .5  # coordinates describe pixel edges/centers, not array indices
    lo = np.floor(positions).astype(int)
    frac = positions - lo
    for dx in (0, 1):
        for dy in (0, 1):
            p = lo + [dx, dy]
            good = np.all((p >= 0) & (p < shape[::-1]), axis=1)
            weights = (frac[:, 0] if dx else 1-frac[:, 0]) * (frac[:, 1] if dy else 1-frac[:, 1])
            np.add.at(image, (p[good, 1], p[good, 0]), weights[good])
    return ndi.gaussian_filter(image, 1.25) * 12 + rng.normal(0, .025, shape)


def make_control(case: str, seed: int, shape=(192, 192)) -> tuple[dict, dict, dict]:
    if case not in CASES:
        raise ValueError(case)
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:shape[0], :shape[1]]
    x = xx + .5
    points = lattice(shape)
    domains = np.ones(shape, np.int16)
    types = np.ones(shape, np.int16)
    angle = np.zeros(shape, float)
    spacing = np.full(shape, 12., float)
    boundary = np.zeros(shape, bool)
    pixel_spacing, offset = 1., [0., 0.]
    negative = case in ("random", "random_minsep", "random_gradient", "noise", "stripes")
    if negative:
        domains[:] = 0; types[:] = 0; angle[:] = np.nan; spacing[:] = np.nan
        if case in ("noise", "stripes"):
            points = np.empty((0, 2))
        elif case == "random":
            points = rng.uniform([0., 0.], shape[::-1], (256, 2))
        else:
            pool = rng.uniform([0., 0.], shape[::-1], (12000, 2))
            if case == "random_gradient":
                pool = pool[rng.random(len(pool)) < (.12 + .88 * pool[:, 0]/shape[1])]
            selected = []
            for p in pool:
                if case == "random_gradient" or not selected or np.min(np.linalg.norm(np.array(selected)-p, axis=1)) >= 7:
                    selected.append(p)
                if len(selected) == 256:
                    break
            points = np.array(selected)
    elif case in ("two_orientations", "different_spacing", "phase_boundary"):
        second = lattice(shape, spacing=16. if case == "different_spacing" else 12.,
                         angle=27. if case == "two_orientations" else 0.,
                         phase=(0., 4.) if case == "phase_boundary" else (0., 0.))
        points = np.vstack((points[points[:, 0] < shape[1]/2], second[second[:, 0] >= shape[1]/2]))
        right = x >= shape[1]/2
        domains[right] = 2
        boundary = np.abs(x - shape[1]/2) < 3
        if case == "two_orientations": angle[right] = 27.
        if case == "different_spacing": types[right] = 2; spacing[right] = 16.
    elif case == "oblique":
        points = lattice(shape, skew=.35); types[:] = 3
        angle[:] = np.nan  # a scalar angle does not specify this oblique cell
        spacing[:] = np.nan
    elif case == "larger_spacing":
        points = lattice(shape, spacing=16.); types[:] = 2; spacing[:] = 16.
    elif case == "disjoint":
        domains[:, shape[1]//2-18:shape[1]//2+18] = 0
        domains[:, shape[1]//2+18:] = 2
        points = points[np.abs(points[:, 0]-shape[1]/2) >= 18]
        types[domains == 0] = 0
        boundary = (np.abs(x-(shape[1]/2-18)) < 3) | (np.abs(x-(shape[1]/2+18)) < 3)
    elif case == "single_defect":
        points = np.delete(points, np.argmin(np.linalg.norm(points-np.array(shape[::-1])/2, axis=1)), axis=0)
    elif case == "disordered_band":
        band = np.abs(x-shape[1]/2) < 18
        domains[band] = 0; domains[x >= shape[1]/2+18] = 2; types[band] = 0
        points = points[np.abs(points[:, 0]-shape[1]/2) >= 18]
        points = np.vstack((points, rng.uniform([shape[1]/2-18, 0], [shape[1]/2+18, shape[0]], (48, 2))))
        boundary = (np.abs(x-(shape[1]/2-18)) < 3) | (np.abs(x-(shape[1]/2+18)) < 3)
    image = render_points(points, shape, np.random.default_rng(seed+40000))
    if case == "stripes": image += .4 * np.cos(yy * 2*np.pi / 12)
    if case == "contrast": image = image * (.25 + 1.5*x/shape[1]) + .2
    if case == "inverted": image = -image
    # Detection ablations leave the underlying image and truth unchanged.
    keep = np.ones(len(points), bool)
    if case.startswith("missing_"):
        if case == "missing_local":
            keep = ~((np.abs(points[:, 0]-shape[1]/2) < 22) & (np.abs(points[:, 1]-shape[0]/2) < 32))
        else:
            keep[rng.permutation(len(points))[:round(len(points)*int(case.split('_')[1])/100)]] = False
    ids = np.array([f"p{i:05}" for i in range(len(points))], dtype="U64")
    if case == "crop":
        # Crop an actual measurement field, not a centered domain-shaped ROI.
        slices = (slice(19, 170), slice(23, 176)); offset = [23., 19.]
        image, domains, types, angle, spacing, boundary = [a[slices] for a in (image, domains, types, angle, spacing, boundary)]
        points = points - offset
        keep &= np.all((points >= 0) & (points < image.shape[::-1]), axis=1)
    if case == "resample_2x":
        image = ndi.zoom(image, 2, order=1, grid_mode=True, mode="nearest")
        domains, types, angle, spacing, boundary = [np.repeat(np.repeat(a, 2, 0), 2, 1) for a in (domains, types, angle, spacing, boundary)]
        points = points * 2; pixel_spacing = .5
    observed = points[keep]
    radius = 2.5 / pixel_spacing
    arrays = dict(image=image, measured=np.ones(image.shape, bool), centers_xy=observed,
                  boxes_xyxy=np.column_stack((observed-radius, observed+radius)), object_ids=ids[keep])
    validate_input(arrays)
    angle[domains == 0] = np.nan; spacing[domains == 0] = np.nan
    truth = dict(domain_labels=domains, type_labels=types, orientation_deg=angle,
                 spacing_reference_px=spacing, evaluation_valid=~boundary, boundary_uncertain=boundary)
    meta = dict(case=case, seed=seed, expected_domain_count=int(domains.max()),
                scope="idealized_lattice_domains_not_material_coverage", boundary_tolerance_px=3/pixel_spacing,
                pixel_spacing_xy=[pixel_spacing]*2, offset_in_base_xy=offset,
                base_pair="single" if case in ("missing_10", "missing_30", "missing_50", "missing_local", "contrast", "inverted", "crop", "resample_2x", "single_defect") else None,
                render=dict(psf_sigma_reference_px=1.25, noise_sigma=.025),
                lattice_basis_reference_px=[[12., 0.], [4.2, 12.]] if case == "oblique" else None)
    return arrays, truth, meta
