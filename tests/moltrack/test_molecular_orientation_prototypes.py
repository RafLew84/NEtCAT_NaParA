import unittest
from dataclasses import replace
from math import sqrt

from moltrack.analysis import (
    LatticeDomainRowAssignment,
    LatticeRow,
    LatticeRowAssignmentAnalysis,
    LatticeRowAssignmentSettings,
    LatticeRowAxisCandidate,
    LatticeRowMemberAssignment,
    MolecularOrientationFrameData,
    MolecularOrientationMeasurement,
    MolecularOrientationPrototypeSettings,
    MolecularOrientationProvenance,
    build_molecular_orientation_prototype_analysis,
    lattice_row_assignment_settings_fingerprint,
    molecular_orientation_prototype_analysis_fingerprint,
    molecular_orientation_prototype_settings_fingerprint,
)


def _row_analysis(
    frame_index: int,
    *,
    row_count: int = 4,
    column_count: int = 4,
    column_start: int = 0,
    missing_sites: frozenset[tuple[int, int]] = frozenset(),
) -> LatticeRowAssignmentAnalysis:
    spacing_nm = 10.0
    row_spacing_nm = spacing_nm * sqrt(3.0) * 0.5
    source_ids = tuple(
        f"f{frame_index:02d}-r{row:02d}-c{column:02d}"
        for row in range(row_count)
        for column in range(column_start, column_start + column_count)
        if (row, column) not in missing_sites
    )
    point_index_by_id = {
        source_id: index for index, source_id in enumerate(source_ids)
    }
    candidates = []
    for candidate_index, axis_angle_deg in enumerate((0.0, 60.0, 120.0)):
        members = tuple(
            LatticeRowMemberAssignment(
                point_index=point_index_by_id[source_id],
                source_id=source_id,
                row_index=row,
                row_parity=row % 2,
                along_coordinate_nm=(
                    column * spacing_nm + 0.5 * row * spacing_nm
                ),
                normal_coordinate_nm=row * row_spacing_nm,
                row_residual_nm=0.0,
            )
            for row in range(row_count)
            for column in range(
                column_start,
                column_start + column_count,
            )
            if (row, column) not in missing_sites
            for source_id in (
                f"f{frame_index:02d}-r{row:02d}-c{column:02d}",
            )
        )
        rows = tuple(
            LatticeRow(
                row_index=row,
                parity=row % 2,
                point_indices=tuple(
                    point_index_by_id[
                        f"f{frame_index:02d}-r{row:02d}-c{column:02d}"
                    ]
                    for column in range(
                        column_start,
                        column_start + column_count,
                    )
                    if (row, column) not in missing_sites
                ),
                source_ids=tuple(
                    f"f{frame_index:02d}-r{row:02d}-c{column:02d}"
                    for column in range(
                        column_start,
                        column_start + column_count,
                    )
                    if (row, column) not in missing_sites
                ),
                normal_coordinate_nm=row * row_spacing_nm,
                maximum_residual_nm=0.0,
            )
            for row in range(row_count)
        )
        candidates.append(
            LatticeRowAxisCandidate(
                candidate_index=candidate_index,
                axis_angle_deg=axis_angle_deg,
                row_spacing_nm=row_spacing_nm,
                row_origin_normal_nm=0.0,
                axis_bond_support_count=12,
                axis_bond_support_fraction=1.0 / 3.0,
                assigned_molecule_count=len(source_ids),
                inlier_molecule_count=len(source_ids),
                inlier_fraction=1.0,
                median_residual_nm=0.0,
                median_residual_fraction=0.0,
                score=1.0,
                source_ids=source_ids,
                member_assignments=members,
                rows=rows,
            )
        )
    domain = LatticeDomainRowAssignment(
        lattice_domain_id=f"domain-{frame_index}",
        molecule_count=len(source_ids),
        source_ids=source_ids,
        status="ambiguous",
        candidates=tuple(candidates),
        selected_candidate_index=None,
        selection_margin=0.0,
        axis_family_coherence=1.0,
        reason="symmetry_equivalent_axes_not_resolved",
    )
    settings = LatticeRowAssignmentSettings()
    return LatticeRowAssignmentAnalysis(
        source_ids=source_ids,
        point_count=len(source_ids),
        domain_assignments=(domain,),
        settings=settings,
        coordinate_frame="sample_nm",
        orientation_reference="+x_sample_axis",
        spatial_calibration_fingerprint="calibration-v1",
        registration_fingerprint=f"registration-{frame_index}",
        point_coordinate_fingerprint=f"points-{frame_index}",
        lattice_domain_analysis_fingerprint=f"domains-{frame_index}",
        settings_fingerprint=lattice_row_assignment_settings_fingerprint(
            settings
        ),
    )


def _measurement(
    *,
    frame_index: int,
    source_id: str,
    angle_deg: float,
    confidence: float,
    periodicity_deg: float = 180.0,
    status: str = "available",
) -> MolecularOrientationMeasurement:
    return MolecularOrientationMeasurement(
        measurement_id=f"orientation-{source_id}",
        status=status,
        angle_deg=angle_deg,
        periodicity_deg=periodicity_deg,
        confidence=confidence,
        method="manual",
        patch_shape_px=(8, 8),
        provenance=MolecularOrientationProvenance(
            source_file_name="movie.mpp",
            source_file_sha256="a" * 64,
            source_session_file_name=None,
            source_session_sha256=None,
            frame_index=frame_index,
            source_view="expanded_aligned",
            source_kind="segmentation",
            source_id=source_id,
            patch_bbox_xyxy=(0.0, 0.0, 8.0, 8.0),
            orientation_reference="sample_x_axis_counterclockwise",
        ),
    )


def _frame_data(
    frame_index: int,
    *,
    state_for_site,
    prototype_angles: tuple[float, ...],
    confidence: float = 1.0,
    row_count: int = 4,
    column_count: int = 4,
    column_start: int = 0,
    missing_sites: frozenset[tuple[int, int]] = frozenset(),
) -> MolecularOrientationFrameData:
    rows = _row_analysis(
        frame_index,
        row_count=row_count,
        column_count=column_count,
        column_start=column_start,
        missing_sites=missing_sites,
    )
    measurements = []
    for row in range(row_count):
        for column in range(column_start, column_start + column_count):
            if (row, column) in missing_sites:
                continue
            source_id = f"f{frame_index:02d}-r{row:02d}-c{column:02d}"
            state_index = int(state_for_site(row, column))
            measurements.append(
                _measurement(
                    frame_index=frame_index,
                    source_id=source_id,
                    angle_deg=prototype_angles[state_index],
                    confidence=confidence,
                )
            )
    return MolecularOrientationFrameData(
        frame_index=frame_index,
        row_assignment=rows,
        measurements=tuple(measurements),
    )


def _with_axis_angles(
    frame: MolecularOrientationFrameData,
    angles_deg: tuple[float, float, float],
) -> MolecularOrientationFrameData:
    domain = frame.row_assignment.domain_assignments[0]
    candidates = tuple(
        replace(candidate, axis_angle_deg=angle)
        for candidate, angle in zip(domain.candidates, angles_deg)
    )
    return replace(
        frame,
        row_assignment=replace(
            frame.row_assignment,
            domain_assignments=(
                replace(domain, candidates=candidates),
            ),
        ),
    )


class MolecularOrientationPrototypeAnalysisTests(unittest.TestCase):
    def test_two_prototypes_are_learned_across_frames_with_confidence_weights(
        self,
    ) -> None:
        frames = (
            _frame_data(
                0,
                state_for_site=lambda row, column: (row + column) % 2,
                prototype_angles=(10.0, 75.0),
                confidence=0.5,
            ),
            _frame_data(
                1,
                state_for_site=lambda row, column: (row + column) % 2,
                prototype_angles=(20.0, 85.0),
                confidence=1.0,
            ),
        )

        result = build_molecular_orientation_prototype_analysis(frames)

        self.assertEqual(result.status, "two_state")
        self.assertEqual(result.reason, "two_supported_states")
        self.assertEqual(result.eligible_frame_indices, (0, 1))
        self.assertEqual(result.eligible_observation_count, 32)
        self.assertEqual(
            tuple(prototype.state_label for prototype in result.prototypes),
            ("A", "B"),
        )
        self.assertGreater(result.prototype_for_state("A").angle_deg, 15.0)
        self.assertLess(result.prototype_for_state("A").angle_deg, 18.0)
        self.assertGreater(result.prototype_for_state("B").angle_deg, 80.0)
        self.assertLess(result.prototype_for_state("B").angle_deg, 83.0)
        self.assertEqual(len(result.axis_evidence), 6)

    def test_prototypes_are_not_hardcoded_to_one_reference_frame(self) -> None:
        first = _frame_data(
            0,
            state_for_site=lambda row, column: column % 2,
            prototype_angles=(34.0, 126.0),
        )
        second = _frame_data(
            1,
            state_for_site=lambda row, column: column % 2,
            prototype_angles=(36.0, 124.0),
        )

        result = build_molecular_orientation_prototype_analysis(
            (first, second)
        )

        self.assertEqual(result.status, "two_state")
        self.assertAlmostEqual(
            result.prototype_for_state("A").angle_deg,
            35.0,
            places=5,
        )
        self.assertAlmostEqual(
            result.prototype_for_state("B").angle_deg,
            125.0,
            places=5,
        )

    def test_periodic_wrap_is_one_state_not_two(self) -> None:
        frames = (
            _frame_data(
                0,
                state_for_site=lambda _row, _column: 0,
                prototype_angles=(178.0,),
            ),
            _frame_data(
                1,
                state_for_site=lambda _row, _column: 0,
                prototype_angles=(2.0,),
            ),
        )
        settings = MolecularOrientationPrototypeSettings(
            cluster_tolerance_deg=6.0
        )

        result = build_molecular_orientation_prototype_analysis(
            frames,
            settings=settings,
        )

        self.assertEqual(result.status, "one_state")
        self.assertEqual(result.reason, "one_supported_state")
        self.assertEqual(len(result.prototypes), 1)
        self.assertLess(
            min(
                result.prototypes[0].angle_deg,
                180.0 - result.prototypes[0].angle_deg,
            ),
            1e-6,
        )
        self.assertEqual(result.axis_evidence, ())

    def test_more_than_two_supported_states_is_not_forced_into_ab(self) -> None:
        frames = tuple(
            _frame_data(
                frame_index,
                state_for_site=lambda row, column: (row + column) % 3,
                prototype_angles=(10.0, 70.0, 130.0),
            )
            for frame_index in (0, 1)
        )

        result = build_molecular_orientation_prototype_analysis(frames)

        self.assertEqual(result.status, "multi_state")
        self.assertEqual(result.reason, "more_than_two_supported_states")
        self.assertEqual(len(result.prototypes), 3)
        self.assertTrue(
            all(
                prototype.state_label is None
                for prototype in result.prototypes
            )
        )
        self.assertEqual(result.axis_evidence, ())

    def test_low_confidence_outlier_does_not_create_a_third_state(self) -> None:
        frames = [
            _frame_data(
                frame_index,
                state_for_site=lambda row, column: (row + column) % 2,
                prototype_angles=(20.0, 80.0),
            )
            for frame_index in (0, 1)
        ]
        outlier = frames[0].measurements[0]
        frames[0] = replace(
            frames[0],
            measurements=(
                replace(outlier, angle_deg=140.0, confidence=0.1),
                *frames[0].measurements[1:],
            ),
        )

        result = build_molecular_orientation_prototype_analysis(tuple(frames))

        self.assertEqual(result.status, "two_state")
        self.assertEqual(result.excluded_low_confidence_count, 1)
        self.assertEqual(result.eligible_observation_count, 31)

    def test_single_frame_outlier_is_not_a_supported_orientation_state(
        self,
    ) -> None:
        frames = [
            _frame_data(
                frame_index,
                state_for_site=lambda row, column: (row + column) % 2,
                prototype_angles=(20.0, 80.0),
            )
            for frame_index in (0, 1)
        ]
        outlier = frames[0].measurements[0]
        frames[0] = replace(
            frames[0],
            measurements=(
                replace(outlier, angle_deg=140.0),
                *frames[0].measurements[1:],
            ),
        )

        result = build_molecular_orientation_prototype_analysis(tuple(frames))

        self.assertEqual(result.status, "two_state")
        self.assertEqual(result.unsupported_state_observation_count, 1)
        self.assertEqual(
            sum(value.observation_count for value in result.prototypes),
            31,
        )

    def test_states_confined_to_separate_frames_are_not_forced_into_ab(
        self,
    ) -> None:
        frames = (
            _frame_data(
                0,
                state_for_site=lambda _row, _column: 0,
                prototype_angles=(20.0,),
            ),
            _frame_data(
                1,
                state_for_site=lambda _row, _column: 0,
                prototype_angles=(80.0,),
            ),
        )

        result = build_molecular_orientation_prototype_analysis(frames)

        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason, "insufficient_state_support")
        self.assertEqual(result.unsupported_state_observation_count, 32)

    def test_single_frame_and_incompatible_periodicity_are_unavailable(
        self,
    ) -> None:
        frame = _frame_data(
            0,
            state_for_site=lambda row, column: column % 2,
            prototype_angles=(20.0, 80.0),
        )

        single = build_molecular_orientation_prototype_analysis((frame,))
        changed = replace(
            frame.measurements[0],
            angle_deg=20.0,
            periodicity_deg=120.0,
        )
        incompatible = build_molecular_orientation_prototype_analysis(
            (
                replace(
                    frame,
                    measurements=(changed, *frame.measurements[1:]),
                ),
                _frame_data(
                    1,
                    state_for_site=lambda row, column: column % 2,
                    prototype_angles=(20.0, 80.0),
                ),
            )
        )

        self.assertEqual(single.status, "unavailable")
        self.assertEqual(single.reason, "insufficient_frame_coverage")
        self.assertEqual(incompatible.status, "unavailable")
        self.assertEqual(
            incompatible.reason,
            "incompatible_periodicity",
        )

    def test_each_axis_compares_abab_baba_and_both_neighbor_directions(
        self,
    ) -> None:
        frames = tuple(
            _frame_data(
                frame_index,
                state_for_site=lambda row, column: (row + column) % 2,
                prototype_angles=(20.0, 80.0),
            )
            for frame_index in (0, 1)
        )

        result = build_molecular_orientation_prototype_analysis(frames)

        self.assertEqual(result.status, "two_state")
        self.assertEqual(len(result.axis_evidence), 6)
        for evidence in result.axis_evidence:
            self.assertEqual(len(evidence.assignments), 16)
            self.assertAlmostEqual(
                evidence.hypothesis("checkerboard", "ABAB").agreement_score,
                1.0,
            )
            self.assertAlmostEqual(
                evidence.hypothesis("checkerboard", "BABA").agreement_score,
                0.0,
            )
            self.assertAlmostEqual(
                evidence.along_row_alternation_score,
                1.0,
            )
            self.assertAlmostEqual(
                evidence.between_row_alternation_score,
                1.0,
            )
            self.assertGreater(evidence.along_row_edge_count, 0)
            self.assertGreater(evidence.between_row_edge_count, 0)

    def test_along_and_between_patterns_keep_their_own_phase_scores(self) -> None:
        along_frames = tuple(
            _frame_data(
                frame_index,
                state_for_site=lambda _row, column: column % 2,
                prototype_angles=(20.0, 80.0),
            )
            for frame_index in (0, 1)
        )
        between_frames = tuple(
            _frame_data(
                frame_index,
                state_for_site=lambda row, _column: row % 2,
                prototype_angles=(20.0, 80.0),
            )
            for frame_index in (0, 1)
        )

        along = build_molecular_orientation_prototype_analysis(along_frames)
        between = build_molecular_orientation_prototype_analysis(
            between_frames
        )

        for evidence in along.axis_evidence:
            self.assertAlmostEqual(
                evidence.hypothesis("along_rows", "ABAB").agreement_score,
                1.0,
            )
            self.assertAlmostEqual(
                evidence.along_row_alternation_score,
                1.0,
            )
        for evidence in between.axis_evidence:
            self.assertAlmostEqual(
                evidence.hypothesis("between_rows", "ABAB").agreement_score,
                1.0,
            )
            self.assertAlmostEqual(
                evidence.between_row_alternation_score,
                1.0,
            )

    def test_range_phase_evidence_aggregates_every_eligible_frame(
        self,
    ) -> None:
        frames = (
            _frame_data(
                0,
                state_for_site=lambda row, column: (row + column) % 2,
                prototype_angles=(20.0, 80.0),
            ),
            _frame_data(
                1,
                state_for_site=lambda row, column: (row + column) % 2,
                prototype_angles=(20.0, 80.0),
            ),
            _frame_data(
                2,
                state_for_site=lambda row, column: 1
                - (row + column) % 2,
                prototype_angles=(20.0, 80.0),
            ),
        )

        result = build_molecular_orientation_prototype_analysis(frames)

        self.assertEqual(len(result.range_axis_evidence), 3)
        for evidence in result.range_axis_evidence:
            self.assertEqual(evidence.frame_indices, (0, 1, 2))
            self.assertEqual(evidence.axis_evidence_count, 3)
            self.assertEqual(evidence.observation_count, 48)
            self.assertAlmostEqual(
                evidence.hypothesis(
                    "checkerboard",
                    "ABAB",
                ).agreement_score,
                2.0 / 3.0,
            )
            self.assertAlmostEqual(
                evidence.hypothesis(
                    "checkerboard",
                    "BABA",
                ).agreement_score,
                1.0 / 3.0,
            )

    def test_range_axis_families_follow_angles_not_local_candidate_indices(
        self,
    ) -> None:
        first = _frame_data(
            0,
            state_for_site=lambda row, column: (row + column) % 2,
            prototype_angles=(20.0, 80.0),
        )
        second = _with_axis_angles(
            _frame_data(
                1,
                state_for_site=lambda row, column: (row + column) % 2,
                prototype_angles=(20.0, 80.0),
            ),
            (30.0, 90.0, 150.0),
        )

        result = build_molecular_orientation_prototype_analysis(
            (first, second)
        )

        self.assertEqual(result.status, "two_state")
        self.assertEqual(result.range_axis_evidence, ())

    def test_small_axis_drift_is_aggregated_in_sample_coordinates(
        self,
    ) -> None:
        first = _frame_data(
            0,
            state_for_site=lambda row, column: (row + column) % 2,
            prototype_angles=(20.0, 80.0),
        )
        second = _with_axis_angles(
            _frame_data(
                1,
                state_for_site=lambda row, column: (row + column) % 2,
                prototype_angles=(20.0, 80.0),
            ),
            (2.0, 62.0, 122.0),
        )

        result = build_molecular_orientation_prototype_analysis(
            (first, second)
        )

        self.assertEqual(
            tuple(
                round(value.axis_angle_deg)
                for value in result.range_axis_evidence
            ),
            (1, 61, 121),
        )
        self.assertTrue(
            all(
                value.axis_evidence_count == 2
                for value in result.range_axis_evidence
            )
        )

    def test_phase_gauge_does_not_follow_the_visible_domain_edge(self) -> None:
        first = _frame_data(
            0,
            state_for_site=lambda row, column: (row + column) % 2,
            prototype_angles=(20.0, 80.0),
        )
        cropped = _frame_data(
            1,
            state_for_site=lambda row, column: (row + column) % 2,
            prototype_angles=(20.0, 80.0),
            column_count=3,
            column_start=1,
        )

        result = build_molecular_orientation_prototype_analysis(
            (first, cropped)
        )

        for evidence in result.range_axis_evidence:
            self.assertAlmostEqual(
                evidence.hypothesis(
                    "checkerboard",
                    "ABAB",
                ).agreement_score,
                1.0,
            )

    def test_settings_and_analysis_are_deterministically_fingerprinted(
        self,
    ) -> None:
        settings = MolecularOrientationPrototypeSettings(
            minimum_confidence=0.6,
            cluster_tolerance_deg=10.0,
        )
        frames = tuple(
            _frame_data(
                frame_index,
                state_for_site=lambda row, column: (row + column) % 2,
                prototype_angles=(20.0, 80.0),
            )
            for frame_index in (0, 1)
        )
        result = build_molecular_orientation_prototype_analysis(
            frames,
            settings=settings,
        )

        self.assertEqual(
            MolecularOrientationPrototypeSettings.from_dict(
                settings.to_dict()
            ),
            settings,
        )
        self.assertEqual(
            result.settings_fingerprint,
            molecular_orientation_prototype_settings_fingerprint(settings),
        )
        self.assertEqual(
            molecular_orientation_prototype_analysis_fingerprint(result),
            molecular_orientation_prototype_analysis_fingerprint(result),
        )
        with self.assertRaisesRegex(ValueError, "state_label"):
            replace(result.prototypes[0], state_label="C")
        with self.assertRaisesRegex(
            ValueError,
            "row-assignment fingerprint",
        ):
            replace(result, row_assignment_fingerprints=((),))
        with self.assertRaisesRegex(ValueError, "at least two"):
            MolecularOrientationPrototypeSettings(
                minimum_frame_count=1,
            )
        with self.assertRaisesRegex(ValueError, "at least two"):
            MolecularOrientationPrototypeSettings(
                minimum_state_frame_count=1,
            )


if __name__ == "__main__":
    unittest.main()
