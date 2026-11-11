"""Nine paired known structural changes, without domain labels or model fitting."""

from __future__ import annotations

import numpy as np

from .controls import lattice, render_points
from .training.data import extract_patch

CONDITIONS = ("identity", "orientation8", "spacing16", "phase4")
PHASES = ((0., 0.), (2., 1.), (4., 3.))
SEEDS = (20261111, 20261112, 20261113)


def make_structure_probe() -> dict:
    """Render96 then sample the same central48 support at48/64 resolution.

    Every phase×seed block receives all four conditions. Fresh identically
    seeded renderers supply exactly the same noise field within a block.
    The phase4 arm shifts the lattice uniformly by (0,4) raw pixels: it is
    not a phase boundary or an extra domain. The orientation8 arm is not a
    square-lattice quarter turn. All arms keep the historical renderer and
    photometric bridge clip(0.5 + 0.4*signal,0,1), applied AFTER interpolation.
    No parameter, support, noise draw or amplitude depends on labels/features.
    """
    patches64 = {name: [] for name in CONDITIONS}
    native48 = {name: [] for name in CONDITIONS}
    sources96 = {name: [] for name in CONDITIONS}
    metadata = []
    row = dict(available=True, raw_edge_xy=[48., 48.], scale_raw_px=48.,
               support_xyxy=[21., 21., 75., 75.])
    normalizer = dict(low=0., high=1.)
    measured = np.ones((96, 96), bool)
    for phase_index, phase in enumerate(PHASES):
        for seed in SEEDS:
            configurations = dict(identity=(0., 12., phase), orientation8=(8., 12., phase),
                                  spacing16=(0., 16., phase), phase4=(0., 12., (phase[0], phase[1] + 4.)))
            clipping = {}
            for name, (angle, spacing, offset) in configurations.items():
                points = lattice((96, 96), spacing=spacing, angle=angle, phase=offset)
                signal = render_points(points, (96, 96), np.random.default_rng(seed))
                image = .5 + .4 * signal
                arrays = dict(image=image, measured=measured)
                sources96[name].append(image)
                clipped = {}
                for size, target in ((48, native48), (64, patches64)):
                    raw = extract_patch(arrays, row, None, size=size)
                    target[name].append(extract_patch(arrays, row, normalizer, size=size))
                    clipped[str(size)] = dict(pixels=raw.size, below_zero=int((raw < 0).sum()),
                                              above_one=int((raw > 1).sum()))
                clipping[name] = clipped
            metadata.append(dict(id=f"phase-{phase_index}-seed-{seed}", baseline_phase_xy=list(phase),
                                 noise_seed=seed, shape_hw=[96, 96], center_raw_xy=[48., 48.],
                                 scale_raw_px=48, clipping=clipping))
    return dict(conditions=list(CONDITIONS), patches64={k: np.stack(v) for k, v in patches64.items()},
                native48={k: np.stack(v) for k, v in native48.items()},
                sources96={k: np.stack(v) for k, v in sources96.items()}, metadata=metadata,
                changes=dict(identity=dict(angle_deg=0., spacing_px=12., phase_delta_xy=[0., 0.]),
                             orientation8=dict(angle_deg=8., spacing_px=12., phase_delta_xy=[0., 0.]),
                             spacing16=dict(angle_deg=0., spacing_px=16., phase_delta_xy=[0., 0.]),
                             phase4=dict(angle_deg=0., spacing_px=12., phase_delta_xy=[0., 4.])),
                interpretation="Paired known image changes, no domain labels; uniform phase shift is not a boundary",
                photometry="clip(0.5+0.4*rendered_signal,0,1) after bilinear extraction; no local normalization")
