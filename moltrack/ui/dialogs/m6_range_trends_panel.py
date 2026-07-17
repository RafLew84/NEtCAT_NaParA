from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pyqtgraph as pg

from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis import (
    M6_DOMAIN_TREND_FIELD_NAMES,
    MolecularRangeComparisonTrendData,
)


@dataclass(frozen=True)
class M6TrendMetricSpec:
    field_name: str
    label: str
    axis_label: str


M6_TREND_METRICS = (
    M6TrendMetricSpec(
        "mean_local_q6_interior",
        "Mean local q6 (interior)",
        "Mean local q6 (interior) [0-1]",
    ),
    M6TrendMetricSpec(
        "mean_local_q6_all_valid",
        "Mean local q6 (all valid)",
        "Mean local q6 (all valid) [0-1]",
    ),
    M6TrendMetricSpec(
        "global_q6_interior",
        "Global q6 (interior)",
        "Global q6 (interior) [0-1]",
    ),
    M6TrendMetricSpec(
        "edge_truncated_fraction_of_valid_representatives",
        "Edge-truncated valid representatives",
        "Edge-truncated fraction of valid representatives [0-1]",
    ),
    M6TrendMetricSpec("full_domain_counts", "Full domains", "Full domains [count]"),
    M6TrendMetricSpec(
        "small_ordered_island_counts",
        "Small ordered islands",
        "Small ordered islands [count]",
    ),
    M6TrendMetricSpec(
        "largest_domain_molecule_fraction",
        "Largest domain molecule fraction",
        "Largest domain fraction of valid representatives [0-1]",
    ),
    M6TrendMetricSpec(
        "largest_domain_footprint_fraction",
        "Largest domain footprint fraction",
        "Largest domain fraction of valid FOV [0-1]",
    ),
    M6TrendMetricSpec(
        "full_domain_molecule_fraction",
        "Molecules in full domains",
        "Full-domain fraction of valid representatives [0-1]",
    ),
    M6TrendMetricSpec(
        "small_island_molecule_fraction",
        "Molecules in small islands",
        "Small-island fraction of valid representatives [0-1]",
    ),
    M6TrendMetricSpec(
        "unassigned_molecule_fraction",
        "Unassigned molecules",
        "Unassigned fraction of valid representatives [0-1]",
    ),
    M6TrendMetricSpec(
        "full_domain_footprint_fraction",
        "Valid FOV: full domains",
        "Full-domain fraction of valid FOV [0-1]",
    ),
    M6TrendMetricSpec(
        "small_island_footprint_fraction",
        "Valid FOV: small islands",
        "Small-island fraction of valid FOV [0-1]",
    ),
    M6TrendMetricSpec(
        "unassigned_supported_footprint_fraction",
        "Valid FOV: unassigned support",
        "Unassigned supported fraction of valid FOV [0-1]",
    ),
    M6TrendMetricSpec(
        "unsupported_background_fraction",
        "Valid FOV: unsupported background",
        "Unsupported background fraction of valid FOV [0-1]",
    ),
    M6TrendMetricSpec(
        "full_domain_molecule_weighted_coherent_q6",
        "Coherent q6 (molecule weighted)",
        "Coherent q6 (molecule weighted) [0-1]",
    ),
    M6TrendMetricSpec(
        "full_domain_footprint_weighted_coherent_q6",
        "Coherent q6 (footprint weighted)",
        "Coherent q6 (footprint weighted) [0-1]",
    ),
    M6TrendMetricSpec(
        "domain_molecule_entropy",
        "Domain molecule entropy",
        "Domain molecule entropy [0-1]",
    ),
    M6TrendMetricSpec(
        "domain_footprint_entropy",
        "Domain footprint entropy",
        "Domain footprint entropy [0-1]",
    ),
)

if tuple(metric.field_name for metric in M6_TREND_METRICS) != (
    M6_DOMAIN_TREND_FIELD_NAMES
):
    raise RuntimeError("M6 trend presentation must match the analysis registry.")

_METRICS_BY_NAME = {metric.field_name: metric for metric in M6_TREND_METRICS}


class M6RangeTrendsPanel(QWidget):
    """Independent-frame M6 trends for two named experimental ranges."""

    _MAX_STATUS_DETAILS = 6

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._trend_data: MolecularRangeComparisonTrendData | None = None
        self._empty_status = "No M6 range analysis."
        self._legend_labels: tuple[str, str] | None = None

        group = QGroupBox("M6 range trends", self)
        group_layout = QVBoxLayout(group)
        controls = QWidget(group)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        self.metric_combo = QComboBox(controls)
        for metric in M6_TREND_METRICS:
            self.metric_combo.addItem(metric.label, metric.field_name)
        form.addRow("Metric", self.metric_combo)
        self.frame_axis_combo = QComboBox(controls)
        self.frame_axis_combo.addItem("Working frame", "working")
        self.frame_axis_combo.addItem("Source frame", "source")
        form.addRow("Frame axis", self.frame_axis_combo)
        controls_layout.addLayout(form)
        controls_layout.addStretch(1)
        group_layout.addWidget(controls)

        self.plot = pg.PlotWidget(group)
        self.plot.setBackground("w")
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.plot.addLegend()
        self.plot.setMinimumHeight(280)
        self.first_curve = self.plot.plot(
            [],
            [],
            pen=pg.mkPen((0, 140, 90), width=2.0),
            symbol="o",
            symbolBrush=pg.mkBrush((0, 140, 90)),
            connect="finite",
        )
        self.second_curve = self.plot.plot(
            [],
            [],
            pen=pg.mkPen((40, 100, 190), width=2.0),
            symbol="s",
            symbolBrush=pg.mkBrush((40, 100, 190)),
            connect="finite",
        )
        group_layout.addWidget(self.plot)
        self.status_label = QLabel("No M6 range analysis.", group)
        self.status_label.setWordWrap(True)
        group_layout.addWidget(self.status_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(group)

        self.metric_combo.currentIndexChanged.connect(self._refresh_plot)
        self.frame_axis_combo.currentIndexChanged.connect(self._refresh_plot)
        self._refresh_plot()

    def set_trend_data(
        self,
        trend_data: MolecularRangeComparisonTrendData | None,
    ) -> None:
        if trend_data is not None and not isinstance(
            trend_data,
            MolecularRangeComparisonTrendData,
        ):
            raise TypeError(
                "trend_data must be MolecularRangeComparisonTrendData or None."
            )
        self._trend_data = trend_data
        self._empty_status = "No M6 range analysis."
        self._refresh_plot()

    def invalidate_for_settings_change(self) -> None:
        if self._trend_data is None:
            return
        self._trend_data = None
        self._empty_status = (
            "M6 settings changed. Run/Recalculate to refresh range trends."
        )
        self._refresh_plot()

    def trend_data(self) -> MolecularRangeComparisonTrendData | None:
        return self._trend_data

    def metric_options(self) -> tuple[str, ...]:
        return tuple(metric.field_name for metric in M6_TREND_METRICS)

    def current_metric(self) -> str:
        return str(self.metric_combo.currentData())

    def set_metric(self, field_name: str) -> None:
        index = self.metric_combo.findData(str(field_name))
        if index < 0:
            raise ValueError(f"Unsupported M6 trend metric: {field_name!r}.")
        self.metric_combo.setCurrentIndex(index)

    def set_frame_axis(self, axis: str) -> None:
        index = self.frame_axis_combo.findData(str(axis))
        if index < 0:
            raise ValueError(f"Unsupported M6 frame axis: {axis!r}.")
        self.frame_axis_combo.setCurrentIndex(index)

    def legend_labels(self) -> tuple[str, str] | None:
        if not self._has_m6_data():
            return None
        assert self._trend_data is not None
        return (
            self._trend_data.first.condition_name,
            self._trend_data.second.condition_name,
        )

    def axis_labels(self) -> tuple[str, str]:
        axis_label = (
            "Source frame number"
            if self.frame_axis_combo.currentData() == "source"
            else "Working frame number"
        )
        return axis_label, _METRICS_BY_NAME[self.current_metric()].axis_label

    def plot_values(self):
        series = self._m6_series()
        if series is None:
            return None
        first, second = series
        metric = self.current_metric()
        return getattr(first, metric), getattr(second, metric)

    def frame_values(self):
        series = self._m6_series()
        if series is None:
            return None
        first, second = series
        field_name = (
            "source_frame_indices"
            if self.frame_axis_combo.currentData() == "source"
            else "frame_indices"
        )
        return tuple(
            tuple(int(value) + 1 for value in getattr(values, field_name))
            for values in (first, second)
        )

    def status_text(self) -> str:
        return self.status_label.text()

    def _has_m6_data(self) -> bool:
        return self._m6_series() is not None

    def _m6_series(self):
        if self._trend_data is None:
            return None
        first = self._trend_data.first.m6_orientation
        second = self._trend_data.second.m6_orientation
        if first is None or second is None:
            return None
        return first, second

    def _refresh_plot(self, _index: int | None = None) -> None:
        legend = self.plot.getPlotItem().legend
        if legend is None:
            legend = self.plot.addLegend()
        self.plot.setLabel("bottom", self.axis_labels()[0])
        self.plot.setLabel("left", self.axis_labels()[1])
        series = self._m6_series()
        if series is None:
            self.first_curve.setData([], [])
            self.second_curve.setData([], [])
            legend.clear()
            self._legend_labels = None
            self.status_label.setText(self._empty_status)
            return
        assert self._trend_data is not None
        frame_values = self.frame_values()
        plot_values = self.plot_values()
        assert frame_values is not None and plot_values is not None
        self._set_curve_data(
            self.first_curve,
            frame_values[0],
            plot_values[0],
        )
        self._set_curve_data(
            self.second_curve,
            frame_values[1],
            plot_values[1],
        )
        labels = (
            self._trend_data.first.condition_name,
            self._trend_data.second.condition_name,
        )
        if labels != self._legend_labels:
            legend.clear()
            legend.addItem(self.first_curve, labels[0])
            legend.addItem(self.second_curve, labels[1])
            self._legend_labels = labels
        self.status_label.setText(self._availability_status(plot_values))

    @staticmethod
    def _set_curve_data(curve, x_values, y_values) -> None:
        x_array = np.asarray(x_values, dtype=np.float64)
        y_array = np.asarray(
            [np.nan if value is None else float(value) for value in y_values],
            dtype=np.float64,
        )
        if not np.any(np.isfinite(y_array)):
            x_array = np.asarray([], dtype=np.float64)
            y_array = np.asarray([], dtype=np.float64)
        curve.setData(x_array, y_array, connect="finite")

    def _availability_status(self, plot_values) -> str:
        assert self._trend_data is not None
        first, second = self._m6_series()
        messages = []
        for condition_name, values, y_values in (
            (self._trend_data.first.condition_name, first, plot_values[0]),
            (self._trend_data.second.condition_name, second, plot_values[1]),
        ):
            for position, (status, reason, value) in enumerate(
                zip(
                    values.availability_statuses,
                    values.unavailability_reasons,
                    y_values,
                )
            ):
                if status != "available" or value is None:
                    detail = reason or "metric undefined"
                    messages.append(
                        f"{condition_name}: working {values.frame_indices[position] + 1}, "
                        f"source {values.source_frame_indices[position] + 1}: {detail}"
                    )
        prefix = "Domain metrics are frame-local; no cross-frame domain tracking."
        if not messages:
            return f"{prefix} All selected M6 frames are available."
        visible = messages[: self._MAX_STATUS_DETAILS]
        remaining = len(messages) - len(visible)
        suffix = "" if remaining == 0 else f"; and {remaining} more"
        return f"{prefix} Gaps: " + "; ".join(visible) + suffix
