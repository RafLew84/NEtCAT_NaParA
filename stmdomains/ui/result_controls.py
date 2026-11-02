"""A stable, single-row result selector, count and scrollable colour legend."""

from html import escape

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QWidget,
)

from stmdomains.core.frame_presentation import PresentedFrame
from stmdomains.ui.result_style import describe_result
from stmdomains.ui.domain_controls import DomainControls


class ResultControls(QWidget):
    mode_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._frame: PresentedFrame | None = None
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.mode = QComboBox()
        self.mode.setObjectName("assignmentMode")
        self.mode.addItem("Domeny", "domains")
        self.mode.addItem("Klasy", "classes")
        self.mode.addItem("Wejściowe", "input")
        self.mode.setEnabled(False)
        row.addWidget(self.mode)
        self.summary = QLabel()
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        row.addWidget(self.summary)
        self.legend = QLabel()
        self.legend.setTextFormat(Qt.TextFormat.RichText)
        self.legend.setContentsMargins(2, 0, 2, 0)
        self.legend_scroll = QScrollArea()
        self.legend_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.legend_scroll.setWidget(self.legend)
        self.legend_scroll.setWidgetResizable(True)
        self.legend_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.legend_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.legend_scroll.setMinimumWidth(60)
        scrollbar = self.legend_scroll.horizontalScrollBar()
        scrollbar_height = scrollbar.sizeHint().height() if scrollbar is not None else 0
        self.legend_scroll.setFixedHeight(self.legend.fontMetrics().height() + scrollbar_height + 4)
        row.addWidget(self.legend_scroll, 1)
        self.regions = DomainControls(self)
        row.addWidget(self.regions)
        self.details_button = QPushButton("Dane…")
        self.details_button.setToolTip("Ustawienia i pochodzenie wyniku tej klatki")
        self.details_button.setEnabled(False)
        row.addWidget(self.details_button)
        self.mode.currentIndexChanged.connect(self._change_mode)
        self._render()
        self.setFixedHeight(self.sizeHint().height())

    def set_frame(self, view: PresentedFrame) -> None:
        self._frame = view
        self.mode.setEnabled(view.result is not None)
        self.details_button.setEnabled(view.result is not None)
        self._render()

    def _change_mode(self) -> None:
        self._render()
        self.mode_changed.emit(self.mode.currentData())

    def _render(self) -> None:
        result = self._frame.result if self._frame is not None else None
        description = describe_result(result, self.mode.currentData())
        self.regions.set_available(result, self.mode.currentData())
        self.summary.setText(description.summary)
        self.summary.setToolTip(description.summary + "\n" + description.note)
        self.mode.setToolTip(description.note)
        self.legend.setText(" &nbsp; · &nbsp; ".join(
            f'<span style="color: {escape(item.color)}">●</span> '
            f"{escape(item.label)}: {item.count}"
            for item in description.legend
        ) or escape(description.note))
        self.legend.setToolTip("\n".join(
            [description.note, *(f"{item.label}: {item.count}" for item in description.legend)]
        ))
        self.legend.setMinimumWidth(self.legend.sizeHint().width())
