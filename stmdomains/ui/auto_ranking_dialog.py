"""Read-only explanation of the actual Auto run, including explicit refusals."""

from collections.abc import Mapping
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QDialog, QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from stmdomains.core.class_catalogue import ClassCatalogue


def selection_summary(selection: Mapping[str, Any] | None) -> str:
    if not selection:
        return "Brak wyboru Auto."
    k = selection["selected_k"]
    return (f"K{k}. " if k is not None else "") + str(selection["reason"])


class AutoRankingDialog(QDialog):
    def __init__(self, selection: Mapping[str, Any], catalogue: ClassCatalogue | None, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("autoRankingDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Auto — ranking ostatniego przebiegu")
        self.resize(820, 420)
        layout = QVBoxLayout(self)
        summary = QLabel(selection_summary(selection))
        summary.setWordWrap(True)
        layout.addWidget(summary)
        frames = catalogue.frame_indices if catalogue else selection.get("fit_working_indices", ())
        scope = f"klatki {frames[0] + 1}–{frames[-1] + 1}" if frames else "bieżące wejście"
        counts = QLabel(
            f"{scope} · użyteczne {selection['useful_count']}/{selection['active_count']} "
            f"({selection['useful_fraction']:.1%}); dopasowanie {selection['fit_count']}; "
            f"ranking {selection['ranking_count']} (limit 1200).\n"
            f"{selection['rule_version']} · K1…{selection['max_k']} · ziarno {selection['seed']}. "
            "Silhouette dotyczy podzbioru; K1 ma osobne kryterium zwartości.")
        counts.setWordWrap(True)
        layout.addWidget(counts)
        ranking = selection["ranking"]
        self.table = QTableWidget(len(ranking), 7)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setHorizontalHeaderLabels(["K", "Silhouette", "Min. grupa", "Promień 95%", "Rozdzielenie", "Dopuszczalny", "Powód"])
        for row, candidate in enumerate(ranking):
            def number(value: float | None) -> str:
                return "—" if value is None else f"{value:.3f}"
            values = (str(candidate["k"]), number(candidate["silhouette"]),
                      str(min(candidate["sizes"])) if candidate["sizes"] else "—",
                      number(max(candidate["radius95"])) if candidate["radius95"] else "—",
                      number(candidate["separation"]), "Tak" if candidate["eligible"] else "Nie", candidate["reason"])
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.table.setItem(row, column, item)
        header = self.table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            header.setStretchLastSection(True)
        layout.addWidget(self.table, 1)
        note = QLabel("Auto może odmówić wyboru. To ograniczona reguła opisów otoczeń, nie liczba fizycznych faz. "
                      "Małe grupy mogą zostać pominięte; zakres i progi porządku wpływają na wynik. "
                      "Edycja parametrów wymaga ponownego Analizuj.")
        note.setWordWrap(True)
        layout.addWidget(note)
        close = QPushButton("Zamknij")
        close.clicked.connect(self.close)
        layout.addWidget(close)
