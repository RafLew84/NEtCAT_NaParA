"""Hierarchical molecular-order tables, plots, and representative navigation."""

from __future__ import annotations

import pyqtgraph as pg
from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis import (
    MolecularOrderSummaryLayer,
    MolecularOrderTypeClassificationSettings,
    MolecularOrderTypeSummary,
    MolecularOrderTypeSummaryRowKey,
)
from moltrack.visualization.molecular_order_type_plot_data import (
    MolecularOrderGeometryScatterData,
    MolecularOrderOrientationDistributionData,
    MolecularOrderStackingShareData,
    build_molecular_order_geometry_scatter_data,
    build_molecular_order_orientation_distribution_data,
    build_molecular_order_stacking_share_data,
)


_LAYER_OPTIONS: tuple[tuple[str, MolecularOrderSummaryLayer], ...] = (
    ("Geometry M3/M6", "geometry"),
    ("Molecular orientation", "orientation"),
    ("Stacking", "stacking"),
    ("Combined hierarchy", "combination"),
)
_RANGE_SYMBOLS = ("o", "s")


class MolecularOrderTypesPanel(QScrollArea):
    """Classify and compare independent molecular-order dimensions."""

    classification_requested = pyqtSignal(object)
    representative_requested = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._summary: MolecularOrderTypeSummary | None = None
        self._geometry_data: MolecularOrderGeometryScatterData | None = None
        self._orientation_data: (
            MolecularOrderOrientationDistributionData | None
        ) = None
        self._stacking_data: MolecularOrderStackingShareData | None = None
        self._orientation_bars = []
        self._stacking_bars = []
        self._geometry_legend_items = []
        self._geometry_legend_labels: tuple[str, ...] = ()
        self._orientation_legend_labels: tuple[str, ...] = ()
        self._stacking_legend_labels: tuple[str, ...] = ()
        self._running = False

        self.setWidgetResizable(True)
        content = QWidget(self)
        layout = QVBoxLayout(content)
        self._build_settings(layout, content)
        self._build_table(layout, content)
        self._build_plots(layout, content)
        layout.addStretch(1)
        self.setWidget(content)
        self._connect()
        self.set_summary(None)

    def _build_settings(self, layout: QVBoxLayout, parent: QWidget) -> None:
        group = QGroupBox("Hierarchical type settings", parent)
        form = QFormLayout(group)

        geometry_row = QHBoxLayout()
        self.chk_dominant_symmetry = QCheckBox("Symmetry", group)
        self.chk_theta3 = QCheckBox("M3 angle", group)
        self.chk_theta6 = QCheckBox("M6 angle", group)
        for checkbox in (
            self.chk_dominant_symmetry,
            self.chk_theta3,
            self.chk_theta6,
        ):
            checkbox.setChecked(True)
            geometry_row.addWidget(checkbox)
        geometry_row.addStretch(1)
        form.addRow("Geometry features", geometry_row)

        self.lattice_tolerance_deg = QDoubleSpinBox(group)
        self.lattice_tolerance_deg.setRange(0.01, 30.0)
        self.lattice_tolerance_deg.setDecimals(2)
        self.lattice_tolerance_deg.setSingleStep(0.5)
        self.lattice_tolerance_deg.setValue(5.0)
        self.lattice_tolerance_deg.setSuffix(" deg")
        form.addRow("Lattice angle tolerance", self.lattice_tolerance_deg)

        self.molecular_tolerance_deg = QDoubleSpinBox(group)
        self.molecular_tolerance_deg.setRange(0.01, 90.0)
        self.molecular_tolerance_deg.setDecimals(2)
        self.molecular_tolerance_deg.setSingleStep(1.0)
        self.molecular_tolerance_deg.setValue(12.0)
        self.molecular_tolerance_deg.setSuffix(" deg")
        form.addRow(
            "Molecular angle tolerance",
            self.molecular_tolerance_deg,
        )

        stacking_row = QHBoxLayout()
        self.chk_stacking_pattern = QCheckBox("Pattern", group)
        self.chk_stacking_pattern.setChecked(True)
        self.chk_stacking_mode = QCheckBox("Mode", group)
        self.chk_stacking_phase = QCheckBox("Phase", group)
        self.chk_stacking_phase.setEnabled(False)
        for checkbox in (
            self.chk_stacking_pattern,
            self.chk_stacking_mode,
            self.chk_stacking_phase,
        ):
            stacking_row.addWidget(checkbox)
        stacking_row.addStretch(1)
        form.addRow("Stacking features", stacking_row)

        self.minimum_observations = QSpinBox(group)
        self.minimum_observations.setRange(1, 1_000_000)
        self.minimum_observations.setValue(1)
        form.addRow("Minimum observations/type", self.minimum_observations)

        self.run_button = QPushButton("Classify Hierarchical Types", group)
        form.addRow(self.run_button)
        layout.addWidget(group)

    def _build_table(self, layout: QVBoxLayout, parent: QWidget) -> None:
        group = QGroupBox("Type shares and changes", parent)
        group_layout = QVBoxLayout(group)
        controls = QHBoxLayout()
        self.layer_combo = QComboBox(group)
        for label, layer in _LAYER_OPTIONS:
            self.layer_combo.addItem(label, layer)
        controls.addWidget(QLabel("Layer", group))
        controls.addWidget(self.layer_combo, 1)
        group_layout.addLayout(controls)

        self.table = QTableWidget(group)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setTextElideMode(
            Qt.TextElideMode.ElideNone
        )
        self.table.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.table.setMinimumHeight(240)
        group_layout.addWidget(self.table)

        representative_row = QHBoxLayout()
        self.btn_first_representative = QPushButton(
            "Show representative",
            group,
        )
        self.btn_second_representative = QPushButton(
            "Show representative",
            group,
        )
        representative_row.addWidget(self.btn_first_representative)
        representative_row.addWidget(self.btn_second_representative)
        representative_row.addStretch(1)
        group_layout.addLayout(representative_row)

        self.status_label = QLabel(
            "Run hierarchical classification to show type shares.",
            group,
        )
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        group_layout.addWidget(self.status_label)
        layout.addWidget(group)

    def _build_plots(self, layout: QVBoxLayout, parent: QWidget) -> None:
        geometry_group = QGroupBox("Lattice geometry", parent)
        geometry_layout = QHBoxLayout(geometry_group)
        self.m3_plot = self._scatter_plot(geometry_group, "M3")
        self.m6_plot = self._scatter_plot(geometry_group, "M6")
        self.m3_legend = self.m3_plot.addLegend()
        self.m6_legend = self.m6_plot.addLegend()
        self.m3_scatter = pg.ScatterPlotItem(size=8.0)
        self.m6_scatter = pg.ScatterPlotItem(size=8.0)
        self.m3_plot.addItem(self.m3_scatter)
        self.m6_plot.addItem(self.m6_scatter)
        geometry_layout.addWidget(self.m3_plot)
        geometry_layout.addWidget(self.m6_plot)
        layout.addWidget(geometry_group)

        orientation_group = QGroupBox(
            "Molecular orientation distribution",
            parent,
        )
        orientation_layout = QVBoxLayout(orientation_group)
        self.orientation_plot = pg.PlotWidget(orientation_group)
        self._configure_plot(
            self.orientation_plot,
            bottom="Molecular orientation [deg]",
            left="Count",
        )
        self.orientation_plot.setMinimumHeight(240)
        self.orientation_legend = self.orientation_plot.addLegend()
        orientation_layout.addWidget(self.orientation_plot)
        layout.addWidget(orientation_group)

        stacking_group = QGroupBox("Stacking shares", parent)
        stacking_layout = QVBoxLayout(stacking_group)
        self.stacking_plot = pg.PlotWidget(stacking_group)
        self._configure_plot(
            self.stacking_plot,
            bottom="Stacking type",
            left="Share of reliable observations [%]",
        )
        self.stacking_plot.setMinimumHeight(240)
        self.stacking_legend = self.stacking_plot.addLegend()
        stacking_layout.addWidget(self.stacking_plot)
        layout.addWidget(stacking_group)

    def _connect(self) -> None:
        self.run_button.clicked.connect(self._request_classification)
        self.chk_stacking_mode.toggled.connect(
            self._sync_phase_dependency
        )
        self.layer_combo.currentIndexChanged.connect(self._populate_table)
        self.table.itemSelectionChanged.connect(
            self._sync_representative_buttons
        )
        self.table.cellDoubleClicked.connect(
            self._open_representative_from_cell
        )
        self.btn_first_representative.clicked.connect(
            lambda: self._emit_representative(0)
        )
        self.btn_second_representative.clicked.connect(
            lambda: self._emit_representative(1)
        )

    def settings(self) -> MolecularOrderTypeClassificationSettings:
        geometry_features = tuple(
            feature
            for checkbox, feature in (
                (self.chk_dominant_symmetry, "dominant_symmetry"),
                (self.chk_theta3, "theta3_lattice"),
                (self.chk_theta6, "theta6_lattice"),
            )
            if checkbox.isChecked()
        )
        stacking_features = tuple(
            feature
            for checkbox, feature in (
                (self.chk_stacking_pattern, "pattern"),
                (self.chk_stacking_mode, "mode"),
                (self.chk_stacking_phase, "phase"),
            )
            if checkbox.isChecked()
        )
        return MolecularOrderTypeClassificationSettings(
            geometry_features=geometry_features,
            stacking_features=stacking_features,
            lattice_orientation_tolerance_deg=(
                self.lattice_tolerance_deg.value()
            ),
            molecular_orientation_tolerance_deg=(
                self.molecular_tolerance_deg.value()
            ),
            minimum_observations_per_type=self.minimum_observations.value(),
        )

    def set_summary(
        self,
        summary: MolecularOrderTypeSummary | None,
        *,
        status_message: str | None = None,
        orientation_distribution: (
            MolecularOrderOrientationDistributionData | None
        ) = None,
    ) -> None:
        if summary is not None and not isinstance(
            summary,
            MolecularOrderTypeSummary,
        ):
            raise TypeError("summary must be MolecularOrderTypeSummary or None.")
        if orientation_distribution is not None and not isinstance(
            orientation_distribution,
            MolecularOrderOrientationDistributionData,
        ):
            raise TypeError(
                "orientation_distribution has an invalid type."
            )
        if summary is None and orientation_distribution is not None:
            raise ValueError(
                "orientation_distribution requires a summary."
            )
        self._summary = summary
        if summary is None:
            self._geometry_data = None
            self._orientation_data = None
            self._stacking_data = None
            self.status_label.setText(
                status_message
                or "Run hierarchical classification to show type shares."
            )
        else:
            self._geometry_data = (
                build_molecular_order_geometry_scatter_data(
                    summary.classification
                )
            )
            self._orientation_data = (
                orientation_distribution
                or build_molecular_order_orientation_distribution_data(
                    summary.classification,
                )
            )
            self._stacking_data = build_molecular_order_stacking_share_data(
                summary
            )
            self.status_label.setText(_summary_status(summary))
        self._populate_table()
        self._render_plots()

    def set_running(self, running: bool) -> None:
        self._running = bool(running)
        self.run_button.setEnabled(not self._running)
        self.run_button.setText(
            "Classifying..."
            if self._running
            else "Classify Hierarchical Types"
        )
        if self._running:
            self.status_label.setText(
                "Classifying hierarchical molecular-order types..."
            )

    def summary(self) -> MolecularOrderTypeSummary | None:
        return self._summary

    def set_layer(self, layer: MolecularOrderSummaryLayer) -> None:
        index = self.layer_combo.findData(str(layer))
        if index < 0:
            raise ValueError(f"Unsupported summary layer: {layer!r}.")
        self.layer_combo.setCurrentIndex(index)

    def current_layer(self) -> MolecularOrderSummaryLayer:
        return self.layer_combo.currentData()

    def headers(self) -> tuple[str, ...]:
        return tuple(
            self.table.horizontalHeaderItem(index).text()
            for index in range(self.table.columnCount())
        )

    def row_labels(self) -> tuple[str, ...]:
        return tuple(
            self.table.item(index, 0).text()
            for index in range(self.table.rowCount())
        )

    def cell_text(self, row_label: str, header: str) -> str:
        row = self.row_labels().index(str(row_label))
        column = self.headers().index(str(header))
        return self.table.item(row, column).text()

    def status_text(self) -> str:
        return self.status_label.text()

    def select_row(self, key: MolecularOrderTypeSummaryRowKey) -> None:
        if not isinstance(key, MolecularOrderTypeSummaryRowKey):
            raise TypeError("key must be MolecularOrderTypeSummaryRowKey.")
        keys = self._row_keys()
        if key not in keys:
            raise KeyError(f"Unknown molecular-order row key: {key!r}.")
        self.table.setCurrentCell(keys.index(key), 0)

    def geometry_point_counts(self) -> tuple[int, int]:
        if self._geometry_data is None:
            return 0, 0
        return (
            len(self._geometry_data.m3_points),
            len(self._geometry_data.m6_points),
        )

    def orientation_prototype_counts(self) -> tuple[int, ...]:
        if self._orientation_data is None:
            return ()
        return tuple(
            sum(value.counts) for value in self._orientation_data.series
        )

    def stacking_share_values(
        self,
    ) -> tuple[tuple[float | None, ...], ...]:
        if self._stacking_data is None:
            return ()
        return tuple(
            value.values_percent for value in self._stacking_data.series
        )

    def geometry_legend_labels(self) -> tuple[str, ...]:
        return self._geometry_legend_labels

    def orientation_legend_labels(self) -> tuple[str, ...]:
        return self._orientation_legend_labels

    def stacking_legend_labels(self) -> tuple[str, ...]:
        return self._stacking_legend_labels

    def geometry_axis_labels(self) -> tuple[str, str]:
        if self._geometry_data is None:
            return "Lattice angle [deg]", "Molecules"
        return self._geometry_data.axis_labels

    def _request_classification(self) -> None:
        try:
            settings = self.settings()
        except (TypeError, ValueError) as exc:
            self.status_label.setText(str(exc))
            return
        self.classification_requested.emit(settings)

    def _sync_phase_dependency(self, checked: bool) -> None:
        self.chk_stacking_phase.setEnabled(bool(checked))
        if not checked:
            self.chk_stacking_phase.setChecked(False)

    def _populate_table(self, _index: int | None = None) -> None:
        blocker = QSignalBlocker(self.table)
        try:
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            summary = self._summary
            if summary is None:
                return
            rows = summary.rows_for_layer(self.current_layer())
            headers = ["Type", "Definition"]
            for frame_range in summary.classification.analysis_scope.ranges:
                headers.extend(
                    (
                        f"{frame_range.name} | Count",
                        f"{frame_range.name} | Share [%]",
                    )
                )
            if len(summary.range_summaries) == 2:
                first, second = summary.range_summaries
                headers.append(
                    f"Delta ({second.range_name} - "
                    f"{first.range_name}) [pp]"
                )
            self.table.setColumnCount(len(headers))
            self.table.setHorizontalHeaderLabels(headers)
            self.table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                values = [row.label, row.description]
                for share in row.range_shares:
                    values.extend(
                        (
                            str(share.count),
                            _format_optional(share.share_percent),
                        )
                    )
                if len(row.range_shares) == 2:
                    values.append(
                        _format_optional(
                            row.share_delta_percentage_points,
                            signed=True,
                        )
                    )
                for column_index, text in enumerate(values):
                    item = QTableWidgetItem(text)
                    if column_index == 0:
                        item.setData(Qt.ItemDataRole.UserRole, row.key)
                    elif column_index >= 2:
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight
                            | Qt.AlignmentFlag.AlignVCenter
                        )
                    self.table.setItem(row_index, column_index, item)
            self.table.resizeRowsToContents()
        finally:
            del blocker
        self._sync_representative_buttons()

    def _selected_row(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected or self._summary is None:
            return None
        key = self.table.item(
            selected[0].row(),
            0,
        ).data(Qt.ItemDataRole.UserRole)
        return next(
            (
                value
                for value in self._summary.rows_for_layer(
                    self.current_layer()
                )
                if value.key == key
            ),
            None,
        )

    def _row_keys(self) -> tuple[MolecularOrderTypeSummaryRowKey, ...]:
        return tuple(
            self.table.item(index, 0).data(Qt.ItemDataRole.UserRole)
            for index in range(self.table.rowCount())
        )

    def _sync_representative_buttons(self) -> None:
        row = self._selected_row()
        shares = () if row is None else row.range_shares
        buttons = (
            self.btn_first_representative,
            self.btn_second_representative,
        )
        for index, button in enumerate(buttons):
            visible = (
                self._summary is not None
                and index < len(self._summary.range_summaries)
            )
            button.setVisible(visible)
            if visible:
                range_name = self._summary.range_summaries[index].range_name
                button.setText(f"Show {range_name} representative")
            button.setEnabled(
                visible
                and index < len(shares)
                and shares[index].representative_observation_key is not None
            )

    def _emit_representative(self, range_index: int) -> None:
        row = self._selected_row()
        if row is None or range_index >= len(row.range_shares):
            return
        key = row.range_shares[
            range_index
        ].representative_observation_key
        if key is not None:
            self.representative_requested.emit(key)

    def _open_representative_from_cell(
        self,
        _row: int,
        column: int,
    ) -> None:
        row = self._selected_row()
        if row is None:
            return
        if 2 <= column < 2 + 2 * len(row.range_shares):
            requested = (column - 2) // 2
        else:
            requested = next(
                (
                    index
                    for index, share in enumerate(row.range_shares)
                    if share.representative_observation_key is not None
                ),
                0,
            )
        self._emit_representative(requested)

    def _render_plots(self) -> None:
        self._render_geometry_plot(
            self.m3_scatter,
            ()
            if self._geometry_data is None
            else self._geometry_data.m3_points,
        )
        self._render_geometry_plot(
            self.m6_scatter,
            ()
            if self._geometry_data is None
            else self._geometry_data.m6_points,
        )
        self._render_geometry_legends()
        self._render_orientation_plot()
        self._render_stacking_plot()

    @staticmethod
    def _render_geometry_plot(scatter, points) -> None:
        scatter.setData(
            [
                {
                    "pos": (point.angle_deg, point.molecule_count),
                    "symbol": _RANGE_SYMBOLS[
                        min(point.range_index, len(_RANGE_SYMBOLS) - 1)
                    ],
                    "pen": pg.mkPen((35, 35, 35, 180), width=0.7),
                    "brush": pg.mkBrush(point.color),
                    "data": point.observation_key,
                }
                for point in points
            ]
        )

    def _render_geometry_legends(self) -> None:
        self.m3_legend.clear()
        self.m6_legend.clear()
        self._geometry_legend_items.clear()
        data = self._geometry_data
        if data is None:
            self._geometry_legend_labels = ()
            return
        entries = (
            *(
                (f"Type {label}", "o", color)
                for label, color in zip(
                    data.type_labels,
                    data.type_colors,
                    strict=True,
                )
            ),
            *(
                (
                    f"Range {name}",
                    _RANGE_SYMBOLS[
                        min(index, len(_RANGE_SYMBOLS) - 1)
                    ],
                    (120, 120, 120, 220),
                )
                for index, name in enumerate(data.range_names)
            ),
        )
        for legend in (self.m3_legend, self.m6_legend):
            for label, symbol, color in entries:
                item = pg.ScatterPlotItem(
                    size=8.0,
                    symbol=symbol,
                    pen=pg.mkPen((35, 35, 35, 180), width=0.7),
                    brush=pg.mkBrush(color),
                )
                legend.addItem(item, label)
                self._geometry_legend_items.append(item)
        self._geometry_legend_labels = tuple(
            value[0] for value in entries
        )

    def _render_orientation_plot(self) -> None:
        for item in self._orientation_bars:
            self.orientation_plot.removeItem(item)
        self._orientation_bars.clear()
        self.orientation_legend.clear()
        data = self._orientation_data
        if data is None or not data.series:
            self._orientation_legend_labels = ()
            return
        centers = tuple(
            (left + right) / 2.0
            for left, right in zip(
                data.bin_edges_deg[:-1],
                data.bin_edges_deg[1:],
            )
        )
        bin_width = data.bin_edges_deg[1] - data.bin_edges_deg[0]
        series_count = len(data.series)
        width = 0.8 * bin_width / series_count
        for index, series in enumerate(data.series):
            offset = (index - (series_count - 1) / 2.0) * width
            item = pg.BarGraphItem(
                x=[value + offset for value in centers],
                height=series.counts,
                width=width,
                pen=pg.mkPen((35, 35, 35, 140), width=0.5),
                brush=pg.mkBrush(
                    (0, 135, 95, 180)
                    if index == 0
                    else (45, 105, 185, 180)
                ),
            )
            self.orientation_plot.addItem(item)
            self._orientation_bars.append(item)
            self.orientation_legend.addItem(item, series.range_name)
        self._orientation_legend_labels = tuple(
            value.range_name for value in data.series
        )

    def _render_stacking_plot(self) -> None:
        for item in self._stacking_bars:
            self.stacking_plot.removeItem(item)
        self._stacking_bars.clear()
        self.stacking_legend.clear()
        data = self._stacking_data
        if data is None or not data.series:
            self._stacking_legend_labels = ()
            self.stacking_plot.getAxis("bottom").setTicks([[]])
            return
        base = tuple(float(index) for index in range(len(data.type_labels)))
        series_count = len(data.series)
        width = 0.72 / series_count
        for index, series in enumerate(data.series):
            offset = (index - (series_count - 1) / 2.0) * width
            finite = tuple(
                (position + offset, value, color)
                for position, value, color in zip(
                    base,
                    series.values_percent,
                    data.type_colors,
                )
                if value is not None
            )
            item = pg.BarGraphItem(
                x=[value[0] for value in finite],
                height=[value[1] for value in finite],
                width=width,
                brushes=[
                    pg.mkBrush(
                        value[2][0],
                        value[2][1],
                        value[2][2],
                        150 if index == 0 and series_count == 2 else 235,
                    )
                    for value in finite
                ],
                pen=pg.mkPen((35, 35, 35, 150), width=0.5),
            )
            self.stacking_plot.addItem(item)
            self._stacking_bars.append(item)
            self.stacking_legend.addItem(item, series.range_name)
        self._stacking_legend_labels = tuple(
            value.range_name for value in data.series
        )
        self.stacking_plot.getAxis("bottom").setTicks(
            [[
                (float(index), label)
                for index, label in enumerate(data.type_labels)
            ]]
        )

    @classmethod
    def _scatter_plot(cls, parent: QWidget, title: str):
        plot = pg.PlotWidget(parent)
        cls._configure_plot(
            plot,
            bottom="Lattice angle [deg]",
            left="Molecules",
        )
        plot.setTitle(title)
        plot.setXRange(0.0, 60.0, padding=0.0)
        plot.setMinimumHeight(240)
        return plot

    @staticmethod
    def _configure_plot(plot, *, bottom: str, left: str) -> None:
        plot.setBackground("w")
        plot.showGrid(x=True, y=True, alpha=0.2)
        plot.setLabel("bottom", bottom)
        plot.setLabel("left", left)


def _summary_status(summary: MolecularOrderTypeSummary) -> str:
    lines = []
    for value in summary.range_summaries:
        parts = tuple(
            (
                f"{layer}: reliable {value.denominator_for_layer(layer)}/"
                f"{value.total_observation_count}, excluded "
                f"{value.excluded_for_layer(layer)}"
            )
            for layer in (
                "geometry",
                "orientation",
                "stacking",
                "combination",
            )
        )
        lines.append(f"{value.range_name}: " + "; ".join(parts))
    lines.append(
        "Shares use reliable observations of each layer; domains are not tracked."
    )
    return "\n".join(lines)


def _format_optional(
    value: float | None,
    *,
    signed: bool = False,
) -> str:
    if value is None:
        return "-"
    return f"{value:+.3f}" if signed else f"{value:.3f}"


__all__ = ["MolecularOrderTypesPanel"]
