"""Bounded per-frame run display shared by single-frame and series analysis."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem

from stmdomains.ui.series_runner import FrameRunStatus, SeriesRun

STATUS_TEXT = {"pending": "Oczekuje", "analysing": "Obliczanie", "not_run": "Niewykonana",
               "complete": "Gotowe", "no_annotations": "Brak oznaczeń",
               "insufficient_data": "Za mało danych", "error": "Błąd"}


class AnalysisStatuses(QTableWidget):
    frame_requested = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__(0, 4)
        self._rows: tuple[int, ...] = ()
        self._shown: dict[int, FrameRunStatus] = {}
        self.setHorizontalHeaderLabels(["Klatka", "Stan tego przebiegu", "Przypisano", "Domeny"])
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setMinimumHeight(80)
        self.setMaximumHeight(100)
        self.setToolTip("Dwukrotnie kliknij wiersz, aby przejść do klatki. Szczegóły stanu są w podpowiedzi.")
        header = self.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cellDoubleClicked.connect(self._show_row)

    def _show_row(self, row: int, column: int) -> None:
        if 0 <= row < len(self._rows):
            self.frame_requested.emit(self._rows[row])

    def refresh(self, run: SeriesRun | None) -> None:
        indices = run.indices if run else ()
        if indices != self._rows:
            self._rows = indices
            self._shown.clear()
            self.setRowCount(len(indices))
        if run is None:
            return
        for row, index in enumerate(indices):
            status = run.frames[index]
            if self._shown.get(index) is status:
                continue
            self._shown[index] = status
            values = (str(index + 1), STATUS_TEXT[status.status],
                      f"{status.assigned}/{status.active}" if status.status == "complete" else "—",
                      str(status.domains) if status.status == "complete" else "—")
            for column, value in enumerate(values):
                item = self.item(row, column)
                if item is None:
                    item = QTableWidgetItem()
                    self.setItem(row, column, item)
                item.setText(value)
                item.setToolTip(status.message)
