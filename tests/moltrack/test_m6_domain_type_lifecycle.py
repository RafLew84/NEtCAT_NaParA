from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from moltrack.analysis import (
    M6DomainTypeAnalysisComputation,
    M6DomainTypeAnalysisStore,
    M6DomainTypeClassificationSettings,
    M6DomainTypeRangeComparison,
    M6SingleRangeDomainTypeSummary,
    MolecularFrameRange,
    MolecularFrameRangeAnalysis,
    MolecularFrameRangeComparison,
    MolecularFrameRangeDifferences,
    MolecularM6OrientationAnalysisSettings,
    adapt_m6_domain_type_analysis_source,
    classify_m6_domain_types,
    extract_m6_domain_type_observations,
)
from moltrack.analysis.molecular_m6_analysis import MolecularM6OrientationAnalysis


class _FootprintPartition:
    def __init__(self, footprints) -> None:
        self._footprints = {
            value.ordered_component_id: value for value in footprints
        }

    def component_for_ordered_id(self, ordered_component_id: int):
        return self._footprints[ordered_component_id]


def _m6_settings() -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings()


def _type_settings(**changes) -> M6DomainTypeClassificationSettings:
    return replace(
        M6DomainTypeClassificationSettings(
            orientation_tolerance_deg=5.0,
            bond_length_tolerance_mode="absolute_nm",
            bond_length_tolerance_value=0.5,
            minimum_observations_per_type=1,
        ),
        **changes,
    )


def _component(
    local_domain_id: int,
    *,
    orientation_deg: float = 10.0,
    bond_length_nm: float = 4.0,
    coherent_q6: float = 0.7,
    component_type: str = "full_domain",
):
    return SimpleNamespace(
        ordered_component_id=local_domain_id,
        m6_orientation_domain_id=(
            local_domain_id if component_type == "full_domain" else None
        ),
        component_type=component_type,
        orientation_deg=orientation_deg,
        molecule_count=10,
        molecule_fraction_of_valid_representatives=0.2,
        domain_mean_local_q6=0.8,
        domain_coherent_q6=coherent_q6,
        centroid_x_nm=5.0,
        centroid_y_nm=6.0,
        min_x_nm=4.0,
        min_y_nm=5.0,
        max_x_nm=6.0,
        max_y_nm=7.0,
        internal_first_shell_bond_count=30,
        domain_median_bond_length_nm=bond_length_nm,
        domain_bond_length_mad_nm=0.1,
        domain_bond_length_iqr_nm=0.2,
        domain_bond_length_robust_cv=0.05,
        insufficient_bonds_for_length_stats_qc=False,
        bond_length_heterogeneity_qc=False,
    )


def _m6_analysis(
    components,
    *,
    source_view: str,
    settings: MolecularM6OrientationAnalysisSettings,
) -> MolecularM6OrientationAnalysis:
    components = tuple(components)
    full_domain_count = sum(
        value.component_type == "full_domain" for value in components
    )
    footprints = tuple(
        SimpleNamespace(
            ordered_component_id=value.ordered_component_id,
            footprint_area_nm2=20.0,
            footprint_fraction_of_valid_fov=0.1,
            molecular_mask_area_nm2=10.0,
            edge_truncated=False,
            footprint_disconnected_qc=False,
        )
        for value in components
    )
    analysis = Mock(spec=MolecularM6OrientationAnalysis)
    analysis.source_view = source_view
    analysis.coordinate_frame = "sample_nm"
    analysis.orientation_reference = "+x_sample_axis"
    analysis.spatial_calibration_fingerprint = "calibration-v1"
    analysis.settings = settings
    analysis.frame_aggregates = SimpleNamespace(
        valid_representative_count=20,
        valid_fov_area_nm2=100.0,
        full_domain_count=full_domain_count,
        full_domain_molecule_fraction=0.2 * full_domain_count,
        full_domain_footprint_fraction=0.1 * full_domain_count,
        domain_metrics=SimpleNamespace(components=components),
        footprint_partition=_FootprintPartition(footprints),
    )
    return analysis


def _range_analysis(
    frame_range: MolecularFrameRange,
    *,
    source_view: str = "raw",
    use_segmentation_centroids: bool = True,
    settings: MolecularM6OrientationAnalysisSettings | None = None,
    component=None,
    m6_available: bool = True,
) -> MolecularFrameRangeAnalysis:
    settings = _m6_settings() if settings is None else settings
    frame_results = []
    for frame_index in frame_range.frame_indices:
        frame_component = (
            _component(frame_index + 10)
            if component is None
            else component
        )
        if m6_available:
            analysis = _m6_analysis(
                () if frame_component is False else (frame_component,),
                source_view=source_view,
                settings=settings,
            )
            status = "available"
            reason = None
        else:
            analysis = None
            status = "unavailable_missing_analysis"
            reason = "M6 analysis has not been completed."
        frame_results.append(
            SimpleNamespace(
                frame_index=frame_index,
                source_frame_index=frame_index + 100,
                source_view=source_view,
                m6_orientation_availability_status=status,
                m6_orientation_unavailability_reason=reason,
                m6_orientation_analysis=analysis,
            )
        )
    return MolecularFrameRangeAnalysis(
        frame_range=frame_range,
        source_view=source_view,
        frame_results=tuple(frame_results),
        aggregates=None,
        intensity_metric="background_corrected_median",
        intensity_unit="a.u.",
        use_segmentation_centroids=use_segmentation_centroids,
        m6_orientation_settings=settings,
    )


def _comparison(
    first: MolecularFrameRangeAnalysis,
    second: MolecularFrameRangeAnalysis,
) -> MolecularFrameRangeComparison:
    return MolecularFrameRangeComparison(
        source_view=first.source_view,
        first_analysis=first,
        second_analysis=second,
        differences=MolecularFrameRangeDifferences(
            direction="second_minus_first",
            distance_unit="nm",
            mean_molecule_count_delta=0.0,
            mean_nearest_neighbor_distance_delta=None,
            mean_line_order_score_delta=None,
            mean_intensity_delta=None,
            median_intensity_delta=None,
        ),
    )


class M6DomainTypeLifecycleTests(unittest.TestCase):
    def test_computation_is_staged_and_published_atomically(self) -> None:
        settings = _type_settings()
        initial_source = adapt_m6_domain_type_analysis_source(
            _range_analysis(MolecularFrameRange("initial", 0, 0)),
            frame_count=2,
        )
        replacement_source = adapt_m6_domain_type_analysis_source(
            _range_analysis(
                MolecularFrameRange("replacement", 1, 1),
                component=_component(11, orientation_deg=23.0),
            ),
            frame_count=2,
        )
        store = M6DomainTypeAnalysisStore()
        previous = store.analyze(
            initial_source,
            classification_settings=settings,
        )
        phases = []

        computation = store.compute(
            replacement_source,
            classification_settings=settings,
            progress_callback=phases.append,
        )

        self.assertIsInstance(computation, M6DomainTypeAnalysisComputation)
        self.assertEqual(
            phases,
            ["extracting_observations", "complete_linkage", "aggregating"],
        )
        self.assertIs(store.current, previous)

        published = store.publish(computation)

        self.assertIs(published, computation.outcome)
        self.assertIs(store.current, computation.outcome)

    def test_failed_staged_computation_preserves_previous_result(self) -> None:
        settings = _type_settings()
        initial_source = adapt_m6_domain_type_analysis_source(
            _range_analysis(MolecularFrameRange("initial", 0, 0)),
            frame_count=2,
        )
        replacement_source = adapt_m6_domain_type_analysis_source(
            _range_analysis(MolecularFrameRange("replacement", 1, 1)),
            frame_count=2,
        )
        store = M6DomainTypeAnalysisStore()
        previous = store.analyze(
            initial_source,
            classification_settings=settings,
        )

        with patch(
            "moltrack.analysis.m6_domain_type_lifecycle.classify_m6_domain_types",
            side_effect=RuntimeError("synthetic classification failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "synthetic classification failure"):
                store.compute(
                    replacement_source,
                    classification_settings=settings,
                )

        self.assertIs(store.current, previous)

    def test_adapter_exposes_named_ranges_and_reuses_completed_m6_only(self) -> None:
        single_analysis = _range_analysis(MolecularFrameRange("single", 0, 0))
        first = _range_analysis(MolecularFrameRange("before", 0, 0))
        second = _range_analysis(MolecularFrameRange("after", 1, 1))
        single_source = adapt_m6_domain_type_analysis_source(
            single_analysis,
            frame_count=2,
        )
        comparison_source = adapt_m6_domain_type_analysis_source(
            _comparison(first, second),
            frame_count=2,
        )

        self.assertEqual(single_source.analysis_mode, "single_range")
        self.assertEqual(
            tuple(value.name for value in single_source.named_ranges),
            ("single",),
        )
        self.assertIs(single_source.named_ranges[0].analysis, single_analysis)
        self.assertEqual(comparison_source.analysis_mode, "compare_ranges")
        self.assertEqual(
            tuple(value.name for value in comparison_source.named_ranges),
            ("before", "after"),
        )
        self.assertIs(comparison_source.named_ranges[0].analysis, first)
        self.assertIs(comparison_source.named_ranges[1].analysis, second)

        store = M6DomainTypeAnalysisStore()
        with (
            patch(
                "moltrack.analysis.orientation_domain_analysis."
                "build_first_shell_graph"
            ) as graph_builder,
            patch(
                "moltrack.analysis.molecular_m6_analysis."
                "analyze_molecular_m6_orientation"
            ) as m6_backend,
        ):
            single = store.analyze(
                single_source,
                classification_settings=_type_settings(),
            )
            comparison = store.analyze(
                comparison_source,
                classification_settings=_type_settings(),
            )

        graph_builder.assert_not_called()
        m6_backend.assert_not_called()
        self.assertEqual(single.status, "ready")
        self.assertIsInstance(single.table_result, M6SingleRangeDomainTypeSummary)
        self.assertEqual(comparison.status, "ready")
        self.assertIsInstance(
            comparison.table_result,
            M6DomainTypeRangeComparison,
        )

    def test_store_reuses_exact_context_and_rejects_every_changed_context(self) -> None:
        base_analysis = _range_analysis(MolecularFrameRange("condition", 0, 0))
        base_source = adapt_m6_domain_type_analysis_source(
            base_analysis,
            frame_count=2,
        )
        settings = _type_settings()
        store = M6DomainTypeAnalysisStore()

        with patch(
            "moltrack.analysis.m6_domain_type_lifecycle.classify_m6_domain_types",
            wraps=classify_m6_domain_types,
        ) as classifier, patch(
            "moltrack.analysis.m6_domain_type_lifecycle."
            "extract_m6_domain_type_observations",
            wraps=extract_m6_domain_type_observations,
        ) as extractor:
            first = store.analyze(
                base_source,
                classification_settings=settings,
            )
            reused = store.analyze(
                base_source,
                classification_settings=settings,
            )

        self.assertIs(reused, first)
        self.assertEqual(classifier.call_count, 1)
        self.assertEqual(extractor.call_count, 1)
        self.assertIs(
            store.current_for(
                base_source,
                classification_settings=settings,
            ),
            first,
        )

        changed_range = adapt_m6_domain_type_analysis_source(
            _range_analysis(MolecularFrameRange("other range", 1, 1)),
            frame_count=2,
        )
        changed_mode = adapt_m6_domain_type_analysis_source(
            _comparison(
                _range_analysis(MolecularFrameRange("before", 0, 0)),
                _range_analysis(MolecularFrameRange("after", 1, 1)),
            ),
            frame_count=2,
        )
        changed_centroids = adapt_m6_domain_type_analysis_source(
            replace(base_analysis, use_segmentation_centroids=False),
            frame_count=2,
        )
        changed_source_view = adapt_m6_domain_type_analysis_source(
            _range_analysis(
                MolecularFrameRange("condition", 0, 0),
                source_view="expanded_aligned",
            ),
            frame_count=2,
        )
        changed_m6_settings_value = replace(_m6_settings(), q_seed=0.91)
        changed_m6 = adapt_m6_domain_type_analysis_source(
            _range_analysis(
                MolecularFrameRange("condition", 0, 0),
                settings=changed_m6_settings_value,
            ),
            frame_count=2,
        )
        changed_frame = adapt_m6_domain_type_analysis_source(
            _range_analysis(
                MolecularFrameRange("condition", 0, 0),
                component=_component(10, coherent_q6=0.6),
            ),
            frame_count=2,
        )
        changed_type_settings = replace(
            settings,
            orientation_tolerance_deg=4.0,
        )

        for source in (
            changed_range,
            changed_mode,
            changed_centroids,
            changed_source_view,
            changed_m6,
            changed_frame,
        ):
            with self.subTest(source=source):
                self.assertIsNone(
                    store.current_for(
                        source,
                        classification_settings=settings,
                    )
                )
        self.assertIsNone(
            store.current_for(
                base_source,
                classification_settings=changed_type_settings,
            )
        )

    def test_missing_m6_and_missing_valid_types_return_controlled_statuses(self) -> None:
        unavailable_source = adapt_m6_domain_type_analysis_source(
            _range_analysis(
                MolecularFrameRange("condition", 0, 0),
                m6_available=False,
            ),
            frame_count=1,
        )
        no_domains_source = adapt_m6_domain_type_analysis_source(
            _range_analysis(
                MolecularFrameRange("condition", 0, 0),
                component=_component(
                    10,
                    component_type="small_ordered_island",
                ),
            ),
            frame_count=1,
        )
        store = M6DomainTypeAnalysisStore()

        unavailable = store.analyze(
            unavailable_source,
            classification_settings=_type_settings(),
        )
        no_domains = store.analyze(
            no_domains_source,
            classification_settings=_type_settings(
                include_small_ordered_islands=True,
            ),
        )

        self.assertEqual(unavailable.status, "m6_unavailable")
        self.assertIsNone(unavailable.classification)
        self.assertIsNone(unavailable.table_result)
        self.assertTrue(unavailable.status_message)
        self.assertEqual(no_domains.status, "no_valid_domain_types")
        self.assertIsNotNone(no_domains.classification)
        self.assertEqual(len(no_domains.classification.domain_types), 1)
        self.assertIsInstance(
            no_domains.table_result,
            M6SingleRangeDomainTypeSummary,
        )
        self.assertEqual(no_domains.table_result.domain_type_count, 0)
        self.assertTrue(no_domains.status_message)


if __name__ == "__main__":
    unittest.main()
