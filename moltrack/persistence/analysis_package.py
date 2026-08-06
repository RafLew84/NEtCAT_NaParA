from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from moltrack import __version__ as moltrack_version
from moltrack.analysis import (
    M6DomainTypeClassificationResult,
    M6DomainTypeRangeComparison,
    M6SingleRangeDomainTypeSummary,
    MolecularFrameAnalysisResult,
    MolecularFrameRange,
    MolecularFrameRangeSelection,
    MolecularM6OrientationAnalysisSettings,
    MolecularOrderHierarchy,
    MolecularOrderTypeClassificationResult,
    MolecularStackingSessionState,
    analyze_molecular_frame_range,
    build_m6_domain_type_range_comparison,
    build_m6_single_range_domain_type_summary,
    extract_m6_domain_type_observations,
)
from moltrack.core import MolTrackImageSeries

from .analysis_export import (
    ANALYSIS_EXPORT_SCHEMA_VERSION,
    build_analysis_source_manifest,
    build_analysis_plots_manifest,
    build_m6_analysis_manifest,
    export_current_frame_analysis_csv,
    export_full_working_series_analysis_csv,
    export_selected_ranges_analysis_csv,
)
from .analysis_environment import (
    resolve_analysis_export_environment,
)
from .m6_domain_type_export import (
    DOMAIN_TYPE_TABLE_FILES,
    M6DomainTypeExportData,
    build_m6_domain_type_export_data,
    write_m6_domain_type_tables,
)
from .molecular_stacking_export import (
    MOLECULAR_STACKING_TABLE_FILES,
    MolecularStackingExportData,
    build_molecular_stacking_export_data,
    write_molecular_stacking_tables,
)
from .molecular_order_type_export import (
    build_molecular_order_type_export_data,
    write_molecular_order_type_tables,
)
from .package_io import (
    path_exists as _path_exists,
    publish_path as _publish_path,
    relative_package_files as _relative_package_files,
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


def _validated_domain_type_m6_settings(
    classification: M6DomainTypeClassificationResult | None,
    *,
    frame_count: int,
    source_view: str,
    m6_settings: MolecularM6OrientationAnalysisSettings | None,
) -> MolecularM6OrientationAnalysisSettings | None:
    if classification is None:
        return m6_settings
    if not isinstance(classification, M6DomainTypeClassificationResult):
        raise TypeError(
            "m6_domain_type_classification must be a domain type result or None."
        )
    if classification.analysis_scope.frame_count != frame_count:
        raise ValueError(
            "Domain type classification frame_count must match the export series."
        )
    if classification.source_view != source_view:
        raise ValueError(
            "Domain type classification source_view must match the export view."
        )
    if m6_settings is None:
        return classification.m6_settings
    if m6_settings != classification.m6_settings:
        raise ValueError(
            "M6 export settings must match the domain type classification."
        )
    return m6_settings


def _validate_domain_type_table_result(
    classification: M6DomainTypeClassificationResult | None,
    table_result: (
        M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison | None
    ),
    *,
    tables_included: bool,
) -> None:
    if table_result is None:
        return
    build_m6_domain_type_export_data(
        classification,
        table_result,
        tables_included=tables_included,
    )


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
    m6_orientation_settings: MolecularM6OrientationAnalysisSettings | None = None
    m6_domain_type_classification: M6DomainTypeClassificationResult | None = None
    m6_domain_type_table_result: (
        M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison | None
    ) = None
    molecular_stacking_state: MolecularStackingSessionState | None = None
    molecular_order_hierarchy: MolecularOrderHierarchy | None = None
    molecular_order_type_classification: (
        MolecularOrderTypeClassificationResult | None
    ) = None

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
        m6_settings = self.m6_orientation_settings
        if m6_settings is not None and not isinstance(
            m6_settings,
            MolecularM6OrientationAnalysisSettings,
        ):
            raise TypeError("m6_orientation_settings must be M6 settings or None.")
        m6_settings = _validated_domain_type_m6_settings(
            self.m6_domain_type_classification,
            frame_count=frame_count,
            source_view=source_view,
            m6_settings=m6_settings,
        )
        _validate_domain_type_table_result(
            self.m6_domain_type_classification,
            self.m6_domain_type_table_result,
            tables_included=include_tables,
        )
        if (
            self.molecular_stacking_state is not None
            and not isinstance(
                self.molecular_stacking_state,
                MolecularStackingSessionState,
            )
        ):
            raise TypeError(
                "molecular_stacking_state must be a stacking session state "
                "or None."
            )
        order_hierarchy = self.molecular_order_hierarchy
        order_classification = self.molecular_order_type_classification
        if (order_hierarchy is None) != (order_classification is None):
            raise ValueError(
                "Molecular-order hierarchy and classification must be "
                "exported together."
            )
        if order_hierarchy is not None:
            if not isinstance(order_hierarchy, MolecularOrderHierarchy):
                raise TypeError(
                    "molecular_order_hierarchy must be a hierarchy or None."
                )
            if not isinstance(
                order_classification,
                MolecularOrderTypeClassificationResult,
            ):
                raise TypeError(
                    "molecular_order_type_classification must be a "
                    "classification result or None."
                )
            if any(
                value >= frame_count
                for value in order_hierarchy.input_frame_indices
            ):
                raise ValueError(
                    "Molecular-order hierarchy exceeds the export series."
                )
            build_molecular_order_type_export_data(
                order_hierarchy,
                order_classification,
                frame_indices=order_hierarchy.input_frame_indices,
                tables_included=include_tables,
            )
            if order_hierarchy.source_view != source_view:
                raise ValueError(
                    "Molecular-order hierarchy source_view must match "
                    "the export view."
                )
            if order_classification.analysis_scope.frame_count != frame_count:
                raise ValueError(
                    "Molecular-order classification frame_count must match "
                    "the export series."
                )
            if order_classification.analysis_scope.source_view != source_view:
                raise ValueError(
                    "Molecular-order classification source_view must match "
                    "the export view."
                )
            if (
                scope == "selected_ranges"
                and selected_ranges is not None
                and order_classification.analysis_scope
                != selected_ranges.to_analysis_scope()
            ):
                raise ValueError(
                    "Molecular-order classification scope must match the "
                    "exported frame ranges."
                )

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
        object.__setattr__(self, "m6_orientation_settings", m6_settings)


def _resolve_domain_type_table_result(
    series: MolTrackImageSeries,
    *,
    classification: M6DomainTypeClassificationResult | None,
    table_result: (
        M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison | None
    ),
    use_segmentation_centroids: bool,
    intensity_metric: str,
    intensity_unit: str,
    background_inner_radius_px: int,
    background_outer_radius_px: int,
) -> M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison | None:
    if classification is None:
        return None
    analyses = tuple(
        analyze_molecular_frame_range(
            series,
            frame_range,
            source_view=classification.source_view,
            use_segmentation_centroids=use_segmentation_centroids,
            intensity_metric=intensity_metric,
            intensity_unit=intensity_unit,
            background_inner_radius_px=background_inner_radius_px,
            background_outer_radius_px=background_outer_radius_px,
            m6_orientation_settings=classification.m6_settings,
        )
        for frame_range in classification.analysis_scope.ranges
    )
    current_observations = tuple(
        sorted(
            (
                observation
                for analysis in analyses
                for observation in extract_m6_domain_type_observations(
                    analysis,
                    settings=classification.classification_settings,
                )
            ),
            key=lambda value: value.stable_key,
        )
    )
    if current_observations != classification.observations:
        return None
    if classification.analysis_scope.analysis_mode == "single_range":
        rebuilt_result = build_m6_single_range_domain_type_summary(
            classification,
            analyses[0],
        )
    else:
        rebuilt_result = build_m6_domain_type_range_comparison(
            classification,
            analyses[0],
            analyses[1],
        )
    return table_result if table_result == rebuilt_result else rebuilt_result


def export_analysis_package(
    series: MolTrackImageSeries,
    settings: AnalysisExportSettings,
    *,
    progress_callback=None,
    environment_provider: Callable[[], Mapping[str, object]] | None = None,
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

        domain_type_export = None
        domain_type_table_result = None
        effective_domain_type_classification = None
        if settings.scope != "selected_ranges":
            domain_type_table_result = _resolve_domain_type_table_result(
                series,
                classification=settings.m6_domain_type_classification,
                table_result=settings.m6_domain_type_table_result,
                use_segmentation_centroids=settings.use_segmentation_centroids,
                intensity_metric=settings.intensity_metric,
                intensity_unit=settings.intensity_unit,
                background_inner_radius_px=settings.background_inner_radius_px,
                background_outer_radius_px=settings.background_outer_radius_px,
            )
            effective_domain_type_classification = (
                settings.m6_domain_type_classification
                if domain_type_table_result is not None
                else None
            )
            domain_type_export = build_m6_domain_type_export_data(
                effective_domain_type_classification,
                domain_type_table_result,
                tables_included=settings.include_tables,
            )

        def analysis_progress(completed, total, _frame_index) -> None:
            emit("analyzing_frames", completed, total)

        current_analysis = None
        manifest_frame_results: tuple[MolecularFrameAnalysisResult, ...] = ()
        if settings.scope == "full_working_series":
            def capture_frame_results(
                frame_results: tuple[MolecularFrameAnalysisResult, ...],
            ) -> None:
                nonlocal manifest_frame_results
                manifest_frame_results = frame_results

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
                m6_orientation_settings=settings.m6_orientation_settings,
                m6_domain_type_classification=(
                    settings.m6_domain_type_classification
                ),
                analysis_results_callback=capture_frame_results,
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
            manifest_frame_results = (current_analysis,)
            paths = {}
            if settings.include_tables:
                emit("writing_tables")
                paths = export_current_frame_analysis_csv(
                    series,
                    current_analysis,
                    staging,
                    use_segmentation_centroids=(
                        settings.use_segmentation_centroids
                    ),
                    m6_domain_type_classification=(
                        settings.m6_domain_type_classification
                    ),
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
                m6_orientation_settings=settings.m6_orientation_settings,
                m6_domain_type_classification=(
                    settings.m6_domain_type_classification
                ),
                m6_domain_type_table_result=(
                    settings.m6_domain_type_table_result
                ),
                molecular_stacking_state=settings.molecular_stacking_state,
                environment_provider=environment_provider,
            )
            if not settings.include_tables:
                for key in (
                    "molecules_csv",
                    "frames_csv",
                    "domains_csv",
                    "lattice_domains_csv",
                    "ranges_csv",
                    "comparison_csv",
                    "domain_types_csv",
                    "domain_type_ranges_csv",
                    "domain_type_comparison_csv",
                    "stacking_molecules_csv",
                    "stacking_domains_csv",
                    "stacking_subdomains_csv",
                ):
                    path = paths.pop(key, None)
                    if path is not None:
                        Path(path).unlink()
            if not settings.include_spatial_grids:
                Path(paths.pop("spatial_bins_csv")).unlink()
        else:
            raise ValueError(
                f"Analysis export scope is not implemented yet: {settings.scope!r}."
            )
        plot_export = None
        if settings.include_plots and settings.scope != "selected_ranges":
            if current_analysis is None:
                current_analysis = _analyze_current_frame(series, settings)
            emit("rendering_plots")
            from .analysis_plots import (
                AnalysisPlotExportResult,
                export_current_frame_position_plot,
                export_m6_domain_type_plots,
            )

            position_paths = export_current_frame_position_plot(
                current_analysis,
                staging / "plots",
                dpi=150,
                size_inches=(8.0, 6.0),
            )
            domain_type_plots = export_m6_domain_type_plots(
                effective_domain_type_classification,
                domain_type_table_result,
                staging / "plots",
                dpi=150,
                size_inches=(8.0, 6.0),
            )
            plot_export = AnalysisPlotExportResult(
                generated=(
                    ("current_frame_positions", position_paths),
                    *domain_type_plots.generated,
                ),
                skipped=domain_type_plots.skipped,
                dpi=150,
                size_inches=(8.0, 6.0),
            )
        if settings.include_tables and settings.scope != "selected_ranges":
            if domain_type_export is None:
                raise RuntimeError("Domain type export data was not prepared.")
            paths.update(
                write_m6_domain_type_tables(staging, domain_type_export)
            )
        stacking_export = build_molecular_stacking_export_data(
            series,
            settings.molecular_stacking_state,
            frame_indices=_stacking_export_frame_indices(settings),
            comparison_ranges=_stacking_export_comparison_ranges(settings),
            expected_source_view=settings.source_view,
        )
        if (
            settings.include_tables
            and stacking_export.available
            and settings.scope != "selected_ranges"
        ):
            paths.update(
                write_molecular_stacking_tables(staging, stacking_export)
            )
        stacking_manifest = _stacking_export_manifest(
            stacking_export,
            tables_included=settings.include_tables,
        )
        order_type_export = build_molecular_order_type_export_data(
            settings.molecular_order_hierarchy,
            settings.molecular_order_type_classification,
            frame_indices=_molecular_order_export_frame_indices(settings),
            tables_included=settings.include_tables,
        )
        if settings.include_tables and order_type_export.available:
            paths.update(
                write_molecular_order_type_tables(
                    staging,
                    order_type_export,
                )
            )
        record_counts = _record_counts(paths.values())
        manifest_path = staging / "manifest.json"
        if settings.scope == "selected_ranges":
            _update_existing_manifest(
                manifest_path,
                settings,
                record_counts=record_counts,
                stacking_manifest=stacking_manifest,
                order_type_manifest=order_type_export.manifest,
            )
        else:
            if domain_type_export is None:
                raise RuntimeError("Domain type export data was not prepared.")
            _write_scope_manifest(
                manifest_path,
                series,
                settings,
                record_counts=record_counts,
                frame_results=manifest_frame_results,
                domain_type_export=domain_type_export,
                stacking_manifest=stacking_manifest,
                order_type_manifest=order_type_export.manifest,
                plot_export=plot_export,
                environment_provider=environment_provider,
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
        m6_orientation_settings=settings.m6_orientation_settings,
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
    frame_results: tuple[MolecularFrameAnalysisResult, ...],
    domain_type_export: M6DomainTypeExportData,
    stacking_manifest: Mapping[str, object],
    order_type_manifest: Mapping[str, object],
    plot_export,
    environment_provider: Callable[[], Mapping[str, object]] | None,
) -> None:
    payload = {
        "export_schema_version": ANALYSIS_EXPORT_SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "application": {"name": "MolTrack", "version": moltrack_version},
        "environment": resolve_analysis_export_environment(environment_provider),
        "scope": settings.scope,
        "source": build_analysis_source_manifest(series, path.parent),
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
            "analysis_coordinate_context": (
                "registered"
                if settings.source_view == "expanded_aligned"
                else "native"
            ),
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
            "m6_orientation": build_m6_analysis_manifest(
                series,
                frame_results,
                requested_settings=settings.m6_orientation_settings,
                use_segmentation_centroids=settings.use_segmentation_centroids,
                source_view=settings.source_view,
            ),
            "m6_domain_types": dict(domain_type_export.manifest),
            "molecular_stacking": dict(stacking_manifest),
            "molecular_order_types": dict(order_type_manifest),
        },
        "plots": build_analysis_plots_manifest(plot_export, path.parent),
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
    stacking_manifest: Mapping[str, object],
    order_type_manifest: Mapping[str, object],
) -> None:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    payload["scope"] = settings.scope
    payload["export_schema_version"] = ANALYSIS_EXPORT_SCHEMA_VERSION
    domain_type_manifest = payload["analysis"]["m6_domain_types"]
    domain_type_manifest["tables_included"] = settings.include_tables
    domain_type_manifest["table_files"] = (
        list(DOMAIN_TYPE_TABLE_FILES)
        if settings.include_tables
        else []
    )
    payload["analysis"]["molecular_stacking"] = dict(stacking_manifest)
    payload["analysis"]["molecular_order_types"] = dict(
        order_type_manifest
    )
    payload["files"] = _package_file_entries(path.parent, record_counts)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _stacking_export_frame_indices(
    settings: AnalysisExportSettings,
) -> tuple[int, ...]:
    if settings.scope == "current_frame":
        return (settings.active_frame_index,)
    if settings.scope == "full_working_series":
        return tuple(range(settings.frame_count))
    selection = settings.selected_ranges
    if selection is None:
        raise ValueError("selected_ranges stacking export requires ranges.")
    return tuple(
        sorted(
            {
                *selection.first_range.frame_indices,
                *selection.second_range.frame_indices,
            }
        )
    )


def _stacking_export_comparison_ranges(
    settings: AnalysisExportSettings,
) -> tuple[MolecularFrameRange, MolecularFrameRange] | None:
    selection = settings.selected_ranges
    if settings.scope != "selected_ranges" or selection is None:
        return None
    return selection.first_range, selection.second_range


def _molecular_order_export_frame_indices(
    settings: AnalysisExportSettings,
) -> tuple[int, ...]:
    hierarchy = settings.molecular_order_hierarchy
    if hierarchy is None:
        return _stacking_export_frame_indices(settings)
    requested = set(_stacking_export_frame_indices(settings))
    return tuple(
        value
        for value in hierarchy.input_frame_indices
        if value in requested
    )


def _stacking_export_manifest(
    export_data: MolecularStackingExportData,
    *,
    tables_included: bool,
) -> dict[str, object]:
    manifest = dict(export_data.manifest)
    manifest["tables_included"] = bool(
        tables_included and export_data.available
    )
    manifest["tables"] = (
        list(MOLECULAR_STACKING_TABLE_FILES)
        if tables_included and export_data.available
        else []
    )
    return manifest


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
    m6_orientation_settings: MolecularM6OrientationAnalysisSettings | None = None,
    m6_domain_type_classification: M6DomainTypeClassificationResult | None = None,
    m6_domain_type_table_result: (
        M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison | None
    ) = None,
    molecular_stacking_state: MolecularStackingSessionState | None = None,
    environment_provider: Callable[[], Mapping[str, object]] | None = None,
) -> AnalysisExportPackageResult:
    """Build an analysis package in staging and publish it after success."""

    package_format = str(package_format).strip().lower()
    if package_format not in ("directory", "zip"):
        raise ValueError("package_format must be 'directory' or 'zip'.")
    m6_orientation_settings = _validated_domain_type_m6_settings(
        m6_domain_type_classification,
        frame_count=series.frame_count,
        source_view=selection.source_view,
        m6_settings=m6_orientation_settings,
    )
    _validate_domain_type_table_result(
        m6_domain_type_classification,
        m6_domain_type_table_result,
        tables_included=True,
    )
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
            m6_orientation_settings=m6_orientation_settings,
            m6_domain_type_classification=m6_domain_type_classification,
            m6_domain_type_table_result=m6_domain_type_table_result,
            molecular_stacking_state=molecular_stacking_state,
            environment_provider=environment_provider,
        )
        record_counts = _record_counts(staging.rglob("*.csv"))
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
        record_counts=record_counts,
    )
