"""Modeless editor: draft settings never alter the displayed completed result."""

from PyQt6.QtCore import QSignalBlocker
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.ui.session_controller import SessionController
from stmdomains.ui.catalogue_style import catalogue_description


class DomainSettingsDialog(QDialog):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Tworzenie domen")
        self.setModal(False)
        self.resize(500, 440)
        self._identity: tuple[str, int] | None = None
        self._latest: FrameAnalysis | None = None
        self._loading = False
        layout = QVBoxLayout(self)
        self.context = QLabel()
        layout.addWidget(self.context)
        note = QLabel("Przeliczanie zachowuje klasy wyświetlanego wyniku.\n"
                      "Liczbę klas i zakres zmienisz w menu Analiza → Klasy i zakres…")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.form_widget = QWidget()
        form = QFormLayout(self.form_widget)
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
        for label, field in (("Minimum molekuł", self.minimum), ("Odległość łączenia", self.link_distance),
                             ("Kontrola geometrii", self.geometry_mode), ("Próg krawędzi", self.edge_threshold),
                             ("Średnica regionu (opis otoczenia)", self.region_diameter), ("Zasięg maski", self.mask_radius)):
            form.addRow(label, field)
        layout.addWidget(self.form_widget)
        self.validation = QLabel()
        self.validation.setWordWrap(True)
        self.validation.setMinimumHeight(self.validation.fontMetrics().height() * 3)
        layout.addWidget(self.validation)
        actions = QHBoxLayout()
        self.baseline = QPushButton("Przywróć bazowe")
        self.baseline.setToolTip("Wpisz wartości bazowe. Zastosuj je przyciskiem Przelicz domeny.")
        self.calculate = QPushButton("Przelicz domeny")
        self.baseline.clicked.connect(lambda: self._load(DomainSettings()))
        self.calculate.clicked.connect(self._calculate)
        actions.addWidget(self.baseline)
        actions.addWidget(self.calculate)
        layout.addLayout(actions)
        comparison = QFormLayout()
        self.comparison = QComboBox()
        self.comparison.addItem("Nowy wynik", "new")
        self.comparison.addItem("Poprzedni wynik", "previous")
        self.comparison.currentIndexChanged.connect(lambda: controller.select_result(self.comparison.currentData()))
        comparison.addRow("Pokaż na obrazie", self.comparison)
        layout.addLayout(comparison)
        self.displayed = QLabel()
        self.displayed.setWordWrap(True)
        self.displayed.setMinimumHeight(self.displayed.fontMetrics().height() * 4)
        layout.addWidget(self.displayed)
        footer = QHBoxLayout()
        self.cancel = QPushButton("Anuluj obliczenia")
        self.cancel.clicked.connect(controller.cancel)
        close = QPushButton("Zamknij")
        close.clicked.connect(self.close)
        footer.addWidget(self.cancel)
        footer.addStretch()
        footer.addWidget(close)
        layout.addLayout(footer)
        for button in (self.baseline, self.calculate, self.cancel, close):
            button.setAutoDefault(False)
        for spin in (self.minimum, self.link_distance, self.edge_threshold, self.region_diameter, self.mask_radius):
            spin.valueChanged.connect(self._validate)
        self.geometry_mode.currentIndexChanged.connect(self._validate)
        controller.frame_changed.connect(lambda _: self.refresh())
        controller.busy_changed.connect(lambda busy, text: self.refresh())
        self._load(DomainSettings())
        self.refresh()

    @staticmethod
    def _number(low: float, high: float, step: float, suffix: str = "") -> QDoubleSpinBox:
        field = QDoubleSpinBox()
        field.setRange(low, high)
        field.setDecimals(2)
        field.setSingleStep(step)
        field.setSuffix(suffix)
        return field

    def _settings(self) -> DomainSettings:
        return DomainSettings(self.minimum.value(), self.link_distance.value(), self.geometry_mode.currentData(),
                              self.edge_threshold.value(), self.region_diameter.value(), self.mask_radius.value())

    def _load(self, settings: DomainSettings) -> None:
        self._loading = True
        self.minimum.setValue(settings.minimum_domain_size)
        self.link_distance.setValue(settings.edge_distance_factor)
        self.geometry_mode.setCurrentIndex(self.geometry_mode.findData(settings.geometry_mode))
        self.edge_threshold.setValue(settings.edge_max_hellinger)
        self.region_diameter.setValue(settings.region_max_hellinger_diameter)
        self.mask_radius.setValue(settings.raster_radius_factor)
        self._loading = False
        self._validate()

    def _validate(self) -> None:
        if self._loading:
            return
        geometry = self.geometry_mode.currentData() != "off"
        self.edge_threshold.setEnabled(geometry)
        self.region_diameter.setEnabled(geometry)
        try:
            settings = self._settings()
        except ValueError as error:
            self.validation.setText(str(error))
            self.calculate.setEnabled(False)
            return
        self.calculate.setEnabled(self.controller.can_analyze)
        displayed = self.controller.result
        changed = displayed is None or settings != DomainSettings.from_parameters(displayed.parameters)
        self.validation.setText("Ustawienia nieprzeliczone. Kliknij „Przelicz domeny”, aby je zastosować."
                                if changed else "Ustawienia zgodne z wyświetlanym wynikiem. Edycja nie zmienia obrazu.")

    def _calculate(self) -> None:
        try:
            settings = self._settings()
        except ValueError:
            self._validate()
            return
        self.controller.recalculate_domains(settings)

    def refresh(self) -> None:
        controller = self.controller
        identity = (controller.series.identity, controller.current_index) if controller.series else None
        latest = controller.latest_result
        if identity != self._identity or latest is not self._latest:
            self._identity, self._latest = identity, latest
            self._load(DomainSettings.from_parameters(latest.parameters) if latest else DomainSettings())
        self.context.setText(f"Klatka {controller.current_index + 1} · ustawienia tworzenia domen"
                             if identity else "Najpierw otwórz zapis z obrazami i oznaczeniami.")
        self.form_widget.setEnabled(controller.can_analyze)
        self.baseline.setEnabled(controller.can_analyze)
        self.cancel.setEnabled(controller.is_busy)
        self.comparison.setEnabled(controller.can_analyze and controller.previous_result is not None)
        with QSignalBlocker(self.comparison):
            self.comparison.setCurrentIndex(self.comparison.findData(controller.result_version))
        result = controller.result
        if result is None:
            text = "Brak wyniku. Przeliczenie użyje wybranego katalogu wspólnego albo dopasuje klasy lokalnie."
        else:
            name = "Poprzedni" if controller.result_version == "previous" else "Nowy"
            settings = DomainSettings.from_parameters(result.parameters)
            text = (f"{name}: {result.domain_count} domen · przypisano {result.assigned_count} / {result.active_count}.\n"
                    f"Użyto: minimum {settings.minimum_domain_size}, łączenie {settings.edge_distance_factor:g}, "
                    f"maska {settings.raster_radius_factor:g} × odstęp.\n"
                    + (f"Próg {settings.edge_max_hellinger:g}, średnica {settings.region_max_hellinger_diameter:g}."
                       if settings.geometry_mode != "off" else "Kontrola zgodności otoczeń wyłączona.")
                    + "\n" + catalogue_description(result.catalogue))
            if result.status != "complete":
                text = result.message
        self.displayed.setText(text)
        self._validate()
