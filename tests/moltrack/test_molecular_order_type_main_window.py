import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularFrameRangeAnalysisScope,
    MolecularOrderTypeClassificationSettings,
)
from moltrack.core import MolTrackImageSeries
from nanotrack.core import STMSequenceMetadata
from test_molecular_order_type_classifier import _domain_frame, _hierarchy

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui import MolTrackMainWindow
    from moltrack.ui.molecular_order_type_worker import (
        analyze_molecular_order_types,
    )


def _comparison_result():
    hierarchy = _hierarchy(
        _domain_frame(0),
        _domain_frame(
            2,
            symmetry="sixfold",
            theta3_deg=None,
            theta6_deg=30.0,
            orientation_angles=(40.0,),
            stacking_pattern="uniform",
        ),
    )
    scope = MolecularFrameRangeAnalysisScope(
        analysis_mode="compare_ranges",
        frame_count=3,
        source_view="expanded_aligned",
        ranges=(
            MolecularFrameRange("before", 0, 0),
            MolecularFrameRange("after", 2, 2),
        ),
    )
    return analyze_molecular_order_types(
        hierarchy,
        scope,
        MolecularOrderTypeClassificationSettings(),
    )


@unittest.skipUnless(
    QApplication is not None,
    "PyQt6 is required for MolTrack GUI tests",
)
class MolecularOrderTypeMainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        if hasattr(self, "window"):
            self.window.close()
            self.window.deleteLater()
            self.__class__._app.processEvents()

    def setUp(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        self.series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((3, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=8,
                pixels_y=8,
                size_nm_x=80.0,
                size_nm_y=80.0,
            ),
        )
        self.window.set_image_series(self.series)

    def test_representative_navigation_selects_frame_and_exact_m6_component(
        self,
    ) -> None:
        result = _comparison_result()
        display_token = object()
        controller = self.window._molecular_order_type_controller
        controller._context_token = display_token
        controller._result = result
        row = result.summary.rows_for_layer("combination")[1]
        observation_key = row.representative_for_range("after")
        domain = result.hierarchy.frame_for_index(
            observation_key[3]
        ).domain_for_id(observation_key[4])
        current_analysis = object()

        with patch.object(
            self.window,
            "_current_molecular_stacking_display_result",
            return_value=display_token,
        ), patch.object(
            self.window,
            "_sync_molecular_stacking_panel",
        ), patch.object(
            self.window,
            "_show_current_frame",
        ), patch.object(
            self.window,
            "_current_m6_analysis_result",
            return_value=current_analysis,
        ), patch.object(
            self.window,
            "_show_selected_m6_component",
        ) as show_component:
            self.window._on_molecular_order_representative_requested(
                observation_key
            )

        self.assertEqual(self.series.active_frame_index, 2)
        show_component.assert_called_once_with(
            current_analysis,
            domain.lattice_domain.source_ids,
        )

    def test_worker_error_remains_visible_after_running_cleanup(self) -> None:
        dialog = unittest.mock.Mock()
        self.window._position_analysis_dialog = dialog
        self.window._molecular_order_type_error_message = "classification failed"

        with patch.object(
            self.window,
            "_current_molecular_stacking_display_result",
            return_value=object(),
        ):
            self.window._sync_molecular_order_type_panel()

        dialog.set_molecular_order_type_summary.assert_called_once_with(
            None,
            status_message="classification failed",
        )

    def test_order_hierarchy_tab_is_not_persisted_as_analysis_state(self) -> None:
        self.window._on_position_analysis_requested()
        dialog = self.window.position_analysis_dialog()
        dialog.activate_analysis_tab("Order Hierarchy")

        ui_state = self.window._current_ui_state()

        self.assertEqual(
            ui_state["position_analysis"]["active_tab"],
            "Current frame",
        )


if __name__ == "__main__":
    unittest.main()
