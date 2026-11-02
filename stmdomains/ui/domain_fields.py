"""The same editable domain parameters in single-frame and series workflows."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QFormLayout, QSpinBox, QWidget

from stmdomains.analysis.domain_settings import DomainSettings


class DomainSettingsFields(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._loading = False
        form = QFormLayout(self)
        form.setContentsMargins(0, 6, 0, 6)
        self.minimum = QSpinBox()
        self.minimum.setRange(1, 3000)
        self.minimum.setToolTip("Minimum molekuł zarówno w grafie, jak i w każdej spójnej części maski.")
        self.link_distance = self._number(.05, 10., .05, " × odstęp")
        self.link_distance.setToolTip("Maksymalna odległość między łączonymi molekułami; odstęp jest wyznaczany z danych.")
        self.geometry_mode = QComboBox()
        self.geometry_mode.addItem("Zgodność otoczeń w całej domenie", "hellinger_region")
        self.geometry_mode.addItem("Bez kontroli zgodności otoczeń", "off")
        self.geometry_mode.setToolTip("Wyłączenie pomija oba progi podobieństwa. Klasy, test porządku i bariery nadal obowiązują.")
        self.edge_threshold = self._number(0., 1., .01)
        self.edge_threshold.setToolTip("Maksymalna różnica opisów otoczenia sąsiednich molekuł (odległość Hellingera).")
        self.region_diameter = self._number(0., 1., .05)
        self.region_diameter.setToolTip("Maksymalna różnica opisów dowolnej pary molekuł w domenie; to nie średnica w pikselach.")
        self.mask_radius = self._number(.05, 10., .05, " × odstęp")
        self.mask_radius.setToolTip("Maksymalny zasięg obszaru przypisanego do najbliższej molekuły.")
        for label, widget in (("Minimum molekuł", self.minimum), ("Odległość łączenia", self.link_distance),
                              ("Kontrola geometrii", self.geometry_mode), ("Próg krawędzi", self.edge_threshold),
                              ("Średnica regionu (opis otoczenia)", self.region_diameter), ("Zasięg maski", self.mask_radius)):
            form.addRow(label, widget)
        for spin in (self.minimum, self.link_distance, self.edge_threshold, self.region_diameter, self.mask_radius):
            spin.valueChanged.connect(self._changed)
        self.geometry_mode.currentIndexChanged.connect(self._changed)
        self.load(DomainSettings())

    @staticmethod
    def _number(low: float, high: float, step: float, suffix: str = "") -> QDoubleSpinBox:
        field = QDoubleSpinBox()
        field.setRange(low, high)
        field.setDecimals(2)
        field.setSingleStep(step)
        field.setSuffix(suffix)
        return field

    def _changed(self) -> None:
        geometry = self.geometry_mode.currentData() != "off"
        self.edge_threshold.setEnabled(geometry)
        self.region_diameter.setEnabled(geometry)
        if not self._loading:
            self.changed.emit()

    def settings(self) -> DomainSettings:
        return DomainSettings(self.minimum.value(), self.link_distance.value(), self.geometry_mode.currentData(),
                              self.edge_threshold.value(), self.region_diameter.value(), self.mask_radius.value())

    def load(self, settings: DomainSettings) -> None:
        self._loading = True
        self.minimum.setValue(settings.minimum_domain_size)
        self.link_distance.setValue(settings.edge_distance_factor)
        self.geometry_mode.setCurrentIndex(self.geometry_mode.findData(settings.geometry_mode))
        self.edge_threshold.setValue(settings.edge_max_hellinger)
        self.region_diameter.setValue(settings.region_max_hellinger_diameter)
        self.mask_radius.setValue(settings.raster_radius_factor)
        self._loading = False
        self._changed()
