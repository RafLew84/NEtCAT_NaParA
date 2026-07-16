import unittest
from dataclasses import replace
from types import SimpleNamespace

import numpy as np

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularM6OrientationAnalysis,
    MolecularM6OrientationAnalysisSettings,
    analyze_molecular_frame_range,
    build_molecular_sample_coordinates,
)
from moltrack.core import (
    MolecularDetection,
    MolecularDetectionSet,
    MolTrackRegistrationFrameResult,
    MolTrackRegistrationResultSet,
    MolTrackRegistrationSettings,
    MolTrackImageSeries,
    build_molecular_centroids,
)
from nanotrack.core import STMSequenceMetadata


class MolecularSampleCoordinateTransformTests(unittest.TestCase):
    def test_raw_centroid_is_transformed_to_canonical_sample_axes(self) -> None:
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1.0, 2.0, 3.0, 4.0),
                    confidence=0.9,
                    detection_id="molecule-a",
                )
            ],
            source_view="raw",
            frame_shape=(10, 10),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 10, 10), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=10,
                pixels_y=10,
                size_nm_x=20.0,
                size_nm_y=10.0,
                scan_angle_deg=90.0,
            ),
            molecular_detections=detections,
        )
        centroids = tuple(
            build_molecular_centroids(
                series,
                frame_index=0,
                source_view="raw",
            )
        )

        coordinates = build_molecular_sample_coordinates(
            series,
            centroids,
            frame_index=0,
            source_view="raw",
        )
        repeated = build_molecular_sample_coordinates(
            series,
            centroids,
            frame_index=0,
            source_view="raw",
        )

        np.testing.assert_allclose(coordinates.points_xy_nm, ((-7.0, 4.0),), atol=1e-12)
        np.testing.assert_allclose(
            coordinates.valid_fov_polygon_xy_nm,
            ((0.0, 0.0), (0.0, 20.0), (-10.0, 20.0), (-10.0, 0.0)),
            atol=1e-12,
        )
        self.assertEqual(coordinates.point_source_ids, ("molecule-a",))
        self.assertAlmostEqual(coordinates.distance_to_valid_fov_boundary_nm[0], 3.0)
        self.assertEqual(coordinates.coordinate_frame, "sample_nm")
        self.assertEqual(coordinates.orientation_reference, "+x_sample_axis")
        self.assertFalse(coordinates.scan_angle_missing_qc)
        self.assertEqual(
            coordinates.coordinate_transform_fingerprint,
            repeated.coordinate_transform_fingerprint,
        )
        self.assertEqual(coordinates.registration_fingerprint, "unregistered")

    def test_expanded_centroids_preserve_registration_translation(self) -> None:
        detections = MolecularDetectionSet(frame_count=2)
        for frame_index, bbox in enumerate(
            ((3.0, 4.0, 5.0, 6.0), (3.0, 2.0, 5.0, 4.0))
        ):
            detections.set_detections(
                frame_index,
                [
                    MolecularDetection(
                        frame_index=frame_index,
                        bbox_xyxy=bbox,
                        confidence=0.9,
                        source_view="expanded_aligned",
                        detection_id=f"molecule-{frame_index}",
                    )
                ],
                source_view="expanded_aligned",
                frame_shape=(14, 14),
            )
        metadata = STMSequenceMetadata(
            pixels_x=10,
            pixels_y=10,
            size_nm_x=10.0,
            size_nm_y=10.0,
            scan_angle_deg=0.0,
        )
        expanded_metadata = STMSequenceMetadata(
            pixels_x=14,
            pixels_y=14,
            size_nm_x=14.0,
            size_nm_y=14.0,
            scan_angle_deg=0.0,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 10, 10), dtype=np.float32),
            metadata=metadata,
            molecular_detections=detections,
            expanded_aligned_stack=SimpleNamespace(
                frames=np.zeros((2, 14, 14), dtype=np.float32),
                metadata=expanded_metadata,
                canvas_offset_xy=(2.0, 2.0),
                padding_ltrb=(2, 2, 2, 2),
                frame_origins_xy=np.asarray(((2.0, 2.0), (2.0, 0.0))),
            ),
        )

        transformed = []
        for frame_index in range(2):
            centroids = tuple(
                build_molecular_centroids(
                    series,
                    frame_index=frame_index,
                    source_view="expanded_aligned",
                )
            )
            transformed.append(
                build_molecular_sample_coordinates(
                    series,
                    centroids,
                    frame_index=frame_index,
                    source_view="expanded_aligned",
                )
            )

        self.assertEqual(transformed[0].points_xy_nm, ((2.0, 7.0),))
        self.assertEqual(transformed[1].points_xy_nm, ((2.0, 9.0),))
        self.assertNotEqual(
            transformed[0].registration_fingerprint,
            transformed[1].registration_fingerprint,
        )
        self.assertNotEqual(
            transformed[0].coordinate_transform_fingerprint,
            transformed[1].coordinate_transform_fingerprint,
        )
        self.assertEqual(
            transformed[0].valid_fov_polygon_xy_nm,
            ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
        )
        self.assertEqual(
            transformed[1].valid_fov_polygon_xy_nm,
            ((0.0, 2.0), (10.0, 2.0), (10.0, 12.0), (0.0, 12.0)),
        )
        self.assertEqual(
            transformed[0].plot_canvas_polygon_xy_nm,
            ((-2.0, -2.0), (12.0, -2.0), (12.0, 12.0), (-2.0, 12.0)),
        )
        series.registration_results = MolTrackRegistrationResultSet(
            settings=MolTrackRegistrationSettings(backend="phase_correlation"),
            results_by_frame={
                0: MolTrackRegistrationFrameResult(
                    frame_index=0,
                    shift_xy=(0.0, 0.0),
                    method="phase_correlation",
                )
            },
        )
        phase_coordinates = build_molecular_sample_coordinates(
            series,
            tuple(
                build_molecular_centroids(
                    series,
                    frame_index=0,
                    source_view="expanded_aligned",
                )
            ),
            frame_index=0,
            source_view="expanded_aligned",
        )
        series.registration_results = MolTrackRegistrationResultSet(
            settings=MolTrackRegistrationSettings(backend="optical_flow_median"),
            results_by_frame={
                0: MolTrackRegistrationFrameResult(
                    frame_index=0,
                    shift_xy=(0.0, 0.0),
                    method="optical_flow_median",
                )
            },
        )
        optical_flow_coordinates = build_molecular_sample_coordinates(
            series,
            tuple(
                build_molecular_centroids(
                    series,
                    frame_index=0,
                    source_view="expanded_aligned",
                )
            ),
            frame_index=0,
            source_view="expanded_aligned",
        )
        self.assertNotEqual(
            phase_coordinates.registration_fingerprint,
            optical_flow_coordinates.registration_fingerprint,
        )


class MolecularM6FrameAnalysisTests(unittest.TestCase):
    def test_frame_result_contains_full_m6_analysis_from_plot_centroids(self) -> None:
        points_xy_nm = np.asarray(
            [
                (5.0 + 2.0 * (column + 0.5 * (row % 2)), 5.0 + np.sqrt(3.0) * row)
                for row in range(5)
                for column in range(5)
            ]
        )
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(x - 0.25, 40.0 - y - 0.25, x + 0.25, 40.0 - y + 0.25),
                    confidence=0.9,
                    detection_id=f"molecule-{index:02d}",
                )
                for index, (x, y) in enumerate(points_xy_nm)
            ],
            source_view="raw",
            frame_shape=(40, 40),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 40, 40), dtype=np.float32),
            metadata=STMSequenceMetadata(
                raw_header={"General Info": {"Angle": "0.0"}},
                pixels_x=40,
                pixels_y=40,
                size_nm_x=40.0,
                size_nm_y=40.0,
                scan_angle_deg=0.0,
            ),
            molecular_detections=detections,
        )
        settings = MolecularM6OrientationAnalysisSettings(
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

        result = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("condition", 0, 0),
            source_view="raw",
            m6_orientation_settings=settings,
        ).frame_results[0]
        legacy_result = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("condition", 0, 0),
            source_view="raw",
        ).frame_results[0]

        m6 = result.m6_orientation_analysis
        self.assertIsInstance(m6, MolecularM6OrientationAnalysis)
        assert m6 is not None
        self.assertEqual(m6.settings, settings)
        self.assertEqual(m6.source_view, "raw")
        self.assertEqual(m6.point_source_ids, result.plot_data.point_source_ids)
        self.assertEqual(m6.point_source_ids, m6.first_shell_graph.point_ids)
        np.testing.assert_allclose(m6.points_xy_nm, result.plot_data.points_xy)
        np.testing.assert_allclose(m6.points_xy_nm, points_xy_nm)
        self.assertEqual(
            m6.coordinate_transform_fingerprint,
            result.plot_data.coordinate_transform_fingerprint,
        )
        self.assertEqual(m6.coordinate_frame, "sample_nm")
        self.assertEqual(m6.orientation_reference, "+x_sample_axis")
        self.assertFalse(m6.scan_angle_missing_qc)
        self.assertIsNotNone(m6.local_order)
        self.assertIsNotNone(m6.segmentation)
        self.assertIsNotNone(m6.pair_correlation)
        self.assertIsNotNone(m6.frame_aggregates)
        self.assertEqual(result.distance_metrics, legacy_result.distance_metrics)
        self.assertEqual(result.angle_metrics, legacy_result.angle_metrics)
        self.assertIsNotNone(result.angle_metrics.line_order_score)
        with self.assertRaisesRegex(ValueError, "this frame and valid FOV"):
            replace(
                m6,
                pair_correlation=replace(m6.pair_correlation, frame_index=1),
            )
        with self.assertRaisesRegex(
            ValueError,
            "graph coordinates must match Position Analysis points",
        ):
            replace(
                m6,
                sample_coordinates=replace(
                    m6.sample_coordinates,
                    points_xy_nm=tuple(
                        (x + 0.5, y) for x, y in m6.points_xy_nm
                    ),
                ),
            )
        shifted_plot = replace(
            result.plot_data,
            points_xy=tuple((x + 1.0, y) for x, y in result.plot_data.points_xy),
        )
        with self.assertRaisesRegex(ValueError, "Position Analysis points"):
            replace(result, plot_data=shifted_plot)
        shifted_centroid = replace(
            result.centroids[0],
            x_px=result.centroids[0].x_px + 1.0,
        )
        with self.assertRaisesRegex(ValueError, "Position Analysis points"):
            replace(
                result,
                centroids=(shifted_centroid,) + result.centroids[1:],
            )

    def test_missing_scan_angle_is_an_explicit_m6_qc_assumption(self) -> None:
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1.0, 2.0, 3.0, 4.0),
                    confidence=0.9,
                    detection_id="molecule-a",
                )
            ],
            source_view="raw",
            frame_shape=(10, 10),
        )
        metadata = STMSequenceMetadata(
            pixels_x=10,
            pixels_y=10,
            size_nm_x=10.0,
            size_nm_y=10.0,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 10, 10), dtype=np.float32),
            metadata=metadata,
            molecular_detections=detections,
        )

        result = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("condition", 0, 0),
            source_view="raw",
            m6_orientation_settings=MolecularM6OrientationAnalysisSettings(),
        ).frame_results[0]

        m6 = result.m6_orientation_analysis
        assert m6 is not None
        self.assertTrue(m6.scan_angle_missing_qc)
        self.assertEqual(m6.orientation_reference, "scan_x_axis_assumed_sample_x")
        self.assertEqual(
            m6.first_shell_graph.orientation_reference,
            "scan_x_axis_assumed_sample_x",
        )
        self.assertEqual(m6.points_xy_nm, ((2.0, 7.0),))
        self.assertEqual(
            m6.coordinate_transform_fingerprint,
            result.plot_data.coordinate_transform_fingerprint,
        )

    def test_disabled_m6_preserves_legacy_position_analysis(self) -> None:
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(0, (0.0, 0.0, 2.0, 2.0), 0.9),
                MolecularDetection(0, (3.0, 0.0, 5.0, 2.0), 0.8),
            ],
            source_view="raw",
            frame_shape=(8, 8),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
            molecular_detections=detections,
        )

        result = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("legacy", 0, 0),
            source_view="raw",
        ).frame_results[0]

        self.assertIsNone(result.m6_orientation_analysis)
        self.assertEqual(result.plot_data.points_xy, ((1.0, 1.0), (4.0, 1.0)))
        self.assertEqual(result.plot_data.coordinate_frame, "image_xy")
        self.assertIsNone(result.plot_data.coordinate_transform_fingerprint)
        self.assertEqual(result.angle_metrics.line_order_score, 1.0)

    def test_enabled_m6_requires_physical_pixel_calibration(self) -> None:
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )

        with self.assertRaisesRegex(ValueError, "positive nm-per-pixel"):
            analyze_molecular_frame_range(
                series,
                MolecularFrameRange("uncalibrated", 0, 0),
                source_view="raw",
                m6_orientation_settings=MolecularM6OrientationAnalysisSettings(),
            )

    def test_expanded_padding_centroid_is_plotted_but_excluded_from_m6(self) -> None:
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(3.0, 3.0, 5.0, 5.0),
                    confidence=0.9,
                    source_view="expanded_aligned",
                    detection_id="inside-valid-fov",
                ),
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
                    confidence=0.8,
                    source_view="expanded_aligned",
                    detection_id="inside-padding",
                ),
            ],
            source_view="expanded_aligned",
            frame_shape=(14, 14),
        )
        metadata = STMSequenceMetadata(
            raw_header={"General Info": {"Angle": "0.0"}},
            pixels_x=10,
            pixels_y=10,
            size_nm_x=10.0,
            size_nm_y=10.0,
            scan_angle_deg=0.0,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 10, 10), dtype=np.float32),
            metadata=metadata,
            molecular_detections=detections,
            expanded_aligned_stack=SimpleNamespace(
                frames=np.zeros((1, 14, 14), dtype=np.float32),
                metadata=STMSequenceMetadata(
                    raw_header={"General Info": {"Angle": "0.0"}},
                    pixels_x=14,
                    pixels_y=14,
                    size_nm_x=14.0,
                    size_nm_y=14.0,
                    scan_angle_deg=0.0,
                ),
                canvas_offset_xy=(2.0, 2.0),
                padding_ltrb=(2, 2, 2, 2),
                frame_origins_xy=np.asarray(((2.0, 2.0),)),
            ),
        )

        result = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("expanded", 0, 0),
            source_view="expanded_aligned",
            m6_orientation_settings=MolecularM6OrientationAnalysisSettings(),
        ).frame_results[0]

        m6 = result.m6_orientation_analysis
        assert m6 is not None
        self.assertEqual(result.plot_data.point_count, 2)
        self.assertEqual(m6.point_source_ids, result.plot_data.point_source_ids)
        self.assertEqual(m6.invalid_position_point_ids, ("inside-padding",))
        self.assertEqual(
            m6.first_shell_graph.point_ids,
            ("inside-valid-fov", "inside-padding"),
        )
        self.assertEqual(
            m6.segmentation.assignment_status,
            ("insufficient_neighbors", "invalid_position"),
        )
        self.assertEqual(m6.pair_correlation.representative_point_ids, ("inside-valid-fov",))
        self.assertEqual(m6.frame_aggregates.original_observation_count, 2)
        self.assertEqual(m6.frame_aggregates.valid_representative_count, 1)
        self.assertEqual(m6.frame_aggregates.invalid_position_count, 1)
        self.assertEqual(
            m6.frame_aggregates.invalid_position_fraction_of_original,
            0.5,
        )

    def test_raw_and_expanded_results_share_ids_and_apply_known_shift(self) -> None:
        points_xy_nm = np.asarray(
            [
                (2.0 + 2.0 * (column + 0.5 * (row % 2)), 2.0 + np.sqrt(3.0) * row)
                for row in range(3)
                for column in range(3)
            ]
        )
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(x - 0.2, 10.0 - y - 0.2, x + 0.2, 10.0 - y + 0.2),
                    confidence=0.9,
                    detection_id=f"molecule-{index}",
                )
                for index, (x, y) in enumerate(points_xy_nm)
            ],
            source_view="raw",
            frame_shape=(10, 10),
        )
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(
                        x + 2.0 - 0.2,
                        10.0 - y - 0.2,
                        x + 2.0 + 0.2,
                        10.0 - y + 0.2,
                    ),
                    confidence=0.9,
                    source_view="expanded_aligned",
                    detection_id=f"molecule-{index}",
                )
                for index, (x, y) in enumerate(points_xy_nm)
            ],
            source_view="expanded_aligned",
            frame_shape=(14, 14),
        )
        raw_metadata = STMSequenceMetadata(
            pixels_x=10,
            pixels_y=10,
            size_nm_x=10.0,
            size_nm_y=10.0,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 10, 10), dtype=np.float32),
            metadata=raw_metadata,
            molecular_detections=detections,
            expanded_aligned_stack=SimpleNamespace(
                frames=np.zeros((1, 14, 14), dtype=np.float32),
                metadata=STMSequenceMetadata(
                    pixels_x=14,
                    pixels_y=14,
                    size_nm_x=14.0,
                    size_nm_y=14.0,
                ),
                canvas_offset_xy=(2.0, 2.0),
                padding_ltrb=(2, 2, 2, 2),
                frame_origins_xy=np.asarray(((2.0, 0.0),)),
            ),
        )
        settings = MolecularM6OrientationAnalysisSettings(
            first_shell_r_min_nm=1.5,
            first_shell_r_max_nm=2.3,
            min_ordered_component_size=3,
            min_seed_size=3,
            min_domain_size=4,
            gr_min_expected_pair_exposure=0.1,
        )

        raw = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("raw", 0, 0),
            source_view="raw",
            m6_orientation_settings=settings,
        ).frame_results[0]
        expanded = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("aligned", 0, 0),
            source_view="expanded_aligned",
            m6_orientation_settings=settings,
        ).frame_results[0]

        raw_m6 = raw.m6_orientation_analysis
        expanded_m6 = expanded.m6_orientation_analysis
        assert raw_m6 is not None and expanded_m6 is not None
        self.assertEqual(
            raw_m6.point_source_ids,
            tuple(f"molecule-{index}" for index in range(len(points_xy_nm))),
        )
        self.assertEqual(expanded_m6.point_source_ids, raw_m6.point_source_ids)
        np.testing.assert_allclose(raw_m6.points_xy_nm, points_xy_nm)
        np.testing.assert_allclose(
            expanded_m6.points_xy_nm,
            points_xy_nm + np.asarray((0.0, 2.0)),
        )
        np.testing.assert_allclose(
            raw_m6.sample_coordinates.distance_to_valid_fov_boundary_nm,
            expanded_m6.sample_coordinates.distance_to_valid_fov_boundary_nm,
        )
        self.assertEqual(
            raw_m6.first_shell_graph.edges_ij,
            expanded_m6.first_shell_graph.edges_ij,
        )
        np.testing.assert_allclose(
            raw_m6.first_shell_graph.distances_nm,
            expanded_m6.first_shell_graph.distances_nm,
        )
        np.testing.assert_allclose(
            tuple(np.nan if value is None else value for value in raw_m6.local_order.q6),
            tuple(
                np.nan if value is None else value
                for value in expanded_m6.local_order.q6
            ),
            equal_nan=True,
        )
        self.assertEqual(
            raw_m6.segmentation.assignment_status,
            expanded_m6.segmentation.assignment_status,
        )
        self.assertEqual(
            raw_m6.frame_aggregates.full_domain_molecule_fraction,
            expanded_m6.frame_aggregates.full_domain_molecule_fraction,
        )
        self.assertEqual(
            raw_m6.frame_aggregates.full_domain_footprint_fraction,
            expanded_m6.frame_aggregates.full_domain_footprint_fraction,
        )
        np.testing.assert_allclose(
            raw_m6.pair_correlation.g_r,
            expanded_m6.pair_correlation.g_r,
            equal_nan=True,
        )
        self.assertEqual(
            raw_m6.spatial_calibration_fingerprint,
            expanded_m6.spatial_calibration_fingerprint,
        )
        self.assertEqual(raw_m6.registration_fingerprint, "unregistered")
        self.assertNotEqual(
            expanded_m6.registration_fingerprint,
            raw_m6.registration_fingerprint,
        )
        self.assertEqual(
            expanded_m6.coordinate_transform_fingerprint,
            expanded.plot_data.coordinate_transform_fingerprint,
        )
        with self.assertRaisesRegex(ValueError, "Position Analysis points"):
            replace(raw, m6_orientation_analysis=expanded_m6)


if __name__ == "__main__":
    unittest.main()
