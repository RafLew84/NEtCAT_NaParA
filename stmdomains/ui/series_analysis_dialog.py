"""Choose both scopes and domain settings, then browse per-frame batch outcomes."""

from PyQt6.QtCore import QSignalBlocker, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.series_analysis import validate_shared_catalogue
from stmdomains.analysis.series_settings import SeriesAnalysisPlan
from stmdomains.ui.catalogue_style import catalogue_description
from stmdomains.ui.domain_fields import DomainSettingsFields
from stmdomains.ui.order_settings_dialog import order_settings_description
from stmdomains.ui.session_controller import SessionController

STATUS_TEXT = {"pending": "Oczekuje", "analysing": "Obliczanie", "not_run": "Niewykonana",
               "complete": "Gotowe", "no_annotations": "Brak oznaczeń",
               "insufficient_data": "Za mało danych", "error": "Błąd"}


class SeriesAnalysisDialog(QDialog):
    def __init__(self, controller: SessionController, parent: QWidget) -> None:
        super().__init__(parent)
        self.controller = controller
        self._series_id: str | None = None
        self._loading = False
        self._rows: tuple[int, ...] = ()
        self._shown_statuses: dict = {}
        self.setWindowTitle("Analiza serii — klasy i domeny")
        self.resize(660, 680)
        self.setModal(False)
        layout = QVBoxLayout(self)
        note = QLabel("Oblicz domeny na wszystkich wybranych klatkach.\n"
                      "Jeden katalog klas i te same parametry domen dla całego przebiegu.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.tabs = QTabWidget()
        scope_page = QWidget()
        form = QFormLayout(scope_page)
        self.scope = QComboBox()
        self.scope.addItem("Wybrany zakres", False)
        self.scope.addItem("Cała seria", True)
        self.start, self.end = QSpinBox(), QSpinBox()
        self.k = QSpinBox()
        self.k.setRange(1, 8)
        self.fit_source = QComboBox()
        for text, value in (("Ten sam zakres co analiza", "same_range"),
                            ("Inny wybrany zakres", "selected_range"), ("Cała seria", "whole_series"),
                            ("Użyj wybranego wspólnego katalogu", "existing")):
            self.fit_source.addItem(text, value)
        self.fit_start, self.fit_end = QSpinBox(), QSpinBox()
        for label, widget in (("Klatki do analizy", self.scope), ("Pierwsza klatka", self.start),
                              ("Ostatnia klatka", self.end), ("Dane do odkrywania klas", self.fit_source),
                              ("Początek dopasowania", self.fit_start), ("Koniec dopasowania", self.fit_end),
                              ("Liczba klas K", self.k)):
            form.addRow(label, widget)
        self.catalogue_label = QLabel()
        self.catalogue_label.setWordWrap(True)
        form.addRow(self.catalogue_label)
        self.tabs.addTab(scope_page, "Zakres i klasy")
        domains_page = QWidget()
        domains_layout = QVBoxLayout(domains_page)
        self.domain_fields = DomainSettingsFields()
        domains_layout.addWidget(self.domain_fields)
        domain_actions = QHBoxLayout()
        self.copy_domains = QPushButton("Z wyświetlanego wyniku")
        self.copy_domains.clicked.connect(self._copy_domains)
        baseline = QPushButton("Przywróć bazowe")
        baseline.clicked.connect(lambda: self.domain_fields.load(DomainSettings()))
        domain_actions.addWidget(self.copy_domains)
        domain_actions.addWidget(baseline)
        domains_layout.addLayout(domain_actions)
        domains_layout.addStretch()
        self.tabs.addTab(domains_page, "Tworzenie domen")
        layout.addWidget(self.tabs)
        self.order_summary = QLabel()
        self.order_summary.setWordWrap(True)
        self.order_summary.setMinimumHeight(self.order_summary.fontMetrics().height() * 3)
        layout.addWidget(self.order_summary)
        self.validation = QLabel()
        self.validation.setWordWrap(True)
        self.validation.setFixedHeight(self.validation.fontMetrics().height() * 3)
        layout.addWidget(self.validation)
        self.calculate = QPushButton("Analizuj wybrane klatki")
        self.calculate.clicked.connect(self._calculate)
        layout.addWidget(self.calculate)
        self.progress = QLabel("Gotowe")
        self.progress.setWordWrap(True)
        self.progress.setFixedHeight(self.progress.fontMetrics().height() * 3)
        layout.addWidget(self.progress)
        self.statuses = QTableWidget(0, 4)
        self.statuses.setHorizontalHeaderLabels(["Klatka", "Stan tego przebiegu", "Przypisano", "Domeny"])
        self.statuses.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.statuses.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.statuses.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.statuses.cellDoubleClicked.connect(self._show_row)
        self.statuses.setToolTip("Dwukrotnie kliknij wiersz, aby przejść do klatki. Szczegóły stanu są w podpowiedzi.")
        self.statuses.setMinimumHeight(120)
        layout.addWidget(self.statuses, 1)
        footer = QHBoxLayout()
        self.cancel = QPushButton("Anuluj analizę serii")
        self.cancel.clicked.connect(controller.cancel)
        close = QPushButton("Zamknij")
        close.clicked.connect(self.close)
        footer.addWidget(self.cancel)
        footer.addStretch()
        footer.addWidget(close)
        layout.addLayout(footer)
        for button in (self.calculate, self.cancel, close, self.copy_domains, baseline):
            button.setAutoDefault(False)
        for spin in (self.start, self.end, self.fit_start, self.fit_end, self.k):
            spin.valueChanged.connect(self._validate)
        self.scope.currentIndexChanged.connect(self._validate)
        self.fit_source.currentIndexChanged.connect(self._validate)
        self.domain_fields.changed.connect(self._validate)
        controller.series_analysis_changed.connect(self.refresh)
        controller.busy_changed.connect(lambda busy, text: self.refresh())
        controller.frame_changed.connect(lambda view: self.refresh())
        self.refresh()

    def _plan(self) -> SeriesAnalysisPlan:
        return SeriesAnalysisPlan(self.start.value() - 1, self.end.value() - 1, self.scope.currentData(),
                                  self.k.value(), self.fit_source.currentData(), self.fit_start.value() - 1,
                                  self.fit_end.value() - 1, self.domain_fields.settings(),
                                  self.controller.current_order_settings)

    def _copy_domains(self) -> None:
        result = self.controller.result
        if result is not None:
            self.domain_fields.load(DomainSettings.from_parameters(result.parameters))

    def _validate(self) -> None:
        if self._loading:
            return
        existing = self.fit_source.currentData() == "existing"
        active = self.controller.active_catalogue
        if existing and active is not None:
            with QSignalBlocker(self.k):
                self.k.setValue(active.k)
        self.k.setEnabled(not existing)
        self.start.setEnabled(not self.scope.currentData())
        self.end.setEnabled(not self.scope.currentData())
        for spin in (self.fit_start, self.fit_end):
            spin.setEnabled(self.fit_source.currentData() == "selected_range")
        series = self.controller.series
        fit_source = self.fit_source.currentData()
        endpoints = None
        if series is not None:
            if fit_source == "same_range":
                endpoints = ((1, series.frame_count) if self.scope.currentData()
                             else (self.start.value(), self.end.value()))
            elif fit_source == "whole_series":
                endpoints = (1, series.frame_count)
            elif existing and active is not None:
                endpoints = (active.frame_indices[0] + 1, active.frame_indices[-1] + 1)
        if endpoints is not None:
            for spin, value in zip((self.fit_start, self.fit_end), endpoints):
                with QSignalBlocker(spin):
                    spin.setValue(value)
        try:
            if series is None:
                raise ValueError("Najpierw otwórz serię.")
            plan = self._plan()
            count = len(plan.indices(series.frame_count))
            plan.fit_settings(series.frame_count)
            if existing:
                validate_shared_catalogue(active, series.identity, plan.k)
            self.validation.setText(f"Analiza {count} klatek · K{plan.k} · minimum {plan.domain_settings.minimum_domain_size} molekuł.\n"
                                    "Przycisk zastosuje ustawienia z obu zakładek. Numery domen są lokalne dla klatki.")
            self.calculate.setEnabled(self.controller.can_analyze)
        except ValueError as error:
            self.validation.setText(str(error))
            self.calculate.setEnabled(False)

    def _calculate(self) -> None:
        try:
            self.controller.start_series_analysis(self._plan())
        except ValueError:
            self._validate()

    def _show_row(self, row: int, column: int) -> None:
        if 0 <= row < len(self._rows):
            self.controller.show_frame(self._rows[row])

    def refresh(self) -> None:
        controller, series = self.controller, self.controller.series
        identity = series.identity if series else None
        if identity != self._series_id:
            self._series_id = identity
            self._loading = True
            for spin in (self.start, self.end, self.fit_start, self.fit_end):
                spin.setRange(1, series.frame_count if series else 1)
            self.start.setValue(series.active_frame_index + 1 if series else 1)
            self.end.setValue(series.frame_count if series else 1)
            self.fit_start.setValue(self.start.value())
            self.fit_end.setValue(self.end.value())
            self.scope.setCurrentIndex(0)
            self.fit_source.setCurrentIndex(0)
            self.k.setValue(5)
            self.domain_fields.load(DomainSettings())
            self._loading = False
        self.tabs.setEnabled(controller.can_analyze)
        self.copy_domains.setEnabled(controller.result is not None)
        self.cancel.setEnabled(controller.series_running)
        self.catalogue_label.setText("Wybrany katalog: " + catalogue_description(controller.active_catalogue))
        run = controller.series_run
        order = run.plan.order_settings if controller.series_running and run else controller.current_order_settings
        self.order_summary.setText("Test porządku dla całego przebiegu: " + order_settings_description(order)
                                   + ".\nŹródło przed startem: wyświetlany wynik, a przy jego braku ustawienia bazowe. "
                                   "Zmiana: Analiza → Test porządku…")
        indices = run.indices if run else ()
        if self._rows != indices:
            self._rows = indices
            self._shown_statuses.clear()
            self.statuses.setRowCount(len(indices))
        self.progress.setText(run.message if run else "Gotowe · nie uruchomiono analizy serii")
        if run is not None:
            changed = False
            for row, index in enumerate(indices):
                status = run.frames[index]
                if self._shown_statuses.get(index) is status:
                    continue
                self._shown_statuses[index] = status
                changed = True
                values = (str(index + 1), STATUS_TEXT[status.status],
                          f"{status.assigned}/{status.active}" if status.status == "complete" else "—",
                          str(status.domains) if status.status == "complete" else "—")
                for column, value in enumerate(values):
                    item = self.statuses.item(row, column)
                    if item is None:
                        item = QTableWidgetItem()
                        self.statuses.setItem(row, column, item)
                    if item.text() != value:
                        item.setText(value)
                    item.setToolTip(status.message)
            if changed:
                self.statuses.resizeColumnsToContents()
        self._validate()
