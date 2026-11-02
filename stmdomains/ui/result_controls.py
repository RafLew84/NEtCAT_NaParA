"""Compact, stable-height controls and legend for one published result frame."""

from html import escape

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from stmdomains.core.frame_presentation import PresentedFrame
from stmdomains.ui.result_style import describe_result


class ResultControls(QWidget):
    mode_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._frame: PresentedFrame | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        row = QHBoxLayout()
        row.addWidget(QLabel("Kolory:"))
        self.mode = QComboBox()
        self.mode.setObjectName("assignmentMode")
        self.mode.addItem("Domeny (lokalne)", "domains")
        self.mode.addItem("Klasy (końcowe)", "classes")
        self.mode.addItem("Oznaczenia wejściowe", "input")
        self.mode.setEnabled(False)
        row.addWidget(self.mode)
        self.summary = QLabel()
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        row.addWidget(self.summary, 1)
        self.details_button = QPushButton("Dane wyniku…")
        self.details_button.setEnabled(False)
        row.addWidget(self.details_button)
        layout.addLayout(row)
        self.legend = QLabel()
        self.legend.setTextFormat(Qt.TextFormat.RichText)
        self.legend.setContentsMargins(2, 0, 2, 0)
        self.legend_scroll = QScrollArea()
        self.legend_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.legend_scroll.setWidget(self.legend)
        self.legend_scroll.setWidgetResizable(True)
        self.legend_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.legend_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scrollbar = self.legend_scroll.horizontalScrollBar()
        scrollbar_height = scrollbar.sizeHint().height() if scrollbar is not None else 0
        self.legend_scroll.setFixedHeight(self.legend.fontMetrics().height() + scrollbar_height + 6)
        layout.addWidget(self.legend_scroll)
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
