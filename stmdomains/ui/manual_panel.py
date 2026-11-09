"""Panel A: editing-only side panel, with a persistent result comparison bar."""

from PyQt6.QtCore import QSignalBlocker, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from stmdomains.core.frame_presentation import PresentedFrame
from stmdomains.core.manual_domains import domain_record
from stmdomains.core.result_names import class_name, domain_name, domain_names
from stmdomains.ui.image_view import ImageView
from stmdomains.ui.manual_controller import ManualController, UNSAVED_MANUAL
from stmdomains.ui.manual_selection import ManualSelection
from stmdomains.ui.manual_class_dialog import ManualClassDialog


class ManualPanel(QWidget):
    def __init__(self, manual: ManualController, view: ImageView) -> None:
        super().__init__()
        self.setObjectName('manualPanel')
        self.manual, self.view = manual, view
        self.selection = ManualSelection(view)
        self.selection.selected.connect(self._select)
        self.selection.escape.connect(self._escape)
        self.toolbar = QWidget()
        bar = QHBoxLayout(self.toolbar)
        bar.setContentsMargins(0, 0, 0, 0)
        self.edit = QPushButton('Edytuj domeny')
        self.edit.setObjectName('editDomains')
        self.edit.clicked.connect(lambda: manual.set_editing(not manual.editing))
        self.variants = QComboBox()
        self.variants.setMinimumWidth(140)
        self.variants.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.variants.currentIndexChanged.connect(lambda: manual.select_variant(self.variants.currentData() or ''))
        self.compare = QCheckBox('Automatyczny przed korektą')
        self.compare.toggled.connect(manual.set_comparison)
        for widget in (self.edit, self.variants, self.compare):
            bar.addWidget(widget, 1 if widget is self.variants else 0)
        self.setFixedWidth(310)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 0, 0, 0)
        title = QLabel('Edycja ręczna domen')
        outer.addWidget(title)
        self.classes = QPushButton('Klasy ręczne…')
        self.class_dialog: ManualClassDialog | None = None
        self.classes.clicked.connect(self._show_classes)
        outer.addWidget(self.classes)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.tool = QComboBox()
        for label, key in [('Lasso', 'lasso'), ('Kliknięcia', 'click'), ('Przesuwanie', 'pan')]:
            self.tool.addItem(label, key)
        self.mode = QComboBox()
        for label, key in [('Zastąp wybór', 'replace'), ('Dodaj do wyboru', 'add'), ('Odejmij z wyboru', 'subtract')]:
            self.mode.addItem(label, key)
        form.addRow('Narzędzie', self.tool)
        form.addRow('Zaznaczanie', self.mode)
        self.count = QLabel('Wybrano: 0')
        self.clear = QPushButton('Wyczyść wybór')
        self.clear.clicked.connect(lambda: self._select((), 'replace'))
        form.addRow(self.count)
        form.addRow(self.clear)
        self.operation = QComboBox()
        for label, key in [('Nowa domena', 'new'), ('Dodaj do domeny', 'add'),
                           ('Usuń z domeny', 'remove'), ('Przenieś do domeny', 'move'),
                           ('Podziel domenę', 'split'), ('Połącz domeny', 'merge')]:
            self.operation.addItem(label, key)
        self.target = QComboBox()
        form.addRow('Operacja', self.operation)
        form.addRow('Domena', self.target)
        self.operation_hint = QLabel()
        self.operation_hint.setWordWrap(True)
        form.addRow(self.operation_hint)
        self.members = QPlainTextEdit()
        self.members.setReadOnly(True)
        self.members.setAccessibleName('Domeny i członkowie objęci operacją')
        self.members.setMaximumHeight(100)
        form.addRow(self.members)
        self.review = QPushButton('Pokaż podgląd')
        self.review.clicked.connect(lambda: manual.preview(self.operation.currentData(), self.target.currentData() or 0))
        self.message = QLabel()
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setWordWrap(True)
        self.support = QLabel()
        self.support.setTextFormat(Qt.TextFormat.PlainText)
        self.support.setWordWrap(True)
        form.addRow(self.support)
        help_text = QLabel('Lasso obejmuje centra molekuł. Shift: dodaj, Alt: odejmij. '
                          'Spacja: przesuń obraz. Esc: anuluj podgląd lub wyczyść wybór.')
        help_text.setWordWrap(True)
        form.addRow(help_text)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        outer.addWidget(self.review)
        outer.addWidget(self.message)
        self.apply = QPushButton('Zastosuj')
        self.apply.clicked.connect(manual.apply)
        self.cancel = QPushButton('Anuluj podgląd')
        self.cancel.clicked.connect(manual.cancel_preview)
        actions = QHBoxLayout()
        actions.addWidget(self.apply)
        actions.addWidget(self.cancel)
        outer.addLayout(actions)
        history = QHBoxLayout()
        self.undo = QPushButton('Cofnij')
        self.redo = QPushButton('Ponów')
        self.undo.clicked.connect(manual.undo)
        self.redo.clicked.connect(manual.redo)
        history.addWidget(self.undo)
        history.addWidget(self.redo)
        outer.addLayout(history)
        note = QLabel('Korekty: Plik → Zapisz projekt…')
        note.setWordWrap(True)
        note.setToolTip(UNSAVED_MANUAL)
        outer.addWidget(note)
        self.tool.currentIndexChanged.connect(self.refresh)
        self.mode.currentIndexChanged.connect(self.refresh)
        self.operation.currentIndexChanged.connect(manual.cancel_preview)
        self.target.currentIndexChanged.connect(manual.cancel_preview)
        manual.changed.connect(self.refresh)
        manual.controller.busy_changed.connect(self.refresh)
        manual.controller.playback_changed.connect(self._playback)
        for shortcut_key, callback in ((QKeySequence.StandardKey.Undo, manual.undo),
                              (QKeySequence.StandardKey.Redo, manual.redo)):
            shortcut = QShortcut(QKeySequence(shortcut_key), self.toolbar)
            shortcut.activated.connect(callback)
        self.refresh()

    def _playback(self, playing: bool) -> None:
        if playing:
            self.manual.set_editing(False)

    def _show_classes(self) -> None:
        if self.class_dialog is None:
            self.class_dialog = ManualClassDialog(self.manual, self)
        self.class_dialog.refresh()
        self.class_dialog.show()
        self.class_dialog.raise_()

    def set_frame(self, frame: PresentedFrame) -> None:
        self.selection.set_frame(frame)
        self.refresh()

    def _select(self, identifiers: tuple[str, ...], mode: str) -> None:
        try:
            self.manual.select_molecules(identifiers, mode)
        except ValueError as error:
            self.manual.message = str(error)
            self.refresh()

    def _escape(self) -> None:
        if self.manual.preview_result is not None:
            self.manual.cancel_preview()
        else:
            self._select((), 'replace')

    def refresh(self, *_: object) -> None:
        manual = self.manual
        controller = manual.controller
        self.setVisible(manual.editing)
        self.toolbar.setVisible(controller.series is not None)
        self.edit.setText('Zakończ edycję' if manual.editing else 'Edytuj domeny')
        self.edit.setEnabled(controller.can_analyze or manual.editing)
        self.classes.setEnabled(manual.can_edit)
        with QSignalBlocker(self.variants):
            self.variants.clear()
            for key, label in manual.choices():
                self.variants.addItem(label, key)
            self.variants.setCurrentIndex(max(0, self.variants.findData(manual.selected.get(controller.current_index, ''))))
        self.variants.setEnabled(not controller.is_busy)
        self.compare.setEnabled(manual.active is not None and not controller.is_busy)
        with QSignalBlocker(self.compare):
            self.compare.setChecked(manual.compare_original)
        self.selection.configure(manual.can_edit, self.tool.currentData(), self.mode.currentData())
        self.selection.set_selected(manual.selection)
        active = manual.active
        self.selection.eligible_ids = active.eligible_ids if active else None
        result = (active.original if manual.compare_original and active is not None else manual.current_result)
        names = domain_names(result) if result else {}
        domains = sorted({a.domain_local_id for a in result.assignments.values() if a.domain_local_id > 0}) if result else []
        operation = self.operation.currentData()
        selected_domains = {result.assignments[key].domain_local_id for key in manual.selection
                            if result is not None and key in result.assignments} - {0}
        if operation == 'merge':
            domains = [d for d in domains if d in selected_domains]
        target = self.target.currentData()
        with QSignalBlocker(self.target):
            self.target.clear()
            for number in domains:
                self.target.addItem(f'{names[number]} (ID {number})', number)
            self.target.setCurrentIndex(max(0, self.target.findData(target)))
        self.target.setEnabled(manual.can_edit and operation in ('add', 'move', 'merge'))
        self.operation_hint.setVisible(operation in ('split', 'merge'))
        self.operation_hint.setText('Wskaż choć jedną molekułę z każdej domeny do połączenia. '
            'Operacja obejmie wszystkich członków tych domen. Wybierz docelowe ID.' if operation == 'merge' else
            'Zaznacz niepustą część jednej domeny. Reszta zachowa ID; wydzielona część dostanie nowe.')
        self.members.setVisible(operation in ('split', 'merge'))
        member_lines = []
        for domain in sorted(selected_domains):
            record = domain_record(domain, result.assignments) if result else {}
            identities, class_id = record.get('member_ids', ()), record.get('class_id', '')
            label = class_name(result, class_id) if result and class_id else 'nieustalona'
            member_lines.append(f'{names[domain]}: {len(identities)} molekuł · klasa {label} · ID {domain}\n'
                                + ', '.join(identities))
        member_text = '\n\n'.join(member_lines) or 'Nie wybrano domen.'
        if self.members.toPlainText() != member_text:
            self.members.setPlainText(member_text)
        self.count.setText(f'Wybrano: {len(manual.selection)} molekuł')
        self.message.setText(manual.message or 'Zaznacz molekuły i przygotuj podgląd zmiany.')
        shown = controller.displayed_result
        unsupported = shown.metadata.get('manual_edit', {}).get('unsupported_domains', ()) if shown else ()
        self.support.setText(('Brak obszaru (za mało wsparcia): ' + ', '.join(domain_name(shown, i) for i in unsupported))
                             if unsupported and shown else 'Obszar przybliża członkostwo; nie potwierdza porządku sieci.')
        self.review.setEnabled(manual.can_edit and bool(manual.selection))
        self.apply.setEnabled(manual.can_edit and manual.preview_result is not None)
        self.cancel.setEnabled(manual.preview_result is not None)
        for button, redo in ((self.undo, False), (self.redo, True)):
            history_target = manual.history_target(redo=redo)
            label = 'Ponów' if redo else 'Cofnij'
            button.setText(f'{label} · {manual.history_label(redo=redo)}' if history_target else label)
            button.setToolTip('Historia operacji projektu; przechodzi do klatki wskazanej na przycisku.')
            button.setEnabled(manual.can_edit and history_target is not None)
        for widget in (self.operation, self.clear, self.tool, self.mode):
            widget.setEnabled(manual.can_edit)
