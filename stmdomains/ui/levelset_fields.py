"""An explicit current-frame draft for the experimental level-set solver."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFormLayout, QLabel, QSpinBox, QVBoxLayout, QWidget

from stmdomains.analysis.levelset_settings import LevelSetSettings
from stmdomains.ui.domain_fields import DomainSettingsFields

STOPPING_LABELS = {'single_region': 'jeden region modelu', 'stable_partition': 'stabilny podział',
                   'iteration_limit': 'osiągnięto limit', 'no_support': 'brak wsparcia'}


class LevelSetFields(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        note = QLabel('Level set z pomiarów sieci — bieżąca klatka.\n'
                      'Prototypy wynikają z tolerancji geometrii; nie są klasami fizycznymi.\n'
                      'Rozłączne obszary dostają osobne numery domen.')
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.regularization = DomainSettingsFields._number(0., 2., .05)
        self.regularization.setToolTip('Bezwymiarowa siła 0–2. 0 wyłącza krzywiznę. '
            'Czas wygładzania co 5 iteracji: 0,05 × siła, w jednostkach NN². '
            'Duża wartość może usunąć małe obszary.')
        self.iterations = QSpinBox()
        self.iterations.setRange(1, 500)
        self.iterations.setToolTip('Maksymalnie 1–500 kroków; stop wcześniej po stabilizacji podziału. '
            'Osiągnięcie limitu nie oznacza zbieżności.')
        form.addRow('Siła regularyzacji', self.regularization)
        form.addRow('Limit iteracji', self.iterations)
        layout.addLayout(form)
        warning = QLabel('Geometria: tolerancje inicjalizacji i skala różnic cech oraz warunki wsparcia.\n'
            'Zaawansowane: te same bariery obrazu co w Geometrii.\n'
            'Braki pomiarów i luki pozostają wyłączone. Granice przesunięcia fazowego nie są sprawdzane.\n'
            'Stabilny podział nie potwierdza poprawności domen. Wynik podaje rzeczywistą liczbę iteracji.')
        warning.setWordWrap(True)
        layout.addWidget(warning)
        layout.addStretch(1)
        self.regularization.valueChanged.connect(self.changed)
        self.iterations.valueChanged.connect(self.changed)
        self.load(LevelSetSettings())

    def settings(self) -> LevelSetSettings:
        return LevelSetSettings(self.regularization.value(), self.iterations.value())

    def load(self, settings: LevelSetSettings) -> None:
        self.regularization.setValue(settings.regularization)
        self.iterations.setValue(settings.iterations)
