from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from moltrack import __version__ as moltrack_version
from moltrack.analysis import (
    MolecularFrameRange,
    MolecularFrameRangeSelection,
    analyze_molecular_frame_range,
)
from moltrack.core import MolTrackImageSeries

from .analysis_export import (
    ANALYSIS_EXPORT_SCHEMA_VERSION,
    export_current_frame_analysis_csv,
    export_full_working_series_analysis_csv,
    export_selected_ranges_analysis_csv,
)


@dataclass(frozen=True)
class AnalysisExportPackageResult:
    """Published analysis package and its portable relative contents."""

    package_path: Path
    package_format: str
    relative_files: tuple[str, ...]
    record_counts: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class AnalysisExportProgress:
    """One observable stage of an analysis package export."""

    phase: str
    completed_count: int = 0
    total_count: int = 0

    def __post_init__(self) -> None:
        phase = str(self.phase).strip()
        completed_count = int(self.completed_count)
        total_count = int(self.total_count)
        if not phase:
            raise ValueError("Analysis export progress phase must not be empty.")
        if completed_count < 0 or total_count < 0 or completed_count > total_count:
            raise ValueError("Analysis export progress counts are invalid.")
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "completed_count", completed_count)
        object.__setattr__(self, "total_count", total_count)


@dataclass(frozen=True)
class AnalysisExportSettings:
    """Immutable UI-to-persistence request for one analysis package."""

    scope: str
    destination: Path
    package_format: str
    include_tables: bool
    include_spatial_grids: bool
    include_plots: bool
    frame_count: int
    active_frame_index: int
    source_view: str
    use_segmentation_centroids: bool
    intensity_metric: str
    intensity_unit: str
    background_inner_radius_px: int
    background_outer_radius_px: int
    density_grid_shape: tuple[int, int]
    selected_ranges: MolecularFrameRangeSelection | None = None
    overwrite: bool = False

    def __post_init__(self) -> None:
        scope = str(self.scope).strip().lower()
        if scope not in ("current_frame", "selected_ranges", "full_working_series"):
            raise ValueError(f"Unsupported analysis export scope: {scope!r}.")
        package_format = str(self.package_format).strip().lower()
        if package_format not in ("directory", "zip"):
            raise ValueError("package_format must be 'directory' or 'zip'.")
        destination_text = str(self.destination).strip()
        if not destination_text:
            raise ValueError("Analysis export destination must not be empty.")
        include_tables = bool(self.include_tables)
        include_spatial_grids = bool(self.include_spatial_grids)
        include_plots = bool(self.include_plots)
        if not (include_tables or include_spatial_grids or include_plots):
            raise ValueError("Analysis export must include at least one content type.")
        if include_spatial_grids and scope != "selected_ranges":
            raise ValueError("spatial grids require selected_ranges scope.")

        frame_count = int(self.frame_count)
        active_frame_index = int(self.active_frame_index)
        if frame_count <= 0:
            raise ValueError("frame_count must be positive.")
        if not 0 <= active_frame_index < frame_count:
            raise ValueError("active_frame_index must fit within frame_count.")
        source_view = str(self.source_view).strip()
        if source_view not in ("raw", "expanded_aligned"):
            raise ValueError(f"Unsupported analysis export source_view: {source_view!r}.")
        inner_radius = int(self.background_inner_radius_px)
        outer_radius = int(self.background_outer_radius_px)
        if inner_radius < 0 or outer_radius <= inner_radius:
            raise ValueError("Analysis export background radii are invalid.")
        try:
            rows, columns = (int(value) for value in self.density_grid_shape)
        except (TypeError, ValueError) as exc:
            raise ValueError("density_grid_shape must contain rows and columns.") from exc
        if rows <= 0 or columns <= 0:
            raise ValueError("density_grid_shape values must be positive.")

        selected_ranges = self.selected_ranges
        if scope == "selected_ranges" and selected_ranges is None:
            raise ValueError("selected_ranges scope requires a frame range selection.")
        if selected_ranges is not None:
            if not isinstance(selected_ranges, MolecularFrameRangeSelection):
                raise TypeError("selected_ranges must be a MolecularFrameRangeSelection.")
            if selected_ranges.frame_count != frame_count:
                raise ValueError("selected_ranges frame_count must match frame_count.")
            if selected_ranges.source_view != source_view:
                raise ValueError("selected_ranges source_view must match source_view.")

        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "destination", Path(destination_text))
        object.__setattr__(self, "package_format", package_format)
        object.__setattr__(self, "include_tables", include_tables)
        object.__setattr__(self, "include_spatial_grids", include_spatial_grids)
        object.__setattr__(self, "include_plots", include_plots)
        object.__setattr__(self, "frame_count", frame_count)
        object.__setattr__(self, "active_frame_index", active_frame_index)
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(
            self,
            "use_segmentation_centroids",
            bool(self.use_segmentation_centroids),
        )
        object.__setattr__(self, "intensity_metric", str(self.intensity_metric).strip())
        object.__setattr__(self, "intensity_unit", str(self.intensity_unit))
        object.__setattr__(self, "background_inner_radius_px", inner_radius)
        object.__setattr__(self, "background_outer_radius_px", outer_radius)
        object.__setattr__(self, "density_grid_shape", (rows, columns))
        object.__setattr__(self, "overwrite", bool(self.overwrite))


def export_analysis_package(
    series: MolTrackImageSeries,
    settings: AnalysisExportSettings,
    *,
    progress_callback=None,
) -> AnalysisExportPackageResult:
    """Build and atomically publish one package from an immutable UI request."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    if not isinstance(settings, AnalysisExportSettings):
        raise TypeError("settings must be an AnalysisExportSettings instance.")
    if settings.frame_count != series.frame_count:
        raise ValueError("settings frame_count must match the working series.")
    if settings.active_frame_index != series.active_frame_index:
        raise ValueError("settings active_frame_index must match the working series.")
    destination = settings.destination
    if _path_exists(destination) and not settings.overwrite:
        raise FileExistsError(f"Analysis package destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
        )
    )
    temporary_archive = None
    try:
        def emit(phase: str, completed_count: int = 0, total_count: int = 0) -> None:
            if progress_callback is not None:
                progress_callback(
                    AnalysisExportProgress(
                        phase=phase,
                        completed_count=completed_count,
                        total_count=total_count,
                    )
                )

        emit("preparing")

        def analysis_progress(completed, total, _frame_index) -> None:
            emit("analyzing_frames", completed, total)

        current_analysis = None
        if settings.scope == "full_working_series":
            paths = export_full_working_series_analysis_csv(
                series,
                staging,
                source_view=settings.source_view,
                use_segmentation_centroids=settings.use_segmentation_centroids,
                intensity_metric=settings.intensity_metric,
                intensity_unit=settings.intensity_unit,
                background_inner_radius_px=settings.background_inner_radius_px,
                background_outer_radius_px=settings.background_outer_radius_px,
                progress_callback=analysis_progress,
                phase_callback=emit,
            )
            if not settings.include_tables:
                for path in paths.values():
                    Path(path).unlink()
                paths = {}
        elif settings.scope == "current_frame":
            current_analysis = _analyze_current_frame(
                series,
                settings,
                progress_callback=analysis_progress,
            )
            paths = {}
            if settings.include_tables:
                emit("writing_tables")
                paths = export_current_frame_analysis_csv(
                    series,
                    current_analysis,
                    staging,
                )
        elif settings.scope == "selected_ranges":
            selection = settings.selected_ranges
            if selection is None:
                raise ValueError("selected_ranges scope requires a frame range selection.")
            paths = export_selected_ranges_analysis_csv(
                series,
                selection,
                staging,
                use_segmentation_centroids=settings.use_segmentation_centroids,
                intensity_metric=settings.intensity_metric,
                intensity_unit=settings.intensity_unit,
                background_inner_radius_px=settings.background_inner_radius_px,
                background_outer_radius_px=settings.background_outer_radius_px,
                density_grid_shape=settings.density_grid_shape,
                include_plots=settings.include_plots,
                progress_callback=analysis_progress,
                phase_callback=emit,
            )
            if not settings.include_tables:
                for key in (
                    "molecules_csv",
                    "frames_csv",
                    "ranges_csv",
                    "comparison_csv",
                ):
                    Path(paths.pop(key)).unlink()
            if not settings.include_spatial_grids:
                Path(paths.pop("spatial_bins_csv")).unlink()
        else:
            raise ValueError(
                f"Analysis export scope is not implemented yet: {settings.scope!r}."
            )
        if settings.include_plots and settings.scope != "selected_ranges":
            if current_analysis is None:
                current_analysis = _analyze_current_frame(series, settings)
            emit("rendering_plots")
            from .analysis_plots import export_current_frame_position_plot

            export_current_frame_position_plot(
                current_analysis,
                staging / "plots",
                dpi=150,
                size_inches=(8.0, 6.0),
            )
        record_counts = _record_counts(paths.values())
        manifest_path = staging / "manifest.json"
        if settings.scope == "selected_ranges":
            _update_existing_manifest(
                manifest_path,
                settings,
                record_counts=record_counts,
            )
        else:
            _write_scope_manifest(
                manifest_path,
                series,
                settings,
                record_counts=record_counts,
            )
        relative_files = _relative_package_files(staging)
        if settings.package_format == "directory":
            emit("publishing")
            _publish_path(staging, destination, overwrite=settings.overwrite)
        else:
            emit("packaging_zip")
            file_descriptor, archive_name = tempfile.mkstemp(
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=destination.parent,
            )
            os.close(file_descriptor)
            temporary_archive = Path(archive_name)
            with zipfile.ZipFile(
                temporary_archive,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=6,
            ) as archive:
                for relative_path in relative_files:
                    archive.write(staging / relative_path, arcname=relative_path)
            emit("publishing")
            _publish_path(
                temporary_archive,
                destination,
                overwrite=settings.overwrite,
            )
        emit("complete")
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if temporary_archive is not None and temporary_archive.exists():
            temporary_archive.unlink()
    return AnalysisExportPackageResult(
        package_path=destination,
        package_format=settings.package_format,
        relative_files=relative_files,
        record_counts=record_counts,
    )


def _analyze_current_frame(
    series: MolTrackImageSeries,
    settings: AnalysisExportSettings,
    *,
    progress_callback=None,
):
    return analyze_molecular_frame_range(
        series,
        MolecularFrameRange(
            "Current frame",
            settings.active_frame_index,
            settings.active_frame_index,
        ),
        source_view=settings.source_view,
        use_segmentation_centroids=settings.use_segmentation_centroids,
        intensity_metric=settings.intensity_metric,
        intensity_unit=settings.intensity_unit,
        background_inner_radius_px=settings.background_inner_radius_px,
        background_outer_radius_px=settings.background_outer_radius_px,
        progress_callback=progress_callback,
    ).frame_results[0]


def _record_counts(paths) -> tuple[tuple[str, int], ...]:
    counts = []
    for path in paths:
        path = Path(path)
        if path.suffix.lower() != ".csv":
            continue
        with path.open("r", encoding="utf-8", newline="") as handle:
            record_count = max(0, sum(1 for _row in csv.reader(handle)) - 1)
        counts.append((path.name, record_count))
    return tuple(sorted(counts))


def _write_scope_manifest(
    path: Path,
    series: MolTrackImageSeries,
    settings: AnalysisExportSettings,
    *,
    record_counts: tuple[tuple[str, int], ...],
) -> None:
    payload = {
        "export_schema_version": ANALYSIS_EXPORT_SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "application": {"name": "MolTrack", "version": moltrack_version},
        "scope": settings.scope,
        "source": {"format": "MPP", "file_name": Path(series.source_path).name},
        "working_series": {
            "frame_count": series.frame_count,
            "source_frame_indices": list(series.source_frame_indices),
            "reverse_frame_order": series.reverse_frame_order,
            "active_frame_index": settings.active_frame_index,
        },
        "analysis": {
            "analysis_mode": "frame_position_distributions_without_tracking",
            "uses_tracking": False,
            "source_view": settings.source_view,
            "centroid_mode": (
                "segmentation_centroids_with_bbox_center_fallback"
                if settings.use_segmentation_centroids
                else "bbox_centers"
            ),
            "intensity": {
                "metric": settings.intensity_metric,
                "unit": settings.intensity_unit,
                "background_inner_radius_px": settings.background_inner_radius_px,
                "background_outer_radius_px": settings.background_outer_radius_px,
            },
        },
        "files": _package_file_entries(path.parent, record_counts),
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _update_existing_manifest(
    path: Path,
    settings: AnalysisExportSettings,
    *,
    record_counts: tuple[tuple[str, int], ...],
) -> None:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    payload["scope"] = settings.scope
    payload["files"] = _package_file_entries(path.parent, record_counts)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _package_file_entries(
    root: Path,
    record_counts: tuple[tuple[str, int], ...],
) -> list[dict[str, object]]:
    counts_by_path = dict(record_counts)
    return [
        {
            "path": relative_path,
            "record_count": counts_by_path.get(relative_path),
        }
        for relative_path in sorted(
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file() and path.name != "manifest.json"
        )
    ]


def export_selected_ranges_analysis_package(
    series: MolTrackImageSeries,
    selection: MolecularFrameRangeSelection,
    destination: str | Path,
    *,
    package_format: str = "directory",
    overwrite: bool = False,
    use_segmentation_centroids: bool = True,
    intensity_metric: str = "background_corrected_median",
    intensity_unit: str = "a.u.",
    background_inner_radius_px: int = 1,
    background_outer_radius_px: int = 3,
    density_grid_shape: tuple[int, int] = (32, 32),
    include_plots: bool = False,
    plot_dpi: int = 150,
    plot_size_inches: tuple[float, float] = (8.0, 6.0),
) -> AnalysisExportPackageResult:
    """Build an analysis package in staging and publish it after success."""

    package_format = str(package_format).strip().lower()
    if package_format not in ("directory", "zip"):
        raise ValueError("package_format must be 'directory' or 'zip'.")
    destination = Path(destination)
    overwrite = bool(overwrite)
    if _path_exists(destination) and not overwrite:
        raise FileExistsError(f"Analysis package destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
        )
    )
    temporary_archive = None
    try:
        export_selected_ranges_analysis_csv(
            series,
            selection,
            staging,
            use_segmentation_centroids=use_segmentation_centroids,
            intensity_metric=intensity_metric,
            intensity_unit=intensity_unit,
            background_inner_radius_px=background_inner_radius_px,
            background_outer_radius_px=background_outer_radius_px,
            density_grid_shape=density_grid_shape,
            include_plots=include_plots,
            plot_dpi=plot_dpi,
            plot_size_inches=plot_size_inches,
        )
        relative_files = _relative_package_files(staging)
        if package_format == "directory":
            _publish_path(staging, destination, overwrite=overwrite)
        else:
            file_descriptor, archive_name = tempfile.mkstemp(
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=destination.parent,
            )
            os.close(file_descriptor)
            temporary_archive = Path(archive_name)
            with zipfile.ZipFile(
                temporary_archive,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=6,
            ) as archive:
                for relative_path in relative_files:
                    archive.write(staging / relative_path, arcname=relative_path)
            _publish_path(temporary_archive, destination, overwrite=overwrite)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if temporary_archive is not None and temporary_archive.exists():
            temporary_archive.unlink()
    return AnalysisExportPackageResult(
        package_path=destination,
        package_format=package_format,
        relative_files=relative_files,
    )


def _relative_package_files(root: Path) -> tuple[str, ...]:
    return tuple(
        sorted(
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        )
    )


def _publish_path(staged: Path, destination: Path, *, overwrite: bool) -> None:
    if not _path_exists(destination):
        os.replace(staged, destination)
        return
    if not overwrite:
        raise FileExistsError(f"Analysis package destination already exists: {destination}")

    file_descriptor, backup_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".backup",
        dir=destination.parent,
    )
    os.close(file_descriptor)
    backup = Path(backup_name)
    backup.unlink()
    os.replace(destination, backup)
    try:
        os.replace(staged, destination)
    except BaseException:
        os.replace(backup, destination)
        raise
    else:
        _remove_path(backup)


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif _path_exists(path):
        path.unlink()


def _path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()
