import unittest
from dataclasses import replace

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularFrameRangeAnalysisScope,
    MolecularOrderFrame,
    MolecularOrderHierarchy,
    MolecularOrderLatticeDomain,
    MolecularOrderOrientationalSubdomain,
    MolecularOrderStacking,
    MolecularOrderTypeClassificationSettings,
    classify_molecular_order_types,
    molecular_order_type_classification_fingerprint,
    periodic_orientation_distance_deg,
)
from test_molecular_order_hierarchy import _inputs


def _domain_frame(
    frame_index,
    *,
    symmetry="trifold",
    theta3_deg=10.0,
    theta6_deg=None,
    orientation_angles=(20.0, 80.0),
    stacking_pattern="ABAB",
    stacking_mode="checkerboard",
    stacking_phase="ABAB",
):
    lattice, rows, stacking = _inputs(frame_index=7)
    from moltrack.analysis import build_molecular_order_hierarchy

    template = build_molecular_order_hierarchy(
        {7: lattice},
        {7: rows},
        stacking,
    ).frames[0].lattice_domains[0]
    domain_id = f"lattice-type-test-{frame_index:04d}"
    if symmetry == "trifold":
        orientation_fields = {
            "theta3_lattice_prototype_deg": theta3_deg,
            "theta6_prototype_deg": None,
            "theta3_lattice_spread_deg": 1.0,
            "theta6_spread_deg": None,
            "dominant_symmetry": "trifold",
            "orientation_reference_channel": "m3_lattice",
            "m3_m6_orientation_relation_status": "not_applicable",
            "m3_m6_orientation_offset_deg": None,
        }
    elif symmetry == "sixfold":
        orientation_fields = {
            "theta3_lattice_prototype_deg": None,
            "theta6_prototype_deg": theta6_deg,
            "theta3_lattice_spread_deg": None,
            "theta6_spread_deg": 1.0,
            "dominant_symmetry": "sixfold",
            "orientation_reference_channel": "m6",
            "m3_m6_orientation_relation_status": "not_applicable",
            "m3_m6_orientation_offset_deg": None,
        }
    elif symmetry == "mixed":
        orientation_fields = {
            "theta3_lattice_prototype_deg": theta3_deg,
            "theta6_prototype_deg": theta6_deg,
            "theta3_lattice_spread_deg": 1.0,
            "theta6_spread_deg": 1.0,
            "dominant_symmetry": "mixed",
            "orientation_reference_channel": "joint",
            "m3_m6_orientation_relation_status": "available",
            "m3_m6_orientation_offset_deg": 0.0,
        }
    else:
        raise ValueError(f"Unsupported test symmetry: {symmetry!r}.")
    lattice_domain = replace(
        template.lattice_domain,
        lattice_domain_id=domain_id,
        **orientation_fields,
    )

    if stacking_pattern == "unavailable":
        stacking_order = replace(
            template.stacking_order,
            frame_index=frame_index,
            lattice_domain_id=domain_id,
            pattern="unavailable",
            axis_candidate_index=None,
            axis_angle_deg=None,
            mode=None,
            phase=None,
            prototype_a_angle_deg=None,
            prototype_b_angle_deg=None,
            periodicity_deg=None,
            score=None,
            confidence=0.0,
            usable_molecule_count=0,
            ordered_molecule_count=0,
            coverage_fraction=0.0,
            ordered_fraction=0.0,
            subdomain_ids=(),
            qc_reasons=("prototype_states_unavailable",),
        )
        hierarchy_domain = MolecularOrderLatticeDomain(
            frame_index=frame_index,
            lattice_domain=lattice_domain,
            stacking_order=stacking_order,
            orientational_subdomains=(),
            unresolved_source_ids=lattice_domain.source_ids,
        )
    else:
        subdomain_id = f"{domain_id}:orient-0001"
        source_subdomain = template.orientational_subdomains[0].stacking_order.subdomain
        if stacking_pattern == "uniform":
            source_subdomain = replace(
                source_subdomain,
                subdomain_id=subdomain_id,
                frame_index=frame_index,
                parent_lattice_domain_id=domain_id,
                pattern="uniform",
                axis_candidate_index=None,
                axis_angle_deg=None,
                mode=None,
                phase=None,
            )
            stacking_order = replace(
                template.stacking_order,
                frame_index=frame_index,
                lattice_domain_id=domain_id,
                pattern="uniform",
                axis_candidate_index=None,
                axis_angle_deg=None,
                mode=None,
                phase=None,
                prototype_a_angle_deg=orientation_angles[0],
                prototype_b_angle_deg=None,
                periodicity_deg=180.0,
                subdomain_ids=(subdomain_id,),
            )
        else:
            source_subdomain = replace(
                source_subdomain,
                subdomain_id=subdomain_id,
                frame_index=frame_index,
                parent_lattice_domain_id=domain_id,
                mode=stacking_mode,
                phase=stacking_phase,
            )
            stacking_order = replace(
                template.stacking_order,
                frame_index=frame_index,
                lattice_domain_id=domain_id,
                mode=stacking_mode,
                phase=stacking_phase,
                prototype_a_angle_deg=orientation_angles[0],
                prototype_b_angle_deg=orientation_angles[1],
                subdomain_ids=(subdomain_id,),
            )
        local_stacking = MolecularOrderStacking(
            frame_index=frame_index,
            parent_lattice_domain_id=domain_id,
            parent_orientational_subdomain_id=subdomain_id,
            subdomain=source_subdomain,
        )
        orientational = MolecularOrderOrientationalSubdomain(
            frame_index=frame_index,
            parent_lattice_domain_id=domain_id,
            orientational_subdomain_id=subdomain_id,
            source_ids=source_subdomain.source_ids,
            stacking_order=local_stacking,
        )
        hierarchy_domain = MolecularOrderLatticeDomain(
            frame_index=frame_index,
            lattice_domain=lattice_domain,
            stacking_order=stacking_order,
            orientational_subdomains=(orientational,),
            unresolved_source_ids=(),
        )
    return MolecularOrderFrame(
        frame_index=frame_index,
        source_ids=lattice_domain.source_ids,
        lattice_domains=(hierarchy_domain,),
        unassigned_source_ids=(),
        lattice_domain_analysis_fingerprint=f"{frame_index + 1:064x}",
        row_assignment_fingerprint=f"{frame_index + 101:064x}",
    )


def _hierarchy(*frames):
    ordered_frames = tuple(sorted(frames, key=lambda value: value.frame_index))
    return MolecularOrderHierarchy(
        frames=ordered_frames,
        input_frame_indices=tuple(
            frame.frame_index for frame in ordered_frames
        ),
        source_file_sha256=None,
        source_view="expanded_aligned",
        prototype_analysis_fingerprint="a" * 64,
        stacking_analysis_fingerprint="b" * 64,
    )


def _single_scope(start_frame, end_frame):
    return MolecularFrameRangeAnalysisScope(
        analysis_mode="single_range",
        frame_count=end_frame + 1,
        source_view="expanded_aligned",
        ranges=(
            MolecularFrameRange("analysis", start_frame, end_frame),
        ),
    )


def _compare_scope():
    return MolecularFrameRangeAnalysisScope(
        analysis_mode="compare_ranges",
        frame_count=3,
        source_view="expanded_aligned",
        ranges=(
            MolecularFrameRange("before", 0, 0),
            MolecularFrameRange("after", 2, 2),
        ),
    )


class MolecularOrderTypeClassifierTests(unittest.TestCase):
    def test_periodic_distance_wraps_for_lattice_and_molecular_angles(
        self,
    ) -> None:
        self.assertAlmostEqual(
            periodic_orientation_distance_deg(
                58.0,
                2.0,
                periodicity_deg=60.0,
            ),
            4.0,
        )
        self.assertAlmostEqual(
            periodic_orientation_distance_deg(
                178.0,
                2.0,
                periodicity_deg=180.0,
            ),
            4.0,
        )

    def test_compare_ranges_share_jointly_defined_types(self) -> None:
        hierarchy = _hierarchy(
            _domain_frame(
                0,
                theta3_deg=58.0,
                orientation_angles=(178.0, 58.0),
            ),
            _domain_frame(
                2,
                theta3_deg=2.0,
                orientation_angles=(2.0, 62.0),
            ),
        )
        settings = MolecularOrderTypeClassificationSettings(
            lattice_orientation_tolerance_deg=5.0,
            molecular_orientation_tolerance_deg=5.0,
            minimum_observations_per_type=2,
        )

        result = classify_molecular_order_types(
            hierarchy,
            analysis_scope=_compare_scope(),
            settings=settings,
        )

        self.assertFalse(result.uses_tracking)
        self.assertEqual(result.analysis_mode, "compare_ranges")
        self.assertEqual(len(result.geometry_types), 1)
        self.assertEqual(len(result.orientation_types), 1)
        self.assertEqual(len(result.stacking_types), 1)
        before = result.assignment_for_domain(
            "before",
            0,
            "lattice-type-test-0000",
        )
        after = result.assignment_for_domain(
            "after",
            2,
            "lattice-type-test-0002",
        )
        self.assertEqual(
            before.geometry.type_id,
            after.geometry.type_id,
        )
        self.assertEqual(
            before.orientation.type_id,
            after.orientation.type_id,
        )
        self.assertEqual(
            before.stacking.type_id,
            after.stacking.type_id,
        )
        before_observation = next(
            value
            for value in result.observations
            if value.range_name == "before"
        )
        self.assertEqual(
            result.assignment_for_observation_key(
                before_observation.stable_key
            ),
            before,
        )

    def test_swapped_prototype_labels_and_phase_define_one_type(
        self,
    ) -> None:
        hierarchy = _hierarchy(
            _domain_frame(
                0,
                orientation_angles=(20.0, 80.0),
                stacking_phase="ABAB",
            ),
            _domain_frame(
                1,
                orientation_angles=(80.0, 20.0),
                stacking_phase="BABA",
            ),
        )

        result = classify_molecular_order_types(
            hierarchy,
            analysis_scope=_single_scope(0, 1),
            settings=MolecularOrderTypeClassificationSettings(
                stacking_features=("pattern", "mode", "phase"),
                minimum_observations_per_type=2,
            ),
        )

        self.assertEqual(len(result.orientation_types), 1)
        self.assertEqual(len(result.stacking_types), 1)
        self.assertEqual(result.stacking_types[0].phase, "ABAB")

    def test_complete_linkage_does_not_bridge_angle_chain(self) -> None:
        hierarchy = _hierarchy(
            _domain_frame(0, theta3_deg=0.0),
            _domain_frame(1, theta3_deg=4.0),
            _domain_frame(2, theta3_deg=8.0),
        )

        result = classify_molecular_order_types(
            hierarchy,
            analysis_scope=_single_scope(0, 2),
            settings=MolecularOrderTypeClassificationSettings(
                geometry_features=("theta3_lattice",),
                lattice_orientation_tolerance_deg=5.0,
            ),
        )

        self.assertEqual(
            sorted(value.observation_count for value in result.geometry_types),
            [1, 2],
        )
        assignments = {
            value.observation_key[3]: value.geometry.type_id
            for value in result.assignments
        }
        self.assertEqual(assignments[0], assignments[1])
        self.assertNotEqual(assignments[1], assignments[2])

    def test_overlapping_ranges_are_rejected_instead_of_reweighted(
        self,
    ) -> None:
        hierarchy = _hierarchy(
            _domain_frame(0),
            _domain_frame(1),
            _domain_frame(2),
        )
        scope = MolecularFrameRangeAnalysisScope(
            analysis_mode="compare_ranges",
            frame_count=3,
            source_view="expanded_aligned",
            ranges=(
                MolecularFrameRange("before", 0, 1),
                MolecularFrameRange("after", 1, 2),
            ),
        )

        with self.assertRaisesRegex(ValueError, "must not overlap"):
            classify_molecular_order_types(
                hierarchy,
                analysis_scope=scope,
                settings=MolecularOrderTypeClassificationSettings(),
            )

    def test_geometry_orientation_and_stacking_are_classified_independently(
        self,
    ) -> None:
        hierarchy = _hierarchy(
            _domain_frame(0),
            _domain_frame(
                1,
                symmetry="sixfold",
                theta3_deg=None,
                theta6_deg=10.0,
            ),
            _domain_frame(
                2,
                orientation_angles=(40.0, 100.0),
            ),
            _domain_frame(
                3,
                orientation_angles=(20.0,),
                stacking_pattern="uniform",
            ),
        )

        result = classify_molecular_order_types(
            hierarchy,
            analysis_scope=_single_scope(0, 3),
            settings=MolecularOrderTypeClassificationSettings(),
        )

        assignments = {
            value.observation_key[3]: value
            for value in result.assignments
        }
        self.assertEqual(
            assignments[0].geometry.type_id,
            assignments[2].geometry.type_id,
        )
        self.assertNotEqual(
            assignments[0].geometry.type_id,
            assignments[1].geometry.type_id,
        )
        self.assertEqual(
            assignments[0].orientation.type_id,
            assignments[1].orientation.type_id,
        )
        self.assertNotEqual(
            assignments[0].orientation.type_id,
            assignments[2].orientation.type_id,
        )
        self.assertEqual(
            assignments[0].stacking.type_id,
            assignments[2].stacking.type_id,
        )
        self.assertNotEqual(
            assignments[0].stacking.type_id,
            assignments[3].stacking.type_id,
        )

    def test_missing_orientation_is_not_replaced_with_zero_degrees(
        self,
    ) -> None:
        hierarchy = _hierarchy(
            _domain_frame(
                0,
                orientation_angles=(0.0, 60.0),
            ),
            _domain_frame(
                1,
                stacking_pattern="unavailable",
            ),
        )

        result = classify_molecular_order_types(
            hierarchy,
            analysis_scope=_single_scope(0, 1),
            settings=MolecularOrderTypeClassificationSettings(),
        )

        assignments = {
            value.observation_key[3]: value
            for value in result.assignments
        }
        self.assertEqual(assignments[0].orientation.status, "classified")
        self.assertEqual(
            result.orientation_types[0].prototype_angles_deg,
            (0.0, 60.0),
        )
        self.assertEqual(assignments[1].orientation.status, "unclassified")
        self.assertEqual(
            assignments[1].orientation.unclassified_reason,
            "orientation_features_unavailable",
        )
        self.assertEqual(assignments[1].stacking.status, "unclassified")
        self.assertEqual(
            assignments[1].stacking.unclassified_reason,
            "stacking_result_unavailable",
        )

    def test_missing_m3_angle_is_not_replaced_with_zero_degrees(self) -> None:
        hierarchy = _hierarchy(
            _domain_frame(0, theta3_deg=0.0),
            _domain_frame(
                1,
                symmetry="sixfold",
                theta3_deg=None,
                theta6_deg=0.0,
            ),
        )

        result = classify_molecular_order_types(
            hierarchy,
            analysis_scope=_single_scope(0, 1),
            settings=MolecularOrderTypeClassificationSettings(
                geometry_features=("theta3_lattice",),
            ),
        )

        assignments = {
            value.observation_key[3]: value
            for value in result.assignments
        }
        self.assertEqual(assignments[0].geometry.status, "classified")
        self.assertEqual(
            result.geometry_types[0].prototype_theta3_lattice_deg,
            0.0,
        )
        self.assertEqual(assignments[1].geometry.status, "unclassified")
        self.assertEqual(
            assignments[1].geometry.unclassified_reason,
            "geometry_features_unavailable",
        )

    def test_selected_stacking_mode_can_split_one_pattern(self) -> None:
        hierarchy = _hierarchy(
            _domain_frame(0, stacking_mode="checkerboard"),
            _domain_frame(1, stacking_mode="along_rows"),
        )
        scope = _single_scope(0, 1)

        pattern_only = classify_molecular_order_types(
            hierarchy,
            analysis_scope=scope,
            settings=MolecularOrderTypeClassificationSettings(
                stacking_features=("pattern",),
            ),
        )
        pattern_and_mode = classify_molecular_order_types(
            hierarchy,
            analysis_scope=scope,
            settings=MolecularOrderTypeClassificationSettings(
                stacking_features=("pattern", "mode"),
            ),
        )

        self.assertEqual(len(pattern_only.stacking_types), 1)
        self.assertEqual(len(pattern_and_mode.stacking_types), 2)

    def test_letter_labels_follow_prototypes_not_frame_identity(self) -> None:
        settings = MolecularOrderTypeClassificationSettings(
            lattice_orientation_tolerance_deg=1.0,
        )
        first = classify_molecular_order_types(
            _hierarchy(
                _domain_frame(0, theta3_deg=20.0),
                _domain_frame(1, theta3_deg=2.0),
            ),
            analysis_scope=_single_scope(0, 1),
            settings=settings,
        )
        second = classify_molecular_order_types(
            _hierarchy(
                _domain_frame(0, theta3_deg=2.0),
                _domain_frame(1, theta3_deg=20.0),
            ),
            analysis_scope=_single_scope(0, 1),
            settings=settings,
        )

        first_prototypes = tuple(
            (value.label, value.prototype_theta3_lattice_deg)
            for value in first.geometry_types
        )
        second_prototypes = tuple(
            (value.label, value.prototype_theta3_lattice_deg)
            for value in second.geometry_types
        )
        self.assertEqual(first_prototypes, second_prototypes)
        self.assertEqual(
            first_prototypes,
            (("A", 2.0), ("B", 20.0)),
        )

    def test_settings_round_trip_and_reject_empty_feature_layers(
        self,
    ) -> None:
        settings = MolecularOrderTypeClassificationSettings(
            geometry_features=("theta3_lattice", "dominant_symmetry"),
            stacking_features=("mode", "pattern"),
            minimum_observations_per_type=2,
        )

        self.assertEqual(
            settings.geometry_features,
            ("dominant_symmetry", "theta3_lattice"),
        )
        self.assertEqual(
            settings.stacking_features,
            ("pattern", "mode"),
        )
        self.assertEqual(
            MolecularOrderTypeClassificationSettings.from_dict(
                settings.to_dict()
            ),
            settings,
        )
        with self.assertRaisesRegex(ValueError, "geometry_features"):
            MolecularOrderTypeClassificationSettings(
                geometry_features=(),
            )
        with self.assertRaisesRegex(ValueError, "include mode"):
            MolecularOrderTypeClassificationSettings(
                stacking_features=("pattern", "phase"),
            )

    def test_result_fingerprint_is_deterministic_and_guards_observations(
        self,
    ) -> None:
        hierarchy = _hierarchy(_domain_frame(0))
        scope = _single_scope(0, 0)
        settings = MolecularOrderTypeClassificationSettings()

        first = classify_molecular_order_types(
            hierarchy,
            analysis_scope=scope,
            settings=settings,
        )
        second = classify_molecular_order_types(
            hierarchy,
            analysis_scope=scope,
            settings=settings,
        )

        self.assertEqual(
            molecular_order_type_classification_fingerprint(first),
            molecular_order_type_classification_fingerprint(second),
        )
        with self.assertRaisesRegex(ValueError, "input_fingerprint"):
            replace(first, input_fingerprint="c" * 64)


if __name__ == "__main__":
    unittest.main()
