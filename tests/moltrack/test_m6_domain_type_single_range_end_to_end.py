import csv
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis import (
    M6DomainTypeAnalysisOutcome,
    M6DomainTypeAnalysisSource,
    M6DomainTypeAnalysisStore,
    M6DomainTypeClassificationSettings,
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
    _component as _source_component,
    _m6_analysis as _source_m6_analysis,
    _m6_settings,
)
from test_m6_session_persistence import _series as _build_session_fixture_series

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.dialogs import PositionAnalysisDialog
    from moltrack.ui.m6_domain_type_worker import M6DomainTypeAnalysisController


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _component(component_id: int, *source_ids: str) -> SimpleNamespace:
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


def _single_range_analysis() -> MolecularFrameRangeAnalysis:
    missing_statistics = _source_component(
        21,
        orientation_deg=30.0,
        bond_length_nm=4.0,
    )
    missing_statistics.domain_median_bond_length_nm = None
    missing_statistics.domain_bond_length_mad_nm = None
    missing_statistics.domain_bond_length_iqr_nm = None
    missing_statistics.domain_bond_length_robust_cv = None
    missing_statistics.insufficient_bonds_for_length_stats_qc = True
    components_by_frame = (
        (),
        (_source_component(10, orientation_deg=1.0, bond_length_nm=2.0),),
        (
            _source_component(20, orientation_deg=20.0, bond_length_nm=4.0),
            missing_statistics,
        ),
        (
            _source_component(30, orientation_deg=2.0, bond_length_nm=2.1),
            _source_component(31, orientation_deg=21.0, bond_length_nm=4.1),
        ),
    )
    settings = _m6_settings()
    frame_results = tuple(
        SimpleNamespace(
            frame_index=frame_index,
            source_frame_index=frame_index + 100,
            source_view="raw",
            m6_orientation_availability_status="available",
            m6_orientation_unavailability_reason=None,
            m6_orientation_analysis=_source_m6_analysis(
                components,
                source_view="raw",
                settings=settings,
            ),
        )
        for frame_index, components in enumerate(components_by_frame)
    )
    return MolecularFrameRangeAnalysis(
        frame_range=MolecularFrameRange("condition", 0, 3),
        source_view="raw",
        frame_results=frame_results,
        aggregates=None,
        intensity_metric="background_corrected_median",
        intensity_unit="a.u.",
        use_segmentation_centroids=True,
        m6_orientation_settings=settings,
    )


def _single_range_source() -> M6DomainTypeAnalysisSource:
    return adapt_m6_domain_type_analysis_source(
        _single_range_analysis(),
        frame_count=4,
    )


def _single_range_classification_settings() -> M6DomainTypeClassificationSettings:
    return M6DomainTypeClassificationSettings(
        orientation_tolerance_deg=5.0,
        bond_length_tolerance_mode="absolute_nm",
        bond_length_tolerance_value=0.5,
        minimum_observations_per_type=2,
    )


def _single_range_outcome() -> M6DomainTypeAnalysisOutcome:
    return M6DomainTypeAnalysisStore().analyze(
        _single_range_source(),
        classification_settings=_single_range_classification_settings(),
    )


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for GUI tests")
class M6DomainTypeSingleRangeEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def process_events_until(self, condition, *, timeout_s: float = 3.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self.__class__._app.processEvents()
            if condition():
                return
            time.sleep(0.005)
        self.fail("Timed out waiting for the domain type worker.")

    def test_core_ui_overlay_state_and_csv_share_one_single_range_result(
        self,
    ) -> None:
        source = _single_range_source()
        classification_settings = _single_range_classification_settings()
        store = M6DomainTypeAnalysisStore()
        dialog = PositionAnalysisDialog()
        self.addCleanup(dialog.deleteLater)
        self.addCleanup(dialog.close)
        controller = M6DomainTypeAnalysisController(store, parent=dialog)
        dialog.configure_frame_ranges(frame_count=4, source_view="raw")
        dialog.set_analysis_mode("single_range")
        panel = dialog.domain_types_panel
        panel.set_analysis_source(source)
        panel.set_settings(classification_settings, notify=False)
        controller.state_changed.connect(panel.set_store_state)
        controller.running_changed.connect(panel.set_running)
        controller.progress.connect(panel.set_progress)
        controller.failed.connect(panel.set_error)
        panel.classification_requested.connect(
            lambda settings: controller.start(
                source,
                classification_settings=settings,
            )
        )

        panel.classify_button.click()
        self.process_events_until(lambda: not controller.is_running)

        outcome = store.current
        self.assertIsNotNone(outcome)
        self.assertIs(panel.outcome(), outcome)
        classification = outcome.classification
        summary = outcome.table_result
        self.assertIsNotNone(classification)
        self.assertIsNotNone(summary)

        self.assertEqual(
            classification.analysis_scope.analysis_mode,
            "single_range",
        )
        self.assertEqual(len(classification.analysis_scope.ranges), 1)
        self.assertEqual(summary.analyzed_frame_count, 4)
        self.assertEqual(summary.available_frame_count, 4)
        self.assertEqual(summary.frames_with_full_domain_count, 3)
        self.assertEqual(summary.frames_with_full_domain_percent, 75.0)
        self.assertEqual(summary.mean_full_domains_per_available_frame, 1.25)
        self.assertEqual(summary.median_full_domains_per_available_frame, 1.5)
        self.assertEqual(summary.max_full_domains_per_available_frame, 2)
        self.assertEqual(summary.domain_observation_count, 5)
        self.assertEqual(summary.domain_type_count, 2)
        self.assertEqual(summary.unclassified_observation_count, 1)
        self.assertFalse(summary.uses_tracking)
        self.assertEqual(
            tuple(
                (item.working_frame_index, item.source_frame_index)
                for item in summary.frame_mapping
            ),
            ((0, 100), (1, 101), (2, 102), (3, 103)),
        )

        expected_labels = ("A", "B", "Unclassified")
        widget = panel.results_table
        self.assertIs(widget.table_result(), summary)
        self.assertIs(panel.plots_panel.outcome(), outcome)
        self.assertEqual(widget.row_labels(), expected_labels)
        self.assertIn("Frames with domains: 3/4 (75.00%)", widget.summary_text())
        self.assertIn("mean 1.250", widget.summary_text())
        self.assertIn("median 1.500", widget.summary_text())
        self.assertIn("max 2", widget.summary_text())
        self.assertNotIn("second", widget.summary_text().lower())
        self.assertFalse(
            any("Delta" in header for header in widget.headers())
        )

        overlay_index = build_m6_domain_type_overlay_index(classification)
        empty_overlay = build_m6_domain_type_frame_overlay(
            _overlay_analysis(),
            overlay_index,
            frame_index=0,
            opacity_percent=70,
        )
        self.assertEqual(empty_overlay.overlay.point_count, 0)
        frame_two_analysis = _overlay_analysis(
            _component(20, "type-b"),
            _component(21, "unclassified"),
        )
        frame_two = build_m6_domain_type_frame_overlay(
            frame_two_analysis,
            overlay_index,
            frame_index=2,
            opacity_percent=70,
        )
        self.assertEqual(
            frame_two.overlay.point_statuses,
            ("domain_type", "unclassified_domain"),
        )
        selected_b = build_m6_domain_type_frame_overlay(
            frame_two_analysis,
            overlay_index,
            frame_index=2,
            opacity_percent=70,
            selection=M6DomainTypeSelection.classified(1),
        )
        selected_unclassified = build_m6_domain_type_frame_overlay(
            frame_two_analysis,
            overlay_index,
            frame_index=2,
            opacity_percent=70,
            selection=M6DomainTypeSelection.unclassified(),
        )
        self.assertEqual(selected_b.highlighted_source_ids, ("type-b",))
        self.assertEqual(
            selected_unclassified.highlighted_source_ids,
            ("unclassified",),
        )
        frame_three = build_m6_domain_type_frame_overlay(
            _overlay_analysis(
                _component(30, "type-a"),
                _component(31, "type-b"),
            ),
            overlay_index,
            frame_index=3,
            opacity_percent=70,
        )
        self.assertEqual(
            frame_three.overlay.point_statuses,
            ("domain_type", "domain_type"),
        )
        self.assertNotEqual(
            frame_three.overlay.colors_rgba[0],
            frame_three.overlay.colors_rgba[1],
        )

        state = M6DomainTypeSessionState.from_outcome(outcome)
        with tempfile.TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            source_path = directory / "movie.mpp"
            source_path.write_bytes(b"single range end-to-end source")
            session_path = directory / "state.moltrack.json"
            save_moltrack_session(
                session_path,
                _build_session_fixture_series(source_path),
                {"m6_domain_type_analysis": state},
            )
            session_payload = json.loads(
                session_path.read_text(encoding="utf-8")
            )
            loaded = load_moltrack_session(session_path)

            export_data = build_m6_domain_type_export_data(
                classification,
                summary,
                tables_included=True,
            )
            csv_paths = write_m6_domain_type_tables(
                directory / "export",
                export_data,
            )
            type_rows = _read_csv(csv_paths["domain_types_csv"])
            range_rows = _read_csv(csv_paths["domain_type_ranges_csv"])
            comparison_rows = _read_csv(csv_paths["domain_type_comparison_csv"])

        restored_state = loaded.m6_domain_type_analysis_state
        self.assertEqual(restored_state, state)
        restored_outcome = restored_state.cache_record.outcome
        self.assertEqual(
            tuple(row.label for row in restored_outcome.table_result.type_summaries)
            + ("Unclassified",),
            expected_labels,
        )
        self.assertEqual(
            restored_outcome.table_result.frame_mapping,
            summary.frame_mapping,
        )
        self.assertFalse(
            session_payload["m6_domain_type_analysis"]["uses_tracking"]
        )

        self.assertEqual(
            tuple(row["domain_type_label"] for row in type_rows),
            expected_labels[:-1],
        )
        self.assertEqual(
            tuple(row["domain_type_label"] for row in range_rows),
            expected_labels,
        )
        self.assertTrue(
            all(row["condition_order"] == "single" for row in range_rows)
        )
        self.assertEqual(comparison_rows, [])
        self.assertEqual(
            {row["working_frame_indices_json"] for row in range_rows},
            {"[0,1,2,3]"},
        )
        self.assertEqual(
            {row["source_frame_indices_json"] for row in range_rows},
            {"[100,101,102,103]"},
        )
        expected_csv_aggregates = {
            "frames_with_full_domain_count": "3",
            "frames_with_full_domain_percent": "75.0",
            "mean_full_domains_per_available_frame": "1.25",
            "median_full_domains_per_available_frame": "1.5",
            "max_full_domains_per_available_frame": "2",
            "domain_observation_count": "5",
            "domain_type_count": "2",
        }
        for field_name, expected_value in expected_csv_aggregates.items():
            with self.subTest(csv_aggregate=field_name):
                self.assertEqual(
                    {row[field_name] for row in range_rows},
                    {expected_value},
                )
        self.assertEqual(
            {
                row["domain_type_label"]: row["observation_count"]
                for row in range_rows
            },
            {"A": "2", "B": "2", "Unclassified": "1"},
        )
        self.assertEqual(export_data.manifest["analysis_mode"], "single_range")
        self.assertEqual(len(export_data.manifest["ranges"]), 1)
        self.assertFalse(export_data.manifest["uses_tracking"])


if __name__ == "__main__":
    unittest.main()
