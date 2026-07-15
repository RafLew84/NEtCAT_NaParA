from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from matplotlib import rc_context
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from moltrack.analysis import (
    MolecularFrameAnalysisResult,
    MolecularFrameRangeComparison,
    MolecularRangeSpatialComparisonData,
    build_molecular_range_comparison_trend_data,
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
    return AnalysisPlotExportResult(
        generated=tuple(generated),
        skipped=tuple(skipped),
        dpi=dpi,
        size_inches=size_inches,
    )


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
