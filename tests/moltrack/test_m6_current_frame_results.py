import os
import unittest
from dataclasses import fields
import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis import (
    aggregate_m6_orientation_frame,
    build_m6_current_frame_results,
)
from test_orientation_domain_footprint import _metrics, _partition
from test_orientation_domain_frame_aggregates import (
    _field_for_metrics,
    _set_component_coherence,
)

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.dialogs.m6_current_frame_results_panel import (
        M6CurrentFrameResultsPanel,
    )


def _two_domain_aggregates():
    points = np.asarray(((0.5, 0.5), (1.5, 0.5), (2.5, 0.5), (3.5, 0.5)))
    metrics = _set_component_coherence(
        _metrics(
            points,
            components=(
                ("full_domain", (0, 1)),
                ("full_domain", (2, 3)),
            ),
            support_radius_nm=10.0,
        ),
        (0.4, 0.8),
    )
    footprint = _partition(points, metrics=metrics, window_size_nm=(4.0, 1.0))
    return aggregate_m6_orientation_frame(
        local_order=_field_for_metrics(metrics),
        domain_metrics=metrics,
        footprint_partition=footprint,
    )


def _empty_aggregates():
    points = np.empty((0, 2), dtype=np.float64)
    metrics = _metrics(points, components=(), support_radius_nm=1.0)
    return aggregate_m6_orientation_frame(
        local_order=_field_for_metrics(metrics),
        domain_metrics=metrics,
        footprint_partition=_partition(
            points,
            metrics=metrics,
            window_size_nm=(4.0, 2.0),
        ),
    )


class M6CurrentFrameResultsProjectionTests(unittest.TestCase):
    def test_projects_two_domains_and_complete_frame_summary(self) -> None:
        aggregates = _two_domain_aggregates()

        result = build_m6_current_frame_results(aggregates)

        self.assertEqual(len(result.domains), 2)
        first = result.domains[0]
        self.assertEqual(first.ordered_component_id, 0)
        self.assertEqual(first.m6_orientation_domain_id, 0)
        self.assertEqual(first.component_type, "full_domain")
        self.assertEqual(first.molecule_count, 2)
        self.assertAlmostEqual(first.molecule_fraction_of_valid_representatives, 0.5)
        self.assertAlmostEqual(first.footprint_fraction_of_valid_fov, 0.5)
        self.assertAlmostEqual(first.footprint_area_nm2, 2.0)
        self.assertAlmostEqual(first.domain_coherent_q6, 0.4)
        self.assertIsNone(first.domain_median_bond_length_nm)
        self.assertIsNone(first.domain_bond_length_robust_cv)
        self.assertEqual(
            first.qc_statuses,
            ("insufficient_bonds_for_length_stats", "edge_truncated"),
        )

        summary = result.summary
        self.assertEqual(summary.full_domain_count, 2)
        self.assertEqual(summary.small_ordered_island_count, 0)
        self.assertAlmostEqual(summary.full_domain_molecule_fraction, 1.0)
        self.assertAlmostEqual(summary.full_domain_footprint_fraction, 1.0)
        self.assertAlmostEqual(summary.full_domain_molecule_weighted_coherent_q6, 0.6)
        self.assertAlmostEqual(summary.full_domain_footprint_weighted_coherent_q6, 0.6)
        self.assertAlmostEqual(summary.domain_molecule_entropy, 1.0)
        self.assertAlmostEqual(summary.domain_footprint_entropy, 1.0)

    def test_projects_readable_empty_domain_state(self) -> None:
        result = build_m6_current_frame_results(_empty_aggregates())

        self.assertEqual(result.domains, ())
        self.assertEqual(result.empty_message, "No M6 domains in current frame.")
        self.assertEqual(result.summary.full_domain_count, 0)


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for MolTrack GUI tests")
class M6CurrentFrameResultsPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.panel = M6CurrentFrameResultsPanel()

    def tearDown(self) -> None:
        self.panel.close()
        self.panel.deleteLater()
        self.__class__._app.processEvents()

    def test_table_values_and_public_selection_signal(self) -> None:
        result = build_m6_current_frame_results(_two_domain_aggregates())
        selected = []
        self.panel.domain_selection_changed.connect(selected.append)

        self.panel.set_results(result)
        self.panel.domain_table.setCurrentCell(1, 0)

        self.assertEqual(self.panel.domain_row_count(), 2)
        self.assertEqual(
            tuple(
                self.panel.domain_table.item(0, column).text()
                for column in range(self.panel.domain_table.columnCount())
            ),
            (
                "0",
                "0",
                "full_domain",
                "2",
                "0.5",
                "0.5",
                "2",
                "0",
                "0.4",
                "0.4",
                "n/a",
                "n/a",
                "n/a",
                "n/a",
                "insufficient_bonds_for_length_stats, edge_truncated",
            ),
        )
        self.assertEqual(
            set(self.panel.summary_value_labels),
            {field.name for field in fields(type(result.summary))},
        )
        for field in fields(type(result.summary)):
            value = getattr(result.summary, field.name)
            expected = "n/a" if value is None else (
                f"{value:.6g}" if isinstance(value, float) else str(value)
            )
            self.assertEqual(
                self.panel.summary_value_labels[field.name].text(),
                expected,
            )
        self.assertEqual(self.panel.current_results(), result)
        self.assertEqual(selected[-1], 1)

    def test_empty_result_shows_explicit_state(self) -> None:
        self.panel.set_results(build_m6_current_frame_results(_empty_aggregates()))

        self.assertEqual(self.panel.domain_row_count(), 0)
        self.assertTrue(self.panel.empty_label.isVisibleTo(self.panel))
        self.assertEqual(self.panel.empty_label.text(), "No M6 domains in current frame.")


if __name__ == "__main__":
    unittest.main()
