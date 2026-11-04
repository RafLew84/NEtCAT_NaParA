"""Panel A: a geometric draft with units and the shared spatial constraints."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFormLayout, QLabel, QSpinBox, QVBoxLayout, QWidget

from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.geometry_domain_settings import GeometryDomainSettings
from stmdomains.ui.domain_fields import DomainSettingsFields


class GeometryDomainFields(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        note = QLabel('Domeny na bieżącej klatce z pomiarów geometrii. Bez zadanej liczby klas i domen.\n'
                      'Wymagane dwa stabilne kierunki; typ struktury pozostaje nieznany.')
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        number = DomainSettingsFields._number
        self.angle = number(.1, 45., 1., '°')
        self.spacing = number(.1, 100., 1., '%')
        self.quality = number(.75, 1., .01)
        self.support = QSpinBox()
        self.support.setRange(10, 3000)
        self.minimum = QSpinBox()
        self.minimum.setRange(1, 3000)
        self.distance = number(.05, 10., .05, ' × odstęp NN')
        self.radius = number(.05, 10., .05, ' × odstęp NN')
        self.angle.setToolTip('Maksymalna różnica dowolnej pary pomiarów w całej domenie. Osie modulo 180°; dopasowanie obu rodzin wraz z rozstawem.')
        self.spacing.setToolTip('100 × |a−b| / min(a,b), osobno dla obu dopasowanych kierunków w całym regionie.')
        self.quality.setToolTip('Minimum koherencji obu osi. Nie jest prawdopodobieństwem poprawności domeny.')
        self.support.setToolTip('Minimum punktów lokalnego pomiaru. Dodatkowo pomiar wymaga Neff ≥ 8 i stabilności. Nie jest to minimum wielkości domeny.')
        for title, widget in (('Tolerancja kąta całej domeny', self.angle), ('Tolerancja rozstawu', self.spacing),
                               ('Minimalna jakość pomiaru', self.quality), ('Minimum punktów lokalnie', self.support),
                               ('Minimum molekuł w domenie', self.minimum), ('Odległość łączenia', self.distance),
                               ('Zasięg maski', self.radius)):
            form.addRow(title, widget)
            widget.valueChanged.connect(self.changed)
        layout.addLayout(form)
        warning = QLabel('Granice przesunięcia fazowego nie są sprawdzane. Brak pomiaru nie dowodzi granicy.\n'
                         'Bariery obrazu: zakładka Zaawansowane. Odległości używają kalibracji X/Y, gdy jest dostępna.\n'
                         'Przełącznik nad obrazem zachowuje ostatni wynik każdej metody w sesji.')
        warning.setWordWrap(True)
        layout.addWidget(warning)
        layout.addStretch(1)
        self.load(GeometryDomainSettings(), DomainSettings())

    def settings(self) -> GeometryDomainSettings:
        return GeometryDomainSettings(self.angle.value(), self.spacing.value(), self.quality.value(), self.support.value())

    def constraints(self) -> DomainSettings:
        return DomainSettings(minimum_domain_size=self.minimum.value(), edge_distance_factor=self.distance.value(),
                              raster_radius_factor=self.radius.value())

    def load(self, settings: GeometryDomainSettings, constraints: DomainSettings) -> None:
        self.angle.setValue(settings.angle_degrees)
        self.spacing.setValue(settings.spacing_percent)
        self.quality.setValue(settings.minimum_coherence)
        self.support.setValue(settings.minimum_local_count)
        self.minimum.setValue(constraints.minimum_domain_size)
        self.distance.setValue(constraints.edge_distance_factor)
        self.radius.setValue(constraints.raster_radius_factor)
