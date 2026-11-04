import pytest
from PyQt6.QtCore import QPointF
from stmdomains.core.geometry import MoleculeGeometry, RowAxis, PixelCalibration
from stmdomains.ui.geometry_overlay import row_segments


def test_raw_aligned_translation_and_anisotropic_direction(qapp):
    record = MoleculeGeometry('a', (50, 60), 'rows_1d', axes=(RowAxis(45, 135, 10, .9),), radius=30)
    calibration = PixelCalibration(.5, 2., 'nm')
    raw = row_segments(record, calibration, (0, 0))[0]
    aligned = row_segments(record, calibration, (17.25, 9.5))[0]
    assert raw.center() == QPointF(50, 60)
    assert aligned.center() == QPointF(67.25, 69.5)
    assert raw.dy()/raw.dx() == pytest.approx(-.25)
    assert aligned.dx() == pytest.approx(raw.dx())
    assert aligned.dy() == pytest.approx(raw.dy())
    assert row_segments(MoleculeGeometry('b', (50,60), 'unresolved'), calibration, (0,0)) == []
