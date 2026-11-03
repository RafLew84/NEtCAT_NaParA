"""Explicit order recalibration for the displayed frame and frozen catalogue."""

from PyQt6.QtCore import QSignalBlocker
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from stmdomains.analysis.order_settings import OrderSettings
from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.ui.catalogue_style import catalogue_description
from stmdomains.ui.session_controller import SessionController


def order_settings_description(settings: OrderSettings) -> str:
    return (f"kwantyl {settings.order_quantile:g}; minimum {settings.order_minimum_local_count} "
            f"/ efektywne {settings.order_minimum_effective_count:g}; "
            f"promień {settings.order_radius_factor:g} × d, sigma {settings.order_sigma_factor:.6g} × d")


class OrderSettingsDialog(QDialog):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._result: FrameAnalysis | None = None
        self._loaded = OrderSettings()
        self.setWindowTitle("Test porządku lokalnego")
        self.setModal(False)
        self.resize(620, 590)
        layout = QVBoxLayout(self)
        self.context = QLabel()
        layout.addWidget(self.context)
        note = QLabel("Przelicz bieżącą klatkę przy zachowanych klasach, ich akceptacji i parametrach domen.\n"
                      "d = odstęp molekuł wyznaczony z tej klatki. Promień i sigma są mnożnikami d.\n"
                      "Kwantyl kontroli nie jest pewnością poprawności domeny. Metoda dopuszcza rzędy: "
                      "jeden kierunek periodyczności nie potwierdza sieci 2D.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.fields = QWidget()
        form = QFormLayout(self.fields)
        self.quantile = self._spin(.5, .999, 3, .005)
        self.minimum_local = QSpinBox()
        self.minimum_local.setRange(3, 200)
        self.minimum_effective = self._spin(2., 200., 2, 1.)
        self.radius = self._spin(.5, 6., 3, .1)
        self.sigma = self._spin(.25, 4., 6, .1)
        self.quantile.setToolTip("Wyższy kwantyl zwykle zaostrza test. Kontrole są generowane ponownie dla wybranej konfiguracji.")
        self.minimum_local.setToolTip("Liczba centrów w promieniu, łącznie z ocenianą molekułą.")
        self.minimum_effective.setToolTip("Efektywna liczba punktów po ważeniu odległością: (suma wag)² / suma kwadratów wag.")
        self.sigma.setToolTip("Szerokość wag Gaussa. Wartość bazowa to dokładnie 4/3 odstępu; pole pokazuje zaokrąglenie.")
        for label, field in (("Kwantyl kontroli", self.quantile), ("Minimum punktów lokalnych", self.minimum_local),
                             ("Minimum punktów efektywnych", self.minimum_effective),
                             ("Promień otoczenia [× d]", self.radius), ("Sigma otoczenia [× d]", self.sigma)):
            form.addRow(label, field)
        layout.addWidget(self.fields)
        self.validation = QLabel()
        self.validation.setWordWrap(True)
        self.validation.setMinimumHeight(self.validation.fontMetrics().height() * 2)
        layout.addWidget(self.validation)
        actions = QHBoxLayout()
        self.baseline = QPushButton("Przywróć bazowe")
        self.baseline.clicked.connect(lambda: self._load(OrderSettings()))
        self.calculate = QPushButton("Kalibruj i przelicz klatkę")
        self.calculate.clicked.connect(lambda: controller.recalculate_order(self._settings()))
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
        self.displayed.setMinimumHeight(self.displayed.fontMetrics().height() * 7)
        layout.addWidget(self.displayed)
        self.progress = QLabel("Gotowe")
        self.progress.setWordWrap(True)
        self.progress.setFixedHeight(self.progress.fontMetrics().height() * 2)
        layout.addWidget(self.progress)
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
        for field in (self.quantile, self.minimum_local, self.minimum_effective, self.radius, self.sigma):
            field.valueChanged.connect(self._validate)
        controller.frame_changed.connect(lambda _: self.refresh())
        controller.busy_changed.connect(self._busy)
        self._load(OrderSettings())
        self.refresh()

    @staticmethod
    def _spin(lower: float, upper: float, decimals: int, step: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(lower, upper)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        return spin

    def _settings(self) -> OrderSettings:
        # Preserve exact loaded values (notably 4/3) when only their display is rounded.
        values = {}
        for key, spin in self._pairs():
            loaded = getattr(self._loaded, key)
            decimals = spin.decimals() if isinstance(spin, QDoubleSpinBox) else 0
            values[key] = loaded if spin.value() == round(loaded, decimals) else spin.value()
        return OrderSettings(**values)

    def _pairs(self) -> tuple:
        return (("order_quantile", self.quantile), ("order_minimum_local_count", self.minimum_local),
                ("order_minimum_effective_count", self.minimum_effective),
                ("order_radius_factor", self.radius), ("order_sigma_factor", self.sigma))

    def _load(self, settings: OrderSettings) -> None:
        self._loaded = settings
        for key, spin in self._pairs():
            with QSignalBlocker(spin):
                spin.setValue(getattr(settings, key))
        self._validate()

    def _validate(self) -> None:
        self.calculate.setEnabled(self.controller.can_tune_order)
        result = self.controller.result
        if result is None or result.status != "complete" or result.catalogue is None:
            text = "Najpierw oblicz klasy i domeny tej klatki w aplikacji."
        elif self._settings() != OrderSettings.from_parameters(result.parameters):
            text = "Ustawienia nieprzeliczone. Przycisk wykona nową ocenę i kalibrację; obraz pozostaje bez zmian."
        else:
            text = "Ustawienia zgodne z wyświetlanym wynikiem. Ponowne odkrycie klas użyje tej oceny porządku."
        self.validation.setText(text)

    def _busy(self, busy: bool, text: str) -> None:
        self.progress.setText(text)
        self.refresh()

    def refresh(self) -> None:
        controller, result = self.controller, self.controller.result
        if result is not self._result:
            self._result = result
            self._load(OrderSettings.from_parameters(result.parameters) if result else OrderSettings())
        self.context.setText(f"Klatka {controller.current_index + 1} · test porządku" if controller.series else "Brak serii")
        self.fields.setEnabled(controller.can_tune_order)
        self.baseline.setEnabled(controller.can_tune_order)
        self.cancel.setEnabled(controller.is_busy)
        self.comparison.setEnabled(controller.can_analyze and controller.previous_result is not None)
        with QSignalBlocker(self.comparison):
            self.comparison.setCurrentIndex(self.comparison.findData(controller.result_version))
        text = "Brak wyniku do porównania."
        if result is not None and result.status == "complete":
            name = "Poprzedni" if controller.result_version == "previous" else "Nowy"
            calibration = result.metadata["order_calibration"]
            scale = result.metadata["order_evaluation"]
            text = (f"{name}: porządek {result.metadata['order_supported_count']}/{result.active_count}; "
                    f"w domenach {result.assigned_count}/{result.active_count}.\n"
                    + order_settings_description(OrderSettings.from_parameters(result.parameters)) + "\n"
                    f"d = {scale['spacing_px']:.3f} px; promień {scale['radius_px']:.3f} px, sigma {scale['sigma_px']:.3f} px.\n"
                    f"Kontrole losowe i z wykluczeniem · ziarno {calibration['seed']} · kalibracja {calibration['identifier'][:8]}.\n"
                    + catalogue_description(result.catalogue))
        elif result is not None:
            text = result.message
        self.displayed.setText(text)
        self._validate()
