"""Descriptive axial summaries, never a domain type classifier."""

from collections.abc import Sequence
import numpy as np

from stmdomains.analysis.geometry_spectrum import axial_difference
from stmdomains.core.geometry import MoleculeGeometry


def summarize_axes(records: Sequence[MoleculeGeometry]) -> dict:
    valid = [record for record in records if record.axes]
    if not valid:
        return {'total_count': len(records), 'valid_count': 0, 'axes': []}
    reference = max(valid, key=lambda m: len(m.axes)).axes
    groups: list[list] = [[] for _ in reference]
    for record in valid:
        axes = record.axes
        if len(axes) == len(reference) == 2:
            direct = sum(axial_difference(a.row_angle_deg, b.row_angle_deg) for a, b in zip(axes, reference))
            reverse = sum(axial_difference(a.row_angle_deg, b.row_angle_deg) for a, b in zip(axes[::-1], reference))
            for group, axis in zip(groups, axes if direct <= reverse else axes[::-1]):
                group.append(axis)
        else:
            axis = axes[0]
            index = min(range(len(reference)), key=lambda i: axial_difference(axis.row_angle_deg, reference[i].row_angle_deg))
            groups[index].append(axis)
    summaries = []
    for group in groups:
        z = np.mean(np.exp(2j*np.deg2rad([axis.row_angle_deg for axis in group])))
        resultant = min(1., float(abs(z)))
        # R < .5 is an explicit descriptive ambiguity gate, not a confidence level.
        angle = float(np.rad2deg(np.angle(z))/2 % 180) if resultant >= .5 else None
        dispersion = float(np.rad2deg(np.sqrt(-2*np.log(resultant)))/2) if resultant > 1e-12 else None
        periods = [axis.period for axis in group]
        summaries.append({'angle_deg': angle, 'dispersion_deg': dispersion, 'resultant': resultant,
                          'count': len(group), 'period_median': float(np.median(periods)),
                          'period_min': min(periods), 'period_max': max(periods)})
    return {'total_count': len(records), 'valid_count': len(valid), 'axes': summaries}
