"""Modeless class editor: shared label metadata, current-frame assignments."""

from PyQt6.QtCore import QSignalBlocker, Qt
from PyQt6.QtGui import QColor, QCloseEvent, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QColorDialog, QComboBox, QDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from stmdomains.ui.manual_controller import ManualController
from stmdomains.ui.class_operation_dialog import ClassOperationDialog


class ManualClassDialog(QDialog):
    def __init__(self, manual: ManualController, parent: QWidget) -> None:
        super().__init__(parent)
        self.manual = manual
        self._context: tuple[object, ...] = ()
        self.operations_dialog: ClassOperationDialog | None = None
        self.setWindowTitle('Klasy ręczne — bieżąca klatka')
        self.resize(620, 680)
        layout = QVBoxLayout(self)
        self.scope = QLabel()
        self.scope.setWordWrap(True)
        layout.addWidget(self.scope)
        grouping = QHBoxLayout()
        self.merge_classes = QPushButton('Scal klasy…')
        self.split_class = QPushButton('Podziel klasę…')
        for button, operation in ((self.merge_classes, 'merge'), (self.split_class, 'split')):
            button.clicked.connect(lambda checked=False, op=operation: self._show_operation(op))
            grouping.addWidget(button)
        layout.addLayout(grouping)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['Nazwa', 'Pochodzenie', 'Na klatce', 'Bez domeny'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setMaximumHeight(145)
        self.table.cellClicked.connect(self._select_row)
        layout.addWidget(self.table)
        form = QFormLayout()
        self.target = QComboBox()
        self.name = QLineEdit()
        self.name.setMaxLength(80)
        self.color = QLineEdit('#5cb8ff')
        self.pick_color = QPushButton('Wybierz kolor…')
        self.pick_color.clicked.connect(self._pick_color)
        colors = QHBoxLayout()
        colors.addWidget(self.color)
        colors.addWidget(self.pick_color)
        form.addRow('Klasa docelowa', self.target)
        form.addRow('Nazwa', self.name)
        form.addRow('Kolor', colors)
        layout.addLayout(form)
        metadata = QHBoxLayout()
        self.create_button = QPushButton('Nowa pusta — podgląd')
        self.update_button = QPushButton('Nazwa/kolor — podgląd')
        self.delete = QPushButton('Usuń pustą — podgląd')
        for button, operation in ((self.create_button, 'create'), (self.update_button, 'update'), (self.delete, 'delete')):
            button.clicked.connect(lambda checked=False, op=operation: self._preview(op))
            metadata.addWidget(button)
        layout.addLayout(metadata)
        self.selection = QLabel()
        self.selection.setWordWrap(True)
        layout.addWidget(self.selection)
        self.assignment_scope = QComboBox()
        self.assignment_scope.addItem('Tylko zaznaczone molekuły (część domeny zostanie wydzielona)', False)
        self.assignment_scope.addItem('Całe domeny wskazane przez zaznaczone molekuły', True)
        layout.addWidget(self.assignment_scope)
        assignments = QHBoxLayout()
        self.assign = QPushButton('Przypisz wybraną — podgląd')
        self.create_assign = QPushButton('Nowa klasa i przypisanie — podgląd')
        self.assign.clicked.connect(lambda: self._preview('assign'))
        self.create_assign.clicked.connect(lambda: self._preview('create_assign'))
        assignments.addWidget(self.assign)
        assignments.addWidget(self.create_assign)
        layout.addLayout(assignments)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.compare = QCheckBox('Automatyczny przed korektą')
        self.compare.toggled.connect(manual.set_comparison)
        layout.addWidget(self.compare)
        actions = QHBoxLayout()
        self.apply = QPushButton('Zastosuj')
        self.cancel = QPushButton('Anuluj podgląd')
        self.undo = QPushButton('Cofnij')
        self.redo = QPushButton('Ponów')
        for button, callback in ((self.apply, manual.apply), (self.cancel, manual.cancel_preview),
                                 (self.undo, manual.undo), (self.redo, manual.redo)):
            button.clicked.connect(callback)
            actions.addWidget(button)
        layout.addLayout(actions)
        note = QLabel('Zaznaczaj molekuły w głównym oknie. Nazwa nie potwierdza typu fizycznego. '
                      'Korekty tylko w sesji; model nie jest douczany.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.target.currentIndexChanged.connect(self._target_changed)
        for field in (self.name, self.color):
            field.textEdited.connect(manual.cancel_preview)
        self.assignment_scope.currentIndexChanged.connect(manual.cancel_preview)
        manual.changed.connect(self.refresh)
        manual.controller.busy_changed.connect(self.refresh)
        self.refresh()

    def _preview(self, operation: str) -> None:
        self.manual.preview_classes(operation, target=self.target.currentData() or '',
            name=self.name.text(), color=self.color.text(), whole_domains=self.assignment_scope.currentData())

    def _show_operation(self, operation: str) -> None:
        self.manual.cancel_preview()
        if self.operations_dialog is None:
            self.operations_dialog = ClassOperationDialog(self.manual, self)
        self.operations_dialog.choose_operation(operation)
        self.hide()
        self.operations_dialog.show()
        self.operations_dialog.raise_()

    def _select_row(self, row: int, column: int) -> None:
        item = self.table.item(row, 0)
        if item is not None:
            self.target.setCurrentIndex(self.target.findData(item.data(Qt.ItemDataRole.UserRole)))

    def _target_changed(self) -> None:
        labels = self.manual.class_list
        label = next((c for c in labels.classes if c.class_id == self.target.currentData()), None) if labels else None
        self.name.setText(label.name if label else '')
        self.color.setText(label.color if label else '#5cb8ff')
        self.manual.cancel_preview()

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.color.text()), self, 'Kolor klasy')
        if color.isValid():
            self.color.setText(color.name())
            self.manual.cancel_preview()

    def refresh(self, *_: object) -> None:
        manual, labels = self.manual, self.manual.class_list
        if not manual.editing:
            self.hide()
        if labels is None or manual.active is None:
            self.setEnabled(False)
            return
        self.setEnabled(True)
        self.name.setPlaceholderText(f'Nowa klasa: automatycznie {labels.suggested_name}')
        self.name.setToolTip('Przy tworzeniu klasy puste pole nada kolejną wolną literę. '
                             'Zmiana nazwy istniejącej klasy wymaga wpisania nazwy.')
        frame = manual.controller.current_index
        context = labels.identifier, labels.version, frame
        active = manual.active
        if context != self._context:
            old_id = self._context[0] if self._context else None
            old_keys = {self.target.itemData(i) for i in range(self.target.count())}
            target = self.target.currentData() if old_id == labels.identifier else ''
            added = [c.class_id for c in labels.classes if c.class_id not in old_keys and c.origin == 'manual']
            if old_id == labels.identifier and added:
                target = added[-1]
            with QSignalBlocker(self.target):
                self.target.clear()
                self.target.addItem('Nieustalona — usuń przypisanie klasy', '')
                for c in labels.classes:
                    identity = c.class_id.removeprefix('manual-')[:8]
                    self.target.addItem(f'{c.name} (ID {identity})', c.class_id)
                    self.target.setItemData(self.target.count() - 1, c.class_id, Qt.ItemDataRole.ToolTipRole)
                self.target.setCurrentIndex(max(0, self.target.findData(target)))
            label = next((c for c in labels.classes if c.class_id == target), None)
            self.name.setText(label.name if label else '')
            self.color.setText(label.color if label else '#5cb8ff')
            self._context = context
        shown_labels = (manual.preview_result.class_list if manual.preview_result is not None else None) or labels
        if manual.compare_original:
            shown_labels = manual.original_class_list or labels
        result = manual.displayed_result(manual.controller.result)
        assignments = result.assignments.values() if result else ()
        classes = shown_labels.classes
        counts = {c.class_id: sum(a.class_id == c.class_id for a in assignments) for c in classes}
        no_domain = {c.class_id: sum(a.class_id == c.class_id and not a.domain_local_id
                                   for a in assignments) for c in classes}
        self.table.setRowCount(len(classes))
        for row, c in enumerate(classes):
            for column, text in enumerate((c.name, 'ręczne' if c.origin == 'manual' else 'automatyczne',
                                           str(counts[c.class_id]), str(no_domain[c.class_id]))):
                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, c.class_id)
                item.setToolTip(f'ID: {c.class_id}\nKolor: {c.color}')
                if column == 0:
                    swatch = QPixmap(14, 14)
                    swatch.fill(QColor(c.color))
                    item.setIcon(QIcon(swatch))
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        catalogue = active.original.catalogue if active.original else None
        model = f'K modelu: {catalogue.k} · katalog {catalogue.identifier[:8]}' if catalogue else 'Brak dopasowanego modelu'
        scope = ('wspólny katalog' if catalogue else
                 'ręczna praca bez analizy' if active.original is None else 'lokalny wynik bez katalogu')
        frames = [index + 1 for index in manual.class_scope_frames]
        frames_text = ', '.join(map(str, frames[:8])) + (f'… ({len(frames)} klatek)' if len(frames) > 8 else '')
        prefix = 'Oryginał · ' if manual.compare_original else 'Podgląd · ' if manual.preview_result else ''
        self.scope.setText(f'{prefix}Lista {shown_labels.identifier[:8]} · wersja {shown_labels.version[:8]} · {scope}\n'
            f'{model} · ręczne: {sum(c.origin == "manual" for c in classes)} · obecne na klatce: '
            f'{sum(n > 0 for n in counts.values())}\n'
            f'Warianty korzystające z listy: kl. {frames_text}. Nazwy i kolory są wspólne.')
        self.scope.setToolTip(f'Lista: {shown_labels.identifier}\nWersja: {shown_labels.version}\nŹródło: {labels.source_key}')
        self.selection.setText(f'Klatka {frame + 1} · zaznaczono {len(manual.selection)} molekuł. '
                               'Przypisania zmienią się tylko w tej klatce.')
        self.message.setText(manual.message or 'Wybierz operację i obejrzyj podgląd przed zastosowaniem.')
        with QSignalBlocker(self.compare):
            self.compare.setChecked(manual.compare_original)
        self.compare.setEnabled(not manual.controller.is_busy)
        self.merge_classes.setEnabled(manual.can_edit and len(labels.classes) >= 2)
        self.split_class.setEnabled(manual.can_edit and bool(labels.classes))
        for widget in (self.target, self.name, self.color, self.pick_color, self.assignment_scope, self.create_button):
            widget.setEnabled(manual.can_edit)
        target_label = next((c for c in labels.classes if c.class_id == self.target.currentData()), None)
        self.update_button.setEnabled(manual.can_edit and target_label is not None)
        self.delete.setEnabled(manual.can_edit and target_label is not None and target_label.origin == 'manual'
                               and manual.class_member_count(target_label.class_id) == 0)
        self.delete.setToolTip('Tylko ręczna klasa bez członków we wszystkich wariantach tej listy.')
        for button in (self.assign, self.create_assign):
            button.setEnabled(manual.can_edit and bool(manual.selection))
        self.apply.setEnabled(manual.can_edit and manual.preview_result is not None)
        self.cancel.setEnabled(manual.preview_result is not None)
        for button, redo in ((self.undo, False), (self.redo, True)):
            button.setEnabled(manual.can_edit and manual.history_target(redo=redo) is not None)
            button.setToolTip(manual.history_label(redo=redo))

    def closeEvent(self, event: QCloseEvent | None) -> None:
        if self.operations_dialog is not None:
            self.operations_dialog.close()
        result = self.manual.preview_result
        if result is not None and result.metadata.get('manual_edit', {}).get('operation', '').startswith('class_'):
            self.manual.cancel_preview()
        super().closeEvent(event)
