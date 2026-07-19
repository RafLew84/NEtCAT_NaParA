from dataclasses import FrozenInstanceError, replace
import math
import unittest
from unittest.mock import Mock, patch

import numpy as np

from moltrack.analysis import (
    M6DomainTypeClassificationSettings,
    M6DomainTypeObservation,
    MolecularFrameRange,
    MolecularFrameRangeSelection,
    MolecularM6OrientationAnalysis,
    MolecularM6OrientationAnalysisSettings,
    analyze_molecular_frame_range,
    compare_molecular_frame_ranges,
    extract_m6_domain_type_observations,
)
from moltrack.analysis._m6_context_fingerprint import m6_context_fingerprint
from moltrack.analysis._m6_settings_fingerprint import m6_settings_fingerprint
from moltrack.core import MolecularDetection, MolecularDetectionSet, MolTrackImageSeries
from nanotrack.core import STMSequenceMetadata


def _triangular_patch(
    width: int,
    height: int,
    shift_xy_nm: tuple[float, float],
    *,
    angle_deg: float = 0.0,
) -> np.ndarray:
    points = np.asarray(
        [
            (2.0 * (column + 0.5 * (row % 2)), math.sqrt(3.0) * row)
            for row in range(height)
            for column in range(width)
        ],
        dtype=np.float64,
    )
    angle = math.radians(angle_deg)
    rotation = np.asarray(
        ((math.cos(angle), -math.sin(angle)), (math.sin(angle), math.cos(angle)))
    )
    return points @ rotation.T + np.asarray(shift_xy_nm)


def _series(
    frame_points: tuple[np.ndarray, ...],
    *,
    reverse_detections: bool = False,
) -> MolTrackImageSeries:
    frame_size = 100
    detections = MolecularDetectionSet(frame_count=len(frame_points))
    for frame_index, points in enumerate(frame_points):
        records = [
            MolecularDetection(
                frame_index=frame_index,
                bbox_xyxy=(
                    x - 0.2,
                    frame_size - y - 0.2,
                    x + 0.2,
                    frame_size - y + 0.2,
                ),
                confidence=0.9,
                detection_id=f"frame-{frame_index}-point-{point_index:04d}",
            )
            for point_index, (x, y) in enumerate(points)
        ]
        if reverse_detections:
            records.reverse()
        detections.set_detections(
            frame_index,
            records,
            source_view="raw",
            frame_shape=(frame_size, frame_size),
        )
    return MolTrackImageSeries(
        source_path="movie.mpp",
        raw_frames=np.zeros(
            (len(frame_points), frame_size, frame_size),
            dtype=np.float32,
        ),
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


def _m6_settings() -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings(
        duplicate_max_distance_nm=0.1,
        first_shell_r_min_nm=1.5,
        first_shell_r_max_nm=2.3,
        min_neighbors_for_local_order=2,
        min_neighbors_for_seed=2,
        min_ordered_component_size=3,
        min_seed_size=3,
        min_domain_size=12,
        q_seed=0.5,
        q_grow=0.1,
        seed_angle_tolerance_deg=8.0,
        grow_angle_tolerance_deg=12.0,
        domain_merge_angle_tolerance_deg=8.0,
        footprint_support_radius_nm=1.2,
        min_bonds_for_domain_length_stats=50,
        domain_bond_length_robust_cv_qc_threshold=0.0,
        gr_bin_width_nm=0.25,
        gr_max_nm=10.0,
        gr_min_expected_pair_exposure=0.1,
    )


def _observation_identity(observation: M6DomainTypeObservation) -> tuple[object, ...]:
    return (
        observation.stable_key,
        observation.component_type,
        observation.qualification_status,
        observation.unclassified_reason,
        observation.insufficient_bonds_for_length_stats_qc,
        observation.bond_length_heterogeneity_qc,
        observation.edge_truncated,
        observation.footprint_disconnected_qc,
    )


def _observation_numeric_signature(
    observation: M6DomainTypeObservation,
) -> tuple[float, ...]:
    optional_values = (
        observation.footprint_fraction_of_valid_fov,
        observation.domain_median_bond_length_nm,
        observation.domain_bond_length_mad_nm,
        observation.domain_bond_length_iqr_nm,
        observation.domain_bond_length_robust_cv,
    )
    return (
        observation.orientation_deg,
        float(observation.molecule_count),
        observation.footprint_area_nm2,
        observation.domain_mean_local_q6,
        observation.domain_coherent_q6,
        observation.centroid_x_nm,
        observation.centroid_y_nm,
        *observation.bounds_xyxy_nm,
        *(float("nan") if value is None else value for value in optional_values),
    )


class M6DomainTypeObservationTests(unittest.TestCase):
    def test_m6_context_excludes_frame_local_registration_provenance(self) -> None:
        analysis = Mock(spec=MolecularM6OrientationAnalysis)
        analysis.source_view = "expanded_aligned"
        analysis.coordinate_frame = "sample_nm"
        analysis.orientation_reference = "+x_sample_axis"
        analysis.spatial_calibration_fingerprint = "calibration-v1"
        analysis.settings = _m6_settings()
        analysis.registration_fingerprint = "frame-registration-1"
        first_fingerprint = m6_context_fingerprint(analysis)

        analysis.registration_fingerprint = "frame-registration-2"

        self.assertEqual(m6_context_fingerprint(analysis), first_fingerprint)

    @classmethod
    def setUpClass(cls) -> None:
        cls.frame_points = (
            _triangular_patch(8, 8, (8.0, 8.0)),
            _triangular_patch(3, 3, (8.0, 8.0)),
            _triangular_patch(4, 4, (8.0, 8.0)),
        )
        cls.series = _series(cls.frame_points)
        cls.series.source_frame_indices = (30, 10, 20)
        cls.range_analysis = analyze_molecular_frame_range(
            cls.series,
            MolecularFrameRange("all conditions", 0, 2),
            source_view="raw",
            m6_orientation_settings=_m6_settings(),
        )

    def test_extracts_complete_full_small_missing_and_heterogeneous_observations(self) -> None:
        classification_settings = M6DomainTypeClassificationSettings(
            include_small_ordered_islands=False,
            exclude_bond_length_heterogeneity_qc=False,
        )

        with patch(
            "moltrack.analysis.orientation_domain_analysis.build_first_shell_graph"
        ) as graph_builder:
            observations = extract_m6_domain_type_observations(
                self.range_analysis,
                settings=classification_settings,
            )

        graph_builder.assert_not_called()
        self.assertEqual(len(observations), 3)
        self.assertEqual(
            tuple(observation.frame_index for observation in observations),
            (0, 1, 2),
        )
        self.assertEqual(
            tuple(observation.source_frame_index for observation in observations),
            (30, 10, 20),
        )
        full_heterogeneous, small_island, full_missing = observations
        self.assertEqual(full_heterogeneous.component_type, "full_domain")
        self.assertEqual(full_heterogeneous.qualification_status, "qualified")
        self.assertIsNone(full_heterogeneous.unclassified_reason)
        self.assertTrue(full_heterogeneous.bond_length_heterogeneity_qc)
        self.assertIsNotNone(full_heterogeneous.domain_median_bond_length_nm)

        self.assertEqual(small_island.component_type, "small_ordered_island")
        self.assertEqual(small_island.qualification_status, "unclassified")
        self.assertEqual(
            small_island.unclassified_reason,
            "small_ordered_island_excluded",
        )

        self.assertEqual(full_missing.component_type, "full_domain")
        self.assertEqual(full_missing.qualification_status, "unclassified")
        self.assertEqual(
            full_missing.unclassified_reason,
            "missing_bond_length_statistics",
        )
        self.assertTrue(full_missing.insufficient_bonds_for_length_stats_qc)
        self.assertIsNone(full_missing.domain_median_bond_length_nm)
        with self.assertRaisesRegex(ValueError, "qualified.*statistics"):
            replace(
                full_missing,
                qualification_status="qualified",
                unclassified_reason=None,
            )

        frame_result = self.range_analysis.frame_results[0]
        m6 = frame_result.m6_orientation_analysis
        assert m6 is not None
        metrics = m6.frame_aggregates.domain_metrics.components[0]
        footprint = m6.frame_aggregates.footprint_partition.components[0]
        self.assertEqual(full_heterogeneous.range_name, "all conditions")
        self.assertEqual(full_heterogeneous.range_start_frame, 0)
        self.assertEqual(full_heterogeneous.range_end_frame, 2)
        self.assertEqual(full_heterogeneous.source_view, "raw")
        self.assertEqual(
            full_heterogeneous.m6_settings_fingerprint,
            m6_settings_fingerprint(m6.settings),
        )
        self.assertTrue(full_heterogeneous.m6_context_fingerprint)
        self.assertEqual(full_heterogeneous.ordered_component_id, 0)
        self.assertEqual(full_heterogeneous.m6_orientation_domain_id, 0)
        self.assertEqual(full_heterogeneous.orientation_deg, metrics.orientation_deg)
        self.assertEqual(full_heterogeneous.molecule_count, metrics.molecule_count)
        self.assertEqual(
            full_heterogeneous.footprint_area_nm2,
            footprint.footprint_area_nm2,
        )
        self.assertEqual(
            full_heterogeneous.footprint_fraction_of_valid_fov,
            footprint.footprint_fraction_of_valid_fov,
        )
        self.assertEqual(
            full_heterogeneous.bounds_xyxy_nm,
            (metrics.min_x_nm, metrics.min_y_nm, metrics.max_x_nm, metrics.max_y_nm),
        )
        with self.assertRaises(FrozenInstanceError):
            full_heterogeneous.molecule_count = 0

    def test_classification_settings_change_reasons_without_dropping_records(self) -> None:
        excluded_heterogeneity = extract_m6_domain_type_observations(
            self.range_analysis,
            settings=M6DomainTypeClassificationSettings(
                include_small_ordered_islands=True,
                exclude_bond_length_heterogeneity_qc=True,
            ),
        )

        self.assertEqual(len(excluded_heterogeneity), 3)
        self.assertEqual(
            excluded_heterogeneity[0].unclassified_reason,
            "bond_length_heterogeneity_qc",
        )
        self.assertEqual(
            excluded_heterogeneity[1].unclassified_reason,
            "missing_bond_length_statistics",
        )

    def test_extracts_one_or_two_ranges_in_range_frame_component_order(self) -> None:
        comparison = compare_molecular_frame_ranges(
            self.series,
            MolecularFrameRangeSelection(
                frame_count=3,
                source_view="raw",
                first_range=MolecularFrameRange("later", 1, 2),
                second_range=MolecularFrameRange("early", 0, 0),
            ),
            m6_orientation_settings=_m6_settings(),
        )
        settings = M6DomainTypeClassificationSettings(
            exclude_bond_length_heterogeneity_qc=False
        )

        observations = extract_m6_domain_type_observations(
            comparison,
            settings=settings,
        )
        permuted_single = replace(
            self.range_analysis,
            frame_results=tuple(reversed(self.range_analysis.frame_results)),
        )

        self.assertEqual(
            tuple(
                (observation.range_name, observation.frame_index)
                for observation in observations
            ),
            (("later", 1), ("later", 2), ("early", 0)),
        )
        self.assertEqual(
            extract_m6_domain_type_observations(
                permuted_single,
                settings=settings,
            ),
            extract_m6_domain_type_observations(
                self.range_analysis,
                settings=settings,
            ),
        )

    def test_overlapping_same_named_ranges_keep_unique_stable_keys(self) -> None:
        comparison = compare_molecular_frame_ranges(
            self.series,
            MolecularFrameRangeSelection(
                frame_count=3,
                source_view="raw",
                first_range=MolecularFrameRange("same", 0, 1),
                second_range=MolecularFrameRange("same", 1, 2),
            ),
            m6_orientation_settings=_m6_settings(),
        )

        observations = extract_m6_domain_type_observations(
            comparison,
            settings=M6DomainTypeClassificationSettings(
                exclude_bond_length_heterogeneity_qc=False
            ),
        )

        self.assertEqual(len(observations), 4)
        self.assertEqual(len({observation.stable_key for observation in observations}), 4)
        shared_frame = tuple(
            observation for observation in observations if observation.frame_index == 1
        )
        self.assertEqual(len(shared_frame), 2)
        self.assertNotEqual(shared_frame[0].stable_key, shared_frame[1].stable_key)

    def test_observation_features_are_stable_after_molecule_input_permutation(self) -> None:
        two_domains = np.vstack(
            (
                _triangular_patch(4, 4, (8.0, 8.0)),
                _triangular_patch(4, 4, (42.0, 8.0), angle_deg=20.0),
            )
        )
        settings = replace(
            _m6_settings(),
            min_bonds_for_domain_length_stats=5,
            domain_bond_length_robust_cv_qc_threshold=0.2,
        )
        classification_settings = M6DomainTypeClassificationSettings()

        normal = analyze_molecular_frame_range(
            _series((two_domains,)),
            MolecularFrameRange("condition", 0, 0),
            source_view="raw",
            m6_orientation_settings=settings,
        )
        permuted = analyze_molecular_frame_range(
            _series((two_domains,), reverse_detections=True),
            MolecularFrameRange("condition", 0, 0),
            source_view="raw",
            m6_orientation_settings=settings,
        )

        normal_observations = extract_m6_domain_type_observations(
            normal,
            settings=classification_settings,
        )
        permuted_observations = extract_m6_domain_type_observations(
            permuted,
            settings=classification_settings,
        )
        self.assertEqual(
            tuple(map(_observation_identity, normal_observations)),
            tuple(map(_observation_identity, permuted_observations)),
        )
        for normal_observation, permuted_observation in zip(
            normal_observations,
            permuted_observations,
        ):
            np.testing.assert_allclose(
                _observation_numeric_signature(normal_observation),
                _observation_numeric_signature(permuted_observation),
                rtol=1e-12,
                atol=1e-12,
                equal_nan=True,
            )


if __name__ == "__main__":
    unittest.main()
