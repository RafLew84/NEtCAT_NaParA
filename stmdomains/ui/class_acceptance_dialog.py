"""Modeless acceptance editor for the displayed result's frozen catalogue."""

from PyQt6.QtCore import QSignalBlocker
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout,
    QLabel, QPushButton, QVBoxLayout, QWidget,
)

from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings
from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.ui.catalogue_style import catalogue_description
from stmdomains.ui.session_controller import SessionController


class ClassAcceptanceDialog(QDialog):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._result: FrameAnalysis | None = None
        self.setWindowTitle("Akceptacja klasy")
        self.setModal(False)
        self.resize(560, 440)
        layout = QVBoxLayout(self)
        self.context = QLabel()
        layout.addWidget(self.context)
        note = QLabel("Zmieniasz akceptację przy zachowanym katalogu klas.\n"
                      "Przeliczenie dotyczy bieżącej klatki i zachowuje jej parametry domen.\n"
                      "Akceptacja klasy nie gwarantuje wejścia do domeny: obowiązuje też porządek i geometria.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.fields = QWidget()
        form = QFormLayout(self.fields)
        self.margin = QDoubleSpinBox()
        self.margin.setRange(0., 1.)
        self.margin.setDecimals(3)
        self.margin.setSingleStep(.005)
        self.margin.setToolTip("Przewaga najlepszej klasy nad drugą; niższy próg dopuszcza większą niejednoznaczność.")
        self.radius = QDoubleSpinBox()
        self.radius.setRange(.05, 10.)
        self.radius.setDecimals(2)
        self.radius.setSingleStep(.05)
        self.radius.setToolTip("Dopuszczalne odchylenie od wzorca w przestrzeni cech. Większy mnożnik łagodzi próg; to nie odległość w nm.")
        form.addRow("Minimalny margines", self.margin)
        form.addRow("Mnożnik promienia klasy", self.radius)
        layout.addWidget(self.fields)
        self.rule = QLabel()
        self.rule.setWordWrap(True)
        self.rule.setMinimumHeight(self.rule.fontMetrics().height() * 2)
        layout.addWidget(self.rule)
        self.validation = QLabel()
        self.validation.setWordWrap(True)
        self.validation.setMinimumHeight(self.validation.fontMetrics().height() * 2)
        layout.addWidget(self.validation)
        actions = QHBoxLayout()
        self.baseline = QPushButton("Przywróć bazowe")
        self.baseline.setToolTip("Wpisz 0,075 i 1,10. Zastosuj przyciskiem Przelicz klatkę.")
        self.baseline.clicked.connect(lambda: self._load(ClassAcceptanceSettings()))
        self.calculate = QPushButton("Przelicz klatkę")
        self.calculate.clicked.connect(lambda: controller.recalculate_class_acceptance(self._settings()))
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
        self.margin.valueChanged.connect(self._validate)
        self.radius.valueChanged.connect(self._validate)
        controller.frame_changed.connect(lambda _: self.refresh())
        controller.busy_changed.connect(lambda busy, text: self.refresh())
        self._load(ClassAcceptanceSettings())
        self.refresh()

    def _settings(self) -> ClassAcceptanceSettings:
        return ClassAcceptanceSettings(self.margin.value(), self.radius.value())

    def _load(self, settings: ClassAcceptanceSettings) -> None:
        with QSignalBlocker(self.margin), QSignalBlocker(self.radius):
            self.margin.setValue(settings.class_margin)
            self.radius.setValue(settings.class_radius_multiplier)
        self._validate()

    def _validate(self) -> None:
        result = self.controller.result
        self.calculate.setEnabled(self.controller.can_tune_acceptance)
        if result is None or result.status != "complete" or result.catalogue is None:
            text = "Najpierw oblicz klasy i domeny tej klatki w aplikacji."
        elif self._settings() != ClassAcceptanceSettings.from_parameters(result.parameters):
            text = "Ustawienia nieprzeliczone. Kliknij „Przelicz klatkę”, aby je zastosować."
        else:
            text = "Ustawienia zgodne z wyświetlanym wynikiem. Edycja nie zmienia obrazu."
        self.validation.setText(text)

    def refresh(self) -> None:
        controller, result = self.controller, self.controller.result
        if result is not self._result:
            self._result = result
            self._load(ClassAcceptanceSettings.from_parameters(result.parameters) if result else ClassAcceptanceSettings())
        self.context.setText(f"Klatka {controller.current_index + 1} · akceptacja klasy"
                             if controller.series else "Najpierw otwórz zapis z obrazami i oznaczeniami.")
        k1 = result is not None and result.catalogue is not None and result.catalogue.k == 1
        self.fields.setEnabled(controller.can_tune_acceptance)
        self.margin.setEnabled(not k1)
        self.baseline.setEnabled(controller.can_tune_acceptance)
        self.cancel.setEnabled(controller.is_busy)
        self.comparison.setEnabled(controller.can_analyze and controller.previous_result is not None)
        with QSignalBlocker(self.comparison):
            self.comparison.setCurrentIndex(self.comparison.findData(controller.result_version))
        self.rule.setText("K1: margines nie dotyczy. Akceptację klasy określa promień i dostępność opisu."
                          if k1 else "Margines i promień sprawdzają podobieństwo otoczeń. Miara podobieństwa nie jest prawdopodobieństwem poprawności.")
        if result is None:
            text = "Brak wyniku do porównania."
        else:
            name = "Poprzedni" if controller.result_version == "previous" else "Nowy"
            settings = ClassAcceptanceSettings.from_parameters(result.parameters)
            margin = "nie dotyczy (K1)" if k1 else f"{settings.class_margin:g}"
            accepted = sum(bool(m.metadata.get("class_reliable")) for m in result.assignments.values())
            text = (f"{name}: akceptacja klasy {accepted}/{result.active_count}; domeny {result.assigned_count}/{result.active_count}.\n"
                    f"Użyto: margines {margin}, mnożnik {settings.class_radius_multiplier:g}.\n"
                    + catalogue_description(result.catalogue))
            if result.status != "complete":
                text = result.message
        self.displayed.setText(text)
        self._validate()
