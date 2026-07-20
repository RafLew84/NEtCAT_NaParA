import csv
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis import (
    M6DomainTypeAnalysisOutcome,
    M6DomainTypeAnalysisSource,
    M6DomainTypeAnalysisStore,
    M6DomainTypeAnalysisStoreState,
    M6DomainTypeSessionState,
    MolecularFrameRange,
    MolecularFrameRangeAnalysis,
    adapt_m6_domain_type_analysis_source,
)
from moltrack.analysis.molecular_m6_analysis import MolecularM6OrientationAnalysis
from moltrack.persistence import load_moltrack_session, save_moltrack_session
from moltrack.persistence.m6_domain_type_export import (
    build_m6_domain_type_export_data,
    write_m6_domain_type_tables,
)
from moltrack.ui.m6_domain_type_overlay import (
    build_m6_domain_type_frame_overlay,
    build_m6_domain_type_overlay_index,
)
from moltrack.ui.m6_domain_type_selection import M6DomainTypeSelection
from test_m6_domain_type_lifecycle import (
    _comparison as _build_range_comparison,
    _component as _build_domain_component,
    _m6_analysis as _build_m6_analysis,
    _m6_settings,
    _type_settings,
)
from test_m6_domain_type_single_range_end_to_end import _single_range_outcome
from test_m6_session_persistence import _series as _build_session_fixture_series

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui import MolTrackMainWindow
    from moltrack.ui.dialogs import PositionAnalysisDialog
    from moltrack.ui.dialogs.m6_domain_type_plots_panel import (
        M6DomainTypePlotsPanel,
    )
    from moltrack.ui.dialogs.m6_domain_type_results_table import (
        M6DomainTypeResultsTable,
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


BEFORE = MolecularFrameRange("before desorption", 0, 2)
AFTER = MolecularFrameRange("after adsorption", 3, 6)


def _domain_component(
    component_id: int,
    orientation_deg: float,
    bond_length_nm: float,
    *,
    coherent_q6: float = 0.7,
    heterogeneous: bool = False,
):
    component = _build_domain_component(
        component_id,
        orientation_deg=orientation_deg,
        bond_length_nm=bond_length_nm,
        coherent_q6=coherent_q6,
    )
    component.bond_length_heterogeneity_qc = bool(heterogeneous)
    return component


def _completed_range(
    frame_range: MolecularFrameRange,
    components_by_frame: dict[int, tuple | None],
) -> MolecularFrameRangeAnalysis:
    settings = _m6_settings()
    frame_results = []
    for frame_index in frame_range.frame_indices:
        components = components_by_frame[frame_index]
        available = components is not None
        frame_results.append(SimpleNamespace(
            frame_index=frame_index,
            source_frame_index=frame_index + 100,
            source_view="raw",
            m6_orientation_availability_status=(
                "available" if available else "unavailable_blocking_graph_qc"
            ),
            m6_orientation_unavailability_reason=(
                None if available else "blocking_rank2_radius_fallback"
            ),
            m6_orientation_analysis=(
                _build_m6_analysis(
                    components,
                    source_view="raw",
                    settings=settings,
                )
                if available
                else None
            ),
        ))
    return MolecularFrameRangeAnalysis(
        frame_range=frame_range,
        source_view="raw",
        frame_results=tuple(frame_results),
        aggregates=None,
        intensity_metric="background_corrected_median",
        intensity_unit="a.u.",
        use_segmentation_centroids=True,
        m6_orientation_settings=settings,
    )


def _comparison_source() -> M6DomainTypeAnalysisSource:
    before = _completed_range(BEFORE, {
        0: (
            _domain_component(11, 1.0, 2.0, coherent_q6=0.5),
            _domain_component(101, 52.0, 8.0, coherent_q6=0.3, heterogeneous=True),
        ),
        1: (_domain_component(12, 2.0, 2.1, coherent_q6=0.6),),
        2: (
            _domain_component(31, 20.0, 4.0, coherent_q6=0.6),
            _domain_component(32, 21.0, 4.1, coherent_q6=0.7),
        ),
    })
    after = _completed_range(AFTER, {
        3: (
            _domain_component(71, 20.5, 4.0, coherent_q6=0.7),
            _domain_component(91, 40.0, 6.0, coherent_q6=0.4),
        ),
        4: (_domain_component(72, 21.5, 4.1, coherent_q6=0.8),),
        5: (
            _domain_component(92, 41.0, 6.1, coherent_q6=0.5),
            _domain_component(102, 52.0, 8.0, coherent_q6=0.3, heterogeneous=True),
        ),
        6: None,
    })
    return adapt_m6_domain_type_analysis_source(
        _build_range_comparison(before, after),
        frame_count=7,
    )


def _comparison_outcome() -> M6DomainTypeAnalysisOutcome:
    return M6DomainTypeAnalysisStore().analyze(
        _comparison_source(),
        classification_settings=_type_settings(
            minimum_observations_per_type=2,
        ),
    )


def _single_source() -> M6DomainTypeAnalysisSource:
    comparison_source = _comparison_source()
    return adapt_m6_domain_type_analysis_source(
        comparison_source.range_analyses[0],
        frame_count=7,
    )


class _RecordingDomainTypeStore:
    def __init__(self) -> None:
        self.state = M6DomainTypeAnalysisStoreState(status="empty", outcome=None)
        self.invalidation_reasons = []

    def set_current(self, outcome: M6DomainTypeAnalysisOutcome) -> None:
        self.state = M6DomainTypeAnalysisStoreState(
            status="current",
            outcome=outcome,
        )

    def clear(self) -> None:
        self.state = M6DomainTypeAnalysisStoreState(status="empty", outcome=None)

    def invalidate(self, reason: str) -> bool:
        self.invalidation_reasons.append(str(reason))
        outcome = self.state.outcome
        if outcome is None:
            return False
        self.state = M6DomainTypeAnalysisStoreState(
            status="out_of_date",
            outcome=outcome,
            invalidation_reason=str(reason),
        )
        return True


def _overlay_component(component_id: int, *source_ids: str) -> SimpleNamespace:
    return SimpleNamespace(
        ordered_component_id=component_id,
        source_ids=tuple(source_ids),
    )


def _overlay_analysis(*components: SimpleNamespace) -> Mock:
    source_ids = tuple(
        source_id for component in components for source_id in component.source_ids
    )
    analysis = Mock(spec=MolecularM6OrientationAnalysis)
    analysis.sample_coordinates = SimpleNamespace(
        point_source_ids=source_ids,
        source_points_xy_px=tuple(
            (float(index + 1), float(index + 2))
            for index in range(len(source_ids))
        ),
    )
    analysis.frame_aggregates = SimpleNamespace(
        domain_metrics=SimpleNamespace(components=tuple(components))
    )
    return analysis


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for GUI tests")
class M6DomainTypeCompareRangesEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def assert_csv_value(self, actual: str, expected) -> None:
        self.assertEqual(actual, "" if expected is None else str(expected))

    def assert_csv_rows_match(self, actual_rows, expected_rows) -> None:
        self.assertEqual(len(actual_rows), len(expected_rows))
        for actual, expected in zip(actual_rows, expected_rows):
            self.assertEqual(set(actual), set(expected))
            for field, expected_value in expected.items():
                self.assert_csv_value(actual[field], expected_value)

    def test_joint_result_is_identical_across_ui_overlay_state_plots_and_csv(
        self,
    ) -> None:
        outcome = _comparison_outcome()
        classification = outcome.classification
        comparison = outcome.table_result

        self.assertEqual(classification.analysis_scope.analysis_mode, "compare_ranges")
        self.assertEqual(
            tuple(domain_type.label for domain_type in classification.domain_types),
            ("A", "B", "C"),
        )
        self.assertEqual(comparison.direction, "second_minus_first")
        self.assertEqual(comparison.first_summary.analyzed_frame_count, 3)
        self.assertEqual(comparison.second_summary.analyzed_frame_count, 4)
        self.assertEqual(comparison.first_summary.available_frame_count, 3)
        self.assertEqual(comparison.second_summary.available_frame_count, 3)
        self.assertEqual(
            (
                comparison.first_summary.valid_representative_fraction_frame_count,
                comparison.second_summary.valid_representative_fraction_frame_count,
            ),
            (3, 3),
        )
        self.assertEqual(
            (
                comparison.first_summary.valid_fov_fraction_frame_count,
                comparison.second_summary.valid_fov_fraction_frame_count,
            ),
            (3, 3),
        )
        self.assertEqual(comparison.first_summary.domain_observation_count, 5)
        self.assertEqual(comparison.second_summary.domain_observation_count, 5)
        self.assertEqual(comparison.first_summary.unclassified_observation_count, 1)
        self.assertEqual(comparison.second_summary.unclassified_observation_count, 1)
        self.assertFalse(comparison.uses_tracking)
        self.assertEqual(
            tuple(
                (item.working_frame_index, item.source_frame_index)
                for item in comparison.first_frame_mapping
            ),
            ((0, 100), (1, 101), (2, 102)),
        )
        self.assertEqual(
            tuple(
                (item.working_frame_index, item.source_frame_index)
                for item in comparison.second_frame_mapping
            ),
            ((3, 103), (4, 104), (5, 105), (6, 106)),
        )

        disappearing, common, appearing = comparison.rows
        self.assertEqual(
            (disappearing.first.domain_instance_count,
             disappearing.second.domain_instance_count,
             disappearing.deltas.domain_instance_count),
            (2, 0, -2),
        )
        self.assertEqual(
            (common.first.domain_instance_count,
             common.second.domain_instance_count,
             common.deltas.domain_instance_count),
            (2, 2, 0),
        )
        self.assertEqual(
            (appearing.first.domain_instance_count,
             appearing.second.domain_instance_count,
             appearing.deltas.domain_instance_count),
            (0, 2, 2),
        )
        self.assertAlmostEqual(
            common.deltas.frames_with_type_percentage_points,
            100.0 / 3.0,
        )
        self.assertAlmostEqual(
            common.deltas.mean_molecule_fraction_percentage_points,
            0.0,
        )
        self.assertAlmostEqual(
            common.deltas.mean_footprint_fraction_percentage_points,
            0.0,
        )
        expected_deltas = (
            (
                -2,
                -2,
                -200.0 / 3.0,
                -2.0 / 3.0,
                -40.0 / 3.0,
                -20.0 / 3.0,
                None,
                None,
                None,
            ),
            (
                0,
                1,
                100.0 / 3.0,
                0.0,
                0.0,
                0.0,
                0.1,
                0.0,
                0.0,
            ),
            (
                2,
                2,
                200.0 / 3.0,
                2.0 / 3.0,
                40.0 / 3.0,
                20.0 / 3.0,
                None,
                None,
                None,
            ),
        )
        for row, expected in zip(comparison.rows, expected_deltas):
            actual = (
                row.deltas.domain_instance_count,
                row.deltas.frames_with_type_count,
                row.deltas.frames_with_type_percentage_points,
                row.deltas.mean_domain_instances_per_available_frame,
                row.deltas.mean_molecule_fraction_percentage_points,
                row.deltas.mean_footprint_fraction_percentage_points,
                row.deltas.mean_domain_coherent_q6,
                row.deltas.mean_molecule_count,
                row.deltas.mean_footprint_area_nm2,
            )
            for actual_value, expected_value in zip(actual, expected):
                if expected_value is None:
                    self.assertIsNone(actual_value)
                else:
                    self.assertAlmostEqual(actual_value, expected_value)

        table = M6DomainTypeResultsTable()
        self.addCleanup(table.deleteLater)
        self.addCleanup(table.close)
        table.set_table_result(comparison)
        self.assertEqual(table.row_labels(), ("A", "B", "C", "Unclassified"))
        self.assertIn("Deltas: second - first", table.summary_text())
        self.assertIn("domains are not tracked", table.summary_text())
        self.assertEqual(
            table.cell_text("A", "Delta (second - first) | Observations"),
            "-2",
        )
        self.assertEqual(
            table.cell_text("B", "Delta (second - first) | Observations"),
            "0",
        )
        self.assertEqual(
            table.cell_text("C", "Delta (second - first) | Observations"),
            "2",
        )
        self.assertEqual(
            table.cell_text(
                "Unclassified",
                "Delta (second - first) | Observations",
            ),
            "0",
        )

        plots = M6DomainTypePlotsPanel()
        self.addCleanup(plots.deleteLater)
        self.addCleanup(plots.close)
        plots.set_outcome(outcome)
        self.assertEqual(plots.scatter_point_count(), 10)
        self.assertEqual(
            plots.scatter_legend_labels(),
            (
                "A",
                "B",
                "C",
                "Unclassified",
                "before desorption",
                "after adsorption",
            ),
        )
        self.assertEqual(
            plots.share_legend_labels(),
            ("before desorption", "after adsorption"),
        )
        self.assertEqual(
            plots.share_data().type_labels,
            ("A", "B", "C", "Unclassified"),
        )
        first_values, second_values = plots.share_values()
        self.assertEqual(first_values, (2.0 / 3.0, 2.0 / 3.0, 0.0, 1.0 / 3.0))
        self.assertEqual(second_values, (0.0, 2.0 / 3.0, 2.0 / 3.0, 1.0 / 3.0))

        overlay_index = build_m6_domain_type_overlay_index(classification)
        before_overlay = build_m6_domain_type_frame_overlay(
            _overlay_analysis(
                _overlay_component(31, "before-common-1"),
                _overlay_component(32, "before-common-2"),
            ),
            overlay_index,
            frame_index=2,
            opacity_percent=60,
            selection=M6DomainTypeSelection.classified(common.domain_type_id),
        )
        after_overlay = build_m6_domain_type_frame_overlay(
            _overlay_analysis(
                _overlay_component(71, "after-common"),
                _overlay_component(91, "after-appearing"),
            ),
            overlay_index,
            frame_index=3,
            opacity_percent=60,
            selection=M6DomainTypeSelection.classified(common.domain_type_id),
        )
        unclassified_overlay = build_m6_domain_type_frame_overlay(
            _overlay_analysis(
                _overlay_component(11, "before-a"),
                _overlay_component(101, "before-unclassified"),
            ),
            overlay_index,
            frame_index=0,
            opacity_percent=60,
            selection=M6DomainTypeSelection.unclassified(),
        )
        self.assertEqual(
            before_overlay.overlay.colors_rgba[0],
            after_overlay.overlay.colors_rgba[0],
        )
        self.assertEqual(
            before_overlay.highlighted_source_ids,
            ("before-common-1", "before-common-2"),
        )
        self.assertEqual(after_overlay.highlighted_source_ids, ("after-common",))
        self.assertEqual(
            unclassified_overlay.highlighted_source_ids,
            ("before-unclassified",),
        )

        state = M6DomainTypeSessionState.from_outcome(outcome)
        with tempfile.TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            source_path = directory / "movie.mpp"
            source_path.write_bytes(b"compare ranges end-to-end source")
            session_path = directory / "state.moltrack.json"
            save_moltrack_session(
                session_path,
                _build_session_fixture_series(source_path),
                {"m6_domain_type_analysis": state},
            )
            payload = json.loads(session_path.read_text(encoding="utf-8"))
            restored = load_moltrack_session(session_path)

            export_data = build_m6_domain_type_export_data(
                classification,
                comparison,
                tables_included=True,
            )
            csv_paths = write_m6_domain_type_tables(directory / "export", export_data)
            type_rows = _read_csv(csv_paths["domain_types_csv"])
            range_rows = _read_csv(csv_paths["domain_type_ranges_csv"])
            comparison_rows = _read_csv(csv_paths["domain_type_comparison_csv"])

        self.assertEqual(restored.m6_domain_type_analysis_state, state)
        restored_outcome = restored.m6_domain_type_analysis_state.cache_record.outcome
        self.assertEqual(
            tuple(row.label for row in restored_outcome.table_result.rows),
            ("A", "B", "C"),
        )
        self.assertEqual(restored_outcome.table_result.direction, "second_minus_first")
        self.assertFalse(payload["m6_domain_type_analysis"]["uses_tracking"])

        self.assert_csv_rows_match(type_rows, export_data.domain_type_rows)
        self.assert_csv_rows_match(range_rows, export_data.range_rows)
        self.assert_csv_rows_match(comparison_rows, export_data.comparison_rows)

        self.assertEqual(
            tuple(row["domain_type_label"] for row in type_rows),
            ("A", "B", "C"),
        )
        self.assertEqual(len(range_rows), 8)
        self.assertEqual(
            {
                (row["condition_order"], row["domain_type_label"])
                for row in range_rows
            },
            {
                (condition, label)
                for condition in ("first", "second")
                for label in ("A", "B", "C", "Unclassified")
            },
        )
        self.assertEqual(
            {
                (row["condition_order"], row["working_frame_indices_json"])
                for row in range_rows
            },
            {("first", "[0,1,2]"), ("second", "[3,4,5,6]")},
        )
        self.assertEqual(
            {
                (row["condition_order"], row["source_frame_indices_json"])
                for row in range_rows
            },
            {("first", "[100,101,102]"), ("second", "[103,104,105,106]")},
        )
        summaries = {
            "first": comparison.first_summary,
            "second": comparison.second_summary,
        }
        for condition, summary in summaries.items():
            rows = [
                row for row in range_rows if row["condition_order"] == condition
            ]
            for row in rows:
                for field, expected in (
                    ("analyzed_frame_count", summary.analyzed_frame_count),
                    ("available_frame_count", summary.available_frame_count),
                    (
                        "valid_representative_fraction_frame_count",
                        summary.valid_representative_fraction_frame_count,
                    ),
                    (
                        "valid_fov_fraction_frame_count",
                        summary.valid_fov_fraction_frame_count,
                    ),
                    (
                        "domain_observation_count",
                        summary.domain_observation_count,
                    ),
                    (
                        "unclassified_observation_count",
                        summary.unclassified_observation_count,
                    ),
                ):
                    self.assert_csv_value(row[field], expected)
        self.assertEqual(
            tuple(row["domain_type_label"] for row in comparison_rows),
            ("A", "B", "C"),
        )
        self.assertEqual(
            tuple(row["domain_instance_count_delta"] for row in comparison_rows),
            ("-2", "0", "2"),
        )
        self.assertTrue(
            all(row["direction"] == "second_minus_first" for row in comparison_rows)
        )
        for csv_row, model_row in zip(comparison_rows, comparison.rows):
            for field, expected in (
                ("domain_type_id", model_row.domain_type_id),
                ("domain_type_label", model_row.label),
                (
                    "prototype_orientation_deg",
                    model_row.prototype_orientation_deg,
                ),
                (
                    "prototype_bond_length_nm",
                    model_row.prototype_bond_length_nm,
                ),
                (
                    "orientation_circular_spread_deg",
                    model_row.orientation_circular_spread_deg,
                ),
                ("bond_length_iqr_nm", model_row.bond_length_iqr_nm),
            ):
                self.assert_csv_value(csv_row[field], expected)
            for prefix, side in (
                ("first", model_row.first),
                ("second", model_row.second),
            ):
                aggregate = side.range_aggregate
                for suffix, expected in (
                    ("domain_instance_count", side.domain_instance_count),
                    ("frames_with_type_count", side.frames_with_type_count),
                    ("frames_with_type_percent", side.frames_with_type_percent),
                    (
                        "mean_domain_instances_per_available_frame",
                        side.mean_domain_instances_per_available_frame,
                    ),
                    ("mean_molecule_fraction", side.mean_molecule_fraction),
                    ("mean_footprint_fraction", side.mean_footprint_fraction),
                    ("mean_domain_coherent_q6", side.mean_domain_coherent_q6),
                    ("mean_molecule_count", side.mean_molecule_count),
                    ("mean_footprint_area_nm2", side.mean_footprint_area_nm2),
                    ("available_frame_count", aggregate.available_frame_count),
                    (
                        "valid_representative_fraction_frame_count",
                        aggregate.valid_representative_fraction_frame_count,
                    ),
                    (
                        "valid_fov_fraction_frame_count",
                        aggregate.valid_fov_fraction_frame_count,
                    ),
                ):
                    self.assert_csv_value(csv_row[f"{prefix}_{suffix}"], expected)
            for suffix, expected in (
                ("domain_instance_count", model_row.deltas.domain_instance_count),
                (
                    "frames_with_type_count",
                    model_row.deltas.frames_with_type_count,
                ),
                (
                    "frames_with_type_percentage_points",
                    model_row.deltas.frames_with_type_percentage_points,
                ),
                (
                    "mean_domain_instances_per_available_frame",
                    model_row.deltas.mean_domain_instances_per_available_frame,
                ),
                (
                    "mean_molecule_fraction_percentage_points",
                    model_row.deltas.mean_molecule_fraction_percentage_points,
                ),
                (
                    "mean_footprint_fraction_percentage_points",
                    model_row.deltas.mean_footprint_fraction_percentage_points,
                ),
                (
                    "mean_domain_coherent_q6",
                    model_row.deltas.mean_domain_coherent_q6,
                ),
                ("mean_molecule_count", model_row.deltas.mean_molecule_count),
                (
                    "mean_footprint_area_nm2",
                    model_row.deltas.mean_footprint_area_nm2,
                ),
            ):
                self.assert_csv_value(csv_row[f"{suffix}_delta"], expected)
        self.assertEqual(export_data.manifest["analysis_mode"], "compare_ranges")
        self.assertEqual(len(export_data.manifest["ranges"]), 2)
        self.assertFalse(export_data.manifest["uses_tracking"])

    def test_switching_same_dialog_out_of_comparison_invalidates_type_result(
        self,
    ) -> None:
        outcome = _comparison_outcome()
        store = _RecordingDomainTypeStore()
        window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            m6_domain_type_store=store,
        )
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        window.set_image_series(_build_session_fixture_series(Path("movie.mpp")))
        window._on_position_analysis_requested()
        dialog = window.position_analysis_dialog()
        dialog.set_analysis_mode("compare_ranges")
        panel = dialog.domain_types_panel
        panel.set_analysis_source(_comparison_source())
        store.set_current(outcome)
        panel.set_store_state(store.state)
        store.invalidation_reasons.clear()
        self.assertIs(panel.results_table.table_result(), outcome.table_result)
        self.assertIs(panel.plots_panel.outcome(), outcome)

        dialog.set_analysis_mode("single_range")

        self.assertEqual(store.invalidation_reasons, ["analysis_mode"])
        self.assertEqual(store.state.status, "out_of_date")
        self.assertIsNone(panel.results_table.table_result())
        self.assertIsNone(panel.plots_panel.outcome())
        self.assertIsNone(dialog.range_analysis_result())

        single_outcome = _single_range_outcome()
        panel.set_analysis_source(_single_source())
        store.set_current(single_outcome)
        panel.set_store_state(store.state)
        self.assertIs(
            panel.results_table.table_result(),
            single_outcome.table_result,
        )

        dialog.set_analysis_mode("compare_ranges")

        self.assertEqual(
            store.invalidation_reasons,
            ["analysis_mode", "analysis_mode"],
        )
        self.assertEqual(store.state.status, "out_of_date")
        self.assertIsNone(panel.results_table.table_result())
        self.assertIsNone(panel.plots_panel.outcome())


if __name__ == "__main__":
    unittest.main()
