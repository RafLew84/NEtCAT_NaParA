import math
import unittest
from unittest.mock import patch

import numpy as np

from moltrack.analysis import (
    LatticeOrientationDomain,
    M6OrientationComponentMetrics,
    M6OrientationDomainMetrics,
    M6OrientationDomainSegmentation,
    MolecularM6OrientationAnalysisSettings,
    compute_m6_orientation_footprint_partition,
)


def _metrics(
    points: np.ndarray,
    *,
    components: tuple[tuple[str, tuple[int, ...]], ...] = (),
    excluded: dict[int, str] | None = None,
    support_radius_nm: float = 1.0,
) -> M6OrientationDomainMetrics:
    excluded = excluded or {}
    point_count = len(points)
    source_ids = tuple(f"p-{index}" for index in range(point_count))
    settings = MolecularM6OrientationAnalysisSettings(
        min_ordered_component_size=1,
        min_seed_size=1,
        min_domain_size=2,
        footprint_support_radius_nm=support_radius_nm,
    )
    ordered_ids = [-1] * point_count
    domain_ids = [-1] * point_count
    component_types = ["unassigned"] * point_count
    statuses = ["insufficient_neighbors"] * point_count
    lattice_components = []
    full_domain_id = 0
    for ordered_id, (component_type, indices) in enumerate(components):
        domain_id = full_domain_id if component_type == "full_domain" else None
        if domain_id is not None:
            full_domain_id += 1
        coordinates = points[np.asarray(indices, dtype=np.int64)]
        component = LatticeOrientationDomain(
            ordered_component_id=ordered_id,
            m6_orientation_domain_id=domain_id,
            component_type=component_type,
            point_indices=indices,
            source_ids=tuple(source_ids[index] for index in indices),
            molecule_count=len(indices),
            centroid_x_nm=float(np.mean(coordinates[:, 0])),
            centroid_y_nm=float(np.mean(coordinates[:, 1])),
            orientation_deg=0.0,
        )
        lattice_components.append(component)
        for index in indices:
            ordered_ids[index] = ordered_id
            domain_ids[index] = domain_id if domain_id is not None else -1
            component_types[index] = component_type
            statuses[index] = "assigned"
    physical_qc = [False] * point_count
    geometry_qc = [False] * point_count
    for index, status in excluded.items():
        statuses[index] = status
        if status == "duplicate_excluded":
            physical_qc[index] = True
    segmentation = M6OrientationDomainSegmentation(
        source_ids=source_ids,
        point_count=point_count,
        ordered_component_id=tuple(ordered_ids),
        m6_orientation_domain_id=tuple(domain_ids),
        component_type=tuple(component_types),
        assignment_status=tuple(statuses),
        edge_truncated_neighborhood=(False,) * point_count,
        physical_duplicate_qc=tuple(physical_qc),
        geometry_duplicate_qc=tuple(geometry_qc),
        components=tuple(lattice_components),
        settings=settings,
        coordinate_frame="sample_nm",
        orientation_reference="+x_sample_axis",
        spatial_calibration_fingerprint="calibration-v1",
        registration_fingerprint="registration-v1",
        point_coordinate_fingerprint="coordinates-v1",
    )
    valid_count = sum(
        status not in {"duplicate_excluded", "invalid_position"}
        for status in statuses
    )
    measured_components = tuple(
        M6OrientationComponentMetrics(
            component=component,
            molecule_fraction_of_valid_representatives=(
                component.molecule_count / valid_count
            ),
            domain_mean_local_q6=1.0,
            domain_coherent_q6=1.0,
            min_x_nm=float(np.min(points[list(component.point_indices), 0])),
            min_y_nm=float(np.min(points[list(component.point_indices), 1])),
            max_x_nm=float(np.max(points[list(component.point_indices), 0])),
            max_y_nm=float(np.max(points[list(component.point_indices), 1])),
            internal_first_shell_bond_count=0,
            domain_median_bond_length_nm=None,
            domain_bond_length_mad_nm=None,
            domain_bond_length_iqr_nm=None,
            domain_bond_length_robust_cv=None,
            insufficient_bonds_for_length_stats_qc=True,
            bond_length_heterogeneity_qc=False,
        )
        for component in lattice_components
    )
    return M6OrientationDomainMetrics(
        segmentation=segmentation,
        valid_representative_count=valid_count,
        components=measured_components,
    )


def _partition(
    points: np.ndarray,
    *,
    metrics: M6OrientationDomainMetrics,
    window_size_nm: tuple[float, float],
    molecular_mask_area_nm2: tuple[float | None, ...] | None = None,
):
    return compute_m6_orientation_footprint_partition(
        points,
        domain_metrics=metrics,
        window_geometry="rectangular",
        window_size_nm=window_size_nm,
        molecular_mask_area_nm2=molecular_mask_area_nm2,
    )


class OrientationDomainFootprintTests(unittest.TestCase):
    def assertFractionsSumToOne(self, result) -> None:
        self.assertAlmostEqual(
            result.full_domain_footprint_fraction
            + result.small_island_footprint_fraction
            + result.unassigned_supported_footprint_fraction
            + result.unsupported_background_fraction,
            1.0,
            places=10,
        )

    def test_empty_partition_assigns_the_whole_valid_fov_to_background(self) -> None:
        points = np.empty((0, 2), dtype=np.float64)
        result = _partition(
            points,
            metrics=_metrics(points),
            window_size_nm=(4.0, 3.0),
        )

        self.assertEqual(result.footprint_construction_method, "empty_partition")
        self.assertEqual(result.valid_representative_point_indices, ())
        self.assertEqual(result.cells, ())
        self.assertAlmostEqual(result.valid_fov_area_nm2, 12.0)
        self.assertAlmostEqual(result.supported_area_nm2, 0.0)
        self.assertEqual(result.full_domain_footprint_fraction, 0.0)
        self.assertEqual(result.small_island_footprint_fraction, 0.0)
        self.assertEqual(result.unassigned_supported_footprint_fraction, 0.0)
        self.assertEqual(result.unsupported_background_fraction, 1.0)
        self.assertAlmostEqual(result.footprint_overlap_error_nm2, 0.0)
        self.assertTrue(result.fewer_than_3_noncollinear_points_qc)
        self.assertFractionsSumToOne(result)

    def test_excluded_duplicate_and_invalid_position_do_not_enter_v_or_support(self) -> None:
        points = np.asarray(((1.0, 1.0), (math.nan, math.nan)))
        metrics = _metrics(
            points,
            excluded={0: "duplicate_excluded", 1: "invalid_position"},
        )

        result = _partition(points, metrics=metrics, window_size_nm=(2.0, 2.0))

        self.assertEqual(result.valid_representative_point_indices, ())
        self.assertEqual(result.cells, ())
        self.assertEqual(result.supported_area_nm2, 0.0)
        self.assertEqual(result.unsupported_background_fraction, 1.0)

    def test_zero_area_valid_fov_has_undefined_area_fractions(self) -> None:
        points = np.empty((0, 2), dtype=np.float64)
        result = compute_m6_orientation_footprint_partition(
            points,
            domain_metrics=_metrics(points),
            window_geometry="irregular",
            valid_fov_mask=np.zeros((2, 2), dtype=bool),
            valid_fov_pixel_size_nm=(1.0, 1.0),
        )

        self.assertEqual(result.valid_fov_area_nm2, 0.0)
        self.assertIsNone(result.full_domain_footprint_fraction)
        self.assertIsNone(result.small_island_footprint_fraction)
        self.assertIsNone(result.unassigned_supported_footprint_fraction)
        self.assertIsNone(result.unsupported_background_fraction)

    def test_rejects_valid_representative_outside_valid_fov(self) -> None:
        points = np.asarray(((3.0, 1.0),))

        with self.assertRaisesRegex(ValueError, "inside valid FOV"):
            _partition(
                points,
                metrics=_metrics(points),
                window_size_nm=(2.0, 2.0),
            )

    def test_single_point_uses_the_whole_bounded_cell_and_support_disk(self) -> None:
        points = np.asarray(((2.0, 2.0),))
        result = _partition(
            points,
            metrics=_metrics(points, support_radius_nm=1.0),
            window_size_nm=(4.0, 4.0),
        )

        self.assertEqual(result.footprint_construction_method, "single_point_cell")
        self.assertAlmostEqual(result.cells[0].bounded_cell_area_nm2, 16.0)
        self.assertAlmostEqual(result.cells[0].supported_area_nm2, math.pi, places=8)
        fragment = result.cells[0].supported_footprint_fragments[0]
        self.assertEqual(fragment.support_disk_center_xy_nm, (2.0, 2.0))
        self.assertEqual(fragment.support_disk_radius_nm, 1.0)
        self.assertAlmostEqual(fragment.area_nm2, math.pi, places=8)
        self.assertAlmostEqual(result.supported_area_nm2, math.pi, places=8)
        self.assertAlmostEqual(
            result.unassigned_supported_footprint_fraction,
            math.pi / 16.0,
            places=8,
        )
        self.assertFalse(result.cells[0].edge_truncated)
        self.assertAlmostEqual(result.footprint_overlap_error_nm2, 0.0, places=10)
        self.assertEqual(result.footprint_support_radius_nm, 1.0)
        self.assertFractionsSumToOne(result)

    def test_two_points_are_split_by_the_perpendicular_bisector(self) -> None:
        points = np.asarray(((1.0, 2.0), (3.0, 2.0)))
        result = _partition(
            points,
            metrics=_metrics(points, support_radius_nm=10.0),
            window_size_nm=(4.0, 4.0),
        )

        self.assertEqual(result.footprint_construction_method, "two_point_bisector")
        self.assertEqual(len(result.cells), 2)
        for cell in result.cells:
            self.assertAlmostEqual(cell.bounded_cell_area_nm2, 8.0)
            self.assertAlmostEqual(cell.supported_area_nm2, 8.0)
            self.assertTrue(cell.edge_truncated)
        self.assertEqual(
            tuple(
                (
                    min(point[0] for point in cell.valid_fov_cell_polygons_xy_nm[0]),
                    max(point[0] for point in cell.valid_fov_cell_polygons_xy_nm[0]),
                )
                for cell in result.cells
            ),
            ((0.0, 2.0), (2.0, 4.0)),
        )
        self.assertAlmostEqual(result.footprint_overlap_error_nm2, 0.0, places=10)
        self.assertFractionsSumToOne(result)

    def test_rank1_uses_adjacent_projection_strips_for_uneven_spacing(self) -> None:
        points = np.asarray(((1.0, 1.0), (2.0, 1.0), (4.0, 1.0)))
        result = _partition(
            points,
            metrics=_metrics(points, support_radius_nm=10.0),
            window_size_nm=(6.0, 2.0),
        )

        self.assertEqual(result.footprint_construction_method, "rank1_projection_strips")
        self.assertEqual(
            tuple(round(cell.bounded_cell_area_nm2, 10) for cell in result.cells),
            (3.0, 3.0, 6.0),
        )
        self.assertEqual(
            tuple(
                (
                    round(
                        min(point[0] for point in cell.valid_fov_cell_polygons_xy_nm[0]),
                        10,
                    ),
                    round(
                        max(point[0] for point in cell.valid_fov_cell_polygons_xy_nm[0]),
                        10,
                    ),
                )
                for cell in result.cells
            ),
            ((0.0, 1.5), (1.5, 3.0), (3.0, 6.0)),
        )
        self.assertAlmostEqual(result.supported_area_nm2, 12.0)
        self.assertAlmostEqual(result.footprint_overlap_error_nm2, 0.0, places=10)
        self.assertFractionsSumToOne(result)

        permutation = np.asarray((2, 0, 1))
        permuted_points = points[permutation]
        permuted_result = _partition(
            permuted_points,
            metrics=_metrics(permuted_points, support_radius_nm=10.0),
            window_size_nm=(6.0, 2.0),
        )
        areas_by_coordinate = {
            tuple(permuted_points[cell.point_index]): cell.bounded_cell_area_nm2
            for cell in permuted_result.cells
        }
        self.assertEqual(
            {coordinate: round(area, 10) for coordinate, area in areas_by_coordinate.items()},
            {(1.0, 1.0): 3.0, (2.0, 1.0): 3.0, (4.0, 1.0): 6.0},
        )

    def test_overlapping_support_disks_form_the_global_support_union(self) -> None:
        points = np.asarray(((2.0, 2.0), (3.0, 2.0)))
        result = _partition(
            points,
            metrics=_metrics(points, support_radius_nm=1.0),
            window_size_nm=(5.0, 4.0),
        )

        distance = 1.0
        lens_area = (
            2.0 * math.acos(distance / 2.0)
            - 0.5 * distance * math.sqrt(4.0 - distance * distance)
        )
        self.assertAlmostEqual(result.supported_area_nm2, 2.0 * math.pi - lens_area)
        self.assertAlmostEqual(result.footprint_overlap_error_nm2, 0.0, places=10)

    def test_rank2_svd_failure_uses_halfplanes_and_reports_degenerate_qc(self) -> None:
        points = np.asarray(((1.0, 1.0), (3.0, 1.0), (2.0, 3.0)))

        with patch(
            "moltrack.analysis.orientation_domain_footprint."
            "deterministic_affine_rank_and_axis",
            side_effect=np.linalg.LinAlgError,
        ):
            result = _partition(
                points,
                metrics=_metrics(points, support_radius_nm=10.0),
                window_size_nm=(4.0, 4.0),
            )

        self.assertEqual(result.footprint_construction_method, "rank2_bounded_voronoi")
        self.assertTrue(result.voronoi_degenerate_qc)
        self.assertAlmostEqual(
            sum(cell.bounded_cell_area_nm2 for cell in result.cells),
            16.0,
        )
        self.assertAlmostEqual(result.footprint_overlap_error_nm2, 0.0, places=10)

    def test_rank2_respects_an_irregular_valid_fov(self) -> None:
        points = np.asarray(((0.5, 0.5), (1.5, 0.5), (0.5, 1.5)))
        mask = np.asarray(((1, 1, 1), (1, 1, 0), (1, 1, 0)), dtype=bool)
        result = compute_m6_orientation_footprint_partition(
            points,
            domain_metrics=_metrics(points, support_radius_nm=10.0),
            window_geometry="irregular",
            valid_fov_mask=mask,
            valid_fov_pixel_size_nm=(1.0, 1.0),
        )

        self.assertEqual(result.footprint_construction_method, "rank2_bounded_voronoi")
        self.assertAlmostEqual(result.valid_fov_area_nm2, 7.0)
        self.assertAlmostEqual(sum(cell.bounded_cell_area_nm2 for cell in result.cells), 7.0)
        self.assertAlmostEqual(result.supported_area_nm2, 7.0)
        self.assertAlmostEqual(result.footprint_overlap_error_nm2, 0.0, places=10)
        self.assertFractionsSumToOne(result)

    def test_global_cells_partition_domains_islands_and_unassigned_points(self) -> None:
        points = np.asarray(
            ((0.5, 1.0), (1.5, 1.0), (2.5, 1.0), (3.5, 1.0), (4.5, 1.0),
             (5.5, 1.0), (0.5, 1.0))
        )
        metrics = _metrics(
            points,
            components=(
                ("full_domain", (0, 1)),
                ("full_domain", (2, 3)),
                ("small_ordered_island", (4,)),
            ),
            excluded={6: "duplicate_excluded"},
            support_radius_nm=10.0,
        )
        result = _partition(
            points,
            metrics=metrics,
            window_size_nm=(6.0, 2.0),
            molecular_mask_area_nm2=(0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 9.9),
        )

        self.assertEqual(result.valid_representative_point_indices, (0, 1, 2, 3, 4, 5))
        self.assertEqual(len(result.cells), 6)
        self.assertAlmostEqual(result.full_domain_footprint_area_nm2, 8.0)
        self.assertAlmostEqual(result.small_island_footprint_area_nm2, 2.0)
        self.assertAlmostEqual(result.unassigned_supported_footprint_area_nm2, 2.0)
        self.assertAlmostEqual(result.unsupported_background_area_nm2, 0.0)
        self.assertEqual(len(result.components), 3)
        self.assertAlmostEqual(result.components[0].footprint_area_nm2, 4.0)
        self.assertAlmostEqual(result.components[1].footprint_area_nm2, 4.0)
        self.assertAlmostEqual(result.components[2].footprint_area_nm2, 2.0)
        self.assertAlmostEqual(result.components[0].molecular_mask_area_nm2, 0.5)
        self.assertAlmostEqual(result.components[1].molecular_mask_area_nm2, 0.9)
        self.assertAlmostEqual(result.components[2].molecular_mask_area_nm2, 0.6)
        self.assertAlmostEqual(result.unassigned_molecular_mask_area_nm2, 0.7)
        self.assertAlmostEqual(result.total_molecular_mask_area_nm2, 2.7)
        self.assertAlmostEqual(result.footprint_overlap_error_nm2, 0.0, places=10)
        self.assertFractionsSumToOne(result)

    def test_reports_edge_clipping_and_disconnected_component_support(self) -> None:
        points = np.asarray(((0.2, 1.0), (4.8, 1.0)))
        metrics = _metrics(
            points,
            components=(("full_domain", (0, 1)),),
            support_radius_nm=0.5,
        )
        result = _partition(points, metrics=metrics, window_size_nm=(5.0, 2.0))

        self.assertTrue(result.components[0].edge_truncated)
        self.assertTrue(result.components[0].footprint_disconnected_qc)
        self.assertTrue(result.footprint_clipped_by_fov_qc)
        self.assertTrue(result.footprint_disconnected_qc)
        self.assertFalse(result.voronoi_degenerate_qc)
        self.assertFalse(result.footprint_overlap_error_qc)
        self.assertFractionsSumToOne(result)

    def test_irregular_fov_gap_disconnects_a_component_despite_overlapping_disks(self) -> None:
        points = np.asarray(((0.5, 0.5), (2.5, 0.5)))
        metrics = _metrics(
            points,
            components=(("full_domain", (0, 1)),),
            support_radius_nm=1.2,
        )

        result = compute_m6_orientation_footprint_partition(
            points,
            domain_metrics=metrics,
            window_geometry="irregular",
            valid_fov_mask=np.asarray(((1, 0, 1),), dtype=bool),
            valid_fov_pixel_size_nm=(1.0, 1.0),
        )

        self.assertLess(np.linalg.norm(points[0] - points[1]), 2.0 * 1.2)
        self.assertTrue(result.components[0].footprint_disconnected_qc)
        self.assertTrue(result.footprint_disconnected_qc)

    def test_touching_supported_cells_form_one_interior_component(self) -> None:
        points = np.asarray(((2.0, 2.0), (3.0, 2.0)))
        metrics = _metrics(
            points,
            components=(("full_domain", (0, 1)),),
            support_radius_nm=0.5,
        )

        result = _partition(points, metrics=metrics, window_size_nm=(5.0, 4.0))

        self.assertFalse(result.components[0].edge_truncated)
        self.assertFalse(result.components[0].footprint_disconnected_qc)
        self.assertAlmostEqual(result.footprint_overlap_error_nm2, 0.0, places=10)

    def test_all_unavailable_mask_areas_remain_unavailable(self) -> None:
        points = np.asarray(((1.0, 1.0),))
        result = _partition(
            points,
            metrics=_metrics(points),
            window_size_nm=(2.0, 2.0),
            molecular_mask_area_nm2=(None,),
        )

        self.assertIsNone(result.total_molecular_mask_area_nm2)
        self.assertIsNone(result.unassigned_molecular_mask_area_nm2)


if __name__ == "__main__":
    unittest.main()
