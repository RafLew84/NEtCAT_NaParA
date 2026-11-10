"""Modeless merge/split editor with explicit, inspectable multi-frame scope."""

from PyQt6.QtCore import QSignalBlocker, Qt
from PyQt6.QtGui import QColor, QCloseEvent
from PyQt6.QtWidgets import (
    QAbstractItemView, QColorDialog, QComboBox, QDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from stmdomains.ui.manual_controller import ManualController
from stmdomains.ui.selection_controls import SelectionControls


class ClassOperationDialog(QDialog):
    def __init__(self, manual: ManualController, parent: QWidget) -> None:
        super().__init__(parent)
        self.manual, self.operations = manual, manual.class_operations
        self._labels_version = ''
        self._labels_id = ''
        self.setWindowTitle('Scalanie i dzielenie klas')
        self.resize(820, 760)
        layout = QVBoxLayout(self)
        self.context = QLabel()
        self.context.setWordWrap(True)
        self.context.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.context)
        form = QFormLayout()
        self.variant = QComboBox()
        form.addRow('Lista i wersja — wariant źródłowy', self.variant)
        self.operation = QComboBox()
        self.operation.addItem('Scal klasy', 'merge')
        self.operation.addItem('Podziel klasę', 'split')
        form.addRow('Operacja', self.operation)
        self.scope = QComboBox()
        for text, key in (('Bieżąca klatka', 'current_frame'), ('Wybrany zakres', 'selected_range'),
                          ('Wszystkie klatki wybranego wyniku tej listy', 'whole_series')):
            self.scope.addItem(text, key)
        self.start, self.end = QSpinBox(), QSpinBox()
        count = manual.controller.series.frame_count if manual.controller.series else 1
        for field in (self.start, self.end):
            field.setRange(1, count)
            field.setValue(manual.controller.current_index + 1)
        ranges = QHBoxLayout()
        ranges.addWidget(self.scope, 1)
        ranges.addWidget(self.start)
        ranges.addWidget(self.end)
        form.addRow('Zakres klatek od / do', ranges)
        self.capture = QPushButton('Ustal / odśwież zakres i wersje')
        self.capture.clicked.connect(self._capture)
        form.addRow(self.capture)
        layout.addLayout(form)
        choices = QHBoxLayout()
        self.sources = QListWidget()
        self.sources.setMaximumHeight(120)
        self.sources.setAccessibleName('Klasy źródłowe')
        choices.addWidget(self.sources, 1)
        target_form = QFormLayout()
        self.target = QComboBox()
        self.name = QLineEdit()
        self.name.setMaxLength(80)
        self.color = QLineEdit('#5cb8ff')
        self.pick_color = QPushButton('Kolor…')
        self.pick_color.clicked.connect(self._pick_color)
        colors = QHBoxLayout()
        colors.addWidget(self.color)
        colors.addWidget(self.pick_color)
        target_form.addRow('Klasa docelowa', self.target)
        target_form.addRow('Nazwa nowej klasy', self.name)
        target_form.addRow('Kolor nowej klasy', colors)
        choices.addLayout(target_form, 2)
        layout.addLayout(choices)
        self.selection_controls = SelectionControls(manual)
        layout.addWidget(self.selection_controls)
        self.selection_mode = QComboBox()
        self.selection_mode.addItem('Zaznaczone molekuły', False)
        self.selection_mode.addItem('Całe wskazane domeny + wybrane punkty bez domeny', True)
        self.remember = QPushButton('Zapamiętaj wskazania bieżącej klatki')
        self.remember.clicked.connect(lambda: self.operations.remember_selection(
            whole_domains=self.selection_mode.currentData()))
        selection = QHBoxLayout()
        selection.addWidget(self.selection_mode)
        selection.addWidget(self.remember)
        layout.addLayout(selection)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.frames = QTableWidget(0, 5)
        self.frames.setHorizontalHeaderLabels(['Klatka', 'Stan / wariant', 'Klasy przed', 'Klasy po', 'Wskazania / domeny'])
        self.frames.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.frames.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.frames.cellDoubleClicked.connect(self._visit)
        layout.addWidget(self.frames, 1)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.message)
        actions = QHBoxLayout()
        self.preview = QPushButton('Pokaż podgląd')
        self.apply = QPushButton('Zastosuj wszystkie klatki')
        self.cancel = QPushButton('Anuluj podgląd')
        self.undo, self.redo = QPushButton('Cofnij'), QPushButton('Ponów')
        for button, callback in ((self.preview, self._preview), (self.apply, self.operations.apply),
                                 (self.cancel, self.operations.cancel_preview),
                                 (self.undo, manual.undo), (self.redo, manual.redo)):
            button.clicked.connect(callback)
            actions.addWidget(button)
        layout.addLayout(actions)
        close = QPushButton('Zamknij')
        close.clicked.connect(self.close)
        layout.addWidget(close)
        for combo in (self.scope, self.variant, self.operation):
            combo.currentIndexChanged.connect(self._scope_changed)
        for field in (self.start, self.end):
            field.valueChanged.connect(self._scope_changed)
        self.sources.itemChanged.connect(self._draft_changed)
        self.target.currentIndexChanged.connect(self._draft_changed)
        self.name.textEdited.connect(self._draft_changed)
        self.color.textEdited.connect(self._draft_changed)
        manual.changed.connect(self.refresh)
        manual.controller.busy_changed.connect(self.refresh)
        self.refresh()

    def choose_operation(self, operation: str) -> None:
        self.operation.setCurrentIndex(self.operation.findData(operation))
        self.refresh()

    def _scope_changed(self, *_: object) -> None:
        self.operations.invalidate('Zakres lub źródło zmienione. Ustal zakres ponownie.')
        self.manual._notify()

    def _draft_changed(self, *_: object) -> None:
        self.operations.cancel_preview()

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.color.text()), self, 'Kolor nowej klasy')
        if color.isValid():
            self.color.setText(color.name())
            self._draft_changed()

    def _capture(self) -> None:
        self.operations.capture(self.scope.currentData(), self.start.value() - 1, self.end.value() - 1,
                                variant_id=self.variant.currentData() or '')

    def _preview(self) -> None:
        self.operations.preview(self.operation.currentData(), sources=self.checked_sources(),
            target=self.target.currentData() or '', name=self.name.text(), color=self.color.text())

    def checked_sources(self) -> tuple[str, ...]:
        return tuple(str(item.data(Qt.ItemDataRole.UserRole)) for i in range(self.sources.count())
                     if (item := self.sources.item(i)) is not None and item.checkState() == Qt.CheckState.Checked)

    def _visit(self, row: int, _column: int) -> None:
        item = self.frames.item(row, 0)
        if item is not None:
            self.manual.controller.show_frame(item.data(Qt.ItemDataRole.UserRole))

    def refresh(self, *_: object) -> None:
        m, op = self.manual, self.operations
        if not m.editing:
            self.hide()
        selected = self.variant.currentData() or (m.active.identifier if m.active else '')
        with QSignalBlocker(self.variant):
            self.variant.clear()
            for key, variant in m.variants.items():
                variant_labels = m.class_lists.get(variant)
                self.variant.addItem(f'Lista {variant_labels.identifier[:8]} · wersja {variant_labels.version[:8]} · '
                                     f'kl. {variant.data.frame.working_index + 1} · wariant {key[:8]}', key)
            self.variant.setCurrentIndex(max(0, self.variant.findData(selected)))
        anchor = m.variants.get(self.variant.currentData())
        labels = op.labels or (m.class_lists.get(anchor) if anchor else None)
        split = self.operation.currentData() == 'split'
        self.selection_controls.setVisible(split)
        count = m.controller.series.frame_count if m.controller.series else 1
        with QSignalBlocker(self.start), QSignalBlocker(self.end):
            self.start.setMaximum(count)
            self.end.setMaximum(count)
        if labels is not None and labels.version != self._labels_version:
            same_list = labels.identifier == self._labels_id
            chosen = set(self.checked_sources()) if same_list else set()
            old_target = self.target.currentData() if same_list else ''
            with QSignalBlocker(self.sources), QSignalBlocker(self.target):
                self.sources.clear()
                self.target.clear()
                self.target.addItem('Nowa klasa ręczna', '')
                for label in labels.classes:
                    item = QListWidgetItem(f'{label.name} (ID {label.class_id.removeprefix("manual-")[:8]})')
                    item.setData(Qt.ItemDataRole.UserRole, label.class_id)
                    item.setForeground(QColor(label.color))
                    item.setCheckState(Qt.CheckState.Checked if label.class_id in chosen else Qt.CheckState.Unchecked)
                    self.sources.addItem(item)
                    self.target.addItem(label.name, label.class_id)
                self.target.setCurrentIndex(max(0, self.target.findData(old_target)))
            self.name.setText(labels.suggested_name)
            self._labels_version = labels.version
            self._labels_id = labels.identifier
        if labels is not None:
            self.name.setPlaceholderText(f'Automatycznie: {labels.suggested_name}')
        if split:
            with QSignalBlocker(self.target):
                self.target.setCurrentIndex(0)
        enabled = m.can_edit and not op.running
        widget: QWidget
        for widget in (self.variant, self.scope, self.operation, self.capture, self.sources):
            widget.setEnabled(enabled)
        self.start.setEnabled(enabled and self.scope.currentData() == 'selected_range')
        self.end.setEnabled(self.start.isEnabled())
        self.target.setEnabled(enabled and not split)
        for widget in (self.name, self.color, self.pick_color):
            widget.setEnabled(enabled and not self.target.currentData())
        existing = next((c for c in labels.classes if c.class_id == self.target.currentData()), None) if labels else None
        if existing is not None:
            self.name.setText(existing.name)
            self.color.setText(existing.color)
        self.selection_mode.setVisible(split)
        self.remember.setVisible(split)
        self.remember.setEnabled(enabled and m.controller.current_index in op.frames and bool(m.selection))
        catalogue = anchor.original.catalogue if anchor and anchor.original else None
        model = f'K modelu: {catalogue.k}' if catalogue else 'Brak modelu'
        effective = op.transaction.after if op.transaction else labels
        present = {a.class_id for i, v in op.frames.items()
                   for a in (op.displayed(i) or v.current).assignments.values() if a.class_id}
        self.context.setText((f'Lista {labels.identifier[:8]} · wersja {labels.version[:8]} · '
                             f'{len(op.frames)} klatek w utrwalonym zakresie.\n'
                             f'{model} · na liście: {len(effective.classes) if effective else 0} · '
                             f'ręczne: {sum(x.origin == "manual" for x in effective.classes) if effective else 0} · '
                             f'obecne w zakresie: {len(present)}. Przypisania zmienią się tylko w zakresie.')
                            if labels else 'Wybierz wariant z listą klas w oknie głównym.')
        if labels:
            self.context.setToolTip(f'Lista: {labels.identifier}\nWersja: {labels.version}\nŹródło: {labels.source_key}')
        self.hint.setText('Podział: zaznacz członków jednej klasy i zapamiętaj wskazania osobno na każdej klatce. '
                         'Dwuklik w tabeli otwiera klatkę. Lasso nie przenosi się między klatkami.' if split else
                         'Scalenie obejmuje wszystkich członków zaznaczonych klas w zakresie. '
                         'Domeny pozostają osobne. Dwuklik w tabeli pokazuje klatkę.')
        self._render_frames()
        self.message.setText(op.message)
        self.preview.setEnabled(enabled and bool(op.frames))
        self.apply.setEnabled(enabled and op.transaction is not None)
        self.cancel.setEnabled(op.running or op.transaction is not None)
        self.undo.setEnabled(enabled and m.history_target() is not None)
        self.redo.setEnabled(enabled and m.history_target(redo=True) is not None)

    def _render_frames(self) -> None:
        op = self.operations
        indices = sorted(set(op.frames) | set(op.skipped))
        self.frames.setRowCount(len(indices))
        labels = op.labels
        revised = op.transaction.after if op.transaction else labels
        def counts(result, names):
            return ', '.join(f'{c.name}={sum(a.class_id == c.class_id for a in result.assignments.values())}'
                             for c in names.classes) if result and names else '—'
        for row, index in enumerate(indices):
            variant = op.frames.get(index)
            before = op.before.get(index)
            after = op.displayed(index)
            domain_text = (f'{len(op.selections.get(index, ()))} wsk.; domeny {before.domain_count}'
                           + (f' → {after.domain_count}' if after else '')) if before else '—'
            sources = self.checked_sources()
            absent = before and sources and not any(a.class_id in sources for a in before.assignments.values())
            state = ('Bez członków wybranych klas' if absent else f'Wariant {variant.identifier[:8]}') if variant else 'Pominięta: ' + op.skipped[index]
            texts = (str(index + 1), state,
                     counts(before, labels), counts(after, revised), domain_text)
            for column, value in enumerate(texts):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, index)
                item.setToolTip(value + ('\n' + ', '.join(op.selections[index]) if column == 4 and index in op.selections else ''))
                self.frames.setItem(row, column, item)
        self.frames.resizeColumnsToContents()

    def closeEvent(self, event: QCloseEvent | None) -> None:
        self.operations.cancel_preview()
        super().closeEvent(event)
