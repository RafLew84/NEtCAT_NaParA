import unittest
from types import SimpleNamespace

import numpy as np

from moltrack.analysis import (
    MolecularIntensityMeasurement,
    build_molecular_intensity_measurements,
    build_molecular_position_plot_data,
    compute_molecular_nearest_neighbor_angle_metrics,
    compute_molecular_nearest_neighbor_metrics,
    measure_molecular_intensity,
)
from moltrack.core import (
    MolecularCentroid,
    MolecularDetection,
    MolecularDetectionSet,
    MolecularSegmentation,
    MolecularSegmentationSet,
    MolTrackImageSeries,
    build_molecular_centroids,
)


class MolecularIntensityMeasurementTests(unittest.TestCase):
    def test_position_plot_aligns_selected_intensity_metric_to_centroid_source_ids(self) -> None:
        centroids = [
            MolecularCentroid(
                frame_index=0,
                source_view="raw",
                x_px=1.0,
                y_px=1.0,
                source_kind="segmentation",
                source_id="seg-a",
            ),
            MolecularCentroid(
                frame_index=0,
                source_view="raw",
                x_px=3.0,
                y_px=1.0,
                source_kind="bbox_center",
                source_id="bbox-missing",
            ),
            MolecularCentroid(
                frame_index=0,
                source_view="raw",
                x_px=5.0,
                y_px=1.0,
                source_kind="segmentation",
                source_id="seg-c",
            ),
        ]
        measurements = [
            MolecularIntensityMeasurement(
                frame_index=0,
                source_id="seg-c",
                source_kind="segmentation",
                pixel_count=2,
                sum=24.0,
                mean=12.0,
                median=12.0,
                max=14.0,
                unit="nA",
                local_background_median=3.0,
                background_corrected_mean=9.0,
                background_corrected_median=9.0,
            ),
            MolecularIntensityMeasurement(
                frame_index=0,
                source_id="seg-a",
                source_kind="segmentation",
                pixel_count=2,
                sum=16.0,
                mean=8.0,
                median=8.0,
                max=10.0,
                unit="nA",
                local_background_median=3.0,
                background_corrected_mean=5.0,
                background_corrected_median=5.0,
            ),
        ]

        plot_data = build_molecular_position_plot_data(
            centroids,
            frame_index=0,
            source_view="raw",
            frame_shape=(8, 8),
            intensity_measurements=measurements,
            intensity_metric="background_corrected_median",
        )

        self.assertEqual(plot_data.points_xy, ((1.0, 1.0), (3.0, 1.0), (5.0, 1.0)))
        self.assertEqual(plot_data.intensity_values, (5.0, None, 9.0))
        self.assertEqual(plot_data.intensity_metric, "background_corrected_median")
        self.assertEqual(plot_data.intensity_unit, "nA")

    def test_position_metrics_depend_only_on_xy_when_intensity_is_present(self) -> None:
        centroids = [
            MolecularCentroid(0, "raw", 0.0, 0.0, "segmentation", "seg-a"),
            MolecularCentroid(0, "raw", 3.0, 0.0, "bbox_center", "bbox-b"),
            MolecularCentroid(0, "raw", 3.0, 4.0, "segmentation", "seg-c"),
        ]
        measurements = [
            MolecularIntensityMeasurement(
                frame_index=0,
                source_id=source_id,
                source_kind="segmentation",
                pixel_count=1,
                sum=value,
                mean=value,
                median=value,
                max=value,
            )
            for source_id, value in (("seg-a", 2.0), ("seg-c", 8.0))
        ]
        plain = build_molecular_position_plot_data(
            centroids,
            frame_index=0,
            source_view="raw",
            frame_shape=(8, 8),
        )
        with_intensity = build_molecular_position_plot_data(
            centroids,
            frame_index=0,
            source_view="raw",
            frame_shape=(8, 8),
            intensity_measurements=measurements,
            intensity_metric="mean",
        )

        self.assertEqual(
            compute_molecular_nearest_neighbor_metrics(with_intensity),
            compute_molecular_nearest_neighbor_metrics(plain),
        )
        self.assertEqual(
            compute_molecular_nearest_neighbor_angle_metrics(with_intensity),
            compute_molecular_nearest_neighbor_angle_metrics(plain),
        )

    def test_builder_prefers_linked_segmentation_and_keeps_unsegmented_bbox_fallback(self) -> None:
        frame = np.ones((6, 6), dtype=np.float32)
        frame[1:3, 1:3] = 10.0
        frame[0:2, 4:6] = 20.0
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(0, 0, 3, 3),
                    confidence=0.9,
                    detection_id="bbox-with-mask",
                ),
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(4, 0, 6, 2),
                    confidence=0.8,
                    detection_id="bbox-fallback",
                ),
            ],
            source_view="raw",
            frame_shape=frame.shape,
        )
        mask = np.zeros(frame.shape, dtype=bool)
        mask[1:3, 1:3] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                mask=mask,
                prompt_detection_ids=("bbox-with-mask",),
                segmentation_id="seg-1",
                origin="sam2",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frame[np.newaxis, ...],
            metadata=object(),
            molecular_detections=detections,
            molecular_segmentations=segmentations,
        )

        measurements = build_molecular_intensity_measurements(series)

        self.assertEqual(
            [(measurement.source_kind, measurement.source_id) for measurement in measurements],
            [("segmentation", "seg-1"), ("bbox", "bbox-fallback")],
        )
        self.assertEqual([measurement.mean for measurement in measurements], [10.0, 20.0])

    def test_builder_reuses_cached_measurement_for_unchanged_annotation(self) -> None:
        frame = np.arange(36, dtype=np.float32).reshape(6, 6)
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [MolecularDetection(0, (1, 1, 3, 3), 0.9, detection_id="bbox-a")],
            source_view="raw",
            frame_shape=frame.shape,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frame[np.newaxis, ...],
            metadata=object(),
            molecular_detections=detections,
        )

        first = build_molecular_intensity_measurements(series)
        second = build_molecular_intensity_measurements(series)

        self.assertIs(second[0], first[0])
        stats = series.molecular_intensity_cache.stats()
        self.assertEqual(stats.entry_count, 1)
        self.assertEqual(stats.hit_count, 1)
        self.assertEqual(stats.miss_count, 1)

    def test_mask_edit_recomputes_only_changed_molecule(self) -> None:
        frame = np.zeros((10, 10), dtype=np.float32)
        frame[1:3, 1:3] = 2.0
        frame[4:6, 1:3] = 8.0
        frame[7:9, 7:9] = 12.0
        first_mask = np.zeros(frame.shape, dtype=bool)
        first_mask[1:3, 1:3] = True
        second_mask = np.zeros(frame.shape, dtype=bool)
        second_mask[7:9, 7:9] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        first_segmentation = segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                mask=first_mask,
                segmentation_id="seg-a",
            )
        )
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                mask=second_mask,
                segmentation_id="seg-b",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frame[np.newaxis, ...],
            metadata=object(),
            molecular_segmentations=segmentations,
        )
        before = build_molecular_intensity_measurements(series)
        edited_mask = np.zeros(frame.shape, dtype=bool)
        edited_mask[4:6, 1:3] = True
        first_segmentation.mask = edited_mask

        after = build_molecular_intensity_measurements(series)

        self.assertIsNot(after[0], before[0])
        self.assertEqual(after[0].mean, 8.0)
        self.assertIs(after[1], before[1])
        stats = series.molecular_intensity_cache.stats()
        self.assertEqual(stats.entry_count, 2)
        self.assertEqual(stats.hit_count, 1)
        self.assertEqual(stats.miss_count, 3)

    def test_removing_segmentation_removes_its_cached_measurement(self) -> None:
        frame = np.ones((6, 6), dtype=np.float32)
        mask = np.zeros(frame.shape, dtype=bool)
        mask[1:3, 1:3] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                mask=mask,
                segmentation_id="seg-a",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frame[np.newaxis, ...],
            metadata=object(),
            molecular_segmentations=segmentations,
        )
        build_molecular_intensity_measurements(series)

        segmentations.remove_segmentation("seg-a")
        measurements = build_molecular_intensity_measurements(series)

        self.assertEqual(measurements, [])
        self.assertEqual(series.molecular_intensity_cache.stats().entry_count, 0)

    def test_bbox_resize_recomputes_only_changed_fallback_measurement(self) -> None:
        frame = np.zeros((10, 10), dtype=np.float32)
        frame[1:3, 1:3] = 2.0
        frame[1:3, 4:6] = 8.0
        frame[7:9, 7:9] = 12.0
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(0, (1, 1, 3, 3), 0.9, detection_id="bbox-a"),
                MolecularDetection(0, (7, 7, 9, 9), 0.8, detection_id="bbox-b"),
            ],
            source_view="raw",
            frame_shape=frame.shape,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frame[np.newaxis, ...],
            metadata=object(),
            molecular_detections=detections,
        )
        before = build_molecular_intensity_measurements(series)

        detections.update_detection_bbox("bbox-a", (4, 1, 6, 3), frame_shape=frame.shape)
        after = build_molecular_intensity_measurements(series)

        self.assertIsNot(after[0], before[0])
        self.assertEqual(after[0].mean, 8.0)
        self.assertIs(after[1], before[1])
        stats = series.molecular_intensity_cache.stats()
        self.assertEqual(stats.entry_count, 2)
        self.assertEqual(stats.hit_count, 1)
        self.assertEqual(stats.miss_count, 3)

    def test_background_ring_parameters_select_independent_cached_measurements(self) -> None:
        frame = np.arange(100, dtype=np.float32).reshape(10, 10)
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [MolecularDetection(0, (4, 4, 6, 6), 0.9, detection_id="bbox-a")],
            source_view="raw",
            frame_shape=frame.shape,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frame[np.newaxis, ...],
            metadata=object(),
            molecular_detections=detections,
        )

        narrow = build_molecular_intensity_measurements(
            series,
            background_inner_radius_px=0,
            background_outer_radius_px=2,
        )
        wide = build_molecular_intensity_measurements(
            series,
            background_inner_radius_px=0,
            background_outer_radius_px=3,
        )
        narrow_again = build_molecular_intensity_measurements(
            series,
            background_inner_radius_px=0,
            background_outer_radius_px=2,
        )

        self.assertIsNot(wide[0], narrow[0])
        self.assertIs(narrow_again[0], narrow[0])
        stats = series.molecular_intensity_cache.stats()
        self.assertEqual(stats.entry_count, 2)
        self.assertEqual(stats.hit_count, 1)
        self.assertEqual(stats.miss_count, 2)

    def test_builder_reuses_unchanged_frame_geometry_context(self) -> None:
        frame = np.ones((32, 32), dtype=np.float32)
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(0, (2, 2, 6, 6), 0.9, detection_id="bbox-a"),
                MolecularDetection(0, (24, 24, 28, 28), 0.8, detection_id="bbox-b"),
            ],
            source_view="raw",
            frame_shape=frame.shape,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frame[np.newaxis, ...],
            metadata=object(),
            molecular_detections=detections,
        )

        build_molecular_intensity_measurements(series)
        build_molecular_intensity_measurements(series)

        stats = series.molecular_intensity_cache.stats()
        self.assertEqual(stats.context_mask_build_count, 1)

    def test_frame_navigation_reuses_measurement_when_returning_to_unchanged_frame(self) -> None:
        frames = np.zeros((2, 8, 8), dtype=np.float32)
        frames[0, 1:3, 1:3] = 2.0
        frames[1, 5:7, 5:7] = 8.0
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [MolecularDetection(0, (1, 1, 3, 3), 0.9, detection_id="frame-0")],
            source_view="raw",
            frame_shape=(8, 8),
        )
        detections.set_detections(
            1,
            [MolecularDetection(1, (5, 5, 7, 7), 0.9, detection_id="frame-1")],
            source_view="raw",
            frame_shape=(8, 8),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=object(),
            molecular_detections=detections,
        )

        first_visit = build_molecular_intensity_measurements(series, frame_index=0)
        build_molecular_intensity_measurements(series, frame_index=1)
        return_visit = build_molecular_intensity_measurements(series, frame_index=0)

        self.assertIs(return_visit[0], first_visit[0])
        stats = series.molecular_intensity_cache.stats()
        self.assertEqual(stats.entry_count, 2)
        self.assertEqual(stats.hit_count, 1)
        self.assertEqual(stats.miss_count, 2)
        self.assertEqual(stats.context_mask_build_count, 2)

    def test_builder_clips_partially_visible_bbox_and_rejects_bbox_outside_frame(self) -> None:
        frame = np.ones((4, 4), dtype=np.float32)
        frame[0:2, 0:2] = 7.0
        detections = MolecularDetectionSet(
            frame_count=1,
            detections_by_frame={
                0: [
                    MolecularDetection(
                        frame_index=0,
                        bbox_xyxy=(-1, -1, 2, 2),
                        confidence=0.9,
                        detection_id="bbox-partial",
                    ),
                    MolecularDetection(
                        frame_index=0,
                        bbox_xyxy=(5, 5, 7, 7),
                        confidence=0.8,
                        detection_id="bbox-outside",
                    ),
                ]
            },
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frame[np.newaxis, ...],
            metadata=object(),
            molecular_detections=detections,
        )

        measurements = build_molecular_intensity_measurements(series)

        self.assertEqual(len(measurements), 1)
        self.assertEqual(measurements[0].source_id, "bbox-partial")
        self.assertEqual(measurements[0].source_kind, "bbox")
        self.assertEqual(measurements[0].pixel_count, 4)
        self.assertEqual(measurements[0].mean, 7.0)

    def test_expanded_bbox_keeps_registered_position_but_measures_raw_signal(self) -> None:
        raw_frame = np.ones((4, 4), dtype=np.float32)
        raw_frame[1:3, 1:3] = 11.0
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(4, 3, 6, 5),
                    confidence=0.9,
                    source_view="expanded_aligned",
                    detection_id="expanded-bbox",
                )
            ],
            source_view="expanded_aligned",
            frame_shape=(7, 8),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=raw_frame[np.newaxis, ...],
            metadata=object(),
            molecular_detections=detections,
            expanded_aligned_stack=SimpleNamespace(
                frames=np.full((1, 7, 8), 999.0, dtype=np.float32),
                frame_origins_xy=np.asarray(((3.0, 2.0),)),
                canvas_offset_xy=(1.0, 1.0),
            ),
        )

        centroids = build_molecular_centroids(series, source_view="expanded_aligned")
        plot_data = build_molecular_position_plot_data(
            centroids,
            frame_index=0,
            source_view="expanded_aligned",
            frame_shape=(7, 8),
            coordinate_origin_px=(1.0, 1.0),
        )
        measurements = build_molecular_intensity_measurements(
            series,
            source_view="expanded_aligned",
        )

        self.assertEqual(plot_data.points_xy, ((4.0, 3.0),))
        self.assertEqual(len(measurements), 1)
        self.assertEqual(measurements[0].source_id, "expanded-bbox")
        self.assertEqual(measurements[0].mean, 11.0)

    def test_expanded_segmentation_is_mapped_to_raw_and_keeps_segmentation_id(self) -> None:
        raw_frame = np.ones((4, 4), dtype=np.float32)
        raw_frame[1:3, 1:3] = 13.0
        expanded_mask = np.zeros((7, 8), dtype=bool)
        expanded_mask[3:5, 4:6] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="expanded_aligned",
                mask=expanded_mask,
                prompt_detection_ids=("expanded-prompt",),
                segmentation_id="expanded-segmentation",
                origin="sam2",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=raw_frame[np.newaxis, ...],
            metadata=object(),
            molecular_segmentations=segmentations,
            expanded_aligned_stack=SimpleNamespace(
                frames=np.full((1, 7, 8), 999.0, dtype=np.float32),
                frame_origins_xy=np.asarray(((3.0, 2.0),)),
            ),
        )

        measurements = build_molecular_intensity_measurements(
            series,
            source_view="expanded_aligned",
        )

        self.assertEqual(len(measurements), 1)
        self.assertEqual(measurements[0].source_kind, "segmentation")
        self.assertEqual(measurements[0].source_id, "expanded-segmentation")
        self.assertEqual(measurements[0].pixel_count, 4)
        self.assertEqual(measurements[0].mean, 13.0)

    def test_expanded_bbox_partly_outside_raw_footprint_uses_observed_pixels_only(self) -> None:
        raw_frame = np.ones((4, 4), dtype=np.float32)
        raw_frame[0:2, 0:2] = 17.0
        detections = MolecularDetectionSet(
            frame_count=1,
            detections_by_frame={
                0: [
                    MolecularDetection(
                        frame_index=0,
                        bbox_xyxy=(0, 1, 4, 4),
                        confidence=0.9,
                        source_view="expanded_aligned",
                        detection_id="partly-observed",
                    )
                ]
            },
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=raw_frame[np.newaxis, ...],
            metadata=object(),
            molecular_detections=detections,
            expanded_aligned_stack=SimpleNamespace(
                frames=np.full((1, 7, 8), 999.0, dtype=np.float32),
                frame_origins_xy=np.asarray(((2.0, 2.0),)),
            ),
        )

        measurements = build_molecular_intensity_measurements(
            series,
            source_view="expanded_aligned",
        )

        self.assertEqual(len(measurements), 1)
        self.assertEqual(measurements[0].source_id, "partly-observed")
        self.assertEqual(measurements[0].pixel_count, 4)
        self.assertEqual(measurements[0].mean, 17.0)

    def test_measurement_reports_signal_statistics_for_active_mask_pixels(self) -> None:
        frame = np.asarray(
            (
                (1.0, 2.0, 3.0),
                (4.0, 5.0, 6.0),
            ),
            dtype=np.float32,
        )
        mask = np.asarray(
            (
                (True, False, True),
                (False, True, False),
            ),
            dtype=bool,
        )

        measurement = measure_molecular_intensity(
            frame,
            mask,
            frame_index=4,
            source_id="seg-1",
            source_kind="segmentation",
        )

        self.assertIsInstance(measurement, MolecularIntensityMeasurement)
        self.assertEqual(measurement.frame_index, 4)
        self.assertEqual(measurement.source_id, "seg-1")
        self.assertEqual(measurement.source_kind, "segmentation")
        self.assertEqual(measurement.pixel_count, 3)
        self.assertEqual(measurement.sum, 9.0)
        self.assertEqual(measurement.mean, 3.0)
        self.assertEqual(measurement.median, 3.0)
        self.assertEqual(measurement.max, 5.0)
        self.assertEqual(measurement.unit, "a.u.")

    def test_measurement_rejects_empty_mask(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one active pixel"):
            measure_molecular_intensity(
                np.ones((2, 3), dtype=np.float32),
                np.zeros((2, 3), dtype=bool),
                frame_index=0,
                source_id="seg-empty",
                source_kind="segmentation",
            )

    def test_measurement_rejects_mask_with_different_shape_than_frame(self) -> None:
        with self.assertRaisesRegex(ValueError, "mask shape must match frame shape"):
            measure_molecular_intensity(
                np.ones((2, 3), dtype=np.float32),
                np.ones((2, 2), dtype=bool),
                frame_index=0,
                source_id="seg-wrong-shape",
                source_kind="segmentation",
            )

    def test_measurement_rejects_frame_that_is_not_two_dimensional(self) -> None:
        with self.assertRaisesRegex(ValueError, "frame must be a 2D array"):
            measure_molecular_intensity(
                np.ones((2, 3, 1), dtype=np.float32),
                np.ones((2, 3, 1), dtype=bool),
                frame_index=0,
                source_id="seg-3d-frame",
                source_kind="segmentation",
            )

    def test_measurement_requires_boolean_mask(self) -> None:
        with self.assertRaisesRegex(TypeError, "mask must use bool dtype"):
            measure_molecular_intensity(
                np.ones((2, 3), dtype=np.float32),
                np.ones((2, 3), dtype=np.uint8),
                frame_index=0,
                source_id="seg-integer-mask",
                source_kind="segmentation",
            )

    def test_measurement_ignores_non_finite_pixels_inside_mask(self) -> None:
        frame = np.asarray(
            (
                (1.0, np.nan, np.inf),
                (-np.inf, 5.0, 9.0),
            ),
            dtype=np.float64,
        )

        measurement = measure_molecular_intensity(
            frame,
            np.ones(frame.shape, dtype=bool),
            frame_index=2,
            source_id="seg-finite-subset",
            source_kind="segmentation",
        )

        self.assertEqual(measurement.pixel_count, 3)
        self.assertEqual(measurement.sum, 15.0)
        self.assertEqual(measurement.mean, 5.0)
        self.assertEqual(measurement.median, 5.0)
        self.assertEqual(measurement.max, 9.0)

    def test_measurement_is_unavailable_when_mask_has_no_finite_pixels(self) -> None:
        frame = np.asarray(
            ((np.nan, 1.0), (2.0, np.inf)),
            dtype=np.float64,
        )
        mask = np.asarray(((True, False), (False, True)), dtype=bool)

        measurement = measure_molecular_intensity(
            frame,
            mask,
            frame_index=3,
            source_id="seg-unavailable",
            source_kind="segmentation",
            unit="nA",
        )

        self.assertEqual(measurement.pixel_count, 0)
        self.assertIsNone(measurement.sum)
        self.assertIsNone(measurement.mean)
        self.assertIsNone(measurement.median)
        self.assertIsNone(measurement.max)
        self.assertEqual(measurement.unit, "nA")

    def test_measurement_subtracts_local_ring_background_from_mean_and_median(self) -> None:
        frame = np.full((7, 7), 10.0, dtype=np.float32)
        frame[3, 3] = 30.0
        mask = np.zeros(frame.shape, dtype=bool)
        mask[3, 3] = True

        measurement = measure_molecular_intensity(
            frame,
            mask,
            frame_index=0,
            source_id="seg-background",
            source_kind="segmentation",
            background_inner_radius_px=0,
            background_outer_radius_px=2,
        )

        self.assertEqual(measurement.mean, 30.0)
        self.assertEqual(measurement.median, 30.0)
        self.assertEqual(measurement.local_background_median, 10.0)
        self.assertEqual(measurement.background_corrected_mean, 20.0)
        self.assertEqual(measurement.background_corrected_median, 20.0)

    def test_local_background_excludes_other_molecule_masks(self) -> None:
        frame = np.full((7, 7), 10.0, dtype=np.float32)
        frame[3, 3] = 30.0
        mask = np.zeros(frame.shape, dtype=bool)
        mask[3, 3] = True
        other_molecules_mask = np.zeros(frame.shape, dtype=bool)
        for y, x in ((2, 3), (3, 2), (3, 4)):
            frame[y, x] = 100.0
            other_molecules_mask[y, x] = True

        measurement = measure_molecular_intensity(
            frame,
            mask,
            frame_index=0,
            source_id="seg-with-neighbors",
            source_kind="segmentation",
            background_inner_radius_px=0,
            background_outer_radius_px=1,
            other_molecules_mask=other_molecules_mask,
        )

        self.assertEqual(measurement.local_background_median, 10.0)
        self.assertEqual(measurement.background_corrected_median, 20.0)

    def test_local_background_uses_available_ring_at_frame_edge(self) -> None:
        frame = np.full((3, 3), 10.0, dtype=np.float32)
        frame[0, 0] = 30.0
        mask = np.zeros(frame.shape, dtype=bool)
        mask[0, 0] = True

        measurement = measure_molecular_intensity(
            frame,
            mask,
            frame_index=0,
            source_id="seg-at-edge",
            source_kind="segmentation",
            background_inner_radius_px=0,
            background_outer_radius_px=1,
        )

        self.assertEqual(measurement.local_background_median, 10.0)
        self.assertEqual(measurement.background_corrected_mean, 20.0)
        self.assertEqual(measurement.background_corrected_median, 20.0)

    def test_measurement_preserves_raw_statistics_when_background_ring_is_unavailable(self) -> None:
        frame = np.full((3, 3), 10.0, dtype=np.float32)
        frame[1, 1] = 30.0
        mask = np.zeros(frame.shape, dtype=bool)
        mask[1, 1] = True

        measurement = measure_molecular_intensity(
            frame,
            mask,
            frame_index=0,
            source_id="seg-without-background",
            source_kind="segmentation",
            background_inner_radius_px=0,
            background_outer_radius_px=1,
            other_molecules_mask=~mask,
        )

        self.assertEqual(measurement.mean, 30.0)
        self.assertEqual(measurement.median, 30.0)
        self.assertEqual(measurement.max, 30.0)
        self.assertIsNone(measurement.local_background_median)
        self.assertIsNone(measurement.background_corrected_mean)
        self.assertIsNone(measurement.background_corrected_median)


if __name__ == "__main__":
    unittest.main()
