"""Single-frame contrast barriers adapted from v0.4, with lengths tied to input scale.

Near-horizontal positive steps only; these are exploratory image barriers, not
physical terrace labels. No external images, masks or calibration files are read.
"""

from collections.abc import Callable
from typing import Any

import numpy as np
from scipy import ndimage as ndi
from stmdomains.analysis.barrier_settings import BarrierSettings


def _components(mask: np.ndarray, check: Callable[[], None]) -> list[dict[str, Any]]:
    labels = np.zeros(mask.shape, dtype=np.int32)
    ndi.label(mask, np.ones((3, 3), dtype=bool), output=labels)
    result = []
    for label, sl in enumerate(ndi.find_objects(labels), 1):
        check()
        if sl is None:
            continue
        yy, xx = np.nonzero(labels[sl] == label)
        yy, xx = yy + sl[0].start, xx + sl[1].start
        xs = np.unique(xx)
        ys = np.array([np.median(yy[xx == x]) for x in xs])
        result.append(dict(label=label, pixels=len(xx), span_x=int(xs[-1] - xs[0] + 1),
                           xmin=int(xs[0]), xmax=int(xs[-1]), xs=xs, ys=ys))
    return result


def _long_components(mask: np.ndarray, min_span: int, check: Callable[[], None]) -> np.ndarray:
    labels = np.zeros(mask.shape, dtype=np.int32)
    ndi.label(mask, np.ones((3, 3), dtype=bool), output=labels)
    keep = [c['label'] for c in _components(mask, check) if c['span_x'] >= min_span]
    return np.isin(labels, keep)


def _line_samples(a, b, shape):
    a, b = np.asarray(a, float), np.asarray(b, float)
    count = max(2, int(np.ceil(np.linalg.norm(b - a) * 3)) + 1)
    line = a[None, :] + np.linspace(0, 1, count)[:, None] * (b - a)[None, :]
    xx = np.clip(np.rint(line[:, 0]).astype(int), 0, shape[1] - 1)
    yy = np.clip(np.rint(line[:, 1]).astype(int), 0, shape[0] - 1)
    return yy, xx


def _endpoint(c, side):
    n = min(10, len(c['xs']))
    xx, yy = (c['xs'][:n], c['ys'][:n]) if side == 'left' else (c['xs'][-n:], c['ys'][-n:])
    slope = float(np.polyfit(xx, yy, 1)[0]) if len(xx) >= 3 else 0.0
    index = 0 if side == 'left' else -1
    return [float(c['xs'][index]), float(c['ys'][index])], slope


def _detect(
    image: np.ndarray,
    spacing: float,
    check: Callable[[], None],
    sigma_yx=(3.0, 5.0),
    low_percentile=65.0,
    high_percentile=90.0,
    max_tilt_degrees=55.0,
    min_span_x=35,
    max_gap_px=20,
    max_edge_extension_px=8,
    support_percentile=55.0,
    min_support_fraction=0.5,
) -> dict[str, Any]:
    """Return observed/completed edge masks and an explicit completion log.

    ``observed`` keeps NMS+hysteresis edges with horizontal span >= min_span_x.
    ``completed`` adds ONLY short bridges or near-edge extensions supported by
    positive gradient measurements. ``added`` identifies every such extra pixel.
    Thresholds are exploratory image parameters, not validated physical cutoffs.
    """
    check()
    z = np.asarray(image, dtype=float)
    if z.ndim != 2 or not np.isfinite(z).all():
        raise ValueError('A finite, display-oriented two-dimensional image is required.')
    gy = ndi.gaussian_filter(z, sigma_yx, order=(1, 0))
    gx = ndi.gaussian_filter(z, sigma_yx, order=(0, 1))
    gm = np.hypot(gx, gy)
    yy, xx = np.indices(z.shape)
    ux, uy = gx / (gm + 1e-12), gy / (gm + 1e-12)
    forward = ndi.map_coordinates(gm, [yy + uy, xx + ux], order=1, mode='nearest')
    backward = ndi.map_coordinates(gm, [yy - uy, xx - ux], order=1, mode='nearest')
    nms = (gm >= forward) & (gm >= backward)
    nms[:3] = False
    nms[-3:] = False
    nms[:, :3] = False
    nms[:, -3:] = False
    direction = gy > np.cos(np.deg2rad(max_tilt_degrees)) * gm
    low, high = np.percentile(gm, [low_percentile, high_percentile])
    admissible = nms & direction & (gm > low)
    observed = ndi.binary_propagation(admissible & (gm > high), mask=admissible,
                                      structure=np.ones((3, 3), bool))
    observed = ndi.binary_closing(observed, structure=np.ones((3, 3), bool))
    observed = _long_components(observed, min_span_x, check)
    completed = observed.copy()
    support_level = float(np.percentile(gm, support_percentile))
    support = ndi.maximum_filter((direction & (gm > support_level)).astype(np.uint8), size=3) > 0
    events = []

    # Join non-overlapping components only across a short, locally supported gap.
    components = _components(observed, check)
    proposals = []
    for ca in components:
        check()
        a, slope_a = _endpoint(ca, 'right')
        for cb in components:
            b, slope_b = _endpoint(cb, 'left')
            dx, dy = b[0] - a[0], b[1] - a[1]
            distance = float(np.hypot(dx, dy))
            if (not (-.4 * spacing <= dx <= 3 * spacing) or not (0 < distance <= 3 * spacing)
                    or cb['xmin'] <= ca['xmin'] or cb['xmax'] <= ca['xmax']):
                continue
            if distance > max_gap_px:
                events.append(dict(kind='short_gap', start_xy=a, end_xy=b,
                    distance_px=distance, support_fraction=None, accepted=False,
                    reason='Gap exceeds conservative interpolation length.'))
                continue
            ys, xs = _line_samples(a, b, z.shape)
            # Short sharp kinks can be almost vertical. They were intentionally
            # excluded from the horizontal-edge detector, but can be joined if
            # the gradient is strong and normal to the proposed joining line.
            normal_response = np.abs(gx * (-dy / distance) + gy * (dx / distance))
            normal_support = ndi.maximum_filter(((gm > support_level) &
                (normal_response > 0.5 * gm)).astype(np.uint8), size=3) > 0
            fraction = float(np.mean(normal_support[ys, xs]))
            proposals.append((distance, ca, cb, a, b, fraction, ys, xs))
    used_right, used_left = set(), set()
    for _, ca, cb, a, b, fraction, ys, xs in sorted(proposals, key=lambda p: p[0]):
        accepted = (fraction >= min_support_fraction and ca['label'] not in used_right
                    and cb['label'] not in used_left)
        events.append(dict(kind='short_gap', start_xy=a, end_xy=b,
                           support_fraction=fraction, accepted=accepted,
                           reason='Gradient-supported short connector.' if accepted else
                           'Insufficient gradient support or endpoint already connected.'))
        if accepted:
            completed[ys, xs] = True
            used_right.add(ca['label'])
            used_left.add(cb['label'])

    # Extend only an already observed near-border endpoint, never a whole line.
    for c in _components(completed, check):
        for side in ['left', 'right']:
            a, slope = _endpoint(c, side)
            edge_x = 0 if side == 'left' else z.shape[1] - 1
            distance = abs(edge_x - a[0])
            if not (0 < distance <= max_edge_extension_px):
                continue
            b = [float(edge_x), float(a[1] + slope * (edge_x - a[0]))]
            if not 0 <= b[1] < z.shape[0]:
                continue
            ys, xs = _line_samples(a, b, z.shape)
            fraction = float(np.mean(support[ys, xs]))
            accepted = fraction >= min_support_fraction
            events.append(dict(kind='near_edge', start_xy=a, end_xy=b,
                               support_fraction=fraction, accepted=accepted))
            if accepted:
                completed[ys, xs] = True

    added = completed & ~observed
    component_metadata = []
    open_endpoints = []
    for c in _components(completed, check):
        component_metadata.append({k: v for k, v in c.items() if k not in {'xs', 'ys'}} |
                                  dict(y_median=float(np.median(c['ys'])),
                                       near_top=bool(np.median(c['ys']) < 20)))
        if 20 <= np.median(c['ys']) <= z.shape[0] - 20:
            for side in ['left', 'right']:
                endpoint, _ = _endpoint(c, side)
                if max_edge_extension_px < endpoint[0] < z.shape[1] - 1 - max_edge_extension_px:
                    open_endpoints.append(dict(component=c['label'], side=side, xy=endpoint))
    parameters = dict(sigma_yx=list(sigma_yx), low_percentile=low_percentile,
                      high_percentile=high_percentile, max_tilt_degrees=max_tilt_degrees,
                      min_span_x=min_span_x, max_gap_px=max_gap_px,
                      max_edge_extension_px=max_edge_extension_px,
                      support_percentile=support_percentile, min_support_fraction=min_support_fraction)
    metadata = dict(parameters=parameters, intensity_gradient_thresholds=dict(low=float(low),
                    high=float(high), completion_support=support_level),
                    observed_pixels=int(observed.sum()), completed_pixels=int(completed.sum()),
                    added_pixels=int(added.sum()), components=component_metadata, completions=events,
                    open_endpoints=open_endpoints,
                    possible_undersegmentation=bool(open_endpoints),
                    interpretation='Image-supported contrast/step candidates; physical terraces unverified.',
                    assumptions='Near-horizontal boundaries brighten downwards; no temporal smoothing or tracking.')
    return dict(observed=observed, completed=completed, added=added,
                gradient_strength=(gm / (np.std(z) + 1e-12)).astype(np.float32), metadata=metadata)


def image_barriers(image: np.ndarray, spacing: float, check: Callable[[], None], *,
                   settings: BarrierSettings = BarrierSettings()):
    result = _detect(image, spacing, check, sigma_yx=(.25 * spacing, 5 / 12 * spacing),
                     low_percentile=settings.low_percentile, high_percentile=settings.high_percentile,
                     max_tilt_degrees=settings.maximum_tilt_degrees,
                     min_span_x=max(3, round(settings.minimum_span_factor * spacing)),
                     max_gap_px=settings.maximum_gap_factor * spacing,
                     max_edge_extension_px=2 / 3 * spacing)
    dilation = max(1, round(settings.dilation_factor * spacing)) if settings.dilation_factor else 0
    mask = ndi.binary_dilation(result["completed"], iterations=dilation) if dilation else result['completed'].copy()
    metadata = dict(result["metadata"], dilated_pixels=int(mask.sum()),
                    dilation_pixels=dilation, requested_settings=settings.parameters())
    return mask, metadata
