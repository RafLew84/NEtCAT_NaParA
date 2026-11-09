"""One persistent parameter draft, one explicit run and independent result browsing."""

from collections.abc import Mapping
from typing import Any

from stmdomains.core.class_catalogue import ClassCatalogue

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
from stmdomains.ui.auto_ranking_dialog import AutoRankingDialog
from stmdomains.analysis.geometry_domain_settings import GeometryDomainSettings, METHOD
from stmdomains.ui.geometry_domain_fields import GeometryDomainFields
from stmdomains.analysis.freud_settings import FreudSettings, METHOD as FREUD_METHOD
from stmdomains.ui.freud_fields import FreudFields
from stmdomains.analysis.levelset_settings import LevelSetSettings, METHOD as LEVELSET_METHOD
from stmdomains.ui.levelset_fields import LevelSetFields, STOPPING_LABELS
from stmdomains.ui.acceptance_fields import AcceptanceFields
from stmdomains.analysis.descriptor_settings import DescriptorSettings
from stmdomains.analysis.barrier_settings import BarrierSettings
from stmdomains.ui.advanced_fields import AdvancedFields
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
        method_row = QHBoxLayout()
        method_row.addWidget(QLabel('Metoda domen'))
        self.method = QComboBox()
        self.method.addItem('Bazowa — klasy i porządek', 'baseline')
        self.method.addItem('Geometria — tolerancje (eksperymentalna)', 'geometry')
        self.method.addItem('freud — podobieństwo otoczeń (eksperymentalna)', 'freud')
        self.method.addItem('Level set (eksperymentalna)', 'levelset')
        method_row.addWidget(self.method, 1)
        layout.addLayout(method_row)
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
        self.advanced_fields = AdvancedFields()
        for title, fields in (("Zakres", self.scope_fields), ("Klasy", classes),
                               ("Porządek", self.order_fields), ("Domeny", self.domain_fields),
                               ("Zaawansowane", self.advanced_fields)):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(fields)
            scroll.setMinimumHeight(150)
            self.tabs.addTab(scroll, title)
        self.geometry_fields = GeometryDomainFields()
        geometry_scroll = QScrollArea()
        geometry_scroll.setWidgetResizable(True)
        geometry_scroll.setWidget(self.geometry_fields)
        self.tabs.addTab(geometry_scroll, 'Geometria')
        self.tabs.setTabVisible(5, False)
        self.freud_fields = FreudFields()
        freud_scroll = QScrollArea()
        freud_scroll.setWidgetResizable(True)
        freud_scroll.setWidget(self.freud_fields)
        self.tabs.addTab(freud_scroll, 'Otoczenia freud')
        self.tabs.setTabVisible(6, False)
        self.levelset_fields = LevelSetFields()
        levelset_scroll = QScrollArea()
        levelset_scroll.setWidgetResizable(True)
        levelset_scroll.setWidget(self.levelset_fields)
        self.tabs.addTab(levelset_scroll, 'Level set')
        self.tabs.setTabVisible(7, False)
        layout.addWidget(self.tabs, 1)
        edits = QHBoxLayout()
        self.copy_result = QPushButton("Z wyświetlanego wyniku")
        self.copy_result.setToolTip("Skopiuj progi i wybierz katalog wyświetlanego wyniku. Zakres analizy pozostaje bez zmian.")
        self.copy_result.clicked.connect(self._copy_result)
        self.baseline = QPushButton("Przywróć bazowe parametry")
        self.baseline.setToolTip("Przywróć opis, bariery i progi akceptacji, porządku oraz domen. Zakresy i wybór klas pozostają bez zmian; inny opis wymaga nowego dopasowania.")
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
        auto_row = QHBoxLayout()
        self.auto_summary = self._label(2)
        self.auto_summary.setWordWrap(False)
        self.auto_details = QPushButton("Ranking Auto…")
        self.auto_details.setAutoDefault(False)
        self.auto_details.clicked.connect(self._show_auto)
        auto_row.addWidget(self.auto_summary, 1)
        auto_row.addWidget(self.auto_details)
        layout.addLayout(auto_row)
        self.statuses = AnalysisStatuses()
        self.statuses.frame_requested.connect(controller.show_frame)
        layout.addWidget(self.statuses)
        comparison = QHBoxLayout()
        self.comparison_label = QLabel("Pokaż na obrazie")
        comparison.addWidget(self.comparison_label)
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
                       self.order_fields, self.domain_fields, self.advanced_fields):
            fields.changed.connect(self._validate)
        self.geometry_fields.changed.connect(self._validate)
        self.freud_fields.changed.connect(self._validate)
        self.levelset_fields.changed.connect(self._validate)
        self.method.currentIndexChanged.connect(self._method_changed)
        self.class_fields.mode.currentIndexChanged.connect(self._load_catalogue_descriptor)
        self.class_fields.catalogue.currentIndexChanged.connect(self._load_catalogue_descriptor)
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

    def plan(self, *, inactive_baseline: bool = False) -> SeriesAnalysisPlan:
        scope, classes = self.scope_fields, self.class_fields
        current = scope.scope.currentData() == "current_frame"
        return SeriesAnalysisPlan(
            start=self.controller.current_index if current else scope.start.value() - 1,
            end=scope.end.value() - 1, current_frame=current,
            whole_series=scope.scope.currentData() == "whole_series", k=classes.chosen_k,
            fit_source="existing" if classes.mode.currentData() == "existing" else classes.fit_source.currentData(),
            fit_start=classes.fit_start.value() - 1, fit_end=classes.fit_end.value() - 1,
            domain_settings=DomainSettings() if inactive_baseline else self.domain_fields.settings(), order_settings=self.order_fields.settings(),
            acceptance=self.acceptance_fields.settings(),
            descriptor_settings=DescriptorSettings() if inactive_baseline else self.advanced_fields.descriptor.settings(),
            barrier_settings=self.advanced_fields.barriers.settings(),
            class_count_mode="auto" if classes.automatic else "manual", auto_max_k=classes.maximum_k,
        )

    def _method_changed(self) -> None:
        geometric = self.method.currentData() in ('geometry', 'freud', 'levelset')
        freud = self.method.currentData() == 'freud'
        levelset = self.method.currentData() == 'levelset'
        self.geometry_fields.set_levelset(levelset)
        for index in range(4):
            self.tabs.setTabVisible(index, not geometric)
        self.tabs.setTabVisible(5, geometric)
        self.tabs.setTabVisible(6, freud)
        self.tabs.setTabVisible(7, levelset)
        self.tabs.setCurrentIndex(7 if levelset else 6 if freud else 5 if geometric else 0)
        self.advanced_fields.descriptor.setVisible(not geometric)
        self.auto_summary.setVisible(not geometric)
        self.auto_details.setVisible(not geometric)
        self.statuses.setVisible(not geometric)
        self.comparison.setVisible(not geometric)
        self.comparison_label.setVisible(not geometric)
        self.refresh()

    def _baseline(self) -> None:
        self._loading = True
        self.geometry_fields.load(GeometryDomainSettings(), DomainSettings())
        self.freud_fields.load(FreudSettings())
        self.levelset_fields.load(LevelSetSettings())
        self.domain_fields.load(DomainSettings())
        self.acceptance_fields.load(ClassAcceptanceSettings())
        self.order_fields.load(OrderSettings())
        self.advanced_fields.descriptor.load(DescriptorSettings())
        self.advanced_fields.barriers.load(BarrierSettings())
        self._loading = False
        self._validate()

    def _copy_result(self) -> None:
        result = self.controller.result
        if result is None:
            return
        self._loading = True
        self.method.setCurrentIndex({METHOD: 1, FREUD_METHOD: 2, LEVELSET_METHOD: 3}.get(result.parameters.get('domain_method', ''), 0))
        self.freud_fields.load(FreudSettings.from_parameters(result.parameters))
        self.levelset_fields.load(LevelSetSettings.from_parameters(result.parameters))
        self.geometry_fields.load(GeometryDomainSettings.from_parameters(result.parameters), DomainSettings.from_parameters(result.parameters))
        self.domain_fields.load(DomainSettings.from_parameters(result.parameters))
        self.acceptance_fields.load(ClassAcceptanceSettings.from_parameters(result.parameters))
        self.order_fields.load(OrderSettings.from_parameters(result.parameters))
        self.advanced_fields.descriptor.load(DescriptorSettings.from_parameters(result.parameters))
        self.advanced_fields.barriers.load(BarrierSettings.from_parameters(result.parameters))
        if result.catalogue is not None:
            self.class_fields.choose_catalogue(result.catalogue)
            self.class_fields.mode.setCurrentIndex(1)
        else:
            self.class_fields.mode.setCurrentIndex(0)
            self.class_fields.count_mode.setCurrentIndex(1 if result.parameters.get("class_count_mode") == "auto" else 0)
            self.class_fields.auto_max_k.setValue(int(result.parameters.get("auto_max_k", 8)))
            if result.parameters.get("k") is not None:
                self.class_fields.k.setValue(int(result.parameters["k"]))
        self._loading = False
        self._validate()

    def _load_catalogue_descriptor(self) -> None:
        if self._loading or self.class_fields.mode.currentData() != 'existing':
            return
        catalogue = self.class_fields.selected_catalogue
        if catalogue is not None:
            self.advanced_fields.descriptor.load(DescriptorSettings.from_parameters(catalogue.parameters))
        self._validate()

    def _validate(self) -> None:
        if self._loading:
            return
        self.scope_fields.refresh()
        self.class_fields.refresh()
        unknown_k = self.class_fields.mode.currentData() == "new" and self.class_fields.automatic
        self.acceptance_fields.set_k(0 if unknown_k else self.class_fields.chosen_k)
        try:
            series = self.controller.series
            if series is None:
                raise ValueError("Najpierw otwórz serię.")
            if self.method.currentData() in ('geometry', 'freud', 'levelset'):
                self.geometry_fields.settings()
                self.geometry_fields.constraints()
                self.advanced_fields.barriers.settings()
                if self.method.currentData() == 'freud':
                    self.freud_fields.settings()
                    from stmdomains.analysis.freud_adapter import require_freud
                    require_freud()
                if self.method.currentData() == 'levelset':
                    self.levelset_fields.settings()
                name = {'freud': 'freud + geometria + bariery', 'levelset': 'Level set + geometria + bariery'}.get(
                    self.method.currentData(), 'geometria + bariery')
                self.validation.setText(f'Szkic: {name} · kl. {self.controller.current_index + 1}.\n'
                                        'Analizuj zastosuje ustawienia. Edycja nie zmienia obrazu.')
                self.validation.setToolTip(self.validation.text())
                self.calculate.setEnabled(self.controller.can_analyze)
                return
            plan = self.plan()
            indices, fit = plan.indices(series.frame_count), plan.fit_settings(series.frame_count)
            target = str(indices[0] + 1) if len(indices) == 1 else f"{indices[0] + 1}–{indices[-1] + 1}"
            if fit is None:
                catalogue = self.class_fields.selected_catalogue
                validate_plan_catalogue(catalogue, series.identity, plan)
                source = "istniejący katalog " + catalogue.identifier[:8] if catalogue else "brak"
            else:
                fit_indices = fit.indices(indices[0], series.frame_count)
                count = f"Auto (maks. {plan.auto_max_k})" if plan.class_count_mode == "auto" else f"K{plan.k}"
                source = (f"nowe {count} z kl. {fit_indices[0] + 1}–{fit_indices[-1] + 1}"
                          + (" (lokalne)" if fit.scope == "current_frame" else " (wspólne)"))
            self.validation.setText(f"Szkic: domeny na kl. {target} ({len(indices)}) · {source}.\n"
                                    "Analizuj zastosuje wszystkie pięć zakładek. Edycja nie zmienia obrazu.")
            self.validation.setToolTip(self.validation.text() + "\n" + order_settings_description(plan.order_settings))
            self.calculate.setEnabled(self.controller.can_analyze)
        except ValueError as error:
            self.validation.setText(str(error))
            self.validation.setToolTip(str(error))
            self.calculate.setEnabled(False)

    def _calculate(self) -> None:
        try:
            if self.method.currentData() == 'levelset':
                self.controller.analyze_levelset_domains(self.levelset_fields.settings(),
                    geometry_settings=self.geometry_fields.settings(), constraints=self.geometry_fields.constraints(),
                    barrier_settings=self.advanced_fields.barriers.settings())
                self.close()
                return
            if self.method.currentData() == 'freud':
                self.controller.analyze_freud_domains(self.freud_fields.settings(),
                    geometry_settings=self.geometry_fields.settings(), constraints=self.geometry_fields.constraints(),
                    barrier_settings=self.advanced_fields.barriers.settings())
                self.close()
                return
            if self.method.currentData() == 'geometry':
                self.controller.analyze_geometry_domains(self.geometry_fields.settings(),
                    constraints=self.geometry_fields.constraints(), barrier_settings=self.advanced_fields.barriers.settings())
                self.close()
                return
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
            self.method.setCurrentIndex(0)
            self.geometry_fields.load(GeometryDomainSettings(), DomainSettings())
            self.freud_fields.load(FreudSettings())
            self.levelset_fields.load(LevelSetSettings())
            count, index = (series.frame_count, series.active_frame_index) if series else (1, 0)
            self.scope_fields.reset(count, index)
            self.class_fields.reset(count, index)
            self.domain_fields.load(DomainSettings())
            self.acceptance_fields.load(ClassAcceptanceSettings())
            self.order_fields.load(OrderSettings())
            self.advanced_fields.descriptor.load(DescriptorSettings())
            self.advanced_fields.barriers.load(BarrierSettings())
            self.advanced_fields.show_barriers.setChecked(False)
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
        self.method.setEnabled(controller.can_analyze)
        self.baseline.setEnabled(controller.can_analyze)
        self.copy_result.setEnabled(controller.can_analyze and controller.result is not None)
        self.cancel.setEnabled(controller.is_busy)
        self.comparison.setEnabled(controller.can_analyze and controller.previous_result is not None)
        with QSignalBlocker(self.comparison):
            self.comparison.setCurrentIndex(self.comparison.findData(controller.result_version))
        self.progress.setText(run.message if run else "Nie uruchomiono analizy. Nowa seria zaczyna od bazowych ustawień.")
        if self.method.currentData() in ('geometry', 'freud', 'levelset'):
            method = self.method.currentData()
            self.progress.setText('Trwa obliczanie — postęp także pod obrazem.' if controller.is_busy else
                                  f'{method}: wynik dostępny na obrazie.' if controller.result_for_method(method) else
                                  'Kliknij Analizuj, aby obliczyć wybraną metodę.')
        self.progress.setToolTip(self.progress.text())
        self.statuses.refresh(run)
        selection, _, context = self._auto_context()
        if selection:
            k = selection["selected_k"]
            heading = context + (f": K{k}" if k is not None else ": nierozstrzygnięte")
            reason = str(selection["reason"])
            brief = self.auto_summary.fontMetrics().elidedText(reason, Qt.TextElideMode.ElideRight, self.auto_summary.width())
            self.auto_summary.setText(heading + "\n" + brief)
            self.auto_summary.setToolTip(heading + "\n" + reason)
        else:
            self.auto_summary.setText("Auto: wybierz tryb w zakładce Klasy.")
            self.auto_summary.setToolTip("")
        self.auto_details.setEnabled(selection is not None)
        self._display_result()
        self._loading = False
        self._validate()

    def _auto_context(self) -> tuple[Mapping[str, Any] | None, ClassCatalogue | None, str]:
        controller = self.controller
        result, run = controller.result, controller.series_run
        shown = result.metadata.get("class_selection") if result else None
        if shown and (controller.result_version == "previous" or not run or not run.selection):
            return shown, result.catalogue if result else None, "Auto wyświetlanego wyniku"
        return (run.selection, run.catalogue, "Auto ostatniego przebiegu") if run else (None, None, "Auto")

    def _show_auto(self) -> None:
        selection, catalogue, context = self._auto_context()
        if selection is None:
            return
        dialog = AutoRankingDialog(selection, catalogue, self)
        dialog.setWindowTitle(context + " — ranking")
        dialog.show()

    def _display_result(self) -> None:
        controller, result = self.controller, self.controller.result
        barrier = result.barrier_mask if result is not None else None
        self.advanced_fields.barrier_status.setText(
            f'Maska wyświetlanego wyniku: {int(barrier.sum())} px; parametry szkicu wymagają Analizuj.'
            if barrier is not None else 'Brak zapisanej maski barier dla tego wyniku. Oblicz wynik, aby ją zobaczyć.')
        if result is None:
            self.displayed.setText("Brak wyniku na oglądanej klatce.")
            self.displayed.setToolTip("")
            return
        if result.parameters.get('domain_method') == LEVELSET_METHOD:
            levelset = LevelSetSettings.from_parameters(result.parameters)
            info = result.metadata.get('levelset', {})
            reason = STOPPING_LABELS.get(info.get('stopping_reason', ''), 'brak ewolucji')
            text = (f'Level set · kl. {result.working_index+1}: {result.domain_count} domen, '
                    f'{result.assigned_count}/{result.active_count} molekuł.\n'
                    f'Użyto: siła {levelset.regularization:g}, iteracje {info.get("iterations", 0)}/{levelset.iterations} · {reason}.\n'
                    f'Regiony modelu: {info.get("initial_model_regions", 0)} → {info.get("final_model_regions", 0)}; typ nieznany, faza niesprawdzana.')
            self.displayed.setText(text)
            self.displayed.setToolTip(text + '\n' + result.message)
            return
        if result.parameters.get('domain_method') == FREUD_METHOD:
            settings = FreudSettings.from_parameters(result.parameters)
            text = (f'freud · kl. {result.working_index+1}: {len(result.classes)} klas otoczeń, '
                    f'{result.domain_count} domen, {result.assigned_count}/{result.active_count} w domenach.\n'
                    f'Użyto: tolerancja {settings.tolerance:g} ×NN, sąsiedzi {settings.neighbor_count}, '
                    f'zasięg {settings.radius_factor:g} ×NN, rejestracja {"obrót/odbicie" if settings.registration else "wyłączona"}.\n'
                    'Klasy lokalne; pełne parametry: Dane… przy legendzie.')
            self.displayed.setText(text)
            self.displayed.setToolTip(text + '\n' + result.message)
            return
        if result.parameters.get('domain_method') == METHOD:
            geometric_settings = GeometryDomainSettings.from_parameters(result.parameters)
            text = (f'Geometria · kl. {result.working_index+1}: {result.domain_count} domen, '
                    f'{result.assigned_count}/{result.active_count} molekuł.\n'
                    f'Użyto: {geometric_settings.angle_degrees:g}°, {geometric_settings.spacing_percent:g}%, '
                    f'jakość ≥ {geometric_settings.minimum_coherence:g}, lokalnie ≥ {geometric_settings.minimum_local_count}.\n'
                    'Typ nieznany; granice fazowe niesprawdzane.')
            self.displayed.setText(text)
            self.displayed.setToolTip(text + '\n' + result.message)
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
        acceptance = ClassAcceptanceSettings.from_parameters(result.parameters)
        self.displayed.setToolTip(text + f"\nUżyto marginesu {acceptance.class_margin:g}, mnożnika {acceptance.class_radius_multiplier:g}.\n"
                                 + order_settings_description(OrderSettings.from_parameters(result.parameters))
                                 + "\nPełne parametry: Dane… przy legendzie obrazu.")
