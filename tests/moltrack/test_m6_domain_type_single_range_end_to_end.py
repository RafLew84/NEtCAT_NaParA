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
    M6DomainTypeAnalysisStoreState,
    M6DomainTypeNamedRangeResult,
    M6DomainTypeSessionState,
    build_m6_single_range_domain_type_summary,
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
from test_m6_session_persistence import _series as _build_session_fixture_series
from test_m6_single_range_domain_type_summary import (
    _classification,
    _observation,
    _range_analysis,
)

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.dialogs import PositionAnalysisDialog


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


def _single_range_outcome() -> M6DomainTypeAnalysisOutcome:
    observations = (
        _observation(
            1,
            10,
            1.0,
            2.0,
            range_end=3,
            molecule_fraction=0.2,
            footprint_fraction=0.1,
        ),
        _observation(
            2,
            20,
            20.0,
            4.0,
            range_end=3,
            molecule_fraction=0.3,
            footprint_fraction=0.2,
        ),
        _observation(
            2,
            21,
            30.0,
            None,
            range_end=3,
            molecule_fraction=0.1,
            footprint_fraction=0.1,
            qualification_status="unclassified",
            unclassified_reason="missing_bond_length_statistics",
        ),
        _observation(
            3,
            30,
            2.0,
            2.1,
            range_end=3,
            molecule_fraction=0.2,
            footprint_fraction=0.2,
        ),
        _observation(
            3,
            31,
            21.0,
            4.1,
            range_end=3,
            molecule_fraction=0.3,
            footprint_fraction=0.3,
        ),
    )
    classification = _classification(observations, frame_count=4)
    table_result = build_m6_single_range_domain_type_summary(
        classification,
        _range_analysis(
            (
                (0, 0.0, 0.0),
                (1, 0.2, 0.1),
                (2, 0.4, 0.3),
                (2, 0.5, 0.5),
            )
        ),
    )
    return M6DomainTypeAnalysisOutcome(
        status="ready",
        status_message="Single-range domain types are ready.",
        context_fingerprint="single-range-end-to-end-v1",
        analysis_scope=classification.analysis_scope,
        available_m6_frame_count=4,
        classification=classification,
        table_result=table_result,
    )


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for GUI tests")
class M6DomainTypeSingleRangeEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_core_ui_overlay_state_and_csv_share_one_single_range_result(
        self,
    ) -> None:
        outcome = _single_range_outcome()
        classification = outcome.classification
        summary = outcome.table_result

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
        range_analysis = _range_analysis(
            (
                (0, 0.0, 0.0),
                (1, 0.2, 0.1),
                (2, 0.4, 0.3),
                (2, 0.5, 0.5),
            )
        )
        source = M6DomainTypeAnalysisSource(
            analysis_mode="single_range",
            frame_count=4,
            source_view="raw",
            use_segmentation_centroids=range_analysis.use_segmentation_centroids,
            m6_settings=(
                range_analysis.frame_results[0].m6_orientation_analysis.settings
            ),
            named_ranges=(M6DomainTypeNamedRangeResult(range_analysis),),
        )
        dialog = PositionAnalysisDialog()
        self.addCleanup(dialog.deleteLater)
        self.addCleanup(dialog.close)
        dialog.configure_frame_ranges(frame_count=4, source_view="raw")
        dialog.set_analysis_mode("single_range")
        panel = dialog.domain_types_panel
        panel.set_analysis_source(source)
        panel.set_store_state(
            M6DomainTypeAnalysisStoreState(status="current", outcome=outcome)
        )
        widget = panel.results_table
        self.assertIs(panel.outcome(), outcome)
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
        self.assertEqual(
            {row["frames_with_full_domain_count"] for row in range_rows},
            {"3"},
        )
        self.assertEqual(
            {row["frames_with_full_domain_percent"] for row in range_rows},
            {"75.0"},
        )
        self.assertEqual(
            {row["mean_full_domains_per_available_frame"] for row in range_rows},
            {"1.25"},
        )
        self.assertEqual(
            {row["median_full_domains_per_available_frame"] for row in range_rows},
            {"1.5"},
        )
        self.assertEqual(
            {row["max_full_domains_per_available_frame"] for row in range_rows},
            {"2"},
        )
        self.assertEqual(
            {row["domain_observation_count"] for row in range_rows},
            {"5"},
        )
        self.assertEqual(
            {row["domain_type_count"] for row in range_rows},
            {"2"},
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
