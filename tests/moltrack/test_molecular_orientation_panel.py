import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis import (
    MolecularOrientationMeasurement,
    MolecularOrientationProvenance,
)

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.widgets import MolecularOrientationPanel
else:  # pragma: no cover - optional outside target GUI env
    MolecularOrientationPanel = None


def _corrected_measurement() -> MolecularOrientationMeasurement:
    automatic = MolecularOrientationMeasurement(
        measurement_id="orientation:segmentation:mask-1",
        status="available",
        angle_deg=25.0,
        periodicity_deg=180.0,
        confidence=0.8,
        method="mask_principal_axis",
        patch_shape_px=(12, 14),
        provenance=MolecularOrientationProvenance(
            source_file_name="movie.mpp",
            source_file_sha256="a" * 64,
            source_session_file_name=None,
            source_session_sha256=None,
            frame_index=0,
            source_view="raw",
            source_kind="segmentation",
            source_id="mask-1",
            patch_bbox_xyxy=(3.0, 4.0, 17.0, 16.0),
            orientation_reference="sample_x_axis_counterclockwise",
        ),
    )
    return automatic.with_manual_correction(
        status="available",
        angle_deg=35.0,
        confidence=1.0,
        reviewer="MolTrack user",
    )


@unittest.skipUnless(
    QApplication is not None,
    "PyQt6 is required for molecular orientation panel tests",
)
class MolecularOrientationPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        self.panel.close()
        self.panel.deleteLater()
        self.__class__._app.processEvents()

    def test_panel_exposes_frame_scopes_and_auditable_manual_controls(self) -> None:
        self.panel = MolecularOrientationPanel()
        emitted = []
        self.panel.estimate_range_requested.connect(
            lambda end_frame: emitted.append(end_frame)
        )
        self.panel.rotate_requested.connect(
            lambda delta: emitted.append(delta)
        )

        self.panel.set_context(
            frame_count=10,
            active_frame_index=3,
            current_segmentation_count=2,
            running=False,
        )
        self.panel.set_measurement(_corrected_measurement())

        self.assertTrue(self.panel.btn_estimate_current.isEnabled())
        self.assertTrue(self.panel.btn_estimate_range.isEnabled())
        self.assertTrue(self.panel.btn_estimate_all.isEnabled())
        self.assertEqual(self.panel.sp_range_end_frame.minimum(), 4)
        self.assertEqual(self.panel.sp_range_end_frame.maximum(), 10)
        self.assertIn("35.0 deg", self.panel.lbl_result.text())
        self.assertIn("manual_correction", self.panel.lbl_result.text())
        self.assertIn("automatic 25.0 deg", self.panel.lbl_result.text())
        self.assertTrue(self.panel.btn_reset.isEnabled())

        self.panel.sp_range_end_frame.setValue(8)
        self.panel.btn_estimate_range.click()
        self.panel.sp_rotate_step_deg.setValue(7.5)
        self.panel.btn_rotate_positive.click()

        self.assertEqual(emitted, [7, 7.5])


if __name__ == "__main__":
    unittest.main()
