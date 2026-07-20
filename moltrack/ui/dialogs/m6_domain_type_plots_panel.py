from __future__ import annotations

from collections import defaultdict

import pyqtgraph as pg

from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis import M6DomainTypeAnalysisOutcome

from .m6_domain_type_plot_data import (
    M6_DOMAIN_TYPE_SHARE_METRICS,
    M6DomainTypeScatterData,
    M6DomainTypeSharePlotData,
    build_m6_domain_type_scatter_data,
    build_m6_domain_type_share_plot_data,
)


class M6DomainTypePlotsPanel(QWidget):
    """Scatter and share plots for one current structural-type outcome."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._outcome: M6DomainTypeAnalysisOutcome | None = None
        self._scatter_data: M6DomainTypeScatterData | None = None
        self._share_data: M6DomainTypeSharePlotData | None = None
        self._scatter_items = []
        self._scatter_legend_items = []
        self._scatter_legend_labels: tuple[str, ...] = ()
        self._share_legend_labels: tuple[str, ...] = ()
        self._empty_message = "Classify domain types to show plots."

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scatter_group = QGroupBox("Domain type separation", self)
        scatter_layout = QVBoxLayout(scatter_group)
        self.scatter_plot = pg.PlotWidget(scatter_group)
        self.scatter_plot.setBackground("w")
        self.scatter_plot.showGrid(x=True, y=True, alpha=0.2)
        self.scatter_plot.setLabel("bottom", "M6 orientation [deg]")
        self.scatter_plot.setLabel("left", "Median bond length [nm]")
        self.scatter_plot.setXRange(0.0, 60.0, padding=0.0)
        self.scatter_plot.setMinimumHeight(280)
        self.scatter_legend = self.scatter_plot.addLegend()
        scatter_layout.addWidget(self.scatter_plot)
        layout.addWidget(scatter_group)

        share_group = QGroupBox("Domain type shares", self)
        share_layout = QVBoxLayout(share_group)
        metric_form = QFormLayout()
        self.metric_combo = QComboBox(share_group)
        for metric in M6_DOMAIN_TYPE_SHARE_METRICS:
            self.metric_combo.addItem(metric.label, metric.key)
        metric_form.addRow("Metric", self.metric_combo)
        share_layout.addLayout(metric_form)
        self.share_plot = pg.PlotWidget(share_group)
        self.share_plot.setBackground("w")
        self.share_plot.showGrid(x=False, y=True, alpha=0.2)
        self.share_plot.setLabel("bottom", "Structural type")
        self.share_plot.setLabel("left", "Instances/frame")
        self.share_plot.setMinimumHeight(260)
        self.share_legend = self.share_plot.addLegend()
        self.first_bars = pg.BarGraphItem(x=[], height=[], width=0.7)
        self.second_bars = pg.BarGraphItem(x=[], height=[], width=0.35)
        self.share_plot.addItem(self.first_bars)
        self.share_plot.addItem(self.second_bars)
        share_layout.addWidget(self.share_plot)
        layout.addWidget(share_group)

        self.status_label = QLabel(self._empty_message, self)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.metric_combo.currentIndexChanged.connect(self._refresh_share_plot)
        self._clear_plots()

    def set_outcome(
        self,
        outcome: M6DomainTypeAnalysisOutcome | None,
        *,
        empty_message: str = "Classify domain types to show plots.",
    ) -> None:
        if outcome is not None and not isinstance(
            outcome,
            M6DomainTypeAnalysisOutcome,
        ):
            raise TypeError("outcome must be an M6 domain type outcome or None.")
        self._outcome = outcome
        self._empty_message = str(empty_message)
        if (
            outcome is None
            or outcome.classification is None
            or outcome.table_result is None
        ):
            self._scatter_data = None
            self._share_data = None
            self._clear_plots()
            self.status_label.setText(
                outcome.status_message if outcome is not None else self._empty_message
            )
            return
        self._scatter_data = build_m6_domain_type_scatter_data(
            outcome.classification
        )
        self._render_scatter()
        self._refresh_share_plot()
        self._refresh_status()

    def outcome(self) -> M6DomainTypeAnalysisOutcome | None:
        return self._outcome

    def scatter_data(self) -> M6DomainTypeScatterData | None:
        return self._scatter_data

    def share_data(self) -> M6DomainTypeSharePlotData | None:
        return self._share_data

    def metric_labels(self) -> tuple[str, ...]:
        return tuple(
            self.metric_combo.itemText(index)
            for index in range(self.metric_combo.count())
        )

    def set_metric(self, metric: str) -> None:
        index = self.metric_combo.findData(str(metric))
        if index < 0:
            raise ValueError(f"Unsupported domain type share metric: {metric!r}.")
        self.metric_combo.setCurrentIndex(index)

    def current_metric(self) -> str:
        return str(self.metric_combo.currentData())

    def scatter_axis_labels(self) -> tuple[str, str]:
        return ("M6 orientation [deg]", "Median bond length [nm]")

    def share_axis_label(self) -> str:
        if self._share_data is not None:
            return self._share_data.axis_label
        return self.share_plot.getAxis("left").labelText

    def scatter_point_count(self) -> int:
        return 0 if self._scatter_data is None else len(self._scatter_data.points)

    def scatter_legend_labels(self) -> tuple[str, ...]:
        return self._scatter_legend_labels

    def share_legend_labels(self) -> tuple[str, ...]:
        return self._share_legend_labels

    def share_values(self):
        if self._share_data is None:
            return None
        return tuple(series.values for series in self._share_data.series)

    def status_text(self) -> str:
        return self.status_label.text()

    def _render_scatter(self) -> None:
        for item in self._scatter_items:
            self.scatter_plot.removeItem(item)
        self._scatter_items.clear()
        self.scatter_legend.clear()
        self._scatter_legend_items.clear()
        data = self._scatter_data
        if data is None:
            self._scatter_legend_labels = ()
            return
        grouped = defaultdict(list)
        for point in data.points:
            grouped[(point.type_label, point.range_index)].append(point)
        for points in grouped.values():
            first = points[0]
            item = pg.ScatterPlotItem(
                x=[point.orientation_deg for point in points],
                y=[point.median_bond_length_nm for point in points],
                size=9.0,
                symbol=first.symbol,
                pen=pg.mkPen((30, 30, 30, 180), width=0.7),
                brush=pg.mkBrush(first.color),
            )
            self.scatter_plot.addItem(item)
            self._scatter_items.append(item)
        legend_entries = (*data.type_legend, *data.range_legend)
        for entry in legend_entries:
            item = pg.ScatterPlotItem(
                size=8.0,
                symbol=entry.symbol,
                pen=pg.mkPen((30, 30, 30, 180), width=0.7),
                brush=pg.mkBrush(entry.color),
            )
            self.scatter_legend.addItem(item, entry.label)
            self._scatter_legend_items.append(item)
        self._scatter_legend_labels = tuple(
            entry.label for entry in legend_entries
        )

    def _refresh_share_plot(self, _index: int | None = None) -> None:
        outcome = self._outcome
        if outcome is None or outcome.table_result is None:
            self._share_data = None
            self._set_bar_data(self.first_bars, (), (), (), width=0.7)
            self._set_bar_data(self.second_bars, (), (), (), width=0.35)
            self.share_legend.clear()
            self._share_legend_labels = ()
            self.share_plot.getAxis("bottom").setTicks([[]])
            return
        self._share_data = build_m6_domain_type_share_plot_data(
            outcome.table_result,
            self.current_metric(),
        )
        data = self._share_data
        series_count = len(data.series)
        base_positions = tuple(float(index) for index in range(len(data.type_labels)))
        if series_count == 1:
            positions = (base_positions,)
            width = 0.7
        else:
            positions = (
                tuple(value - 0.2 for value in base_positions),
                tuple(value + 0.2 for value in base_positions),
            )
            width = 0.36
        self._set_bar_data(
            self.first_bars,
            positions[0],
            data.series[0].values,
            data.type_colors,
            width=width,
        )
        if series_count == 2:
            self._set_bar_data(
                self.second_bars,
                positions[1],
                data.series[1].values,
                data.type_colors,
                width=width,
            )
        else:
            self._set_bar_data(self.second_bars, (), (), (), width=0.35)
        self.share_plot.setLabel("left", data.axis_label)
        self.share_plot.getAxis("bottom").setTicks(
            [[(float(index), label) for index, label in enumerate(data.type_labels)]]
        )
        labels = tuple(series.name for series in data.series)
        self.share_legend.clear()
        self.share_legend.addItem(self.first_bars, labels[0])
        if len(labels) == 2:
            self.share_legend.addItem(self.second_bars, labels[1])
        self._share_legend_labels = labels

    @staticmethod
    def _set_bar_data(item, positions, values, colors, *, width: float) -> None:
        finite = tuple(
            (position, float(value), color)
            for position, value, color in zip(positions, values, colors)
            if value is not None
        )
        item.setOpts(
            x=[value[0] for value in finite],
            height=[value[1] for value in finite],
            width=width,
            brushes=[pg.mkBrush(value[2]) for value in finite],
            pen=pg.mkPen((35, 35, 35, 160), width=0.6),
            pens=None,
        )

    def _clear_plots(self) -> None:
        self._render_scatter()
        self._refresh_share_plot()
        self.status_label.setText(self._empty_message)

    def _refresh_status(self) -> None:
        data = self._scatter_data
        if data is None:
            self.status_label.setText(self._empty_message)
            return
        suffix = (
            ""
            if data.omitted_missing_bond_length_count == 0
            else (
                f" Omitted without bond length: "
                f"{data.omitted_missing_bond_length_count}."
            )
        )
        self.status_label.setText(
            f"Scatter observations: {len(data.points)}.{suffix} "
            "Colors identify shared structural types; domains are not tracked."
        )


__all__ = [
    "M6DomainTypePlotsPanel",
]
