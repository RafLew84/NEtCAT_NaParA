"""Saved point support, displayed independently of model execution and movie pixels."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QResizeEvent
from PyQt6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QSizePolicy,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from stmviewer.correspondence_types import CorrespondenceDiagnostics


def correspondence_details_text(details: CorrespondenceDiagnostics) -> str:
    outcome = ('Odmowa dopasowania — brak nowego wyniku pary.' if details.final_shift_xy is None
               else f'Przesunięcie: X {details.final_shift_xy[0]:.3f} · Y {details.final_shift_xy[1]:.3f} px')
    residual = 'brak' if details.median_residual_px is None else f'{details.median_residual_px:.3f} px'
    return (f'{outcome}\nZgodne punkty: {details.inlier_count} / {details.valid_count}; '
            f'wyjście modelu: {details.input_count}.\n'
            f'Rozrzut zgodnych przesunięć (mediana): {residual}.\n'
            f'Zasięg X/Y — bazowa: {details.reference_span_xy[0]:.0%} / '
            f'{details.reference_span_xy[1]:.0%}; przesuwana: '
            f'{details.moving_span_xy[0]:.0%} / {details.moving_span_xy[1]:.0%}.\n'
            f'{details.reason}\nPoparcie estymatora, bez niezależnej oceny jakości. '
            'Liczba punktów nie jest prawdopodobieństwem poprawnego dryfu.')


class CorrespondenceDetails(QWidget):
    """Two 4×4 counts grids preserve the spatial meaning of original-image evidence."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._details: CorrespondenceDiagnostics | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._summary = QLabel(self)
        self._summary.setObjectName('pairCorrespondenceDetails')
        self._summary.setWordWrap(True)
        self._summary.setTextFormat(Qt.TextFormat.PlainText)
        self._summary.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._summary)
        self._legend = QLabel('Zgodne punkty w siatce 4 × 4 oryginału. '
                              'Góra siatki odpowiada górze obrazu.', self)
        self._legend.setWordWrap(True)
        self._legend.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._legend)
        grids = QHBoxLayout()
        layout.addLayout(grids)
        self._grids: list[QTableWidget] = []
        for name, title in (('Reference', 'Bazowa'), ('Moving', 'Przesuwana')):
            column = QVBoxLayout()
            column.addWidget(QLabel(title, self))
            table = QTableWidget(4, 4, self)
            table.setObjectName(f'correspondence{name}Support')
            table.setAccessibleName(f'Rozkład zgodnych punktów: klatka {title.lower()}')
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
            table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            for header in (table.verticalHeader(), table.horizontalHeader()):
                assert header is not None
                header.hide()
                header.setMinimumSectionSize(20)
                header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setFixedHeight(116)
            table.setMinimumWidth(108)
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            column.addWidget(table)
            grids.addLayout(column)
            self._grids.append(table)
        self.hide()

    def set_details(self, details: CorrespondenceDiagnostics | None) -> None:
        self.setVisible(details is not None)
        if details is self._details:
            return
        self._details = details
        self._summary.setText(correspondence_details_text(details) if details else '')
        if details is not None:
            for table, counts in zip(self._grids, (details.reference_support, details.moving_support)):
                maximum = max(max(counts), 1)
                for index, count in enumerate(counts):
                    row, column = divmod(index, 4)
                    item = QTableWidgetItem(str(count))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setBackground(QColor(245 - int(105 * count / maximum), 250, 245 - int(75 * count / maximum)))
                    item.setForeground(QColor('black'))
                    item.setToolTip(f'X: {column * 25}–{(column + 1) * 25}%; '
                                    f'Y: {row * 25}–{(row + 1) * 25}%; zgodne punkty: {count}.')
                    table.setItem(row, column, item)
        self._resize_labels()

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        super().resizeEvent(event)
        self._resize_labels()

    def _resize_labels(self) -> None:
        for label in (self._summary, self._legend):
            label.setMinimumHeight(max(0, label.heightForWidth(max(1, self.width()))))
