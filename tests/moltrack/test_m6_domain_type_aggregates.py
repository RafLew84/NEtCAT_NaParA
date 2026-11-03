from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from moltrack.analysis import (
    M6DomainTypeClassificationSettings,
    M6DomainTypeObservation,
    M6DomainTypeRangeAggregate,
    MolecularFrameRange,
    MolecularFrameRangeAnalysis,
    MolecularFrameRangeAnalysisScope,
    MolecularM6OrientationAnalysisSettings,
    aggregate_m6_domain_types_for_range,
    classify_m6_domain_types,
)
from moltrack.analysis._m6_context_fingerprint import m6_context_fingerprint
from moltrack.analysis._m6_settings_fingerprint import m6_settings_fingerprint
from moltrack.analysis.molecular_m6_analysis import MolecularM6OrientationAnalysis


def _m6_settings() -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings()


def _m6_analysis(
    *,
    valid_representative_count: int,
    valid_fov_area_nm2: float,
    spatial_calibration_fingerprint: str = "calibration-v1",
) -> MolecularM6OrientationAnalysis:
    analysis = Mock(spec=MolecularM6OrientationAnalysis)
    analysis.source_view = "raw"
    analysis.coordinate_frame = "sample_nm"
    analysis.orientation_reference = "+x_sample_axis"
    analysis.spatial_calibration_fingerprint = spatial_calibration_fingerprint
    analysis.settings = _m6_settings()
    analysis.frame_aggregates = SimpleNamespace(
        valid_representative_count=valid_representative_count,
        valid_fov_area_nm2=valid_fov_area_nm2,
    )
    return analysis


M6_CONTEXT = m6_context_fingerprint(
    _m6_analysis(valid_representative_count=1, valid_fov_area_nm2=1.0)
)


def _observation(
    frame_index: int,
    component_id: int,
    orientation_deg: float,
    bond_length_nm: float | None,
    *,
    range_name: str,
    range_bounds: tuple[int, int],
    molecule_count: int,
    molecule_fraction: float,
    footprint_area_nm2: float,
    footprint_fraction: float | None,
    coherent_q6: float,
    qualification_status: str = "qualified",
    unclassified_reason: str | None = None,
) -> M6DomainTypeObservation:
    statistics_missing = bond_length_nm is None
    return M6DomainTypeObservation(
        range_name=range_name,
        range_start_frame=range_bounds[0],
        range_end_frame=range_bounds[1],
        source_view="raw",
        m6_settings_fingerprint=m6_settings_fingerprint(_m6_settings()),
        m6_context_fingerprint=M6_CONTEXT,
        frame_index=frame_index,
        source_frame_index=frame_index + 100,
        ordered_component_id=component_id,
        m6_orientation_domain_id=component_id,
        component_type="full_domain",
        qualification_status=qualification_status,
        unclassified_reason=unclassified_reason,
        orientation_deg=orientation_deg,
        molecule_count=molecule_count,
        molecule_fraction_of_valid_representatives=molecule_fraction,
        footprint_area_nm2=footprint_area_nm2,
        footprint_fraction_of_valid_fov=footprint_fraction,
        molecular_mask_area_nm2=footprint_area_nm2 / 2.0,
        domain_mean_local_q6=min(1.0, coherent_q6 + 0.1),
        domain_coherent_q6=coherent_q6,
        centroid_x_nm=float(component_id + 1),
        centroid_y_nm=float(frame_index + 1),
        min_x_nm=float(component_id),
        min_y_nm=float(frame_index),
        max_x_nm=float(component_id + 2),
        max_y_nm=float(frame_index + 2),
        internal_first_shell_bond_count=30,
        domain_median_bond_length_nm=bond_length_nm,
        domain_bond_length_mad_nm=None if statistics_missing else 0.1,
        domain_bond_length_iqr_nm=None if statistics_missing else 0.2,
        domain_bond_length_robust_cv=None if statistics_missing else 0.05,
        insufficient_bonds_for_length_stats_qc=statistics_missing,
        bond_length_heterogeneity_qc=False,
        edge_truncated=False,
        footprint_disconnected_qc=False,
    )


def _scope() -> MolecularFrameRangeAnalysisScope:
    return MolecularFrameRangeAnalysisScope(
        analysis_mode="compare_ranges",
        frame_count=6,
        source_view="raw",
        ranges=(
            MolecularFrameRange("before", 0, 3),
            MolecularFrameRange("after", 4, 5),
        ),
    )


def _classification():
    before = {"range_name": "before", "range_bounds": (0, 3)}
    after = {"range_name": "after", "range_bounds": (4, 5)}
    observations = (
        _observation(0, 0, 1.0, 2.0, molecule_count=10, molecule_fraction=0.2,
                     footprint_area_nm2=20.0, footprint_fraction=0.1,
                     coherent_q6=0.6, **before),
        _observation(1, 0, 2.0, 2.1, molecule_count=20, molecule_fraction=0.3,
                     footprint_area_nm2=30.0, footprint_fraction=None,
                     coherent_q6=0.7, **before),
        _observation(2, 0, 3.0, 2.2, molecule_count=30, molecule_fraction=0.4,
                     footprint_area_nm2=40.0, footprint_fraction=0.2,
                     coherent_q6=0.8, **before),
        _observation(2, 1, 20.0, 4.0, molecule_count=8, molecule_fraction=0.2,
                     footprint_area_nm2=10.0, footprint_fraction=0.2,
                     coherent_q6=0.5, **before),
        _observation(2, 2, 21.0, 4.1, molecule_count=12, molecule_fraction=0.3,
                     footprint_area_nm2=14.0, footprint_fraction=0.3,
                     coherent_q6=0.7, **before),
        _observation(
            1,
            3,
            30.0,
            None,
            molecule_count=5,
            molecule_fraction=0.1,
            footprint_area_nm2=6.0,
            footprint_fraction=None,
            coherent_q6=0.4,
            qualification_status="unclassified",
            unclassified_reason="missing_bond_length_statistics",
            **before,
        ),
        _observation(4, 0, 40.0, 6.0, molecule_count=9, molecule_fraction=0.2,
                     footprint_area_nm2=16.0, footprint_fraction=0.1,
                     coherent_q6=0.6, **after),
        _observation(5, 0, 41.0, 6.1, molecule_count=11, molecule_fraction=0.3,
                     footprint_area_nm2=18.0, footprint_fraction=0.2,
                     coherent_q6=0.8, **after),
    )
    return classify_m6_domain_types(
        reversed(observations),
        analysis_scope=_scope(),
        classification_settings=M6DomainTypeClassificationSettings(
            orientation_tolerance_deg=5.0,
            bond_length_tolerance_mode="absolute_nm",
            bond_length_tolerance_value=0.5,
            minimum_observations_per_type=2,
        ),
        m6_settings=_m6_settings(),
        m6_context_fingerprint=M6_CONTEXT,
    )


def _range_analysis() -> MolecularFrameRangeAnalysis:
    frame_results = (
        _frame_result(0, valid_representative_count=10, valid_fov_area_nm2=100.0),
        _frame_result(1, valid_representative_count=10, valid_fov_area_nm2=0.0),
        _frame_result(2, valid_representative_count=20, valid_fov_area_nm2=100.0),
        SimpleNamespace(
            frame_index=3,
            source_view="raw",
            m6_orientation_availability_status="unavailable_blocking_graph_qc",
            m6_orientation_analysis=None,
        ),
    )
    return MolecularFrameRangeAnalysis(
        frame_range=MolecularFrameRange("before", 0, 3),
        source_view="raw",
        frame_results=frame_results,
        aggregates=None,
        intensity_metric="background_corrected_median",
        intensity_unit="a.u.",
    )


def _after_range_analysis() -> MolecularFrameRangeAnalysis:
    return MolecularFrameRangeAnalysis(
        frame_range=MolecularFrameRange("after", 4, 5),
        source_view="raw",
        frame_results=(
            _frame_result(
                4,
                valid_representative_count=10,
                valid_fov_area_nm2=100.0,
            ),
            _frame_result(
                5,
                valid_representative_count=10,
                valid_fov_area_nm2=100.0,
            ),
        ),
        aggregates=None,
        intensity_metric="background_corrected_median",
        intensity_unit="a.u.",
    )


def _frame_result(
    frame_index: int,
    *,
    valid_representative_count: int,
    valid_fov_area_nm2: float,
):
    return SimpleNamespace(
        frame_index=frame_index,
        source_view="raw",
        m6_orientation_availability_status="available",
        m6_orientation_analysis=_m6_analysis(
            valid_representative_count=valid_representative_count,
            valid_fov_area_nm2=valid_fov_area_nm2,
        ),
    )


class M6DomainTypeRangeAggregateTests(unittest.TestCase):
    def test_aggregates_all_partial_absent_and_unclassified_types(self) -> None:
        result = aggregate_m6_domain_types_for_range(
            _classification(),
            _range_analysis(),
        )

        self.assertEqual(result.analyzed_frame_count, 4)
        self.assertEqual(result.available_frame_count, 3)
        self.assertEqual(result.valid_representative_fraction_frame_count, 3)
        self.assertEqual(result.valid_fov_fraction_frame_count, 2)
        self.assertEqual(
            tuple(item.label for item in result.type_aggregates),
            ("A", "B", "C"),
        )

        all_frames, partial, absent = result.type_aggregates
        self.assertEqual(all_frames.observation_count, 3)
        self.assertEqual(all_frames.frames_with_type_count, 3)
        self.assertEqual(all_frames.mean_instances_per_available_frame, 1.0)
        self.assertAlmostEqual(
            all_frames.mean_molecule_fraction_of_valid_representatives,
            0.3,
        )
        self.assertAlmostEqual(
            all_frames.mean_footprint_fraction_of_valid_fov,
            0.15,
        )
        self.assertAlmostEqual(all_frames.mean_domain_coherent_q6, 0.7)
        self.assertEqual(all_frames.mean_molecule_count, 20.0)
        self.assertEqual(all_frames.mean_footprint_area_nm2, 30.0)

        self.assertEqual(partial.observation_count, 2)
        self.assertEqual(partial.frames_with_type_count, 1)
        self.assertAlmostEqual(
            partial.mean_instances_per_available_frame,
            2.0 / 3.0,
        )
        self.assertAlmostEqual(
            partial.mean_molecule_fraction_of_valid_representatives,
            0.5 / 3.0,
        )
        self.assertAlmostEqual(
            partial.mean_footprint_fraction_of_valid_fov,
            0.25,
        )
        self.assertAlmostEqual(partial.mean_domain_coherent_q6, 0.6)
        self.assertEqual(partial.mean_molecule_count, 10.0)
        self.assertEqual(partial.mean_footprint_area_nm2, 12.0)

        self.assertEqual(absent.observation_count, 0)
        self.assertEqual(absent.frames_with_type_count, 0)
        self.assertEqual(absent.mean_instances_per_available_frame, 0.0)
        self.assertEqual(
            absent.mean_molecule_fraction_of_valid_representatives,
            0.0,
        )
        self.assertEqual(absent.mean_footprint_fraction_of_valid_fov, 0.0)
        self.assertIsNone(absent.mean_domain_coherent_q6)
        self.assertIsNone(absent.mean_molecule_count)
        self.assertIsNone(absent.mean_footprint_area_nm2)

        unclassified = result.unclassified_aggregate
        self.assertEqual(unclassified.label, "Unclassified")
        self.assertIsNone(unclassified.domain_type_id)
        self.assertEqual(unclassified.observation_count, 1)
        self.assertEqual(unclassified.frames_with_type_count, 1)
        self.assertAlmostEqual(
            unclassified.mean_instances_per_available_frame,
            1.0 / 3.0,
        )
        self.assertAlmostEqual(
            unclassified.mean_molecule_fraction_of_valid_representatives,
            0.1 / 3.0,
        )
        self.assertEqual(unclassified.mean_footprint_fraction_of_valid_fov, 0.0)
        self.assertEqual(unclassified.mean_domain_coherent_q6, 0.4)
        self.assertEqual(unclassified.mean_molecule_count, 5.0)
        self.assertEqual(unclassified.mean_footprint_area_nm2, 6.0)

    def test_excludes_unavailable_frames_and_rejects_mismatched_range(self) -> None:
        result = aggregate_m6_domain_types_for_range(
            _classification(),
            _range_analysis(),
        )

        self.assertEqual(result.type_aggregates[0].mean_instances_per_available_frame, 1.0)
        mismatched = _range_analysis()
        mismatched = MolecularFrameRangeAnalysis(
            frame_range=MolecularFrameRange("other", 0, 3),
            source_view=mismatched.source_view,
            frame_results=mismatched.frame_results,
            aggregates=mismatched.aggregates,
            intensity_metric=mismatched.intensity_metric,
            intensity_unit=mismatched.intensity_unit,
        )
        with self.assertRaisesRegex(ValueError, "classification scope"):
            aggregate_m6_domain_types_for_range(_classification(), mismatched)

    def test_frame_normalization_is_comparable_across_different_range_lengths(self) -> None:
        classification = _classification()

        before = aggregate_m6_domain_types_for_range(
            classification,
            _range_analysis(),
        )
        after = aggregate_m6_domain_types_for_range(
            classification,
            _after_range_analysis(),
        )

        before_type = before.type_aggregates[0]
        after_type = after.type_aggregates[2]
        self.assertEqual(before_type.observation_count, 3)
        self.assertEqual(after_type.observation_count, 2)
        self.assertEqual(before_type.mean_instances_per_available_frame, 1.0)
        self.assertEqual(after_type.mean_instances_per_available_frame, 1.0)

    def test_rejects_foreign_m6_context(self) -> None:
        range_analysis = _range_analysis()
        range_analysis.frame_results[
            0
        ].m6_orientation_analysis.spatial_calibration_fingerprint = "foreign"

        with self.assertRaisesRegex(ValueError, "M6 context"):
            aggregate_m6_domain_types_for_range(
                _classification(),
                range_analysis,
            )

    def test_public_row_rejects_nonzero_fractions_without_observations(self) -> None:
        with self.assertRaisesRegex(ValueError, "absent type"):
            M6DomainTypeRangeAggregate(
                domain_type_id=0,
                label="A",
                available_frame_count=1,
                valid_representative_fraction_frame_count=1,
                valid_fov_fraction_frame_count=1,
                observation_count=0,
                frames_with_type_count=0,
                mean_instances_per_available_frame=0.0,
                mean_molecule_fraction_of_valid_representatives=0.1,
                mean_footprint_fraction_of_valid_fov=0.2,
                mean_domain_coherent_q6=None,
                mean_molecule_count=None,
                mean_footprint_area_nm2=None,
            )

    def test_zero_available_frames_produce_undefined_means(self) -> None:
        classification = classify_m6_domain_types(
            (),
            analysis_scope=_scope(),
            classification_settings=M6DomainTypeClassificationSettings(),
            m6_settings=_m6_settings(),
            m6_context_fingerprint=M6_CONTEXT,
        )
        unavailable_results = tuple(
            SimpleNamespace(
                frame_index=frame_index,
                source_view="raw",
                m6_orientation_availability_status=(
                    "unavailable_blocking_graph_qc"
                ),
                m6_orientation_analysis=None,
            )
            for frame_index in range(4)
        )
        range_analysis = MolecularFrameRangeAnalysis(
            frame_range=MolecularFrameRange("before", 0, 3),
            source_view="raw",
            frame_results=unavailable_results,
            aggregates=None,
            intensity_metric="background_corrected_median",
            intensity_unit="a.u.",
        )

        result = aggregate_m6_domain_types_for_range(
            classification,
            range_analysis,
        )

        self.assertEqual(result.available_frame_count, 0)
        self.assertEqual(result.type_aggregates, ())
        self.assertIsNone(
            result.unclassified_aggregate.mean_instances_per_available_frame
        )
        self.assertIsNone(
            result.unclassified_aggregate.mean_molecule_fraction_of_valid_representatives
        )
        self.assertIsNone(
            result.unclassified_aggregate.mean_footprint_fraction_of_valid_fov
        )


if __name__ == "__main__":
    unittest.main()
