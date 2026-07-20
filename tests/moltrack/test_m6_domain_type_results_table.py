from dataclasses import replace
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis import (
    MolecularFrameRange,
    build_m6_domain_type_range_comparison,
    build_m6_single_range_domain_type_summary,
)
from test_m6_domain_type_range_comparison import (
    _classification as _comparison_classification,
    _range_analysis as _comparison_range_analysis,
)
from test_m6_single_range_domain_type_summary import (
    _classification as _single_classification,
    _observation as _single_observation,
    _range_analysis as _single_range_analysis,
)

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.dialogs.m6_domain_type_results_table import (
        M6DomainTypeResultsTable,
    )


def _single_result():
    observations = (
        _single_observation(
            0,
            0,
            1.0,
            2.0,
            range_end=3,
            molecule_fraction=0.2,
            footprint_fraction=0.1,
        ),
        _single_observation(
            1,
            0,
            2.0,
            2.1,
            range_end=3,
            molecule_fraction=0.3,
            footprint_fraction=None,
        ),
        _single_observation(
            2,
            1,
            20.0,
            4.0,
            range_end=3,
            molecule_fraction=0.2,
            footprint_fraction=0.2,
        ),
        _single_observation(
            2,
            2,
            21.0,
            4.1,
            range_end=3,
            molecule_fraction=0.3,
            footprint_fraction=0.3,
        ),
        _single_observation(
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
    return build_m6_single_range_domain_type_summary(
        _single_classification(observations, frame_count=4),
        _single_range_analysis(
            (
                (1, 0.2, 0.1),
                (2, 0.4, None),
                (2, 0.5, 0.5),
                None,
            )
        ),
    )


def _comparison_result():
    classification = _comparison_classification()
    first_range, second_range = classification.analysis_scope.comparison_ranges
    return build_m6_domain_type_range_comparison(
        classification,
        _comparison_range_analysis(first_range),
        _comparison_range_analysis(second_range),
    )


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for GUI tests")
class M6DomainTypeResultsTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.widget = M6DomainTypeResultsTable()

    def tearDown(self) -> None:
        self.widget.close()
        self.widget.deleteLater()
        self.__class__._app.processEvents()

    def test_single_range_summary_table_and_unclassified_row(self) -> None:
        result = _single_result()
        self.widget.set_table_result(result)

        summary = self.widget.summary_text()
        self.assertIn("condition", summary)
        self.assertIn("Frames with domains: 3/3 (100.00%)", summary)
        self.assertIn("mean 1.667", summary)
        self.assertIn("median 2.000", summary)
        self.assertIn("max 2", summary)
        self.assertIn("Observations: 5", summary)
        self.assertIn("Unclassified: 1", summary)
        self.assertIn("Types: 2", summary)

        self.assertEqual(self.widget.row_labels(), ("A", "B", "Unclassified"))
        first = result.type_summaries[0]
        self.assertEqual(
            self.widget.cell_text("A", "Orientation [deg]"),
            f"{first.prototype_orientation_deg:.3f}",
        )
        self.assertEqual(
            self.widget.cell_text("A", "Circular spread [deg]"),
            f"{first.orientation_circular_spread_deg:.3f}",
        )
        self.assertEqual(
            self.widget.cell_text("A", "Median bond length [nm]"),
            f"{first.prototype_bond_length_nm:.3f}",
        )
        self.assertEqual(
            self.widget.cell_text("A", "Bond length IQR [nm]"),
            f"{first.bond_length_iqr_nm:.3f}",
        )
        self.assertEqual(self.widget.cell_text("A", "Observations"), "2")
        self.assertEqual(self.widget.cell_text("A", "Frames with type"), "2")
        self.assertEqual(self.widget.cell_text("A", "Frames with type [%]"), "66.667")
        self.assertEqual(self.widget.cell_text("A", "Instances/frame"), "0.667")
        self.assertEqual(self.widget.cell_text("A", "Molecule fraction [%]"), "16.667")
        self.assertEqual(
            self.widget.cell_text("A", "Footprint fraction [%]"),
            f"{first.mean_footprint_fraction_of_valid_fov * 100.0:.3f}",
        )
        self.assertEqual(
            self.widget.cell_text("A", "Mean coherent q6"),
            f"{first.mean_domain_coherent_q6:.3f}",
        )
        self.assertEqual(self.widget.cell_text("Unclassified", "Observations"), "1")
        self.assertEqual(self.widget.cell_text("Unclassified", "Orientation [deg]"), "-")

    def test_comparison_has_shared_disappearing_appearing_zero_and_delta_values(self) -> None:
        result = _comparison_result()
        self.widget.set_table_result(result)

        self.assertEqual(
            self.widget.row_labels(),
            ("A", "B", "C", "Unclassified"),
        )
        self.assertIn("before desorption", self.widget.summary_text())
        self.assertIn("after adsorption", self.widget.summary_text())
        self.assertIn("second - first", self.widget.summary_text())

        first_observations = "before desorption | Observations"
        second_observations = "after adsorption | Observations"
        delta_observations = "Delta (second - first) | Observations"
        self.assertIn(first_observations, self.widget.headers())
        self.assertIn(second_observations, self.widget.headers())
        self.assertIn(delta_observations, self.widget.headers())
        self.assertEqual(self.widget.cell_text("A", first_observations), "2")
        self.assertEqual(self.widget.cell_text("A", second_observations), "0")
        self.assertEqual(self.widget.cell_text("A", delta_observations), "-2")
        self.assertEqual(self.widget.cell_text("B", delta_observations), "0")
        self.assertEqual(self.widget.cell_text("C", first_observations), "0")
        self.assertEqual(
            self.widget.cell_text("A", "after adsorption | Mean coherent q6"),
            "-",
        )
        self.assertEqual(
            self.widget.cell_text("A", "after adsorption | Molecule fraction [%]"),
            "0.000",
        )
        self.assertEqual(
            self.widget.cell_text("Unclassified", delta_observations),
            "0",
        )
        self.assertEqual(
            self.widget.cell_text(
                "A",
                "Delta (second - first) | Frames with type [pp]",
            ),
            "-66.667",
        )
        self.assertEqual(
            self.widget.cell_text(
                "B",
                "Delta (second - first) | Instances/frame",
            ),
            "0.000",
        )
        self.assertEqual(
            self.widget.cell_text(
                "B",
                "Delta (second - first) | Molecule fraction [pp]",
            ),
            "3.333",
        )
        self.assertEqual(
            self.widget.cell_text(
                "B",
                "Delta (second - first) | Footprint fraction [pp]",
            ),
            "5.000",
        )
        self.assertEqual(
            self.widget.cell_text(
                "B",
                "Delta (second - first) | Mean coherent q6",
            ),
            "0.100",
        )

        self.widget.resize(520, 320)
        self.widget.show()
        self.__class__._app.processEvents()
        self.assertGreater(self.widget.table.horizontalScrollBar().maximum(), 0)

    def test_long_range_names_and_empty_results_remain_readable(self) -> None:
        result = _comparison_result()
        first_name = "very long condition name before controlled desorption"
        second_name = "very long condition name after controlled readsorption"
        renamed = replace(
            result,
            first_summary=replace(
                result.first_summary,
                frame_range=MolecularFrameRange(
                    first_name,
                    result.first_range.start_frame,
                    result.first_range.end_frame,
                ),
            ),
            second_summary=replace(
                result.second_summary,
                frame_range=MolecularFrameRange(
                    second_name,
                    result.second_range.start_frame,
                    result.second_range.end_frame,
                ),
            ),
        )

        self.widget.set_table_result(renamed)
        self.assertIn(first_name, self.widget.summary_text())
        self.assertIn(second_name, self.widget.summary_text())
        self.assertIn(f"{first_name} | Observations", self.widget.headers())
        self.assertIn(f"{second_name} | Observations", self.widget.headers())

        self.widget.set_table_result(None, empty_message="Run classification first.")
        self.assertEqual(self.widget.empty_state_text(), "Run classification first.")
        self.assertTrue(self.widget.table.isHidden())

        no_domains = build_m6_single_range_domain_type_summary(
            _single_classification((), frame_count=3),
            _single_range_analysis(((0, 0.0, 0.0),) * 3),
        )
        self.widget.set_table_result(no_domains)
        self.assertEqual(self.widget.row_labels(), ("Unclassified",))
        self.assertEqual(self.widget.cell_text("Unclassified", "Observations"), "0")
        self.assertIn("No classified domain types", self.widget.empty_state_text())
        self.assertFalse(self.widget.table.isHidden())


if __name__ == "__main__":
    unittest.main()
