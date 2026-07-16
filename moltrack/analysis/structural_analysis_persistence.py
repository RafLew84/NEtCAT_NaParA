from __future__ import annotations

from dataclasses import dataclass

from moltrack.core import (
    MolTrackImageSeries,
    build_molecular_centroids,
)

from .m6_headless_validation_manifest import M6_ORIENTATION_ALGORITHM_VERSION
from .m6_settings import MolecularM6OrientationAnalysisSettings
from .sample_coordinates import (
    MolecularSampleCoordinates,
    build_molecular_sample_coordinates,
)
from .structural_analysis_cache import (
    StructuralAnalysisCache,
    StructuralAnalysisCacheKey,
    build_structural_analysis_cache_key,
)


@dataclass(frozen=True)
class StructuralAnalysisCacheRecord:
    """Safe, reproducible representation of one persisted M6 cache entry."""

    cache_key: StructuralAnalysisCacheKey
    sample_coordinates: MolecularSampleCoordinates
    settings: MolecularM6OrientationAnalysisSettings

    def __post_init__(self) -> None:
        if not isinstance(self.cache_key, StructuralAnalysisCacheKey):
            raise TypeError("cache_key must be StructuralAnalysisCacheKey.")
        if not isinstance(self.sample_coordinates, MolecularSampleCoordinates):
            raise TypeError("sample_coordinates must be MolecularSampleCoordinates.")
        if not isinstance(self.settings, MolecularM6OrientationAnalysisSettings):
            raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")


@dataclass(frozen=True)
class StructuralAnalysisCacheRestoreStats:
    restored_count: int
    incompatible_count: int
    skipped_count: int


def export_structural_analysis_cache_records(
    series: MolTrackImageSeries,
) -> tuple[StructuralAnalysisCacheRecord, ...]:
    """Export successful cache entries without serializing executable objects."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    cache = series.structural_analysis_cache
    if not isinstance(cache, StructuralAnalysisCache):
        return ()
    records_by_key = {
        key: StructuralAnalysisCacheRecord(
            cache_key=key,
            sample_coordinates=sample_coordinates,
            settings=settings,
        )
        for key, sample_coordinates, settings in cache._reproducible_entries()
    }
    records_by_key.update(
        {
            key: StructuralAnalysisCacheRecord(
                cache_key=key,
                sample_coordinates=analysis.sample_coordinates,
                settings=analysis.settings,
            )
            for key, analysis in cache._successful_entries()
        }
    )
    return tuple(records_by_key.values())


def restore_structural_analysis_cache_records(
    series: MolTrackImageSeries,
    records: tuple[StructuralAnalysisCacheRecord, ...],
) -> StructuralAnalysisCacheRestoreStats:
    """Restore compatible reproducible inputs without blocking session opening."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    records = tuple(records)
    if not all(isinstance(record, StructuralAnalysisCacheRecord) for record in records):
        raise TypeError("records must contain StructuralAnalysisCacheRecord instances.")
    if not records:
        series.structural_analysis_cache = None
        return StructuralAnalysisCacheRestoreStats(0, 0, 0)

    cache = StructuralAnalysisCache()
    series.structural_analysis_cache = cache
    restored_count = 0
    incompatible_count = 0
    skipped_count = 0
    source_positions = {
        int(source_index): position
        for position, source_index in enumerate(series.source_frame_indices)
    }
    for record in records:
        if (
            record.cache_key.source_view == "expanded_aligned"
            and series.expanded_aligned_stack is None
        ):
            if series.registration_results is None:
                skipped_count += 1
                continue
            cache._put_reproducible(
                record.cache_key,
                record.sample_coordinates,
                record.settings,
            )
            restored_count += 1
            continue
        try:
            source_index = int(record.cache_key.frame_id.removeprefix("source-frame-"))
            frame_index = source_positions[source_index]
            use_segmentation_centroids = (
                record.cache_key.centroid_mode == "segmentation_preferred"
            )
            centroids = build_molecular_centroids(
                series,
                frame_index=frame_index,
                source_view=record.cache_key.source_view,
                use_segmentation_centroids=use_segmentation_centroids,
            )
            current_sample = build_molecular_sample_coordinates(
                series,
                centroids,
                frame_index=frame_index,
                source_view=record.cache_key.source_view,
            )
            current_key = build_structural_analysis_cache_key(
                series,
                current_sample,
                use_segmentation_centroids=use_segmentation_centroids,
                settings=record.settings,
                algorithm_version=M6_ORIENTATION_ALGORITHM_VERSION,
            )
        except (IndexError, KeyError, TypeError, ValueError):
            skipped_count += 1
            continue
        if current_key != record.cache_key:
            incompatible_count += 1
            continue
        cache._put_reproducible(
            current_key,
            current_sample,
            record.settings,
        )
        restored_count += 1
    return StructuralAnalysisCacheRestoreStats(
        restored_count=restored_count,
        incompatible_count=incompatible_count,
        skipped_count=skipped_count,
    )
