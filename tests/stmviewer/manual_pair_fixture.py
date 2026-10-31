"""Interactive fractional-start fixture, never an accuracy test of an estimator.

Run from the repository root with PYTHONPATH=. in the netcat environment.
The synthetic backend deliberately returns (2.4, -1.25) for cpu.mpp pair 1→2.
"""

from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np
from numpy.typing import NDArray
from PyQt6.QtCore import QSignalBlocker
from PyQt6.QtWidgets import QApplication, QComboBox, QLabel, QScrollArea, QVBoxLayout, QWidget

from nanotrack.core import RegistrationFrameResult
from stmviewer.series import open_frame_series
from stmviewer.ui.pair_dialog import PairComparisonDialog


@dataclass(frozen=True)
class FractionalFixtureConfig:
    fixture: str = 'SYNTHETIC fractional start; not an estimated displacement'
    shift_xy: tuple[float, float] = (2.4, -1.25)


class FractionalFixtureBackend:
    config = FractionalFixtureConfig()

    def estimate(self, reference_frame: NDArray[np.float64], moving_frame: NDArray[np.float64],
                 *, moving_frame_index: int) -> RegistrationFrameResult:
        return RegistrationFrameResult(moving_frame_index, self.config.shift_xy,
                                       'fractional_fixture', status='manual_review')


def create_fixture(parent: QWidget) -> PairComparisonDialog:
    source = Path(__file__).resolve().parent / 'fixtures' / 'registration' / 'cpu.mpp'
    frames = open_frame_series([source])[:2]
    dialog = PairComparisonDialog(frames, 1, parent, backend=FractionalFixtureBackend())
    dialog.setWindowTitle('REG-01a — wzorzec ułamkowego startu (wynik syntetyczny)')
    method = dialog.findChild(QComboBox, 'pairMethod')
    assert method is not None
    with QSignalBlocker(method):
        method.clear()
        method.addItem('Wzorzec: XY = (2.4, -1.25)', 'phase_correlation')
    scroll = dialog.findChild(QScrollArea)
    assert scroll is not None
    panel = scroll.widget()
    assert panel is not None
    layout = panel.layout()
    assert isinstance(layout, QVBoxLayout)
    note = QLabel('WZORZEC TESTOWY: „Oblicz parę” zawsze zwraca (2.4, −1.25) px. '
                  'To zadany wynik do sprawdzenia korekty, nie pomiar ani wynik Phase.', dialog)
    note.setWordWrap(True)
    layout.insertWidget(0, note)
    return dialog


def main() -> None:
    app = QApplication(sys.argv)
    parent = QWidget()
    dialog = create_fixture(parent)
    dialog.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
