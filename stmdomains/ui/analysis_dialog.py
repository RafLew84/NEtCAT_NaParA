"""One persistent parameter draft, one explicit run and independent result browsing."""

from PyQt6.QtCore import QSignalBlocker, Qt
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QTabWidget, QVBoxLayout, QWidget,
)

from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.order_settings import OrderSettings
from stmdomains.analysis.series_analysis import validate_plan_catalogue
from stmdomains.analysis.series_settings import SeriesAnalysisPlan
from stmdomains.ui.acceptance_fields import AcceptanceFields
from stmdomains.ui.analysis_scope_fields import AnalysisScopeFields, ClassFields
from stmdomains.ui.analysis_status import AnalysisStatuses
from stmdomains.ui.catalogue_style import catalogue_description
from stmdomains.ui.domain_fields import DomainSettingsFields
from stmdomains.ui.order_fields import OrderFields, order_settings_description
from stmdomains.ui.session_controller import SessionController


class AnalysisDialog(QDialog):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._series_id: str | None = None
        self._loading = False
        self._seen_catalogue: tuple[str, str] | None = None
        self.setWindowTitle("Analiza — klasy i domeny")
        self.setModal(False)
        self.resize(660, 650)
        layout = QVBoxLayout(self)
        self.context = QLabel()
        layout.addWidget(self.context)
        self.tabs = QTabWidget()
        self.scope_fields = AnalysisScopeFields()
        self.class_fields = ClassFields()
        self.acceptance_fields = AcceptanceFields()
        classes = QWidget()
        class_layout = QVBoxLayout(classes)
        class_layout.setContentsMargins(0, 0, 0, 0)
        class_layout.addWidget(self.class_fields)
        class_layout.addWidget(self.acceptance_fields)
        self.order_fields = OrderFields()
        self.domain_fields = DomainSettingsFields()
        for title, fields in (("Zakres", self.scope_fields), ("Klasy", classes),
                               ("Porządek", self.order_fields), ("Domeny", self.domain_fields)):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(fields)
            scroll.setMinimumHeight(150)
            self.tabs.addTab(scroll, title)
        layout.addWidget(self.tabs, 1)
        edits = QHBoxLayout()
        self.copy_result = QPushButton("Z wyświetlanego wyniku")
        self.copy_result.setToolTip("Skopiuj progi i wybierz katalog wyświetlanego wyniku. Zakres analizy pozostaje bez zmian.")
        self.copy_result.clicked.connect(self._copy_result)
        self.baseline = QPushButton("Przywróć bazowe parametry")
        self.baseline.setToolTip("Przywróć progi akceptacji, porządku i domen. Zakresy i wybór klas pozostają bez zmian.")
        self.baseline.clicked.connect(self._baseline)
        edits.addWidget(self.copy_result)
        edits.addWidget(self.baseline)
        layout.addLayout(edits)
        self.validation = self._label(2)
        layout.addWidget(self.validation)
        actions = QHBoxLayout()
        self.calculate = QPushButton("Analizuj")
        self.calculate.clicked.connect(self._calculate)
        self.cancel = QPushButton("Anuluj obliczenia")
        self.cancel.clicked.connect(controller.cancel)
        actions.addWidget(self.calculate, 1)
        actions.addWidget(self.cancel)
        layout.addLayout(actions)
        self.progress = self._label(2)
        layout.addWidget(self.progress)
        self.statuses = AnalysisStatuses()
        self.statuses.frame_requested.connect(controller.show_frame)
        layout.addWidget(self.statuses)
        comparison = QHBoxLayout()
        comparison.addWidget(QLabel("Pokaż na obrazie"))
        self.comparison = QComboBox()
        self.comparison.addItem("Nowy wynik", "new")
        self.comparison.addItem("Poprzedni wynik", "previous")
        self.comparison.currentIndexChanged.connect(lambda: controller.select_result(self.comparison.currentData()))
        comparison.addWidget(self.comparison, 1)
        close = QPushButton("Zamknij")
        close.clicked.connect(self.close)
        comparison.addWidget(close)
        layout.addLayout(comparison)
        self.displayed = self._label(3)
        layout.addWidget(self.displayed)
        for button in (self.copy_result, self.baseline, self.calculate, self.cancel, close):
            button.setAutoDefault(False)
        for fields in (self.scope_fields, self.class_fields, self.acceptance_fields,
                       self.order_fields, self.domain_fields):
            fields.changed.connect(self._validate)
        controller.frame_changed.connect(lambda _: self.refresh())
        controller.series_changed.connect(lambda _: self.refresh())
        controller.series_analysis_changed.connect(self.refresh)
        controller.busy_changed.connect(lambda busy, text: self.refresh())
        self.refresh()

    @staticmethod
    def _label(lines: int) -> QLabel:
        label = QLabel()
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setFixedHeight(label.fontMetrics().lineSpacing() * lines + 6)
        label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        return label

    def select_current_frame(self) -> None:
        """The image button changes only the target scope, keeping the parameter draft."""
        if not self.controller.series_running:
            self.scope_fields.scope.setCurrentIndex(0)
        self.refresh()

    def plan(self) -> SeriesAnalysisPlan:
        scope, classes = self.scope_fields, self.class_fields
        current = scope.scope.currentData() == "current_frame"
        return SeriesAnalysisPlan(
            start=self.controller.current_index if current else scope.start.value() - 1,
            end=scope.end.value() - 1, current_frame=current,
            whole_series=scope.scope.currentData() == "whole_series", k=classes.chosen_k,
            fit_source="existing" if classes.mode.currentData() == "existing" else classes.fit_source.currentData(),
            fit_start=classes.fit_start.value() - 1, fit_end=classes.fit_end.value() - 1,
            domain_settings=self.domain_fields.settings(), order_settings=self.order_fields.settings(),
            acceptance=self.acceptance_fields.settings(),
        )

    def _baseline(self) -> None:
        self._loading = True
        self.domain_fields.load(DomainSettings())
        self.acceptance_fields.load(ClassAcceptanceSettings())
        self.order_fields.load(OrderSettings())
        self._loading = False
        self._validate()

    def _copy_result(self) -> None:
        result = self.controller.result
        if result is None:
            return
        self._loading = True
        self.domain_fields.load(DomainSettings.from_parameters(result.parameters))
        self.acceptance_fields.load(ClassAcceptanceSettings.from_parameters(result.parameters))
        self.order_fields.load(OrderSettings.from_parameters(result.parameters))
        if result.catalogue is not None:
            self.class_fields.choose_catalogue(result.catalogue)
            self.class_fields.mode.setCurrentIndex(1)
        else:
            self.class_fields.mode.setCurrentIndex(0)
            self.class_fields.k.setValue(int(result.parameters["k"]))
        self._loading = False
        self._validate()

    def _validate(self) -> None:
        if self._loading:
            return
        self.scope_fields.refresh()
        self.class_fields.refresh()
        self.acceptance_fields.set_k(self.class_fields.chosen_k)
        try:
            series = self.controller.series
            if series is None:
                raise ValueError("Najpierw otwórz serię.")
            plan = self.plan()
            indices, fit = plan.indices(series.frame_count), plan.fit_settings(series.frame_count)
            target = str(indices[0] + 1) if len(indices) == 1 else f"{indices[0] + 1}–{indices[-1] + 1}"
            if fit is None:
                catalogue = self.class_fields.selected_catalogue
                validate_plan_catalogue(catalogue, series.identity, plan)
                source = "istniejący katalog " + catalogue.identifier[:8] if catalogue else "brak"
            else:
                fit_indices = fit.indices(indices[0], series.frame_count)
                source = (f"nowe K{plan.k} z kl. {fit_indices[0] + 1}–{fit_indices[-1] + 1}"
                          + (" (lokalne)" if fit.scope == "current_frame" else " (wspólne)"))
            self.validation.setText(f"Szkic: domeny na kl. {target} ({len(indices)}) · {source}.\n"
                                    "Analizuj zastosuje wszystkie cztery zakładki. Edycja nie zmienia obrazu.")
            self.validation.setToolTip(self.validation.text() + "\n" + order_settings_description(plan.order_settings))
            self.calculate.setEnabled(self.controller.can_analyze)
        except ValueError as error:
            self.validation.setText(str(error))
            self.validation.setToolTip(str(error))
            self.calculate.setEnabled(False)

    def _calculate(self) -> None:
        try:
            plan = self.plan()
            self.controller.start_series_analysis(plan, catalogue=self.class_fields.selected_catalogue)
        except ValueError:
            self._validate()

    def refresh(self) -> None:
        if self._loading:
            return
        self._loading = True
        controller, series = self.controller, self.controller.series
        identity = series.identity if series else None
        if identity != self._series_id:
            self._series_id = identity
            self._seen_catalogue = None
            count, index = (series.frame_count, series.active_frame_index) if series else (1, 0)
            self.scope_fields.reset(count, index)
            self.class_fields.reset(count, index)
            self.domain_fields.load(DomainSettings())
            self.acceptance_fields.load(ClassAcceptanceSettings())
            self.order_fields.load(OrderSettings())
            self.context.setToolTip("Otwarto nową serię: szkic parametrów i wybór katalogu zostały zresetowane.")
        self.class_fields.offer_catalogues(controller.available_catalogues)
        run = controller.series_run
        if run is not None and run.catalogue is not None:
            key = (run.identifier, run.catalogue.identifier)
            if key != self._seen_catalogue:
                self._seen_catalogue = key
                self.class_fields.choose_catalogue(run.catalogue)
        self.context.setText(f"Klatka {controller.current_index + 1} · szkic ustawień tej serii" if series else "Brak serii")
        self.tabs.setEnabled(controller.can_analyze)
        self.baseline.setEnabled(controller.can_analyze)
        self.copy_result.setEnabled(controller.can_analyze and controller.result is not None)
        self.cancel.setEnabled(controller.series_running)
        self.comparison.setEnabled(controller.can_analyze and controller.previous_result is not None)
        with QSignalBlocker(self.comparison):
            self.comparison.setCurrentIndex(self.comparison.findData(controller.result_version))
        self.progress.setText(run.message if run else "Nie uruchomiono analizy. Nowa seria zaczyna od bazowych ustawień.")
        self.progress.setToolTip(self.progress.text())
        self.statuses.refresh(run)
        self._display_result()
        self._loading = False
        self._validate()

    def _display_result(self) -> None:
        controller, result = self.controller, self.controller.result
        if result is None:
            self.displayed.setText("Brak wyniku na oglądanej klatce.")
            self.displayed.setToolTip("")
            return
        name = "Poprzedni" if controller.result_version == "previous" else "Nowy"
        accepted = sum(bool(a.metadata.get("class_reliable")) for a in result.assignments.values())
        text = (f"{name} · kl. {result.working_index + 1}: klasy {accepted}/{result.active_count}; "
                f"porządek {result.metadata.get('order_supported_count', '—')}; "
                f"domeny {result.domain_count}, przypisano {result.assigned_count}/{result.active_count}.\n"
                + catalogue_description(result.catalogue))
        if result.status != "complete":
            text = f"{name}: " + result.message
        run = controller.series_run
        if run and result.metadata.get("series_analysis", {}).get("run_id") != run.identifier:
            text += "\nWyświetlono wynik spoza tego przebiegu."
        self.displayed.setText(text)
        settings = ClassAcceptanceSettings.from_parameters(result.parameters)
        self.displayed.setToolTip(text + f"\nUżyto marginesu {settings.class_margin:g}, mnożnika {settings.class_radius_multiplier:g}.\n"
                                 + order_settings_description(OrderSettings.from_parameters(result.parameters))
                                 + "\nPełne parametry: Dane… przy legendzie obrazu.")
