from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis import (
    M6DomainTypeRangeComparison,
    M6DomainTypeRangeComparisonRow,
    M6SingleRangeDomainTypeSummary,
)


_SINGLE_HEADERS = (
    "Type",
    "Orientation [deg]",
    "Circular spread [deg]",
    "Median bond length [nm]",
    "Bond length IQR [nm]",
    "Observations",
    "Frames with type",
    "Frames with type [%]",
    "Instances/frame",
    "Molecule fraction [%]",
    "Footprint fraction [%]",
    "Mean coherent q6",
)

_COMPARISON_PROTOTYPE_HEADERS = (
    "Type",
    "Orientation [deg]",
    "Circular spread [deg]",
    "Median bond length [nm]",
    "Bond length IQR [nm]",
    "Total observations",
)

_OptionalNumber = int | float | None


@dataclass(frozen=True)
class _TablePresentation:
    summary: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    empty_message: str = ""


@dataclass(frozen=True)
class _ComparisonMetric:
    label: str
    first_value: Callable[[M6DomainTypeRangeComparisonRow], _OptionalNumber]
    second_value: Callable[[M6DomainTypeRangeComparisonRow], _OptionalNumber]
    delta_value: Callable[[M6DomainTypeRangeComparisonRow], _OptionalNumber]
    delta_label: str | None = None
    first_scale: float = 1.0
    second_scale: float = 1.0
    delta_scale: float = 1.0
    shows_unclassified_observations: bool = False

    def headers(
        self,
        first_name: str,
        second_name: str,
        delta_name: str,
    ) -> tuple[str, str, str]:
        return (
            f"{first_name} | {self.label}",
            f"{second_name} | {self.label}",
            f"{delta_name} | {self.delta_label or self.label}",
        )

    def values(
        self,
        row: M6DomainTypeRangeComparisonRow,
    ) -> tuple[str, str, str]:
        return (
            _format_optional(self.first_value(row), scale=self.first_scale),
            _format_optional(self.second_value(row), scale=self.second_scale),
            _format_optional(self.delta_value(row), scale=self.delta_scale),
        )

    def unclassified_values(
        self,
        first_count: int,
        second_count: int,
    ) -> tuple[str, str, str]:
        if not self.shows_unclassified_observations:
            return ("-", "-", "-")
        return (
            str(first_count),
            str(second_count),
            str(second_count - first_count),
        )


_COMPARISON_METRICS = (
    _ComparisonMetric(
        "Observations",
        first_value=lambda row: row.first.domain_instance_count,
        second_value=lambda row: row.second.domain_instance_count,
        delta_value=lambda row: row.deltas.domain_instance_count,
        shows_unclassified_observations=True,
    ),
    _ComparisonMetric(
        "Frames with type",
        first_value=lambda row: row.first.frames_with_type_count,
        second_value=lambda row: row.second.frames_with_type_count,
        delta_value=lambda row: row.deltas.frames_with_type_count,
    ),
    _ComparisonMetric(
        "Frames with type [%]",
        first_value=lambda row: row.first.frames_with_type_percent,
        second_value=lambda row: row.second.frames_with_type_percent,
        delta_value=lambda row: row.deltas.frames_with_type_percentage_points,
        delta_label="Frames with type [pp]",
    ),
    _ComparisonMetric(
        "Instances/frame",
        first_value=lambda row: row.first.mean_domain_instances_per_available_frame,
        second_value=lambda row: row.second.mean_domain_instances_per_available_frame,
        delta_value=lambda row: row.deltas.mean_domain_instances_per_available_frame,
    ),
    _ComparisonMetric(
        "Molecule fraction [%]",
        first_value=lambda row: row.first.mean_molecule_fraction,
        second_value=lambda row: row.second.mean_molecule_fraction,
        delta_value=lambda row: row.deltas.mean_molecule_fraction_percentage_points,
        delta_label="Molecule fraction [pp]",
        first_scale=100.0,
        second_scale=100.0,
    ),
    _ComparisonMetric(
        "Footprint fraction [%]",
        first_value=lambda row: row.first.mean_footprint_fraction,
        second_value=lambda row: row.second.mean_footprint_fraction,
        delta_value=lambda row: row.deltas.mean_footprint_fraction_percentage_points,
        delta_label="Footprint fraction [pp]",
        first_scale=100.0,
        second_scale=100.0,
    ),
    _ComparisonMetric(
        "Mean coherent q6",
        first_value=lambda row: row.first.mean_domain_coherent_q6,
        second_value=lambda row: row.second.mean_domain_coherent_q6,
        delta_value=lambda row: row.deltas.mean_domain_coherent_q6,
    ),
)


class M6DomainTypeResultsTable(QWidget):
    """Adaptive table for one-range summaries and joint range comparisons."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._table_result: (
            M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison | None
        ) = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.summary_label = QLabel("", self)
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.summary_label.hide()
        layout.addWidget(self.summary_label)

        self.empty_label = QLabel(
            "Classify domain types to show the result table.",
            self,
        )
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        self.table = QTableWidget(0, 0, self)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setTextElideMode(Qt.TextElideMode.ElideNone)
        self.table.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.table.setMinimumHeight(260)
        self.table.hide()
        layout.addWidget(self.table)

    def set_table_result(
        self,
        result: M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison | None,
        *,
        empty_message: str = "Classify domain types to show the result table.",
    ) -> None:
        if result is not None and not isinstance(
            result,
            (M6SingleRangeDomainTypeSummary, M6DomainTypeRangeComparison),
        ):
            raise TypeError("result must be a domain type table result or None.")
        self._table_result = result
        if result is None:
            self._clear_table()
            self.summary_label.hide()
            self.empty_label.setText(str(empty_message))
            self.empty_label.show()
            self.table.hide()
            return

        presentation = (
            _single_range_presentation(result)
            if isinstance(result, M6SingleRangeDomainTypeSummary)
            else _comparison_presentation(result)
        )
        self.summary_label.setText(presentation.summary)
        self.summary_label.show()
        self.empty_label.setText(presentation.empty_message)
        self.empty_label.setVisible(bool(presentation.empty_message))
        self._populate_table(presentation)
        self.table.show()

    def table_result(
        self,
    ) -> M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison | None:
        return self._table_result

    def summary_text(self) -> str:
        return self.summary_label.text()

    def empty_state_text(self) -> str:
        return self.empty_label.text()

    def headers(self) -> tuple[str, ...]:
        return tuple(
            self.table.horizontalHeaderItem(index).text()
            for index in range(self.table.columnCount())
        )

    def row_labels(self) -> tuple[str, ...]:
        return tuple(
            self.table.item(row_index, 0).text()
            for row_index in range(self.table.rowCount())
        )

    def cell_text(self, row_label: str, header: str) -> str:
        try:
            row_index = self.row_labels().index(str(row_label))
        except ValueError as exc:
            raise KeyError(f"Unknown domain type row: {row_label!r}.") from exc
        try:
            column_index = self.headers().index(str(header))
        except ValueError as exc:
            raise KeyError(f"Unknown domain type column: {header!r}.") from exc
        return self.table.item(row_index, column_index).text()

    def _clear_table(self) -> None:
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)

    def _populate_table(self, presentation: _TablePresentation) -> None:
        self._clear_table()
        self.table.setColumnCount(len(presentation.headers))
        self.table.setHorizontalHeaderLabels(presentation.headers)
        self.table.setRowCount(len(presentation.rows))
        for column_index, header in enumerate(presentation.headers):
            header_item = self.table.horizontalHeaderItem(column_index)
            header_item.setToolTip(header)
        for row_index, values in enumerate(presentation.rows):
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column_index > 0:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row_index, column_index, item)
        self.table.resizeRowsToContents()


def _single_range_presentation(
    result: M6SingleRangeDomainTypeSummary,
) -> _TablePresentation:
    frame_percent = _format_optional(result.frames_with_full_domain_percent, 2)
    summary = (
        f"Range: {result.range_name}\n"
        f"Frames with domains: {result.frames_with_full_domain_count}/"
        f"{result.available_frame_count} ({frame_percent}%) | "
        "Domains per available frame: "
        f"mean {_format_optional(result.mean_full_domains_per_available_frame)} | "
        f"median {_format_optional(result.median_full_domains_per_available_frame)} | "
        f"max {_format_optional(result.max_full_domains_per_available_frame)}\n"
        f"Observations: {result.domain_observation_count} | "
        f"Unclassified: {result.unclassified_observation_count} | "
        f"Types: {result.domain_type_count}"
    )
    rows = []
    for row in sorted(result.type_summaries, key=lambda value: value.domain_type_id):
        rows.append(
            (
                row.label,
                _format_optional(row.prototype_orientation_deg),
                _format_optional(row.orientation_circular_spread_deg),
                _format_optional(row.prototype_bond_length_nm),
                _format_optional(row.bond_length_iqr_nm),
                str(row.observation_count),
                str(row.frames_with_type_count),
                _format_optional(row.frames_with_type_percent),
                _format_optional(row.mean_instances_per_available_frame),
                _format_optional(
                    row.mean_molecule_fraction_of_valid_representatives,
                    scale=100.0,
                ),
                _format_optional(
                    row.mean_footprint_fraction_of_valid_fov,
                    scale=100.0,
                ),
                _format_optional(row.mean_domain_coherent_q6),
            )
        )
    rows.append(
        (
            "Unclassified",
            "-",
            "-",
            "-",
            "-",
            str(result.unclassified_observation_count),
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
        )
    )
    return _TablePresentation(
        summary=summary,
        headers=_SINGLE_HEADERS,
        rows=tuple(rows),
        empty_message=(
            "No classified domain types. Unclassified observations are listed below."
            if not result.type_summaries
            else ""
        ),
    )


def _comparison_presentation(
    result: M6DomainTypeRangeComparison,
) -> _TablePresentation:
    first_name = result.first_range_name
    second_name = result.second_range_name
    delta_name = "Delta (second - first)"
    headers = list(_COMPARISON_PROTOTYPE_HEADERS)
    for metric in _COMPARISON_METRICS:
        headers.extend(metric.headers(first_name, second_name, delta_name))

    rows = []
    for row in sorted(result.rows, key=lambda value: value.domain_type_id):
        values = [
            row.label,
            _format_optional(row.prototype_orientation_deg),
            _format_optional(row.orientation_circular_spread_deg),
            _format_optional(row.prototype_bond_length_nm),
            _format_optional(row.bond_length_iqr_nm),
            str(row.domain_type.observation_count),
        ]
        for metric in _COMPARISON_METRICS:
            values.extend(metric.values(row))
        rows.append(tuple(values))

    first_unclassified = result.first_summary.unclassified_observation_count
    second_unclassified = result.second_summary.unclassified_observation_count
    unclassified = [
        "Unclassified",
        "-",
        "-",
        "-",
        "-",
        str(first_unclassified + second_unclassified),
    ]
    for metric in _COMPARISON_METRICS:
        unclassified.extend(
            metric.unclassified_values(first_unclassified, second_unclassified)
        )
    rows.append(tuple(unclassified))

    return _TablePresentation(
        summary=(
            f"Ranges: {first_name} vs {second_name} | "
            "Deltas: second - first | Shared structural types; domains are not tracked."
        ),
        headers=tuple(headers),
        rows=tuple(rows),
        empty_message=(
            "No classified domain types. Unclassified observations are listed below."
            if not result.rows
            else ""
        ),
    )


def _format_optional(
    value: int | float | None,
    decimals: int = 3,
    *,
    scale: float = 1.0,
) -> str:
    if value is None:
        return "-"
    if isinstance(value, int):
        return str(value)
    return f"{float(value) * scale:.{decimals}f}"
