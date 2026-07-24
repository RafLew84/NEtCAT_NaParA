import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis import (
    MolecularOrientationMeasurement,
    MolecularOrientationProvenance,
    MolecularStackingInspection,
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

    def test_stacking_layers_have_independent_visibility_and_opacity(self) -> None:
        self.panel = MolecularOrientationPanel()
        changed = []
        requested = []
        self.panel.orientation_view_changed.connect(
            lambda: changed.append("orientation")
        )
        self.panel.ab_states_view_changed.connect(
            lambda: changed.append("ab")
        )
        self.panel.stacking_subdomains_view_changed.connect(
            lambda: changed.append("subdomains")
        )
        self.panel.analyze_stacking_requested.connect(
            lambda: requested.append("analyze")
        )

        self.panel.set_stacking_context(
            can_analyze=True,
            computed=True,
            running=False,
            status_text="2 frames | 1 domain",
        )
        self.panel.chk_show_axes.setChecked(False)
        self.panel.slider_orientation_opacity.setValue(45)
        self.panel.chk_show_ab_states.setChecked(False)
        self.panel.chk_show_ab_states.setChecked(True)
        self.panel.slider_ab_states_opacity.setValue(55)
        self.panel.chk_show_stacking_subdomains.setChecked(False)
        self.panel.chk_show_stacking_subdomains.setChecked(True)
        self.panel.slider_stacking_subdomains_opacity.setValue(35)
        self.panel.btn_analyze_stacking.click()

        self.assertTrue(self.panel.btn_analyze_stacking.isEnabled())
        self.assertFalse(self.panel.orientation_overlay_visible())
        self.assertEqual(self.panel.orientation_opacity_percent(), 45)
        self.assertTrue(self.panel.ab_states_overlay_visible())
        self.assertEqual(self.panel.ab_states_opacity_percent(), 55)
        self.assertTrue(self.panel.stacking_subdomains_overlay_visible())
        self.assertEqual(
            self.panel.stacking_subdomains_opacity_percent(),
            35,
        )
        self.assertEqual(
            changed,
            [
                "orientation",
                "orientation",
                "ab",
                "ab",
                "ab",
                "subdomains",
                "subdomains",
                "subdomains",
            ],
        )
        self.assertEqual(requested, ["analyze"])
        self.assertEqual(
            self.panel.lbl_stacking_status.text(),
            "2 frames | 1 domain",
        )

    def test_selected_stacking_molecule_shows_hierarchical_audit(self) -> None:
        self.panel = MolecularOrientationPanel()
        self.panel.set_stacking_context(
            can_analyze=True,
            computed=True,
            running=False,
            status_text="computed",
        )

        self.panel.set_stacking_inspection(
            MolecularStackingInspection(
                frame_index=3,
                source_id="mask-12",
                parent_lattice_domain_id="domain-4",
                subdomain_id="domain-4:subdomain-2",
                state_label="B",
                pattern="ABAB",
                mode="between_rows",
                phase="BABA",
                axis_candidate_index=1,
                axis_angle_deg=31.5,
                prototype_a_angle_deg=22.0,
                prototype_b_angle_deg=82.0,
                score=0.91,
                confidence=0.88,
                coverage_fraction=0.75,
                qc_reasons=("phase_boundary",),
                parent_pattern="mixed",
                parent_score=0.76,
                parent_confidence=0.71,
                parent_coverage_fraction=0.82,
                parent_qc_reasons=(
                    "phase_boundary",
                    "incomplete_coverage",
                ),
            )
        )

        text = self.panel.lbl_stacking_selection.text()
        self.assertIn("Parent: domain-4 | mixed", text)
        self.assertIn("Parent score: 0.760", text)
        self.assertIn(
            "Parent QC: phase_boundary, incomplete_coverage",
            text,
        )
        self.assertIn(
            "Subdomain: domain-4:subdomain-2 | ABAB",
            text,
        )
        self.assertIn("A/B state: B", text)
        self.assertIn("between_rows/BABA", text)
        self.assertIn("31.5 deg", text)
        self.assertIn("A 22.0 deg, B 82.0 deg", text)
        self.assertIn("Subdomain score: 0.910", text)
        self.assertIn("coverage 0.750", text)
        self.assertIn("Subdomain QC: phase_boundary", text)


if __name__ == "__main__":
    unittest.main()
