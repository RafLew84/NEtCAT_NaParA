import unittest
from dataclasses import replace
from math import atan2, cos, degrees, hypot, radians, sin, sqrt

import numpy as np

from moltrack.analysis import (
    LatticeDomain,
    LatticeDomainAnalysis,
    LatticeDomainAnalysisSettings,
    LatticeDomainGeometry,
    LatticeDomainInternalBond,
    LatticeDomainQc,
    LatticeRowAssignmentSettings,
    build_lattice_row_assignment_analysis,
    lattice_domain_analysis_fingerprint,
    lattice_domain_analysis_settings_fingerprint,
    lattice_domain_id_from_members,
    lattice_row_assignment_analysis_fingerprint,
    lattice_row_assignment_settings_fingerprint,
)
from moltrack.analysis._coordinate_fingerprint import (
    point_coordinate_fingerprint,
)


def _triangular_analysis(
    *,
    row_count: int = 4,
    column_count: int = 5,
    spacing_nm: float = 10.0,
    rotation_deg: float = 0.0,
    translation_xy_nm: tuple[float, float] = (0.0, 0.0),
    missing_source_ids: tuple[str, ...] = (),
    registration_fingerprint: str = "registered-v1",
    source_prefix: str = "m",
    reverse_source_labels: bool = False,
) -> LatticeDomainAnalysis:
    angle = radians(rotation_deg)
    rotation = np.asarray(
        ((cos(angle), -sin(angle)), (sin(angle), cos(angle))),
        dtype=np.float64,
    )
    translation = np.asarray(translation_xy_nm, dtype=np.float64)
    records = []
    for row_index in range(row_count):
        for column_index in range(column_count):
            if reverse_source_labels:
                label_index = (
                    row_count * column_count
                    - 1
                    - (row_index * column_count + column_index)
                )
                source_id = f"{source_prefix}-{label_index:04d}"
            else:
                source_id = (
                    f"{source_prefix}-{row_index:02d}-{column_index:02d}"
                )
            if source_id in missing_source_ids:
                continue
            base = np.asarray(
                (
                    spacing_nm * (column_index + 0.5 * row_index),
                    spacing_nm * sqrt(3.0) * 0.5 * row_index,
                ),
                dtype=np.float64,
            )
            point = rotation @ base + translation
            records.append((source_id, float(point[0]), float(point[1])))
    records.sort(key=lambda value: value[0])
    source_ids = tuple(record[0] for record in records)
    points = tuple((record[1], record[2]) for record in records)
    point_by_id = dict(zip(source_ids, points))
    index_by_id = {
        source_id: point_index
        for point_index, source_id in enumerate(source_ids)
    }

    bonds = []
    for left_index, left_id in enumerate(source_ids):
        for right_id in source_ids[left_index + 1 :]:
            left = point_by_id[left_id]
            right = point_by_id[right_id]
            delta_x = right[0] - left[0]
            delta_y = right[1] - left[1]
            distance = hypot(delta_x, delta_y)
            if not np.isclose(distance, spacing_nm, atol=1e-8):
                continue
            bonds.append(
                LatticeDomainInternalBond(
                    source_ids=(left_id, right_id),
                    distance_nm=distance,
                    axial_angle_deg=degrees(atan2(delta_y, delta_x)) % 180.0,
                )
            )
    bonds = tuple(sorted(bonds, key=lambda value: value.source_ids))
    distances = np.asarray(
        tuple(bond.distance_nm for bond in bonds),
        dtype=np.float64,
    )
    median = float(np.median(distances))
    mad = float(np.median(np.abs(distances - median)))
    q25, q75 = np.percentile(distances, (25.0, 75.0))
    settings = LatticeDomainAnalysisSettings(
        min_domain_size=1,
        min_bonds_for_length_stats=1,
    )
    domain_id = lattice_domain_id_from_members(
        tuple(records),
        coordinate_frame="sample_nm",
    )
    point_indices = tuple(index_by_id[source_id] for source_id in source_ids)
    centroid = np.mean(np.asarray(points, dtype=np.float64), axis=0)
    domain = LatticeDomain(
        lattice_domain_id=domain_id,
        source_component_id=0,
        component_type="full_domain",
        point_indices=point_indices,
        source_ids=source_ids,
        core_point_indices=point_indices,
        core_source_ids=source_ids,
        halo_point_indices=(),
        halo_source_ids=(),
        molecule_count=len(source_ids),
        core_size=len(source_ids),
        halo_size=0,
        molecule_fraction_of_valid_representatives=1.0,
        adjacent_boundary_point_count=0,
        adjacent_boundary_source_ids=(),
        adjacent_boundary_point_fraction=0.0,
        theta3_lattice_prototype_deg=None,
        theta6_prototype_deg=rotation_deg % 60.0,
        theta3_lattice_spread_deg=None,
        theta6_spread_deg=0.0,
        dominant_symmetry="sixfold",
        orientation_reference_channel="m6",
        m3_m6_orientation_relation_status="not_applicable",
        m3_m6_orientation_offset_deg=None,
        confidence=1.0,
        geometry=LatticeDomainGeometry(
            centroid_x_nm=float(centroid[0]),
            centroid_y_nm=float(centroid[1]),
            min_x_nm=min(point[0] for point in points),
            min_y_nm=min(point[1] for point in points),
            max_x_nm=max(point[0] for point in points),
            max_y_nm=max(point[1] for point in points),
            internal_first_shell_bond_count=len(bonds),
            internal_first_shell_bonds=bonds,
            median_bond_length_nm=median,
            bond_length_mad_nm=mad,
            bond_length_iqr_nm=float(q75 - q25),
            bond_length_robust_cv=1.4826 * mad / median,
            footprint_area_nm2=None,
            footprint_fraction_of_valid_fov=None,
        ),
        qc=LatticeDomainQc(
            edge_truncated_neighborhood=False,
            graph_disconnected=False,
            insufficient_bonds_for_length_stats=False,
            bond_length_heterogeneity=False,
            footprint_unavailable=True,
            footprint_clipped_by_fov=False,
            symmetry_alias_unresolvable_from_centroids=False,
        ),
    )
    point_fingerprint = point_coordinate_fingerprint(
        np.asarray(points, dtype=np.float64),
        source_ids,
    )
    return LatticeDomainAnalysis(
        source_ids=source_ids,
        point_count=len(source_ids),
        points_xy_nm=points,
        valid_representative=(True,) * len(source_ids),
        point_role=("core",) * len(source_ids),
        boundary_reason=(None,) * len(source_ids),
        point_lattice_domain_id=(domain_id,) * len(source_ids),
        first_shell_bonds=bonds,
        domains=(domain,),
        small_ordered_islands=(),
        valid_representative_count=len(source_ids),
        classified_molecule_count=len(source_ids),
        classified_molecule_fraction=1.0,
        boundary_point_count=0,
        boundary_point_fraction=0.0,
        settings=settings,
        coordinate_frame="sample_nm",
        orientation_reference="+x_sample_axis",
        spatial_calibration_fingerprint="calibration-v1",
        registration_fingerprint=registration_fingerprint,
        point_coordinate_fingerprint=point_fingerprint,
        first_shell_graph_fingerprint="first-shell-v1",
        local_order_analysis_fingerprint="local-order-v1",
        local_symmetry_evidence_settings_fingerprint="evidence-settings-v1",
        local_symmetry_bond_evidence_fingerprint="bond-evidence-v1",
        seed_growth_settings_fingerprint="seed-settings-v1",
        seed_growth_result_fingerprint="seed-result-v1",
        settings_fingerprint=lattice_domain_analysis_settings_fingerprint(
            settings
        ),
    )


def _combine_domain_analyses(
    *analyses: LatticeDomainAnalysis,
) -> LatticeDomainAnalysis:
    source_ids = tuple(
        sorted(
            source_id
            for analysis in analyses
            for source_id in analysis.source_ids
        )
    )
    point_by_source_id = {
        source_id: point
        for analysis in analyses
        for source_id, point in zip(
            analysis.source_ids,
            analysis.points_xy_nm,
        )
    }
    points = tuple(point_by_source_id[source_id] for source_id in source_ids)
    point_index_by_source_id = {
        source_id: point_index
        for point_index, source_id in enumerate(source_ids)
    }
    valid_count = len(source_ids)
    components = tuple(
        replace(
            component,
            point_indices=tuple(
                point_index_by_source_id[source_id]
                for source_id in component.source_ids
            ),
            core_point_indices=tuple(
                point_index_by_source_id[source_id]
                for source_id in component.core_source_ids
            ),
            halo_point_indices=tuple(
                point_index_by_source_id[source_id]
                for source_id in component.halo_source_ids
            ),
            molecule_fraction_of_valid_representatives=(
                component.molecule_count / valid_count
            ),
        )
        for analysis in analyses
        for component in analysis.components
    )
    component_by_source_id = {
        source_id: component.lattice_domain_id
        for component in components
        for source_id in component.source_ids
    }
    first = analyses[0]
    bonds = tuple(
        sorted(
            (
                bond
                for analysis in analyses
                for bond in analysis.first_shell_bonds
            ),
            key=lambda value: value.source_ids,
        )
    )
    return LatticeDomainAnalysis(
        source_ids=source_ids,
        point_count=valid_count,
        points_xy_nm=points,
        valid_representative=(True,) * valid_count,
        point_role=("core",) * valid_count,
        boundary_reason=(None,) * valid_count,
        point_lattice_domain_id=tuple(
            component_by_source_id[source_id]
            for source_id in source_ids
        ),
        first_shell_bonds=bonds,
        domains=tuple(
            sorted(components, key=lambda value: value.lattice_domain_id)
        ),
        small_ordered_islands=(),
        valid_representative_count=valid_count,
        classified_molecule_count=valid_count,
        classified_molecule_fraction=1.0,
        boundary_point_count=0,
        boundary_point_fraction=0.0,
        settings=first.settings,
        coordinate_frame=first.coordinate_frame,
        orientation_reference=first.orientation_reference,
        spatial_calibration_fingerprint=(
            first.spatial_calibration_fingerprint
        ),
        registration_fingerprint=first.registration_fingerprint,
        point_coordinate_fingerprint=point_coordinate_fingerprint(
            np.asarray(points, dtype=np.float64),
            source_ids,
        ),
        first_shell_graph_fingerprint="combined-first-shell-v1",
        local_order_analysis_fingerprint="combined-local-order-v1",
        local_symmetry_evidence_settings_fingerprint=(
            "combined-evidence-settings-v1"
        ),
        local_symmetry_bond_evidence_fingerprint=(
            "combined-bond-evidence-v1"
        ),
        seed_growth_settings_fingerprint="combined-seed-settings-v1",
        seed_growth_result_fingerprint="combined-seed-result-v1",
        settings_fingerprint=lattice_domain_analysis_settings_fingerprint(
            first.settings
        ),
    )


def _partition_signature(candidate) -> frozenset[frozenset[str]]:
    return frozenset(
        frozenset(row.source_ids)
        for row in candidate.rows
    )


def _candidate_by_angle(result, expected_angle_deg: float):
    assignment = result.domain_assignments[0]
    return min(
        assignment.candidates,
        key=lambda candidate: min(
            abs(candidate.axis_angle_deg - expected_angle_deg),
            180.0 - abs(candidate.axis_angle_deg - expected_angle_deg),
        ),
    )


class LatticeRowAssignmentTests(unittest.TestCase):
    def test_perfect_triangular_domain_keeps_all_symmetric_axes_ambiguous(
        self,
    ) -> None:
        source = _triangular_analysis()

        result = build_lattice_row_assignment_analysis(source)

        self.assertEqual(result.coordinate_frame, "sample_nm")
        self.assertEqual(result.registration_fingerprint, "registered-v1")
        self.assertEqual(
            result.lattice_domain_analysis_fingerprint,
            lattice_domain_analysis_fingerprint(source),
        )
        self.assertEqual(len(result.domain_assignments), 1)
        assignment = result.domain_assignments[0]
        self.assertEqual(assignment.status, "ambiguous")
        self.assertIsNone(assignment.selected_candidate_index)
        self.assertEqual(len(assignment.candidates), 3)
        self.assertAlmostEqual(assignment.selection_margin, 0.0, places=8)
        for candidate in assignment.candidates:
            self.assertAlmostEqual(
                candidate.row_spacing_nm,
                10.0 * sqrt(3.0) * 0.5,
                places=7,
            )
            self.assertEqual(candidate.assigned_molecule_count, 20)
            self.assertEqual(
                {
                    source_id
                    for row in candidate.rows
                    for source_id in row.source_ids
                },
                set(source.source_ids),
            )
            for row in candidate.rows:
                self.assertEqual(row.parity, row.row_index % 2)
                self.assertEqual(
                    row.point_indices,
                    tuple(
                        source.source_ids.index(source_id)
                        for source_id in row.source_ids
                    ),
                )

    def test_row_partitions_survive_rotation_and_translation(self) -> None:
        baseline = build_lattice_row_assignment_analysis(
            _triangular_analysis()
        )
        transformed = build_lattice_row_assignment_analysis(
            _triangular_analysis(
                rotation_deg=17.0,
                translation_xy_nm=(123.4, -51.2),
            )
        )

        baseline_signatures = {
            _partition_signature(candidate)
            for candidate in baseline.domain_assignments[0].candidates
        }
        transformed_signatures = {
            _partition_signature(candidate)
            for candidate in transformed.domain_assignments[0].candidates
        }

        self.assertEqual(transformed_signatures, baseline_signatures)

    def test_row_indices_survive_rotation_up_to_axial_sign(self) -> None:
        baseline = build_lattice_row_assignment_analysis(
            _triangular_analysis()
        )

        for rotation_deg in (-1.0, 17.0, 31.0, 70.0):
            rotated = build_lattice_row_assignment_analysis(
                _triangular_analysis(rotation_deg=rotation_deg)
            )
            for baseline_candidate in (
                baseline.domain_assignments[0].candidates
            ):
                rotated_candidate = _candidate_by_angle(
                    rotated,
                    (
                        baseline_candidate.axis_angle_deg
                        + rotation_deg
                    )
                    % 180.0,
                )
                baseline_rows = {
                    member.source_id: (
                        member.row_index,
                        member.row_parity,
                    )
                    for member in baseline_candidate.member_assignments
                }
                rotated_rows = {
                    member.source_id: (
                        member.row_index,
                        member.row_parity,
                    )
                    for member in rotated_candidate.member_assignments
                }
                self.assertEqual(
                    {
                        source_id: (abs(row_index), parity)
                        for source_id, (row_index, parity)
                        in baseline_rows.items()
                    },
                    {
                        source_id: (abs(row_index), parity)
                        for source_id, (row_index, parity)
                        in rotated_rows.items()
                    },
                )
                signs = {
                    1 if rotated_rows[source_id][0] == row_index else -1
                    for source_id, (row_index, _parity)
                    in baseline_rows.items()
                    if row_index != 0
                }
                self.assertLessEqual(len(signs), 1)

    def test_each_domain_uses_its_own_local_axis_family(self) -> None:
        source = _combine_domain_analyses(
            _triangular_analysis(
                row_count=3,
                column_count=4,
                source_prefix="a",
            ),
            _triangular_analysis(
                row_count=3,
                column_count=4,
                rotation_deg=25.0,
                translation_xy_nm=(100.0, 80.0),
                source_prefix="b",
            ),
        )

        result = build_lattice_row_assignment_analysis(source)

        self.assertEqual(len(result.domain_assignments), 2)
        assignment_by_prefix = {
            assignment.source_ids[0][0]: assignment
            for assignment in result.domain_assignments
        }
        self.assertEqual(
            tuple(
                round(candidate.axis_angle_deg, 7)
                for candidate in assignment_by_prefix["a"].candidates
            ),
            (0.0, 60.0, 120.0),
        )
        self.assertEqual(
            tuple(
                round(candidate.axis_angle_deg, 7)
                for candidate in assignment_by_prefix["b"].candidates
            ),
            (25.0, 85.0, 145.0),
        )

    def test_row_indices_do_not_depend_on_source_id_ordering(self) -> None:
        baseline_source = _triangular_analysis()
        relabeled_source = _triangular_analysis(
            reverse_source_labels=True
        )
        baseline = build_lattice_row_assignment_analysis(baseline_source)
        relabeled = build_lattice_row_assignment_analysis(relabeled_source)

        for candidate in baseline.domain_assignments[0].candidates:
            relabeled_candidate = _candidate_by_angle(
                relabeled,
                candidate.axis_angle_deg,
            )
            self.assertEqual(
                {
                    baseline_source.points_xy_nm[member.point_index]: (
                        member.row_index,
                        member.row_parity,
                    )
                    for member in candidate.member_assignments
                },
                {
                    relabeled_source.points_xy_nm[member.point_index]: (
                        member.row_index,
                        member.row_parity,
                    )
                    for member in relabeled_candidate.member_assignments
                },
            )

    def test_missing_interior_molecule_does_not_reindex_other_rows(self) -> None:
        baseline = build_lattice_row_assignment_analysis(
            _triangular_analysis()
        )
        missing_id = "m-01-02"
        with_vacancy = build_lattice_row_assignment_analysis(
            _triangular_analysis(missing_source_ids=(missing_id,))
        )

        for candidate in baseline.domain_assignments[0].candidates:
            vacancy_candidate = _candidate_by_angle(
                with_vacancy,
                candidate.axis_angle_deg,
            )
            baseline_rows = {
                source_id: (member.row_index, member.row_parity)
                for source_id, member in zip(
                    candidate.source_ids,
                    candidate.member_assignments,
                )
                if source_id != missing_id
            }
            vacancy_rows = {
                source_id: (member.row_index, member.row_parity)
                for source_id, member in zip(
                    vacancy_candidate.source_ids,
                    vacancy_candidate.member_assignments,
                )
            }
            self.assertEqual(vacancy_rows, baseline_rows)

    def test_missing_orientation_gauge_bond_does_not_flip_row_indices(
        self,
    ) -> None:
        baseline = build_lattice_row_assignment_analysis(
            _triangular_analysis()
        )
        missing_id = "m-00-01"
        with_vacancy = build_lattice_row_assignment_analysis(
            _triangular_analysis(missing_source_ids=(missing_id,))
        )

        for candidate in baseline.domain_assignments[0].candidates:
            vacancy_candidate = _candidate_by_angle(
                with_vacancy,
                candidate.axis_angle_deg,
            )
            self.assertEqual(
                {
                    member.source_id: (
                        member.row_index,
                        member.row_parity,
                    )
                    for member in candidate.member_assignments
                    if member.source_id != missing_id
                },
                {
                    member.source_id: (
                        member.row_index,
                        member.row_parity,
                    )
                    for member in vacancy_candidate.member_assignments
                },
            )

    def test_missing_molecule_near_sample_origin_does_not_flip_gauge(
        self,
    ) -> None:
        centroid_y = 10.0 * sqrt(3.0) * 0.5 * 1.5
        translation = (0.0, 0.01 - centroid_y)
        baseline = build_lattice_row_assignment_analysis(
            _triangular_analysis(translation_xy_nm=translation)
        )
        missing_id = "m-03-04"
        with_vacancy = build_lattice_row_assignment_analysis(
            _triangular_analysis(
                translation_xy_nm=translation,
                missing_source_ids=(missing_id,),
            )
        )

        for candidate in baseline.domain_assignments[0].candidates:
            vacancy_candidate = _candidate_by_angle(
                with_vacancy,
                candidate.axis_angle_deg,
            )
            self.assertEqual(
                {
                    member.source_id: (
                        member.row_index,
                        member.row_parity,
                    )
                    for member in candidate.member_assignments
                    if member.source_id != missing_id
                },
                {
                    member.source_id: (
                        member.row_index,
                        member.row_parity,
                    )
                    for member in vacancy_candidate.member_assignments
                },
            )

    def test_missing_boundary_row_does_not_reindex_visible_rows(self) -> None:
        baseline = build_lattice_row_assignment_analysis(
            _triangular_analysis()
        )
        missing_ids = tuple(f"m-00-{column:02d}" for column in range(5))
        clipped = build_lattice_row_assignment_analysis(
            _triangular_analysis(missing_source_ids=missing_ids)
        )

        for candidate in baseline.domain_assignments[0].candidates:
            clipped_candidate = _candidate_by_angle(
                clipped,
                candidate.axis_angle_deg,
            )
            baseline_rows = {
                member.source_id: (member.row_index, member.row_parity)
                for member in candidate.member_assignments
                if member.source_id not in missing_ids
            }
            clipped_rows = {
                member.source_id: (member.row_index, member.row_parity)
                for member in clipped_candidate.member_assignments
            }
            self.assertEqual(clipped_rows, baseline_rows)

    def test_registration_shift_is_expressed_in_sample_row_coordinates(
        self,
    ) -> None:
        row_spacing = 10.0 * sqrt(3.0) * 0.5
        first = build_lattice_row_assignment_analysis(
            _triangular_analysis(registration_fingerprint="registration-a")
        )
        second = build_lattice_row_assignment_analysis(
            _triangular_analysis(
                translation_xy_nm=(0.0, 2.0 * row_spacing),
                registration_fingerprint="registration-b",
            )
        )

        self.assertEqual(
            {
                _partition_signature(candidate)
                for candidate in first.domain_assignments[0].candidates
            },
            {
                _partition_signature(candidate)
                for candidate in second.domain_assignments[0].candidates
            },
        )
        first_horizontal = _candidate_by_angle(first, 0.0)
        second_horizontal = _candidate_by_angle(second, 0.0)
        self.assertEqual(
            {
                member.source_id: (
                    member.row_index + 2,
                    member.row_parity,
                )
                for member in first_horizontal.member_assignments
            },
            {
                member.source_id: (
                    member.row_index,
                    member.row_parity,
                )
                for member in second_horizontal.member_assignments
            },
        )
        self.assertNotEqual(
            lattice_row_assignment_analysis_fingerprint(first),
            lattice_row_assignment_analysis_fingerprint(second),
        )

    def test_sparse_axis_family_keeps_all_three_row_candidates(self) -> None:
        source = _triangular_analysis(row_count=1, column_count=3)

        result = build_lattice_row_assignment_analysis(source)

        assignment = result.domain_assignments[0]
        self.assertEqual(len(assignment.candidates), 3)
        self.assertEqual(assignment.status, "ambiguous")
        self.assertIsNotNone(assignment.selection_margin)

    def test_small_domain_is_explicitly_unavailable_with_members_preserved(
        self,
    ) -> None:
        source = _triangular_analysis(row_count=1, column_count=2)

        result = build_lattice_row_assignment_analysis(source)

        assignment = result.domain_assignments[0]
        self.assertEqual(assignment.status, "unavailable")
        self.assertEqual(assignment.reason, "insufficient_domain_molecules")
        self.assertEqual(assignment.source_ids, source.source_ids)
        self.assertEqual(assignment.candidates, ())
        self.assertIsNone(assignment.selection_margin)

    def test_contract_rejects_inconsistent_parity_and_provenance(self) -> None:
        source = _triangular_analysis()
        result = build_lattice_row_assignment_analysis(source)
        candidate = result.domain_assignments[0].candidates[0]
        member = candidate.member_assignments[0]

        with self.assertRaisesRegex(ValueError, "row_parity"):
            replace(member, row_parity=1 - member.row_parity)
        with self.assertRaisesRegex(ValueError, "settings_fingerprint"):
            replace(
                result,
                settings_fingerprint="wrong",
            )
        with self.assertRaisesRegex(ValueError, "reason"):
            replace(
                result.domain_assignments[0],
                reason="misspelled_reason",
            )
        with self.assertRaisesRegex(ValueError, "status"):
            replace(
                result.domain_assignments[0],
                reason="unique_best_axis",
            )
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            replace(
                result.domain_assignments[0],
                candidates=(),
                selection_margin=None,
                axis_family_coherence=None,
            )
        with self.assertRaisesRegex(ValueError, "candidate"):
            replace(
                result.domain_assignments[0],
                status="unavailable",
                reason="axis_family_unavailable",
            )

        unavailable = build_lattice_row_assignment_analysis(
            _triangular_analysis(row_count=1, column_count=2)
        ).domain_assignments[0]
        with self.assertRaisesRegex(ValueError, "candidate"):
            replace(
                unavailable,
                reason="candidate_score_below_minimum",
            )

    def test_contract_rejects_duplicate_and_mispaired_row_members(self) -> None:
        result = build_lattice_row_assignment_analysis(
            _triangular_analysis()
        )
        candidate = result.domain_assignments[0].candidates[0]
        rows = list(candidate.rows)
        destination_index = next(
            index for index, row in enumerate(rows) if len(row.source_ids) >= 2
        )
        source_index = next(
            index for index in range(len(rows)) if index != destination_index
        )
        destination = rows[destination_index]
        source = rows[source_index]
        duplicate_pairs = sorted(
            (
                *zip(destination.source_ids, destination.point_indices),
                (source.source_ids[0], source.point_indices[0]),
            )
        )
        duplicate_row = replace(
            destination,
            source_ids=tuple(pair[0] for pair in duplicate_pairs),
            point_indices=tuple(pair[1] for pair in duplicate_pairs),
        )
        duplicate_rows = list(rows)
        duplicate_rows[destination_index] = duplicate_row

        with self.assertRaisesRegex(ValueError, "partition"):
            replace(candidate, rows=tuple(duplicate_rows))

        swapped_pairs = list(
            zip(destination.source_ids, destination.point_indices)
        )
        swapped_pairs[0] = (
            swapped_pairs[0][0],
            swapped_pairs[1][1],
        )
        swapped_pairs[1] = (
            swapped_pairs[1][0],
            destination.point_indices[0],
        )
        mispaired_row = replace(
            destination,
            point_indices=tuple(pair[1] for pair in swapped_pairs),
        )
        mispaired_rows = list(rows)
        mispaired_rows[destination_index] = mispaired_row

        with self.assertRaisesRegex(ValueError, "pairs"):
            replace(candidate, rows=tuple(mispaired_rows))

        first_row, second_row = rows[:2]
        first_member = next(
            member
            for member in candidate.member_assignments
            if member.source_id == first_row.source_ids[0]
        )
        second_source_id = second_row.source_ids[0]
        duplicate_index_assignments = tuple(
            replace(member, point_index=first_member.point_index)
            if member.source_id == second_source_id
            else member
            for member in candidate.member_assignments
        )
        duplicate_index_rows = tuple(
            replace(
                row,
                point_indices=tuple(
                    first_member.point_index
                    if source_id == second_source_id
                    else point_index
                    for source_id, point_index in zip(
                        row.source_ids,
                        row.point_indices,
                    )
                ),
            )
            if second_source_id in row.source_ids
            else row
            for row in rows
        )

        with self.assertRaisesRegex(ValueError, "point indices"):
            replace(
                candidate,
                member_assignments=duplicate_index_assignments,
                rows=duplicate_index_rows,
            )

    def test_settings_are_versioned_and_fingerprinted(self) -> None:
        settings = LatticeRowAssignmentSettings(
            axis_cluster_tolerance_deg=12.0,
            row_residual_tolerance_fraction=0.2,
            minimum_selection_margin=0.08,
        )

        self.assertEqual(
            LatticeRowAssignmentSettings.from_dict(settings.to_dict()),
            settings,
        )
        self.assertEqual(
            lattice_row_assignment_settings_fingerprint(settings),
            lattice_row_assignment_settings_fingerprint(settings),
        )


if __name__ == "__main__":
    unittest.main()
