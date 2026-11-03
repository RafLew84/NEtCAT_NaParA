from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from moltrack.analysis import (
    M6DomainTypeClassificationSettings,
    M6DomainTypeObservation,
    MolecularFrameRange,
    MolecularFrameRangeAnalysis,
    MolecularFrameRangeAnalysisScope,
    MolecularM6OrientationAnalysisSettings,
    build_m6_single_range_domain_type_summary,
    classify_m6_domain_types,
)
from moltrack.analysis._m6_context_fingerprint import m6_context_fingerprint
from moltrack.analysis._m6_settings_fingerprint import m6_settings_fingerprint
from moltrack.analysis.molecular_m6_analysis import MolecularM6OrientationAnalysis


def _m6_settings() -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings()


def _m6_analysis(
    *,
    full_domain_count: int,
    full_domain_molecule_fraction: float,
    full_domain_footprint_fraction: float | None,
    valid_fov_area_nm2: float = 100.0,
) -> MolecularM6OrientationAnalysis:
    analysis = Mock(spec=MolecularM6OrientationAnalysis)
    analysis.source_view = "raw"
    analysis.coordinate_frame = "sample_nm"
    analysis.orientation_reference = "+x_sample_axis"
    analysis.spatial_calibration_fingerprint = "calibration-v1"
    analysis.settings = _m6_settings()
    analysis.frame_aggregates = SimpleNamespace(
        valid_representative_count=10,
        valid_fov_area_nm2=valid_fov_area_nm2,
        full_domain_count=full_domain_count,
        full_domain_molecule_fraction=full_domain_molecule_fraction,
        full_domain_footprint_fraction=full_domain_footprint_fraction,
    )
    return analysis


M6_CONTEXT = m6_context_fingerprint(
    _m6_analysis(
        full_domain_count=0,
        full_domain_molecule_fraction=0.0,
        full_domain_footprint_fraction=0.0,
    )
)


def _observation(
    frame_index: int,
    component_id: int,
    orientation_deg: float,
    bond_length_nm: float | None,
    *,
    range_end: int,
    molecule_fraction: float,
    footprint_fraction: float | None,
    component_type: str = "full_domain",
    qualification_status: str = "qualified",
    unclassified_reason: str | None = None,
) -> M6DomainTypeObservation:
    missing_statistics = bond_length_nm is None
    return M6DomainTypeObservation(
        range_name="condition",
        range_start_frame=0,
        range_end_frame=range_end,
        source_view="raw",
        m6_settings_fingerprint=m6_settings_fingerprint(_m6_settings()),
        m6_context_fingerprint=M6_CONTEXT,
        frame_index=frame_index,
        source_frame_index=frame_index + 100,
        ordered_component_id=component_id,
        m6_orientation_domain_id=(
            component_id if component_type == "full_domain" else None
        ),
        component_type=component_type,
        qualification_status=qualification_status,
        unclassified_reason=unclassified_reason,
        orientation_deg=orientation_deg,
        molecule_count=10 + component_id,
        molecule_fraction_of_valid_representatives=molecule_fraction,
        footprint_area_nm2=20.0 + component_id,
        footprint_fraction_of_valid_fov=footprint_fraction,
        molecular_mask_area_nm2=10.0,
        domain_mean_local_q6=0.8,
        domain_coherent_q6=0.7,
        centroid_x_nm=float(component_id + 1),
        centroid_y_nm=float(frame_index + 1),
        min_x_nm=float(component_id),
        min_y_nm=float(frame_index),
        max_x_nm=float(component_id + 2),
        max_y_nm=float(frame_index + 2),
        internal_first_shell_bond_count=30,
        domain_median_bond_length_nm=bond_length_nm,
        domain_bond_length_mad_nm=None if missing_statistics else 0.1,
        domain_bond_length_iqr_nm=None if missing_statistics else 0.2,
        domain_bond_length_robust_cv=None if missing_statistics else 0.05,
        insufficient_bonds_for_length_stats_qc=missing_statistics,
        bond_length_heterogeneity_qc=False,
        edge_truncated=False,
        footprint_disconnected_qc=False,
    )


def _classification(
    observations,
    *,
    frame_count: int,
    include_small_ordered_islands: bool = False,
):
    return classify_m6_domain_types(
        observations,
        analysis_scope=MolecularFrameRangeAnalysisScope(
            analysis_mode="single_range",
            frame_count=frame_count,
            source_view="raw",
            ranges=(MolecularFrameRange("condition", 0, frame_count - 1),),
        ),
        classification_settings=M6DomainTypeClassificationSettings(
            orientation_tolerance_deg=5.0,
            bond_length_tolerance_mode="absolute_nm",
            bond_length_tolerance_value=0.5,
            minimum_observations_per_type=2,
            include_small_ordered_islands=include_small_ordered_islands,
        ),
        m6_settings=_m6_settings(),
        m6_context_fingerprint=M6_CONTEXT,
    )


def _range_analysis(
    frame_specs: tuple[tuple[int, float, float | None] | None, ...],
) -> MolecularFrameRangeAnalysis:
    frame_results = []
    for frame_index, spec in enumerate(frame_specs):
        if spec is None:
            frame_results.append(
                SimpleNamespace(
                    frame_index=frame_index,
                    source_frame_index=frame_index + 100,
                    source_view="raw",
                    m6_orientation_availability_status=(
                        "unavailable_blocking_graph_qc"
                    ),
                    m6_orientation_unavailability_reason=(
                        "blocking_rank2_radius_fallback"
                    ),
                    m6_orientation_analysis=None,
                )
            )
            continue
        domain_count, molecule_fraction, footprint_fraction = spec
        valid_fov_area = 0.0 if footprint_fraction is None else 100.0
        frame_results.append(
            SimpleNamespace(
                frame_index=frame_index,
                source_frame_index=frame_index + 100,
                source_view="raw",
                m6_orientation_availability_status="available",
                m6_orientation_unavailability_reason=None,
                m6_orientation_analysis=_m6_analysis(
                    full_domain_count=domain_count,
                    full_domain_molecule_fraction=molecule_fraction,
                    full_domain_footprint_fraction=footprint_fraction,
                    valid_fov_area_nm2=valid_fov_area,
                ),
            )
        )
    return MolecularFrameRangeAnalysis(
        frame_range=MolecularFrameRange("condition", 0, len(frame_specs) - 1),
        source_view="raw",
        frame_results=tuple(frame_results),
        aggregates=None,
        intensity_metric="background_corrected_median",
        intensity_unit="a.u.",
    )


class M6SingleRangeDomainTypeSummaryTests(unittest.TestCase):
    def test_one_structure_on_ten_frames_has_distinct_counts(self) -> None:
        observations = tuple(
            _observation(
                frame_index,
                0,
                1.0,
                2.0,
                range_end=9,
                molecule_fraction=0.2,
                footprint_fraction=0.1,
            )
            for frame_index in range(10)
        )

        result = build_m6_single_range_domain_type_summary(
            _classification(observations, frame_count=10),
            _range_analysis(((1, 0.2, 0.1),) * 10),
        )

        self.assertEqual(result.domain_observation_count, 10)
        self.assertEqual(result.mean_full_domains_per_available_frame, 1.0)
        self.assertEqual(result.domain_type_count, 1)
        self.assertEqual(result.frames_with_full_domain_count, 10)
        self.assertEqual(result.frames_with_full_domain_percent, 100.0)
        self.assertEqual(result.median_full_domains_per_available_frame, 1.0)
        self.assertEqual(result.max_full_domains_per_available_frame, 1)
        self.assertEqual(result.full_domain_molecule_fraction, 0.2)
        self.assertEqual(result.full_domain_footprint_fraction, 0.1)
        self.assertEqual(
            tuple(
                (item.working_frame_index, item.source_frame_index)
                for item in result.frame_mapping
            ),
            tuple((index, index + 100) for index in range(10)),
        )
        row = result.type_summaries[0]
        self.assertEqual(row.label, "A")
        self.assertEqual(row.observation_count, 10)
        self.assertEqual(row.frames_with_type_count, 10)
        self.assertEqual(row.frames_with_type_percent, 100.0)
        self.assertEqual(row.mean_instances_per_available_frame, 1.0)
        self.assertAlmostEqual(row.prototype_orientation_deg, 1.0)
        self.assertEqual(row.prototype_bond_length_nm, 2.0)
        self.assertFalse(result.uses_tracking)

    def test_sporadic_types_and_unavailable_frame_use_correct_denominators(
        self,
    ) -> None:
        observations = (
            _observation(0, 0, 1.0, 2.0, range_end=3,
                         molecule_fraction=0.2, footprint_fraction=0.1),
            _observation(1, 0, 2.0, 2.1, range_end=3,
                         molecule_fraction=0.3, footprint_fraction=None),
            _observation(2, 1, 20.0, 4.0, range_end=3,
                         molecule_fraction=0.2, footprint_fraction=0.2),
            _observation(2, 2, 21.0, 4.1, range_end=3,
                         molecule_fraction=0.3, footprint_fraction=0.3),
            _observation(
                1,
                3,
                30.0,
                None,
                range_end=3,
                molecule_fraction=0.1,
                footprint_fraction=None,
                qualification_status="unclassified",
                unclassified_reason="missing_bond_length_statistics",
            ),
        )

        result = build_m6_single_range_domain_type_summary(
            _classification(observations, frame_count=4),
            _range_analysis(
                (
                    (1, 0.2, 0.1),
                    (2, 0.4, None),
                    (2, 0.5, 0.5),
                    None,
                )
            ),
        )

        self.assertEqual(result.analyzed_frame_count, 4)
        self.assertEqual(result.available_frame_count, 3)
        self.assertEqual(result.frames_with_full_domain_count, 3)
        self.assertEqual(result.domain_observation_count, 5)
        self.assertEqual(result.domain_type_count, 2)
        self.assertEqual(result.unclassified_observation_count, 1)
        self.assertEqual(result.unclassified_aggregate.observation_count, 1)
        self.assertAlmostEqual(
            result.unclassified_aggregate.mean_instances_per_available_frame,
            1.0 / 3.0,
        )
        self.assertAlmostEqual(
            result.unclassified_aggregate.mean_molecule_fraction_of_valid_representatives,
            0.1 / 3.0,
        )
        self.assertEqual(
            result.unclassified_aggregate.mean_footprint_fraction_of_valid_fov,
            0.0,
        )
        self.assertAlmostEqual(
            result.mean_full_domains_per_available_frame,
            5.0 / 3.0,
        )
        self.assertEqual(result.median_full_domains_per_available_frame, 2.0)
        self.assertEqual(result.max_full_domains_per_available_frame, 2)
        self.assertAlmostEqual(
            result.full_domain_molecule_fraction,
            (0.2 + 0.4 + 0.5) / 3.0,
        )
        self.assertEqual(result.full_domain_footprint_fraction, 0.3)
        self.assertEqual(
            tuple(row.frames_with_type_count for row in result.type_summaries),
            (2, 1),
        )
        self.assertAlmostEqual(result.type_summaries[0].frames_with_type_percent,
                               200.0 / 3.0)
        self.assertAlmostEqual(result.type_summaries[1].frames_with_type_percent,
                               100.0 / 3.0)
        self.assertEqual(
            result.frame_mapping[-1].m6_availability_status,
            "unavailable_blocking_graph_qc",
        )

    def test_range_without_domains_reports_zero_without_inventing_a_condition(self) -> None:
        result = build_m6_single_range_domain_type_summary(
            _classification((), frame_count=3),
            _range_analysis(((0, 0.0, 0.0),) * 3),
        )

        self.assertEqual(result.range_name, "condition")
        self.assertEqual(result.analyzed_frame_count, 3)
        self.assertEqual(result.available_frame_count, 3)
        self.assertEqual(result.frames_with_full_domain_count, 0)
        self.assertEqual(result.frames_with_full_domain_percent, 0.0)
        self.assertEqual(result.mean_full_domains_per_available_frame, 0.0)
        self.assertEqual(result.median_full_domains_per_available_frame, 0.0)
        self.assertEqual(result.max_full_domains_per_available_frame, 0)
        self.assertEqual(result.domain_observation_count, 0)
        self.assertEqual(result.domain_type_count, 0)
        self.assertEqual(result.unclassified_observation_count, 0)
        self.assertEqual(result.full_domain_molecule_fraction, 0.0)
        self.assertEqual(result.full_domain_footprint_fraction, 0.0)
        self.assertEqual(result.type_summaries, ())
        self.assertEqual(result.analysis_mode, "single_range_structural_domain_type_summary")

        with self.assertRaisesRegex(ValueError, "counters"):
            replace(result, domain_observation_count=1)

    def test_summary_excludes_small_ordered_islands_in_both_setting_modes(self) -> None:
        for include_small_islands in (False, True):
            observations = tuple(
                _observation(
                    frame_index,
                    frame_index,
                    20.0,
                    4.0,
                    range_end=1,
                    molecule_fraction=0.2,
                    footprint_fraction=0.1,
                    component_type="small_ordered_island",
                    qualification_status=(
                        "qualified" if include_small_islands else "unclassified"
                    ),
                    unclassified_reason=(
                        None
                        if include_small_islands
                        else "small_ordered_island_excluded"
                    ),
                )
                for frame_index in range(2)
            )
            with self.subTest(include_small_islands=include_small_islands):
                result = build_m6_single_range_domain_type_summary(
                    _classification(
                        observations,
                        frame_count=2,
                        include_small_ordered_islands=include_small_islands,
                    ),
                    _range_analysis(((0, 0.0, 0.0),) * 2),
                )

                self.assertEqual(result.domain_observation_count, 0)
                self.assertEqual(result.domain_type_count, 0)
                self.assertEqual(result.unclassified_observation_count, 0)
                self.assertEqual(result.type_summaries, ())

    def test_rejects_per_frame_count_and_source_mapping_mismatches(self) -> None:
        observations = (
            _observation(0, 0, 1.0, 2.0, range_end=1,
                         molecule_fraction=0.2, footprint_fraction=0.1),
            _observation(1, 0, 2.0, 2.1, range_end=1,
                         molecule_fraction=0.2, footprint_fraction=0.1),
        )
        classification = _classification(observations, frame_count=2)

        with self.assertRaisesRegex(ValueError, "per-frame"):
            build_m6_single_range_domain_type_summary(
                classification,
                _range_analysis(((2, 0.4, 0.2), (0, 0.0, 0.0))),
            )

        source_mismatch = _range_analysis(((1, 0.2, 0.1),) * 2)
        source_mismatch.frame_results[1].source_frame_index = 999
        with self.assertRaisesRegex(ValueError, "source frame"):
            build_m6_single_range_domain_type_summary(
                classification,
                source_mismatch,
            )


if __name__ == "__main__":
    unittest.main()
