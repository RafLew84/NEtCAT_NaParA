from __future__ import annotations

from collections.abc import Mapping
from collections import OrderedDict
from dataclasses import dataclass, fields, is_dataclass
import hashlib
import json
from numbers import Integral
import sys
from typing import Callable, Literal

import numpy as np

from moltrack.core import MolTrackImageSeries

from .m6_errors import M6BlockingGraphQCError
from .m6_headless_validation_manifest import M6_ORIENTATION_ALGORITHM_VERSION
from .m6_settings import MolecularM6OrientationAnalysisSettings
from .molecular_m6_analysis import (
    MolecularM6OrientationAnalysis,
    analyze_molecular_m6_orientation,
    attach_lattice_domain_analysis,
)
from .lattice_domain_models import lattice_domain_analysis_fingerprint
from .sample_coordinates import (
    SAMPLE_COORDINATE_TRANSFORM_VERSION,
    MolecularSampleCoordinates,
)


StructuralCentroidMode = Literal["segmentation_preferred", "bbox_centers"]

DEFAULT_STRUCTURAL_CACHE_MAX_ENTRIES = 64
DEFAULT_STRUCTURAL_CACHE_MAX_BYTES = 256 * 1024 * 1024


@dataclass(frozen=True)
class StructuralAnalysisCacheKey:
    """Complete identity of one reusable M6 frame analysis."""

    frame_id: str
    source_view: str
    centroid_mode: StructuralCentroidMode
    annotation_fingerprint: str
    registration_fingerprint: str
    spatial_calibration_fingerprint: str
    coordinate_transform_fingerprint: str
    sample_geometry_fingerprint: str
    valid_fov_fingerprint: str
    settings_hash: str
    algorithm_version: str

    def __post_init__(self) -> None:
        for field_name in (
            "frame_id",
            "source_view",
            "annotation_fingerprint",
            "registration_fingerprint",
            "spatial_calibration_fingerprint",
            "coordinate_transform_fingerprint",
            "sample_geometry_fingerprint",
            "valid_fov_fingerprint",
            "settings_hash",
            "algorithm_version",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string.")
        if self.source_view not in {"raw", "expanded_aligned"}:
            raise ValueError("Unsupported structural cache source_view.")
        if self.centroid_mode not in {"segmentation_preferred", "bbox_centers"}:
            raise ValueError("Unsupported structural cache centroid_mode.")

    @property
    def frame_context(self) -> tuple[str, str, StructuralCentroidMode]:
        return self.frame_id, self.source_view, self.centroid_mode

    @property
    def structural_input_context(self) -> tuple[str, ...]:
        return (
            self.frame_id,
            self.source_view,
            self.centroid_mode,
            self.annotation_fingerprint,
            self.registration_fingerprint,
            self.spatial_calibration_fingerprint,
            self.coordinate_transform_fingerprint,
            self.sample_geometry_fingerprint,
            self.valid_fov_fingerprint,
        )


@dataclass(frozen=True)
class StructuralAnalysisCacheStats:
    """Observable LRU counters and current structural-cache footprint."""

    entry_count: int
    estimated_bytes: int
    max_entries: int
    max_bytes: int
    hit_count: int
    miss_count: int
    eviction_count: int
    oversized_rejection_count: int


@dataclass(frozen=True)
class _StructuralAnalysisCacheEntry:
    analysis: MolecularM6OrientationAnalysis | None
    blocking_qc_status: str | None
    reproducible_sample: MolecularSampleCoordinates | None
    reproducible_settings: MolecularM6OrientationAnalysisSettings | None
    expected_lattice_domain_result_fingerprint: str | None
    estimated_bytes: int

    def __post_init__(self) -> None:
        modes = (
            self.analysis is not None,
            self.blocking_qc_status is not None,
            self.reproducible_sample is not None,
        )
        if sum(modes) != 1:
            raise ValueError(
                "Cache entry requires analysis, blocking QC, or reproducible input."
            )
        if (self.reproducible_sample is None) != (
            self.reproducible_settings is None
        ):
            raise ValueError(
                "Reproducible sample and settings must be stored together."
            )
        expected = self.expected_lattice_domain_result_fingerprint
        if expected is not None and (
            self.reproducible_sample is None
            or len(expected) != 64
            or any(character not in "0123456789abcdef" for character in expected)
        ):
            raise ValueError(
                "Expected lattice-domain fingerprint requires reproducible input."
            )


class StructuralAnalysisCache:
    """Per-series LRU cache bounded by entry count and estimated serialized bytes."""

    def __init__(
        self,
        *,
        max_entries: int = DEFAULT_STRUCTURAL_CACHE_MAX_ENTRIES,
        max_bytes: int = DEFAULT_STRUCTURAL_CACHE_MAX_BYTES,
    ) -> None:
        if (
            not isinstance(max_entries, Integral)
            or isinstance(max_entries, bool)
            or max_entries <= 0
        ):
            raise ValueError("max_entries must be a positive integer.")
        if not isinstance(max_bytes, Integral) or isinstance(max_bytes, bool) or max_bytes <= 0:
            raise ValueError("max_bytes must be a positive integer.")
        self.max_entries = int(max_entries)
        self.max_bytes = int(max_bytes)
        self._entries: OrderedDict[
            StructuralAnalysisCacheKey,
            _StructuralAnalysisCacheEntry,
        ] = OrderedDict()
        self._estimated_bytes = 0
        self._hit_count = 0
        self._miss_count = 0
        self._eviction_count = 0
        self._oversized_rejection_count = 0

    def get(
        self,
        key: StructuralAnalysisCacheKey,
    ) -> MolecularM6OrientationAnalysis | None:
        if not isinstance(key, StructuralAnalysisCacheKey):
            raise TypeError("key must be a StructuralAnalysisCacheKey.")
        entry = self._entries.get(key)
        if entry is None:
            self._miss_count += 1
            return None
        if entry.reproducible_sample is not None:
            self._miss_count += 1
            return None
        if entry.analysis is not None and entry.analysis.local_multisymmetry_order is None:
            self._entries.pop(key)
            self._estimated_bytes -= entry.estimated_bytes
            self._miss_count += 1
            return None
        if (
            entry.analysis is not None
            and (
                entry.analysis.lattice_domain_seed_growth is None
                or entry.analysis.lattice_domain_analysis is None
            )
        ):
            upgraded = attach_lattice_domain_analysis(entry.analysis)
            upgraded_size = _estimate_cache_entry_bytes(key, upgraded)
            self._estimated_bytes -= entry.estimated_bytes
            if upgraded_size > self.max_bytes:
                self._entries.pop(key)
                self._oversized_rejection_count += 1
                self._hit_count += 1
                return upgraded
            else:
                entry = _StructuralAnalysisCacheEntry(
                    analysis=upgraded,
                    blocking_qc_status=None,
                    reproducible_sample=None,
                    reproducible_settings=None,
                    expected_lattice_domain_result_fingerprint=None,
                    estimated_bytes=upgraded_size,
                )
                self._entries[key] = entry
                self._estimated_bytes += upgraded_size
        self._entries.move_to_end(key)
        self._hit_count += 1
        if entry.blocking_qc_status is not None:
            raise M6BlockingGraphQCError(entry.blocking_qc_status)
        assert entry.analysis is not None
        return entry.analysis

    def _put(
        self,
        key: StructuralAnalysisCacheKey,
        analysis: MolecularM6OrientationAnalysis,
    ) -> bool:
        if not isinstance(key, StructuralAnalysisCacheKey):
            raise TypeError("key must be a StructuralAnalysisCacheKey.")
        if not isinstance(analysis, MolecularM6OrientationAnalysis):
            raise TypeError("analysis must be a MolecularM6OrientationAnalysis.")
        _validate_analysis_matches_key(analysis, key)
        estimated_bytes = _estimate_cache_entry_bytes(key, analysis)
        return self._store(
            key,
            _StructuralAnalysisCacheEntry(
                analysis=analysis,
                blocking_qc_status=None,
                reproducible_sample=None,
                reproducible_settings=None,
                expected_lattice_domain_result_fingerprint=None,
                estimated_bytes=estimated_bytes,
            ),
        )

    def _put_blocking(
        self,
        key: StructuralAnalysisCacheKey,
        qc_status: str,
    ) -> bool:
        if not isinstance(key, StructuralAnalysisCacheKey):
            raise TypeError("key must be a StructuralAnalysisCacheKey.")
        qc_status = str(qc_status).strip()
        if not qc_status.startswith("blocking_"):
            raise ValueError("qc_status must identify blocking graph QC.")
        return self._store(
            key,
            _StructuralAnalysisCacheEntry(
                analysis=None,
                blocking_qc_status=qc_status,
                reproducible_sample=None,
                reproducible_settings=None,
                expected_lattice_domain_result_fingerprint=None,
                estimated_bytes=_estimate_blocking_entry_bytes(key, qc_status),
            ),
        )

    def _put_reproducible(
        self,
        key: StructuralAnalysisCacheKey,
        sample_coordinates: MolecularSampleCoordinates,
        settings: MolecularM6OrientationAnalysisSettings,
        *,
        expected_lattice_domain_result_fingerprint: str | None = None,
    ) -> bool:
        if not isinstance(key, StructuralAnalysisCacheKey):
            raise TypeError("key must be a StructuralAnalysisCacheKey.")
        if not isinstance(sample_coordinates, MolecularSampleCoordinates):
            raise TypeError("sample_coordinates must be MolecularSampleCoordinates.")
        if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
            raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
        return self._store(
            key,
            _StructuralAnalysisCacheEntry(
                analysis=None,
                blocking_qc_status=None,
                reproducible_sample=sample_coordinates,
                reproducible_settings=settings,
                expected_lattice_domain_result_fingerprint=(
                    expected_lattice_domain_result_fingerprint
                ),
                estimated_bytes=_estimate_reproducible_entry_bytes(
                    key,
                    sample_coordinates,
                    settings,
                ),
            ),
        )

    def clear(self) -> None:
        self._entries.clear()
        self._estimated_bytes = 0

    def keys(self) -> tuple[StructuralAnalysisCacheKey, ...]:
        return tuple(self._entries)

    def _expected_lattice_domain_result_fingerprint(
        self,
        key: StructuralAnalysisCacheKey,
    ) -> str | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        return entry.expected_lattice_domain_result_fingerprint

    def _successful_entries(
        self,
    ) -> tuple[tuple[StructuralAnalysisCacheKey, MolecularM6OrientationAnalysis], ...]:
        return tuple(
            (key, entry.analysis)
            for key, entry in self._entries.items()
            if entry.analysis is not None
        )

    def _reproducible_entries(
        self,
    ) -> tuple[
        tuple[
            StructuralAnalysisCacheKey,
            MolecularSampleCoordinates,
            MolecularM6OrientationAnalysisSettings,
            str | None,
        ],
        ...,
    ]:
        return tuple(
            (
                key,
                entry.reproducible_sample,
                entry.reproducible_settings,
                entry.expected_lattice_domain_result_fingerprint,
            )
            for key, entry in self._entries.items()
            if entry.reproducible_sample is not None
            and entry.reproducible_settings is not None
        )

    def stats(self) -> StructuralAnalysisCacheStats:
        return StructuralAnalysisCacheStats(
            entry_count=len(self._entries),
            estimated_bytes=self._estimated_bytes,
            max_entries=self.max_entries,
            max_bytes=self.max_bytes,
            hit_count=self._hit_count,
            miss_count=self._miss_count,
            eviction_count=self._eviction_count,
            oversized_rejection_count=self._oversized_rejection_count,
        )

    def _evict_to_limits(self) -> None:
        while (
            len(self._entries) > self.max_entries
            or self._estimated_bytes > self.max_bytes
        ):
            _key, entry = self._entries.popitem(last=False)
            self._estimated_bytes -= entry.estimated_bytes
            self._eviction_count += 1

    def _store(
        self,
        key: StructuralAnalysisCacheKey,
        entry: _StructuralAnalysisCacheEntry,
    ) -> bool:
        if entry.estimated_bytes > self.max_bytes:
            self._oversized_rejection_count += 1
            return False
        stale_keys = tuple(
            existing_key
            for existing_key in self._entries
            if existing_key != key
            and existing_key.frame_context == key.frame_context
            and existing_key.structural_input_context
            != key.structural_input_context
        )
        for stale_key in stale_keys:
            self._remove(stale_key)
        existing = self._entries.pop(key, None)
        if existing is not None:
            self._estimated_bytes -= existing.estimated_bytes
        self._entries[key] = entry
        self._estimated_bytes += entry.estimated_bytes
        self._evict_to_limits()
        return key in self._entries

    def _remove(self, key: StructuralAnalysisCacheKey) -> None:
        entry = self._entries.pop(key, None)
        if entry is not None:
            self._estimated_bytes -= entry.estimated_bytes


def build_structural_analysis_cache_key(
    series: MolTrackImageSeries,
    sample_coordinates: MolecularSampleCoordinates,
    *,
    use_segmentation_centroids: bool,
    settings: MolecularM6OrientationAnalysisSettings,
    algorithm_version: str = M6_ORIENTATION_ALGORITHM_VERSION,
) -> StructuralAnalysisCacheKey:
    """Build the exact reuse identity for one transformed M6 frame input."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    if not isinstance(sample_coordinates, MolecularSampleCoordinates):
        raise TypeError("sample_coordinates must be MolecularSampleCoordinates.")
    frame_index = sample_coordinates.frame_index
    series.get_frame(frame_index)
    source_frame_index = int(series.source_frame_indices[frame_index])
    centroid_mode: StructuralCentroidMode = (
        "segmentation_preferred"
        if bool(use_segmentation_centroids)
        else "bbox_centers"
    )
    return StructuralAnalysisCacheKey(
        frame_id=f"source-frame-{source_frame_index}",
        source_view=sample_coordinates.source_view,
        centroid_mode=centroid_mode,
        annotation_fingerprint=_annotation_fingerprint(
            sample_coordinates,
        ),
        registration_fingerprint=sample_coordinates.registration_fingerprint,
        spatial_calibration_fingerprint=(
            sample_coordinates.spatial_calibration_fingerprint
        ),
        coordinate_transform_fingerprint=(
            sample_coordinates.coordinate_transform_fingerprint
        ),
        sample_geometry_fingerprint=_sample_geometry_fingerprint(
            sample_coordinates
        ),
        valid_fov_fingerprint=_valid_fov_fingerprint(sample_coordinates),
        settings_hash=structural_analysis_settings_hash(settings),
        algorithm_version=str(algorithm_version).strip(),
    )


def structural_analysis_settings_hash(
    settings: MolecularM6OrientationAnalysisSettings,
) -> str:
    """Hash every M6 setting together with the coordinate convention version."""

    if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
        raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
    return _fingerprint(
        {
            "m6_settings": settings.to_dict(),
            "coordinate_frame": "sample_nm",
            "coordinate_transform_version": SAMPLE_COORDINATE_TRANSFORM_VERSION,
        }
    )


def _get_or_compute_molecular_m6_orientation(
    series: MolTrackImageSeries,
    sample_coordinates: MolecularSampleCoordinates,
    *,
    use_segmentation_centroids: bool,
    settings: MolecularM6OrientationAnalysisSettings,
    algorithm_version: str = M6_ORIENTATION_ALGORITHM_VERSION,
    analysis_factory: Callable[..., MolecularM6OrientationAnalysis] = (
        analyze_molecular_m6_orientation
    ),
) -> MolecularM6OrientationAnalysis:
    """Reuse M6 for sample coordinates freshly built from current annotations."""

    key = build_structural_analysis_cache_key(
        series,
        sample_coordinates,
        use_segmentation_centroids=use_segmentation_centroids,
        settings=settings,
        algorithm_version=algorithm_version,
    )
    cache = series.structural_analysis_cache
    if not isinstance(cache, StructuralAnalysisCache):
        cache = StructuralAnalysisCache()
        series.structural_analysis_cache = cache
    cached = cache.get(key)
    if cached is not None:
        return cached
    expected_lattice_fingerprint = (
        cache._expected_lattice_domain_result_fingerprint(key)
    )
    try:
        analysis = analysis_factory(sample_coordinates, settings=settings)
    except M6BlockingGraphQCError as error:
        cache._put_blocking(key, error.qc_status)
        raise
    if expected_lattice_fingerprint is not None:
        lattice_analysis = analysis.lattice_domain_analysis
        if (
            lattice_analysis is None
            or lattice_domain_analysis_fingerprint(lattice_analysis)
            != expected_lattice_fingerprint
        ):
            cache._remove(key)
            raise ValueError(
                "Recomputed lattice-domain result does not match the saved cache fingerprint."
            )
    cache._put(key, analysis)
    return analysis


def _annotation_fingerprint(
    sample_coordinates: MolecularSampleCoordinates,
) -> str:
    return _fingerprint(
        tuple(
            (source_id, source_kind, annotation_fingerprint)
            for source_id, source_kind, annotation_fingerprint in zip(
                sample_coordinates.point_source_ids,
                sample_coordinates.point_source_kinds,
                sample_coordinates.point_annotation_fingerprints,
            )
        )
    )


def _fingerprint(payload: object) -> str:
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(serialized).hexdigest()


def _estimate_cache_entry_bytes(
    key: StructuralAnalysisCacheKey,
    analysis: MolecularM6OrientationAnalysis,
) -> int:
    seen: set[int] = set()
    return (
        _deep_size_bytes(key, seen)
        + _deep_size_bytes(analysis, seen)
        + 256
    )


def _estimate_blocking_entry_bytes(
    key: StructuralAnalysisCacheKey,
    qc_status: str,
) -> int:
    seen: set[int] = set()
    return (
        _deep_size_bytes(key, seen)
        + _deep_size_bytes(qc_status, seen)
        + 256
    )


def _estimate_reproducible_entry_bytes(
    key: StructuralAnalysisCacheKey,
    sample_coordinates: MolecularSampleCoordinates,
    settings: MolecularM6OrientationAnalysisSettings,
) -> int:
    seen: set[int] = set()
    return (
        _deep_size_bytes(key, seen)
        + _deep_size_bytes(sample_coordinates, seen)
        + _deep_size_bytes(settings, seen)
        + 256
    )


def _deep_size_bytes(value: object, seen: set[int] | None = None) -> int:
    if seen is None:
        seen = set()
    identity = id(value)
    if identity in seen:
        return 0
    seen.add(identity)
    size = sys.getsizeof(value)
    if isinstance(value, np.ndarray):
        if value.flags.owndata or value.base is None:
            return size
        return size + _deep_size_bytes(value.base, seen)
    if is_dataclass(value) and not isinstance(value, type):
        return size + sum(
            _deep_size_bytes(getattr(value, field.name), seen)
            for field in fields(value)
        )
    if isinstance(value, Mapping):
        return size + sum(
            _deep_size_bytes(key, seen) + _deep_size_bytes(item, seen)
            for key, item in value.items()
        )
    if isinstance(value, (tuple, list, set, frozenset, OrderedDict)):
        return size + sum(_deep_size_bytes(item, seen) for item in value)
    return size


def _validate_analysis_matches_key(
    analysis: MolecularM6OrientationAnalysis,
    key: StructuralAnalysisCacheKey,
) -> None:
    if (
        analysis.source_view != key.source_view
        or analysis.registration_fingerprint != key.registration_fingerprint
        or analysis.spatial_calibration_fingerprint
        != key.spatial_calibration_fingerprint
        or analysis.coordinate_transform_fingerprint
        != key.coordinate_transform_fingerprint
        or _sample_geometry_fingerprint(analysis.sample_coordinates)
        != key.sample_geometry_fingerprint
        or structural_analysis_settings_hash(analysis.settings) != key.settings_hash
        or _valid_fov_fingerprint(analysis.sample_coordinates)
        != key.valid_fov_fingerprint
    ):
        raise ValueError("Cached M6 analysis context must match its cache key.")


def _sample_geometry_fingerprint(
    sample_coordinates: MolecularSampleCoordinates,
) -> str:
    return _fingerprint(
        {
            "frame_index": sample_coordinates.frame_index,
            "point_source_ids": sample_coordinates.point_source_ids,
            "point_source_kinds": sample_coordinates.point_source_kinds,
            "point_annotation_fingerprints": (
                sample_coordinates.point_annotation_fingerprints
            ),
            "source_points_xy_px": sample_coordinates.source_points_xy_px,
            "points_xy_nm": sample_coordinates.points_xy_nm,
            "distance_to_valid_fov_boundary_nm": (
                sample_coordinates.distance_to_valid_fov_boundary_nm
            ),
            "coordinate_frame": sample_coordinates.coordinate_frame,
            "orientation_reference": sample_coordinates.orientation_reference,
        }
    )


def _valid_fov_fingerprint(
    sample_coordinates: MolecularSampleCoordinates,
) -> str:
    return _fingerprint(
        {
            "valid_fov_polygon_xy_nm": (
                sample_coordinates.valid_fov_polygon_xy_nm
            ),
            "window_side_lengths_nm": sample_coordinates.window_side_lengths_nm,
        }
    )
