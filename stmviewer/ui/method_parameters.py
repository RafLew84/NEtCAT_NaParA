"""One modeless editor with atomic drafts and shared immutable method profiles."""
from __future__ import annotations

from dataclasses import asdict
from collections.abc import Callable

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel,
    QLineEdit, QMenuBar, QPushButton, QScrollArea, QStackedWidget, QToolButton,
    QVBoxLayout, QWidget,
)

from stmviewer.method_parameters import (
    PARAMETER_METHODS, AkazeParameters, LightGlueParameters, FeatureParameters,
    MethodProfiles, decode_profile,
)


class ParameterForm(QWidget):
    def __init__(self, method: str, parameters: FeatureParameters, parent: QWidget) -> None:
        super().__init__(parent)
        self.method = method
        self.fields: dict[str, QLineEdit] = {}
        layout = QVBoxLayout(self)
        basic = QFormLayout()
        layout.addLayout(basic)
        threshold_help = 'Mniejszy próg dopuszcza więcej punktów, również pochodzących z szumu.'
        if method == 'akaze':
            self._field(basic, 'threshold', 'Próg detektora', threshold_help)
        else:
            self._field(basic, 'detection_threshold', 'Próg SuperPoint', threshold_help)
            self._field(basic, 'max_keypoints', 'Maksymalna liczba punktów',
                        'Więcej punktów może zwiększyć czas i zużycie pamięci; nie gwarantuje poprawnego XY.')
            self._field(basic, 'filter_threshold', 'Próg dopasowań LightGlue',
                        'Mniejszy próg dopuszcza więcej dopasowań, również błędnych.')
        self._field(basic, 'radius', 'Tolerancja zgodności [px original]',
                    'Dopuszczalna rozbieżność wektorów pary. To nie jest próg Hubera.')
        contrast = self._group(layout, 'Przygotowanie kontrastu')
        self.mode = QComboBox(self)
        self.mode.setObjectName(method + '_contrast_mode')
        for label, key in (('Min–max (dotychczasowe)', 'minmax'),
                           ('Percentyle', 'percentiles'), ('CLAHE', 'clahe')):
            self.mode.addItem(label, key)
        contrast.addRow('Tryb', self.mode)
        for key, label, help_text in (
            ('lower', 'Dolny percentyl', 'Zakres 0–100; dolny musi być mniejszy od górnego.'),
            ('upper', 'Górny percentyl', 'Zakres wyznaczany osobno dla każdego obrazu.'),
            ('clip_limit', 'Limit kontrastu CLAHE', 'Dodatnia wartość; wyższa może wzmacniać także szum.'),
            ('grid_x', 'Siatka CLAHE — kolumny', 'Dodatnia liczba całkowita.'),
            ('grid_y', 'Siatka CLAHE — wiersze', 'Dodatnia liczba całkowita.'),
        ):
            self._field(contrast, key, label, help_text)
        self.mode.currentIndexChanged.connect(self._contrast_visibility)
        self.full: QCheckBox | None = None
        if method == 'lightglue_superpoint':
            advanced = self._group(layout, 'Ustawienia zaawansowane')
            self._field(advanced, 'nms_radius', 'Promień NMS [px original]',
                        'Nieujemna liczba całkowita. Większy promień rozsuwa wybierane punkty.')
            self.full = QCheckBox('Pełne obliczenia LightGlue', self)
            self.full.setObjectName(method + '_full_computation')
            self.full.setToolTip('Wyłącza wczesne zakończenie i redukcję punktów; może zwiększyć czas obliczeń.')
            advanced.addRow(self.full)
        note = QLabel('Kontrast zmienia tylko wejście algorytmu. Obrazy original, '
                      'gamma podglądu i wartości eksportu pozostają zachowane.', self)
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        self.set_profile(parameters)

    def _field(self, layout: QFormLayout, key: str, label: str, help_text: str) -> None:
        entry = QLineEdit(self)
        entry.setObjectName(self.method + '_' + key)
        entry.setToolTip(help_text)
        entry.setAccessibleName(label)
        self.fields[key] = entry
        layout.addRow(label, entry)
        caption = layout.labelForField(entry)
        if caption is not None:
            caption.setToolTip(help_text)

    def _group(self, layout: QVBoxLayout, title: str) -> QFormLayout:
        toggle = QToolButton(self)
        toggle.setText(title)
        toggle.setCheckable(True)
        toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toggle.setArrowType(Qt.ArrowType.RightArrow)
        content = QWidget(self)
        form = QFormLayout(content)
        content.hide()
        toggle.toggled.connect(content.setVisible)
        toggle.toggled.connect(lambda checked: toggle.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow))
        layout.addWidget(toggle)
        layout.addWidget(content)
        return form

    def _contrast_visibility(self) -> None:
        mode = self.mode.currentData()
        for key in ('lower', 'upper', 'clip_limit', 'grid_x', 'grid_y'):
            active = mode == ('percentiles' if key in ('lower', 'upper') else 'clahe')
            self.fields[key].setEnabled(active)

    def set_profile(self, parameters: FeatureParameters) -> None:
        values = asdict(parameters)
        contrast = values.pop('contrast')
        self.mode.setCurrentIndex(self.mode.findData(contrast.pop('mode')))
        values.update(contrast)
        if self.full is not None:
            self.full.setChecked(values.pop('full_computation'))
        for key, value in values.items():
            self.fields[key].setText(str(value))
        self._contrast_visibility()

    def profile(self) -> FeatureParameters:
        integers = {'max_keypoints', 'nms_radius', 'grid_x', 'grid_y'}
        values: dict[str, object] = {}
        for key, entry in self.fields.items():
            text = entry.text().strip().replace(',', '.')
            try:
                values[key] = int(text) if key in integers else float(text)
            except ValueError as error:
                raise ValueError(f'{entry.accessibleName()}: wpisz poprawną liczbę.') from error
        contrast = {key: values.pop(key) for key in ('lower', 'upper', 'clip_limit', 'grid_x', 'grid_y')}
        contrast['mode'] = str(self.mode.currentData())
        values['contrast'] = contrast
        if self.full is not None:
            values['full_computation'] = self.full.isChecked()
        return decode_profile(self.method, values)


class MethodParametersDialog(QDialog):
    def __init__(self, controls: MethodParameterControls, method: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName('methodParametersDialog')
        self.setWindowTitle('Parametry metod rejestracji')
        self.resize(590, 460)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._controls = controls
        layout = QVBoxLayout(self)
        self._method = QComboBox(self)
        self._method.setObjectName('parameterMethod')
        for key, label in PARAMETER_METHODS.items():
            self._method.addItem(label, key)
        layout.addWidget(self._method)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        self._stack = QStackedWidget(scroll)
        self._forms = {key: ParameterForm(key, controls.profiles.get(key), self._stack)
                       for key in PARAMETER_METHODS}
        for form in self._forms.values():
            self._stack.addWidget(form)
        scroll.setWidget(self._stack)
        layout.addWidget(scroll, 1)
        self._method.currentIndexChanged.connect(self._select)
        self._method.setCurrentIndex(self._method.findData(method))
        self._select()
        note = QLabel('Zmiany dotyczą kolejnego obliczenia.', self)
        note.setWordWrap(True)
        layout.addWidget(note)
        self._error = QLabel(self)
        self._error.setObjectName('parameterError')
        self._error.setTextFormat(Qt.TextFormat.PlainText)
        self._error.setWordWrap(True)
        layout.addWidget(self._error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        assert ok is not None and cancel is not None
        self._ok = ok
        ok.setText('OK')
        cancel.setText('Anuluj')
        reset = QPushButton('Przywróć domyślne', self)
        reset.setObjectName('resetMethodParameters')
        buttons.addButton(reset, QDialogButtonBox.ButtonRole.ResetRole)
        reset.clicked.connect(self._reset)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.set_busy(controls.busy)

    def _select(self) -> None:
        self._stack.setCurrentIndex(self._method.currentIndex())
        self._controls.last_method = str(self._method.currentData())

    def _reset(self) -> None:
        method = str(self._method.currentData())
        self._forms[method].set_profile(MethodProfiles().get(method))
        self._error.clear()

    def set_busy(self, busy: bool) -> None:
        self._ok.setEnabled(not busy)
        self._error.setText('Trwają obliczenia lub zapis. Zatwierdzenie będzie dostępne po zakończeniu.' if busy else '')

    def accept(self) -> None:
        if self._controls.busy:
            return
        try:
            akaze = self._forms['akaze'].profile()
            lightglue = self._forms['lightglue_superpoint'].profile()
            assert isinstance(akaze, AkazeParameters) and isinstance(lightglue, LightGlueParameters)
            self._controls.restore(MethodProfiles(akaze, lightglue), close_editor=False)
        except ValueError as error:
            self._error.setText(str(error))
            return
        super().accept()


class MethodParameterControls(QObject):
    changed = pyqtSignal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._profiles = MethodProfiles()
        self.last_method = 'akaze'
        self.busy = False
        self._dialog: MethodParametersDialog | None = None

    @property
    def profiles(self) -> MethodProfiles:
        return self._profiles

    def add_menu(self, menu: QMenuBar, selected_method: Callable[[], str]) -> None:
        registration = menu.addMenu('Rejestracja')
        assert registration is not None
        action = QAction('Parametry metod…', self)
        action.setObjectName('methodParametersAction')
        action.triggered.connect(lambda: self.open(selected_method()))
        registration.addAction(action)

    def open(self, selected_method: str) -> None:
        if self._dialog is None:
            method = selected_method if selected_method in PARAMETER_METHODS else self.last_method
            parent = self.parent()
            assert isinstance(parent, QWidget)
            self._dialog = MethodParametersDialog(self, method, parent)
            self._dialog.finished.connect(self._closed)
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    def _closed(self) -> None:
        self._dialog = None

    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        if self._dialog is not None:
            self._dialog.set_busy(busy)

    def restore(self, profiles: MethodProfiles, *, close_editor: bool = True) -> None:
        if close_editor and self._dialog is not None:
            self._dialog.reject()
        if profiles != self._profiles:
            self._profiles = profiles
            self.changed.emit()
