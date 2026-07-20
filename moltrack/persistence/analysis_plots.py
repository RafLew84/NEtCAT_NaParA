from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from matplotlib import rc_context
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from moltrack.analysis import (
    M6DomainTypeClassificationResult,
    M6DomainTypeRangeComparison,
    M6SingleRangeDomainTypeSummary,
    MolecularFrameAnalysisResult,
    MolecularFrameRangeComparison,
    MolecularRangeSpatialComparisonData,
    build_molecular_range_comparison_trend_data,
    validate_m6_domain_type_table_result,
)
from moltrack.visualization.m6_domain_type_plot_data import (
    M6_DOMAIN_TYPE_SHARE_METRICS,
    M6DomainTypePlotSymbol,
    build_m6_domain_type_scatter_data,
    build_m6_domain_type_share_plot_data,
)

@dataclass(frozen=True)
class AnalysisPlotExportResult:
    generated: tuple[tuple[str, tuple[Path, Path]], ...]
    skipped: tuple[tuple[str, str], ...]
    dpi: int
    size_inches: tuple[float, float]


def export_selected_range_analysis_plots(
    frame_analysis: MolecularFrameAnalysisResult,
    comparison: MolecularFrameRangeComparison,
    spatial_data: MolecularRangeSpatialComparisonData,
    destination_dir: str | Path,
    *,
    dpi: int,
    size_inches: tuple[float, float],
    m6_domain_type_classification: M6DomainTypeClassificationResult | None = None,
    m6_domain_type_table_result: (
        M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison | None
    ) = None,
) -> AnalysisPlotExportResult:
    """Render every available selected-range analysis plot."""

    dpi, size_inches = _normalize_render_settings(dpi, size_inches)
    destination = Path(destination_dir)
    generated = [
        (
            "current_frame_positions",
            export_current_frame_position_plot(
                frame_analysis,
                destination,
                dpi=dpi,
                size_inches=size_inches,
            ),
        ),
        (
            "range_trends",
            _export_range_trends_plot(
                comparison,
                destination,
                dpi=dpi,
                size_inches=size_inches,
            ),
        ),
        (
            "spatial_comparison",
            _export_spatial_comparison_plot(
                spatial_data,
                destination,
                dpi=dpi,
                size_inches=size_inches,
            ),
        ),
        (
            "density_maps",
            _export_density_maps_plot(
                spatial_data,
                destination,
                dpi=dpi,
                size_inches=size_inches,
            ),
        ),
    ]
    skipped = []
    if spatial_data.intensity_value_range is not None:
        generated.append(
            (
                "intensity_maps",
                _export_intensity_maps_plot(
                    spatial_data,
                    destination,
                    dpi=dpi,
                    size_inches=size_inches,
                ),
            )
        )
    else:
        skipped.append(
            ("intensity_maps", "No finite intensity values are available.")
        )
    domain_type_plots = export_m6_domain_type_plots(
        m6_domain_type_classification,
        m6_domain_type_table_result,
        destination,
        dpi=dpi,
        size_inches=size_inches,
    )
    generated.extend(domain_type_plots.generated)
    skipped.extend(domain_type_plots.skipped)
    return AnalysisPlotExportResult(
        generated=tuple(generated),
        skipped=tuple(skipped),
        dpi=dpi,
        size_inches=size_inches,
    )


def export_m6_domain_type_plots(
    classification: M6DomainTypeClassificationResult | None,
    table_result: (
        M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison | None
    ),
    destination_dir: str | Path,
    *,
    dpi: int,
    size_inches: tuple[float, float],
) -> AnalysisPlotExportResult:
    """Render domain-type model data without accessing any GUI widget."""

    dpi, size_inches = _normalize_render_settings(dpi, size_inches)
    if classification is None or table_result is None:
        if classification is not None or table_result is not None:
            raise ValueError(
                "Domain type plot export requires classification and table result."
            )
        reason = "Domain type classification is not available."
        return AnalysisPlotExportResult(
            generated=(),
            skipped=(
                ("domain_type_scatter", reason),
                ("domain_type_shares", reason),
            ),
            dpi=dpi,
            size_inches=size_inches,
        )
    validate_m6_domain_type_table_result(classification, table_result)
    destination = Path(destination_dir)
    scatter_data = build_m6_domain_type_scatter_data(classification)
    generated = (
        (
            "domain_type_scatter",
            _export_m6_domain_type_scatter_plot(
                scatter_data,
                classification,
                destination,
                dpi=dpi,
                size_inches=size_inches,
            ),
        ),
        (
            "domain_type_shares",
            _export_m6_domain_type_shares_plot(
                table_result,
                destination,
                dpi=dpi,
                size_inches=size_inches,
            ),
        ),
    )
    return AnalysisPlotExportResult(
        generated=generated,
        skipped=(),
        dpi=dpi,
        size_inches=size_inches,
    )


def _export_m6_domain_type_scatter_plot(
    data,
    classification: M6DomainTypeClassificationResult,
    destination: Path,
    *,
    dpi: int,
    size_inches: tuple[float, float],
) -> tuple[Path, Path]:
    figure = _new_figure(size_inches, dpi)
    axes = figure.add_subplot(1, 1, 1)
    grouped = {}
    for point in data.points:
        grouped.setdefault((point.type_label, point.range_index), []).append(point)
    for points in grouped.values():
        first = points[0]
        axes.scatter(
            [point.orientation_deg for point in points],
            [point.median_bond_length_nm for point in points],
            s=36,
            marker=_matplotlib_marker(first.symbol),
            facecolor=_rgba(first.color),
            edgecolor=(0.12, 0.12, 0.12, 0.7),
            linewidth=0.7,
        )
    range_names = tuple(value.name for value in classification.analysis_scope.ranges)
    axes.set_title(f"Domain type separation - {' vs '.join(range_names)}")
    axes.set_xlabel(data.axis_labels[0])
    axes.set_ylabel(data.axis_labels[1])
    axes.set_xlim(0.0, 60.0)
    axes.grid(True, alpha=0.25)
    legend_handles = [
        Line2D(
            [],
            [],
            linestyle="none",
            marker="o",
            markersize=7,
            markerfacecolor=_rgba(entry.color),
            markeredgecolor=(0.12, 0.12, 0.12, 0.7),
            label=entry.label,
        )
        for entry in data.type_legend
    ]
    legend_handles.extend(
        Line2D(
            [],
            [],
            linestyle="none",
            marker=_matplotlib_marker(entry.symbol),
            markersize=7,
            markerfacecolor=_rgba(entry.color),
            markeredgecolor=(0.2, 0.2, 0.2, 1.0),
            label=entry.label,
        )
        for entry in data.range_legend
    )
    if legend_handles:
        axes.legend(handles=legend_handles)
    if data.omitted_missing_bond_length_count:
        axes.text(
            0.01,
            0.01,
            f"Missing bond length omitted: {data.omitted_missing_bond_length_count}",
            transform=axes.transAxes,
            fontsize="small",
        )
    return _save_figure(figure, destination, "domain_type_scatter", dpi=dpi)


def _export_m6_domain_type_shares_plot(
    table_result: M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison,
    destination: Path,
    *,
    dpi: int,
    size_inches: tuple[float, float],
) -> tuple[Path, Path]:
    figure = Figure(figsize=size_inches, dpi=dpi)
    FigureCanvasAgg(figure)
    figure.subplots_adjust(
        left=0.1,
        right=0.98,
        bottom=0.28,
        top=0.78,
        wspace=0.55,
    )
    axes_items = figure.subplots(1, len(M6_DOMAIN_TYPE_SHARE_METRICS), squeeze=False)[0]
    figure.suptitle("Domain type shares")
    for axes, metric in zip(axes_items, M6_DOMAIN_TYPE_SHARE_METRICS, strict=True):
        data = build_m6_domain_type_share_plot_data(table_result, metric.key)
        positions = np.arange(len(data.type_labels), dtype=np.float64)
        series_count = len(data.series)
        width = 0.7 if series_count == 1 else 0.36
        offsets = (0.0,) if series_count == 1 else (-0.2, 0.2)
        hatches = ("", "//")
        for series_index, (series, offset) in enumerate(zip(data.series, offsets)):
            values = [np.nan if value is None else float(value) for value in series.values]
            axes.bar(
                positions + offset,
                values,
                width=width,
                color=[_rgba(color) for color in data.type_colors],
                edgecolor=(0.12, 0.12, 0.12, 0.8),
                linewidth=0.6,
                hatch=hatches[series_index],
            )
        axes.set_title(metric.label)
        axes.set_ylabel(data.axis_label)
        axes.set_xticks(positions, data.type_labels, rotation=30, ha="right")
        axes.grid(True, axis="y", alpha=0.25)
        axes.legend(
            handles=[
                Patch(
                    facecolor=(0.7, 0.7, 0.7, 0.8),
                    edgecolor=(0.12, 0.12, 0.12, 0.8),
                    hatch=hatches[index],
                    label=series.name,
                )
                for index, series in enumerate(data.series)
            ]
        )
    return _save_figure(figure, destination, "domain_type_shares", dpi=dpi)


def _rgba(color: tuple[int, int, int, int]) -> tuple[float, float, float, float]:
    return tuple(channel / 255.0 for channel in color)


def _matplotlib_marker(symbol: M6DomainTypePlotSymbol) -> str:
    try:
        return {"o": "o", "s": "s", "t": "^", "d": "D"}[symbol]
    except KeyError as exc:
        raise ValueError(f"Unsupported domain type plot symbol: {symbol!r}.") from exc


def export_current_frame_position_plot(
    frame_analysis: MolecularFrameAnalysisResult,
    destination_dir: str | Path,
    *,
    dpi: int,
    size_inches: tuple[float, float],
) -> tuple[Path, Path]:
    """Render the current-frame position data directly to SVG and PNG."""

    dpi, size_inches = _normalize_render_settings(dpi, size_inches)
    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    figure = Figure(figsize=size_inches, dpi=dpi, constrained_layout=True)
    FigureCanvasAgg(figure)
    axes = figure.add_subplot(1, 1, 1)
    plot_data = frame_analysis.plot_data
    points = np.asarray(plot_data.points_xy, dtype=np.float64)
    if points.size:
        axes.scatter(points[:, 0], points[:, 1], s=24, label="Molecules")
    else:
        axes.scatter([], [], s=24, label="Molecules")
    axes.set_title(f"Current frame positions - frame {frame_analysis.frame_index + 1}")
    axes.set_xlabel(f"x [{plot_data.unit}]")
    axes.set_ylabel(f"y [{plot_data.unit}]")
    axes.set_xlim(*plot_data.x_range)
    axes.set_ylim(plot_data.y_range[1], plot_data.y_range[0])
    axes.set_aspect("equal", adjustable="box")
    axes.legend()
    axes.grid(True, alpha=0.25)

    return _save_figure(figure, destination, "current_frame_positions", dpi=dpi)


def _export_range_trends_plot(
    comparison: MolecularFrameRangeComparison,
    destination: Path,
    *,
    dpi: int,
    size_inches: tuple[float, float],
) -> tuple[Path, Path]:
    trend_data = build_molecular_range_comparison_trend_data(comparison)
    figure = _new_figure(size_inches, dpi)
    axes = figure.subplots(2, 2)
    figure.suptitle("Range trends")
    specifications = (
        ("molecule_counts", "Molecules [count]"),
        (
            "nearest_neighbor_distances",
            f"Mean nearest-neighbor distance [{trend_data.first.distance_unit}]",
        ),
        ("line_order_scores", "Line order score"),
        ("mean_intensities", f"Mean intensity [{trend_data.first.intensity_unit}]"),
    )
    for axes_item, (attribute, label) in zip(axes.flat, specifications):
        for trend in (trend_data.first, trend_data.second):
            values = [
                np.nan if value is None else float(value)
                for value in getattr(trend, attribute)
            ]
            axes_item.plot(
                [frame_index + 1 for frame_index in trend.frame_indices],
                values,
                marker="o",
                label=trend.condition_name,
            )
        axes_item.set_xlabel("Working frame number")
        axes_item.set_ylabel(label)
        axes_item.grid(True, alpha=0.25)
    axes[0, 0].legend()
    return _save_figure(figure, destination, "range_trends", dpi=dpi)


def _export_spatial_comparison_plot(
    spatial_data: MolecularRangeSpatialComparisonData,
    destination: Path,
    *,
    dpi: int,
    size_inches: tuple[float, float],
) -> tuple[Path, Path]:
    figure = _new_figure(size_inches, dpi)
    axes = figure.subplots(1, 2, squeeze=False)[0]
    figure.suptitle("Spatial comparison")
    for axes_item, condition in zip(axes, (spatial_data.first, spatial_data.second)):
        points = np.asarray(condition.points_xy, dtype=np.float64)
        if points.size:
            axes_item.scatter(points[:, 0], points[:, 1], s=20, label="Molecules")
        else:
            axes_item.scatter([], [], s=20, label="Molecules")
        axes_item.set_title(condition.condition_name)
        _set_spatial_axes(axes_item, spatial_data)
        axes_item.legend()
    return _save_figure(figure, destination, "spatial_comparison", dpi=dpi)


def _export_density_maps_plot(
    spatial_data: MolecularRangeSpatialComparisonData,
    destination: Path,
    *,
    dpi: int,
    size_inches: tuple[float, float],
) -> tuple[Path, Path]:
    figure = _new_figure(size_inches, dpi)
    axes = figure.subplots(1, 2, squeeze=False)[0]
    figure.suptitle("Density maps")
    maximum = max(float(spatial_data.density_value_range[1]), 1.0)
    image = None
    for axes_item, condition in zip(axes, (spatial_data.first, spatial_data.second)):
        image = axes_item.imshow(
            np.asarray(condition.density_grid, dtype=np.float64),
            origin="lower",
            extent=_spatial_extent(spatial_data),
            vmin=0.0,
            vmax=maximum,
            cmap="viridis",
            aspect="equal",
        )
        axes_item.set_title(condition.condition_name)
        _set_spatial_axes(axes_item, spatial_data)
    figure.colorbar(image, ax=list(axes), label="Molecules per frame per bin")
    return _save_figure(figure, destination, "density_maps", dpi=dpi)


def _export_intensity_maps_plot(
    spatial_data: MolecularRangeSpatialComparisonData,
    destination: Path,
    *,
    dpi: int,
    size_inches: tuple[float, float],
) -> tuple[Path, Path]:
    figure = _new_figure(size_inches, dpi)
    axes = figure.subplots(1, 2, squeeze=False)[0]
    figure.suptitle(f"Mean intensity maps - {spatial_data.intensity_metric}")
    value_min, value_max = spatial_data.intensity_value_range
    if value_min == value_max:
        value_max = value_min + 1.0
    image = None
    for axes_item, condition in zip(axes, (spatial_data.first, spatial_data.second)):
        image = axes_item.imshow(
            np.ma.masked_invalid(np.asarray(condition.intensity_grid, dtype=np.float64)),
            origin="lower",
            extent=_spatial_extent(spatial_data),
            vmin=value_min,
            vmax=value_max,
            cmap="magma",
            aspect="equal",
        )
        axes_item.set_title(condition.condition_name)
        _set_spatial_axes(axes_item, spatial_data)
    figure.colorbar(
        image,
        ax=list(axes),
        label=f"Mean intensity [{spatial_data.intensity_unit}]",
    )
    return _save_figure(figure, destination, "intensity_maps", dpi=dpi)


def _new_figure(size_inches: tuple[float, float], dpi: int) -> Figure:
    figure = Figure(figsize=size_inches, dpi=dpi, constrained_layout=True)
    FigureCanvasAgg(figure)
    return figure


def _spatial_extent(
    spatial_data: MolecularRangeSpatialComparisonData,
) -> tuple[float, float, float, float]:
    return (
        spatial_data.x_range[0],
        spatial_data.x_range[1],
        spatial_data.y_range[0],
        spatial_data.y_range[1],
    )


def _set_spatial_axes(axes, spatial_data: MolecularRangeSpatialComparisonData) -> None:
    axes.set_xlabel(f"x [{spatial_data.unit}]")
    axes.set_ylabel(f"y [{spatial_data.unit}]")
    axes.set_xlim(*spatial_data.x_range)
    axes.set_ylim(spatial_data.y_range[1], spatial_data.y_range[0])
    axes.set_aspect("equal", adjustable="box")


def _save_figure(
    figure: Figure,
    destination: Path,
    stem: str,
    *,
    dpi: int,
) -> tuple[Path, Path]:
    destination.mkdir(parents=True, exist_ok=True)
    svg_path = destination / f"{stem}.svg"
    png_path = destination / f"{stem}.png"
    with rc_context({"svg.fonttype": "none"}):
        figure.savefig(svg_path, format="svg")
        figure.savefig(png_path, format="png", dpi=dpi)
    figure.clear()
    return svg_path, png_path


def _normalize_render_settings(
    dpi: int,
    size_inches: tuple[float, float],
) -> tuple[int, tuple[float, float]]:
    dpi = int(dpi)
    if dpi <= 0:
        raise ValueError("plot_dpi must be positive.")
    try:
        width, height = (float(value) for value in size_inches)
    except (TypeError, ValueError) as exc:
        raise ValueError("plot_size_inches must contain width and height.") from exc
    if not np.isfinite(width) or not np.isfinite(height) or width <= 0.0 or height <= 0.0:
        raise ValueError("plot_size_inches values must be positive and finite.")
    return dpi, (width, height)
