import hashlib
import json
import math
import sys
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

import numpy as np

from moltrack.analysis import (
    M6_ORIENTATION_ALGORITHM_VERSION,
    SAMPLE_COORDINATE_TRANSFORM_VERSION,
    MolecularFrameRange,
    MolecularM6OrientationAnalysisSettings,
    StructuralAnalysisCacheKey,
    analyze_molecular_frame_range,
    analyze_molecular_m6_orientation,
    build_molecular_sample_coordinates,
    build_structural_analysis_cache_key,
)
from moltrack.analysis.m6_errors import M6BlockingGraphQCError
from moltrack.analysis.structural_analysis_cache import (
    StructuralAnalysisCache,
    _deep_size_bytes,
    _get_or_compute_molecular_m6_orientation,
)
from moltrack.core import (
    MolecularDetection,
    MolecularDetectionSet,
    MolecularSegmentation,
    MolecularSegmentationSet,
    MolTrackImageSeries,
    build_molecular_centroids,
)
from nanotrack.core import STMSequenceMetadata


def _triangular_patch(*, width: int = 5, height: int = 5) -> np.ndarray:
    return np.asarray(
        [
            (6.0 + 2.0 * (column + 0.5 * (row % 2)), 6.0 + math.sqrt(3.0) * row)
            for row in range(height)
            for column in range(width)
        ],
        dtype=np.float64,
    )


def _settings() -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings(
        first_shell_r_min_nm=1.5,
        first_shell_r_max_nm=2.3,
        min_ordered_component_size=3,
        min_seed_size=5,
        min_domain_size=8,
        footprint_support_radius_nm=1.2,
        gr_bin_width_nm=0.25,
        gr_max_nm=10.0,
        gr_min_expected_pair_exposure=0.1,
    )


def _build_series(frame_count: int = 2) -> MolTrackImageSeries:
    frame_size = 40
    points = _triangular_patch()
    detections = MolecularDetectionSet(frame_count=frame_count)
    for frame_index in range(frame_count):
        detections.set_detections(
            frame_index,
            [
                MolecularDetection(
                    frame_index=frame_index,
                    bbox_xyxy=(
                        x - 0.2,
                        frame_size - y - 0.2,
                        x + 0.2,
                        frame_size - y + 0.2,
                    ),
                    confidence=0.9,
                    detection_id=f"frame-{frame_index}-point-{point_index}",
                )
                for point_index, (x, y) in enumerate(points)
            ],
            source_view="raw",
            frame_shape=(frame_size, frame_size),
        )
    return MolTrackImageSeries(
        source_path="movie.mpp",
        raw_frames=np.zeros((frame_count, frame_size, frame_size), dtype=np.float32),
        metadata=STMSequenceMetadata(
            raw_header={"General Info": {"Angle": "0.0"}},
            pixels_x=frame_size,
            pixels_y=frame_size,
            size_nm_x=float(frame_size),
            size_nm_y=float(frame_size),
            scan_angle_deg=0.0,
        ),
        molecular_detections=detections,
    )


def _sample(series: MolTrackImageSeries, frame_index: int = 0):
    centroids = tuple(
        build_molecular_centroids(
            series,
            frame_index=frame_index,
            source_view="raw",
            use_segmentation_centroids=True,
        )
    )
    return build_molecular_sample_coordinates(
        series,
        centroids,
        frame_index=frame_index,
        source_view="raw",
    )


class StructuralAnalysisCacheKeyTests(unittest.TestCase):
    def test_key_contains_full_context_and_changes_for_every_invalidation_axis(self) -> None:
        series = _build_series()
        settings = _settings()
        sample = _sample(series)

        key = build_structural_analysis_cache_key(
            series,
            sample,
            use_segmentation_centroids=True,
            settings=settings,
        )

        self.assertIsInstance(key, StructuralAnalysisCacheKey)
        self.assertEqual(key.frame_id, "source-frame-0")
        self.assertEqual(key.source_view, "raw")
        self.assertEqual(key.centroid_mode, "segmentation_preferred")
        self.assertEqual(key.registration_fingerprint, "unregistered")
        self.assertEqual(
            key.spatial_calibration_fingerprint,
            sample.spatial_calibration_fingerprint,
        )
        self.assertEqual(key.algorithm_version, M6_ORIENTATION_ALGORITHM_VERSION)
        for value in (
            key.annotation_fingerprint,
            key.coordinate_transform_fingerprint,
            key.sample_geometry_fingerprint,
            key.valid_fov_fingerprint,
            key.settings_hash,
        ):
            self.assertEqual(len(value), 64)
        expected_settings_payload = json.dumps(
            {
                "m6_settings": settings.to_dict(),
                "coordinate_frame": "sample_nm",
                "coordinate_transform_version": (
                    SAMPLE_COORDINATE_TRANSFORM_VERSION
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii")
        self.assertEqual(
            key.settings_hash,
            hashlib.sha256(expected_settings_payload).hexdigest(),
        )

        changed_registration = build_structural_analysis_cache_key(
            series,
            replace(
                sample,
                registration_fingerprint="changed-registration",
                coordinate_transform_fingerprint="changed-transform-registration",
            ),
            use_segmentation_centroids=True,
            settings=settings,
        )
        original_metadata = series.metadata
        series.metadata = replace(series.metadata, size_nm_x=80.0)
        scaled_sample = _sample(series)
        changed_calibration = build_structural_analysis_cache_key(
            series,
            scaled_sample,
            use_segmentation_centroids=True,
            settings=settings,
        )
        series.metadata = original_metadata
        shifted_fov = tuple((x + 0.5, y) for x, y in sample.valid_fov_polygon_xy_nm)
        changed_fov = build_structural_analysis_cache_key(
            series,
            replace(sample, valid_fov_polygon_xy_nm=shifted_fov),
            use_segmentation_centroids=True,
            settings=settings,
        )
        changed_settings = build_structural_analysis_cache_key(
            series,
            sample,
            use_segmentation_centroids=True,
            settings=replace(settings, q_seed=0.7),
        )
        changed_algorithm = build_structural_analysis_cache_key(
            series,
            sample,
            use_segmentation_centroids=True,
            settings=settings,
            algorithm_version="m6-orientation-domains-v2-test",
        )

        self.assertNotEqual(changed_registration, key)
        self.assertNotEqual(changed_calibration, key)
        self.assertNotEqual(changed_fov, key)
        self.assertNotEqual(changed_settings, key)
        self.assertNotEqual(changed_algorithm, key)
        series.bbox_overlay_opacity = 0.0
        self.assertEqual(
            build_structural_analysis_cache_key(
                series,
                sample,
                use_segmentation_centroids=True,
                settings=settings,
            ),
            key,
        )

    def test_annotation_fingerprint_detects_mask_edit_with_same_centroid_and_area(
        self,
    ) -> None:
        first_mask = np.zeros((8, 8), dtype=bool)
        first_mask[2, 2] = True
        first_mask[4, 4] = True
        second_mask = np.zeros((8, 8), dtype=bool)
        second_mask[2, 4] = True
        second_mask[4, 2] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentation = segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                mask=first_mask,
                segmentation_id="molecule-mask",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=8,
                pixels_y=8,
                size_nm_x=8.0,
                size_nm_y=8.0,
                scan_angle_deg=0.0,
            ),
            molecular_segmentations=segmentations,
        )
        settings = _settings()
        before_sample = _sample(series)
        before = build_structural_analysis_cache_key(
            series,
            before_sample,
            use_segmentation_centroids=True,
            settings=settings,
        )
        compute = Mock(wraps=analyze_molecular_m6_orientation)
        _get_or_compute_molecular_m6_orientation(
            series,
            before_sample,
            use_segmentation_centroids=True,
            settings=settings,
            analysis_factory=compute,
        )

        segmentation.mask = second_mask
        after_sample = _sample(series)
        after = build_structural_analysis_cache_key(
            series,
            after_sample,
            use_segmentation_centroids=True,
            settings=settings,
        )
        _get_or_compute_molecular_m6_orientation(
            series,
            after_sample,
            use_segmentation_centroids=True,
            settings=settings,
            analysis_factory=compute,
        )

        self.assertEqual(before_sample.source_points_xy_px, after_sample.source_points_xy_px)
        self.assertNotEqual(before.annotation_fingerprint, after.annotation_fingerprint)
        self.assertNotEqual(before, after)
        self.assertEqual(compute.call_count, 2)


class StructuralAnalysisCacheIntegrationTests(unittest.TestCase):
    def test_recomputes_for_transform_fov_settings_and_version_changes(self) -> None:
        series = _build_series(frame_count=1)
        settings = _settings()
        base_sample = _sample(series)
        changed_registration = replace(
            base_sample,
            registration_fingerprint="changed-registration",
            coordinate_transform_fingerprint="changed-transform-registration",
        )
        original_metadata = series.metadata
        series.metadata = replace(series.metadata, size_nm_x=80.0)
        changed_scale = _sample(series)
        series.metadata = original_metadata
        changed_fov = replace(
            base_sample,
            valid_fov_polygon_xy_nm=tuple(
                (x + 0.1, y) for x, y in base_sample.valid_fov_polygon_xy_nm
            ),
        )
        compute = Mock(wraps=analyze_molecular_m6_orientation)

        variants = (
            (base_sample, settings, M6_ORIENTATION_ALGORITHM_VERSION),
            (changed_registration, settings, M6_ORIENTATION_ALGORITHM_VERSION),
            (changed_scale, settings, M6_ORIENTATION_ALGORITHM_VERSION),
            (changed_fov, settings, M6_ORIENTATION_ALGORITHM_VERSION),
            (base_sample, settings, "m6-orientation-domains-v2-test"),
            (base_sample, replace(settings, q_seed=0.7), M6_ORIENTATION_ALGORITHM_VERSION),
        )
        for sample_coordinates, variant_settings, algorithm_version in variants:
            _get_or_compute_molecular_m6_orientation(
                series,
                sample_coordinates,
                use_segmentation_centroids=True,
                settings=variant_settings,
                algorithm_version=algorithm_version,
                analysis_factory=compute,
            )
        _get_or_compute_molecular_m6_orientation(
            series,
            variants[-1][0],
            use_segmentation_centroids=True,
            settings=variants[-1][1],
            algorithm_version=variants[-1][2],
            analysis_factory=compute,
        )

        self.assertEqual(compute.call_count, len(variants))
        stats = series.structural_analysis_cache.stats()
        self.assertEqual(stats.miss_count, len(variants))
        self.assertEqual(stats.hit_count, 1)

    def test_reuses_same_frame_and_selectively_recomputes_changed_bbox(self) -> None:
        series = _build_series()
        settings = _settings()

        with patch(
            "moltrack.analysis.range_analysis.analyze_molecular_m6_orientation",
            wraps=analyze_molecular_m6_orientation,
        ) as compute:
            first = analyze_molecular_frame_range(
                series,
                MolecularFrameRange("frame 0", 0, 0),
                source_view="raw",
                m6_orientation_settings=settings,
            )
            repeated = analyze_molecular_frame_range(
                series,
                MolecularFrameRange("frame 0", 0, 0),
                source_view="raw",
                m6_orientation_settings=settings,
            )
            frame_one = analyze_molecular_frame_range(
                series,
                MolecularFrameRange("frame 1", 1, 1),
                source_view="raw",
                m6_orientation_settings=settings,
            )
            detection = series.molecular_detections.get_detections(0)[0]
            x1, y1, x2, y2 = detection.bbox_xyxy
            series.molecular_detections.update_detection_bbox(
                detection.detection_id,
                (x1 + 0.1, y1, x2 + 0.1, y2),
                frame_shape=series.frame_shape,
            )
            changed = analyze_molecular_frame_range(
                series,
                MolecularFrameRange("frame 0", 0, 0),
                source_view="raw",
                m6_orientation_settings=settings,
            )
            repeated_frame_one = analyze_molecular_frame_range(
                series,
                MolecularFrameRange("frame 1", 1, 1),
                source_view="raw",
                m6_orientation_settings=settings,
            )

        self.assertEqual(compute.call_count, 3)
        self.assertIs(
            first.frame_results[0].m6_orientation_analysis,
            repeated.frame_results[0].m6_orientation_analysis,
        )
        self.assertIsNot(
            first.frame_results[0].m6_orientation_analysis,
            changed.frame_results[0].m6_orientation_analysis,
        )
        self.assertIs(
            frame_one.frame_results[0].m6_orientation_analysis,
            repeated_frame_one.frame_results[0].m6_orientation_analysis,
        )
        stats = series.structural_analysis_cache.stats()
        self.assertEqual(stats.entry_count, 2)
        self.assertEqual(stats.hit_count, 2)
        self.assertEqual(stats.miss_count, 3)

        series.remove_frame(0)
        self.assertIsNone(series.structural_analysis_cache)

    def test_reuses_blocking_graph_qc_without_recomputing_the_frame(self) -> None:
        series = _build_series(frame_count=1)

        with patch(
            "moltrack.analysis.range_analysis.analyze_molecular_m6_orientation",
            side_effect=M6BlockingGraphQCError(
                "blocking_rank2_radius_fallback"
            ),
        ) as compute:
            first = analyze_molecular_frame_range(
                series,
                MolecularFrameRange("blocked", 0, 0),
                source_view="raw",
                m6_orientation_settings=_settings(),
            )
            repeated = analyze_molecular_frame_range(
                series,
                MolecularFrameRange("blocked", 0, 0),
                source_view="raw",
                m6_orientation_settings=_settings(),
            )

        self.assertEqual(compute.call_count, 1)
        for analysis in (first, repeated):
            result = analysis.frame_results[0]
            self.assertIsNone(result.m6_orientation_analysis)
            self.assertEqual(
                result.m6_orientation_availability_status,
                "unavailable_blocking_graph_qc",
            )
            self.assertEqual(
                result.m6_orientation_unavailability_reason,
                "blocking_rank2_radius_fallback",
            )
        stats = series.structural_analysis_cache.stats()
        self.assertEqual(stats.entry_count, 1)
        self.assertEqual(stats.hit_count, 1)
        self.assertEqual(stats.miss_count, 1)

    def test_retains_distinct_settings_variants_for_the_same_frame_input(self) -> None:
        series = _build_series(frame_count=1)
        first_settings = _settings()
        second_settings = replace(first_settings, q_seed=0.7)

        with patch(
            "moltrack.analysis.range_analysis.analyze_molecular_m6_orientation",
            wraps=analyze_molecular_m6_orientation,
        ) as compute:
            first = analyze_molecular_frame_range(
                series,
                MolecularFrameRange("frame", 0, 0),
                source_view="raw",
                m6_orientation_settings=first_settings,
            )
            analyze_molecular_frame_range(
                series,
                MolecularFrameRange("frame", 0, 0),
                source_view="raw",
                m6_orientation_settings=second_settings,
            )
            repeated_first = analyze_molecular_frame_range(
                series,
                MolecularFrameRange("frame", 0, 0),
                source_view="raw",
                m6_orientation_settings=first_settings,
            )

        self.assertEqual(compute.call_count, 2)
        self.assertIs(
            first.frame_results[0].m6_orientation_analysis,
            repeated_first.frame_results[0].m6_orientation_analysis,
        )
        self.assertEqual(series.structural_analysis_cache.stats().entry_count, 2)

    def test_lru_enforces_entry_and_memory_limits(self) -> None:
        series = _build_series()
        settings = _settings()
        analyses = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("both", 0, 1),
            source_view="raw",
            m6_orientation_settings=settings,
        )
        first_analysis = analyses.frame_results[0].m6_orientation_analysis
        second_analysis = analyses.frame_results[1].m6_orientation_analysis
        assert first_analysis is not None and second_analysis is not None
        first_key = build_structural_analysis_cache_key(
            series,
            first_analysis.sample_coordinates,
            use_segmentation_centroids=True,
            settings=settings,
        )
        second_key = build_structural_analysis_cache_key(
            series,
            second_analysis.sample_coordinates,
            use_segmentation_centroids=True,
            settings=settings,
        )

        limited = StructuralAnalysisCache(max_entries=1, max_bytes=64 * 1024 * 1024)
        with self.assertRaisesRegex(ValueError, "context must match"):
            limited._put(first_key, second_analysis)
        self.assertTrue(limited._put(first_key, first_analysis))
        self.assertTrue(limited._put(second_key, second_analysis))
        self.assertIsNone(limited.get(first_key))
        self.assertIs(limited.get(second_key), second_analysis)
        self.assertEqual(limited.stats().eviction_count, 1)

        first_size_cache = StructuralAnalysisCache(
            max_entries=2,
            max_bytes=64 * 1024 * 1024,
        )
        second_size_cache = StructuralAnalysisCache(
            max_entries=2,
            max_bytes=64 * 1024 * 1024,
        )
        first_size_cache._put(first_key, first_analysis)
        second_size_cache._put(second_key, second_analysis)
        cumulative_limit = max(
            first_size_cache.stats().estimated_bytes,
            second_size_cache.stats().estimated_bytes,
        ) + 1
        byte_limited = StructuralAnalysisCache(
            max_entries=2,
            max_bytes=cumulative_limit,
        )
        self.assertTrue(byte_limited._put(first_key, first_analysis))
        self.assertTrue(byte_limited._put(second_key, second_analysis))
        self.assertEqual(byte_limited.stats().entry_count, 1)
        self.assertEqual(byte_limited.stats().eviction_count, 1)
        self.assertIsNone(byte_limited.get(first_key))
        self.assertIs(byte_limited.get(second_key), second_analysis)

        too_small = StructuralAnalysisCache(max_entries=2, max_bytes=1)
        self.assertFalse(too_small._put(first_key, first_analysis))
        self.assertEqual(too_small.stats().entry_count, 0)
        self.assertEqual(too_small.stats().oversized_rejection_count, 1)
        with self.assertRaisesRegex(ValueError, "positive integer"):
            StructuralAnalysisCache(max_entries=1.9)

    def test_memory_estimate_counts_owned_numpy_buffer_once_and_view_base_once(self) -> None:
        owned = np.arange(32, dtype=np.float64)
        view = owned[4:20]

        self.assertEqual(_deep_size_bytes(owned), sys.getsizeof(owned))
        self.assertEqual(
            _deep_size_bytes(view),
            sys.getsizeof(view) + sys.getsizeof(owned),
        )


if __name__ == "__main__":
    unittest.main()
