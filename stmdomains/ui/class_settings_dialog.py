"""Explicit K/scope discovery and comparison in a small modeless menu window."""

from PyQt6.QtCore import QSignalBlocker
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from stmdomains.analysis.class_settings import ClassFitSettings
from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.ui.catalogue_style import catalogue_description
from stmdomains.ui.session_controller import SessionController


class ClassSettingsDialog(QDialog):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Klasy i zakres odkrywania")
        self.resize(520, 460)
        self.setModal(False)
        self._identity: tuple[str, int] | None = None
        self._latest: FrameAnalysis | None = None
        self._loading = False
        layout = QVBoxLayout(self)
        self.context = QLabel()
        layout.addWidget(self.context)
        note = QLabel("K to liczba klas otoczeń molekuł. Jedna klasa może tworzyć wiele domen.\n"
                      "Zakres określa dane do dopasowania klas. Wynik domen powstanie tylko dla bieżącej klatki.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.form_widget = QWidget()
        form = QFormLayout(self.form_widget)
        form.setContentsMargins(0, 6, 0, 6)
        self.k = QSpinBox()
        self.k.setRange(1, 8)
        self.k.setValue(5)
        self.scope = QComboBox()
        self.scope.addItem("Bieżąca klatka", "current_frame")
        self.scope.addItem("Wybrany zakres", "selected_range")
        self.scope.addItem("Cała seria", "whole_series")
        self.start, self.end = QSpinBox(), QSpinBox()
        for label, field in (("Liczba klas K", self.k), ("Dane do odkrywania klas", self.scope),
                             ("Pierwsza klatka", self.start), ("Ostatnia klatka", self.end)):
            form.addRow(label, field)
        layout.addWidget(self.form_widget)
        self.validation = QLabel()
        self.validation.setWordWrap(True)
        self.validation.setFixedHeight(self.validation.fontMetrics().height() * 3)
        layout.addWidget(self.validation)
        self.calculate = QPushButton("Dopasuj klasy i analizuj klatkę")
        self.calculate.clicked.connect(self._calculate)
        layout.addWidget(self.calculate)
        comparison = QFormLayout()
        self.comparison = QComboBox()
        self.comparison.addItem("Nowy wynik", "new")
        self.comparison.addItem("Poprzedni wynik", "previous")
        comparison.addRow("Pokaż wynik i wybierz jego katalog", self.comparison)
        self.comparison.currentIndexChanged.connect(lambda: controller.select_result(self.comparison.currentData()))
        layout.addLayout(comparison)
        self.displayed = QLabel()
        self.displayed.setWordWrap(True)
        self.displayed.setMinimumHeight(self.displayed.fontMetrics().height() * 4)
        layout.addWidget(self.displayed)
        self.progress = QLabel("Gotowe")
        self.progress.setWordWrap(True)
        self.progress.setFixedHeight(self.progress.fontMetrics().height() * 3)
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
        for button in (self.calculate, self.cancel, close):
            button.setAutoDefault(False)
        for spin in (self.k, self.start, self.end):
            spin.valueChanged.connect(self._validate)
        self.scope.currentIndexChanged.connect(self._validate)
        controller.frame_changed.connect(lambda _: self.refresh())
        controller.busy_changed.connect(self._busy)
        self.refresh()

    def _settings(self) -> ClassFitSettings:
        if self.scope.currentData() != "selected_range":
            return ClassFitSettings(self.k.value(), self.scope.currentData())
        return ClassFitSettings(self.k.value(), self.scope.currentData(),
                                self.start.value() - 1, self.end.value() - 1)

    def _validate(self) -> None:
        if self._loading:
            return
        ranged = self.scope.currentData() == "selected_range"
        self.start.setEnabled(ranged)
        self.end.setEnabled(ranged)
        try:
            series = self.controller.series
            if series is None:
                raise ValueError("Najpierw otwórz zapis z obrazami i oznaczeniami.")
            # Disabled endpoints cannot invalidate current-frame/whole-series modes.
            settings = self._settings()
            settings.indices(self.controller.current_index, series.frame_count)
        except ValueError as error:
            self.validation.setText(str(error))
            self.calculate.setEnabled(False)
            return
        self.calculate.setEnabled(self.controller.can_analyze)
        self.validation.setText("Edycja pól nie zmienia obrazu. Przycisk dopasuje nowy katalog.\n"
                                "Klasa 1 z różnych katalogów nie musi oznaczać tego samego.")

    def _calculate(self) -> None:
        try:
            settings = self._settings()
        except ValueError:
            self._validate()
            return
        self.controller.fit_current_classes(settings)

    def _busy(self, busy: bool, text: str) -> None:
        self.progress.setText(text)
        self.refresh()

    def refresh(self) -> None:
        controller, series = self.controller, self.controller.series
        identity = (series.identity, controller.current_index) if series else None
        latest = controller.latest_result
        if identity != self._identity or latest is not self._latest:
            self._identity, self._latest = identity, latest
            catalogue = controller.result.catalogue if controller.result is not None else controller.active_catalogue
            self._loading = True
            count = series.frame_count if series else 1
            for field in (self.start, self.end):
                field.setRange(1, count)
            self.k.setValue(catalogue.k if catalogue else 5)
            if catalogue is not None and catalogue.scope != "current_frame":
                self.scope.setCurrentIndex(self.scope.findData(catalogue.scope))
                self.start.setValue(catalogue.frame_indices[0] + 1)
                self.end.setValue(catalogue.frame_indices[-1] + 1)
            else:
                self.scope.setCurrentIndex(0)
                self.start.setValue(controller.current_index + 1)
                self.end.setValue(controller.current_index + 1)
            self._loading = False
        self.context.setText(f"Wynik dla klatki {controller.current_index + 1}" if series else "Brak serii")
        self.form_widget.setEnabled(controller.can_analyze)
        self.cancel.setEnabled(controller.is_busy)
        self.comparison.setEnabled(controller.can_analyze and controller.previous_result is not None)
        with QSignalBlocker(self.comparison):
            self.comparison.setCurrentIndex(self.comparison.findData(controller.result_version))
        result = controller.result
        displayed = catalogue_description(result.catalogue) if result else "Nieprzeliczone"
        prefix = "Wynik wcześniejszego katalogu" if controller.catalogue_status == "earlier" else "Wyświetlany wynik"
        self.displayed.setText(f"{prefix}: {displayed}\n"
                               f"Wybrany katalog: {catalogue_description(controller.active_catalogue)}")
        if controller.active_catalogue is not None:
            catalogue = controller.active_catalogue
            records = catalogue.provenance["frames"]
            used = sum(record["used_samples"] > 0 for record in records)
            self.displayed.setText(self.displayed.text() +
                                   f"\nDopasowanie: {catalogue.state['fit_count']} otoczeń; klatki z próbkami {used}/{len(records)}.")
        self._validate()
