import cmath
import math
import unittest
from dataclasses import FrozenInstanceError, replace

import numpy as np

from moltrack.analysis import (
    LocalSixfoldBondOrderField,
    M6OrientationFrameAggregates,
    aggregate_m6_orientation_frame,
    compute_m6_orientation_footprint_partition,
)
from moltrack.analysis._m6_settings_fingerprint import m6_settings_fingerprint
from test_orientation_domain_footprint import _metrics, _partition


def _field_for_metrics(
    metrics,
    *,
    edge_indices: tuple[int, ...] = (),
    valid_psi6: dict[int, complex] | None = None,
) -> LocalSixfoldBondOrderField:
    edge_set = set(edge_indices)
    supplied_psi6 = valid_psi6 or {}
    statuses = []
    psi6 = []
    q6 = []
    orientations = []
    orientation_status = []
    neighbor_count = []
    medians = []
    mads = []
    iqrs = []
    robust_cvs = []
    boundary_distances = []
    for index, assignment_status in enumerate(metrics.segmentation.assignment_status):
        if assignment_status in {"assigned", "boundary_or_disordered"}:
            status = "valid_order"
            neighbors = 3
            ordered_component_id = metrics.segmentation.ordered_component_id[index]
            default_psi6 = (
                1.0 + 0.0j
                if ordered_component_id < 0
                else complex(
                    metrics.components[
                        ordered_component_id
                    ].domain_coherent_q6,
                    0.0,
                )
            )
            point_psi6 = supplied_psi6.get(index, default_psi6)
            point_q6 = abs(point_psi6)
            psi6.append(point_psi6)
            q6.append(point_q6)
            if point_q6 == 0.0:
                orientations.append(None)
                orientation_status.append("undefined_zero_magnitude")
            else:
                orientations.append(
                    math.degrees(cmath.phase(point_psi6) / 6.0) % 60.0
                )
                orientation_status.append("defined")
        else:
            status = assignment_status
            neighbors = 2 if status == "insufficient_neighbors" else 0
            psi6.append(None)
            q6.append(None)
            orientations.append(None)
            orientation_status.append("not_available")
        statuses.append(status)
        neighbor_count.append(neighbors)
        if neighbors:
            medians.append(2.0)
            mads.append(0.0)
            iqrs.append(0.0)
            robust_cvs.append(0.0)
        else:
            medians.append(None)
            mads.append(None)
            iqrs.append(None)
            robust_cvs.append(None)
        boundary_distances.append(
            None
            if status == "invalid_position"
            else (1.0 if index in edge_set else 10.0)
        )
    edge_flags = tuple(
        distance is not None and distance < metrics.settings.first_shell_r_max_nm
        for distance in boundary_distances
    )
    return LocalSixfoldBondOrderField(
        source_ids=metrics.source_ids,
        point_count=metrics.point_count,
        psi6=tuple(psi6),
        q6=tuple(q6),
        lattice_orientation_deg=tuple(orientations),
        orientation_status=tuple(orientation_status),
        neighbor_count=tuple(neighbor_count),
        computation_status=tuple(statuses),
        local_median_bond_length_nm=tuple(medians),
        local_bond_length_mad_nm=tuple(mads),
        local_bond_length_iqr_nm=tuple(iqrs),
        local_bond_length_robust_cv=tuple(robust_cvs),
        physical_duplicate_qc=metrics.segmentation.physical_duplicate_qc,
        geometry_duplicate_qc=metrics.segmentation.geometry_duplicate_qc,
        edge_truncated_neighborhood=edge_flags,
        distance_to_valid_fov_boundary_nm=tuple(boundary_distances),
        first_shell_r_max_nm=metrics.settings.first_shell_r_max_nm,
        coordinate_frame="sample_nm",
        orientation_reference=metrics.orientation_reference,
        spatial_calibration_fingerprint=metrics.spatial_calibration_fingerprint,
        registration_fingerprint=metrics.registration_fingerprint,
        min_neighbors_for_local_order=metrics.settings.min_neighbors_for_local_order,
        analysis_settings_fingerprint=m6_settings_fingerprint(metrics.settings),
    )


def _replace_segmentation_state(
    metrics,
    *,
    assignment_status=None,
    edge_truncated=None,
):
    segmentation = replace(
        metrics.segmentation,
        assignment_status=(
            metrics.segmentation.assignment_status
            if assignment_status is None
            else tuple(assignment_status)
        ),
        edge_truncated_neighborhood=(
            metrics.segmentation.edge_truncated_neighborhood
            if edge_truncated is None
            else tuple(edge_truncated)
        ),
    )
    return replace(metrics, segmentation=segmentation)


def _set_component_coherence(metrics, values: tuple[float, ...]):
    return replace(
        metrics,
        components=tuple(
            replace(
                component,
                domain_mean_local_q6=value,
                domain_coherent_q6=value,
            )
            for component, value in zip(metrics.components, values)
        ),
    )


class OrientationDomainFrameAggregateTests(unittest.TestCase):
    def test_aggregates_mixed_domains_with_exact_denominators_and_weights(self) -> None:
        points = np.asarray(
            tuple((index + 0.5, 0.5) for index in range(9))
            + ((0.5, 0.5), (math.nan, math.nan))
        )
        metrics = _metrics(
            points,
            components=(
                ("full_domain", (0, 1, 2, 3)),
                ("full_domain", (4, 5)),
                ("small_ordered_island", (6,)),
            ),
            excluded={9: "duplicate_excluded", 10: "invalid_position"},
            support_radius_nm=10.0,
        )
        statuses = list(metrics.segmentation.assignment_status)
        statuses[7] = "boundary_or_disordered"
        edge_flags = [False] * len(points)
        edge_flags[0] = True
        edge_flags[8] = True
        metrics = _replace_segmentation_state(
            metrics,
            assignment_status=statuses,
            edge_truncated=edge_flags,
        )
        dominant_coherent_q6 = math.sqrt(9.25) / 4.0
        metrics = replace(
            metrics,
            components=(
                replace(
                    metrics.components[0],
                    domain_mean_local_q6=0.875,
                    domain_coherent_q6=dominant_coherent_q6,
                ),
                replace(
                    metrics.components[1],
                    domain_mean_local_q6=1.0,
                    domain_coherent_q6=1.0,
                ),
                replace(
                    metrics.components[2],
                    domain_mean_local_q6=1.0,
                    domain_coherent_q6=1.0,
                ),
            ),
        )
        footprint = _partition(points, metrics=metrics, window_size_nm=(9.0, 1.0))
        local_order = _field_for_metrics(
            metrics,
            edge_indices=(0, 8),
            valid_psi6={
                0: 0.0 + 0.5j,
                1: 1.0 + 0.0j,
                2: 1.0 + 0.0j,
                3: 1.0 + 0.0j,
                4: -1.0 + 0.0j,
                5: -1.0 + 0.0j,
                6: -1.0 + 0.0j,
                7: 1.0 + 0.0j,
            },
        )

        result = aggregate_m6_orientation_frame(
            local_order=local_order,
            domain_metrics=metrics,
            footprint_partition=footprint,
        )

        self.assertIsInstance(result, M6OrientationFrameAggregates)
        self.assertEqual(result.full_domain_count, 2)
        self.assertEqual(result.small_ordered_island_count, 1)
        self.assertEqual(result.ordered_component_count, 3)
        self.assertEqual(result.original_observation_count, 11)
        self.assertEqual(result.valid_representative_count, 9)
        self.assertEqual(result.duplicate_excluded_count, 1)
        self.assertEqual(result.invalid_position_count, 1)
        self.assertAlmostEqual(result.valid_fov_area_nm2, 9.0)
        self.assertAlmostEqual(result.supported_area_nm2, 9.0)
        self.assertAlmostEqual(result.full_domain_molecule_fraction, 6.0 / 9.0)
        self.assertAlmostEqual(result.small_island_molecule_fraction, 1.0 / 9.0)
        self.assertAlmostEqual(result.unassigned_molecule_fraction, 2.0 / 9.0)
        self.assertAlmostEqual(result.assigned_molecule_fraction, 7.0 / 9.0)
        self.assertAlmostEqual(result.largest_domain_molecule_fraction, 4.0 / 9.0)
        self.assertAlmostEqual(result.duplicate_excluded_fraction_of_original, 1.0 / 11.0)
        self.assertAlmostEqual(result.invalid_position_fraction_of_original, 1.0 / 11.0)
        self.assertAlmostEqual(result.full_domain_footprint_fraction, 6.0 / 9.0)
        self.assertAlmostEqual(result.small_island_footprint_fraction, 1.0 / 9.0)
        self.assertAlmostEqual(
            result.unassigned_supported_footprint_fraction,
            2.0 / 9.0,
        )
        self.assertAlmostEqual(result.unsupported_background_fraction, 0.0)
        self.assertAlmostEqual(result.assigned_footprint_fraction, 7.0 / 9.0)
        self.assertAlmostEqual(result.largest_domain_footprint_fraction, 4.0 / 9.0)
        self.assertAlmostEqual(result.mean_local_q6_interior, 1.0)
        self.assertAlmostEqual(result.global_q6_interior, 1.0 / 7.0)
        self.assertAlmostEqual(result.mean_local_q6_all_valid, 7.5 / 8.0)
        self.assertAlmostEqual(result.global_q6_all_valid, math.sqrt(1.25) / 8.0)
        self.assertAlmostEqual(
            result.edge_truncated_fraction_of_valid_representatives,
            2.0 / 9.0,
        )
        expected_weighted_q6 = (4.0 * dominant_coherent_q6 + 2.0) / 6.0
        self.assertAlmostEqual(
            result.full_domain_molecule_weighted_coherent_q6,
            expected_weighted_q6,
        )
        self.assertAlmostEqual(
            result.full_domain_footprint_weighted_coherent_q6,
            expected_weighted_q6,
        )
        self.assertAlmostEqual(result.mean_full_domain_footprint_area_nm2, 3.0)
        self.assertAlmostEqual(result.median_full_domain_footprint_area_nm2, 3.0)
        expected_entropy = -(
            (2.0 / 3.0) * math.log(2.0 / 3.0)
            + (1.0 / 3.0) * math.log(1.0 / 3.0)
        ) / math.log(2.0)
        self.assertAlmostEqual(result.domain_molecule_entropy, expected_entropy)
        self.assertAlmostEqual(result.domain_footprint_entropy, expected_entropy)
        self.assertFalse(result.non_positive_valid_fov_area_qc)
        self.assertAlmostEqual(
            result.full_domain_molecule_fraction
            + result.small_island_molecule_fraction
            + result.unassigned_molecule_fraction,
            1.0,
        )
        self.assertAlmostEqual(
            result.full_domain_footprint_fraction
            + result.small_island_footprint_fraction
            + result.unassigned_supported_footprint_fraction
            + result.unsupported_background_fraction,
            1.0,
        )
        self.assertFalse(hasattr(result, "support_limited_fraction"))
        self.assertFalse(hasattr(result, "unassigned_footprint_fraction"))
        with self.assertRaises(FrozenInstanceError):
            result.full_domain_count = 3
        invalid_changes = (
            {
                "full_domain_molecule_fraction": 2.0 / 9.0,
                "unassigned_molecule_fraction": 6.0 / 9.0,
            },
            {"edge_truncated_fraction_of_valid_representatives": 1.0 / 9.0},
            {
                "full_domain_footprint_fraction": 2.0 / 9.0,
                "unassigned_supported_footprint_fraction": 6.0 / 9.0,
            },
            {"full_domain_molecule_weighted_coherent_q6": 0.5},
            {"domain_molecule_entropy": 0.5},
        )
        for changes in invalid_changes:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    replace(result, **changes)

    def test_two_equal_domains_have_unit_entropies(self) -> None:
        points = np.asarray(((0.5, 0.5), (1.5, 0.5), (2.5, 0.5), (3.5, 0.5)))
        metrics = _set_component_coherence(
            _metrics(
                points,
                components=(
                    ("full_domain", (0, 1)),
                    ("full_domain", (2, 3)),
                ),
                support_radius_nm=10.0,
            ),
            (0.4, 0.8),
        )
        result = aggregate_m6_orientation_frame(
            local_order=_field_for_metrics(metrics),
            domain_metrics=metrics,
            footprint_partition=_partition(
                points,
                metrics=metrics,
                window_size_nm=(4.0, 1.0),
            ),
        )

        self.assertAlmostEqual(result.domain_molecule_entropy, 1.0)
        self.assertAlmostEqual(result.domain_footprint_entropy, 1.0)
        self.assertAlmostEqual(result.full_domain_molecule_weighted_coherent_q6, 0.6)
        self.assertAlmostEqual(result.full_domain_footprint_weighted_coherent_q6, 0.6)

    def test_footprint_weights_are_independent_from_equal_molecule_counts(self) -> None:
        points = np.asarray(((0.5, 0.5), (3.5, 0.5), (4.5, 0.5), (5.5, 0.5)))
        metrics = _set_component_coherence(
            _metrics(
                points,
                components=(
                    ("full_domain", (0, 1)),
                    ("full_domain", (2, 3)),
                ),
                support_radius_nm=10.0,
            ),
            (0.4, 0.8),
        )
        result = aggregate_m6_orientation_frame(
            local_order=_field_for_metrics(metrics),
            domain_metrics=metrics,
            footprint_partition=_partition(
                points,
                metrics=metrics,
                window_size_nm=(6.0, 1.0),
            ),
        )

        self.assertAlmostEqual(result.full_domain_molecule_weighted_coherent_q6, 0.6)
        self.assertAlmostEqual(
            result.full_domain_footprint_weighted_coherent_q6,
            (4.0 * 0.4 + 2.0 * 0.8) / 6.0,
        )
        self.assertEqual(result.domain_molecule_entropy, 1.0)
        expected_footprint_entropy = -(
            (2.0 / 3.0) * math.log(2.0 / 3.0)
            + (1.0 / 3.0) * math.log(1.0 / 3.0)
        ) / math.log(2.0)
        self.assertAlmostEqual(
            result.domain_footprint_entropy,
            expected_footprint_entropy,
        )

    def test_one_full_domain_has_zero_entropy(self) -> None:
        points = np.asarray(((0.5, 0.5), (1.5, 0.5)))
        metrics = _set_component_coherence(
            _metrics(
                points,
                components=(("full_domain", (0, 1)),),
                support_radius_nm=10.0,
            ),
            (0.7,),
        )
        result = aggregate_m6_orientation_frame(
            local_order=_field_for_metrics(metrics),
            domain_metrics=metrics,
            footprint_partition=_partition(
                points,
                metrics=metrics,
                window_size_nm=(2.0, 1.0),
            ),
        )

        self.assertEqual(result.domain_molecule_entropy, 0.0)
        self.assertEqual(result.domain_footprint_entropy, 0.0)
        self.assertAlmostEqual(result.full_domain_molecule_weighted_coherent_q6, 0.7)
        self.assertAlmostEqual(result.full_domain_footprint_weighted_coherent_q6, 0.7)
        with self.assertRaises(TypeError):
            replace(result, full_domain_count=True)

        inconsistent_local_order = _field_for_metrics(
            metrics,
            valid_psi6={0: 0.2 + 0.0j, 1: 0.2 + 0.0j},
        )
        with self.assertRaisesRegex(ValueError, "Domain q6 metrics"):
            aggregate_m6_orientation_frame(
                local_order=inconsistent_local_order,
                domain_metrics=metrics,
                footprint_partition=result.footprint_partition,
            )

    def test_no_domains_leaves_domain_statistics_unavailable(self) -> None:
        points = np.asarray(((0.5, 0.5), (1.5, 0.5)))
        metrics = _metrics(points, support_radius_nm=10.0)
        metrics = _replace_segmentation_state(
            metrics,
            edge_truncated=(True, False),
        )
        result = aggregate_m6_orientation_frame(
            local_order=_field_for_metrics(metrics, edge_indices=(0,)),
            domain_metrics=metrics,
            footprint_partition=_partition(
                points,
                metrics=metrics,
                window_size_nm=(2.0, 1.0),
            ),
        )

        self.assertEqual(result.full_domain_count, 0)
        self.assertEqual(result.unassigned_molecule_fraction, 1.0)
        self.assertEqual(result.unassigned_supported_footprint_fraction, 1.0)
        self.assertEqual(result.edge_truncated_fraction_of_valid_representatives, 0.5)
        self.assertIsNone(result.mean_local_q6_interior)
        self.assertIsNone(result.global_q6_interior)
        self.assertIsNone(result.full_domain_molecule_weighted_coherent_q6)
        self.assertIsNone(result.full_domain_footprint_weighted_coherent_q6)
        self.assertIsNone(result.mean_full_domain_footprint_area_nm2)
        self.assertIsNone(result.median_full_domain_footprint_area_nm2)
        self.assertIsNone(result.domain_molecule_entropy)
        self.assertIsNone(result.domain_footprint_entropy)

    def test_empty_o_v_and_w_have_explicit_unavailable_fractions(self) -> None:
        points = np.empty((0, 2), dtype=np.float64)
        metrics = _metrics(points)
        local_order = _field_for_metrics(metrics)
        positive_window = _partition(
            points,
            metrics=metrics,
            window_size_nm=(2.0, 2.0),
        )
        empty_result = aggregate_m6_orientation_frame(
            local_order=local_order,
            domain_metrics=metrics,
            footprint_partition=positive_window,
        )

        self.assertEqual(empty_result.original_observation_count, 0)
        self.assertEqual(empty_result.valid_representative_count, 0)
        self.assertIsNone(empty_result.full_domain_molecule_fraction)
        self.assertIsNone(empty_result.small_island_molecule_fraction)
        self.assertIsNone(empty_result.unassigned_molecule_fraction)
        self.assertIsNone(empty_result.assigned_molecule_fraction)
        self.assertIsNone(empty_result.largest_domain_molecule_fraction)
        self.assertIsNone(empty_result.duplicate_excluded_fraction_of_original)
        self.assertIsNone(empty_result.invalid_position_fraction_of_original)
        self.assertIsNone(
            empty_result.edge_truncated_fraction_of_valid_representatives
        )
        self.assertEqual(empty_result.unsupported_background_fraction, 1.0)
        self.assertFalse(empty_result.non_positive_valid_fov_area_qc)

        zero_window = compute_m6_orientation_footprint_partition(
            points,
            domain_metrics=metrics,
            window_geometry="irregular",
            valid_fov_mask=np.zeros((2, 2), dtype=bool),
            valid_fov_pixel_size_nm=(1.0, 1.0),
        )
        zero_result = aggregate_m6_orientation_frame(
            local_order=local_order,
            domain_metrics=metrics,
            footprint_partition=zero_window,
        )
        self.assertTrue(zero_result.non_positive_valid_fov_area_qc)
        self.assertIsNone(zero_result.full_domain_footprint_fraction)
        self.assertIsNone(zero_result.small_island_footprint_fraction)
        self.assertIsNone(zero_result.unassigned_supported_footprint_fraction)
        self.assertIsNone(zero_result.unsupported_background_fraction)

        rejected_points = np.asarray(((0.5, 0.5), (math.nan, math.nan)))
        rejected_metrics = _metrics(
            rejected_points,
            excluded={0: "duplicate_excluded", 1: "invalid_position"},
        )
        rejected_result = aggregate_m6_orientation_frame(
            local_order=_field_for_metrics(rejected_metrics),
            domain_metrics=rejected_metrics,
            footprint_partition=_partition(
                rejected_points,
                metrics=rejected_metrics,
                window_size_nm=(2.0, 2.0),
            ),
        )
        self.assertEqual(rejected_result.original_observation_count, 2)
        self.assertEqual(rejected_result.valid_representative_count, 0)
        self.assertEqual(rejected_result.duplicate_excluded_fraction_of_original, 0.5)
        self.assertEqual(rejected_result.invalid_position_fraction_of_original, 0.5)
        self.assertIsNone(rejected_result.unassigned_molecule_fraction)
        self.assertEqual(rejected_result.unsupported_background_fraction, 1.0)


if __name__ == "__main__":
    unittest.main()
