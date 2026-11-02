"""Modeless editor: draft settings never alter the displayed completed result."""

from PyQt6.QtCore import QSignalBlocker
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout, QWidget,
)

from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.ui.session_controller import SessionController
from stmdomains.ui.catalogue_style import catalogue_description
from stmdomains.ui.domain_fields import DomainSettingsFields


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
        self.form_widget = DomainSettingsFields()
        self.minimum = self.form_widget.minimum
        self.link_distance = self.form_widget.link_distance
        self.geometry_mode = self.form_widget.geometry_mode
        self.edge_threshold = self.form_widget.edge_threshold
        self.region_diameter = self.form_widget.region_diameter
        self.mask_radius = self.form_widget.mask_radius
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
        self.form_widget.changed.connect(self._validate)
        controller.frame_changed.connect(lambda _: self.refresh())
        controller.busy_changed.connect(lambda busy, text: self.refresh())
        self._load(DomainSettings())
        self.refresh()

    def _settings(self) -> DomainSettings:
        return self.form_widget.settings()

    def _load(self, settings: DomainSettings) -> None:
        self.form_widget.load(settings)

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
