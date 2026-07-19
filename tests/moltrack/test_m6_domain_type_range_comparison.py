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
    build_m6_domain_type_range_comparison,
    classify_m6_domain_types,
)
from moltrack.analysis._m6_context_fingerprint import m6_context_fingerprint
from moltrack.analysis._m6_settings_fingerprint import m6_settings_fingerprint
from moltrack.analysis.molecular_m6_analysis import MolecularM6OrientationAnalysis


BEFORE = MolecularFrameRange("before desorption", 0, 2)
AFTER = MolecularFrameRange("after adsorption", 3, 6)


def _m6_settings() -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings()


def _m6_analysis(
    *,
    full_domain_count: int,
    full_domain_molecule_fraction: float,
    full_domain_footprint_fraction: float,
) -> MolecularM6OrientationAnalysis:
    analysis = Mock(spec=MolecularM6OrientationAnalysis)
    analysis.source_view = "raw"
    analysis.coordinate_frame = "sample_nm"
    analysis.orientation_reference = "+x_sample_axis"
    analysis.spatial_calibration_fingerprint = "calibration-v1"
    analysis.settings = _m6_settings()
    analysis.frame_aggregates = SimpleNamespace(
        valid_representative_count=20,
        valid_fov_area_nm2=100.0,
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
    local_domain_id: int,
    orientation_deg: float,
    bond_length_nm: float,
    *,
    frame_range: MolecularFrameRange,
    molecule_count: int,
    molecule_fraction: float,
    footprint_area_nm2: float,
    footprint_fraction: float,
    coherent_q6: float,
) -> M6DomainTypeObservation:
    return M6DomainTypeObservation(
        range_name=frame_range.name,
        range_start_frame=frame_range.start_frame,
        range_end_frame=frame_range.end_frame,
        source_view="raw",
        m6_settings_fingerprint=m6_settings_fingerprint(_m6_settings()),
        m6_context_fingerprint=M6_CONTEXT,
        frame_index=frame_index,
        source_frame_index=frame_index + 100,
        ordered_component_id=local_domain_id,
        m6_orientation_domain_id=local_domain_id,
        component_type="full_domain",
        qualification_status="qualified",
        unclassified_reason=None,
        orientation_deg=orientation_deg,
        molecule_count=molecule_count,
        molecule_fraction_of_valid_representatives=molecule_fraction,
        footprint_area_nm2=footprint_area_nm2,
        footprint_fraction_of_valid_fov=footprint_fraction,
        molecular_mask_area_nm2=footprint_area_nm2 / 2.0,
        domain_mean_local_q6=min(1.0, coherent_q6 + 0.1),
        domain_coherent_q6=coherent_q6,
        centroid_x_nm=float(local_domain_id),
        centroid_y_nm=float(frame_index),
        min_x_nm=float(local_domain_id - 1),
        min_y_nm=float(frame_index - 1),
        max_x_nm=float(local_domain_id + 1),
        max_y_nm=float(frame_index + 1),
        internal_first_shell_bond_count=30,
        domain_median_bond_length_nm=bond_length_nm,
        domain_bond_length_mad_nm=0.1,
        domain_bond_length_iqr_nm=0.2,
        domain_bond_length_robust_cv=0.05,
        insufficient_bonds_for_length_stats_qc=False,
        bond_length_heterogeneity_qc=False,
        edge_truncated=False,
        footprint_disconnected_qc=False,
    )


def _classification():
    observations = (
        # Type A disappears after the first range.
        _observation(0, 11, 1.0, 2.0, frame_range=BEFORE,
                     molecule_count=10, molecule_fraction=0.2,
                     footprint_area_nm2=10.0, footprint_fraction=0.1,
                     coherent_q6=0.5),
        _observation(1, 12, 2.0, 2.1, frame_range=BEFORE,
                     molecule_count=12, molecule_fraction=0.2,
                     footprint_area_nm2=12.0, footprint_fraction=0.1,
                     coherent_q6=0.6),
        # Type B occurs in both ranges despite unrelated frame-local IDs.
        _observation(2, 31, 20.0, 4.0, frame_range=BEFORE,
                     molecule_count=10, molecule_fraction=0.1,
                     footprint_area_nm2=10.0, footprint_fraction=0.05,
                     coherent_q6=0.6),
        _observation(2, 32, 21.0, 4.1, frame_range=BEFORE,
                     molecule_count=20, molecule_fraction=0.2,
                     footprint_area_nm2=20.0, footprint_fraction=0.1,
                     coherent_q6=0.7),
        _observation(3, 71, 20.5, 4.0, frame_range=AFTER,
                     molecule_count=20, molecule_fraction=0.2,
                     footprint_area_nm2=20.0, footprint_fraction=0.1,
                     coherent_q6=0.7),
        _observation(4, 72, 21.5, 4.1, frame_range=AFTER,
                     molecule_count=30, molecule_fraction=0.2,
                     footprint_area_nm2=30.0, footprint_fraction=0.2,
                     coherent_q6=0.8),
        # Type C appears only after adsorption.
        _observation(3, 91, 40.0, 6.0, frame_range=AFTER,
                     molecule_count=8, molecule_fraction=0.1,
                     footprint_area_nm2=8.0, footprint_fraction=0.05,
                     coherent_q6=0.4),
        _observation(5, 92, 41.0, 6.1, frame_range=AFTER,
                     molecule_count=10, molecule_fraction=0.3,
                     footprint_area_nm2=10.0, footprint_fraction=0.15,
                     coherent_q6=0.5),
    )
    return classify_m6_domain_types(
        observations,
        analysis_scope=MolecularFrameRangeAnalysisScope(
            analysis_mode="compare_ranges",
            frame_count=7,
            source_view="raw",
            ranges=(BEFORE, AFTER),
        ),
        classification_settings=M6DomainTypeClassificationSettings(
            orientation_tolerance_deg=5.0,
            bond_length_tolerance_mode="absolute_nm",
            bond_length_tolerance_value=0.5,
            minimum_observations_per_type=2,
        ),
        m6_settings=_m6_settings(),
        m6_context_fingerprint=M6_CONTEXT,
    )


def _frame_result(
    frame_index: int,
    *,
    full_domain_count: int,
    molecule_fraction: float,
    footprint_fraction: float,
):
    return SimpleNamespace(
        frame_index=frame_index,
        source_frame_index=frame_index + 100,
        source_view="raw",
        m6_orientation_availability_status="available",
        m6_orientation_unavailability_reason=None,
        m6_orientation_analysis=_m6_analysis(
            full_domain_count=full_domain_count,
            full_domain_molecule_fraction=molecule_fraction,
            full_domain_footprint_fraction=footprint_fraction,
        ),
    )


def _range_analysis(frame_range: MolecularFrameRange) -> MolecularFrameRangeAnalysis:
    if frame_range == BEFORE:
        frame_results = (
            _frame_result(0, full_domain_count=1, molecule_fraction=0.2,
                          footprint_fraction=0.1),
            _frame_result(1, full_domain_count=1, molecule_fraction=0.2,
                          footprint_fraction=0.1),
            _frame_result(2, full_domain_count=2, molecule_fraction=0.3,
                          footprint_fraction=0.15),
        )
    else:
        frame_results = (
            _frame_result(3, full_domain_count=2, molecule_fraction=0.3,
                          footprint_fraction=0.15),
            _frame_result(4, full_domain_count=1, molecule_fraction=0.2,
                          footprint_fraction=0.2),
            _frame_result(5, full_domain_count=1, molecule_fraction=0.3,
                          footprint_fraction=0.15),
            SimpleNamespace(
                frame_index=6,
                source_frame_index=106,
                source_view="raw",
                m6_orientation_availability_status=(
                    "unavailable_blocking_graph_qc"
                ),
                m6_orientation_unavailability_reason=(
                    "blocking_rank2_radius_fallback"
                ),
                m6_orientation_analysis=None,
            ),
        )
    return MolecularFrameRangeAnalysis(
        frame_range=frame_range,
        source_view="raw",
        frame_results=frame_results,
        aggregates=None,
        intensity_metric="background_corrected_median",
        intensity_unit="a.u.",
    )


class M6DomainTypeRangeComparisonTests(unittest.TestCase):
    def test_joint_table_covers_disappearing_common_and_appearing_types(self) -> None:
        result = build_m6_domain_type_range_comparison(
            _classification(),
            _range_analysis(BEFORE),
            _range_analysis(AFTER),
        )

        self.assertEqual(result.direction, "second_minus_first")
        self.assertEqual(result.first_range_name, "before desorption")
        self.assertEqual(result.second_range_name, "after adsorption")
        self.assertEqual(result.first_summary.analyzed_frame_count, 3)
        self.assertEqual(result.second_summary.analyzed_frame_count, 4)
        self.assertEqual(result.first_summary.available_frame_count, 3)
        self.assertEqual(result.second_summary.available_frame_count, 3)
        self.assertEqual(
            tuple(item.source_frame_index for item in result.second_frame_mapping),
            (103, 104, 105, 106),
        )
        self.assertEqual(
            result.second_frame_mapping[-1].m6_availability_status,
            "unavailable_blocking_graph_qc",
        )
        self.assertEqual(tuple(row.label for row in result.rows), ("A", "B", "C"))
        self.assertEqual(result.domain_type_identity, "shared_structural_type")
        self.assertEqual(
            result.domain_instance_identity,
            "one_full_m6_domain_component_in_one_frame",
        )
        self.assertEqual(result.local_m6_domain_id_scope, "frame_local")

        disappearing, common, appearing = result.rows
        self.assertEqual(disappearing.first.domain_instance_count, 2)
        self.assertEqual(disappearing.second.domain_instance_count, 0)
        self.assertEqual(disappearing.second.frames_with_type_count, 0)
        self.assertEqual(disappearing.second.frames_with_type_percent, 0.0)
        self.assertEqual(
            disappearing.second.mean_domain_instances_per_available_frame,
            0.0,
        )
        self.assertEqual(disappearing.second.mean_molecule_fraction, 0.0)
        self.assertEqual(disappearing.second.mean_footprint_fraction, 0.0)
        self.assertEqual(disappearing.deltas.domain_instance_count, -2)
        self.assertEqual(disappearing.deltas.frames_with_type_count, -2)
        self.assertAlmostEqual(
            disappearing.deltas.frames_with_type_percentage_points,
            -200.0 / 3.0,
        )
        self.assertAlmostEqual(
            disappearing.deltas.mean_domain_instances_per_available_frame,
            -2.0 / 3.0,
        )
        self.assertAlmostEqual(
            disappearing.deltas.mean_molecule_fraction_percentage_points,
            -40.0 / 3.0,
        )
        self.assertAlmostEqual(
            disappearing.deltas.mean_footprint_fraction_percentage_points,
            -20.0 / 3.0,
        )
        self.assertIsNone(disappearing.deltas.mean_domain_coherent_q6)
        self.assertIsNone(disappearing.deltas.mean_molecule_count)
        self.assertIsNone(disappearing.deltas.mean_footprint_area_nm2)

        self.assertEqual(common.first.domain_instance_count, 2)
        self.assertEqual(common.second.domain_instance_count, 2)
        self.assertEqual(common.deltas.domain_instance_count, 0)
        self.assertEqual(common.deltas.frames_with_type_count, 1)
        self.assertAlmostEqual(
            common.deltas.frames_with_type_percentage_points,
            100.0 / 3.0,
        )
        self.assertEqual(
            common.deltas.mean_domain_instances_per_available_frame,
            0.0,
        )
        self.assertAlmostEqual(
            common.deltas.mean_molecule_fraction_percentage_points,
            10.0 / 3.0,
        )
        self.assertAlmostEqual(
            common.deltas.mean_footprint_fraction_percentage_points,
            5.0,
        )
        self.assertAlmostEqual(common.deltas.mean_domain_coherent_q6, 0.1)
        self.assertEqual(common.deltas.mean_molecule_count, 10.0)
        self.assertEqual(common.deltas.mean_footprint_area_nm2, 10.0)

        self.assertEqual(appearing.first.domain_instance_count, 0)
        self.assertEqual(appearing.second.domain_instance_count, 2)
        self.assertEqual(appearing.deltas.domain_instance_count, 2)
        self.assertAlmostEqual(
            appearing.deltas.frames_with_type_percentage_points,
            200.0 / 3.0,
        )
        self.assertAlmostEqual(
            appearing.deltas.mean_molecule_fraction_percentage_points,
            40.0 / 3.0,
        )

    def test_rejects_ranges_in_an_order_different_from_joint_scope(self) -> None:
        with self.assertRaisesRegex(ValueError, "classification range order"):
            build_m6_domain_type_range_comparison(
                _classification(),
                _range_analysis(AFTER),
                _range_analysis(BEFORE),
            )

    def test_public_result_rejects_sides_from_the_wrong_summary(self) -> None:
        result = build_m6_domain_type_range_comparison(
            _classification(),
            _range_analysis(BEFORE),
            _range_analysis(AFTER),
        )

        with self.assertRaisesRegex(ValueError, "present types"):
            replace(
                result,
                first_summary=result.second_summary,
                second_summary=result.first_summary,
            )


if __name__ == "__main__":
    unittest.main()
