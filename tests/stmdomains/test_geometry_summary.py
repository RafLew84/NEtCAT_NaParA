from stmdomains.analysis.geometry_summary import summarize_axes
from stmdomains.core.geometry import MoleculeGeometry, RowAxis


def record(name, angle):
    return MoleculeGeometry(name, (0., 0.), 'rows_1d', axes=(RowAxis(angle, (angle+90)%180, 10., .9),))


def test_axial_summary_wraps_at_180_and_counts_missing_members():
    summary = summarize_axes([record('a', 179), record('b', 1), MoleculeGeometry('c', (0, 0), 'unresolved')])
    assert summary['valid_count'] == 2 and summary['total_count'] == 3
    axis = summary['axes'][0]
    assert min(axis['angle_deg'], 180-axis['angle_deg']) < .01
    assert .9 < axis['dispersion_deg'] < 1.1
    assert axis['count'] == 2


def test_conflicting_directions_are_not_a_confident_average():
    summary = summarize_axes([record('a', 0), record('b', 90)])
    assert summary['axes'][0]['angle_deg'] is None
