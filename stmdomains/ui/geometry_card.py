"""Layout C: a bounded floating measurement card, without reflowing the viewer."""

import json
from dataclasses import asdict
from stmdomains.core.immutable import plain_metadata
from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton,
                            QScrollArea, QTabBar, QVBoxLayout, QWidget, QDialog, QPlainTextEdit, QSizePolicy, QLayout)
from stmdomains.core.frame_presentation import PresentedFrame
from stmdomains.ui.geometry_text import geometry_text


class GeometryCard(QFrame):
    def __init__(self, controller, image_view) -> None:
        super().__init__(image_view.viewport())
        self.setObjectName('geometryCard')
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAutoFillBackground(True)
        self.controller, self.image_view = controller, image_view
        self.view: PresentedFrame | None = None
        self.selected_id: str | None = None
        self.on_right = True
        self.folded = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        header = QHBoxLayout()
        self.title = QLabel('Geometria')
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.title.setMinimumWidth(0)
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.side = QPushButton('⇄')
        self.side.setToolTip('Przenieś kartę na drugą stronę obrazu')
        self.side.setFixedWidth(32)
        self.collapse = QPushButton('Zwiń')
        self.collapse.setFixedWidth(66)
        self.close_button = QPushButton('×')
        self.close_button.setToolTip('Ukryj kartę i nakładkę geometrii')
        self.close_button.setFixedWidth(26)
        header.addWidget(self.title, 1)
        for button in (self.side, self.collapse, self.close_button):
            header.addWidget(button)
        layout.addLayout(header)
        self.body = QWidget()
        body_layout = QVBoxLayout(self.body)
        body_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        body_layout.setContentsMargins(0, 0, 0, 0)
        actions = QHBoxLayout()
        self.measure = QPushButton('Pomierz geometrię')
        self.measure.setObjectName('measureGeometry')
        self.cancel = QPushButton('Anuluj')
        actions.addWidget(self.measure, 1)
        actions.addWidget(self.cancel)
        body_layout.addLayout(actions)
        self.progress = QLabel('Gotowe')
        self.progress.setTextFormat(Qt.TextFormat.PlainText)
        self.progress.setFixedHeight(self.progress.fontMetrics().height()+4)
        body_layout.addWidget(self.progress)
        self.tabs = QTabBar()
        self.tabs.addTab('Molekuła')
        self.tabs.addTab('Domena')
        body_layout.addWidget(self.tabs)
        self.details = QLabel()
        self.details.setTextFormat(Qt.TextFormat.RichText)
        self.details.setWordWrap(True)
        self.details.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.details.setMargin(6)
        self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body_layout.addWidget(self.details, 1)
        self.directions = QCheckBox('Kierunki rzędów')
        self.directions.setChecked(True)
        self.all_points = QCheckBox('Wszystkie molekuły')
        self.neighborhood = QCheckBox('Otoczenie wybranej molekuły')
        self.neighborhood.setChecked(True)
        for check in (self.directions, self.all_points, self.neighborhood):
            body_layout.addWidget(check)
            check.toggled.connect(self._layers)
        self.data_button = QPushButton('Dane i ustawienia pomiaru…')
        self.data_button.clicked.connect(self._show_data)
        body_layout.addWidget(self.data_button)
        note = QLabel('Pomiary w tej sesji. Zapis projektu i eksport domen nie obejmują geometrii.')
        note.setWordWrap(True)
        note.setStyleSheet('color: #b5a980;')
        body_layout.addWidget(note)
        self.body_scroll = QScrollArea()
        self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setWidget(self.body)
        layout.addWidget(self.body_scroll, 1)
        self.measure.clicked.connect(controller.measure_current_geometry)
        self.cancel.clicked.connect(controller.cancel)
        self.side.clicked.connect(self._move_side)
        self.collapse.clicked.connect(self._fold)
        self.close_button.clicked.connect(self._hide)
        self.tabs.currentChanged.connect(self.refresh)
        controller.busy_changed.connect(self._busy)
        parent = self.parentWidget()
        if parent is not None:
            parent.installEventFilter(self)
        self.hide()
        self.refresh()

    def open(self) -> None:
        self.controller.pause()
        self.show()
        self.raise_()
        self._position()
        self._layers()
        self._busy(self.controller.is_busy, 'Gotowe' if not self.controller.is_busy else 'Trwa zadanie…')

    def _hide(self) -> None:
        self.hide()
        self._layers()

    def set_frame(self, view: PresentedFrame) -> None:
        same = self.view and (self.view.series_id, self.view.frame.working_index) == (view.series_id, view.frame.working_index)
        if not same:
            self.selected_id = None
        self.view = view
        self.refresh()

    def select(self, selected) -> None:
        self.selected_id = getattr(selected, 'detection_id', None)
        self.refresh()

    def refresh(self) -> None:
        self.title.setText(self.selected_id or 'Geometria')
        self.title.setToolTip(self.selected_id or 'Pomiar geometrii bieżącej klatki')
        self.details.setText(geometry_text(self.view, self.selected_id, self.tabs.currentIndex() == 1))
        self.data_button.setEnabled(self.view is not None and self.view.geometry is not None)
        self._position()
        self._layers()

    def _layers(self) -> None:
        overlay = self.image_view.geometry_overlay
        overlay.selected_id = self.selected_id
        overlay.show_all = self.all_points.isChecked()
        overlay.show_neighborhood = self.neighborhood.isChecked()
        overlay.setVisible(self.isVisible() and self.directions.isChecked())
        overlay.update()

    def _show_data(self) -> None:
        if self.view is None or self.view.geometry is None:
            return
        geometry = self.view.geometry
        payload = {'series_id': geometry.series_id, 'working_index': geometry.working_index,
                   'source_index': geometry.source_index, 'calibration': asdict(geometry.calibration),
                   'parameters': plain_metadata(geometry.parameters), 'metadata': plain_metadata(geometry.metadata),
                   'molecules': {key: asdict(value) for key, value in geometry.molecules.items()}}
        dialog = QDialog(self)
        dialog.setWindowTitle('Pomiary geometrii — dane i pochodzenie (indeksy od 0)')
        dialog.resize(680, 480)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit(json.dumps(payload, ensure_ascii=False, indent=2))
        text.setReadOnly(True)
        layout.addWidget(text)
        close = QPushButton('Zamknij')
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def _busy(self, busy: bool, text: str) -> None:
        self.measure.setEnabled(self.controller.can_analyze)
        self.cancel.setEnabled(self.controller.geometry_running)
        self.progress.setText(text)
        self.progress.setToolTip(text)

    def _move_side(self) -> None:
        self.on_right = not self.on_right
        self._position()

    def _fold(self) -> None:
        self.folded = not self.folded
        self.body_scroll.setVisible(not self.folded)
        self.collapse.setText('Rozwiń' if self.folded else 'Zwiń')
        self._position()

    def _position(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        width = max(180, min(360, parent.width()-16))
        height = 42 if self.folded else min(560, max(150, parent.height()-16))
        self.setGeometry(max(8, parent.width()-width-8) if self.on_right else 8, 8, width, height)
        # A word-wrapped QLabel otherwise advertises only its minimum line
        # height inside a scrollable layout and silently clips the remaining text.
        self.details.setMinimumHeight(self.details.heightForWidth(max(80, width-64)))

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:
        if event is not None and event.type() == QEvent.Type.Resize:
            self._position()
        return super().eventFilter(watched, event)
