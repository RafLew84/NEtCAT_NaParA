import cmath
import math
import unittest
from dataclasses import replace

import numpy as np

from moltrack.analysis import (
    LatticeOrientationDomain,
    M6OrientationDomainMetrics,
    M6OrientationDomainSegmentation,
    MolecularM6OrientationAnalysisSettings,
    build_first_shell_graph,
    compute_local_sixfold_bond_order,
    compute_m6_orientation_domain_metrics,
)


def _inputs(
    *,
    min_bonds_for_domain_length_stats: int = 5,
) -> tuple[
    np.ndarray,
    object,
    object,
    M6OrientationDomainSegmentation,
    MolecularM6OrientationAnalysisSettings,
    tuple[complex, ...],
]:
    points = np.asarray(
        (
            (0.0, 0.0),
            (1.0, 0.0),
            (0.0, 1.3),
            (1.2, 1.1),
            (10.0, 10.0),
        ),
        dtype=np.float64,
    )
    source_ids = ("a", "b", "c", "d", "unassigned")
    settings = MolecularM6OrientationAnalysisSettings(
        duplicate_max_distance_nm=0.1,
        first_shell_r_min_nm=0.5,
        first_shell_r_max_nm=2.0,
        min_neighbors_for_local_order=2,
        min_neighbors_for_seed=2,
        min_ordered_component_size=2,
        min_seed_size=2,
        min_domain_size=4,
        q_seed=0.5,
        q_grow=0.1,
        min_bonds_for_domain_length_stats=min_bonds_for_domain_length_stats,
        domain_bond_length_robust_cv_qc_threshold=0.01,
    )
    graph = build_first_shell_graph(
        points,
        point_ids=source_ids,
        settings=settings,
        spatial_calibration_fingerprint="calibration-v1",
        registration_fingerprint="registration-v1",
    )
    local_order = compute_local_sixfold_bond_order(
        graph,
        distance_to_valid_fov_boundary_nm=(100.0,) * len(points),
        settings=settings,
    )
    q_values = (1.0, 0.8, 0.6, 0.9)
    orientation_values = (59.0, 1.0, 4.0, 56.0)
    psi_values = tuple(
        q_value * cmath.exp(6j * math.radians(orientation_deg))
        for q_value, orientation_deg in zip(q_values, orientation_values)
    )
    local_order = replace(
        local_order,
        psi6=psi_values + (None,),
        q6=q_values + (None,),
        lattice_orientation_deg=orientation_values + (None,),
        orientation_status=("defined",) * 4 + ("not_available",),
    )
    mean_psi = sum(psi_values) / len(psi_values)
    orientation_deg = math.degrees(cmath.phase(mean_psi)) / 6.0 % 60.0
    component = LatticeOrientationDomain(
        ordered_component_id=0,
        m6_orientation_domain_id=0,
        component_type="full_domain",
        point_indices=(0, 1, 2, 3),
        source_ids=source_ids[:4],
        molecule_count=4,
        centroid_x_nm=float(np.mean(points[:4, 0])),
        centroid_y_nm=float(np.mean(points[:4, 1])),
        orientation_deg=orientation_deg,
    )
    segmentation = M6OrientationDomainSegmentation(
        source_ids=source_ids,
        point_count=5,
        ordered_component_id=(0, 0, 0, 0, -1),
        m6_orientation_domain_id=(0, 0, 0, 0, -1),
        component_type=(
            "full_domain",
            "full_domain",
            "full_domain",
            "full_domain",
            "unassigned",
        ),
        assignment_status=(
            "assigned",
            "assigned",
            "assigned",
            "assigned",
            "insufficient_neighbors",
        ),
        edge_truncated_neighborhood=(False,) * 5,
        physical_duplicate_qc=(False,) * 5,
        geometry_duplicate_qc=(False,) * 5,
        components=(component,),
        settings=settings,
        coordinate_frame="sample_nm",
        orientation_reference="+x_sample_axis",
        spatial_calibration_fingerprint="calibration-v1",
        registration_fingerprint="registration-v1",
        point_coordinate_fingerprint=graph.point_coordinate_fingerprint,
    )
    return points, graph, local_order, segmentation, settings, psi_values


class OrientationDomainMetricsTests(unittest.TestCase):
    def test_computes_component_quality_geometry_and_unique_bond_statistics(self) -> None:
        points, graph, local_order, segmentation, settings, psi_values = _inputs()

        result = compute_m6_orientation_domain_metrics(
            points,
            first_shell_graph=graph,
            local_order=local_order,
            segmentation=segmentation,
            settings=settings,
        )

        self.assertIsInstance(result, M6OrientationDomainMetrics)
        self.assertEqual(result.valid_representative_count, 5)
        self.assertEqual(len(result.components), 1)
        component = result.components[0]
        self.assertEqual(component.molecule_count, 4)
        self.assertAlmostEqual(component.molecule_fraction_of_valid_representatives, 0.8)
        self.assertAlmostEqual(component.domain_mean_local_q6, 0.825)
        expected_mean_psi = sum(psi_values) / len(psi_values)
        self.assertAlmostEqual(component.domain_coherent_q6, abs(expected_mean_psi))
        self.assertLess(component.domain_coherent_q6, component.domain_mean_local_q6)
        self.assertAlmostEqual(
            component.orientation_deg,
            math.degrees(cmath.phase(expected_mean_psi)) / 6.0 % 60.0,
        )
        self.assertAlmostEqual(component.centroid_x_nm, 0.55)
        self.assertAlmostEqual(component.centroid_y_nm, 0.6)
        self.assertEqual(
            (
                component.min_x_nm,
                component.min_y_nm,
                component.max_x_nm,
                component.max_y_nm,
            ),
            (0.0, 0.0, 1.2, 1.3),
        )

        member_indices = set(segmentation.components[0].point_indices)
        internal_distances = np.asarray(
            [
                distance
                for (left, right), distance in zip(
                    graph.edges_ij,
                    graph.distances_nm,
                )
                if left in member_indices and right in member_indices
            ],
            dtype=np.float64,
        )
        self.assertEqual(component.internal_first_shell_bond_count, 5)
        median = float(np.median(internal_distances))
        mad = float(np.median(np.abs(internal_distances - median)))
        q25, q75 = np.percentile(internal_distances, (25.0, 75.0))
        self.assertAlmostEqual(component.domain_median_bond_length_nm, median)
        self.assertAlmostEqual(component.domain_bond_length_mad_nm, mad)
        self.assertAlmostEqual(component.domain_bond_length_iqr_nm, float(q75 - q25))
        self.assertAlmostEqual(component.domain_bond_length_robust_cv, 1.4826 * mad / median)
        self.assertFalse(component.insufficient_bonds_for_length_stats_qc)
        self.assertTrue(component.bond_length_heterogeneity_qc)

    def test_marks_length_statistics_unavailable_below_configured_bond_count(self) -> None:
        points, graph, local_order, segmentation, settings, _ = _inputs(
            min_bonds_for_domain_length_stats=6,
        )

        component = compute_m6_orientation_domain_metrics(
            points,
            first_shell_graph=graph,
            local_order=local_order,
            segmentation=segmentation,
            settings=settings,
        ).components[0]

        self.assertEqual(component.internal_first_shell_bond_count, 5)
        self.assertIsNone(component.domain_median_bond_length_nm)
        self.assertIsNone(component.domain_bond_length_mad_nm)
        self.assertIsNone(component.domain_bond_length_iqr_nm)
        self.assertIsNone(component.domain_bond_length_robust_cv)
        self.assertTrue(component.insufficient_bonds_for_length_stats_qc)
        self.assertFalse(component.bond_length_heterogeneity_qc)

    def test_models_reject_inconsistent_statistics_fractions_and_context(self) -> None:
        points, graph, local_order, segmentation, settings, _ = _inputs()
        result = compute_m6_orientation_domain_metrics(
            points,
            first_shell_graph=graph,
            local_order=local_order,
            segmentation=segmentation,
            settings=settings,
        )
        component = result.components[0]

        with self.assertRaisesRegex(ValueError, "1.4826"):
            replace(
                component,
                domain_bond_length_robust_cv=(
                    component.domain_bond_length_robust_cv + 0.1
                ),
            )
        with self.assertRaisesRegex(ValueError, "valid representatives"):
            replace(
                result,
                components=(
                    replace(
                        component,
                        molecule_fraction_of_valid_representatives=0.9,
                    ),
                ),
            )
        self.assertEqual(result.component_for_ordered_id(0), component)
        with self.assertRaises(KeyError):
            result.component_for_ordered_id(1)
        self.assertFalse(hasattr(component, "domain_bond_length_bimodality"))

        changed_settings = replace(settings, min_bonds_for_domain_length_stats=6)
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            compute_m6_orientation_domain_metrics(
                points,
                first_shell_graph=graph,
                local_order=local_order,
                segmentation=replace(segmentation, settings=changed_settings),
                settings=changed_settings,
            )

    def test_rejects_segmentation_geometry_inconsistent_with_source_values(self) -> None:
        points, graph, local_order, segmentation, settings, _ = _inputs()
        component = segmentation.components[0]

        for field_name, value in (
            ("centroid_x_nm", component.centroid_x_nm + 0.1),
            ("orientation_deg", component.orientation_deg + 0.1),
        ):
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(ValueError, field_name):
                    compute_m6_orientation_domain_metrics(
                        points,
                        first_shell_graph=graph,
                        local_order=local_order,
                        segmentation=replace(
                            segmentation,
                            components=(replace(component, **{field_name: value}),),
                        ),
                        settings=settings,
                    )


if __name__ == "__main__":
    unittest.main()
