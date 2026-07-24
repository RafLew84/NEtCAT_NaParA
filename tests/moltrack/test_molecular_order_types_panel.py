import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis import (
    MolecularOrderTypeClassificationSettings,
    build_molecular_order_type_summary,
)
from test_molecular_order_type_summary import _comparison_classification

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.dialogs import (
        MolecularOrderTypesPanel,
        PositionAnalysisDialog,
    )


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for GUI tests")
class MolecularOrderTypesPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.panel = MolecularOrderTypesPanel()
        self.summary = build_molecular_order_type_summary(
            _comparison_classification()
        )

    def tearDown(self) -> None:
        self.panel.close()
        self.panel.deleteLater()
        self.__class__._app.processEvents()

    def test_table_switches_layers_and_shows_reliable_denominators(self) -> None:
        self.panel.set_summary(self.summary)

        self.assertEqual(self.panel.current_layer(), "geometry")
        self.assertEqual(self.panel.row_labels(), ("G:A", "G:B"))
        self.assertIn("before | Count", self.panel.headers())
        self.assertIn("after | Share [%]", self.panel.headers())
        self.assertIn("Delta (after - before) [pp]", self.panel.headers())
        self.assertEqual(
            self.panel.cell_text("G:A", "before | Share [%]"),
            "100.000",
        )
        self.assertEqual(
            self.panel.cell_text("G:A", "after | Share [%]"),
            "0.000",
        )
        self.assertIn("geometry: reliable 2/2", self.panel.status_text())
        self.assertIn("orientation: reliable 1/2", self.panel.status_text())

        self.panel.set_layer("combination")

        self.assertEqual(
            self.panel.row_labels(),
            ("G:A / O:B / S:A", "G:B / O:A / S:B"),
        )

    def test_representative_buttons_emit_range_specific_observation(self) -> None:
        emitted = []
        self.panel.representative_requested.connect(emitted.append)
        self.panel.set_summary(self.summary)
        self.panel.set_layer("combination")

        self.panel.select_row(self.summary.rows_for_layer("combination")[0].key)
        self.panel.btn_first_representative.click()
        self.assertEqual(emitted[-1][0], "before")
        self.assertEqual(emitted[-1][3], 0)
        self.assertFalse(self.panel.btn_second_representative.isEnabled())

        self.panel.select_row(self.summary.rows_for_layer("combination")[1].key)
        self.panel.btn_second_representative.click()
        self.assertEqual(emitted[-1][0], "after")
        self.assertEqual(emitted[-1][3], 2)

    def test_plots_show_m3_m6_orientation_and_stacking_data(self) -> None:
        self.panel.set_summary(self.summary)

        self.assertEqual(self.panel.geometry_point_counts(), (2, 2))
        self.assertEqual(self.panel.orientation_prototype_counts(), (4, 1))
        self.assertEqual(
            self.panel.stacking_share_values(),
            ((100.0, 0.0), (0.0, 100.0)),
        )
        self.assertEqual(
            self.panel.geometry_axis_labels(),
            ("Lattice angle [deg]", "Molecules"),
        )
        self.assertEqual(
            self.panel.geometry_legend_labels(),
            ("Type A", "Type B", "Range before", "Range after"),
        )
        self.assertEqual(
            self.panel.orientation_legend_labels(),
            ("before", "after"),
        )
        self.assertEqual(
            self.panel.stacking_legend_labels(),
            ("before", "after"),
        )

    def test_settings_emit_explicit_features_and_validate_phase_dependency(
        self,
    ) -> None:
        requested = []
        self.panel.classification_requested.connect(requested.append)
        self.panel.chk_stacking_mode.setChecked(True)
        self.panel.chk_stacking_phase.setChecked(True)
        self.panel.run_button.click()

        self.assertEqual(len(requested), 1)
        settings = requested[0]
        self.assertEqual(
            settings.stacking_features,
            ("pattern", "mode", "phase"),
        )
        self.assertEqual(
            settings.geometry_features,
            ("dominant_symmetry", "theta3_lattice", "theta6_lattice"),
        )

        self.panel.chk_stacking_mode.setChecked(False)

        self.assertFalse(self.panel.chk_stacking_phase.isChecked())
        self.assertFalse(self.panel.chk_stacking_phase.isEnabled())

    def test_set_settings_round_trip_restores_every_control(self) -> None:
        settings = MolecularOrderTypeClassificationSettings(
            geometry_features=("dominant_symmetry", "theta6_lattice"),
            stacking_features=("pattern", "mode", "phase"),
            lattice_orientation_tolerance_deg=3.5,
            molecular_orientation_tolerance_deg=8.0,
            minimum_observations_per_type=4,
        )

        self.panel.set_settings(settings)

        self.assertEqual(self.panel.settings(), settings)

    def test_position_dialog_hosts_panel_and_forwards_requests(self) -> None:
        dialog = PositionAnalysisDialog()
        requested = []
        dialog.molecular_order_type_classification_requested.connect(
            requested.append
        )
        try:
            tab_labels = tuple(
                dialog.tabs.tabText(index)
                for index in range(dialog.tabs.count())
            )
            self.assertIn("Order Hierarchy", tab_labels)

            dialog.set_molecular_order_type_summary(self.summary)
            dialog.molecular_order_types_panel.run_button.click()

            self.assertIs(
                dialog.molecular_order_types_panel.summary(),
                self.summary,
            )
            self.assertEqual(len(requested), 1)
        finally:
            dialog.close()
            dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
