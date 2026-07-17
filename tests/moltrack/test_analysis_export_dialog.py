import os
import unittest
from pathlib import Path

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularFrameRangeSelection,
    MolecularM6OrientationAnalysisSettings,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.dialogs import ExportAnalysisDialog
else:  # pragma: no cover - optional outside target GUI env
    ExportAnalysisDialog = None


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for MolTrack GUI tests")
class ExportAnalysisDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        if hasattr(self, "dialog"):
            self.dialog.close()
            self.dialog.deleteLater()
            self.__class__._app.processEvents()

    def test_current_frame_context_disables_options_that_require_range_comparison(self) -> None:
        self.dialog = ExportAnalysisDialog(
            frame_count=5,
            active_frame_index=2,
            source_view="raw",
            use_segmentation_centroids=False,
            intensity_metric="mean",
            intensity_unit="a.u.",
            background_inner_radius_px=1,
            background_outer_radius_px=3,
            density_grid_shape=(8, 12),
            selected_ranges=None,
        )

        self.assertEqual(self.dialog.windowTitle(), "Export Analysis")
        self.assertEqual(
            self.dialog.scope_options(),
            (
                ("current_frame", True),
                ("selected_ranges", False),
                ("full_working_series", True),
            ),
        )
        self.assertEqual(self.dialog.selected_scope(), "current_frame")
        self.assertEqual(
            self.dialog.analysis_context(),
            {
                "source_view": "raw",
                "centroid_mode": "bbox_centers",
                "intensity_metric": "mean",
            },
        )
        self.assertEqual(
            self.dialog.content_option_states(),
            {
                "tables": (True, True),
                "spatial_grids": (False, False),
                "plots": (False, True),
            },
        )
        self.assertEqual(
            self.dialog.comparison_requirement_message(),
            "Run Compare ranges in Position Analysis to export selected ranges or spatial grids.",
        )
        self.assertFalse(self.dialog.is_export_enabled())
        self.assertEqual(self.dialog.validation_message(), "Choose a destination path.")

        self.dialog.set_destination_path(Path("current-frame-analysis"))

        self.assertTrue(self.dialog.is_export_enabled())
        self.assertEqual(self.dialog.validation_message(), "")

    def test_completed_comparison_maps_selected_range_options_to_export_settings(self) -> None:
        selection = MolecularFrameRangeSelection(
            frame_count=5,
            source_view="expanded_aligned",
            first_range=MolecularFrameRange("before", 0, 1),
            second_range=MolecularFrameRange("after", 3, 4),
        )
        m6_settings = MolecularM6OrientationAnalysisSettings(q_seed=0.7)
        self.dialog = ExportAnalysisDialog(
            frame_count=5,
            active_frame_index=3,
            source_view="expanded_aligned",
            use_segmentation_centroids=True,
            intensity_metric="max",
            intensity_unit="nA",
            background_inner_radius_px=2,
            background_outer_radius_px=5,
            density_grid_shape=(3, 4),
            selected_ranges=selection,
            m6_orientation_settings=m6_settings,
        )

        self.dialog.set_scope("selected_ranges")
        self.dialog.set_include_tables(False)
        self.dialog.set_include_spatial_grids(True)
        self.dialog.set_include_plots(True)
        self.dialog.set_package_format("zip")
        self.dialog.set_destination_path(Path("comparison.zip"))

        self.assertEqual(
            self.dialog.scope_options(),
            (
                ("current_frame", True),
                ("selected_ranges", True),
                ("full_working_series", True),
            ),
        )
        self.assertEqual(
            self.dialog.content_option_states(),
            {
                "tables": (False, True),
                "spatial_grids": (True, True),
                "plots": (True, True),
            },
        )
        self.assertEqual(self.dialog.comparison_requirement_message(), "")
        settings = self.dialog.export_settings()
        self.assertEqual(settings.scope, "selected_ranges")
        self.assertEqual(settings.destination, Path("comparison.zip"))
        self.assertEqual(settings.package_format, "zip")
        self.assertFalse(settings.include_tables)
        self.assertTrue(settings.include_spatial_grids)
        self.assertTrue(settings.include_plots)
        self.assertEqual(settings.active_frame_index, 3)
        self.assertEqual(settings.source_view, "expanded_aligned")
        self.assertTrue(settings.use_segmentation_centroids)
        self.assertEqual(settings.intensity_metric, "max")
        self.assertEqual(settings.intensity_unit, "nA")
        self.assertEqual(settings.background_inner_radius_px, 2)
        self.assertEqual(settings.background_outer_radius_px, 5)
        self.assertEqual(settings.density_grid_shape, (3, 4))
        self.assertIs(settings.selected_ranges, selection)
        self.assertIs(settings.m6_orientation_settings, m6_settings)


if __name__ == "__main__":
    unittest.main()
