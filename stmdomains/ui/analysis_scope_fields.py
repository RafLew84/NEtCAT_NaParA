"""Independent analysis and discovery scopes, with an explicit catalogue selection."""

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFormLayout, QLabel, QSpinBox, QWidget

from stmdomains.core.class_catalogue import ClassCatalogue
from stmdomains.ui.catalogue_style import catalogue_description


def frame_spin() -> QSpinBox:
    spin = QSpinBox()
    spin.setMinimum(1)
    spin.setKeyboardTracking(False)
    return spin


class AnalysisScopeFields(QWidget):
    changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.form = form = QFormLayout(self)
        self.scope = QComboBox()
        for text, value in (("Bieżąca klatka", "current_frame"), ("Wybrany zakres", "selected_range"),
                            ("Cała seria", "whole_series")):
            self.scope.addItem(text, value)
        self.start, self.end = frame_spin(), frame_spin()
        form.addRow("Oblicz domeny", self.scope)
        form.addRow("Pierwsza klatka", self.start)
        form.addRow("Ostatnia klatka", self.end)
        note = QLabel("Ten zakres określa, które klatki otrzymają wynik. Dane do odkrywania klas wybierzesz "
                      "osobno w zakładce Klasy. Numery domen są lokalne dla każdej klatki.")
        note.setWordWrap(True)
        form.addRow(note)
        self.scope.currentIndexChanged.connect(self.changed)
        self.start.valueChanged.connect(self.changed)
        self.end.valueChanged.connect(self.changed)

    def reset(self, count: int, index: int) -> None:
        for spin in (self.start, self.end):
            spin.setRange(1, count)
        self.start.setValue(index + 1)
        self.end.setValue(count)
        self.scope.setCurrentIndex(0)

    def refresh(self) -> None:
        selected = self.scope.currentData() == "selected_range"
        self.start.setEnabled(selected)
        self.end.setEnabled(selected)
        self.form.setRowVisible(self.start, selected)
        self.form.setRowVisible(self.end, selected)


class ClassFields(QWidget):
    changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._catalogues: dict[str, ClassCatalogue] = {}
        form = QFormLayout(self)
        self.mode = QComboBox()
        self.mode.addItem("Dopasuj nowe klasy", "new")
        self.mode.addItem("Użyj istniejących klas", "existing")
        self.count_mode = QComboBox()
        self.count_mode.addItem("Ręczna liczba klas", "manual")
        self.count_mode.addItem("Auto — wybierz z danych", "auto")
        self.auto_max_k = QSpinBox()
        self.auto_max_k.setRange(1, 8)
        self.auto_max_k.setValue(8)
        self.auto_max_k.setToolTip("Auto może wybrać K1, kilka klas lub pozostać nierozstrzygnięte. Maksimum ogranicza poszukiwanie.")
        self.k = QSpinBox()
        self.k.setRange(1, 8)
        self.k.setValue(5)
        self.fit_source = QComboBox()
        for text, value in (("Ten sam zakres co analiza", "same_range"),
                            ("Inny wybrany zakres", "selected_range"), ("Cała seria", "whole_series")):
            self.fit_source.addItem(text, value)
        self.fit_start, self.fit_end = frame_spin(), frame_spin()
        self.catalogue = QComboBox()
        self.catalogue.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.catalogue.setMinimumContentsLength(22)
        self.catalogue_label = QLabel("Brak katalogu. Dopasuj nowe klasy.")
        self.catalogue_label.setWordWrap(True)
        for label, field in (("Źródło klas", self.mode), ("Wybór liczby klas", self.count_mode),
                             ("Ręczne K", self.k), ("Maksimum dla Auto", self.auto_max_k),
                             ("Dane do odkrywania klas", self.fit_source), ("Pierwsza klatka dopasowania", self.fit_start),
                             ("Ostatnia klatka dopasowania", self.fit_end), ("Istniejący katalog", self.catalogue)):
            form.addRow(label, field)
        form.addRow(self.catalogue_label)
        note = QLabel("K to liczba klas otoczeń molekuł. Jedna klasa może tworzyć wiele domen. "
                      "Klasa 1 z różnych katalogów nie musi oznaczać tego samego.")
        note.setWordWrap(True)
        form.addRow(note)
        for combo in (self.mode, self.count_mode, self.fit_source, self.catalogue):
            combo.currentIndexChanged.connect(self.changed)
        for spin in (self.k, self.auto_max_k, self.fit_start, self.fit_end):
            spin.valueChanged.connect(self.changed)

    @property
    def selected_catalogue(self) -> ClassCatalogue | None:
        return self._catalogues.get(self.catalogue.currentData())

    @property
    def chosen_k(self) -> int:
        active = self.selected_catalogue
        return active.k if self.mode.currentData() == "existing" and active else self.k.value()

    @property
    def automatic(self) -> bool:
        active = self.selected_catalogue
        if self.mode.currentData() == "existing" and active is not None:
            return "class_selection" in active.state
        return self.count_mode.currentData() == "auto"

    @property
    def maximum_k(self) -> int:
        active = self.selected_catalogue
        if self.mode.currentData() == "existing" and active is not None:
            return int(active.state.get("class_selection", {}).get("max_k", self.auto_max_k.value()))
        return self.auto_max_k.value()

    def reset(self, count: int, index: int) -> None:
        self._catalogues.clear()
        self.catalogue.clear()
        self.mode.setCurrentIndex(0)
        self.k.setValue(5)
        self.count_mode.setCurrentIndex(0)
        self.auto_max_k.setValue(8)
        self.fit_source.setCurrentIndex(0)
        for spin in (self.fit_start, self.fit_end):
            spin.setRange(1, count)
        self.fit_start.setValue(index + 1)
        self.fit_end.setValue(count)

    def offer_catalogues(self, catalogues: tuple[ClassCatalogue, ...]) -> None:
        # Keep only catalogues still referenced by results or the explicit draft selection.
        selected = self.selected_catalogue
        available = {item.identifier: item for item in catalogues}
        if selected is not None:
            available[selected.identifier] = selected
        if tuple(available) == tuple(self._catalogues):
            return
        self._catalogues = available
        with QSignalBlocker(self.catalogue):
            self.catalogue.clear()
            for identifier, item in available.items():
                self.catalogue.addItem(catalogue_description(item), identifier)
            if selected is not None:
                self.catalogue.setCurrentIndex(self.catalogue.findData(selected.identifier))

    def choose_catalogue(self, catalogue: ClassCatalogue) -> None:
        self.offer_catalogues((*self._catalogues.values(), catalogue))
        self.catalogue.setCurrentIndex(self.catalogue.findData(catalogue.identifier))

    def refresh(self) -> None:
        existing = self.mode.currentData() == "existing"
        selected = self.selected_catalogue
        if existing and selected is not None:
            with QSignalBlocker(self.k), QSignalBlocker(self.count_mode), QSignalBlocker(self.auto_max_k):
                self.k.setValue(selected.k)
                selection = selected.state.get("class_selection")
                self.count_mode.setCurrentIndex(1 if selection else 0)
                if selection:
                    self.auto_max_k.setValue(int(selection["max_k"]))
        self.count_mode.setEnabled(not existing)
        self.auto_max_k.setEnabled(not existing and self.automatic)
        self.k.setEnabled(not existing and not self.automatic)
        self.fit_source.setEnabled(not existing)
        self.catalogue.setEnabled(existing)
        for spin in (self.fit_start, self.fit_end):
            spin.setEnabled(not existing and self.fit_source.currentData() == "selected_range")
        self.catalogue_label.setText("Wybrany katalog: " + catalogue_description(selected))
        self.catalogue.setToolTip(self.catalogue_label.text())
