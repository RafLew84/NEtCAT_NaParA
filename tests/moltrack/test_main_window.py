import os
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from moltrack.analysis import (
    MolecularOrientationBatchResult,
    MolecularOrientationEstimationProgress,
    MolecularOrientationMeasurement,
    MolecularOrientationProvenance,
    MolecularOrientationStore,
    MolecularStackingDisplayResult,
    MolecularFrameRange,
    MolecularFrameRangeSelection,
    MolecularIntensityMeasurement,
    MolecularM6OrientationAnalysisSettings,
    MolecularM6SessionState,
    MolecularM6ViewSettings,
    TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET,
    analyze_molecular_stacking,
    build_molecular_orientation_prototype_analysis,
    build_molecular_position_plot_data,
    compare_molecular_frame_ranges,
)
from moltrack.core import (
    MolecularCentroid,
    MolecularDetection,
    MolecularDetectionSet,
    MolecularSegmentation,
    MolecularSegmentationSet,
    MolTrackImageSeries,
    MolTrackPositionAnalysisRange,
    MolTrackPositionAnalysisState,
    MolTrackRegistrationFrameResult,
    MolTrackRegistrationResultSet,
    MolTrackRegistrationSettings,
)
from moltrack.persistence import (
    AnalysisExportProgress,
    AnalysisExportSettings,
    MolTrackStateSaveProgress,
    load_moltrack_session,
    save_moltrack_session,
)
from moltrack.sam2 import MolTrackSam2PromptRejection
from moltrack.sam3 import (
    MolTrackSam3Preview,
    MolTrackSam3PreviewProposal,
    MolTrackSam3Proposal,
    build_moltrack_sam3_preview,
)
from nanotrack.core import STMSequenceMetadata
from test_molecular_stacking_analysis import _prototype_analysis

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from PyQt6.QtCore import QThread
    from PyQt6.QtWidgets import (
        QDialog,
        QFileDialog,
        QGroupBox,
        QMessageBox,
        QPushButton,
        QScrollArea,
    )

    from moltrack.ui import MolTrackMainWindow
    from moltrack.ui.molecular_stacking_controller import (
        build_molecular_stacking_input_frames,
    )
    from moltrack.ui.dialogs import PositionAnalysisDialog
else:  # pragma: no cover - optional outside target GUI env
    QFileDialog = None
    QMessageBox = None
    MolTrackMainWindow = None
    build_molecular_stacking_input_frames = None


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for MolTrack GUI tests")
class MolTrackMainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        if hasattr(self, "window"):
            self.window.close()
            self.window.deleteLater()
            self.__class__._app.processEvents()

    def process_events_until(self, condition, *, timeout_s: float = 3.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self.__class__._app.processEvents()
            if condition():
                return
            time.sleep(0.01)
        self.fail("Timed out waiting for Qt event-loop condition.")

    def sam2_dialog_factory(
        self,
        *,
        threshold: float = 0.5,
        checkpoint_path: Path | None = None,
        existing_policy: str = "replace",
        keep_largest_component: bool = False,
        min_mask_area_px: int = 0,
        accepted: bool = True,
        calls=None,
    ):
        class FakeSam2SettingsDialog:
            def __init__(self, default_checkpoint_path=None) -> None:
                self._default_checkpoint_path = default_checkpoint_path

            def exec(self):
                if accepted:
                    return QDialog.DialogCode.Accepted
                return QDialog.DialogCode.Rejected

            def mask_probability_threshold(self) -> float:
                return float(threshold)

            def checkpoint_path(self):
                if checkpoint_path is not None:
                    return checkpoint_path
                return self._default_checkpoint_path

            def existing_sam2_masks_policy(self) -> str:
                return str(existing_policy)

            def keep_largest_component(self) -> bool:
                return bool(keep_largest_component)

            def min_mask_area_px(self) -> int:
                return int(min_mask_area_px)

        def factory(**kwargs):
            if calls is not None:
                calls.append(dict(kwargs))
            return FakeSam2SettingsDialog(default_checkpoint_path=kwargs.get("selected_checkpoint_path"))

        return factory

    def load_single_bbox_series(self, *, frame_shape=(4, 4), detection_id: str = "bbox-1"):
        height, width = frame_shape
        frames = np.arange(height * width, dtype=np.float32).reshape(1, height, width)
        detections = MolecularDetectionSet(frame_count=1)
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(1, 1, min(3, width), min(3, height)),
            confidence=0.9,
            source_view="raw",
            detection_id=detection_id,
        )
        detections.set_detections(0, [detection], source_view="raw", frame_shape=frame_shape)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=width, pixels_y=height),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.select_molecular_detection_at_pixel(2.0, 2.0)
        self.__class__._app.processEvents()
        return series, detection, frames

    def test_empty_workspace_exposes_file_actions_and_disables_frame_navigation(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])

        self.assertEqual(
            tuple(action.text() for action in self.window.menuBar().actions()),
            ("File", "Parameters"),
        )
        self.assertEqual(self.window.parameters_menu.title(), "Parameters")
        self.assertEqual(self.window.m6_presets_menu.title(), "M6 presets")
        self.assertEqual(self.window.action_m6_preset_ttmapp.text(), "TTMAPP")
        self.assertFalse(self.window.action_m6_preset_ttmapp.isEnabled())
        self.assertEqual(self.window.action_open_stm.text(), "Open STM...")
        self.assertEqual(self.window.action_open_stm_reverse.text(), "Open STM Reverse...")
        self.assertEqual(self.window.action_open_state.text(), "Open State...")
        self.assertEqual(self.window.action_save_state.text(), "Save State...")
        self.assertEqual(self.window.action_save_state_as.text(), "Save State As...")
        self.assertEqual(self.window.lbl_frame.text(), "Frame: - / -")
        self.assertFalse(self.window.slider_frame.isEnabled())
        self.assertFalse(self.window.btn_remove_current_frame.isEnabled())
        self.assertTrue(self.window.action_open_state.isEnabled())
        self.assertFalse(self.window.action_save_state.isEnabled())
        self.assertFalse(self.window.action_save_state_as.isEnabled())
        self.assertEqual(self.window.metadata_panel.title(), "Metadata")
        self.assertEqual(self.window.yolo_group.title(), "YOLO Detection")
        self.assertEqual(self.window.cmb_yolo_model.count(), 0)
        self.assertIn("No YOLO models found in nanotrack/yolo_models", self.window.lbl_yolo_models.text())
        self.assertFalse(self.window.btn_yolo_detect_current.isEnabled())
        self.assertEqual(self.window.btn_yolo_detect_range.text(), "Detect Frames In Range")
        self.assertFalse(self.window.sp_yolo_range_end_frame.isEnabled())
        self.assertFalse(self.window.btn_yolo_detect_range.isEnabled())
        self.assertEqual(self.window.btn_yolo_detect_all_frames.text(), "Detect All Frames")
        self.assertFalse(self.window.btn_yolo_detect_all_frames.isEnabled())
        self.assertFalse(self.window.btn_yolo_clear_current.isEnabled())
        self.assertIn("current 0", self.window.lbl_yolo_status.text())
        self.assertIn("series 0", self.window.lbl_yolo_status.text())
        self.assertEqual(self.window.bbox_resize_group.title(), "BBox Resize")
        self.assertEqual(self.window.btn_bbox_increase.text(), "Increase BBoxes")
        self.assertEqual(self.window.btn_bbox_decrease.text(), "Decrease BBoxes")
        self.assertEqual(self.window.btn_bbox_reset.text(), "Reset BBoxes")
        self.assertFalse(self.window.btn_bbox_increase.isEnabled())
        self.assertFalse(self.window.btn_bbox_decrease.isEnabled())
        self.assertFalse(self.window.btn_bbox_reset.isEnabled())
        self.assertEqual(self.window.segmentation_group.title(), "Segmentation")
        self.assertEqual(self.window.cmb_segmentation_backend.count(), 2)
        self.assertEqual(self.window.cmb_segmentation_backend.currentText(), "SAM2")
        self.assertFalse(self.window.cmb_segmentation_backend.isEnabled())
        self.assertAlmostEqual(self.window.sp_sam2_mask_threshold.value(), 0.5)
        self.assertFalse(self.window.sp_sam2_mask_threshold.isEnabled())
        self.assertEqual(self.window.btn_sam2_segment_selected.text(), "Segment Selected BBox")
        self.assertFalse(self.window.btn_sam2_segment_selected.isEnabled())
        self.assertEqual(self.window.btn_sam2_segment_all_current.text(), "Segment All BBoxes In Image")
        self.assertFalse(self.window.btn_sam2_segment_all_current.isEnabled())
        self.assertEqual(self.window.cmb_sam3_model.currentText(), "facebook/sam3")
        self.assertFalse(self.window.cmb_sam3_model.isEnabled())
        self.assertEqual(self.window.cmb_sam3_prompt_source.currentText(), "Active selected BBox")
        self.assertFalse(self.window.cmb_sam3_prompt_source.isEnabled())
        self.assertEqual(self.window.btn_sam3_run_concepts.text(), "Run SAM3 Concepts")
        self.assertFalse(self.window.btn_sam3_run_concepts.isEnabled())
        self.assertEqual(self.window.btn_sam3_commit_proposals.text(), "Commit Proposals")
        self.assertFalse(self.window.btn_sam3_commit_proposals.isEnabled())
        self.assertEqual(self.window.lbl_segmentation_status.text(), "No series loaded")

    def test_molecular_orientation_runs_async_and_supports_manual_reset(
        self,
    ) -> None:
        scopes = []

        def orientation_estimator(
            series,
            *,
            frame_indices,
            source_view,
            progress_callback,
            should_cancel,
        ):
            frame_indices = tuple(frame_indices)
            scopes.append(frame_indices)
            measurements = []
            segmentations = [
                segmentation
                for frame_index in frame_indices
                for segmentation in series.molecular_segmentations.get_segmentations(
                    frame_index,
                    source_view=source_view,
                )
            ]
            progress_callback(
                MolecularOrientationEstimationProgress(
                    completed_count=0,
                    total_count=len(segmentations),
                    frame_index=None,
                    source_id=None,
                )
            )
            for completed, segmentation in enumerate(segmentations, start=1):
                measurements.append(
                    MolecularOrientationMeasurement(
                        measurement_id=(
                            "orientation:segmentation:"
                            f"{segmentation.segmentation_id}"
                        ),
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
                            frame_index=segmentation.frame_index,
                            source_view=source_view,
                            source_kind="segmentation",
                            source_id=segmentation.segmentation_id,
                            patch_bbox_xyxy=(3.0, 4.0, 17.0, 16.0),
                            orientation_reference=(
                                "sample_x_axis_counterclockwise"
                            ),
                        ),
                    )
                )
                progress_callback(
                    MolecularOrientationEstimationProgress(
                        completed_count=completed,
                        total_count=len(segmentations),
                        frame_index=segmentation.frame_index,
                        source_id=segmentation.segmentation_id,
                    )
                )
            return MolecularOrientationBatchResult(
                measurements=tuple(measurements),
                failures=(),
                completed_count=len(segmentations),
                total_count=len(segmentations),
            )

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            molecular_orientation_estimator=orientation_estimator,
        )
        masks = MolecularSegmentationSet(frame_count=2)
        mask = np.zeros((20, 20), dtype=bool)
        mask[7:13, 4:16] = True
        for frame_index in range(2):
            masks.add_segmentation(
                MolecularSegmentation(
                    frame_index=frame_index,
                    source_view="raw",
                    bbox_xyxy=(4, 7, 16, 13),
                    mask=mask,
                    origin="sam2",
                    segmentation_id=f"mask-{frame_index}",
                )
            )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 20, 20), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=20,
                pixels_y=20,
                size_nm_x=40.0,
                size_nm_y=40.0,
                scan_angle_deg=0.0,
            ),
            molecular_segmentations=masks,
        )
        self.window.set_image_series(series)
        self.window.select_molecular_segmentation_at_pixel(8.0, 9.0)

        self.window.orientation_panel.btn_estimate_current.click()
        self.process_events_until(
            lambda: not self.window._molecular_orientation_running
        )

        automatic = series.molecular_orientations.get(
            "segmentation",
            "mask-0",
        )
        self.assertEqual(scopes, [(0,)])
        self.assertAlmostEqual(automatic.angle_deg, 25.0)
        self.assertIn(
            "mask_principal_axis",
            self.window.orientation_panel.lbl_result.text(),
        )
        self.assertEqual(
            self.window.viewer.visible_molecular_orientation_axis_count(),
            1,
        )

        self.window.orientation_panel.sp_manual_angle_deg.setValue(42.0)
        self.window.orientation_panel.btn_set_angle.click()
        corrected = series.molecular_orientations.get(
            "segmentation",
            "mask-0",
        )
        self.assertTrue(corrected.is_manually_corrected)
        self.assertAlmostEqual(corrected.angle_deg, 42.0)
        self.assertAlmostEqual(
            corrected.manual_correction.original_result.angle_deg,
            25.0,
        )

        self.window.orientation_panel.btn_reset.click()
        reset = series.molecular_orientations.get(
            "segmentation",
            "mask-0",
        )
        self.assertFalse(reset.is_manually_corrected)
        self.assertAlmostEqual(reset.angle_deg, 25.0)

        self.window.orientation_panel.sp_range_end_frame.setValue(2)
        self.window.orientation_panel.btn_estimate_range.click()
        self.process_events_until(
            lambda: not self.window._molecular_orientation_running
        )
        self.window.orientation_panel.btn_estimate_all.click()
        self.process_events_until(
            lambda: not self.window._molecular_orientation_running
        )

        self.assertEqual(scopes, [(0,), (0, 1), (0, 1)])
        self.assertEqual(series.molecular_orientations.measurement_count, 2)

        edited_mask = mask.copy()
        edited_mask[7, 4] = False
        self.window._remember_mask_edit_state(
            masks.get_segmentation("mask-0")
        )
        self.window._apply_segmentation_mask_update(
            masks.get_segmentation("mask-0"),
            edited_mask,
        )
        self.window._show_current_frame()

        self.assertIsNone(
            series.molecular_orientations.get(
                "segmentation",
                "mask-0",
            )
        )
        series.molecular_orientations.put(automatic)
        self.assertTrue(self.window.undo_last_mask_edit())
        self.assertIsNone(
            series.molecular_orientations.get(
                "segmentation",
                "mask-0",
            )
        )
        self.assertEqual(
            self.window.orientation_panel.lbl_result.text(),
            "No orientation selected",
        )
        series.molecular_orientations.put(automatic)
        masks.remove_segmentation("mask-0")
        self.window._prune_orphaned_molecular_orientations()
        self.assertIsNone(
            series.molecular_orientations.get(
                "segmentation",
                "mask-0",
            )
        )

    def test_stacking_analysis_runs_once_and_view_changes_only_render(
        self,
    ) -> None:
        frames, _prototypes = _prototype_analysis(
            state_for_site=lambda row, column: (row + column) % 2,
        )
        calls = []

        def stacking_analyzer(input_frames):
            input_frames = tuple(input_frames)
            calls.append(input_frames)
            prototypes = build_molecular_orientation_prototype_analysis(
                input_frames
            )
            return MolecularStackingDisplayResult(
                frames=input_frames,
                prototype_analysis=prototypes,
                stacking_analysis=analyze_molecular_stacking(
                    input_frames,
                    prototypes,
                ),
            )

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            molecular_stacking_analyzer=stacking_analyzer,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 20, 20), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=20,
                pixels_y=20,
                size_nm_x=40.0,
                size_nm_y=40.0,
            ),
        )
        self.window.set_image_series(series)
        completed_m6_context = object()
        self.window._m6_completed_context = completed_m6_context

        with patch.object(
            self.window,
            "_molecular_stacking_input_frames",
            return_value=frames,
        ), patch.object(
            self.window,
            "_molecular_stacking_inputs_available",
            return_value=True,
        ), patch.object(
            self.window,
            "_current_m6_analysis_result",
            return_value=None,
        ):
            self.window._sync_molecular_orientation_panel()
            self.window.orientation_panel.btn_analyze_stacking.click()
            self.process_events_until(
                lambda: not (
                    self.window._molecular_stacking_controller.running
                )
            )
            self.window.orientation_panel.chk_show_ab_states.setChecked(
                False
            )
            self.window.orientation_panel.slider_ab_states_opacity.setValue(
                40
            )
            self.window.orientation_panel.chk_show_stacking_subdomains.setChecked(
                False
            )

        self.assertEqual(calls, [frames])
        self.assertIs(
            self.window._molecular_stacking_controller.bound_m6_context,
            completed_m6_context,
        )
        self.assertIsInstance(
            self.window._current_molecular_stacking_display_result(),
            MolecularStackingDisplayResult,
        )
        self.assertIn(
            "2 frame",
            self.window.orientation_panel.lbl_stacking_status.text(),
        )

    def test_stacking_input_adapter_joins_m6_rows_with_saved_orientations(
        self,
    ) -> None:
        frames, _prototypes = _prototype_analysis(
            state_for_site=lambda row, column: (row + column) % 2,
        )
        store = MolecularOrientationStore(frame_count=2)
        for frame in frames:
            for measurement in frame.measurements:
                store.put(measurement)
        frame_results = tuple(
            SimpleNamespace(
                frame_index=frame.frame_index,
                source_view="expanded_aligned",
                m6_orientation_analysis=SimpleNamespace(
                    lattice_row_assignment_analysis=frame.row_assignment,
                ),
            )
            for frame in frames
        )

        collected = build_molecular_stacking_input_frames(
            frame_results,
            store,
            source_view="expanded_aligned",
        )

        self.assertEqual(
            tuple(frame.frame_index for frame in collected),
            (0, 1),
        )
        self.assertEqual(
            collected[0].row_assignment,
            frames[0].row_assignment,
        )
        self.assertEqual(
            collected[0].measurements,
            frames[0].measurements,
        )

    def test_selected_segmentation_accepts_first_manual_orientation(
        self,
    ) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        mask = np.zeros((20, 20), dtype=bool)
        mask[7:13, 4:16] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(4, 7, 16, 13),
                mask=mask,
                origin="sam2",
                segmentation_id="manual-angle-mask",
            )
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "movie.mpp"
            source_path.write_bytes(b"manual orientation source")
            series = MolTrackImageSeries(
                source_path=source_path,
                raw_frames=np.zeros((1, 20, 20), dtype=np.float32),
                metadata=STMSequenceMetadata(
                    pixels_x=20,
                    pixels_y=20,
                    size_nm_x=40.0,
                    size_nm_y=40.0,
                    scan_angle_deg=0.0,
                ),
                molecular_segmentations=segmentations,
            )
            original_mask = mask.copy()
            original_bbox = segmentations.get_segmentation(
                "manual-angle-mask"
            ).bbox_xyxy
            self.window.set_image_series(series)
            self.window.select_molecular_segmentation_at_pixel(8.0, 9.0)

            self.assertTrue(
                self.window.orientation_panel.btn_set_angle.isEnabled()
            )
            self.window.orientation_panel.sp_manual_angle_deg.setValue(55.0)
            self.window.orientation_panel.btn_set_angle.click()

        measurement = series.molecular_orientations.get(
            "segmentation",
            "manual-angle-mask",
        )
        self.assertEqual(measurement.method, "manual")
        self.assertAlmostEqual(measurement.angle_deg, 55.0)
        np.testing.assert_array_equal(
            segmentations.get_segmentation("manual-angle-mask").mask,
            original_mask,
        )
        self.assertEqual(
            segmentations.get_segmentation("manual-angle-mask").bbox_xyxy,
            original_bbox,
        )

    def test_ttmapp_parameter_preset_updates_m6_dialog_and_session_configuration(self) -> None:
        previous_settings = MolecularM6OrientationAnalysisSettings(
            first_shell_r_min_nm=1.5,
            first_shell_r_max_nm=2.5,
        )
        previous_view_settings = MolecularM6ViewSettings(
            overlay_mode="orientation",
            overlay_opacity_percent=37,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=8,
                pixels_y=8,
                size_nm_x=800.0,
                size_nm_y=800.0,
            ),
            m6_analysis_state=MolecularM6SessionState(
                enabled=True,
                source_view="raw",
                use_segmentation_centroids=False,
                settings=previous_settings,
                view_settings=previous_view_settings,
            ),
        )
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()

        self.assertTrue(self.window.action_m6_preset_ttmapp.isEnabled())
        self.window.action_m6_preset_ttmapp.trigger()

        dialog = self.window.position_analysis_dialog()
        self.assertEqual(
            dialog.m6_analysis_settings(),
            TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET,
        )
        self.assertEqual(
            series.m6_analysis_state.settings,
            TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET,
        )
        self.assertFalse(series.m6_analysis_state.enabled)
        self.assertEqual(series.m6_analysis_state.source_view, "raw")
        self.assertFalse(series.m6_analysis_state.use_segmentation_centroids)
        self.assertEqual(series.m6_analysis_state.view_settings, previous_view_settings)
        self.assertIn("TTMAPP", self.window.statusBar().currentMessage())

    def test_ttmapp_parameter_preset_contains_validated_dataset_values(self) -> None:
        settings = TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET

        self.assertEqual(settings.duplicate_max_distance_nm, 10.0)
        self.assertEqual(settings.first_shell_r_min_nm, 30.0)
        self.assertEqual(settings.first_shell_r_max_nm, 70.0)
        self.assertEqual(settings.footprint_support_radius_nm, 35.0)
        self.assertEqual(settings.min_neighbors_for_local_order, 3)
        self.assertEqual(settings.min_neighbors_for_seed, 5)
        self.assertEqual(settings.min_ordered_component_size, 3)
        self.assertEqual(settings.min_seed_size, 5)
        self.assertEqual(settings.min_domain_size, 12)
        self.assertEqual(settings.gr_bin_width_nm, 5.0)
        self.assertEqual(settings.gr_max_nm, 250.0)

    def test_ttmapp_parameter_preset_applies_before_position_dialog_is_opened(self) -> None:
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        self.window.set_image_series(series)

        self.window.action_m6_preset_ttmapp.trigger()

        self.assertIsNone(self.window.position_analysis_dialog())
        self.assertEqual(
            series.m6_analysis_state.settings,
            TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET,
        )
        self.window.btn_position_analysis.click()
        self.assertEqual(
            self.window.position_analysis_dialog().m6_analysis_settings(),
            TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET,
        )

    def test_right_control_panel_is_scrollable_and_contains_control_groups(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])

        scroll_area = self.window.findChild(QScrollArea, "moltrack_right_controls_scroll")

        self.assertIsNotNone(scroll_area)
        self.assertTrue(scroll_area.widgetResizable())
        self.assertGreaterEqual(scroll_area.minimumWidth(), 320)
        content = scroll_area.widget()
        self.assertIsNotNone(content)
        self.assertEqual(content.objectName(), "moltrack_right_controls_content")
        self.assertIs(self.window.metadata_panel.parent(), content)
        self.assertIs(self.window.btn_remove_current_frame.parent(), content)

        groups = content.findChildren(QGroupBox)
        self.assertIn(self.window.registration_group, groups)
        self.assertIn(self.window.yolo_group, groups)
        self.assertIn(self.window.bbox_resize_group, groups)
        self.assertIn(self.window.bbox_edit_group, groups)
        self.assertIn(self.window.segmentation_group, groups)
        self.assertIs(self.window.registration_group.parent(), content)
        self.assertIs(self.window.yolo_group.parent(), content)
        self.assertIs(self.window.bbox_resize_group.parent(), content)
        self.assertIs(self.window.bbox_edit_group.parent(), content)
        self.assertIs(self.window.segmentation_group.parent(), content)

    def test_sam3_run_is_blocked_without_positive_prompt(self) -> None:
        class FakeSam3Adapter:
            def __init__(self) -> None:
                self.calls = []

            def segment_prompts(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                raise AssertionError("SAM3 must not run without a positive prompt")

        fake_sam3 = FakeSam3Adapter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam3_adapter=fake_sam3,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(16, dtype=np.float32).reshape(1, 4, 4),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
        )
        self.window.set_image_series(series)

        self.assertEqual(self.window.cmb_segmentation_backend.count(), 2)
        self.window.cmb_segmentation_backend.setCurrentText("SAM3")
        self.__class__._app.processEvents()
        self.assertTrue(self.window.btn_sam3_run_concepts.isEnabled())

        self.window.btn_sam3_run_concepts.click()
        self.__class__._app.processEvents()

        self.assertEqual(fake_sam3.calls, [])
        self.assertIsNone(series.sam3_preview)
        self.assertIn("positive", self.window.lbl_segmentation_status.text())

    def test_sam3_run_concepts_runs_in_worker_and_stores_preview(self) -> None:
        class SlowSam3Adapter:
            def __init__(self) -> None:
                self.calls = []

            def segment_prompts(
                self,
                frame,
                prompts,
                *,
                frame_index,
                source_view,
                model_id,
                score_threshold,
                mask_threshold,
                max_results,
            ):
                self.calls.append(
                    {
                        "frame": frame.copy(),
                        "prompts": tuple(prompts),
                        "frame_index": frame_index,
                        "source_view": source_view,
                        "model_id": model_id,
                        "score_threshold": score_threshold,
                        "mask_threshold": mask_threshold,
                        "max_results": max_results,
                    }
                )
                time.sleep(0.25)
                mask = np.zeros(frame.shape[:2], dtype=bool)
                mask[2:4, 2:4] = True
                return [
                    MolTrackSam3Proposal(
                        frame_index=frame_index,
                        source_view=source_view,
                        bbox_xyxy=(2, 2, 4, 4),
                        score=0.82,
                        mask=mask,
                        polygon_xy=((2, 2), (4, 2), (4, 4), (2, 4)),
                        prompt_detection_ids=("bbox-1",),
                        model_name=model_id,
                    )
                ]

        slow_sam3 = SlowSam3Adapter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam3_adapter=slow_sam3,
        )
        frames = np.arange(1 * 5 * 5, dtype=np.float32).reshape(1, 5, 5)
        detections = MolecularDetectionSet(frame_count=1)
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(1, 1, 3, 3),
            confidence=0.9,
            source_view="raw",
            detection_id="bbox-1",
        )
        detections.set_detections(0, [detection], source_view="raw", frame_shape=(5, 5))
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.cmb_segmentation_backend.setCurrentText("SAM3")
        self.window.cmb_sam3_prompt_source.setCurrentText("All current BBoxes")
        self.window.cmb_sam3_model.setCurrentText("facebook/sam3.1")
        self.window.sp_sam3_score_threshold.setValue(0.41)
        self.window.sp_sam3_mask_threshold.setValue(0.62)
        self.window.sp_sam3_max_results.setValue(12)
        self.__class__._app.processEvents()

        start = time.monotonic()
        self.window.btn_sam3_run_concepts.click()
        elapsed_s = time.monotonic() - start

        self.assertLess(elapsed_s, 0.15)
        self.assertFalse(self.window.btn_sam3_run_concepts.isEnabled())
        self.assertIsNotNone(self.window._sam3_concept_progress_dialog)
        self.assertIn("Running SAM3", self.window.lbl_segmentation_status.text())

        self.process_events_until(
            lambda: series.sam3_preview is not None and series.sam3_preview.proposal_count == 1,
            timeout_s=3.0,
        )

        self.assertEqual(len(slow_sam3.calls), 1)
        call = slow_sam3.calls[0]
        np.testing.assert_array_equal(call["frame"], frames[0])
        self.assertEqual(call["frame_index"], 0)
        self.assertEqual(call["source_view"], "raw")
        self.assertEqual(call["model_id"], "facebook/sam3.1")
        self.assertAlmostEqual(call["score_threshold"], 0.41)
        self.assertAlmostEqual(call["mask_threshold"], 0.62)
        self.assertEqual(call["max_results"], 12)
        self.assertEqual([prompt.detection_id for prompt in call["prompts"]], ["bbox-1"])
        self.assertIsNotNone(series.sam3_preview)
        self.assertEqual(series.sam3_preview.proposals[0].bbox_xyxy, (2.0, 2.0, 4.0, 4.0))
        self.assertEqual(series.molecular_detections.detection_count, 1)
        self.assertIsNone(series.molecular_segmentations)
        self.assertEqual(self.window.viewer.visible_sam3_preview_count(), 1)
        self.assertIsNone(self.window._sam3_concept_progress_dialog)
        self.assertTrue(self.window.btn_sam3_run_concepts.isEnabled())
        self.assertTrue(self.window.btn_sam3_commit_proposals.isEnabled())
        self.assertIn("SAM3 preview", self.window.statusBar().currentMessage())

    def test_sam3_run_concepts_uses_manual_prompt_bboxes_with_labels(self) -> None:
        class FakeSam3Adapter:
            def __init__(self) -> None:
                self.calls = []

            def segment_prompts(
                self,
                frame,
                prompts,
                *,
                frame_index,
                source_view,
                model_id,
                score_threshold,
                mask_threshold,
                max_results,
            ):
                self.calls.append(
                    {
                        "frame": frame.copy(),
                        "prompts": tuple(prompts),
                        "frame_index": frame_index,
                        "source_view": source_view,
                        "model_id": model_id,
                        "score_threshold": score_threshold,
                        "mask_threshold": mask_threshold,
                        "max_results": max_results,
                    }
                )
                mask = np.zeros(frame.shape[:2], dtype=bool)
                mask[1:3, 1:3] = True
                return [
                    MolTrackSam3Proposal(
                        frame_index=frame_index,
                        source_view=source_view,
                        bbox_xyxy=(1, 1, 3, 3),
                        score=0.91,
                        mask=mask,
                        polygon_xy=((1, 1), (3, 1), (3, 3), (1, 3)),
                        prompt_detection_ids=(),
                        model_name=model_id,
                    )
                ]

        fake_sam3 = FakeSam3Adapter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam3_adapter=fake_sam3,
        )
        frames = np.arange(1 * 5 * 5, dtype=np.float32).reshape(1, 5, 5)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
        )
        self.window.set_image_series(series)
        self.window.cmb_segmentation_backend.setCurrentText("SAM3")
        self.__class__._app.processEvents()

        self.assertNotEqual(self.window.cmb_sam3_prompt_source.findText("Manual prompt BBoxes"), -1)
        self.assertTrue(self.window.add_sam3_manual_prompt_bbox((0, 0, 2, 2), label=1))
        self.assertTrue(self.window.add_sam3_manual_prompt_bbox((3, 3, 5, 5), label=0))
        self.window.cmb_sam3_prompt_source.setCurrentText("Manual prompt BBoxes")
        self.__class__._app.processEvents()

        self.window.btn_sam3_run_concepts.click()
        self.process_events_until(
            lambda: series.sam3_preview is not None and len(fake_sam3.calls) == 1,
            timeout_s=3.0,
        )

        call = fake_sam3.calls[0]
        np.testing.assert_array_equal(call["frame"], frames[0])
        self.assertEqual(call["frame_index"], 0)
        self.assertEqual(call["source_view"], "raw")
        self.assertEqual([prompt.label for prompt in call["prompts"]], [1, 0])
        self.assertEqual(
            [prompt.bbox_xyxy for prompt in call["prompts"]],
            [(0.0, 0.0, 2.0, 2.0), (3.0, 3.0, 5.0, 5.0)],
        )
        self.assertEqual([prompt.detection_id for prompt in call["prompts"]], ["", ""])
        self.assertIsNone(series.molecular_detections)
        self.assertEqual(series.sam3_preview.proposal_count, 1)

    def test_sam3_expanded_prompts_run_on_raw_and_transform_proposals_back_to_expanded(self) -> None:
        calls = []

        class FakeSam3Adapter:
            def segment_prompts(self, frame, prompts, *, frame_index, source_view, model_id, **_kwargs):
                calls.append((np.asarray(frame).copy(), tuple(prompts), frame_index, source_view))
                mask = np.zeros(frame.shape[:2], dtype=bool)
                mask[1:3, 1:3] = True
                return [
                    MolTrackSam3Proposal(
                        frame_index=frame_index,
                        source_view=source_view,
                        bbox_xyxy=(1, 1, 3, 3),
                        score=0.9,
                        mask=mask,
                        polygon_xy=((1, 1), (3, 1), (3, 3), (1, 3)),
                        model_name=model_id,
                    )
                ]

        raw_frame = np.arange(25, dtype=np.float32).reshape(5, 5)
        expanded_frame = np.full((8, 9), np.nan, dtype=np.float32)
        expanded_frame[1:6, 2:7] = raw_frame

        def fake_expanded_builder(series):
            stack = SimpleNamespace(
                frames=expanded_frame[np.newaxis, ...],
                metadata=STMSequenceMetadata(pixels_x=9, pixels_y=8),
                padding_ltrb=(2, 1, 2, 2),
                frame_origins_xy=np.asarray(((2.0, 1.0),), dtype=np.float64),
            )
            series.expanded_aligned_stack = stack
            return stack

        settings = MolTrackRegistrationSettings()
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=raw_frame[np.newaxis, ...],
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            registration_results=MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    0: MolTrackRegistrationFrameResult(
                        frame_index=0,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                    )
                },
            ),
        )
        self.window = MolTrackMainWindow(
            expanded_aligned_builder=fake_expanded_builder,
            yolo_model_discovery=lambda: [],
            sam3_adapter=FakeSam3Adapter(),
        )
        self.window.set_image_series(series)
        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.window.cmb_segmentation_backend.setCurrentText("SAM3")
        self.window.add_sam3_manual_prompt_bbox((3, 2, 5, 4), label=1)
        self.window.add_sam3_manual_prompt_bbox((5, 3, 7, 5), label=0)
        self.window.cmb_sam3_prompt_source.setCurrentText("Manual prompt BBoxes")

        self.window.btn_sam3_run_concepts.click()
        self.process_events_until(lambda: series.sam3_preview is not None and len(calls) == 1)

        np.testing.assert_array_equal(calls[0][0], raw_frame)
        self.assertEqual(calls[0][2], 0)
        self.assertEqual(calls[0][3], "raw")
        self.assertEqual([prompt.label for prompt in calls[0][1]], [1, 0])
        self.assertEqual(
            [prompt.bbox_xyxy for prompt in calls[0][1]],
            [(1.0, 1.0, 3.0, 3.0), (3.0, 2.0, 5.0, 4.0)],
        )
        preview = series.sam3_preview
        self.assertEqual(preview.source_view, "expanded_aligned")
        self.assertEqual(preview.proposals[0].bbox_xyxy, (3.0, 2.0, 5.0, 4.0))
        self.assertEqual(
            preview.proposals[0].polygon_xy,
            ((3.0, 2.0), (5.0, 2.0), (5.0, 4.0), (3.0, 4.0)),
        )
        expected_mask = np.zeros(expanded_frame.shape, dtype=bool)
        expected_mask[2:4, 3:5] = True
        np.testing.assert_array_equal(preview.proposals[0].mask, expected_mask)

    def test_sam3_run_concepts_rejects_manual_negative_prompts_without_positive_prompt(self) -> None:
        class FakeSam3Adapter:
            def __init__(self) -> None:
                self.calls = []

            def segment_prompts(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                raise AssertionError("SAM3 must not run without a positive prompt")

        fake_sam3 = FakeSam3Adapter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam3_adapter=fake_sam3,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(25, dtype=np.float32).reshape(1, 5, 5),
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
        )
        self.window.set_image_series(series)
        self.window.cmb_segmentation_backend.setCurrentText("SAM3")
        self.window.cmb_sam3_prompt_source.setCurrentText("Manual prompt BBoxes")
        self.__class__._app.processEvents()

        self.assertTrue(self.window.add_sam3_manual_prompt_bbox((3, 3, 5, 5), label=0))
        self.window.btn_sam3_run_concepts.click()
        self.__class__._app.processEvents()

        self.assertEqual(fake_sam3.calls, [])
        self.assertIsNone(series.sam3_preview)
        self.assertIn("positive", self.window.lbl_segmentation_status.text())

    def test_sam3_manual_prompt_round_trip_keeps_preview_and_does_not_restore_prompts_from_state(self) -> None:
        class FakeSam3Adapter:
            def __init__(self) -> None:
                self.calls = []

            def segment_prompts(
                self,
                frame,
                prompts,
                *,
                frame_index,
                source_view,
                model_id,
                score_threshold,
                mask_threshold,
                max_results,
            ):
                self.calls.append(
                    {
                        "frame": frame.copy(),
                        "prompts": tuple(prompts),
                        "frame_index": frame_index,
                        "source_view": source_view,
                        "model_id": model_id,
                        "score_threshold": score_threshold,
                        "mask_threshold": mask_threshold,
                        "max_results": max_results,
                    }
                )
                time.sleep(0.15)
                mask = np.zeros(frame.shape[:2], dtype=bool)
                mask[1:3, 1:3] = True
                return [
                    MolTrackSam3Proposal(
                        frame_index=frame_index,
                        source_view=source_view,
                        bbox_xyxy=(1, 1, 3, 3),
                        score=0.93,
                        mask=mask,
                        polygon_xy=((1, 1), (3, 1), (3, 3), (1, 3)),
                        prompt_detection_ids=(),
                        model_name=model_id,
                    )
                ]

        fake_sam3 = FakeSam3Adapter()
        saved = []
        loaded_session = SimpleNamespace(registration_view_mode="Show raw")
        restored_series = MolTrackImageSeries(
            source_path="restored.mpp",
            raw_frames=np.arange(25, dtype=np.float32).reshape(1, 5, 5),
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
        )

        def fake_saver(path, series, ui_state):
            saved.append((path, series, dict(ui_state)))

        def fake_loader(path):
            self.assertEqual(path, "state.moltrack.json")
            return loaded_session

        def fake_restorer(session):
            self.assertIs(session, loaded_session)
            return restored_series

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam3_adapter=fake_sam3,
            session_saver=fake_saver,
            session_loader=fake_loader,
            session_restorer=fake_restorer,
        )
        frames = np.arange(25, dtype=np.float32).reshape(1, 5, 5)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
        )
        self.window.set_image_series(series)
        self.window.cmb_segmentation_backend.setCurrentText("SAM3")
        self.window.cmb_sam3_prompt_source.setCurrentText("Manual prompt BBoxes")
        self.__class__._app.processEvents()

        self.window.btn_sam3_add_positive_prompt.click()
        self.__class__._app.processEvents()
        self.window.viewer.finish_manual_bbox_drag_from_pixels((0.0, 0.0), (2.0, 2.0))
        self.window.btn_sam3_add_negative_prompt.click()
        self.__class__._app.processEvents()
        self.window.viewer.finish_manual_bbox_drag_from_pixels((3.0, 3.0), (5.0, 5.0))
        self.__class__._app.processEvents()

        self.assertEqual(self.window.sam3_manual_prompt_counts(), (1, 1))
        self.assertEqual(self.window.viewer.visible_sam3_manual_prompt_count(), 2)

        self.window.btn_sam3_run_concepts.click()
        self.assertIsNotNone(self.window._sam3_concept_progress_dialog)
        self.assertIn("Running SAM3", self.window.lbl_segmentation_status.text())
        self.process_events_until(
            lambda: series.sam3_preview is not None and len(fake_sam3.calls) == 1,
            timeout_s=3.0,
        )

        call = fake_sam3.calls[0]
        self.assertEqual([prompt.label for prompt in call["prompts"]], [1, 0])
        self.assertEqual(series.sam3_preview.proposal_count, 1)
        self.assertEqual(self.window.viewer.visible_sam3_preview_count(), 1)
        self.assertEqual(self.window.viewer.visible_sam3_manual_prompt_count(), 2)
        self.assertEqual(self.window.sam3_manual_prompt_counts(), (1, 1))
        self.assertTrue(self.window.btn_sam3_commit_proposals.isEnabled())

        self.window.btn_sam3_commit_proposals.click()
        self.__class__._app.processEvents()

        self.assertIsNone(series.sam3_preview)
        self.assertEqual(series.molecular_detections.detection_count, 1)
        self.assertEqual(series.molecular_segmentations.segmentation_count, 1)
        self.assertEqual(self.window.viewer.visible_sam3_manual_prompt_count(), 2)

        self.window.save_state("state.moltrack.json")
        self.assertEqual(
            saved,
            [
                (
                    "state.moltrack.json",
                    series,
                    {
                        "registration_view_mode": "Show raw",
                        "bbox_overlay_visible": True,
                        "bbox_opacity_percent": 100,
                        "mask_opacity_percent": 30,
                    },
                )
            ],
        )

        self.window.open_state("state.moltrack.json")
        self.__class__._app.processEvents()

        self.assertIs(self.window._series, restored_series)
        self.assertEqual(self.window.sam3_manual_prompt_counts(), (0, 0))
        self.assertEqual(self.window.viewer.visible_sam3_manual_prompt_count(), 0)
        self.assertIsNone(self.window.sam3_prompt_draw_mode())
        self.assertFalse(self.window.btn_sam3_add_positive_prompt.isChecked())
        self.assertFalse(self.window.btn_sam3_add_negative_prompt.isChecked())

    def test_sam3_commit_proposals_commits_preview_as_bbox_and_segmentation(self) -> None:
        preview = MolTrackSam3Preview(
            frame_index=0,
            source_view="raw",
            proposals=(
                MolTrackSam3PreviewProposal(
                    frame_index=0,
                    source_view="raw",
                    bbox_xyxy=(1, 1, 3, 3),
                    score=0.86,
                    mask=np.asarray(
                        [
                            [False, False, False, False],
                            [False, True, True, False],
                            [False, True, True, False],
                            [False, False, False, False],
                        ],
                        dtype=bool,
                    ),
                    polygon_xy=((1, 1), (3, 1), (3, 3), (1, 3)),
                    prompt_detection_ids=("prompt-1",),
                    model_name="facebook/sam3",
                    proposal_id="commit-1",
                ),
            ),
        )
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(16, dtype=np.float32).reshape(1, 4, 4),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            sam3_preview=preview,
        )
        self.window.set_image_series(series)
        self.window.cmb_segmentation_backend.setCurrentText("SAM3")
        self.__class__._app.processEvents()

        self.assertTrue(self.window.btn_sam3_commit_proposals.isEnabled())
        self.assertEqual(self.window.viewer.visible_sam3_preview_count(), 1)
        self.window.btn_sam3_commit_proposals.click()
        self.__class__._app.processEvents()

        self.assertIsNone(series.sam3_preview)
        self.assertIsNotNone(series.molecular_detections)
        committed_detection = series.molecular_detections.get_detection("sam3-bbox-commit-1")
        self.assertIsNotNone(committed_detection)
        self.assertEqual(committed_detection.origin, "sam3_concept")
        self.assertEqual(committed_detection.bbox_xyxy, (1.0, 1.0, 3.0, 3.0))
        self.assertIsNotNone(series.molecular_segmentations)
        committed_segmentation = series.molecular_segmentations.get_segmentation("sam3-seg-commit-1")
        self.assertIsNotNone(committed_segmentation)
        self.assertEqual(committed_segmentation.origin, "sam3")
        self.assertEqual(committed_segmentation.prompt_detection_ids, ("prompt-1",))
        self.assertEqual(self.window.viewer.visible_sam3_preview_count(), 0)
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertEqual(self.window.viewer.visible_molecular_segmentation_ids(), ["sam3-seg-commit-1"])
        self.assertIn("Committed SAM3 proposals", self.window.statusBar().currentMessage())

    def test_sam3_manual_prompt_state_is_temporary_and_contextual(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.arange(2 * 5 * 5, dtype=np.float32).reshape(2, 5, 5)
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1, 1, 3, 3),
                    confidence=0.9,
                    source_view="raw",
                    detection_id="bbox-1",
                )
            ],
            source_view="raw",
            frame_shape=(5, 5),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)

        self.assertEqual(self.window.sam3_manual_prompt_counts(), (0, 0))

        self.assertTrue(self.window.add_sam3_manual_prompt_bbox((0, 0, 2, 2), label=1))
        self.assertTrue(self.window.add_sam3_manual_prompt_bbox((3, 3, 5, 5), label=0))

        self.assertEqual(self.window.sam3_manual_prompt_counts(), (1, 1))
        self.assertEqual(self.window.sam3_manual_prompt_bboxes(label=1), ((0.0, 0.0, 2.0, 2.0),))
        self.assertEqual(self.window.sam3_manual_prompt_bboxes(label=0), ((3.0, 3.0, 5.0, 5.0),))
        self.assertEqual(series.molecular_detections.detection_count, 1)
        self.assertEqual(series.molecular_detections.get_detection("bbox-1").bbox_xyxy, (1.0, 1.0, 3.0, 3.0))

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.sam3_manual_prompt_counts(), (0, 0))
        self.assertTrue(self.window.add_sam3_manual_prompt_bbox((1, 1, 4, 4), label=1))
        self.assertEqual(self.window.sam3_manual_prompt_counts(), (1, 0))

        self.window.slider_frame.setValue(0)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.sam3_manual_prompt_counts(), (1, 1))
        self.window.clear_sam3_manual_prompts()
        self.assertEqual(self.window.sam3_manual_prompt_counts(), (0, 0))
        self.assertEqual(series.molecular_detections.detection_count, 1)

    def test_sam3_prompt_tool_controls_are_available_and_exclusive(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        mask = np.zeros((5, 5), dtype=bool)
        mask[1:4, 1:4] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentation = MolecularSegmentation(
            frame_index=0,
            source_view="raw",
            mask=mask,
            original_mask=mask.copy(),
            bbox_xyxy=(1, 1, 4, 4),
            origin="sam2",
            segmentation_id="sam2-mask-1",
        )
        segmentations.add_segmentation(segmentation)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(25, dtype=np.float32).reshape(1, 5, 5),
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_segmentations=segmentations,
        )
        self.window.set_image_series(series)
        self.window.viewer.select_molecular_segmentation_by_id("sam2-mask-1")
        self.window.cmb_segmentation_backend.setCurrentText("SAM3")
        self.__class__._app.processEvents()

        self.assertEqual(self.window.btn_sam3_add_positive_prompt.text(), "Add + Prompt BBox")
        self.assertEqual(self.window.btn_sam3_add_negative_prompt.text(), "Add - Prompt BBox")
        self.assertEqual(self.window.btn_sam3_clear_prompts.text(), "Clear SAM3 Prompts")
        self.assertTrue(self.window.btn_sam3_add_positive_prompt.isEnabled())
        self.assertTrue(self.window.btn_sam3_add_negative_prompt.isEnabled())
        self.assertTrue(self.window.btn_sam3_clear_prompts.isEnabled())
        self.assertEqual(self.window.lbl_sam3_prompt_status.text(), "Manual prompts: +0 / -0")

        self.window.btn_bbox_add.click()
        self.__class__._app.processEvents()
        self.assertTrue(self.window.btn_bbox_add.isChecked())
        self.assertTrue(self.window.viewer.molecular_bbox_add_mode_enabled())

        self.window.btn_sam3_add_positive_prompt.click()
        self.__class__._app.processEvents()

        self.assertTrue(self.window.btn_sam3_add_positive_prompt.isChecked())
        self.assertFalse(self.window.btn_sam3_add_negative_prompt.isChecked())
        self.assertFalse(self.window.btn_bbox_add.isChecked())
        self.assertFalse(self.window.btn_bbox_add.isEnabled())
        self.assertFalse(self.window.viewer.molecular_bbox_add_mode_enabled())
        self.assertFalse(self.window.btn_edit_mask.isChecked())
        self.assertFalse(self.window.btn_edit_mask.isEnabled())
        self.assertFalse(self.window.viewer.mask_brush_edit_mode_enabled())

        self.assertTrue(self.window.add_sam3_manual_prompt_bbox((0, 0, 2, 2), label=1))
        self.assertEqual(self.window.lbl_sam3_prompt_status.text(), "Manual prompts: +1 / -0")

        self.window.btn_sam3_add_positive_prompt.click()
        self.__class__._app.processEvents()
        self.assertIsNone(self.window.sam3_prompt_draw_mode())
        self.assertTrue(self.window.btn_edit_mask.isEnabled())
        self.window.btn_edit_mask.click()
        self.__class__._app.processEvents()
        self.assertTrue(self.window.btn_edit_mask.isChecked())
        self.assertTrue(self.window.viewer.mask_brush_edit_mode_enabled())

        self.window.btn_sam3_add_negative_prompt.click()
        self.__class__._app.processEvents()

        self.assertFalse(self.window.btn_sam3_add_positive_prompt.isChecked())
        self.assertTrue(self.window.btn_sam3_add_negative_prompt.isChecked())
        self.assertFalse(self.window.btn_edit_mask.isChecked())
        self.assertFalse(self.window.btn_edit_mask.isEnabled())
        self.assertFalse(self.window.viewer.mask_brush_edit_mode_enabled())
        self.assertTrue(self.window.add_sam3_manual_prompt_bbox((3, 3, 5, 5), label=0))
        self.assertEqual(self.window.lbl_sam3_prompt_status.text(), "Manual prompts: +1 / -1")

    def test_sam3_prompt_tool_drag_adds_temporary_prompt_without_creating_detection(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(25, dtype=np.float32).reshape(1, 5, 5),
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
        )
        self.window.set_image_series(series)
        self.window.cmb_segmentation_backend.setCurrentText("SAM3")
        self.__class__._app.processEvents()

        self.window.btn_sam3_add_positive_prompt.click()
        self.__class__._app.processEvents()
        self.window.viewer.finish_manual_bbox_drag_from_pixels((0.0, 0.0), (2.0, 2.0))
        self.__class__._app.processEvents()

        self.assertEqual(self.window.sam3_manual_prompt_counts(), (1, 0))
        self.assertEqual(self.window.sam3_manual_prompt_bboxes(label=1), ((0.0, 0.0, 2.0, 2.0),))
        self.assertIsNone(series.molecular_detections)
        self.assertEqual(self.window.lbl_sam3_prompt_status.text(), "Manual prompts: +1 / -0")

        self.window.btn_sam3_add_negative_prompt.click()
        self.__class__._app.processEvents()
        self.window.viewer.finish_manual_bbox_drag_from_pixels((3.0, 3.0), (5.0, 5.0))
        self.__class__._app.processEvents()

        self.assertEqual(self.window.sam3_manual_prompt_counts(), (1, 1))
        self.assertEqual(self.window.sam3_manual_prompt_bboxes(label=0), ((3.0, 3.0, 5.0, 5.0),))
        self.assertIsNone(series.molecular_detections)
        self.assertEqual(self.window.lbl_sam3_prompt_status.text(), "Manual prompts: +1 / -1")

        self.window.btn_sam3_add_negative_prompt.click()
        self.window.btn_bbox_add.click()
        self.__class__._app.processEvents()
        self.window.viewer.finish_manual_bbox_drag_from_pixels((1.0, 1.0), (4.0, 4.0))
        self.__class__._app.processEvents()

        self.assertIsNotNone(series.molecular_detections)
        self.assertEqual(series.molecular_detections.detection_count, 1)
        self.assertEqual(self.window.sam3_manual_prompt_counts(), (1, 1))

    def test_sam3_manual_prompt_overlay_distinguishes_labels_and_context(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(2 * 5 * 5, dtype=np.float32).reshape(2, 5, 5),
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
        )
        self.window.set_image_series(series)
        self.window.cmb_segmentation_backend.setCurrentText("SAM3")
        self.__class__._app.processEvents()

        self.window.btn_sam3_add_positive_prompt.click()
        self.__class__._app.processEvents()
        self.window.viewer.finish_manual_bbox_drag_from_pixels((0.0, 0.0), (2.0, 2.0))
        self.window.btn_sam3_add_negative_prompt.click()
        self.__class__._app.processEvents()
        self.window.viewer.finish_manual_bbox_drag_from_pixels((3.0, 3.0), (5.0, 5.0))
        self.__class__._app.processEvents()

        self.assertEqual(self.window.viewer.visible_sam3_manual_prompt_count(), 2)
        prompt_colors = self.window.viewer.visible_sam3_manual_prompt_colors()
        self.assertEqual(len(prompt_colors), 2)
        self.assertNotEqual(prompt_colors[0], prompt_colors[1])
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 0)
        self.assertEqual(self.window.viewer.visible_sam3_preview_count(), 0)
        self.assertIsNone(series.molecular_detections)

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.sam3_manual_prompt_counts(), (0, 0))
        self.assertEqual(self.window.viewer.visible_sam3_manual_prompt_count(), 0)

        self.window.slider_frame.setValue(0)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.sam3_manual_prompt_counts(), (1, 1))
        self.assertEqual(self.window.viewer.visible_sam3_manual_prompt_count(), 2)

    def test_sam3_prompt_tool_turns_off_when_frame_context_changes(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(2 * 5 * 5, dtype=np.float32).reshape(2, 5, 5),
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
        )
        self.window.set_image_series(series)
        self.window.cmb_segmentation_backend.setCurrentText("SAM3")
        self.__class__._app.processEvents()

        self.window.btn_sam3_add_positive_prompt.click()
        self.__class__._app.processEvents()
        self.window.viewer.finish_manual_bbox_drag_from_pixels((0.0, 0.0), (2.0, 2.0))
        self.__class__._app.processEvents()

        self.assertEqual(self.window.sam3_prompt_draw_mode(), "positive")
        self.assertTrue(self.window.btn_sam3_add_positive_prompt.isChecked())
        self.assertTrue(self.window.viewer.prompt_bbox_draw_mode_enabled())
        self.assertEqual(self.window.viewer.visible_sam3_manual_prompt_count(), 1)

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()

        self.assertIsNone(self.window.sam3_prompt_draw_mode())
        self.assertFalse(self.window.btn_sam3_add_positive_prompt.isChecked())
        self.assertFalse(self.window.btn_sam3_add_negative_prompt.isChecked())
        self.assertFalse(self.window.viewer.prompt_bbox_draw_mode_enabled())
        self.assertEqual(self.window.lbl_sam3_prompt_status.text(), "Manual prompts: +0 / -0")
        self.assertEqual(self.window.viewer.visible_sam3_manual_prompt_count(), 0)

    def test_sam3_prompt_tool_turns_off_when_source_view_context_changes(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.arange(1 * 5 * 5, dtype=np.float32).reshape(1, 5, 5)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
        )
        settings = MolTrackRegistrationSettings(backend="phase_correlation")
        series.registration_results = MolTrackRegistrationResultSet(
            settings=settings,
            results_by_frame={
                0: MolTrackRegistrationFrameResult(
                    frame_index=0,
                    shift_xy=(0.0, 0.0),
                    method="identity",
                    quality_score=1.0,
                )
            },
        )
        series.expanded_aligned_stack = SimpleNamespace(
            frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            padding_ltrb=(0, 0, 0, 0),
            frame_origins_xy=np.zeros((1, 2), dtype=np.float64),
        )
        self.window.set_image_series(series)
        self.window.cmb_segmentation_backend.setCurrentText("SAM3")
        self.__class__._app.processEvents()

        self.window.btn_sam3_add_positive_prompt.click()
        self.__class__._app.processEvents()
        self.window.viewer.finish_manual_bbox_drag_from_pixels((0.0, 0.0), (2.0, 2.0))
        self.__class__._app.processEvents()

        self.assertEqual(self.window.sam3_prompt_draw_mode(), "positive")
        self.assertEqual(self.window.sam3_manual_prompt_counts(), (1, 0))
        self.assertEqual(self.window.viewer.visible_sam3_manual_prompt_count(), 1)

        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.__class__._app.processEvents()

        self.assertIsNone(self.window.sam3_prompt_draw_mode())
        self.assertFalse(self.window.btn_sam3_add_positive_prompt.isChecked())
        self.assertFalse(self.window.viewer.prompt_bbox_draw_mode_enabled())
        self.assertEqual(self.window.sam3_manual_prompt_counts(), (0, 0))
        self.assertEqual(self.window.lbl_sam3_prompt_status.text(), "Manual prompts: +0 / -0")
        self.assertEqual(self.window.viewer.visible_sam3_manual_prompt_count(), 0)

    def test_sam3_clear_prompts_button_clears_overlay_status_and_batch(self) -> None:
        class FakeSam3Adapter:
            def __init__(self) -> None:
                self.calls = []

            def segment_prompts(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                raise AssertionError("SAM3 must not run after manual prompts are cleared")

        fake_sam3 = FakeSam3Adapter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam3_adapter=fake_sam3,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(25, dtype=np.float32).reshape(1, 5, 5),
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
        )
        self.window.set_image_series(series)
        self.window.cmb_segmentation_backend.setCurrentText("SAM3")
        self.window.cmb_sam3_prompt_source.setCurrentText("Manual prompt BBoxes")
        self.__class__._app.processEvents()

        self.assertTrue(self.window.add_sam3_manual_prompt_bbox((0, 0, 2, 2), label=1))
        self.assertTrue(self.window.add_sam3_manual_prompt_bbox((3, 3, 5, 5), label=0))
        self.assertEqual(self.window.sam3_manual_prompt_counts(), (1, 1))
        self.assertEqual(self.window.viewer.visible_sam3_manual_prompt_count(), 2)

        self.window.btn_sam3_clear_prompts.click()
        self.__class__._app.processEvents()

        self.assertEqual(self.window.sam3_manual_prompt_counts(), (0, 0))
        self.assertEqual(self.window.lbl_sam3_prompt_status.text(), "Manual prompts: +0 / -0")
        self.assertEqual(self.window.viewer.visible_sam3_manual_prompt_count(), 0)

        self.window.btn_sam3_run_concepts.click()
        self.__class__._app.processEvents()

        self.assertEqual(fake_sam3.calls, [])
        self.assertIsNone(series.sam3_preview)
        self.assertIn("positive", self.window.lbl_segmentation_status.text())

    def test_sam2_segment_selected_bbox_is_disabled_without_selected_bbox(self) -> None:
        class FakeSam2Segmenter:
            def __init__(self) -> None:
                self.calls = []

            def segment_detection(self, frame, detection, **_kwargs):
                self.calls.append((frame, detection))
                raise AssertionError("SAM2 must not run without a selected BBox")

        fake_segmenter = FakeSam2Segmenter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_segmenter=fake_segmenter,
        )
        frames = np.arange(16, dtype=np.float32).reshape(1, 4, 4)
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1, 1, 3, 3),
                    confidence=0.9,
                    source_view="raw",
                    detection_id="bbox-1",
                )
            ],
            source_view="raw",
            frame_shape=(4, 4),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )

        self.window.set_image_series(series)

        self.assertEqual(self.window.segmentation_group.title(), "Segmentation")
        self.assertEqual(self.window.btn_sam2_segment_selected.text(), "Segment Selected BBox")
        self.assertFalse(self.window.btn_sam2_segment_selected.isEnabled())
        self.assertTrue(self.window.btn_sam2_segment_all_current.isEnabled())
        self.window.btn_sam2_segment_selected.click()
        self.__class__._app.processEvents()
        self.assertEqual(fake_segmenter.calls, [])

    def test_sam2_controls_are_disabled_when_no_checkpoints_are_available(self) -> None:
        class FakeSam2Segmenter:
            def segment_detection(self, frame, detection, **_kwargs):
                raise AssertionError("SAM2 must not run without a checkpoint")

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_checkpoint_discovery=lambda: [],
            sam2_segmenter=FakeSam2Segmenter(),
        )
        frames = np.arange(16, dtype=np.float32).reshape(1, 4, 4)
        detections = MolecularDetectionSet(frame_count=1)
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(1, 1, 3, 3),
            confidence=0.9,
            source_view="raw",
            detection_id="bbox-1",
        )
        detections.set_detections(0, [detection], source_view="raw", frame_shape=(4, 4))
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.select_molecular_detection_at_pixel(2.0, 2.0)
        self.__class__._app.processEvents()

        self.assertFalse(self.window.sp_sam2_mask_threshold.isEnabled())
        self.assertFalse(self.window.btn_sam2_segment_selected.isEnabled())
        self.assertFalse(self.window.btn_sam2_segment_all_current.isEnabled())
        self.assertIn("No SAM2 checkpoints found", self.window.lbl_segmentation_status.text())

    def test_sam2_segmentation_dialog_cancel_prevents_algorithm_run(self) -> None:
        class FakeSam2Segmenter:
            def __init__(self) -> None:
                self.calls = []

            def segment_detection(self, frame, detection, **_kwargs):
                self.calls.append((frame, detection))
                raise AssertionError("SAM2 must not run when the settings dialog is canceled")

        dialog_calls = []
        fake_segmenter = FakeSam2Segmenter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_segmenter=fake_segmenter,
            sam2_settings_dialog_factory=self.sam2_dialog_factory(accepted=False, calls=dialog_calls),
        )
        frames = np.arange(16, dtype=np.float32).reshape(1, 4, 4)
        detections = MolecularDetectionSet(frame_count=1)
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(1, 1, 3, 3),
            confidence=0.9,
            source_view="raw",
            detection_id="bbox-1",
        )
        detections.set_detections(0, [detection], source_view="raw", frame_shape=(4, 4))
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.select_molecular_detection_at_pixel(2.0, 2.0)
        self.__class__._app.processEvents()

        self.window.btn_sam2_segment_selected.click()
        self.__class__._app.processEvents()

        self.assertEqual(len(dialog_calls), 1)
        self.assertEqual(dialog_calls[0]["bbox_count"], 1)
        self.assertEqual(fake_segmenter.calls, [])
        self.assertIsNone(self.window._sam2_segmentation_progress_dialog)
        self.assertIn("SAM2 segmentation canceled", self.window.statusBar().currentMessage())

    def test_sam2_segment_selected_bbox_stores_segmentation_for_active_frame_and_view(self) -> None:
        class FakeSam2Segmenter:
            def __init__(self) -> None:
                self.calls = []

            def segment_detection(self, frame, detection, **_kwargs):
                self.calls.append((frame.copy(), detection))
                mask = np.zeros(frame.shape[:2], dtype=bool)
                mask[1:3, 1:3] = True
                return MolecularSegmentation(
                    frame_index=detection.frame_index,
                    source_view=detection.source_view,
                    bbox_xyxy=(1, 1, 3, 3),
                    mask=mask,
                    score=0.8,
                    origin="sam2",
                    prompt_detection_ids=(detection.detection_id,),
                    model_name="fake-sam2",
                    segmentation_id="sam2-seg-1",
                )

        fake_segmenter = FakeSam2Segmenter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_segmenter=fake_segmenter,
            sam2_settings_dialog_factory=self.sam2_dialog_factory(threshold=0.55),
        )
        frames = np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4)
        detections = MolecularDetectionSet(frame_count=2)
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(1, 1, 3, 3),
            confidence=0.9,
            source_view="raw",
            detection_id="bbox-1",
        )
        detections.set_detections(
            0,
            [detection],
            source_view="raw",
            frame_shape=(4, 4),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.select_molecular_detection_at_pixel(2.0, 2.0)
        self.__class__._app.processEvents()

        self.assertTrue(self.window.btn_sam2_segment_selected.isEnabled())
        self.window.btn_sam2_segment_selected.click()
        self.process_events_until(
            lambda: (
                series.molecular_segmentations is not None
                and series.molecular_segmentations.get_segmentation("sam2-seg-1") is not None
            ),
            timeout_s=3.0,
        )

        self.assertEqual(len(fake_segmenter.calls), 1)
        np.testing.assert_array_equal(fake_segmenter.calls[0][0], frames[0])
        self.assertIs(fake_segmenter.calls[0][1], detection)
        self.assertIsNotNone(series.molecular_segmentations)
        segmentations = series.molecular_segmentations.get_segmentations(0, source_view="raw")
        self.assertEqual([segmentation.segmentation_id for segmentation in segmentations], ["sam2-seg-1"])
        self.assertEqual(segmentations[0].origin, "sam2")
        self.assertEqual(segmentations[0].prompt_detection_ids, ("bbox-1",))
        self.assertEqual(detection.bbox_xyxy, (1.0, 1.0, 3.0, 3.0))
        self.assertEqual(self.window.viewer.visible_molecular_segmentation_ids(), ["sam2-seg-1"])
        self.assertIn("SAM2 segmented selected BBox", self.window.statusBar().currentMessage())

    def test_sam2_segment_selected_bbox_uses_one_item_batch_not_legacy_call(self) -> None:
        class FakeBatchSam2Segmenter:
            def __init__(self) -> None:
                self.batch_calls = []
                self.legacy_calls = []

            def segment_frame_detections(self, frame, detections, **kwargs):
                detections = list(detections)
                self.batch_calls.append((np.asarray(frame).copy(), detections, dict(kwargs)))
                detection = detections[0]
                mask = np.zeros(frame.shape[:2], dtype=bool)
                mask[1:3, 1:3] = True
                return [
                    MolecularSegmentation(
                        frame_index=detection.frame_index,
                        source_view=detection.source_view,
                        bbox_xyxy=(1, 1, 3, 3),
                        mask=mask,
                        origin="sam2",
                        prompt_detection_ids=(detection.detection_id,),
                        segmentation_id="sam2-selected-batch",
                    )
                ]

            def segment_detection(self, frame, detection, **kwargs):
                self.legacy_calls.append((frame, detection, kwargs))
                raise AssertionError("Selected BBox must use the frame batch adapter")

        segmenter = FakeBatchSam2Segmenter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_checkpoint_discovery=lambda: [Path(r"C:\models\sam2.pt")],
            sam2_segmenter=segmenter,
            sam2_settings_dialog_factory=self.sam2_dialog_factory(threshold=0.62),
        )
        series, detection, frames = self.load_single_bbox_series()

        with patch.object(
            QMessageBox,
            "critical",
            return_value=QMessageBox.StandardButton.Ok,
        ):
            self.window.btn_sam2_segment_selected.click()
            self.process_events_until(
                lambda: series.molecular_segmentations is not None
                and series.molecular_segmentations.get_segmentation("sam2-selected-batch")
                is not None,
            )

        self.assertEqual(len(segmenter.batch_calls), 1)
        np.testing.assert_array_equal(segmenter.batch_calls[0][0], frames[0])
        self.assertEqual(segmenter.batch_calls[0][1], [detection])
        self.assertAlmostEqual(
            segmenter.batch_calls[0][2]["mask_probability_threshold"],
            0.62,
        )
        self.assertEqual(segmenter.legacy_calls, [])

    def test_sam2_batch_backend_can_be_disabled_for_legacy_diagnostics(self) -> None:
        class DualPathSam2Segmenter:
            def __init__(self) -> None:
                self.batch_calls = []
                self.legacy_calls = []

            def segment_frame_detections(self, frame, detections, **kwargs):
                self.batch_calls.append((frame, list(detections), kwargs))
                raise AssertionError("Diagnostic fallback must not use batch SAM2")

            def segment_detection(self, frame, detection, **kwargs):
                self.legacy_calls.append((np.asarray(frame).copy(), detection, dict(kwargs)))
                mask = np.zeros(frame.shape[:2], dtype=bool)
                mask[1:3, 1:3] = True
                return MolecularSegmentation(
                    frame_index=detection.frame_index,
                    source_view=detection.source_view,
                    bbox_xyxy=(1, 1, 3, 3),
                    mask=mask,
                    origin="sam2",
                    prompt_detection_ids=(detection.detection_id,),
                    segmentation_id="sam2-legacy-diagnostic",
                )

        segmenter = DualPathSam2Segmenter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_checkpoint_discovery=lambda: [Path(r"C:\models\sam2.pt")],
            sam2_segmenter=segmenter,
            sam2_settings_dialog_factory=self.sam2_dialog_factory(),
            sam2_use_batch_backend=False,
        )
        series, detection, _frames = self.load_single_bbox_series()

        self.window.btn_sam2_segment_selected.click()
        self.process_events_until(
            lambda: series.molecular_segmentations is not None
            and series.molecular_segmentations.get_segmentation("sam2-legacy-diagnostic")
            is not None,
        )

        self.assertEqual(segmenter.batch_calls, [])
        self.assertEqual(len(segmenter.legacy_calls), 1)
        self.assertIs(segmenter.legacy_calls[0][1], detection)

    def test_selecting_sam2_segmentation_by_mask_pixel_updates_segmentation_panel(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.zeros((1, 5, 5), dtype=np.float32)
        detections = MolecularDetectionSet(frame_count=1)
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(1, 1, 4, 4),
            confidence=0.9,
            source_view="raw",
            detection_id="bbox-1",
        )
        detections.set_detections(0, [detection], source_view="raw", frame_shape=(5, 5))
        mask = np.zeros((5, 5), dtype=bool)
        mask[1:3, 1:3] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(1, 1, 3, 3),
                mask=mask,
                origin="sam2",
                prompt_detection_ids=("bbox-1",),
                model_name="sam2-test",
                metadata={"mask_area_px": 4.0},
                segmentation_id="sam2-seg-1",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_detections=detections,
            molecular_segmentations=segmentations,
        )
        self.window.set_image_series(series)

        selected_id = self.window.select_molecular_segmentation_at_pixel(1.0, 1.0)

        self.assertEqual(selected_id, "sam2-seg-1")
        self.assertEqual(self.window.selected_molecular_segmentation_id(), "sam2-seg-1")
        self.assertEqual(self.window.viewer.selected_molecular_segmentation_id(), "sam2-seg-1")
        self.assertEqual(self.window.viewer.highlighted_molecular_segmentation_ids(), ["sam2-seg-1"])
        panel_text = self.window.lbl_active_segmentation_status.text()
        self.assertIn("sam2-seg-1", panel_text)
        self.assertIn("sam2", panel_text)
        self.assertIn("bbox-1", panel_text)
        self.assertIn("area 4", panel_text)
        self.assertIn("bbox 1.0,1.0,3.0,3.0", panel_text)

    def test_delete_active_segmentation_removes_mask_but_keeps_prompt_bbox(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.zeros((1, 5, 5), dtype=np.float32)
        detections = MolecularDetectionSet(frame_count=1)
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(1, 1, 4, 4),
            confidence=0.9,
            source_view="raw",
            detection_id="bbox-1",
        )
        detections.set_detections(0, [detection], source_view="raw", frame_shape=(5, 5))
        mask = np.zeros((5, 5), dtype=bool)
        mask[1:3, 1:3] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(1, 1, 3, 3),
                mask=mask,
                origin="sam2",
                prompt_detection_ids=("bbox-1",),
                segmentation_id="sam2-seg-1",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_detections=detections,
            molecular_segmentations=segmentations,
        )
        self.window.set_image_series(series)

        self.assertFalse(self.window.btn_delete_active_segmentation.isEnabled())
        self.assertEqual(
            self.window.select_molecular_segmentation_at_pixel(1.0, 1.0),
            "sam2-seg-1",
        )
        self.assertTrue(self.window.btn_delete_active_segmentation.isEnabled())

        self.window.btn_delete_active_segmentation.click()
        self.__class__._app.processEvents()

        self.assertIsNone(segmentations.get_segmentation("sam2-seg-1"))
        self.assertIs(detections.get_detection("bbox-1"), detection)
        self.assertEqual(self.window.viewer.visible_molecular_segmentation_ids(), [])
        self.assertIsNone(self.window.selected_molecular_segmentation_id())
        self.assertIsNone(self.window.viewer.selected_molecular_segmentation_id())
        self.assertFalse(self.window.btn_delete_active_segmentation.isEnabled())
        self.assertEqual(self.window.lbl_active_segmentation_status.text(), "No active segmentation")
        self.assertIn("Deleted segmentation", self.window.statusBar().currentMessage())

    def test_segmentation_panel_combo_selects_specific_mask_for_same_bbox(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.zeros((1, 5, 5), dtype=np.float32)
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(0, 0, 5, 5),
                    confidence=0.9,
                    source_view="raw",
                    detection_id="bbox-1",
                )
            ],
            source_view="raw",
            frame_shape=(5, 5),
        )
        first_mask = np.zeros((5, 5), dtype=bool)
        first_mask[1, 1] = True
        second_mask = np.zeros((5, 5), dtype=bool)
        second_mask[3, 3] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        for segmentation_id, mask, bbox in (
            ("sam2-first", first_mask, (1, 1, 2, 2)),
            ("sam2-second", second_mask, (3, 3, 4, 4)),
        ):
            segmentations.add_segmentation(
                MolecularSegmentation(
                    frame_index=0,
                    source_view="raw",
                    bbox_xyxy=bbox,
                    mask=mask,
                    origin="sam2",
                    prompt_detection_ids=("bbox-1",),
                    model_name="sam2-test",
                    segmentation_id=segmentation_id,
                )
            )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_detections=detections,
            molecular_segmentations=segmentations,
        )
        self.window.set_image_series(series)

        self.assertEqual(self.window.cmb_active_segmentation.count(), 2)
        index = self.window.cmb_active_segmentation.findData("sam2-second")
        self.window.cmb_active_segmentation.setCurrentIndex(index)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.selected_molecular_segmentation_id(), "sam2-second")
        self.assertEqual(self.window.viewer.selected_molecular_segmentation_id(), "sam2-second")
        self.assertEqual(self.window.viewer.highlighted_molecular_segmentation_ids(), ["sam2-second"])
        self.assertIn("sam2-second", self.window.lbl_active_segmentation_status.text())

    def test_selecting_segmentation_preserves_bbox_selection_and_frame_change_clears_segmentation(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.zeros((2, 5, 5), dtype=np.float32)
        detections = MolecularDetectionSet(frame_count=2)
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(1, 1, 4, 4),
            confidence=0.9,
            source_view="raw",
            detection_id="bbox-1",
        )
        detections.set_detections(0, [detection], source_view="raw", frame_shape=(5, 5))
        mask = np.zeros((5, 5), dtype=bool)
        mask[1:3, 1:3] = True
        segmentations = MolecularSegmentationSet(frame_count=2)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(1, 1, 3, 3),
                mask=mask,
                origin="sam2",
                prompt_detection_ids=("bbox-1",),
                segmentation_id="sam2-seg-1",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_detections=detections,
            molecular_segmentations=segmentations,
        )
        self.window.set_image_series(series)
        self.window.select_molecular_detection_at_pixel(2.0, 2.0)

        self.window.select_molecular_segmentation_at_pixel(1.0, 1.0)

        self.assertEqual(self.window.selected_molecular_detection_id(), "bbox-1")
        self.assertEqual(self.window.selected_molecular_segmentation_id(), "sam2-seg-1")
        self.assertEqual(self.window.viewer.highlighted_molecular_detection_ids(), ["bbox-1"])
        self.assertEqual(self.window.viewer.highlighted_molecular_segmentation_ids(), ["sam2-seg-1"])

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()

        self.assertIsNone(self.window.selected_molecular_segmentation_id())
        self.assertIsNone(self.window.viewer.selected_molecular_segmentation_id())
        self.assertEqual(self.window.lbl_active_segmentation_status.text(), "No active segmentation")

    def test_changing_view_clears_active_segmentation_when_it_is_not_visible(self) -> None:
        expanded_frames = np.zeros((1, 5, 5), dtype=np.float32)

        def fake_expanded_builder(series):
            expanded_stack = SimpleNamespace(
                frames=expanded_frames,
                metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
                padding_ltrb=(0, 0, 0, 0),
                frame_origins_xy=np.zeros((series.frame_count, 2), dtype=np.float64),
            )
            series.expanded_aligned_stack = expanded_stack
            return expanded_stack

        self.window = MolTrackMainWindow(
            expanded_aligned_builder=fake_expanded_builder,
            yolo_model_discovery=lambda: [],
        )
        mask = np.zeros((5, 5), dtype=bool)
        mask[1:3, 1:3] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(1, 1, 3, 3),
                mask=mask,
                origin="sam2",
                prompt_detection_ids=("bbox-1",),
                segmentation_id="sam2-raw",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 5, 5), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            registration_results=MolTrackRegistrationResultSet(
                settings=MolTrackRegistrationSettings(),
                results_by_frame={
                    0: MolTrackRegistrationFrameResult(
                        frame_index=0,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                    )
                },
            ),
            molecular_segmentations=segmentations,
        )
        self.window.set_image_series(series)
        self.window.select_molecular_segmentation_at_pixel(1.0, 1.0)
        self.assertEqual(self.window.selected_molecular_segmentation_id(), "sam2-raw")

        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.__class__._app.processEvents()

        self.assertIsNone(self.window.selected_molecular_segmentation_id())
        self.assertIsNone(self.window.viewer.selected_molecular_segmentation_id())
        self.assertEqual(self.window.lbl_active_segmentation_status.text(), "No active segmentation")

    def test_add_mask_brush_updates_active_sam2_mask_bbox_area_and_metadata(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.zeros((1, 5, 5), dtype=np.float32)
        mask = np.zeros((5, 5), dtype=bool)
        mask[1, 1] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(1, 1, 2, 2),
                mask=mask,
                origin="sam2",
                prompt_detection_ids=("bbox-1",),
                model_name="sam2-test",
                metadata={
                    "checkpoint_name": "sam2.1_hiera_base_plus.pt",
                    "sam2_threshold": 0.61,
                },
                segmentation_id="sam2-edit",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_segmentations=segmentations,
        )
        self.window.set_image_series(series)
        self.window.select_molecular_segmentation_at_pixel(1.0, 1.0)

        edited = self.window.apply_mask_brush_at_pixel(
            3.0,
            3.0,
            mode="add",
            brush_size_px=1,
        )

        self.assertTrue(edited)
        segmentation = series.molecular_segmentations.get_segmentation("sam2-edit")
        expected = np.zeros((5, 5), dtype=bool)
        expected[1, 1] = True
        expected[2, 3] = True
        expected[3, 2] = True
        expected[3, 3] = True
        expected[3, 4] = True
        expected[4, 3] = True
        np.testing.assert_array_equal(segmentation.mask, expected)
        self.assertEqual(segmentation.bbox_xyxy, (1.0, 1.0, 5.0, 5.0))
        self.assertEqual(segmentation.metadata["mask_area_px"], 6.0)
        self.assertEqual(segmentation.metadata["mask_component_count"], 2)
        self.assertTrue(segmentation.metadata["edited"])
        self.assertEqual(segmentation.metadata["edit_tool"], "manual_brush")
        self.assertEqual(segmentation.metadata["edit_mode"], "add")
        self.assertEqual(segmentation.metadata["brush_size_px"], 1)
        self.assertEqual(segmentation.metadata["checkpoint_name"], "sam2.1_hiera_base_plus.pt")
        self.assertAlmostEqual(segmentation.metadata["sam2_threshold"], 0.61)
        self.assertIn("area 6", self.window.lbl_active_segmentation_status.text())

    def test_erase_mask_brush_updates_mask_bbox_and_rejects_empty_result(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.zeros((1, 5, 5), dtype=np.float32)
        mask = np.zeros((5, 5), dtype=bool)
        mask[1, 1] = True
        mask[4, 4] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(1, 1, 5, 5),
                mask=mask,
                origin="sam2",
                prompt_detection_ids=("bbox-1",),
                segmentation_id="sam2-erase",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_segmentations=segmentations,
        )
        self.window.set_image_series(series)
        self.window.select_molecular_segmentation_at_pixel(1.0, 1.0)

        edited = self.window.apply_mask_brush_at_pixel(
            1.0,
            1.0,
            mode="erase",
            brush_size_px=1,
        )

        self.assertTrue(edited)
        segmentation = series.molecular_segmentations.get_segmentation("sam2-erase")
        expected = np.zeros((5, 5), dtype=bool)
        expected[4, 4] = True
        np.testing.assert_array_equal(segmentation.mask, expected)
        self.assertEqual(segmentation.bbox_xyxy, (4.0, 4.0, 5.0, 5.0))
        self.assertEqual(segmentation.metadata["mask_area_px"], 1.0)
        self.assertEqual(segmentation.metadata["mask_component_count"], 1)
        self.assertEqual(segmentation.metadata["edit_mode"], "erase")

        rejected = self.window.apply_mask_brush_at_pixel(
            4.0,
            4.0,
            mode="erase",
            brush_size_px=1,
        )

        self.assertFalse(rejected)
        np.testing.assert_array_equal(segmentation.mask, expected)
        self.assertEqual(segmentation.bbox_xyxy, (4.0, 4.0, 5.0, 5.0))
        self.assertIn("cannot be empty", self.window.statusBar().currentMessage())

    def test_edit_mask_controls_apply_brush_drag_to_active_sam2_segmentation(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.zeros((1, 5, 5), dtype=np.float32)
        mask = np.zeros((5, 5), dtype=bool)
        mask[1, 1] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(1, 1, 2, 2),
                mask=mask,
                origin="sam2",
                prompt_detection_ids=("bbox-1",),
                segmentation_id="sam2-drag-edit",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_segmentations=segmentations,
        )
        self.window.set_image_series(series)
        self.window.select_molecular_segmentation_at_pixel(1.0, 1.0)

        self.assertTrue(self.window.btn_edit_mask.isEnabled())
        self.window.btn_edit_mask.setChecked(True)
        self.window.cmb_mask_brush_mode.setCurrentText("Add pixels")
        self.window.sp_mask_brush_size.setValue(1)
        self.assertTrue(self.window.viewer.mask_brush_edit_mode_enabled())

        self.window.viewer.finish_mask_brush_drag_from_pixels((3.0, 3.0), (3.0, 3.0))
        self.__class__._app.processEvents()

        segmentation = series.molecular_segmentations.get_segmentation("sam2-drag-edit")
        self.assertTrue(segmentation.mask[3, 3])
        self.assertEqual(segmentation.metadata["edit_mode"], "add")
        self.assertEqual(segmentation.metadata["brush_size_px"], 1)

    def test_reset_to_sam2_result_restores_original_mask_after_manual_edit(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.zeros((1, 5, 5), dtype=np.float32)
        original_mask = np.zeros((5, 5), dtype=bool)
        original_mask[1, 1] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(1, 1, 2, 2),
                mask=original_mask,
                original_mask=original_mask,
                origin="sam2",
                prompt_detection_ids=("bbox-1",),
                segmentation_id="sam2-reset",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_segmentations=segmentations,
        )
        self.window.set_image_series(series)
        self.window.select_molecular_segmentation_at_pixel(1.0, 1.0)
        self.window.apply_mask_brush_at_pixel(3.0, 3.0, mode="add", brush_size_px=1)

        reset = self.window.reset_active_segmentation_to_sam2_result()

        segmentation = series.molecular_segmentations.get_segmentation("sam2-reset")
        self.assertTrue(reset)
        np.testing.assert_array_equal(segmentation.mask, original_mask)
        np.testing.assert_array_equal(segmentation.original_mask, original_mask)
        self.assertEqual(segmentation.bbox_xyxy, (1.0, 1.0, 2.0, 2.0))
        self.assertEqual(segmentation.metadata["mask_area_px"], 1.0)
        self.assertEqual(segmentation.metadata["mask_component_count"], 1)
        self.assertFalse(segmentation.metadata["edited"])
        self.assertIn("Reset SAM2 mask", self.window.statusBar().currentMessage())

    def test_undo_mask_edit_reverts_last_brush_stroke_only(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.zeros((1, 5, 5), dtype=np.float32)
        mask = np.zeros((5, 5), dtype=bool)
        mask[1, 1] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(1, 1, 2, 2),
                mask=mask,
                original_mask=mask,
                origin="sam2",
                prompt_detection_ids=("bbox-1",),
                segmentation_id="sam2-undo",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_segmentations=segmentations,
        )
        self.window.set_image_series(series)
        self.window.select_molecular_segmentation_at_pixel(1.0, 1.0)
        self.window.apply_mask_brush_at_pixel(3.0, 3.0, mode="add", brush_size_px=0)
        first_edit = series.molecular_segmentations.get_segmentation("sam2-undo").mask.copy()
        self.window.apply_mask_brush_at_pixel(4.0, 4.0, mode="add", brush_size_px=0)

        undone = self.window.undo_last_mask_edit()

        segmentation = series.molecular_segmentations.get_segmentation("sam2-undo")
        self.assertTrue(undone)
        np.testing.assert_array_equal(segmentation.mask, first_edit)
        self.assertEqual(segmentation.bbox_xyxy, (1.0, 1.0, 4.0, 4.0))
        self.assertEqual(segmentation.metadata["mask_area_px"], 2.0)
        self.assertIn("Undo", self.window.statusBar().currentMessage())

    def test_cancel_mask_edit_restores_state_from_edit_session_start(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.zeros((1, 5, 5), dtype=np.float32)
        mask = np.zeros((5, 5), dtype=bool)
        mask[1, 1] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(1, 1, 2, 2),
                mask=mask,
                original_mask=mask,
                origin="sam2",
                prompt_detection_ids=("bbox-1",),
                metadata={"checkpoint_name": "sam2.pt", "edited": False},
                segmentation_id="sam2-cancel",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_segmentations=segmentations,
        )
        self.window.set_image_series(series)
        self.window.select_molecular_segmentation_at_pixel(1.0, 1.0)
        self.window.btn_edit_mask.setChecked(True)
        self.window.apply_mask_brush_at_pixel(3.0, 3.0, mode="add", brush_size_px=0)
        self.window.apply_mask_brush_at_pixel(4.0, 4.0, mode="add", brush_size_px=0)

        canceled = self.window.cancel_active_mask_edit()

        segmentation = series.molecular_segmentations.get_segmentation("sam2-cancel")
        self.assertTrue(canceled)
        np.testing.assert_array_equal(segmentation.mask, mask)
        self.assertEqual(segmentation.bbox_xyxy, (1.0, 1.0, 2.0, 2.0))
        self.assertEqual(segmentation.metadata["checkpoint_name"], "sam2.pt")
        self.assertFalse(segmentation.metadata["edited"])
        self.assertFalse(self.window.btn_edit_mask.isChecked())
        self.assertIn("Cancel", self.window.statusBar().currentMessage())

    def test_apply_mask_edit_commits_current_mask_and_ends_edit_session(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.zeros((1, 5, 5), dtype=np.float32)
        mask = np.zeros((5, 5), dtype=bool)
        mask[1, 1] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(1, 1, 2, 2),
                mask=mask,
                original_mask=mask,
                origin="sam2",
                prompt_detection_ids=("bbox-1",),
                segmentation_id="sam2-apply",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_segmentations=segmentations,
        )
        self.window.set_image_series(series)
        self.window.select_molecular_segmentation_at_pixel(1.0, 1.0)
        self.window.btn_edit_mask.setChecked(True)
        self.window.apply_mask_brush_at_pixel(3.0, 3.0, mode="add", brush_size_px=0)
        committed_mask = series.molecular_segmentations.get_segmentation("sam2-apply").mask.copy()

        applied = self.window.apply_active_mask_edit()

        segmentation = series.molecular_segmentations.get_segmentation("sam2-apply")
        self.assertTrue(applied)
        np.testing.assert_array_equal(segmentation.mask, committed_mask)
        self.assertTrue(segmentation.metadata["edited"])
        self.assertFalse(self.window.btn_edit_mask.isChecked())
        self.assertIn("Apply", self.window.statusBar().currentMessage())

        self.assertFalse(self.window.undo_last_mask_edit())
        np.testing.assert_array_equal(segmentation.mask, committed_mask)

    def test_sam2_replace_existing_masks_for_same_bbox_by_default(self) -> None:
        class FakeSam2Segmenter:
            def __init__(self) -> None:
                self.calls = []

            def segment_detection(self, frame, detection, **_kwargs):
                self.calls.append(detection.detection_id)
                mask = np.zeros(frame.shape[:2], dtype=bool)
                mask[1:3, 1:3] = True
                return MolecularSegmentation(
                    frame_index=detection.frame_index,
                    source_view=detection.source_view,
                    bbox_xyxy=(1, 1, 3, 3),
                    mask=mask,
                    score=0.8,
                    origin="sam2",
                    prompt_detection_ids=(detection.detection_id,),
                    model_name="fake-sam2",
                    segmentation_id=f"sam2-seg-{len(self.calls)}",
                )

        fake_segmenter = FakeSam2Segmenter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_checkpoint_discovery=lambda: [Path(r"C:\models\sam2.1_hiera_base_plus.pt")],
            sam2_segmenter=fake_segmenter,
            sam2_settings_dialog_factory=self.sam2_dialog_factory(existing_policy="replace"),
        )
        frames = np.arange(16, dtype=np.float32).reshape(1, 4, 4)
        detections = MolecularDetectionSet(frame_count=1)
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(1, 1, 3, 3),
            confidence=0.9,
            source_view="raw",
            detection_id="bbox-1",
        )
        detections.set_detections(0, [detection], source_view="raw", frame_shape=(4, 4))
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.select_molecular_detection_at_pixel(2.0, 2.0)
        self.__class__._app.processEvents()

        self.window.btn_sam2_segment_selected.click()
        self.process_events_until(
            lambda: series.molecular_segmentations is not None
            and series.molecular_segmentations.get_segmentation("sam2-seg-1") is not None,
            timeout_s=3.0,
        )
        self.window.btn_sam2_segment_selected.click()
        self.process_events_until(
            lambda: series.molecular_segmentations.get_segmentation("sam2-seg-2") is not None,
            timeout_s=3.0,
        )

        segmentations = series.molecular_segmentations.get_segmentations(0, source_view="raw")
        self.assertEqual([segmentation.segmentation_id for segmentation in segmentations], ["sam2-seg-2"])
        np.testing.assert_array_equal(segmentations[0].original_mask, segmentations[0].mask)
        self.assertEqual(fake_segmenter.calls, ["bbox-1", "bbox-1"])

    def test_sam2_append_existing_masks_keeps_multiple_results_for_same_bbox(self) -> None:
        class FakeSam2Segmenter:
            def __init__(self) -> None:
                self.calls = []

            def segment_detection(self, frame, detection, **_kwargs):
                self.calls.append(detection.detection_id)
                mask = np.zeros(frame.shape[:2], dtype=bool)
                mask[1:3, 1:3] = True
                return MolecularSegmentation(
                    frame_index=detection.frame_index,
                    source_view=detection.source_view,
                    bbox_xyxy=(1, 1, 3, 3),
                    mask=mask,
                    score=0.8,
                    origin="sam2",
                    prompt_detection_ids=(detection.detection_id,),
                    model_name="fake-sam2",
                    segmentation_id=f"sam2-append-{len(self.calls)}",
                )

        fake_segmenter = FakeSam2Segmenter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_checkpoint_discovery=lambda: [Path(r"C:\models\sam2.1_hiera_base_plus.pt")],
            sam2_segmenter=fake_segmenter,
            sam2_settings_dialog_factory=self.sam2_dialog_factory(existing_policy="append"),
        )
        series, _detection, _frames = self.load_single_bbox_series()

        self.window.btn_sam2_segment_selected.click()
        self.process_events_until(
            lambda: series.molecular_segmentations is not None
            and series.molecular_segmentations.get_segmentation("sam2-append-1") is not None,
            timeout_s=3.0,
        )
        self.window.btn_sam2_segment_selected.click()
        self.process_events_until(
            lambda: series.molecular_segmentations.get_segmentation("sam2-append-2") is not None,
            timeout_s=3.0,
        )

        segmentations = series.molecular_segmentations.get_segmentations(0, source_view="raw")
        self.assertEqual(
            [segmentation.segmentation_id for segmentation in segmentations],
            ["sam2-append-1", "sam2-append-2"],
        )
        self.assertEqual(fake_segmenter.calls, ["bbox-1", "bbox-1"])

    def test_sam2_skip_existing_masks_does_not_call_segmenter_for_existing_bbox(self) -> None:
        class FakeSam2Segmenter:
            def __init__(self) -> None:
                self.calls = []

            def segment_detection(self, frame, detection, **_kwargs):
                self.calls.append(detection.detection_id)
                raise AssertionError("SAM2 must not run for BBoxes with existing SAM2 masks")

        fake_segmenter = FakeSam2Segmenter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_checkpoint_discovery=lambda: [Path(r"C:\models\sam2.1_hiera_base_plus.pt")],
            sam2_segmenter=fake_segmenter,
            sam2_settings_dialog_factory=self.sam2_dialog_factory(existing_policy="skip"),
        )
        series, detection, _frames = self.load_single_bbox_series()
        segmentations = MolecularSegmentationSet(frame_count=1)
        existing_mask = np.zeros((4, 4), dtype=bool)
        existing_mask[1:3, 1:3] = True
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(1, 1, 3, 3),
                mask=existing_mask,
                origin="sam2",
                prompt_detection_ids=(detection.detection_id,),
                model_name="fake-sam2",
                segmentation_id="existing-sam2-mask",
            )
        )
        series.molecular_segmentations = segmentations

        self.window.btn_sam2_segment_selected.click()
        self.__class__._app.processEvents()

        self.assertEqual(fake_segmenter.calls, [])
        self.assertEqual(series.molecular_segmentations.segmentation_count, 1)
        self.assertIn("skipped", self.window.statusBar().currentMessage().lower())

    def test_sam2_dialog_passes_selected_checkpoint_path_to_segmenter(self) -> None:
        class FakeSam2Segmenter:
            def __init__(self) -> None:
                self.calls = []

            def segment_detection(
                self,
                frame,
                detection,
                *,
                mask_probability_threshold=0.5,
                checkpoint_path=None,
                existing_masks_policy=None,
                keep_largest_component=False,
                min_mask_area_px=0,
            ):
                self.calls.append(
                    (
                        detection,
                        mask_probability_threshold,
                        checkpoint_path,
                        existing_masks_policy,
                        keep_largest_component,
                        min_mask_area_px,
                    )
                )
                mask = np.zeros(frame.shape[:2], dtype=bool)
                mask[1:3, 1:3] = True
                return MolecularSegmentation(
                    frame_index=detection.frame_index,
                    source_view=detection.source_view,
                    bbox_xyxy=(1, 1, 3, 3),
                    mask=mask,
                    score=0.8,
                    origin="sam2",
                    prompt_detection_ids=(detection.detection_id,),
                    model_name=Path(checkpoint_path).name,
                    segmentation_id="sam2-checkpoint-seg",
                )

        checkpoint_tiny = Path(r"C:\models\sam2.1_hiera_tiny.pt")
        checkpoint_base = Path(r"C:\models\sam2.1_hiera_base_plus.pt")
        dialog_calls = []
        fake_segmenter = FakeSam2Segmenter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_checkpoint_discovery=lambda: [checkpoint_tiny, checkpoint_base],
            sam2_segmenter=fake_segmenter,
            sam2_settings_dialog_factory=self.sam2_dialog_factory(
                threshold=0.61,
                checkpoint_path=checkpoint_tiny,
                existing_policy="append",
                keep_largest_component=True,
                min_mask_area_px=7,
                calls=dialog_calls,
            ),
        )
        frames = np.arange(16, dtype=np.float32).reshape(1, 4, 4)
        detections = MolecularDetectionSet(frame_count=1)
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(1, 1, 3, 3),
            confidence=0.9,
            source_view="raw",
            detection_id="bbox-1",
        )
        detections.set_detections(0, [detection], source_view="raw", frame_shape=(4, 4))
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.select_molecular_detection_at_pixel(2.0, 2.0)
        self.__class__._app.processEvents()

        self.window.btn_sam2_segment_selected.click()
        self.process_events_until(
            lambda: (
                series.molecular_segmentations is not None
                and series.molecular_segmentations.get_segmentation("sam2-checkpoint-seg") is not None
            ),
            timeout_s=3.0,
        )

        self.assertEqual([Path(path).name for path in dialog_calls[0]["checkpoints"]], [
            "sam2.1_hiera_tiny.pt",
            "sam2.1_hiera_base_plus.pt",
        ])
        self.assertEqual(Path(dialog_calls[0]["selected_checkpoint_path"]).name, "sam2.1_hiera_base_plus.pt")
        self.assertEqual(len(fake_segmenter.calls), 1)
        self.assertAlmostEqual(fake_segmenter.calls[0][1], 0.61)
        self.assertEqual(fake_segmenter.calls[0][2], checkpoint_tiny)
        self.assertEqual(fake_segmenter.calls[0][3], "append")
        self.assertTrue(fake_segmenter.calls[0][4])
        self.assertEqual(fake_segmenter.calls[0][5], 7)

    def test_sam2_segment_all_bboxes_in_current_image_stores_segmentations(self) -> None:
        class FakeSam2Segmenter:
            def __init__(self) -> None:
                self.calls = []

            def segment_detection(self, frame, detection, *, mask_probability_threshold=0.5, checkpoint_path=None, **_kwargs):
                self.calls.append((frame.copy(), detection, mask_probability_threshold))
                mask = np.zeros(frame.shape[:2], dtype=bool)
                x0, y0, x1, y1 = (int(value) for value in detection.bbox_xyxy)
                mask[y0:y1, x0:x1] = True
                return MolecularSegmentation(
                    frame_index=detection.frame_index,
                    source_view=detection.source_view,
                    bbox_xyxy=detection.bbox_xyxy,
                    mask=mask,
                    score=0.8,
                    origin="sam2",
                    prompt_detection_ids=(detection.detection_id,),
                    model_name="fake-sam2",
                    segmentation_id=f"sam2-{detection.detection_id}",
                )

        dialog_calls = []
        fake_segmenter = FakeSam2Segmenter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_segmenter=fake_segmenter,
            sam2_settings_dialog_factory=self.sam2_dialog_factory(
                threshold=0.72,
                calls=dialog_calls,
            ),
        )
        frames = np.arange(2 * 6 * 6, dtype=np.float32).reshape(2, 6, 6)
        detections = MolecularDetectionSet(frame_count=2)
        raw_frame0 = [
            MolecularDetection(
                frame_index=0,
                bbox_xyxy=(1, 1, 3, 3),
                confidence=0.9,
                source_view="raw",
                detection_id="bbox-1",
            ),
            MolecularDetection(
                frame_index=0,
                bbox_xyxy=(3, 2, 5, 5),
                confidence=0.8,
                source_view="raw",
                detection_id="bbox-2",
            ),
        ]
        detections.set_detections(0, raw_frame0, source_view="raw", frame_shape=(6, 6))
        detections.set_detections(
            1,
            [
                MolecularDetection(
                    frame_index=1,
                    bbox_xyxy=(0, 0, 2, 2),
                    confidence=0.7,
                    source_view="raw",
                    detection_id="bbox-other-frame",
                )
            ],
            source_view="raw",
            frame_shape=(6, 6),
        )
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(0, 0, 2, 2),
                    confidence=0.6,
                    source_view="expanded_aligned",
                    detection_id="bbox-expanded",
                )
            ],
            source_view="expanded_aligned",
            frame_shape=(6, 6),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=6, pixels_y=6),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)

        self.assertTrue(self.window.btn_sam2_segment_all_current.isEnabled())
        self.window.btn_sam2_segment_all_current.click()
        self.process_events_until(
            lambda: (
                series.molecular_segmentations is not None
                and series.molecular_segmentations.segmentation_count == 2
            ),
            timeout_s=3.0,
        )

        self.assertEqual(len(dialog_calls), 1)
        self.assertEqual(dialog_calls[0]["bbox_count"], 2)
        self.assertAlmostEqual(dialog_calls[0]["initial_mask_threshold"], 0.5)
        self.assertEqual([call[1].detection_id for call in fake_segmenter.calls], ["bbox-1", "bbox-2"])
        self.assertTrue(all(call[2] == 0.72 for call in fake_segmenter.calls))
        np.testing.assert_array_equal(fake_segmenter.calls[0][0], frames[0])
        np.testing.assert_array_equal(fake_segmenter.calls[1][0], frames[0])
        segmentations = series.molecular_segmentations.get_segmentations(0, source_view="raw")
        self.assertEqual(
            [segmentation.segmentation_id for segmentation in segmentations],
            ["sam2-bbox-1", "sam2-bbox-2"],
        )
        self.assertEqual(self.window.viewer.visible_molecular_segmentation_ids(), ["sam2-bbox-1", "sam2-bbox-2"])
        self.process_events_until(
            lambda: "SAM2 segmented 2 BBox(es)" in self.window.statusBar().currentMessage(),
            timeout_s=3.0,
        )
        self.assertIn("SAM2 segmented 2 BBox(es)", self.window.statusBar().currentMessage())

    def test_sam2_all_current_uses_one_frame_batch_and_reports_chunk_progress(self) -> None:
        class SlowBatchSam2Segmenter:
            def __init__(self) -> None:
                self.batch_calls = []
                self.legacy_calls = []

            def segment_frame_detections(self, frame, detections, **kwargs):
                detections = list(detections)
                self.batch_calls.append((np.asarray(frame).copy(), detections, dict(kwargs)))
                time.sleep(0.2)
                results = []
                for detection in detections:
                    mask = np.zeros(frame.shape[:2], dtype=bool)
                    x1, y1, x2, y2 = (int(value) for value in detection.bbox_xyxy)
                    mask[y1:y2, x1:x2] = True
                    results.append(
                        MolecularSegmentation(
                            frame_index=detection.frame_index,
                            source_view=detection.source_view,
                            bbox_xyxy=detection.bbox_xyxy,
                            mask=mask,
                            origin="sam2",
                            prompt_detection_ids=(detection.detection_id,),
                            segmentation_id=f"sam2-batch-{detection.detection_id}",
                        )
                    )
                return results

            def segment_detection(self, frame, detection, **kwargs):
                self.legacy_calls.append((frame, detection, kwargs))
                raise AssertionError("All BBoxes In Image must use one frame batch")

        segmenter = SlowBatchSam2Segmenter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_checkpoint_discovery=lambda: [Path(r"C:\models\sam2.pt")],
            sam2_segmenter=segmenter,
            sam2_settings_dialog_factory=self.sam2_dialog_factory(threshold=0.71),
        )
        frames = np.arange(36, dtype=np.float32).reshape(1, 6, 6)
        detections = MolecularDetectionSet(frame_count=1)
        frame_detections = [
            MolecularDetection(
                frame_index=0,
                bbox_xyxy=(1, 1, 3, 3),
                confidence=0.9,
                detection_id="one",
            ),
            MolecularDetection(
                frame_index=0,
                bbox_xyxy=(3, 2, 5, 5),
                confidence=0.8,
                detection_id="two",
            ),
        ]
        detections.set_detections(
            0,
            frame_detections,
            source_view="raw",
            frame_shape=(6, 6),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=6, pixels_y=6),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)

        self.window.btn_sam2_segment_all_current.click()
        self.process_events_until(
            lambda: self.window._sam2_segmentation_progress_dialog is not None
            and "Chunks 0/1"
            in self.window._sam2_segmentation_progress_dialog.labelText(),
        )
        progress_label = self.window._sam2_segmentation_progress_dialog.labelText()
        self.assertIn("BBox 1/2", progress_label)
        self.assertIn("Chunks 0/1", progress_label)
        self.process_events_until(
            lambda: series.molecular_segmentations is not None
            and series.molecular_segmentations.segmentation_count == 2,
        )

        self.assertEqual(len(segmenter.batch_calls), 1)
        self.assertEqual(segmenter.batch_calls[0][1], frame_detections)
        self.assertAlmostEqual(
            segmenter.batch_calls[0][2]["mask_probability_threshold"],
            0.71,
        )
        self.assertEqual(segmenter.legacy_calls, [])
        self.assertEqual(
            [item.segmentation_id for item in series.molecular_segmentations.get_segmentations(0)],
            ["sam2-batch-one", "sam2-batch-two"],
        )

    def test_sam2_segment_all_bboxes_in_inclusive_frame_range(self) -> None:
        class FakeSam2Segmenter:
            def __init__(self) -> None:
                self.calls = []

            def segment_detection(self, frame, detection, **_kwargs):
                self.calls.append((np.asarray(frame).copy(), detection))
                mask = np.zeros(frame.shape[:2], dtype=bool)
                x0, y0, x1, y1 = (int(value) for value in detection.bbox_xyxy)
                mask[y0:y1, x0:x1] = True
                return MolecularSegmentation(
                    frame_index=detection.frame_index,
                    source_view=detection.source_view,
                    bbox_xyxy=detection.bbox_xyxy,
                    mask=mask,
                    origin="sam2",
                    prompt_detection_ids=(detection.detection_id,),
                    segmentation_id=f"sam2-{detection.detection_id}",
                )

        dialog_calls = []
        segmenter = FakeSam2Segmenter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_checkpoint_discovery=lambda: [Path(r"C:\models\sam2.pt")],
            sam2_segmenter=segmenter,
            sam2_settings_dialog_factory=self.sam2_dialog_factory(calls=dialog_calls),
        )
        frames = np.stack(
            [np.full((6, 6), frame_index, dtype=np.float32) for frame_index in range(4)]
        )
        detections = MolecularDetectionSet(frame_count=4)
        detections.set_detections(
            0,
            [MolecularDetection(0, (0, 0, 2, 2), 0.9, detection_id="outside-range")],
            source_view="raw",
            frame_shape=(6, 6),
        )
        detections.set_detections(
            1,
            [
                MolecularDetection(1, (1, 1, 3, 3), 0.9, detection_id="frame-2-a"),
                MolecularDetection(1, (3, 1, 5, 3), 0.8, detection_id="frame-2-b"),
            ],
            source_view="raw",
            frame_shape=(6, 6),
        )
        detections.set_detections(
            3,
            [MolecularDetection(3, (2, 2, 4, 4), 0.7, detection_id="frame-4-a")],
            source_view="raw",
            frame_shape=(6, 6),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=6, pixels_y=6),
            active_frame_index=1,
            molecular_detections=detections,
        )
        self.window.set_image_series(series)

        self.assertEqual(self.window.sp_sam2_range_end_frame.minimum(), 2)
        self.assertEqual(self.window.sp_sam2_range_end_frame.maximum(), 4)
        self.window.sp_sam2_range_end_frame.setValue(4)
        self.assertTrue(self.window.btn_sam2_segment_range.isEnabled())
        self.window.btn_sam2_segment_range.click()
        self.process_events_until(
            lambda: series.molecular_segmentations is not None
            and series.molecular_segmentations.segmentation_count == 3,
            timeout_s=3.0,
        )
        self.process_events_until(
            lambda: self.window._sam2_segmentation_progress_dialog is None,
            timeout_s=3.0,
        )

        self.assertEqual(dialog_calls[0]["bbox_count"], 3)
        self.assertEqual(
            [call[1].detection_id for call in segmenter.calls],
            ["frame-2-a", "frame-2-b", "frame-4-a"],
        )
        self.assertEqual([float(call[0][0, 0]) for call in segmenter.calls], [1.0, 1.0, 3.0])
        self.assertEqual(series.active_frame_index, 1)
        self.assertIsNone(series.molecular_segmentations.get_segmentation("sam2-outside-range"))
        self.assertEqual(
            [
                segmentation.segmentation_id
                for segmentation in series.molecular_segmentations.get_segmentations(1)
            ],
            ["sam2-frame-2-a", "sam2-frame-2-b"],
        )
        self.process_events_until(
            lambda: "frames 2-4" in self.window.statusBar().currentMessage(),
            timeout_s=3.0,
        )
        self.assertIn("frames 2-4", self.window.statusBar().currentMessage())

    def test_sam2_range_uses_one_persistent_session_and_skips_empty_frames(self) -> None:
        class ProgressRecordingWindow(MolTrackMainWindow):
            def __init__(self, *args, **kwargs) -> None:
                self.sam2_progress_events = []
                super().__init__(*args, **kwargs)

            def _on_sam2_segmentation_progress(self, progress) -> None:
                self.sam2_progress_events.append(progress)
                super()._on_sam2_segmentation_progress(progress)

        class FakePersistentSession:
            def __init__(self, owner) -> None:
                self.owner = owner

            def __enter__(self):
                self.owner.enter_count += 1
                return self

            def __exit__(self, exc_type, exc_value, traceback) -> None:
                self.owner.exit_count += 1

            def segment_frame_detections(self, frame, detections, **kwargs):
                detections = list(detections)
                segmentation_set = self.owner.series.molecular_segmentations
                self.owner.saved_counts_before_frame.append(
                    0 if segmentation_set is None else segmentation_set.segmentation_count
                )
                self.owner.frame_calls.append(
                    (
                        detections[0].frame_index,
                        np.asarray(frame).copy(),
                        [detection.detection_id for detection in detections],
                        dict(kwargs),
                    )
                )
                results = []
                for detection in detections:
                    mask = np.zeros(frame.shape[:2], dtype=bool)
                    x0, y0, x1, y1 = (int(value) for value in detection.bbox_xyxy)
                    mask[y0:y1, x0:x1] = True
                    results.append(
                        MolecularSegmentation(
                            frame_index=detection.frame_index,
                            source_view=detection.source_view,
                            bbox_xyxy=detection.bbox_xyxy,
                            mask=mask,
                            origin="sam2",
                            prompt_detection_ids=(detection.detection_id,),
                            segmentation_id=f"sam2-{detection.detection_id}",
                        )
                    )
                return results

        class FakePersistentSegmenter:
            def __init__(self) -> None:
                self.open_checkpoints = []
                self.enter_count = 0
                self.exit_count = 0
                self.frame_calls = []
                self.saved_counts_before_frame = []
                self.series = None

            def open_persistent_image_session(self, *, checkpoint_path=None):
                self.open_checkpoints.append(Path(checkpoint_path))
                return FakePersistentSession(self)

        segmenter = FakePersistentSegmenter()
        checkpoint_path = Path(r"C:\models\sam2.pt")
        self.window = ProgressRecordingWindow(
            yolo_model_discovery=lambda: [],
            sam2_checkpoint_discovery=lambda: [checkpoint_path],
            sam2_segmenter=segmenter,
            sam2_settings_dialog_factory=self.sam2_dialog_factory(
                threshold=0.67,
                checkpoint_path=checkpoint_path,
            ),
        )
        frames = np.stack(
            [np.full((6, 6), frame_index, dtype=np.float32) for frame_index in range(3)]
        )
        detections = MolecularDetectionSet(frame_count=3)
        detections.set_detections(
            0,
            [
                MolecularDetection(0, (1, 1, 3, 3), 0.9, detection_id="frame-1-a"),
                MolecularDetection(0, (3, 1, 5, 3), 0.8, detection_id="frame-1-b"),
            ],
            source_view="raw",
            frame_shape=(6, 6),
        )
        detections.set_detections(
            2,
            [MolecularDetection(2, (2, 2, 4, 4), 0.7, detection_id="frame-3-a")],
            source_view="raw",
            frame_shape=(6, 6),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=6, pixels_y=6),
            active_frame_index=0,
            molecular_detections=detections,
        )
        segmenter.series = series
        self.window.set_image_series(series)
        self.window.sp_sam2_range_end_frame.setValue(3)

        self.window.btn_sam2_segment_range.click()
        self.process_events_until(
            lambda: series.molecular_segmentations is not None
            and series.molecular_segmentations.segmentation_count == 3,
            timeout_s=3.0,
        )

        self.process_events_until(
            lambda: self.window._sam2_segmentation_progress_dialog is None,
            timeout_s=3.0,
        )
        self.assertEqual(segmenter.open_checkpoints, [checkpoint_path])
        self.assertEqual(segmenter.enter_count, 1)
        self.assertEqual(segmenter.exit_count, 1)
        self.assertEqual(
            [(call[0], call[2]) for call in segmenter.frame_calls],
            [
                (0, ["frame-1-a", "frame-1-b"]),
                (2, ["frame-3-a"]),
            ],
        )
        self.assertEqual([float(call[1][0, 0]) for call in segmenter.frame_calls], [0.0, 2.0])
        self.assertEqual(segmenter.saved_counts_before_frame, [0, 2])
        self.assertTrue(
            all(call[3]["mask_probability_threshold"] == 0.67 for call in segmenter.frame_calls)
        )
        self.assertEqual(series.active_frame_index, 0)
        progress_events = self.window.sam2_progress_events
        self.assertEqual(
            [event.phase for event in progress_events],
            [
                "Loading model",
                "Embedding frame",
                "Segmenting chunk",
                "Saving frame results",
                "Embedding frame",
                "Segmenting chunk",
                "Saving frame results",
            ],
        )
        self.assertTrue(all(event.total_bbox_count == 3 for event in progress_events))
        self.assertTrue(all(event.total_chunk_count == 2 for event in progress_events))
        self.assertEqual(
            [event.completed_bbox_count for event in progress_events],
            [0, 0, 0, 2, 2, 2, 3],
        )
        self.assertEqual(
            [event.completed_chunk_count for event in progress_events],
            [0, 0, 0, 1, 1, 1, 2],
        )

    def test_sam2_range_skips_rejected_prompt_and_saves_other_masks(self) -> None:
        class FakeSession:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback) -> None:
                return None

            def segment_frame_detections(self, frame, detections, **kwargs):
                self.test_case.assertAlmostEqual(
                    kwargs["mask_probability_threshold"],
                    0.95,
                )
                outcomes = []
                for detection in detections:
                    if detection.detection_id == "empty-prompt":
                        outcomes.append(
                            MolTrackSam2PromptRejection(
                                prompt_detection_id=detection.detection_id,
                                reason="SAM2 returned an empty mask after post-processing.",
                            )
                        )
                        continue
                    mask = np.zeros(frame.shape[:2], dtype=bool)
                    x0, y0, x1, y1 = (int(value) for value in detection.bbox_xyxy)
                    mask[y0:y1, x0:x1] = True
                    outcomes.append(
                        MolecularSegmentation(
                            frame_index=detection.frame_index,
                            source_view=detection.source_view,
                            bbox_xyxy=detection.bbox_xyxy,
                            mask=mask,
                            origin="sam2",
                            prompt_detection_ids=(detection.detection_id,),
                            segmentation_id=f"sam2-{detection.detection_id}",
                        )
                    )
                return outcomes

        class FakeSegmenter:
            def open_persistent_image_session(self, *, checkpoint_path=None):
                session = FakeSession()
                session.test_case = self.test_case
                return session

        segmenter = FakeSegmenter()
        segmenter.test_case = self
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_checkpoint_discovery=lambda: [Path(r"C:\models\sam2.pt")],
            sam2_segmenter=segmenter,
            sam2_settings_dialog_factory=self.sam2_dialog_factory(threshold=0.95),
        )
        frames = np.zeros((2, 6, 6), dtype=np.float32)
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(0, (1, 1, 3, 3), 0.9, detection_id="valid-first"),
                MolecularDetection(0, (3, 1, 5, 3), 0.8, detection_id="empty-prompt"),
            ],
            source_view="raw",
            frame_shape=(6, 6),
        )
        detections.set_detections(
            1,
            [MolecularDetection(1, (2, 2, 4, 4), 0.7, detection_id="valid-second")],
            source_view="raw",
            frame_shape=(6, 6),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=6, pixels_y=6),
            active_frame_index=0,
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.sp_sam2_range_end_frame.setValue(2)

        with patch.object(QMessageBox, "critical") as critical:
            self.window.btn_sam2_segment_range.click()
            self.process_events_until(
                lambda: self.window._sam2_segmentation_progress_dialog is None,
                timeout_s=3.0,
            )

        critical.assert_not_called()
        self.assertIsNotNone(series.molecular_segmentations)
        self.assertEqual(series.molecular_segmentations.segmentation_count, 2)
        self.assertEqual(
            {
                segmentation.prompt_detection_ids[0]
                for frame_index in range(2)
                for segmentation in series.molecular_segmentations.get_segmentations(frame_index)
            },
            {"valid-first", "valid-second"},
        )
        self.process_events_until(
            lambda: "skipped 1" in self.window.statusBar().currentMessage(),
            timeout_s=3.0,
        )

    def test_sam2_persistent_range_does_not_send_frame_emptied_by_skip_existing(self) -> None:
        class FakeSession:
            def __init__(self, owner) -> None:
                self.owner = owner

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback) -> None:
                pass

            def segment_frame_detections(self, frame, detections, **_kwargs):
                detections = list(detections)
                self.owner.frame_indices.append(detections[0].frame_index)
                detection = detections[0]
                mask = np.zeros(frame.shape[:2], dtype=bool)
                mask[1:3, 1:3] = True
                return [
                    MolecularSegmentation(
                        frame_index=detection.frame_index,
                        source_view=detection.source_view,
                        bbox_xyxy=(1, 1, 3, 3),
                        mask=mask,
                        origin="sam2",
                        prompt_detection_ids=(detection.detection_id,),
                        segmentation_id=f"sam2-{detection.detection_id}",
                    )
                ]

        class FakeSegmenter:
            def __init__(self) -> None:
                self.frame_indices = []
                self.open_count = 0

            def open_persistent_image_session(self, *, checkpoint_path=None):
                self.open_count += 1
                return FakeSession(self)

        segmenter = FakeSegmenter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_checkpoint_discovery=lambda: [Path(r"C:\models\sam2.pt")],
            sam2_segmenter=segmenter,
            sam2_settings_dialog_factory=self.sam2_dialog_factory(existing_policy="skip"),
        )
        frames = np.zeros((2, 4, 4), dtype=np.float32)
        detections = MolecularDetectionSet(frame_count=2)
        first_detection = MolecularDetection(
            0,
            (1, 1, 3, 3),
            0.9,
            detection_id="already-segmented",
        )
        second_detection = MolecularDetection(
            1,
            (1, 1, 3, 3),
            0.8,
            detection_id="needs-segmentation",
        )
        detections.set_detections(
            0,
            [first_detection],
            source_view="raw",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            1,
            [second_detection],
            source_view="raw",
            frame_shape=(4, 4),
        )
        segmentations = MolecularSegmentationSet(frame_count=2)
        existing_mask = np.zeros((4, 4), dtype=bool)
        existing_mask[1:3, 1:3] = True
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(1, 1, 3, 3),
                mask=existing_mask,
                origin="sam2",
                prompt_detection_ids=(first_detection.detection_id,),
                segmentation_id="existing-sam2",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
            molecular_segmentations=segmentations,
        )
        self.window.set_image_series(series)
        self.window.sp_sam2_range_end_frame.setValue(2)

        self.window.btn_sam2_segment_range.click()
        self.process_events_until(
            lambda: series.molecular_segmentations.segmentation_count == 2,
            timeout_s=3.0,
        )

        self.assertEqual(segmenter.open_count, 1)
        self.assertEqual(segmenter.frame_indices, [1])
        self.assertIsNotNone(
            series.molecular_segmentations.get_segmentation("existing-sam2")
        )
        self.assertIsNotNone(
            series.molecular_segmentations.get_segmentation("sam2-needs-segmentation")
        )

    def test_cancel_sam2_persistent_range_keeps_completed_frames_and_restores_ui(self) -> None:
        class FakeSession:
            def __init__(self, owner) -> None:
                self.owner = owner

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback) -> None:
                self.owner.session_closed = True

            def cancel(self) -> None:
                self.owner.cancel_requested.set()

            def segment_frame_detections(self, frame, detections, **_kwargs):
                detection = list(detections)[0]
                if detection.frame_index == 1:
                    self.owner.second_frame_started.set()
                    self.owner.cancel_requested.wait(timeout=2.0)
                    if self.owner.cancel_requested.is_set():
                        raise RuntimeError("persistent session canceled")
                mask = np.zeros(frame.shape[:2], dtype=bool)
                mask[1:3, 1:3] = True
                return [
                    MolecularSegmentation(
                        frame_index=detection.frame_index,
                        source_view=detection.source_view,
                        bbox_xyxy=(1, 1, 3, 3),
                        mask=mask,
                        origin="sam2",
                        prompt_detection_ids=(detection.detection_id,),
                        segmentation_id=f"sam2-{detection.detection_id}",
                    )
                ]

        class FakeSegmenter:
            def __init__(self) -> None:
                self.cancel_requested = threading.Event()
                self.second_frame_started = threading.Event()
                self.session_closed = False
                self.session = FakeSession(self)

            def open_persistent_image_session(self, *, checkpoint_path=None):
                return self.session

        segmenter = FakeSegmenter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_checkpoint_discovery=lambda: [Path(r"C:\models\sam2.pt")],
            sam2_segmenter=segmenter,
            sam2_settings_dialog_factory=self.sam2_dialog_factory(),
        )
        frames = np.zeros((2, 4, 4), dtype=np.float32)
        detections = MolecularDetectionSet(frame_count=2)
        for frame_index in range(2):
            detections.set_detections(
                frame_index,
                [
                    MolecularDetection(
                        frame_index,
                        (1, 1, 3, 3),
                        0.9,
                        detection_id=f"bbox-{frame_index}",
                    )
                ],
                source_view="raw",
                frame_shape=(4, 4),
            )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.sp_sam2_range_end_frame.setValue(2)

        with patch.object(QMessageBox, "critical"):
            self.window.btn_sam2_segment_range.click()
            self.process_events_until(
                lambda: series.molecular_segmentations is not None
                and series.molecular_segmentations.segmentation_count == 1
                and segmenter.second_frame_started.is_set(),
                timeout_s=3.0,
            )
            progress_dialog = self.window._sam2_segmentation_progress_dialog
            cancel_button = next(
                (
                    button
                    for button in progress_dialog.findChildren(QPushButton)
                    if button.text() == "Cancel"
                ),
                None,
            )
            if cancel_button is None:
                segmenter.cancel_requested.set()
            else:
                cancel_button.click()
            self.process_events_until(
                lambda: not self.window._sam2_segmentation_running,
                timeout_s=3.0,
            )

        self.assertIsNotNone(cancel_button)
        self.assertTrue(segmenter.cancel_requested.is_set())
        self.assertTrue(segmenter.session_closed)
        self.assertEqual(series.molecular_segmentations.segmentation_count, 1)
        self.assertIsNotNone(series.molecular_segmentations.get_segmentation("sam2-bbox-0"))
        self.assertIsNone(series.molecular_segmentations.get_segmentation("sam2-bbox-1"))
        self.assertIsNone(self.window._sam2_segmentation_progress_dialog)
        self.assertTrue(self.window.btn_sam2_segment_range.isEnabled())
        self.assertIn("canceled", self.window.statusBar().currentMessage().lower())

    def test_sam2_range_oom_keeps_completed_frames_and_explains_chunk_recovery(self) -> None:
        class FakeSession:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback) -> None:
                pass

            def segment_frame_detections(self, frame, detections, **_kwargs):
                detection = list(detections)[0]
                if detection.frame_index == 1:
                    raise RuntimeError("CUDA out of memory while decoding SAM2 chunk")
                mask = np.zeros(frame.shape[:2], dtype=bool)
                mask[1:3, 1:3] = True
                return [
                    MolecularSegmentation(
                        frame_index=0,
                        source_view="raw",
                        bbox_xyxy=(1, 1, 3, 3),
                        mask=mask,
                        origin="sam2",
                        prompt_detection_ids=(detection.detection_id,),
                        segmentation_id="sam2-first-complete",
                    )
                ]

        class FakeSegmenter:
            def open_persistent_image_session(self, *, checkpoint_path=None):
                return FakeSession()

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_checkpoint_discovery=lambda: [Path(r"C:\models\sam2.pt")],
            sam2_segmenter=FakeSegmenter(),
            sam2_settings_dialog_factory=self.sam2_dialog_factory(),
        )
        frames = np.zeros((2, 4, 4), dtype=np.float32)
        detections = MolecularDetectionSet(frame_count=2)
        for frame_index in range(2):
            detections.set_detections(
                frame_index,
                [
                    MolecularDetection(
                        frame_index,
                        (1, 1, 3, 3),
                        0.9,
                        detection_id=f"bbox-{frame_index}",
                    )
                ],
                source_view="raw",
                frame_shape=(4, 4),
            )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.sp_sam2_range_end_frame.setValue(2)
        error_messages = []

        with patch.object(
            QMessageBox,
            "critical",
            side_effect=lambda _parent, _title, message: error_messages.append(str(message)),
        ):
            self.window.btn_sam2_segment_range.click()
            self.process_events_until(
                lambda: not self.window._sam2_segmentation_running,
                timeout_s=3.0,
            )

        self.assertEqual(series.molecular_segmentations.segmentation_count, 1)
        self.assertIsNotNone(
            series.molecular_segmentations.get_segmentation("sam2-first-complete")
        )
        self.assertEqual(len(error_messages), 1)
        self.assertIn("CUDA out of memory", error_messages[0])
        self.assertIn("smaller SAM2 chunk", error_messages[0])
        self.assertIn("checkpoint was not changed", error_messages[0])
        self.assertTrue(self.window.btn_sam2_segment_range.isEnabled())

    def test_sam2_range_progress_shows_frame_and_bbox_positions(self) -> None:
        class SlowSam2Segmenter:
            def segment_detection(self, frame, detection, **_kwargs):
                time.sleep(0.15)
                mask = np.zeros(frame.shape[:2], dtype=bool)
                mask[1:3, 1:3] = True
                return MolecularSegmentation(
                    frame_index=detection.frame_index,
                    source_view=detection.source_view,
                    bbox_xyxy=(1, 1, 3, 3),
                    mask=mask,
                    origin="sam2",
                    prompt_detection_ids=(detection.detection_id,),
                    segmentation_id=f"sam2-{detection.detection_id}",
                )

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_checkpoint_discovery=lambda: [Path(r"C:\models\sam2.pt")],
            sam2_segmenter=SlowSam2Segmenter(),
            sam2_settings_dialog_factory=self.sam2_dialog_factory(),
        )
        frames = np.zeros((3, 4, 4), dtype=np.float32)
        detections = MolecularDetectionSet(frame_count=3)
        for frame_index in (1, 2):
            detections.set_detections(
                frame_index,
                [
                    MolecularDetection(
                        frame_index,
                        (1, 1, 3, 3),
                        0.9,
                        detection_id=f"bbox-{frame_index + 1}",
                    )
                ],
                source_view="raw",
                frame_shape=(4, 4),
            )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            active_frame_index=1,
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.sp_sam2_range_end_frame.setValue(3)

        self.window.btn_sam2_segment_range.click()
        self.process_events_until(
            lambda: (
                self.window._sam2_segmentation_progress_dialog is not None
                and "Frame 2/3" in self.window._sam2_segmentation_progress_dialog.labelText()
                and "BBox 1/2" in self.window._sam2_segmentation_progress_dialog.labelText()
            ),
            timeout_s=3.0,
        )

        label = self.window._sam2_segmentation_progress_dialog.labelText()
        self.assertIn("Frame 2/3", label)
        self.assertIn("BBox 1/2", label)
        self.assertIn("1/1 in frame", label)
        self.assertFalse(self.window.btn_sam2_segment_range.isEnabled())
        self.process_events_until(
            lambda: series.molecular_segmentations is not None
            and series.molecular_segmentations.segmentation_count == 2,
            timeout_s=3.0,
        )
        self.process_events_until(
            lambda: self.window._sam2_segmentation_progress_dialog is None,
            timeout_s=3.0,
        )
        self.assertTrue(self.window.btn_sam2_segment_range.isEnabled())

    def test_sam2_expanded_range_runs_each_frame_on_raw_and_transforms_results_back(self) -> None:
        calls = []

        class FakeSam2Segmenter:
            def __init__(self) -> None:
                self.open_count = 0

            def open_persistent_image_session(self, *, checkpoint_path=None):
                self.open_count += 1
                return self

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback) -> None:
                pass

            def segment_frame_detections(self, frame, detections, **_kwargs):
                return [
                    self.segment_detection(frame, detection)
                    for detection in detections
                ]

            def segment_detection(self, frame, detection, **_kwargs):
                calls.append((np.asarray(frame).copy(), detection))
                mask = np.zeros(frame.shape[:2], dtype=bool)
                x0, y0, x1, y1 = (int(value) for value in detection.bbox_xyxy)
                mask[y0:y1, x0:x1] = True
                return MolecularSegmentation(
                    frame_index=detection.frame_index,
                    source_view=detection.source_view,
                    bbox_xyxy=detection.bbox_xyxy,
                    mask=mask,
                    original_mask=mask,
                    origin="sam2",
                    prompt_detection_ids=(detection.detection_id,),
                    segmentation_id=f"sam2-{detection.detection_id}",
                )

        raw_frames = np.stack(
            [
                np.full((4, 5), 1.0, dtype=np.float32),
                np.full((4, 5), 2.0, dtype=np.float32),
            ]
        )
        expanded_frames = np.full((2, 6, 8), np.nan, dtype=np.float32)
        expanded_frames[0, 1:5, 1:6] = raw_frames[0]
        expanded_frames[1, 0:4, 2:7] = raw_frames[1]

        def fake_expanded_builder(series):
            stack = SimpleNamespace(
                frames=expanded_frames,
                metadata=STMSequenceMetadata(pixels_x=8, pixels_y=6),
                padding_ltrb=(1, 1, 2, 1),
                frame_origins_xy=np.asarray(((1.0, 1.0), (2.0, 0.0))),
            )
            series.expanded_aligned_stack = stack
            return stack

        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    0,
                    (2, 2, 4, 4),
                    0.9,
                    source_view="expanded_aligned",
                    detection_id="expanded-1",
                )
            ],
            source_view="expanded_aligned",
            frame_shape=(6, 8),
        )
        detections.set_detections(
            1,
            [
                MolecularDetection(
                    1,
                    (2, 1, 4, 3),
                    0.8,
                    source_view="expanded_aligned",
                    detection_id="expanded-2",
                )
            ],
            source_view="expanded_aligned",
            frame_shape=(6, 8),
        )
        registration_settings = MolTrackRegistrationSettings()
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=raw_frames,
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=4),
            registration_results=MolTrackRegistrationResultSet(
                settings=registration_settings,
                results_by_frame={
                    0: MolTrackRegistrationFrameResult(0, (0.0, 0.0), "identity"),
                    1: MolTrackRegistrationFrameResult(1, (1.0, -1.0), "test"),
                },
            ),
            molecular_detections=detections,
        )
        segmenter = FakeSam2Segmenter()
        self.window = MolTrackMainWindow(
            expanded_aligned_builder=fake_expanded_builder,
            yolo_model_discovery=lambda: [],
            sam2_checkpoint_discovery=lambda: [Path(r"C:\models\sam2.pt")],
            sam2_segmenter=segmenter,
            sam2_settings_dialog_factory=self.sam2_dialog_factory(),
        )
        self.window.set_image_series(series)
        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.window.sp_sam2_range_end_frame.setValue(2)

        self.window.btn_sam2_segment_range.click()
        self.process_events_until(
            lambda: series.molecular_segmentations is not None
            and series.molecular_segmentations.segmentation_count == 2,
            timeout_s=3.0,
        )

        self.assertEqual(segmenter.open_count, 1)
        self.assertEqual([call[1].source_view for call in calls], ["raw", "raw"])
        self.assertEqual([call[1].bbox_xyxy for call in calls], [(1.0, 1.0, 3.0, 3.0), (0.0, 1.0, 2.0, 3.0)])
        self.assertEqual([float(call[0][0, 0]) for call in calls], [1.0, 2.0])
        first = series.molecular_segmentations.get_segmentation("sam2-expanded-1")
        second = series.molecular_segmentations.get_segmentation("sam2-expanded-2")
        self.assertEqual(first.source_view, "expanded_aligned")
        self.assertEqual(first.bbox_xyxy, (2.0, 2.0, 4.0, 4.0))
        self.assertEqual(second.source_view, "expanded_aligned")
        self.assertEqual(second.bbox_xyxy, (2.0, 1.0, 4.0, 3.0))

    def test_sam2_expanded_bbox_runs_on_raw_and_transforms_mask_back_to_expanded(self) -> None:
        calls = []

        class FakeSam2Segmenter:
            def segment_detection(self, frame, detection, **_kwargs):
                calls.append((np.asarray(frame).copy(), detection))
                mask = np.zeros(frame.shape[:2], dtype=bool)
                mask[1:3, 1:4] = True
                return MolecularSegmentation(
                    frame_index=detection.frame_index,
                    source_view=detection.source_view,
                    bbox_xyxy=(1, 1, 4, 3),
                    mask=mask,
                    original_mask=mask,
                    score=0.8,
                    origin="sam2",
                    prompt_detection_ids=(detection.detection_id,),
                    model_name="fake-sam2",
                    segmentation_id="sam2-expanded",
                )

        raw_frame = np.arange(20, dtype=np.float32).reshape(4, 5)
        expanded_frame = np.full((7, 8), np.nan, dtype=np.float32)
        expanded_frame[1:5, 2:7] = raw_frame

        def fake_expanded_builder(series):
            stack = SimpleNamespace(
                frames=expanded_frame[np.newaxis, ...],
                metadata=STMSequenceMetadata(pixels_x=8, pixels_y=7),
                padding_ltrb=(2, 1, 1, 2),
                frame_origins_xy=np.asarray(((2.0, 1.0),), dtype=np.float64),
            )
            series.expanded_aligned_stack = stack
            return stack

        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(3, 2, 6, 4),
                    confidence=0.9,
                    source_view="expanded_aligned",
                    detection_id="expanded-bbox",
                )
            ],
            source_view="expanded_aligned",
            frame_shape=expanded_frame.shape,
        )
        settings = MolTrackRegistrationSettings()
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=raw_frame[np.newaxis, ...],
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=4),
            registration_results=MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    0: MolTrackRegistrationFrameResult(
                        frame_index=0,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                    )
                },
            ),
            molecular_detections=detections,
        )
        self.window = MolTrackMainWindow(
            expanded_aligned_builder=fake_expanded_builder,
            yolo_model_discovery=lambda: [],
            sam2_segmenter=FakeSam2Segmenter(),
            sam2_settings_dialog_factory=self.sam2_dialog_factory(),
        )
        self.window.set_image_series(series)
        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.window.select_molecular_detection_at_pixel(4.0, 3.0)

        self.window.btn_sam2_segment_selected.click()
        self.process_events_until(
            lambda: series.molecular_segmentations is not None
            and series.molecular_segmentations.get_segmentation("sam2-expanded") is not None,
        )

        self.assertEqual(len(calls), 1)
        np.testing.assert_array_equal(calls[0][0], raw_frame)
        self.assertEqual(calls[0][1].source_view, "raw")
        self.assertEqual(calls[0][1].bbox_xyxy, (1.0, 1.0, 4.0, 3.0))
        self.assertEqual(calls[0][1].detection_id, "expanded-bbox")
        segmentation = series.molecular_segmentations.get_segmentation("sam2-expanded")
        self.assertEqual(segmentation.source_view, "expanded_aligned")
        self.assertEqual(segmentation.bbox_xyxy, (3.0, 2.0, 6.0, 4.0))
        self.assertEqual(segmentation.prompt_detection_ids, ("expanded-bbox",))
        expected_mask = np.zeros(expanded_frame.shape, dtype=bool)
        expected_mask[2:4, 3:6] = True
        np.testing.assert_array_equal(segmentation.mask, expected_mask)
        np.testing.assert_array_equal(segmentation.original_mask, expected_mask)

    def test_sam2_segment_selected_bbox_runs_in_worker_with_progress_dialog_and_threshold(self) -> None:
        class SlowSam2Segmenter:
            def __init__(self) -> None:
                self.calls = []

            def segment_detection(self, frame, detection, *, mask_probability_threshold=0.5, checkpoint_path=None, **_kwargs):
                self.calls.append((frame.copy(), detection, mask_probability_threshold))
                time.sleep(0.25)
                mask = np.zeros(frame.shape[:2], dtype=bool)
                mask[1:3, 1:3] = True
                return MolecularSegmentation(
                    frame_index=detection.frame_index,
                    source_view=detection.source_view,
                    bbox_xyxy=(1, 1, 3, 3),
                    mask=mask,
                    score=0.75,
                    origin="sam2",
                    prompt_detection_ids=(detection.detection_id,),
                    model_name="slow-sam2",
                    segmentation_id="slow-sam2-seg",
                )

        slow_segmenter = SlowSam2Segmenter()
        dialog_calls = []
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_segmenter=slow_segmenter,
            sam2_settings_dialog_factory=self.sam2_dialog_factory(
                threshold=0.65,
                calls=dialog_calls,
            ),
        )
        frames = np.arange(16, dtype=np.float32).reshape(1, 4, 4)
        detections = MolecularDetectionSet(frame_count=1)
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(1, 1, 3, 3),
            confidence=0.9,
            source_view="raw",
            detection_id="bbox-1",
        )
        detections.set_detections(0, [detection], source_view="raw", frame_shape=(4, 4))
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.sp_sam2_mask_threshold.setValue(0.65)
        self.window.select_molecular_detection_at_pixel(2.0, 2.0)
        self.__class__._app.processEvents()

        start = time.monotonic()
        self.window.btn_sam2_segment_selected.click()
        elapsed_s = time.monotonic() - start

        self.assertLess(elapsed_s, 0.15)
        self.assertFalse(self.window.btn_sam2_segment_selected.isEnabled())
        self.assertFalse(self.window.btn_sam2_segment_all_current.isEnabled())
        self.assertIsNotNone(self.window._sam2_segmentation_progress_dialog)
        self.assertIn("Running SAM2", self.window.lbl_segmentation_status.text())

        self.process_events_until(
            lambda: (
                series.molecular_segmentations is not None
                and series.molecular_segmentations.get_segmentation("slow-sam2-seg") is not None
            ),
            timeout_s=3.0,
        )

        self.assertEqual(len(dialog_calls), 1)
        self.assertEqual(dialog_calls[0]["bbox_count"], 1)
        self.assertEqual(len(slow_segmenter.calls), 1)
        self.assertAlmostEqual(slow_segmenter.calls[0][2], 0.65)
        self.assertAlmostEqual(self.window.sp_sam2_mask_threshold.value(), 0.65)
        self.assertIsNone(self.window._sam2_segmentation_progress_dialog)
        self.assertTrue(self.window.btn_sam2_segment_selected.isEnabled())
        self.assertTrue(self.window.btn_sam2_segment_all_current.isEnabled())
        self.assertEqual(self.window.viewer.visible_molecular_segmentation_ids(), ["slow-sam2-seg"])
        self.assertIn("SAM2 segmented selected BBox", self.window.statusBar().currentMessage())

    def test_sam2_segmentation_error_reports_failure_without_losing_selected_bbox(self) -> None:
        class FailingSam2Segmenter:
            def __init__(self) -> None:
                self.calls = []

            def segment_detection(self, frame, detection, *, mask_probability_threshold=0.5, checkpoint_path=None, **_kwargs):
                self.calls.append((frame.copy(), detection, mask_probability_threshold))
                raise RuntimeError("SAM2 checkpoint missing")

        failing_segmenter = FailingSam2Segmenter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_segmenter=failing_segmenter,
            sam2_settings_dialog_factory=self.sam2_dialog_factory(threshold=0.5),
        )
        frames = np.arange(16, dtype=np.float32).reshape(1, 4, 4)
        detections = MolecularDetectionSet(frame_count=1)
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(1, 1, 3, 3),
            confidence=0.9,
            source_view="raw",
            detection_id="bbox-1",
        )
        detections.set_detections(0, [detection], source_view="raw", frame_shape=(4, 4))
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.select_molecular_detection_at_pixel(2.0, 2.0)
        self.__class__._app.processEvents()

        with patch.object(QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok) as critical:
            self.window.btn_sam2_segment_selected.click()
            self.process_events_until(
                lambda: "SAM2 segmentation failed" in self.window.statusBar().currentMessage(),
                timeout_s=3.0,
            )

        self.assertEqual(len(failing_segmenter.calls), 1)
        critical.assert_called_once()
        _parent, title, message = critical.call_args.args
        self.assertEqual(title, "SAM2 segmentation error")
        self.assertIn("SAM2 checkpoint missing", message)
        self.assertIsNone(series.molecular_segmentations)
        self.assertEqual(series.molecular_detections.get_detection("bbox-1"), detection)
        self.assertEqual(self.window.selected_molecular_detection_id(), "bbox-1")
        self.assertTrue(self.window.btn_sam2_segment_selected.isEnabled())
        self.assertTrue(self.window.btn_sam2_segment_all_current.isEnabled())
        self.assertIsNone(self.window._sam2_segmentation_progress_dialog)

    def test_sam2_batch_failure_keeps_existing_masks_and_all_bboxes(self) -> None:
        class FailingBatchSam2Segmenter:
            def __init__(self) -> None:
                self.batch_calls = []

            def segment_frame_detections(self, frame, detections, **kwargs):
                self.batch_calls.append((np.asarray(frame).copy(), list(detections), dict(kwargs)))
                raise RuntimeError("SAM2 batch worker failed")

            def segment_detection(self, *_args, **_kwargs):
                raise AssertionError("Batch failure test must not use legacy SAM2")

        segmenter = FailingBatchSam2Segmenter()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            sam2_checkpoint_discovery=lambda: [Path(r"C:\models\sam2.pt")],
            sam2_segmenter=segmenter,
            sam2_settings_dialog_factory=self.sam2_dialog_factory(existing_policy="replace"),
        )
        frames = np.zeros((1, 5, 5), dtype=np.float32)
        detections = MolecularDetectionSet(frame_count=1)
        frame_detections = [
            MolecularDetection(
                frame_index=0,
                bbox_xyxy=(0, 0, 2, 2),
                confidence=0.9,
                detection_id="bbox-existing",
            ),
            MolecularDetection(
                frame_index=0,
                bbox_xyxy=(2, 2, 5, 5),
                confidence=0.8,
                detection_id="bbox-new",
            ),
        ]
        detections.set_detections(
            0,
            frame_detections,
            source_view="raw",
            frame_shape=(5, 5),
        )
        old_mask = np.zeros((5, 5), dtype=bool)
        old_mask[0:2, 0:2] = True
        old_segmentation = MolecularSegmentation(
            frame_index=0,
            source_view="raw",
            bbox_xyxy=(0, 0, 2, 2),
            mask=old_mask,
            origin="sam2",
            prompt_detection_ids=("bbox-existing",),
            segmentation_id="existing-before-failure",
        )
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(old_segmentation)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_detections=detections,
            molecular_segmentations=segmentations,
        )
        self.window.set_image_series(series)

        with patch.object(
            QMessageBox,
            "critical",
            return_value=QMessageBox.StandardButton.Ok,
        ) as critical:
            self.window.btn_sam2_segment_all_current.click()
            self.process_events_until(
                lambda: "SAM2 segmentation failed" in self.window.statusBar().currentMessage(),
            )

        self.assertEqual(len(segmenter.batch_calls), 1)
        critical.assert_called_once()
        self.assertEqual(series.molecular_segmentations.segmentation_count, 1)
        self.assertIs(
            series.molecular_segmentations.get_segmentation("existing-before-failure"),
            old_segmentation,
        )
        self.assertEqual(
            [item.detection_id for item in series.molecular_detections.get_detections(0)],
            ["bbox-existing", "bbox-new"],
        )

    def test_canceling_open_dialog_keeps_loaded_series_unchanged(self) -> None:
        calls = []

        def fake_loader(source_path, *, reverse_frame_order=False):
            calls.append((source_path, reverse_frame_order))
            raise AssertionError("loader must not run when the dialog is canceled")

        self.window = MolTrackMainWindow(series_loader=fake_loader)
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="loaded.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2, image_type="Topo"),
        )
        self.window.set_image_series(series)

        with (
            patch.object(QFileDialog, "getOpenFileName", return_value=("", "")),
            patch.object(QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok) as critical,
        ):
            self.window.action_open_stm.trigger()
            self.__class__._app.processEvents()

        self.assertEqual(calls, [])
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 1 / 3")
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, frames[0])
        self.assertIn("Active frame: 1 / 3", self.window.metadata_panel.metadata_text())
        critical.assert_not_called()

    def test_open_dialog_loader_error_reports_problem_and_preserves_loaded_series(self) -> None:
        calls = []

        def fake_loader(source_path, *, reverse_frame_order=False):
            calls.append((source_path, reverse_frame_order))
            raise ValueError(f"Only .mpp STM movies are supported: {source_path}")

        self.window = MolTrackMainWindow(series_loader=fake_loader)
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="current.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2, image_type="Topo"),
        )
        self.window.set_image_series(series)
        self.window.slider_frame.setValue(2)
        self.__class__._app.processEvents()

        with (
            patch.object(QFileDialog, "getOpenFileName", return_value=("bad.txt", "")),
            patch.object(QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok) as critical,
        ):
            self.window.action_open_stm.trigger()
            self.__class__._app.processEvents()

        self.assertEqual(calls, [("bad.txt", False)])
        self.assertEqual(series.active_frame_index, 2)
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 3 / 3")
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, frames[2])
        metadata_text = self.window.metadata_panel.metadata_text()
        self.assertIn("Source: current.mpp", metadata_text)
        self.assertIn("Active frame: 3 / 3", metadata_text)
        critical.assert_called_once()
        _parent, title, message = critical.call_args.args
        self.assertEqual(title, "Open STM failed")
        self.assertIn("bad.txt", message)
        self.assertIn("Open STM failed", self.window.statusBar().currentMessage())

    def test_save_state_as_uses_dialog_and_remembers_session_path(self) -> None:
        saved = []

        def fake_saver(path, series, ui_state):
            saved.append((path, series, dict(ui_state)))
            return SimpleNamespace(source_path=series.source_path)

        self.window = MolTrackMainWindow(session_saver=fake_saver)
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)

        self.assertTrue(self.window.action_save_state.isEnabled())
        self.assertTrue(self.window.action_save_state_as.isEnabled())

        with patch.object(QFileDialog, "getSaveFileName", return_value=("state.moltrack.json", "")) as dialog:
            self.window.action_save_state_as.trigger()
            self.__class__._app.processEvents()
            self.process_events_until(lambda: not self.window._state_io_running)

        dialog.assert_called_once()
        expected_saved_state = [
            (
                "state.moltrack.json",
                series,
                {
                    "registration_view_mode": "Show raw",
                    "bbox_overlay_visible": True,
                    "bbox_opacity_percent": 100,
                    "mask_opacity_percent": 30,
                },
            )
        ]
        self.assertEqual(saved, expected_saved_state)
        self.assertIn("Saved state state.moltrack.json", self.window.statusBar().currentMessage())

        saved.clear()
        with patch.object(QFileDialog, "getSaveFileName", return_value=("other.moltrack.json", "")) as dialog:
            self.window.action_save_state.trigger()
            self.__class__._app.processEvents()
            self.process_events_until(lambda: not self.window._state_io_running)

        dialog.assert_not_called()
        self.assertEqual(saved, expected_saved_state)

    def test_save_state_from_menu_runs_in_worker_and_shows_progress(self) -> None:
        saver_started = threading.Event()
        release_saver = threading.Event()

        def blocking_saver(path, series, ui_state):
            saver_started.set()
            release_saver.wait(timeout=1.0)

        self.window = MolTrackMainWindow(session_saver=blocking_saver)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 2, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)
        self.window._session_path = "state.moltrack.json"

        started_at = time.monotonic()
        self.window.action_save_state.trigger()
        elapsed = time.monotonic() - started_at

        try:
            self.assertLess(elapsed, 0.2)
            self.process_events_until(saver_started.is_set)
            self.assertTrue(self.window._state_io_running)
            self.assertIsNotNone(self.window._state_io_progress_dialog)
            self.assertIn(
                "Saving state",
                self.window._state_io_progress_dialog.labelText(),
            )
            self.assertFalse(self.window.action_open_state.isEnabled())
        finally:
            release_saver.set()

        self.process_events_until(lambda: not self.window._state_io_running)
        self.assertIsNone(self.window._state_io_progress_dialog)
        self.assertTrue(self.window.action_open_state.isEnabled())
        self.assertIn("Saved state state.moltrack.json", self.window.statusBar().currentMessage())

    def test_save_state_dialog_reports_segmentation_encoding_progress(self) -> None:
        saver_started = threading.Event()
        release_saver = threading.Event()
        received_callbacks = []

        def progress_saver(path, series, ui_state, *, progress_callback=None):
            received_callbacks.append(progress_callback)
            if progress_callback is not None:
                progress_callback(
                    MolTrackStateSaveProgress(
                        phase="segmentations",
                        completed_count=25,
                        total_count=100,
                    )
                )
            saver_started.set()
            release_saver.wait(timeout=1.0)

        self.window = MolTrackMainWindow(session_saver=progress_saver)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 2, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)
        self.window._session_path = "state.moltrack.json"

        self.window.action_save_state.trigger()
        try:
            self.process_events_until(saver_started.is_set)
            self.assertIsNotNone(received_callbacks[0])
            self.process_events_until(
                lambda: self.window._state_io_progress_dialog is not None
                and self.window._state_io_progress_dialog.maximum() == 100
            )
            progress_dialog = self.window._state_io_progress_dialog
            self.assertEqual(progress_dialog.maximum(), 100)
            self.assertEqual(progress_dialog.value(), 25)
            self.assertIn("25/100", progress_dialog.labelText())
        finally:
            release_saver.set()

        self.process_events_until(lambda: not self.window._state_io_running)

    def test_open_state_uses_dialog_and_restores_working_series(self) -> None:
        loaded_session = SimpleNamespace(registration_view_mode="Show raw")
        load_calls = []
        restore_calls = []
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)

        def fake_session_loader(path):
            load_calls.append(path)
            return loaded_session

        def fake_session_restorer(session):
            restore_calls.append(session)
            return MolTrackImageSeries(
                source_path="movie.mpp",
                raw_frames=frames,
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
                active_frame_index=1,
            )

        self.window = MolTrackMainWindow(
            session_loader=fake_session_loader,
            session_restorer=fake_session_restorer,
        )

        with patch.object(QFileDialog, "getOpenFileName", return_value=("state.moltrack.json", "")) as dialog:
            self.window.action_open_state.trigger()
            self.__class__._app.processEvents()
            self.process_events_until(lambda: not self.window._state_io_running)

        dialog.assert_called_once()
        self.assertEqual(load_calls, ["state.moltrack.json"])
        self.assertEqual(restore_calls, [loaded_session])
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 2 / 3")
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, frames[1])
        self.assertIn("Source: movie.mpp", self.window.metadata_panel.metadata_text())
        self.assertIn("Loaded state state.moltrack.json", self.window.statusBar().currentMessage())
        self.assertTrue(self.window.action_save_state.isEnabled())

    def test_open_state_from_menu_runs_in_worker_and_preserves_series_until_finished(self) -> None:
        loader_started = threading.Event()
        release_loader = threading.Event()
        loaded_session = SimpleNamespace(registration_view_mode="Show raw")
        old_series = MolTrackImageSeries(
            source_path="old.mpp",
            raw_frames=np.zeros((1, 2, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        new_series = MolTrackImageSeries(
            source_path="new.mpp",
            raw_frames=np.ones((1, 2, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )

        def blocking_loader(path):
            loader_started.set()
            release_loader.wait(timeout=1.0)
            return loaded_session

        self.window = MolTrackMainWindow(
            session_loader=blocking_loader,
            session_restorer=lambda session: new_series,
        )
        self.window.set_image_series(old_series)

        with patch.object(
            QFileDialog,
            "getOpenFileName",
            return_value=("state.moltrack.json", ""),
        ):
            started_at = time.monotonic()
            self.window.action_open_state.trigger()
            elapsed = time.monotonic() - started_at

        try:
            self.assertLess(elapsed, 0.2)
            self.process_events_until(loader_started.is_set)
            self.assertIs(self.window._series, old_series)
            self.assertTrue(self.window._state_io_running)
            self.assertIsNotNone(self.window._state_io_progress_dialog)
            self.assertIn(
                "Opening state",
                self.window._state_io_progress_dialog.labelText(),
            )
        finally:
            release_loader.set()

        self.process_events_until(lambda: not self.window._state_io_running)
        self.assertIs(self.window._series, new_series)
        self.assertIsNone(self.window._state_io_progress_dialog)
        self.assertIn("Loaded state state.moltrack.json", self.window.statusBar().currentMessage())

    def test_save_then_open_state_round_trip_restores_working_series_and_expanded_view(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_path = tmp_path / "movie.mpp"
            source_path.write_bytes(b"fake mpp bytes")
            session_path = tmp_path / "state.moltrack.json"
            full_frames = np.arange(40, dtype=np.float32).reshape(5, 2, 4)
            working_series = MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=full_frames.copy(),
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
                active_frame_index=2,
            )
            working_series.remove_frame(1)
            working_series.remove_frame(2)
            working_series.set_active_frame(1)
            settings = MolTrackRegistrationSettings(backend="phase_correlation")
            working_series.registration_results = MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    frame_index: MolTrackRegistrationFrameResult(
                        frame_index=frame_index,
                        shift_xy=(float(frame_index), -float(frame_index)),
                        method="phase_correlation",
                        quality_score=0.8,
                    )
                    for frame_index in range(working_series.frame_count)
                },
            )
            detections = MolecularDetectionSet(frame_count=working_series.frame_count)
            detections.set_detections(
                1,
                [
                    MolecularDetection(
                        frame_index=1,
                        bbox_xyxy=(1, 0, 4, 2),
                        original_bbox_xyxy=(0, 0, 3, 2),
                        confidence=0.86,
                        model_name="missing-model.pt",
                        checkpoint_path="nanotrack/yolo_models/missing-model.pt",
                        source_view="expanded_aligned",
                    )
                ],
                source_view="expanded_aligned",
                frame_shape=(3, 5),
            )
            working_series.molecular_detections = detections
            expanded_frames = np.arange(working_series.frame_count * 3 * 5, dtype=np.float32).reshape(
                working_series.frame_count,
                3,
                5,
            )
            loader_calls = []
            expanded_builder_calls = []

            def fake_series_loader(source_path_arg, *, reverse_frame_order=False):
                loader_calls.append((str(source_path_arg), reverse_frame_order))
                return MolTrackImageSeries(
                    source_path=str(source_path_arg),
                    raw_frames=full_frames.copy(),
                    metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
                    reverse_frame_order=reverse_frame_order,
                )

            def fake_expanded_builder(series):
                expanded_builder_calls.append(series.frame_count)
                expanded_stack = SimpleNamespace(
                    frames=expanded_frames,
                    metadata=STMSequenceMetadata(pixels_x=5, pixels_y=3),
                    padding_ltrb=(0, 1, 1, 0),
                    frame_origins_xy=np.zeros((series.frame_count, 2), dtype=np.float64),
                )
                series.expanded_aligned_stack = expanded_stack
                return expanded_stack

            self.window = MolTrackMainWindow(
                series_loader=fake_series_loader,
                expanded_aligned_builder=fake_expanded_builder,
                yolo_model_discovery=lambda: [],
            )
            self.window.set_image_series(working_series)
            self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
            self.__class__._app.processEvents()
            expanded_builder_calls.clear()

            with patch.object(QFileDialog, "getSaveFileName", return_value=(str(session_path), "")):
                self.window.action_save_state_as.trigger()
                self.__class__._app.processEvents()
                self.process_events_until(lambda: not self.window._state_io_running)

            self.window.close()
            self.window.deleteLater()
            self.__class__._app.processEvents()
            self.window = MolTrackMainWindow(
                series_loader=fake_series_loader,
                expanded_aligned_builder=fake_expanded_builder,
                yolo_model_discovery=lambda: [],
            )

            with patch.object(QFileDialog, "getOpenFileName", return_value=(str(session_path), "")):
                self.window.action_open_state.trigger()
                self.__class__._app.processEvents()
                self.process_events_until(lambda: not self.window._state_io_running)

            self.assertEqual(loader_calls, [(str(source_path.resolve()), False)])
            self.assertEqual(expanded_builder_calls, [3])
            self.assertEqual(self.window.lbl_frame.text(), "Frame: 2 / 3")
            self.assertEqual(self.window.slider_frame.maximum(), 2)
            self.assertEqual(self.window.cmb_registration_view_mode.currentText(), "Show expanded aligned")
            np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, expanded_frames[1])
            self.assertIn("Expanded aligned", self.window.viewer.lbl_title.text())
            self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
            self.assertIsNotNone(self.window._series.molecular_detections)
            restored_detections = self.window._series.molecular_detections.get_detections(
                1,
                source_view="expanded_aligned",
            )
            self.assertEqual(restored_detections[0].bbox_xyxy, (1.0, 0.0, 4.0, 2.0))
            self.assertEqual(restored_detections[0].original_bbox_xyxy, (0.0, 0.0, 3.0, 2.0))
            self.assertIn(f"Loaded state {session_path}", self.window.statusBar().currentMessage())

            self.window.btn_bbox_reset.click()
            self.__class__._app.processEvents()

            self.assertEqual(restored_detections[0].bbox_xyxy, (0.0, 0.0, 3.0, 2.0))
            self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
            self.assertIn("Reset 1", self.window.statusBar().currentMessage())
            self.assertIn("No YOLO models found", self.window.lbl_yolo_models.text())
            self.assertIn("current 1", self.window.lbl_yolo_status.text())
            self.assertIn("series 1", self.window.lbl_yolo_status.text())
            metadata_text = self.window.metadata_panel.metadata_text()
            self.assertIn("Frames: 3", metadata_text)
            self.assertIn("Active frame: 2 / 3", metadata_text)
            self.assertIn("Expanded shape: 5x3 px", metadata_text)

    def test_save_then_open_state_restores_sam2_segmentation_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_path = tmp_path / "movie.mpp"
            source_path.write_bytes(b"fake mpp bytes")
            session_path = tmp_path / "state.moltrack.json"
            frames = np.arange(2 * 4 * 5, dtype=np.float32).reshape(2, 4, 5)

            def fake_series_loader(source_path_arg, *, reverse_frame_order=False):
                return MolTrackImageSeries(
                    source_path=str(source_path_arg),
                    raw_frames=frames.copy(),
                    metadata=STMSequenceMetadata(pixels_x=5, pixels_y=4),
                    reverse_frame_order=reverse_frame_order,
                )

            detections = MolecularDetectionSet(frame_count=2)
            detection = MolecularDetection(
                frame_index=0,
                bbox_xyxy=(1, 1, 4, 3),
                confidence=0.93,
                source_view="raw",
                detection_id="bbox-1",
            )
            detections.set_detections(0, [detection], source_view="raw", frame_shape=(4, 5))
            mask = np.array(
                [
                    [False, False, False, False, False],
                    [False, True, True, True, False],
                    [False, False, True, True, False],
                    [False, False, False, False, False],
                ],
                dtype=bool,
            )
            segmentations = MolecularSegmentationSet(frame_count=2)
            segmentations.add_segmentation(
                MolecularSegmentation(
                    frame_index=0,
                    source_view="raw",
                    bbox_xyxy=(1, 1, 4, 3),
                    mask=mask,
                    score=0.88,
                    origin="sam2",
                    prompt_detection_ids=("bbox-1",),
                    model_name="missing-sam2.pt",
                    metadata={"checkpoint": "missing/sam2.pt"},
                    segmentation_id="sam2-seg-1",
                )
            )
            working_series = MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=frames.copy(),
                metadata=STMSequenceMetadata(pixels_x=5, pixels_y=4),
                molecular_detections=detections,
                molecular_segmentations=segmentations,
            )

            self.window = MolTrackMainWindow(
                series_loader=fake_series_loader,
                yolo_model_discovery=lambda: [],
            )
            self.window.set_image_series(working_series)
            self.assertEqual(self.window.viewer.visible_molecular_segmentation_ids(), ["sam2-seg-1"])

            with patch.object(QFileDialog, "getSaveFileName", return_value=(str(session_path), "")):
                self.window.action_save_state_as.trigger()
                self.__class__._app.processEvents()
                self.process_events_until(lambda: not self.window._state_io_running)

            self.window.close()
            self.window.deleteLater()
            self.__class__._app.processEvents()
            self.window = MolTrackMainWindow(
                series_loader=fake_series_loader,
                yolo_model_discovery=lambda: [],
            )

            with patch.object(QFileDialog, "getOpenFileName", return_value=(str(session_path), "")):
                self.window.action_open_state.trigger()
                self.__class__._app.processEvents()
                self.process_events_until(lambda: not self.window._state_io_running)

            self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
            self.assertEqual(self.window.viewer.visible_molecular_segmentation_count(), 1)
            self.assertEqual(self.window.viewer.visible_molecular_segmentation_ids(), ["sam2-seg-1"])
            restored_detection = self.window._series.molecular_detections.get_detection("bbox-1")
            self.assertIsNotNone(restored_detection)
            restored_segmentation = self.window._series.molecular_segmentations.get_segmentation("sam2-seg-1")
            self.assertIsNotNone(restored_segmentation)
            self.assertEqual(restored_segmentation.prompt_detection_ids, ("bbox-1",))
            self.assertEqual(restored_segmentation.model_name, "missing-sam2.pt")
            np.testing.assert_array_equal(restored_segmentation.mask, mask)
            self.assertIn(f"Loaded state {session_path}", self.window.statusBar().currentMessage())

    def test_save_then_open_state_restores_manual_bbox_for_reset_and_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_path = tmp_path / "movie.mpp"
            source_path.write_bytes(b"fake mpp bytes")
            session_path = tmp_path / "state.moltrack.json"
            frames = np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4)

            def fake_series_loader(source_path_arg, *, reverse_frame_order=False):
                return MolTrackImageSeries(
                    source_path=str(source_path_arg),
                    raw_frames=frames.copy(),
                    metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
                    reverse_frame_order=reverse_frame_order,
                )

            self.window = MolTrackMainWindow(
                series_loader=fake_series_loader,
                yolo_model_discovery=lambda: [],
            )
            self.window.set_image_series(
                MolTrackImageSeries(
                    source_path=str(source_path),
                    raw_frames=frames.copy(),
                    metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
                )
            )
            manual_detection = self.window.add_manual_bbox_from_pixel_drag((1.0, 1.0), (3.0, 3.0))
            self.assertIsNotNone(manual_detection)
            manual_detection_id = manual_detection.detection_id
            self.window.sp_bbox_resize_margin.setValue(1.0)
            self.window.btn_bbox_increase.click()
            self.__class__._app.processEvents()

            with patch.object(QFileDialog, "getSaveFileName", return_value=(str(session_path), "")):
                self.window.action_save_state_as.trigger()
                self.__class__._app.processEvents()
                self.process_events_until(lambda: not self.window._state_io_running)

            self.window.close()
            self.window.deleteLater()
            self.__class__._app.processEvents()
            self.window = MolTrackMainWindow(
                series_loader=fake_series_loader,
                yolo_model_discovery=lambda: [],
            )

            with patch.object(QFileDialog, "getOpenFileName", return_value=(str(session_path), "")):
                self.window.action_open_state.trigger()
                self.__class__._app.processEvents()
                self.process_events_until(lambda: not self.window._state_io_running)

            self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
            self.assertIsNotNone(self.window._series.molecular_detections)
            restored_detection = self.window._series.molecular_detections.get_detection(manual_detection_id)
            self.assertIsNotNone(restored_detection)
            self.assertEqual(restored_detection.origin, "manual")
            self.assertEqual(restored_detection.model_name, "manual")
            self.assertEqual(restored_detection.checkpoint_path, "")
            self.assertEqual(restored_detection.original_bbox_xyxy, (1.0, 1.0, 3.0, 3.0))
            self.assertEqual(restored_detection.bbox_xyxy, (0.0, 0.0, 4.0, 4.0))

            self.window.btn_bbox_reset.click()
            self.__class__._app.processEvents()

            self.assertEqual(restored_detection.bbox_xyxy, (1.0, 1.0, 3.0, 3.0))
            self.assertEqual(self.window.select_molecular_detection_at_pixel(2.0, 2.0), manual_detection_id)
            self.assertTrue(self.window.btn_bbox_delete_selected.isEnabled())

            self.window.btn_bbox_delete_selected.click()
            self.__class__._app.processEvents()

            self.assertIsNone(self.window._series.molecular_detections.get_detection(manual_detection_id))
            self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 0)
            self.assertIsNone(self.window.selected_molecular_detection_id())
            self.assertIn("current 0", self.window.lbl_yolo_status.text())
            self.assertIn("series 0", self.window.lbl_yolo_status.text())

    def test_open_state_reports_missing_source_and_preserves_loaded_series(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_path = tmp_path / "movie.mpp"
            source_path.write_bytes(b"fake mpp bytes")
            session_path = tmp_path / "state.moltrack.json"
            saved_series = MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=np.arange(16, dtype=np.float32).reshape(2, 2, 4),
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
            )
            save_moltrack_session(session_path, saved_series, None)
            source_path.unlink()

            self.window = MolTrackMainWindow()
            current_frames = np.full((2, 2, 4), 7.0, dtype=np.float32)
            current_series = MolTrackImageSeries(
                source_path="current.mpp",
                raw_frames=current_frames,
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
                active_frame_index=1,
            )
            self.window.set_image_series(current_series)

            with (
                patch.object(QFileDialog, "getOpenFileName", return_value=(str(session_path), "")),
                patch.object(QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok) as critical,
            ):
                self.window.action_open_state.trigger()
                self.__class__._app.processEvents()
                self.process_events_until(lambda: not self.window._state_io_running)

            self.assertEqual(self.window.lbl_frame.text(), "Frame: 2 / 2")
            np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, current_frames[1])
            self.assertIn("Source: current.mpp", self.window.metadata_panel.metadata_text())
            critical.assert_called_once()
            _parent, title, message = critical.call_args.args
            self.assertEqual(title, "Open State failed")
            self.assertIn("does not exist", message)
            self.assertIn("Open State failed", self.window.statusBar().currentMessage())

    def test_setting_series_enables_frame_navigation_and_slider_selects_frame(self) -> None:
        self.window = MolTrackMainWindow()
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )

        self.window.set_image_series(series)

        self.assertTrue(self.window.slider_frame.isEnabled())
        self.assertEqual(self.window.slider_frame.minimum(), 0)
        self.assertEqual(self.window.slider_frame.maximum(), 2)
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 1 / 3")

        self.window.slider_frame.setValue(2)
        self.__class__._app.processEvents()

        self.assertEqual(series.active_frame_index, 2)
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 3 / 3")
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, frames[2])

    def test_viewer_shows_molecular_detections_for_active_raw_frame(self) -> None:
        self.window = MolTrackMainWindow()
        frames = np.arange(48, dtype=np.float32).reshape(3, 4, 4)
        detections = MolecularDetectionSet(frame_count=3)
        detections.set_detections(
            0,
            [
                MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9, selected=True),
                MolecularDetection(frame_index=0, bbox_xyxy=(2, 1, 4, 3), confidence=0.6, selected=False),
            ],
            source_view="raw",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            2,
            [MolecularDetection(frame_index=2, bbox_xyxy=(1, 1, 3, 3), confidence=0.7)],
            source_view="raw",
            frame_shape=(4, 4),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )

        self.window.set_image_series(series)

        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 2)
        self.assertEqual(
            self.window.viewer.visible_molecular_detection_colors(),
            [(255, 0, 255), (255, 140, 0)],
        )

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 0)

        self.window.slider_frame.setValue(2)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)

    def test_bbox_opacity_slider_controls_detection_overlay_without_changing_detections(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.arange(32, dtype=np.float32).reshape(2, 4, 4)
        detections = MolecularDetectionSet(frame_count=2)
        first_detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(0, 0, 2, 2),
            confidence=0.9,
            source_view="raw",
        )
        second_detection = MolecularDetection(
            frame_index=1,
            bbox_xyxy=(1, 1, 3, 3),
            confidence=0.8,
            source_view="raw",
        )
        detections.set_detections(0, [first_detection], source_view="raw", frame_shape=(4, 4))
        detections.set_detections(1, [second_detection], source_view="raw", frame_shape=(4, 4))
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )
        original_bboxes = (first_detection.bbox_xyxy, second_detection.bbox_xyxy)

        self.window.set_image_series(series)

        self.assertEqual(self.window.slider_bbox_opacity.minimum(), 0)
        self.assertEqual(self.window.slider_bbox_opacity.maximum(), 100)
        self.assertEqual(self.window.slider_bbox_opacity.value(), 100)
        self.assertEqual(self.window.viewer.visible_molecular_detection_opacities(), [1.0])

        self.window.slider_bbox_opacity.setValue(25)
        self.__class__._app.processEvents()
        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.lbl_bbox_opacity.text(), "BBox opacity: 25%")
        self.assertEqual(self.window.viewer.visible_molecular_detection_opacities(), [0.25])
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertEqual((first_detection.bbox_xyxy, second_detection.bbox_xyxy), original_bboxes)

    def test_show_bboxes_toggle_skips_bbox_rendering_without_changing_detections(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.arange(32, dtype=np.float32).reshape(2, 4, 4)
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(0, 0, 2, 2),
                    confidence=0.9,
                    source_view="raw",
                )
            ],
            source_view="raw",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            1,
            [
                MolecularDetection(
                    frame_index=1,
                    bbox_xyxy=(1, 1, 3, 3),
                    confidence=0.8,
                    source_view="raw",
                )
            ],
            source_view="raw",
            frame_shape=(4, 4),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )

        self.window.set_image_series(series)

        self.assertTrue(self.window.chk_show_bboxes.isChecked())
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)

        self.window.chk_show_bboxes.setChecked(False)
        self.__class__._app.processEvents()

        self.assertFalse(self.window.slider_bbox_opacity.isEnabled())
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 0)
        self.assertEqual(detections.detection_count, 2)

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 0)
        self.assertEqual(detections.detection_count, 2)

        self.window.chk_show_bboxes.setChecked(True)
        self.__class__._app.processEvents()

        self.assertTrue(self.window.slider_bbox_opacity.isEnabled())
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)

    def test_mask_opacity_slider_controls_sam2_and_sam3_overlays_without_changing_masks(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        mask = np.zeros((4, 4), dtype=bool)
        mask[1:3, 1:3] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                mask=mask,
                origin="sam2",
                segmentation_id="sam2-mask",
            )
        )
        preview = build_moltrack_sam3_preview(
            [
                MolTrackSam3Proposal(
                    frame_index=0,
                    source_view="raw",
                    bbox_xyxy=(1, 1, 3, 3),
                    score=0.9,
                    mask=mask,
                )
            ],
            frame_index=0,
            source_view="raw",
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 4, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_segmentations=segmentations,
            sam3_preview=preview,
        )
        original_mask = segmentations.get_segmentation("sam2-mask").mask.copy()

        self.window.set_image_series(series)

        self.assertEqual(self.window.slider_mask_opacity.minimum(), 0)
        self.assertEqual(self.window.slider_mask_opacity.maximum(), 100)
        self.assertEqual(self.window.slider_mask_opacity.value(), 30)
        self.assertEqual(self.window.viewer.visible_molecular_segmentation_opacities(), [0.3])
        self.assertEqual(self.window.viewer.visible_sam3_preview_opacities(), [0.3])

        self.window.slider_mask_opacity.setValue(12)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.lbl_mask_opacity.text(), "Mask opacity: 12%")
        self.assertEqual(self.window.viewer.visible_molecular_segmentation_opacities(), [0.12])
        self.assertEqual(self.window.viewer.visible_sam3_preview_opacities(), [0.12])
        np.testing.assert_array_equal(segmentations.get_segmentation("sam2-mask").mask, original_mask)

    def test_show_centroids_toggle_adds_positions_without_hiding_bbox_and_mask_overlays(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(0, 0, 3, 3),
                    confidence=0.9,
                    detection_id="bbox-with-mask",
                ),
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(3, 3, 5, 5),
                    confidence=0.8,
                    detection_id="bbox-fallback",
                ),
            ],
            source_view="raw",
            frame_shape=(5, 5),
        )
        mask = np.zeros((5, 5), dtype=bool)
        mask[1:3, 1:3] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                mask=mask,
                prompt_detection_ids=("bbox-with-mask",),
                segmentation_id="seg-1",
                origin="sam2",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 5, 5), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_detections=detections,
            molecular_segmentations=segmentations,
        )

        self.window.set_image_series(series)

        self.assertEqual(self.window.chk_show_centroids.text(), "Show centroids")
        self.assertFalse(self.window.chk_show_centroids.isChecked())
        self.assertEqual(self.window.viewer.visible_molecular_centroid_count(), 0)
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 2)
        self.assertEqual(self.window.viewer.visible_molecular_segmentation_count(), 1)

        self.window.chk_show_centroids.setChecked(True)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.viewer.visible_molecular_centroid_count(), 2)
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 2)
        self.assertEqual(self.window.viewer.visible_molecular_segmentation_count(), 1)

    def test_centroid_overlay_refreshes_per_frame_and_is_independent_of_bbox_opacity(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9)],
            source_view="raw",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            1,
            [
                MolecularDetection(frame_index=1, bbox_xyxy=(0, 0, 2, 2), confidence=0.8),
                MolecularDetection(frame_index=1, bbox_xyxy=(2, 2, 4, 4), confidence=0.7),
            ],
            source_view="raw",
            frame_shape=(4, 4),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 4, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.chk_show_centroids.setChecked(True)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.viewer.visible_molecular_centroid_count(), 1)

        self.window.slider_bbox_opacity.setValue(0)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.viewer.visible_molecular_detection_opacities(), [0.0])
        self.assertEqual(self.window.viewer.visible_molecular_centroid_count(), 1)

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.viewer.visible_molecular_centroid_count(), 2)
        self.window.chk_show_centroids.setChecked(False)
        self.__class__._app.processEvents()
        self.assertEqual(self.window.viewer.visible_molecular_centroid_count(), 0)
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 2)

    def test_position_analysis_button_opens_scatter_plot_for_current_frame(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(frame_index=0, bbox_xyxy=(1, 1, 3, 3), confidence=0.9),
                MolecularDetection(frame_index=0, bbox_xyxy=(6, 2, 8, 4), confidence=0.8),
            ],
            source_view="raw",
            frame_shape=(5, 10),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 5, 10), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=10,
                pixels_y=5,
                size_nm_x=20.0,
                size_nm_y=5.0,
            ),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)

        self.assertEqual(self.window.btn_position_analysis.text(), "Position Analysis...")
        self.assertTrue(self.window.btn_position_analysis.isEnabled())

        self.window.btn_position_analysis.click()
        self.__class__._app.processEvents()

        dialog = self.window.position_analysis_dialog()
        self.assertIsNotNone(dialog)
        self.assertTrue(dialog.isVisible())
        self.assertEqual(dialog.windowTitle(), "Position Analysis")
        self.assertEqual(dialog.point_count(), 2)
        self.assertEqual(dialog.displayed_points_xy(), ((4.0, 2.0), (14.0, 3.0)))
        self.assertEqual(dialog.axis_unit(), "nm")
        self.assertEqual(dialog.axis_labels(), ("x [nm]", "y [nm]"))
        self.assertEqual(dialog.axis_ranges(), ((0.0, 20.0), (0.0, 5.0)))
        self.assertIn("Nearest neighbor [nm]:", dialog.metrics_summary_text())
        self.assertEqual(dialog.lbl_status.text(), "Points: 2")

    def test_position_analysis_colors_points_by_intensity_with_shared_colorbar(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frame = np.ones((8, 12), dtype=np.float32)
        frame[1:3, 1:3] = 6.0
        frame[1:3, 8:10] = 11.0
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1, 1, 3, 3),
                    confidence=0.9,
                    detection_id="low-signal",
                ),
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(8, 1, 10, 3),
                    confidence=0.8,
                    detection_id="high-signal",
                ),
            ],
            source_view="raw",
            frame_shape=frame.shape,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frame[np.newaxis, ...],
            metadata=STMSequenceMetadata(pixels_x=12, pixels_y=8),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)

        self.window.btn_position_analysis.click()
        self.__class__._app.processEvents()

        dialog = self.window.position_analysis_dialog()
        self.assertEqual(dialog.chk_color_by_intensity.text(), "Color points by intensity")
        self.assertTrue(dialog.chk_color_by_intensity.isChecked())
        self.assertTrue(dialog.chk_color_by_intensity.isEnabled())
        self.assertEqual(dialog.cmb_intensity_metric.currentData(), "background_corrected_median")
        self.assertEqual(
            dialog.intensity_metric_options(),
            (
                "Background-corrected median",
                "Mean",
                "Maximum",
                "Integrated",
            ),
        )
        self.assertEqual(dialog.displayed_intensity_values(), (5.0, 10.0))
        self.assertNotEqual(dialog.displayed_point_colors()[0], dialog.displayed_point_colors()[1])
        self.assertEqual(dialog.displayed_point_sizes(), (8.0, 8.0))
        self.assertEqual(dialog.intensity_color_range(), (5.0, 10.0))
        self.assertEqual(
            dialog.intensity_colorbar_label(),
            "Background-corrected median [a.u.]",
        )

    def test_position_analysis_switches_intensity_metric_without_moving_points(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frame = np.ones((8, 12), dtype=np.float32)
        frame[1:3, 1:3] = np.asarray(((4.0, 6.0), (8.0, 10.0)), dtype=np.float32)
        frame[1:3, 8:10] = np.asarray(((12.0, 14.0), (16.0, 18.0)), dtype=np.float32)
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1, 1, 3, 3),
                    confidence=0.9,
                    detection_id="first",
                ),
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(8, 1, 10, 3),
                    confidence=0.8,
                    detection_id="second",
                ),
            ],
            source_view="raw",
            frame_shape=frame.shape,
        )
        self.window.set_image_series(
            MolTrackImageSeries(
                source_path="movie.mpp",
                raw_frames=frame[np.newaxis, ...],
                metadata=STMSequenceMetadata(pixels_x=12, pixels_y=8),
                molecular_detections=detections,
            )
        )
        self.window.btn_position_analysis.click()
        self.__class__._app.processEvents()
        dialog = self.window.position_analysis_dialog()
        original_points = dialog.displayed_points_xy()

        dialog.cmb_intensity_metric.setCurrentText("Maximum")
        self.__class__._app.processEvents()

        self.assertEqual(dialog.cmb_intensity_metric.currentData(), "max")
        self.assertEqual(dialog.displayed_intensity_values(), (10.0, 18.0))
        self.assertEqual(dialog.intensity_color_range(), (10.0, 18.0))
        self.assertEqual(dialog.intensity_colorbar_label(), "Maximum [a.u.]")
        self.assertEqual(dialog.displayed_points_xy(), original_points)
        self.assertEqual(dialog.displayed_point_sizes(), (8.0, 8.0))

    def test_position_analysis_uses_neutral_color_for_missing_intensity_and_descriptive_tooltips(self) -> None:
        self.window = PositionAnalysisDialog()
        centroids = [
            MolecularCentroid(0, "raw", 1.0, 2.0, "bbox_center", "bbox-low"),
            MolecularCentroid(
                0,
                "raw",
                3.0,
                4.0,
                "segmentation",
                "seg-high",
                area_px=3,
            ),
            MolecularCentroid(0, "raw", 5.0, 6.0, "bbox_center", "bbox-missing"),
        ]
        measurements = [
            MolecularIntensityMeasurement(
                frame_index=0,
                source_id="bbox-low",
                source_kind="bbox",
                pixel_count=4,
                sum=8.0,
                mean=2.0,
                median=2.0,
                max=3.0,
            ),
            MolecularIntensityMeasurement(
                frame_index=0,
                source_id="seg-high",
                source_kind="segmentation",
                pixel_count=3,
                sum=24.0,
                mean=8.0,
                median=8.0,
                max=9.0,
            ),
        ]
        plot_data = build_molecular_position_plot_data(
            centroids,
            frame_index=0,
            source_view="raw",
            frame_shape=(8, 8),
            intensity_measurements=measurements,
            intensity_metric="mean",
        )

        self.window.set_plot_data(plot_data)

        self.assertEqual(self.window.intensity_color_range(), (2.0, 8.0))
        self.assertEqual(
            self.window.displayed_point_colors()[2],
            self.window.missing_intensity_color(),
        )
        self.assertIn("x: 1.000 px", self.window.point_tooltip(0))
        self.assertIn("Mean: 2.000 a.u.", self.window.point_tooltip(0))
        self.assertIn("Area: 4 px^2", self.window.point_tooltip(0))
        self.assertIn("Source: bbox", self.window.point_tooltip(0))
        self.assertIn("Source: segmentation", self.window.point_tooltip(1))
        self.assertIn("Intensity: unavailable", self.window.point_tooltip(2))

    def test_position_analysis_can_select_raw_metric_when_local_background_is_unavailable(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frame = np.full((4, 4), 7.0, dtype=np.float32)
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(0, 0, 4, 4),
                    confidence=0.9,
                    detection_id="full-frame",
                )
            ],
            source_view="raw",
            frame_shape=frame.shape,
        )
        self.window.set_image_series(
            MolTrackImageSeries(
                source_path="movie.mpp",
                raw_frames=frame[np.newaxis, ...],
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
                molecular_detections=detections,
            )
        )
        self.window.btn_position_analysis.click()
        self.__class__._app.processEvents()
        dialog = self.window.position_analysis_dialog()

        self.assertEqual(dialog.displayed_intensity_values(), (None,))
        self.assertTrue(dialog.cmb_intensity_metric.isEnabled())
        dialog.cmb_intensity_metric.setCurrentText("Mean")
        self.__class__._app.processEvents()

        self.assertEqual(dialog.displayed_intensity_values(), (7.0,))
        self.assertEqual(dialog.intensity_color_range(), (7.0, 7.0))

    def test_position_analysis_switches_between_segmentation_centroids_and_bbox_centers(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        detections = MolecularDetectionSet(frame_count=2)
        segmentations = MolecularSegmentationSet(frame_count=2)
        for frame_index in range(2):
            detection_id = f"bbox-{frame_index}"
            detections.set_detections(
                frame_index,
                [
                    MolecularDetection(
                        frame_index=frame_index,
                        bbox_xyxy=(0, 0, 4, 4),
                        confidence=0.9,
                        detection_id=detection_id,
                    )
                ],
                source_view="raw",
                frame_shape=(6, 6),
            )
            mask = np.zeros((6, 6), dtype=bool)
            mask[frame_index, frame_index] = True
            segmentations.add_segmentation(
                MolecularSegmentation(
                    frame_index=frame_index,
                    source_view="raw",
                    mask=mask,
                    prompt_detection_ids=(detection_id,),
                    segmentation_id=f"seg-{frame_index}",
                    origin="sam2",
                )
            )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 6, 6), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=6, pixels_y=6),
            molecular_detections=detections,
            molecular_segmentations=segmentations,
        )
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()
        self.__class__._app.processEvents()
        dialog = self.window.position_analysis_dialog()

        self.assertEqual(dialog.chk_use_segmentation_centroids.text(), "Use segmentation centroids")
        self.assertTrue(dialog.chk_use_segmentation_centroids.isChecked())
        self.assertEqual(dialog.displayed_points_xy(), ((0.5, 0.5),))

        dialog.chk_use_segmentation_centroids.setChecked(False)
        self.__class__._app.processEvents()

        self.assertEqual(dialog.displayed_points_xy(), ((2.0, 2.0),))
        dialog.btn_compare_ranges.click()
        self.__class__._app.processEvents()
        self.assertEqual(dialog.range_spatial_data().first.points_xy, ((2.0, 2.0),))
        self.assertEqual(dialog.range_spatial_data().second.points_xy, ((2.0, 2.0),))

        dialog.chk_use_segmentation_centroids.setChecked(True)
        self.__class__._app.processEvents()

        self.assertEqual(dialog.displayed_points_xy(), ((0.5, 0.5),))
        self.assertEqual(dialog.range_spatial_data().first.points_xy, ((0.5, 0.5),))
        self.assertEqual(dialog.range_spatial_data().second.points_xy, ((1.5, 1.5),))

        previous_comparison = dialog.range_comparison()
        dialog.btn_range_mode_single.click()
        with patch(
            "moltrack.ui.main_window.compare_molecular_frame_ranges",
            wraps=compare_molecular_frame_ranges,
        ) as comparison_spy:
            dialog.btn_compare_ranges.click()
            dialog.chk_use_segmentation_centroids.setChecked(False)
            dialog.cmb_intensity_metric.setCurrentText("Maximum")
            dialog.sp_background_outer_radius.setValue(4)
            self.__class__._app.processEvents()

        comparison_spy.assert_not_called()
        self.assertIsNotNone(previous_comparison)
        self.assertIsNone(dialog.range_comparison())

    def test_position_analysis_dialog_shows_empty_current_frame_without_error(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 3, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=3),
        )
        self.window.set_image_series(series)

        self.window.btn_position_analysis.click()
        self.__class__._app.processEvents()

        dialog = self.window.position_analysis_dialog()
        self.assertIsNotNone(dialog)
        self.assertTrue(dialog.isVisible())
        self.assertEqual(dialog.point_count(), 0)
        self.assertEqual(dialog.displayed_points_xy(), ())
        self.assertEqual(dialog.axis_unit(), "px")
        self.assertEqual(dialog.axis_ranges(), ((0.0, 4.0), (0.0, 3.0)))
        self.assertIn("Molecules: 0", dialog.metrics_summary_text())
        self.assertIn("Nearest neighbor [px]: unavailable", dialog.metrics_summary_text())
        self.assertIn("Angular coherence: unavailable", dialog.metrics_summary_text())
        self.assertEqual(dialog.histogram_counts(), (0,) * 18)
        self.assertEqual(dialog.lbl_status.text(), "Points: 0")

    def test_position_analysis_passes_one_public_export_settings_model_to_persistence(self) -> None:
        settings = AnalysisExportSettings(
            scope="current_frame",
            destination=Path("analysis-package"),
            package_format="directory",
            include_tables=True,
            include_spatial_grids=False,
            include_plots=True,
            frame_count=2,
            active_frame_index=0,
            source_view="raw",
            use_segmentation_centroids=True,
            intensity_metric="mean",
            intensity_unit="a.u.",
            background_inner_radius_px=1,
            background_outer_radius_px=3,
            density_grid_shape=(32, 32),
        )
        dialog_calls = []
        export_calls = []

        class FakeExportAnalysisDialog:
            def exec(self):
                return QDialog.DialogCode.Accepted

            def export_settings(self):
                return settings

        def export_dialog_factory(**kwargs):
            dialog_calls.append(dict(kwargs))
            return FakeExportAnalysisDialog()

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            analysis_export_dialog_factory=export_dialog_factory,
            analysis_exporter=lambda series, request: export_calls.append((series, request)),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 4, 5), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=4),
        )
        self.window.set_image_series(series)

        self.window.btn_position_analysis.click()
        position_dialog = self.window.position_analysis_dialog()
        self.assertIsNotNone(position_dialog)
        self.assertEqual(position_dialog.btn_export_analysis.text(), "Export Analysis...")

        with patch.object(QMessageBox, "information"):
            position_dialog.btn_export_analysis.click()
            self.process_events_until(
                lambda: len(export_calls) == 1
                and not self.window.analysis_export_running()
            )

        self.assertEqual(len(dialog_calls), 1)
        self.assertEqual(dialog_calls[0]["frame_count"], 2)
        self.assertEqual(dialog_calls[0]["active_frame_index"], 0)
        self.assertEqual(dialog_calls[0]["source_view"], "raw")
        self.assertIsNone(dialog_calls[0]["selected_ranges"])
        self.assertEqual(export_calls, [(series, settings)])

    def test_position_analysis_export_inherits_active_m6_settings(self) -> None:
        m6_settings = MolecularM6OrientationAnalysisSettings(q_seed=0.7)
        dialog_calls = []

        class CancelledExportAnalysisDialog:
            def exec(self):
                return QDialog.DialogCode.Rejected

        def export_dialog_factory(**kwargs):
            dialog_calls.append(dict(kwargs))
            return CancelledExportAnalysisDialog()

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            analysis_export_dialog_factory=export_dialog_factory,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=8,
                pixels_y=8,
                size_nm_x=8.0,
                size_nm_y=8.0,
            ),
            m6_analysis_state=MolecularM6SessionState(
                enabled=True,
                source_view="raw",
                use_segmentation_centroids=True,
                settings=m6_settings,
            ),
        )
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()

        self.window._on_position_analysis_export_requested()

        self.assertEqual(len(dialog_calls), 1)
        self.assertIs(dialog_calls[0]["m6_orientation_settings"], m6_settings)

    def test_analysis_export_runs_without_blocking_ui_and_blocks_a_second_export(self) -> None:
        exporter_started = threading.Event()
        release_exporter = threading.Event()
        export_calls = []
        settings = AnalysisExportSettings(
            scope="current_frame",
            destination=Path("analysis-package"),
            package_format="directory",
            include_tables=True,
            include_spatial_grids=False,
            include_plots=False,
            frame_count=2,
            active_frame_index=0,
            source_view="raw",
            use_segmentation_centroids=True,
            intensity_metric="mean",
            intensity_unit="a.u.",
            background_inner_radius_px=1,
            background_outer_radius_px=3,
            density_grid_shape=(32, 32),
        )

        class FakeExportAnalysisDialog:
            def exec(self):
                return QDialog.DialogCode.Accepted

            def export_settings(self):
                return settings

        def blocking_exporter(series, request, *, progress_callback=None):
            export_calls.append((series, request, progress_callback))
            exporter_started.set()
            release_exporter.wait(timeout=2.0)
            return SimpleNamespace(
                package_path=request.destination,
                relative_files=("molecules.csv", "frames.csv"),
                record_counts=(("molecules.csv", 3), ("frames.csv", 2)),
            )

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            analysis_export_dialog_factory=lambda **_kwargs: FakeExportAnalysisDialog(),
            analysis_exporter=blocking_exporter,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 4, 5), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=4),
        )
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()
        position_dialog = self.window.position_analysis_dialog()
        release_timer = threading.Timer(0.5, release_exporter.set)
        release_timer.start()

        try:
            with patch.object(QMessageBox, "information") as information:
                started_at = time.monotonic()
                position_dialog.btn_export_analysis.click()
                elapsed = time.monotonic() - started_at

                self.assertLess(elapsed, 0.2)
                self.process_events_until(exporter_started.is_set)
                self.assertTrue(self.window.analysis_export_running())
                progress_dialog = self.window.analysis_export_progress_dialog()
                self.assertIsNotNone(progress_dialog)
                self.assertTrue(progress_dialog.isVisible())
                self.assertFalse(position_dialog.isEnabled())
                self.assertFalse(self.window.action_open_stm.isEnabled())
                position_dialog.btn_export_analysis.click()
                self.__class__._app.processEvents()
                self.assertEqual(len(export_calls), 1)
                self.assertIsNotNone(export_calls[0][2])
                release_exporter.set()
                self.process_events_until(lambda: not self.window.analysis_export_running())

                self.assertTrue(position_dialog.isEnabled())
                self.assertTrue(self.window.action_open_stm.isEnabled())
                information.assert_called_once()
        finally:
            release_exporter.set()
            release_timer.cancel()

    def test_default_analysis_exporter_publishes_a_full_series_package(self) -> None:
        frame_count = 20
        detections = MolecularDetectionSet(frame_count=frame_count)
        for frame_index in range(frame_count):
            detections.set_detections(
                frame_index,
                [
                    MolecularDetection(
                        frame_index,
                        (1, 1, 3, 3),
                        0.9,
                        detection_id=f"molecule-{frame_index}",
                    )
                ],
                source_view="raw",
                frame_shape=(5, 5),
            )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((frame_count, 5, 5), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_detections=detections,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "full-series-analysis"
            settings = AnalysisExportSettings(
                scope="full_working_series",
                destination=destination,
                package_format="directory",
                include_tables=True,
                include_spatial_grids=False,
                include_plots=False,
                frame_count=frame_count,
                active_frame_index=0,
                source_view="raw",
                use_segmentation_centroids=True,
                intensity_metric="mean",
                intensity_unit="a.u.",
                background_inner_radius_px=1,
                background_outer_radius_px=3,
                density_grid_shape=(8, 8),
            )

            class FakeExportAnalysisDialog:
                def exec(self):
                    return QDialog.DialogCode.Accepted

                def export_settings(self):
                    return settings

            self.window = MolTrackMainWindow(
                yolo_model_discovery=lambda: [],
                analysis_export_dialog_factory=lambda **_kwargs: FakeExportAnalysisDialog(),
            )
            self.window.set_image_series(series)
            self.window.btn_position_analysis.click()

            with patch.object(QMessageBox, "information") as information:
                self.window.position_analysis_dialog().btn_export_analysis.click()

                self.assertTrue(self.window.analysis_export_running())
                self.process_events_until(
                    lambda: not self.window.analysis_export_running(),
                    timeout_s=5.0,
                )

            self.assertTrue((destination / "molecules.csv").is_file())
            self.assertTrue((destination / "frames.csv").is_file())
            self.assertTrue((destination / "manifest.json").is_file())
            success_message = information.call_args.args[2]
            self.assertIn(str(destination), success_message)
            self.assertIn("molecules: 20", success_message)
            self.assertIn("frames: 20", success_message)

    def test_analysis_export_failure_closes_progress_and_preserves_position_analysis(self) -> None:
        settings = AnalysisExportSettings(
            scope="current_frame",
            destination=Path("failed-analysis"),
            package_format="directory",
            include_tables=True,
            include_spatial_grids=False,
            include_plots=False,
            frame_count=1,
            active_frame_index=0,
            source_view="raw",
            use_segmentation_centroids=True,
            intensity_metric="mean",
            intensity_unit="a.u.",
            background_inner_radius_px=1,
            background_outer_radius_px=3,
            density_grid_shape=(4, 4),
        )

        class FakeExportAnalysisDialog:
            def exec(self):
                return QDialog.DialogCode.Accepted

            def export_settings(self):
                return settings

        def failing_exporter(_series, _request, *, progress_callback=None):
            raise RuntimeError("controlled export failure")

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            analysis_export_dialog_factory=lambda **_kwargs: FakeExportAnalysisDialog(),
            analysis_exporter=failing_exporter,
        )
        self.window.set_image_series(
            MolTrackImageSeries(
                source_path="movie.mpp",
                raw_frames=np.zeros((1, 4, 5), dtype=np.float32),
                metadata=STMSequenceMetadata(pixels_x=5, pixels_y=4),
            )
        )
        self.window.btn_position_analysis.click()
        position_dialog = self.window.position_analysis_dialog()
        error_observations = []

        def capture_error(_parent, title, message):
            error_observations.append(
                (
                    title,
                    message,
                    self.window.analysis_export_progress_dialog() is None,
                    position_dialog.isVisible(),
                )
            )

        with patch.object(QMessageBox, "critical", side_effect=capture_error):
            position_dialog.btn_export_analysis.click()
            self.process_events_until(lambda: bool(error_observations))
            self.process_events_until(lambda: not self.window.analysis_export_running())

        self.assertEqual(
            error_observations,
            [
                (
                    "Analysis export error",
                    "controlled export failure",
                    True,
                    True,
                )
            ],
        )
        self.assertIsNone(self.window.analysis_export_progress_dialog())
        self.assertTrue(position_dialog.isVisible())
        self.assertTrue(position_dialog.isEnabled())
        self.assertTrue(self.window.action_open_stm.isEnabled())
        self.assertIn("controlled export failure", self.window.statusBar().currentMessage())

    def test_analysis_export_dialog_reports_frame_and_table_progress(self) -> None:
        frame_progress_sent = threading.Event()
        continue_to_tables = threading.Event()
        table_progress_sent = threading.Event()
        release_exporter = threading.Event()
        settings = AnalysisExportSettings(
            scope="full_working_series",
            destination=Path("progress-analysis"),
            package_format="directory",
            include_tables=True,
            include_spatial_grids=False,
            include_plots=False,
            frame_count=7,
            active_frame_index=0,
            source_view="raw",
            use_segmentation_centroids=True,
            intensity_metric="mean",
            intensity_unit="a.u.",
            background_inner_radius_px=1,
            background_outer_radius_px=3,
            density_grid_shape=(4, 4),
        )

        class FakeExportAnalysisDialog:
            def exec(self):
                return QDialog.DialogCode.Accepted

            def export_settings(self):
                return settings

        def progress_exporter(_series, request, *, progress_callback=None):
            progress_callback(AnalysisExportProgress("analyzing_frames", 3, 7))
            frame_progress_sent.set()
            continue_to_tables.wait(timeout=2.0)
            progress_callback(AnalysisExportProgress("writing_tables"))
            table_progress_sent.set()
            release_exporter.wait(timeout=2.0)
            return SimpleNamespace(
                package_path=request.destination,
                relative_files=("molecules.csv", "frames.csv"),
                record_counts=(("molecules.csv", 12), ("frames.csv", 7)),
            )

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            analysis_export_dialog_factory=lambda **_kwargs: FakeExportAnalysisDialog(),
            analysis_exporter=progress_exporter,
        )
        self.window.set_image_series(
            MolTrackImageSeries(
                source_path="movie.mpp",
                raw_frames=np.zeros((7, 4, 5), dtype=np.float32),
                metadata=STMSequenceMetadata(pixels_x=5, pixels_y=4),
            )
        )
        self.window.btn_position_analysis.click()

        try:
            with patch.object(QMessageBox, "information"):
                self.window.position_analysis_dialog().btn_export_analysis.click()
                self.process_events_until(frame_progress_sent.is_set)
                self.process_events_until(
                    lambda: self.window.analysis_export_progress_dialog().maximum() == 7
                )
                progress_dialog = self.window.analysis_export_progress_dialog()
                self.assertEqual(progress_dialog.value(), 3)
                self.assertEqual(progress_dialog.labelText(), "Analyzing frames... 3/7")

                continue_to_tables.set()
                self.process_events_until(table_progress_sent.is_set)
                self.process_events_until(
                    lambda: self.window.analysis_export_progress_dialog().labelText()
                    == "Writing analysis tables..."
                )
                release_exporter.set()
                self.process_events_until(lambda: not self.window.analysis_export_running())
        finally:
            continue_to_tables.set()
            release_exporter.set()

    def test_position_analysis_dialog_presents_nearest_neighbor_metrics_and_angle_histogram(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9),
                MolecularDetection(frame_index=0, bbox_xyxy=(2, 0, 4, 2), confidence=0.8),
                MolecularDetection(frame_index=0, bbox_xyxy=(5, 0, 7, 2), confidence=0.7),
            ],
            source_view="raw",
            frame_shape=(3, 8),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 3, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=3),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)

        self.window.btn_position_analysis.click()
        self.__class__._app.processEvents()

        dialog = self.window.position_analysis_dialog()
        summary = dialog.metrics_summary_text()
        self.assertIn("Molecules: 3", summary)
        self.assertIn(
            "Nearest neighbor [px]: mean 2.333 | median 2.000 | min 2.000 | max 3.000",
            summary,
        )
        self.assertIn("Angular coherence: 1.000", summary)
        self.assertEqual(dialog.histogram_counts(), (3,) + (0,) * 17)
        self.assertEqual(dialog.histogram_axis_labels(), ("Angle [deg]", "Count"))

    def test_position_analysis_dialog_edits_two_frame_ranges_independently(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((12, 3, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=3),
        )
        self.window.set_image_series(series)

        self.window.btn_position_analysis.click()
        self.__class__._app.processEvents()

        dialog = self.window.position_analysis_dialog()
        dialog.edit_first_range_name.setText("before desorption")
        dialog.sp_first_range_start.setValue(1)
        dialog.sp_first_range_end.setValue(4)
        dialog.edit_second_range_name.setText("after adsorption")
        dialog.sp_second_range_start.setValue(9)
        dialog.sp_second_range_end.setValue(12)

        selection = dialog.frame_range_selection()
        self.assertEqual(selection.source_view, "raw")
        self.assertEqual(selection.first_range.frame_indices, (0, 1, 2, 3))
        self.assertEqual(selection.second_range.frame_indices, (8, 9, 10, 11))

        dialog.sp_first_range_end.setValue(3)
        edited_selection = dialog.frame_range_selection()
        self.assertEqual(edited_selection.first_range.frame_indices, (0, 1, 2))
        self.assertEqual(edited_selection.second_range, selection.second_range)

    def test_position_analysis_dialog_reports_reversed_frame_range(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((6, 3, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=3),
        )
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()

        dialog = self.window.position_analysis_dialog()
        dialog.sp_first_range_start.setValue(5)
        dialog.sp_first_range_end.setValue(3)
        self.__class__._app.processEvents()

        self.assertFalse(dialog.has_valid_frame_range_selection())
        self.assertIn("Start frame must not exceed end frame", dialog.range_validation_message())

    def test_position_analysis_dialog_compares_ranges_on_four_trend_plots(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9),
                MolecularDetection(frame_index=0, bbox_xyxy=(2, 0, 4, 2), confidence=0.8),
            ],
            source_view="raw",
            frame_shape=(8, 8),
        )
        detections.set_detections(
            1,
            [
                MolecularDetection(frame_index=1, bbox_xyxy=(0, 0, 2, 2), confidence=0.9),
                MolecularDetection(frame_index=1, bbox_xyxy=(3, 0, 5, 2), confidence=0.8),
                MolecularDetection(frame_index=1, bbox_xyxy=(0, 3, 2, 5), confidence=0.7),
                MolecularDetection(frame_index=1, bbox_xyxy=(3, 3, 5, 5), confidence=0.6),
            ],
            source_view="raw",
            frame_shape=(8, 8),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()

        dialog.btn_compare_ranges.click()
        self.__class__._app.processEvents()

        trend_data = dialog.range_trend_data()
        self.assertEqual(
            dialog.analysis_tab_labels(),
            (
                "Current frame",
                "Range trends",
                "Spatial comparison",
                "Sixfold Bond Order",
                "Domain Types",
            ),
        )
        self.assertEqual(dialog.active_analysis_tab(), "Range trends")
        self.assertEqual(dialog.trend_legend_labels(), ("before desorption", "after adsorption"))
        self.assertEqual(trend_data.first.molecule_counts, (2,))
        self.assertEqual(trend_data.second.molecule_counts, (4,))
        self.assertEqual(trend_data.first.median_intensities, (0.0,))
        self.assertEqual(trend_data.second.median_intensities, (0.0,))
        self.assertEqual(
            dialog.trend_axis_labels(),
            (
                ("Frame", "Molecules"),
                ("Frame", "Nearest neighbor [px]"),
                ("Frame", "Angular coherence"),
                ("Frame", "Median intensity [a.u.]"),
            ),
        )
        self.assertIsNotNone(dialog.intensity_trend_plot)
        spatial_data = dialog.range_spatial_data()
        self.assertEqual(spatial_data.first.points_xy, ((1.0, 1.0), (3.0, 1.0)))
        self.assertEqual(
            spatial_data.second.points_xy,
            ((1.0, 1.0), (4.0, 1.0), (1.0, 4.0), (4.0, 4.0)),
        )
        self.assertEqual(dialog.spatial_condition_names(), ("before desorption", "after adsorption"))
        self.assertEqual(dialog.spatial_axis_ranges(), ((0.0, 8.0), (0.0, 8.0)))
        first_scale, second_scale = dialog.spatial_density_value_ranges()
        self.assertEqual(first_scale, second_scale)
        dialog.activate_analysis_tab("Spatial comparison")
        self.assertEqual(dialog.active_analysis_tab(), "Spatial comparison")

        dialog.cmb_intensity_metric.setCurrentText("Maximum")
        self.__class__._app.processEvents()

        self.assertEqual(dialog.range_trend_data().first.intensity_metric, "max")
        self.assertEqual(dialog.range_trend_data().second.intensity_metric, "max")
        self.assertEqual(dialog.active_analysis_tab(), "Spatial comparison")

    def test_m6_run_uses_worker_and_reports_frame_progress_without_blocking_qt(self) -> None:
        worker_started = threading.Event()
        release_worker = threading.Event()
        received_settings = []

        def blocking_comparator(series, selection, **kwargs):
            received_settings.append(kwargs.get("m6_orientation_settings"))
            progress_callback = kwargs.get("progress_callback")
            if progress_callback is not None:
                progress_callback(1, 2, 0)
            worker_started.set()
            release_worker.wait(timeout=2.0)
            return compare_molecular_frame_ranges(series, selection, **kwargs)

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            position_range_comparator=blocking_comparator,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=8,
                pixels_y=8,
                size_nm_x=8.0,
                size_nm_y=8.0,
                scan_angle_deg=0.0,
            ),
        )
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        dialog.activate_analysis_tab("Sixfold Bond Order")

        started_at = time.monotonic()
        dialog.m6_run_button.click()
        elapsed = time.monotonic() - started_at

        try:
            self.assertLess(elapsed, 0.2)
            self.process_events_until(worker_started.is_set)
            self.assertTrue(self.window._m6_analysis_running)
            self.assertTrue(dialog.m6_run_button.isEnabled())
            self.assertEqual(dialog.m6_run_button.text(), "Cancel analysis")
            self.assertFalse(dialog.range_group.isEnabled())
            self.assertFalse(dialog.chk_use_segmentation_centroids.isEnabled())
            self.assertFalse(
                dialog.m6_settings_panel.pair_correlation_plot.current_r_max_line.movable
            )
            self.process_events_until(
                lambda: "1/2" in dialog.m6_settings_panel.progress_label.text()
            )
            self.assertIsNone(series.m6_analysis_state)
            self.assertEqual(received_settings, [dialog.m6_analysis_settings()])
            dialog.m6_settings_panel.overlay_opacity.setValue(37)
            self.assertEqual(
                self.window._m6_pending_session_state.view_settings.overlay_opacity_percent,
                37,
            )
        finally:
            release_worker.set()

        self.process_events_until(lambda: not self.window._m6_analysis_running)
        self.assertTrue(dialog.m6_run_button.isEnabled())
        self.assertTrue(
            dialog.m6_settings_panel.pair_correlation_plot.current_r_max_line.movable
        )
        self.assertTrue(series.m6_analysis_state.enabled)
        self.assertEqual(
            series.m6_analysis_state.view_settings.overlay_opacity_percent,
            37,
        )
        self.assertEqual(dialog.active_analysis_tab(), "Sixfold Bond Order")
        self.assertTrue(
            dialog.m6_settings_panel.pair_correlation_plot.has_result()
        )
        self.assertIn("complete", self.window.statusBar().currentMessage().lower())

    def test_m6_overlay_tracks_active_frame_controls_and_keeps_bbox_layer_independent(self) -> None:
        frame_size = 32
        points = tuple(
            (
                6.0 + 2.0 * (column + 0.5 * (row % 2)),
                6.0 + np.sqrt(3.0) * row,
            )
            for row in range(4)
            for column in range(4)
        )
        detections = MolecularDetectionSet(frame_count=2)
        for frame_index in range(2):
            detections.set_detections(
                frame_index,
                [
                    MolecularDetection(
                        frame_index=frame_index,
                        bbox_xyxy=(
                            x - 0.2,
                            frame_size - y - 0.2,
                            x + 0.2,
                            frame_size - y + 0.2,
                        ),
                        confidence=0.9,
                        detection_id=f"molecule-{frame_index}-{index}",
                    )
                    for index, (x, y) in enumerate(points)
                ],
                source_view="raw",
                frame_shape=(frame_size, frame_size),
            )
        linked_mask = np.zeros((frame_size, frame_size), dtype=bool)
        linked_mask[26, 6] = True
        segmentations = MolecularSegmentationSet(frame_count=2)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                mask=linked_mask,
                prompt_detection_ids=("molecule-0-0",),
                segmentation_id="segmentation-0-0",
                origin="sam2",
            )
        )
        settings = MolecularM6OrientationAnalysisSettings(
            first_shell_r_min_nm=1.5,
            first_shell_r_max_nm=2.3,
            gr_max_nm=12.0,
            min_ordered_component_size=3,
            min_seed_size=5,
            min_domain_size=8,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, frame_size, frame_size), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=frame_size,
                pixels_y=frame_size,
                size_nm_x=float(frame_size),
                size_nm_y=float(frame_size),
                scan_angle_deg=0.0,
            ),
            molecular_detections=detections,
            molecular_segmentations=segmentations,
            m6_analysis_state=MolecularM6SessionState(
                enabled=True,
                settings=settings,
                view_settings=MolecularM6ViewSettings(
                    overlay_mode="domain_id",
                    overlay_opacity_percent=60,
                ),
            ),
        )
        selection = MolecularFrameRangeSelection(
            frame_count=2,
            source_view="raw",
            first_range=MolecularFrameRange("first", 0, 0),
            second_range=MolecularFrameRange("second", 1, 1),
        )
        comparison = compare_molecular_frame_ranges(
            series,
            selection,
            m6_orientation_settings=settings,
        )
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        dialog.apply_frame_range_selection(selection, notify=False)
        self.window._m6_completed_context = SimpleNamespace(
            result=comparison,
            scope=selection.to_analysis_scope(),
            use_segmentation_centroids=True,
            settings=settings,
        )

        self.window._render_current_m6_overlay()

        self.assertEqual(self.window.viewer.visible_m6_overlay_count(), len(points))
        self.assertEqual(self.window.viewer.m6_overlay_graphics_item_count(), 1)
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), len(points))
        self.assertTrue(
            all(color[3] == 153 for color in self.window.viewer.visible_m6_overlay_colors())
        )
        analysis = self.window._current_m6_analysis_result()
        self.assertIsNotNone(analysis)
        component = analysis.frame_aggregates.domain_metrics.components[0]
        original_domain_ids = analysis.segmentation.m6_orientation_domain_id
        self.assertEqual(
            dialog.m6_settings_panel.current_frame_results_panel.domain_row_count(),
            len(analysis.frame_aggregates.domain_metrics.components),
        )
        selected_source_id = analysis.point_source_ids[5]
        self.window.viewer.select_molecular_detection_by_id(selected_source_id)
        selected_text = dialog.m6_settings_panel.selected_point_text()
        self.assertIn(selected_source_id, selected_text)
        self.assertIn("q3", selected_text)
        self.assertIn("q6", selected_text)
        self.window.viewer.select_molecular_detection_by_id("molecule-0-0")
        self.assertIn(
            "segmentation-0-0",
            dialog.m6_settings_panel.selected_point_text(),
        )

        with patch("moltrack.ui.main_window.analyze_molecular_frame_range") as compute:
            dialog.set_m6_overlay_mode("q3")
            dialog.set_m6_overlay_mode("m3_orientation")
            dialog.set_m6_overlay_mode("symmetry_evidence")
        compute.assert_not_called()
        self.assertEqual(self.window.viewer.visible_m6_overlay_count(), len(points))

        dialog.m6_settings_panel.current_frame_results_panel.domain_table.setCurrentCell(
            0,
            0,
        )

        self.assertEqual(
            self.window.viewer.highlighted_m6_overlay_source_ids(),
            component.source_ids,
        )
        self.assertEqual(
            analysis.segmentation.m6_orientation_domain_id,
            original_domain_ids,
        )

        dialog.set_m6_overlay_mode("none")

        self.assertEqual(
            self.window.viewer.visible_m6_overlay_source_ids(),
            component.source_ids,
        )
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), len(points))

        dialog.m6_settings_panel.current_frame_results_panel.domain_table.setCurrentCell(
            -1,
            -1,
        )
        self.assertEqual(self.window.viewer.visible_m6_overlay_count(), 0)
        dialog.m6_settings_panel.current_frame_results_panel.domain_table.setCurrentCell(
            0,
            0,
        )
        self.assertEqual(
            self.window.viewer.highlighted_m6_overlay_source_ids(),
            component.source_ids,
        )

        dialog.set_m6_overlay_mode("domain_id")
        graphics_item = self.window.viewer._m6_point_overlay_item
        dialog.m6_settings_panel.overlay_opacity.setValue(40)
        self.assertIs(self.window.viewer._m6_point_overlay_item, graphics_item)
        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.viewer.visible_m6_overlay_count(), len(points))
        self.assertTrue(
            all(color[3] == 102 for color in self.window.viewer.visible_m6_overlay_colors())
        )
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), len(points))

        series.metadata = replace(series.metadata, scan_angle_deg=15.0)
        self.window._render_current_m6_overlay()

        self.assertEqual(self.window.viewer.visible_m6_overlay_count(), 0)

        dialog.chk_use_segmentation_centroids.setChecked(False)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.viewer.visible_m6_overlay_count(), 0)
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), len(points))

    def test_replacing_series_recreates_position_dialog_with_new_m6_settings(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        first = MolTrackImageSeries(
            source_path="first.mpp",
            raw_frames=np.zeros((2, 4, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
        )
        second_settings = MolecularM6OrientationAnalysisSettings(q_seed=0.8, q_grow=0.4)
        second = MolTrackImageSeries(
            source_path="second.mpp",
            raw_frames=np.zeros((2, 4, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            m6_analysis_state=MolecularM6SessionState(settings=second_settings),
        )
        self.window.set_image_series(first)
        self.window.btn_position_analysis.click()
        first_dialog = self.window.position_analysis_dialog()
        first_dialog.m6_settings_panel.q_seed.setValue(0.7)

        self.window.set_image_series(second)
        self.window.btn_position_analysis.click()
        second_dialog = self.window.position_analysis_dialog()

        self.assertIsNot(second_dialog, first_dialog)
        self.assertEqual(second_dialog.m6_analysis_settings(), second_settings)

    def test_m6_first_shell_suggestion_can_start_before_a_previous_m6_run(self) -> None:
        comparator_started = threading.Event()
        received_settings = []

        def comparator(series, selection, **kwargs):
            received_settings.append(kwargs.get("m6_orientation_settings"))
            comparator_started.set()
            return compare_molecular_frame_ranges(series, selection, **kwargs)

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            position_range_comparator=comparator,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=8,
                pixels_y=8,
                size_nm_x=8.0,
                size_nm_y=8.0,
            ),
        )
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        dialog.btn_compare_ranges.click()
        self.assertIsNotNone(dialog.range_comparison())
        self.assertTrue(
            all(
                frame.m6_orientation_analysis is None
                for frame in dialog.range_comparison().first_analysis.frame_results
            )
        )
        received_settings.clear()
        comparator_started.clear()
        first_settings = dialog.m6_analysis_settings()

        dialog.m6_settings_panel.suggest_button.click()

        self.process_events_until(comparator_started.is_set)
        self.assertEqual(received_settings, [first_settings])
        self.process_events_until(lambda: not self.window._m6_analysis_running)
        self.assertIsNone(series.m6_analysis_state)
        self.assertIsNotNone(dialog.range_comparison())

        comparator_started.clear()
        dialog.edit_first_range_name.setText("changed range")
        dialog.m6_settings_panel.suggest_button.click()

        self.process_events_until(comparator_started.is_set)
        self.process_events_until(lambda: not self.window._m6_analysis_running)

        comparator_started.clear()
        dialog.chk_use_segmentation_centroids.setChecked(False)
        dialog.m6_settings_panel.suggest_button.click()

        self.process_events_until(comparator_started.is_set)
        self.process_events_until(lambda: not self.window._m6_analysis_running)

        comparator_started.clear()
        dialog.m6_settings_panel.q_seed.setValue(0.7)
        second_settings = dialog.m6_analysis_settings()
        dialog.m6_settings_panel.suggest_button.click()

        self.process_events_until(comparator_started.is_set)
        self.process_events_until(lambda: not self.window._m6_analysis_running)
        self.assertEqual(
            received_settings,
            [first_settings, first_settings, first_settings, second_settings],
        )

    def test_m6_does_not_start_during_conflicting_state_io_operations(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        self.window.set_image_series(
            MolTrackImageSeries(
                source_path="movie.mpp",
                raw_frames=np.zeros((2, 4, 4), dtype=np.float32),
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            )
        )
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        try:
            for operation in ("save", "open"):
                self.window._state_io_running = True
                self.window._state_io_operation = operation
                dialog.m6_run_button.click()
                self.assertFalse(self.window._m6_analysis_running)
                self.assertIsNone(self.window._m6_analysis_thread)
        finally:
            self.window._state_io_running = False
            self.window._state_io_operation = ""

    def test_failed_m6_worker_preserves_previous_state_and_reenables_controls(self) -> None:
        previous_state = MolecularM6SessionState(
            enabled=True,
            settings=MolecularM6OrientationAnalysisSettings(q_seed=0.7, q_grow=0.3),
        )

        def failing_comparator(_series, _selection, **_kwargs):
            raise RuntimeError("synthetic M6 failure")

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            position_range_comparator=failing_comparator,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=8,
                pixels_y=8,
                size_nm_x=8.0,
                size_nm_y=8.0,
            ),
            m6_analysis_state=previous_state,
        )
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        dialog.activate_analysis_tab("Sixfold Bond Order")
        dialog.m6_settings_panel.q_seed.setValue(0.8)

        with patch.object(QMessageBox, "critical") as critical:
            dialog.m6_run_button.click()
            self.process_events_until(lambda: not self.window._m6_analysis_running)

        self.assertEqual(series.m6_analysis_state, previous_state)
        self.assertTrue(dialog.m6_run_button.isEnabled())
        critical.assert_called_once()

    def test_restoring_completed_m6_analysis_recomputes_in_worker(self) -> None:
        comparator_started = threading.Event()
        release_comparator = threading.Event()
        received_settings = []

        def comparator(series, selection, **kwargs):
            received_settings.append(kwargs.get("m6_orientation_settings"))
            comparator_started.set()
            if not release_comparator.wait(timeout=2.0):
                raise RuntimeError("Test did not release the M6 comparator.")
            return compare_molecular_frame_ranges(series, selection, **kwargs)

        settings = MolecularM6OrientationAnalysisSettings(q_seed=0.7, q_grow=0.3)
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            position_range_comparator=comparator,
        )
        self.window.set_image_series(
            MolTrackImageSeries(
                source_path="movie.mpp",
                raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
                metadata=STMSequenceMetadata(
                    pixels_x=8,
                    pixels_y=8,
                    size_nm_x=8.0,
                    size_nm_y=8.0,
                ),
                m6_analysis_state=MolecularM6SessionState(
                    enabled=True,
                    settings=settings,
                ),
            )
        )
        state = MolTrackPositionAnalysisState(
            source_view="raw",
            first_range=MolTrackPositionAnalysisRange("before", 0, 0),
            second_range=MolTrackPositionAnalysisRange("after", 1, 1),
            comparison_completed=True,
            active_tab="Sixfold Bond Order",
            density_grid_shape=(12, 18),
        )

        self.window._restore_position_analysis_state(state)

        self.process_events_until(comparator_started.is_set)
        self.assertTrue(self.window._m6_analysis_running)
        self.assertTrue(self.window._m6_analysis_thread.isRunning())
        self.assertEqual(received_settings, [settings])
        release_comparator.set()
        self.process_events_until(lambda: not self.window._m6_analysis_running)
        dialog = self.window.position_analysis_dialog()
        self.assertEqual(dialog.active_analysis_tab(), "Sixfold Bond Order")
        self.assertEqual(dialog.density_grid_shape(), (12, 18))
        self.assertIsNotNone(dialog.range_comparison())

    def test_position_analysis_spatial_comparison_uses_shared_intensity_scale(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.zeros((2, 8, 8), dtype=np.float32)
        frames[0, 1:3, 1:3] = 2.0
        frames[1, 5:7, 5:7] = 10.0
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [MolecularDetection(0, (1, 1, 3, 3), 0.9, detection_id="before")],
            source_view="raw",
            frame_shape=(8, 8),
        )
        detections.set_detections(
            1,
            [MolecularDetection(1, (5, 5, 7, 7), 0.9, detection_id="after")],
            source_view="raw",
            frame_shape=(8, 8),
        )
        self.window.set_image_series(
            MolTrackImageSeries(
                source_path="movie.mpp",
                raw_frames=frames,
                metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
                molecular_detections=detections,
            )
        )
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        dialog.cmb_intensity_metric.setCurrentText("Mean")

        dialog.btn_compare_ranges.click()
        self.__class__._app.processEvents()

        expected_levels = ((2.0, 10.0), (2.0, 10.0))
        self.assertEqual(dialog.spatial_scatter_intensity_value_ranges(), expected_levels)
        first_colors, second_colors = dialog.spatial_scatter_point_colors()
        self.assertNotEqual(first_colors[0], second_colors[0])
        self.assertEqual(dialog.spatial_intensity_value_ranges(), expected_levels)
        self.assertIsNotNone(dialog.first_intensity_plot)
        self.assertIsNotNone(dialog.second_intensity_plot)
        self.assertEqual(
            dialog.spatial_intensity_condition_names(),
            ("before desorption", "after adsorption"),
        )
        first_density, second_density = dialog.spatial_density_value_ranges()
        self.assertEqual(first_density, second_density)

    def test_save_state_captures_position_analysis_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_path = tmp_path / "movie.mpp"
            source_path.write_bytes(b"fake mpp bytes")
            session_path = tmp_path / "state.moltrack.json"
            self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
            self.window.set_image_series(
                MolTrackImageSeries(
                    source_path=str(source_path),
                    raw_frames=np.zeros((4, 3, 4), dtype=np.float32),
                    metadata=STMSequenceMetadata(pixels_x=4, pixels_y=3),
                )
            )
            self.window.btn_position_analysis.click()
            dialog = self.window.position_analysis_dialog()
            dialog.edit_first_range_name.setText("before desorption")
            dialog.sp_first_range_start.setValue(1)
            dialog.sp_first_range_end.setValue(2)
            dialog.edit_second_range_name.setText("after adsorption")
            dialog.sp_second_range_start.setValue(3)
            dialog.sp_second_range_end.setValue(4)
            dialog.chk_use_segmentation_centroids.setChecked(False)
            dialog.cmb_intensity_metric.setCurrentText("Maximum")
            dialog.chk_color_by_intensity.setChecked(False)
            dialog.set_intensity_background_radii(2, 5)
            dialog.m6_settings_panel.q_seed.setValue(0.7)
            dialog.m6_settings_panel.q_grow.setValue(0.3)
            dialog.m6_settings_panel.gr_bin_width_nm.setValue(0.25)
            dialog.m6_settings_panel.gr_max_nm.setValue(8.0)
            dialog.m6_settings_panel.gr_min_expected_pair_exposure.setValue(7.5)
            dialog.m6_settings_panel.gr_min_contributing_frames.setValue(2)
            dialog.m6_settings_panel.gr_smoothing_width.setValue(1.25)
            dialog.m6_settings_panel.gr_peak_prominence.setValue(0.15)
            dialog.btn_compare_ranges.click()
            dialog.activate_analysis_tab("Spatial comparison")
            dialog.close()
            self.__class__._app.processEvents()

            self.window.save_state(session_path)
            loaded = load_moltrack_session(session_path)

            self.assertIsNotNone(loaded.position_analysis)
            self.assertEqual(loaded.position_analysis.first_range.name, "before desorption")
            self.assertEqual(loaded.position_analysis.first_range.frame_indices, (0, 1))
            self.assertEqual(loaded.position_analysis.second_range.name, "after adsorption")
            self.assertEqual(loaded.position_analysis.second_range.frame_indices, (2, 3))
            self.assertTrue(loaded.position_analysis.comparison_completed)
            self.assertEqual(loaded.position_analysis.active_tab, "Spatial comparison")
            self.assertEqual(loaded.position_analysis.density_grid_shape, (32, 32))
            self.assertFalse(loaded.position_analysis.use_segmentation_centroids)
            self.assertEqual(loaded.position_analysis.intensity_metric, "max")
            self.assertFalse(loaded.position_analysis.color_points_by_intensity)
            self.assertEqual(loaded.position_analysis.background_inner_radius_px, 2)
            self.assertEqual(loaded.position_analysis.background_outer_radius_px, 5)
            self.assertTrue(loaded.position_analysis.shared_intensity_scale)
            self.assertIsNotNone(loaded.m6_analysis_state)
            self.assertFalse(loaded.m6_analysis_state.enabled)
            self.assertEqual(loaded.m6_analysis_state.settings.q_seed, 0.7)
            self.assertEqual(loaded.m6_analysis_state.settings.q_grow, 0.3)
            self.assertEqual(loaded.m6_analysis_state.settings.gr_bin_width_nm, 0.25)
            self.assertEqual(loaded.m6_analysis_state.settings.gr_max_nm, 8.0)
            self.assertEqual(
                loaded.m6_analysis_state.settings.gr_min_expected_pair_exposure,
                7.5,
            )
            self.assertEqual(
                loaded.m6_analysis_state.settings.gr_min_contributing_frames,
                2,
            )
            self.assertEqual(loaded.m6_analysis_state.settings.gr_smoothing_width, 1.25)
            self.assertEqual(loaded.m6_analysis_state.settings.gr_peak_prominence, 0.15)
            self.assertFalse(loaded.m6_analysis_state.use_segmentation_centroids)

    def test_async_save_rejects_invalid_m6_settings_without_entering_io_state(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        self.window.set_image_series(
            MolTrackImageSeries(
                source_path="movie.mpp",
                raw_frames=np.zeros((2, 4, 4), dtype=np.float32),
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            )
        )
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        dialog.m6_first_shell_r_min_spin.setValue(3.0)
        dialog.m6_first_shell_r_max_spin.setValue(2.0)

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            QMessageBox,
            "critical",
        ) as critical:
            self.window._start_save_state(Path(tmpdir) / "invalid.moltrack.json")

        self.assertFalse(self.window._state_io_running)
        self.assertIsNone(self.window._state_io_thread)
        self.assertIsNone(self.window._state_io_progress_dialog)
        critical.assert_called_once()

    def test_open_state_restores_position_analysis_and_recomputes_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_path = tmp_path / "movie.mpp"
            source_path.write_bytes(b"fake mpp bytes")
            session_path = tmp_path / "state.moltrack.json"
            frames = np.zeros((4, 4, 4), dtype=np.float32)

            def fake_series_loader(source_path_arg, *, reverse_frame_order=False):
                return MolTrackImageSeries(
                    source_path=str(source_path_arg),
                    raw_frames=frames.copy(),
                    metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
                    reverse_frame_order=reverse_frame_order,
                )

            detections = MolecularDetectionSet(frame_count=4)
            detections.set_detections(
                0,
                [MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9)],
                source_view="raw",
                frame_shape=(4, 4),
            )
            detections.set_detections(
                2,
                [
                    MolecularDetection(frame_index=2, bbox_xyxy=(0, 0, 2, 2), confidence=0.9),
                    MolecularDetection(frame_index=2, bbox_xyxy=(2, 2, 4, 4), confidence=0.8),
                ],
                source_view="raw",
                frame_shape=(4, 4),
            )
            self.window = MolTrackMainWindow(
                series_loader=fake_series_loader,
                yolo_model_discovery=lambda: [],
            )
            self.window.set_image_series(
                MolTrackImageSeries(
                    source_path=str(source_path),
                    raw_frames=frames.copy(),
                    metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
                    molecular_detections=detections,
                )
            )
            self.window.btn_position_analysis.click()
            dialog = self.window.position_analysis_dialog()
            dialog.edit_first_range_name.setText("before")
            dialog.edit_second_range_name.setText("after")
            dialog.chk_use_segmentation_centroids.setChecked(False)
            dialog.cmb_intensity_metric.setCurrentText("Maximum")
            dialog.chk_color_by_intensity.setChecked(False)
            dialog.set_intensity_background_radii(2, 5)
            dialog.btn_compare_ranges.click()
            dialog.activate_analysis_tab("Spatial comparison")
            self.window.save_state(session_path)

            self.window.close()
            self.window.deleteLater()
            self.__class__._app.processEvents()
            self.window = MolTrackMainWindow(
                series_loader=fake_series_loader,
                yolo_model_discovery=lambda: [],
            )

            self.window.open_state(session_path)
            self.__class__._app.processEvents()

            restored_dialog = self.window.position_analysis_dialog()
            self.assertIsNotNone(restored_dialog)
            self.assertTrue(restored_dialog.isVisible())
            restored_selection = restored_dialog.frame_range_selection()
            self.assertEqual(restored_selection.first_range.name, "before")
            self.assertEqual(restored_selection.first_range.frame_indices, (0, 1))
            self.assertEqual(restored_selection.second_range.name, "after")
            self.assertEqual(restored_selection.second_range.frame_indices, (2, 3))
            self.assertTrue(restored_dialog.has_range_comparison())
            self.assertEqual(restored_dialog.active_analysis_tab(), "Spatial comparison")
            self.assertFalse(restored_dialog.chk_use_segmentation_centroids.isChecked())
            self.assertEqual(restored_dialog.cmb_intensity_metric.currentData(), "max")
            self.assertFalse(restored_dialog.chk_color_by_intensity.isChecked())
            self.assertEqual(restored_dialog.intensity_background_radii(), (2, 5))
            self.assertEqual(restored_dialog.range_trend_data().first.molecule_counts, (1, 0))
            self.assertEqual(restored_dialog.range_trend_data().second.molecule_counts, (2, 0))
            self.assertEqual(restored_dialog.range_trend_data().first.intensity_metric, "max")
            self.assertEqual(len(restored_dialog.range_spatial_data().first.points_xy), 1)
            self.assertEqual(len(restored_dialog.range_spatial_data().second.points_xy), 2)
            self.assertEqual(restored_dialog.range_spatial_data().intensity_metric, "max")

    def test_open_state_rejects_unrepresentable_gr_settings_before_replacing_series(self) -> None:
        original_series = MolTrackImageSeries(
            source_path="original.mpp",
            raw_frames=np.zeros((2, 4, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
        )
        incoming_series = MolTrackImageSeries(
            source_path="incoming.mpp",
            raw_frames=np.zeros((2, 4, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            m6_analysis_state=MolecularM6SessionState(
                settings=MolecularM6OrientationAnalysisSettings(
                    gr_bin_width_nm=1e9,
                    gr_max_nm=1e13,
                )
            ),
        )
        session = SimpleNamespace(
            registration_view_mode="Show raw",
            position_analysis=None,
        )
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            session_loader=lambda _path: session,
            session_restorer=lambda _session: incoming_series,
        )
        self.window.set_image_series(original_series)

        with patch.object(QMessageBox, "critical") as critical:
            self.window.open_state("unrepresentable.moltrack.json")

        self.assertIs(self.window._series, original_series)
        self.assertIsNone(self.window._session_path)
        critical.assert_called_once()

    def test_open_position_analysis_dialog_refreshes_when_frame_changes(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9)],
            source_view="raw",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            1,
            [
                MolecularDetection(frame_index=1, bbox_xyxy=(1, 1, 3, 3), confidence=0.8),
                MolecularDetection(frame_index=1, bbox_xyxy=(2, 2, 4, 4), confidence=0.7),
            ],
            source_view="raw",
            frame_shape=(4, 4),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 4, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()
        self.__class__._app.processEvents()
        dialog = self.window.position_analysis_dialog()

        self.assertEqual(dialog.displayed_points_xy(), ((1.0, 1.0),))
        self.assertEqual(dialog.frame_range_selection().source_view, "raw")

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()

        self.assertIs(self.window.position_analysis_dialog(), dialog)
        self.assertEqual(dialog.displayed_points_xy(), ((2.0, 2.0), (3.0, 3.0)))
        self.assertEqual(dialog.point_count(), 2)
        self.assertEqual(dialog.lbl_status.text(), "Points: 2")

    def test_open_position_analysis_dialog_refreshes_when_source_view_changes(self) -> None:
        expanded_stack = SimpleNamespace(
            frames=np.zeros((1, 6, 6), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=6, pixels_y=6),
            padding_ltrb=(1, 1, 1, 1),
            frame_origins_xy=np.zeros((1, 2), dtype=np.float64),
        )

        def fake_expanded_builder(series):
            series.expanded_aligned_stack = expanded_stack
            return expanded_stack

        self.window = MolTrackMainWindow(
            expanded_aligned_builder=fake_expanded_builder,
            yolo_model_discovery=lambda: [],
        )
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9)],
            source_view="raw",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(2, 2, 4, 4),
                    confidence=0.8,
                    source_view="expanded_aligned",
                ),
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(4, 4, 6, 6),
                    confidence=0.7,
                    source_view="expanded_aligned",
                ),
            ],
            source_view="expanded_aligned",
            frame_shape=(6, 6),
        )
        settings = MolTrackRegistrationSettings()
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 4, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
            registration_results=MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    0: MolTrackRegistrationFrameResult(
                        frame_index=0,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                        quality_score=1.0,
                    )
                },
            ),
        )
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()
        self.__class__._app.processEvents()
        dialog = self.window.position_analysis_dialog()

        self.assertEqual(dialog.displayed_points_xy(), ((1.0, 1.0),))

        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.__class__._app.processEvents()

        self.assertIs(self.window.position_analysis_dialog(), dialog)
        self.assertEqual(dialog.displayed_points_xy(), ((2.0, 2.0), (4.0, 4.0)))
        self.assertEqual(dialog.axis_ranges(), ((-1.0, 5.0), (-1.0, 5.0)))
        self.assertEqual(dialog.frame_range_selection().source_view, "expanded_aligned")
        self.assertEqual(dialog.point_count(), 2)

    def test_save_then_open_state_restores_bbox_opacity(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_path = tmp_path / "movie.mpp"
            source_path.write_bytes(b"fake mpp bytes")
            session_path = tmp_path / "state.moltrack.json"
            frames = np.arange(16, dtype=np.float32).reshape(1, 4, 4)

            def fake_series_loader(source_path_arg, *, reverse_frame_order=False):
                detections = MolecularDetectionSet(frame_count=1)
                detections.set_detections(
                    0,
                    [
                        MolecularDetection(
                            frame_index=0,
                            bbox_xyxy=(1, 1, 3, 3),
                            confidence=0.9,
                            source_view="raw",
                        )
                    ],
                    source_view="raw",
                    frame_shape=(4, 4),
                )
                segmentations = MolecularSegmentationSet(frame_count=1)
                mask = np.zeros((4, 4), dtype=bool)
                mask[1:3, 1:3] = True
                segmentations.add_segmentation(
                    MolecularSegmentation(
                        frame_index=0,
                        mask=mask,
                        origin="sam2",
                        segmentation_id="saved-mask",
                    )
                )
                return MolTrackImageSeries(
                    source_path=str(source_path_arg),
                    raw_frames=frames.copy(),
                    metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
                    reverse_frame_order=reverse_frame_order,
                    molecular_detections=detections,
                    molecular_segmentations=segmentations,
                )

            self.window = MolTrackMainWindow(
                series_loader=fake_series_loader,
                yolo_model_discovery=lambda: [],
            )
            self.window.set_image_series(fake_series_loader(source_path))
            self.window.slider_bbox_opacity.setValue(35)
            self.window.slider_mask_opacity.setValue(18)
            self.window.chk_show_bboxes.setChecked(False)
            self.window.save_state(session_path)

            self.window.slider_bbox_opacity.setValue(100)
            self.window.slider_mask_opacity.setValue(90)
            self.window.chk_show_bboxes.setChecked(True)
            self.window.open_state(session_path)
            self.__class__._app.processEvents()

            self.assertFalse(self.window.chk_show_bboxes.isChecked())
            self.assertEqual(self.window.slider_bbox_opacity.value(), 35)
            self.assertEqual(self.window.lbl_bbox_opacity.text(), "BBox opacity: 35%")
            self.assertEqual(self.window.viewer.visible_molecular_detection_opacities(), [])
            self.assertEqual(self.window.slider_mask_opacity.value(), 18)
            self.assertEqual(self.window.lbl_mask_opacity.text(), "Mask opacity: 18%")
            self.assertEqual(self.window.viewer.visible_molecular_segmentation_opacities(), [0.18])

    def test_selecting_molecular_detection_by_pixel_tracks_active_raw_bbox(self) -> None:
        self.window = MolTrackMainWindow()
        frames = np.arange(16, dtype=np.float32).reshape(1, 4, 4)
        detections = MolecularDetectionSet(frame_count=1)
        left_detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(0, 0, 2, 2),
            confidence=0.9,
            source_view="raw",
            detection_id="left",
        )
        right_detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(2, 0, 4, 2),
            confidence=0.8,
            selected=False,
            source_view="raw",
            detection_id="right",
        )
        detections.set_detections(
            0,
            [left_detection, right_detection],
            source_view="raw",
            frame_shape=(4, 4),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)

        selected_id = self.window.select_molecular_detection_at_pixel(1.0, 1.0)

        self.assertEqual(selected_id, "left")
        self.assertEqual(self.window.selected_molecular_detection_id(), "left")
        self.assertEqual(self.window.viewer.selected_molecular_detection_id(), "left")
        self.assertEqual(self.window.viewer.highlighted_molecular_detection_ids(), ["left"])

        selected_id = self.window.select_molecular_detection_at_pixel(3.0, 1.0)

        self.assertEqual(selected_id, "right")
        self.assertEqual(self.window.selected_molecular_detection_id(), "right")
        self.assertEqual(self.window.viewer.highlighted_molecular_detection_ids(), ["right"])
        self.assertFalse(right_detection.selected)

        selected_id = self.window.select_molecular_detection_at_pixel(3.5, 3.5)

        self.assertIsNone(selected_id)
        self.assertIsNone(self.window.selected_molecular_detection_id())
        self.assertEqual(self.window.viewer.highlighted_molecular_detection_ids(), [])

    def test_delete_selected_bbox_removes_only_active_raw_detection(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4)
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(0, 0, 2, 2),
                    confidence=0.9,
                    source_view="raw",
                    detection_id="raw-active",
                )
            ],
            source_view="raw",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            1,
            [
                MolecularDetection(
                    frame_index=1,
                    bbox_xyxy=(1, 1, 3, 3),
                    confidence=0.8,
                    source_view="raw",
                    detection_id="raw-other-frame",
                )
            ],
            source_view="raw",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1, 1, 4, 4),
                    confidence=0.7,
                    source_view="expanded_aligned",
                    detection_id="expanded-active",
                )
            ],
            source_view="expanded_aligned",
            frame_shape=(4, 4),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)

        self.assertFalse(self.window.btn_bbox_delete_selected.isEnabled())
        self.assertEqual(self.window.select_molecular_detection_at_pixel(1.0, 1.0), "raw-active")
        self.assertTrue(self.window.btn_bbox_delete_selected.isEnabled())

        self.window.btn_bbox_delete_selected.click()
        self.__class__._app.processEvents()

        self.assertIsNone(series.molecular_detections.get_detection("raw-active"))
        self.assertIsNotNone(series.molecular_detections.get_detection("raw-other-frame"))
        self.assertIsNotNone(series.molecular_detections.get_detection("expanded-active"))
        self.assertEqual(series.molecular_detections.get_detections(0, source_view="raw"), [])
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 0)
        self.assertIsNone(self.window.selected_molecular_detection_id())
        self.assertFalse(self.window.btn_bbox_delete_selected.isEnabled())
        self.assertIn("current 0", self.window.lbl_yolo_status.text())
        self.assertIn("series 2", self.window.lbl_yolo_status.text())

    def test_add_bbox_drag_adds_manual_raw_detection_clamped_to_active_frame(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
        )
        self.window.set_image_series(series)

        self.assertEqual(self.window.btn_bbox_add.text(), "Add BBox")
        self.assertTrue(self.window.btn_bbox_add.isEnabled())
        self.assertFalse(self.window.viewer.molecular_bbox_add_mode_enabled())

        self.window.btn_bbox_add.click()
        self.__class__._app.processEvents()

        self.assertTrue(self.window.viewer.molecular_bbox_add_mode_enabled())

        detection = self.window.add_manual_bbox_from_pixel_drag((-2.0, 1.0), (3.5, 9.0))
        self.__class__._app.processEvents()

        self.assertIsNotNone(detection)
        self.assertEqual(detection.frame_index, 0)
        self.assertEqual(detection.source_view, "raw")
        self.assertEqual(detection.origin, "manual")
        self.assertEqual(detection.model_name, "manual")
        self.assertEqual(detection.bbox_xyxy, (0.0, 1.0, 3.5, 4.0))
        self.assertEqual(detection.original_bbox_xyxy, detection.bbox_xyxy)
        self.assertEqual(series.molecular_detections.get_detections(0, source_view="raw"), [detection])
        self.assertEqual(series.molecular_detections.get_detections(1, source_view="raw"), [])
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertEqual(self.window.selected_molecular_detection_id(), detection.detection_id)
        self.assertEqual(self.window.viewer.highlighted_molecular_detection_ids(), [detection.detection_id])
        self.assertIn("current 1", self.window.lbl_yolo_status.text())
        self.assertIn("series 1", self.window.lbl_yolo_status.text())

        self.window.sp_bbox_resize_margin.setValue(1.0)
        self.window.btn_bbox_increase.click()
        self.__class__._app.processEvents()

        self.assertEqual(detection.bbox_xyxy, (0.0, 0.0, 4.0, 4.0))

        self.window.btn_bbox_reset.click()
        self.__class__._app.processEvents()

        self.assertEqual(detection.bbox_xyxy, (0.0, 1.0, 3.5, 4.0))
        self.assertEqual(detection.original_bbox_xyxy, (0.0, 1.0, 3.5, 4.0))

    def test_add_bbox_drag_rejects_tiny_bbox_without_creating_detection(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.arange(16, dtype=np.float32).reshape(1, 4, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
        )
        self.window.set_image_series(series)

        detection = self.window.add_manual_bbox_from_pixel_drag((1.0, 1.0), (1.4, 2.0))
        self.__class__._app.processEvents()

        self.assertIsNone(detection)
        self.assertIsNone(series.molecular_detections)
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 0)
        self.assertIn("larger BBox", self.window.statusBar().currentMessage())

    def test_add_bbox_drag_uses_expanded_aligned_view_when_active(self) -> None:
        expanded_frames = np.arange(1 * 5 * 6, dtype=np.float32).reshape(1, 5, 6)

        def fake_expanded_builder(series):
            expanded_stack = SimpleNamespace(
                frames=expanded_frames,
                metadata=STMSequenceMetadata(pixels_x=6, pixels_y=5),
                padding_ltrb=(1, 1, 1, 1),
                frame_origins_xy=np.zeros((series.frame_count, 2), dtype=np.float64),
            )
            series.expanded_aligned_stack = expanded_stack
            return expanded_stack

        self.window = MolTrackMainWindow(
            expanded_aligned_builder=fake_expanded_builder,
            yolo_model_discovery=lambda: [],
        )
        settings = MolTrackRegistrationSettings()
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(1 * 4 * 4, dtype=np.float32).reshape(1, 4, 4),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            registration_results=MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    0: MolTrackRegistrationFrameResult(
                        frame_index=0,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                    )
                },
            ),
        )
        self.window.set_image_series(series)
        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.__class__._app.processEvents()

        detection = self.window.add_manual_bbox_from_pixel_drag((2.0, 1.0), (8.0, 6.0))
        self.__class__._app.processEvents()

        self.assertIsNotNone(detection)
        self.assertEqual(detection.source_view, "expanded_aligned")
        self.assertEqual(detection.origin, "manual")
        self.assertEqual(detection.bbox_xyxy, (2.0, 1.0, 6.0, 5.0))
        self.assertEqual(detection.original_bbox_xyxy, detection.bbox_xyxy)
        self.assertEqual(series.molecular_detections.get_detections(0, source_view="raw"), [])
        self.assertEqual(
            series.molecular_detections.get_detections(0, source_view="expanded_aligned"),
            [detection],
        )
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertEqual(self.window.selected_molecular_detection_id(), detection.detection_id)
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, expanded_frames[0])

    def test_remove_current_frame_after_manual_bbox_clears_detections_and_selection(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
        )
        self.window.set_image_series(series)
        detection = self.window.add_manual_bbox_from_pixel_drag((1.0, 1.0), (3.0, 3.0))
        self.__class__._app.processEvents()

        self.assertIsNotNone(detection)
        self.assertIsNotNone(series.molecular_detections)
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertEqual(self.window.selected_molecular_detection_id(), detection.detection_id)
        self.assertTrue(self.window.btn_bbox_delete_selected.isEnabled())
        self.assertTrue(self.window.btn_bbox_increase.isEnabled())

        self.window.btn_remove_current_frame.click()
        self.__class__._app.processEvents()

        self.assertIsNone(series.molecular_detections)
        self.assertEqual(series.frame_count, 1)
        self.assertEqual(series.active_frame_index, 0)
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 0)
        self.assertIsNone(self.window.selected_molecular_detection_id())
        self.assertFalse(self.window.btn_bbox_delete_selected.isEnabled())
        self.assertFalse(self.window.btn_bbox_increase.isEnabled())
        self.assertIn("current 0", self.window.lbl_yolo_status.text())
        self.assertIn("series 0", self.window.lbl_yolo_status.text())

    def test_viewer_uses_detection_source_view_for_expanded_aligned_overlay(self) -> None:
        expanded_frames = np.arange(2 * 5 * 6, dtype=np.float32).reshape(2, 5, 6)

        def fake_expanded_builder(series):
            expanded_stack = SimpleNamespace(
                frames=expanded_frames,
                metadata=STMSequenceMetadata(pixels_x=6, pixels_y=5),
                padding_ltrb=(1, 1, 1, 2),
                frame_origins_xy=np.zeros((series.frame_count, 2), dtype=np.float64),
            )
            series.expanded_aligned_stack = expanded_stack
            return expanded_stack

        self.window = MolTrackMainWindow(expanded_aligned_builder=fake_expanded_builder)
        frames = np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4)
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9, source_view="raw"),
                MolecularDetection(frame_index=0, bbox_xyxy=(2, 2, 4, 4), confidence=0.7, source_view="raw"),
            ],
            source_view="raw",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1, 1, 5, 4),
                    confidence=0.8,
                    source_view="expanded_aligned",
                    detection_id="expanded",
                )
            ],
            source_view="expanded_aligned",
            frame_shape=(5, 6),
        )
        settings = MolTrackRegistrationSettings()
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            registration_results=MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    frame_index: MolTrackRegistrationFrameResult(
                        frame_index=frame_index,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                    )
                    for frame_index in range(2)
                },
            ),
            molecular_detections=detections,
        )

        self.window.set_image_series(series)

        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 2)
        self.assertIsNotNone(self.window.select_molecular_detection_at_pixel(1.0, 1.0))

        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.__class__._app.processEvents()

        self.assertIsNone(self.window.selected_molecular_detection_id())
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertEqual(self.window.select_molecular_detection_at_pixel(3.0, 2.0), "expanded")
        self.assertEqual(self.window.viewer.highlighted_molecular_detection_ids(), ["expanded"])
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, expanded_frames[0])
        self.assertIn("Expanded aligned", self.window.viewer.lbl_title.text())

    def test_yolo_detect_current_frame_stores_raw_detections_and_updates_viewer(self) -> None:
        calls = []
        checkpoint = Path("model-a.pt")

        class FakeYoloDetector:
            def detect_frame(
                self,
                frame,
                *,
                frame_index,
                checkpoint_path,
                confidence_threshold,
                iou_threshold,
                source_view,
                size_filter=None,
            ):
                calls.append(
                    {
                        "frame": np.asarray(frame).copy(),
                        "frame_index": frame_index,
                        "checkpoint_path": checkpoint_path,
                        "confidence_threshold": confidence_threshold,
                        "iou_threshold": iou_threshold,
                        "source_view": source_view,
                        "size_filter": size_filter,
                    }
                )
                return [
                    MolecularDetection(
                        frame_index=frame_index,
                        bbox_xyxy=(1, 1, 3, 3),
                        confidence=0.82,
                        model_name="model-a.pt",
                        checkpoint_path=str(checkpoint_path),
                        source_view=source_view,
                    )
                ]

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [SimpleNamespace(name="model-a.pt", path=checkpoint)],
            yolo_detector=FakeYoloDetector(),
        )
        frames = np.arange(3 * 4 * 4, dtype=np.float32).reshape(3, 4, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
        )
        self.window.set_image_series(series)
        self.window.slider_frame.setValue(1)
        self.window.sp_yolo_confidence.setValue(0.35)
        self.window.sp_yolo_iou.setValue(0.55)
        self.__class__._app.processEvents()

        self.window.btn_yolo_detect_current.click()
        self.__class__._app.processEvents()

        self.assertEqual(len(calls), 1)
        np.testing.assert_array_equal(calls[0]["frame"], frames[1])
        self.assertEqual(calls[0]["frame_index"], 1)
        self.assertEqual(calls[0]["checkpoint_path"], checkpoint)
        self.assertAlmostEqual(calls[0]["confidence_threshold"], 0.35)
        self.assertAlmostEqual(calls[0]["iou_threshold"], 0.55)
        self.assertEqual(calls[0]["source_view"], "raw")
        self.assertIsNotNone(series.molecular_detections)
        current = series.molecular_detections.get_detections(1, source_view="raw")
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0].model_name, "model-a.pt")
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertIn("current 1", self.window.lbl_yolo_status.text())
        self.assertIn("series 1", self.window.lbl_yolo_status.text())
        self.assertIn("model-a.pt", self.window.statusBar().currentMessage())
        self.assertIn("1 detection", self.window.statusBar().currentMessage())
        self.assertIn("frame 2", self.window.statusBar().currentMessage())

    def test_yolo_size_filter_controls_are_optional_and_enable_together(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        self.window.set_image_series(
            MolTrackImageSeries(
                source_path="movie.mpp",
                raw_frames=np.zeros((1, 8, 8), dtype=np.float32),
                metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
            )
        )

        self.assertEqual(self.window.chk_yolo_size_filter.text(), "Enable size filter")
        self.assertFalse(self.window.chk_yolo_size_filter.isChecked())
        self.assertFalse(self.window.sp_yolo_min_area_px2.isEnabled())
        self.assertFalse(self.window.sp_yolo_max_area_px2.isEnabled())
        self.assertFalse(self.window.sp_yolo_max_aspect_ratio.isEnabled())

        self.window.chk_yolo_size_filter.setChecked(True)

        self.assertTrue(self.window.sp_yolo_min_area_px2.isEnabled())
        self.assertTrue(self.window.sp_yolo_max_area_px2.isEnabled())
        self.assertTrue(self.window.sp_yolo_max_aspect_ratio.isEnabled())

    def test_yolo_detect_current_frame_passes_enabled_size_filter(self) -> None:
        calls = []
        checkpoint = Path("model-a.pt")

        class FakeYoloDetector:
            def detect_frame(self, frame, **kwargs):
                calls.append(kwargs)
                return []

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [SimpleNamespace(name="model-a.pt", path=checkpoint)],
            yolo_detector=FakeYoloDetector(),
        )
        self.window.set_image_series(
            MolTrackImageSeries(
                source_path="movie.mpp",
                raw_frames=np.zeros((1, 16, 16), dtype=np.float32),
                metadata=STMSequenceMetadata(pixels_x=16, pixels_y=16),
            )
        )
        self.window.chk_yolo_size_filter.setChecked(True)
        self.window.sp_yolo_min_area_px2.setValue(12.0)
        self.window.sp_yolo_max_area_px2.setValue(80.0)
        self.window.sp_yolo_max_aspect_ratio.setValue(2.5)

        self.window.btn_yolo_detect_current.click()

        self.assertEqual(len(calls), 1)
        size_filter = calls[0]["size_filter"]
        self.assertEqual(size_filter.min_area_px2, 12.0)
        self.assertEqual(size_filter.max_area_px2, 80.0)
        self.assertEqual(size_filter.max_aspect_ratio, 2.5)

    def test_yolo_detect_all_frames_stores_raw_detections_from_worker_thread(self) -> None:
        calls = []
        thread_ids = []
        main_thread_id = int(QThread.currentThreadId())
        checkpoint = Path("model-a.pt")

        class FakeYoloDetector:
            def detect_frame(
                self,
                frame,
                *,
                frame_index,
                checkpoint_path,
                confidence_threshold,
                iou_threshold,
                source_view,
                size_filter=None,
            ):
                thread_ids.append(int(QThread.currentThreadId()))
                calls.append(
                    {
                        "frame": np.asarray(frame).copy(),
                        "frame_index": frame_index,
                        "checkpoint_path": checkpoint_path,
                        "confidence_threshold": confidence_threshold,
                        "iou_threshold": iou_threshold,
                        "source_view": source_view,
                        "size_filter": size_filter,
                    }
                )
                return [
                    MolecularDetection(
                        frame_index=frame_index,
                        bbox_xyxy=(0, 0, 2, 2),
                        confidence=0.8,
                        model_name="model-a.pt",
                        checkpoint_path=str(checkpoint_path),
                        source_view=source_view,
                    )
                ]

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [SimpleNamespace(name="model-a.pt", path=checkpoint)],
            yolo_detector=FakeYoloDetector(),
        )
        frames = np.arange(3 * 4 * 4, dtype=np.float32).reshape(3, 4, 4)
        detections = MolecularDetectionSet(frame_count=3)
        detections.set_detections(
            0,
            [MolecularDetection(frame_index=0, bbox_xyxy=(1, 1, 3, 3), confidence=0.5, source_view="raw")],
            source_view="raw",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(2, 2, 4, 4),
                    confidence=0.6,
                    source_view="expanded_aligned",
                )
            ],
            source_view="expanded_aligned",
            frame_shape=(4, 4),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            active_frame_index=1,
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.sp_yolo_confidence.setValue(0.4)
        self.window.sp_yolo_iou.setValue(0.6)
        self.window.chk_yolo_size_filter.setChecked(True)
        self.window.sp_yolo_min_area_px2.setValue(3.0)
        self.window.sp_yolo_max_area_px2.setValue(9.0)
        self.window.sp_yolo_max_aspect_ratio.setValue(1.5)

        self.window.btn_yolo_detect_all_frames.click()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            self.__class__._app.processEvents()
            if (
                series.molecular_detections is not None
                and series.molecular_detections.detection_count == 4
                and "detections" in self.window.statusBar().currentMessage()
            ):
                break
            time.sleep(0.01)
        else:
            self.fail(
                "Timed out waiting for YOLO all-frames completion. "
                f"count={series.molecular_detections.detection_count}, "
                f"status={self.window.statusBar().currentMessage()!r}, "
                f"calls={calls!r}"
            )

        self.assertEqual([call["frame_index"] for call in calls], [0, 1, 2])
        self.assertTrue(thread_ids)
        self.assertTrue(all(thread_id != main_thread_id for thread_id in thread_ids))
        for frame_index, call in enumerate(calls):
            np.testing.assert_array_equal(call["frame"], frames[frame_index])
            self.assertEqual(call["checkpoint_path"], checkpoint)
            self.assertAlmostEqual(call["confidence_threshold"], 0.4)
            self.assertAlmostEqual(call["iou_threshold"], 0.6)
            self.assertEqual(call["source_view"], "raw")
            self.assertEqual(call["size_filter"].min_area_px2, 3.0)
            self.assertEqual(call["size_filter"].max_area_px2, 9.0)
            self.assertEqual(call["size_filter"].max_aspect_ratio, 1.5)
            current = series.molecular_detections.get_detections(frame_index, source_view="raw")
            self.assertEqual(len(current), 1)
            self.assertEqual(current[0].model_name, "model-a.pt")
        self.assertEqual(len(series.molecular_detections.get_detections(0, source_view="expanded_aligned")), 1)
        self.assertEqual(series.active_frame_index, 1)
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertIn("current 1", self.window.lbl_yolo_status.text())
        self.assertIn("series 4", self.window.lbl_yolo_status.text())
        self.assertIn("model-a.pt", self.window.statusBar().currentMessage())
        self.assertIn("3 detections", self.window.statusBar().currentMessage())
        self.assertIn("3 frames", self.window.statusBar().currentMessage())

    def test_yolo_detect_range_uses_current_and_inclusive_end_frame(self) -> None:
        calls = []
        checkpoint = Path("model-a.pt")

        class FakeYoloDetector:
            def detect_frame(
                self,
                frame,
                *,
                frame_index,
                checkpoint_path,
                confidence_threshold,
                iou_threshold,
                source_view,
                size_filter=None,
            ):
                calls.append((frame_index, np.asarray(frame).copy()))
                return [
                    MolecularDetection(
                        frame_index=frame_index,
                        bbox_xyxy=(0, 0, 2, 2),
                        confidence=0.8,
                        source_view=source_view,
                    )
                ]

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [SimpleNamespace(name="model-a.pt", path=checkpoint)],
            yolo_detector=FakeYoloDetector(),
        )
        frames = np.arange(4 * 4 * 4, dtype=np.float32).reshape(4, 4, 4)
        detections = MolecularDetectionSet(frame_count=4)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1, 1, 3, 3),
                    confidence=0.5,
                    source_view="raw",
                )
            ],
            source_view="raw",
            frame_shape=(4, 4),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            active_frame_index=1,
            molecular_detections=detections,
        )
        self.window.set_image_series(series)

        self.assertEqual(self.window.sp_yolo_range_end_frame.minimum(), 2)
        self.assertEqual(self.window.sp_yolo_range_end_frame.maximum(), 4)
        self.window.sp_yolo_range_end_frame.setValue(4)
        self.window.btn_yolo_detect_range.click()
        self.process_events_until(
            lambda: (
                self.window._yolo_detection_thread is None
                and series.molecular_detections.detection_count == 4
                and "3 detections" in self.window.statusBar().currentMessage()
            )
        )

        self.assertEqual([frame_index for frame_index, _frame in calls], [1, 2, 3])
        for frame_index, frame in calls:
            np.testing.assert_array_equal(frame, frames[frame_index])
        self.assertEqual(len(series.molecular_detections.get_detections(0, source_view="raw")), 1)
        self.assertEqual(series.active_frame_index, 1)
        self.assertIn("3 detections", self.window.statusBar().currentMessage())
        self.assertIn("3 frames", self.window.statusBar().currentMessage())

    def test_yolo_detect_all_frames_shows_progress_dialog_while_worker_runs(self) -> None:
        events = []

        class FakeProgressDialog:
            def __init__(self, label_text, cancel_button_text, minimum, maximum, parent):
                events.append(("init", label_text, cancel_button_text, minimum, maximum, parent))

            def setWindowTitle(self, title):
                events.append(("title", title))

            def setWindowModality(self, modality):
                events.append(("modality", modality))

            def setCancelButton(self, button):
                events.append(("cancel_button", button))

            def setMinimumDuration(self, duration_ms):
                events.append(("minimum_duration", duration_ms))

            def setAutoClose(self, enabled):
                events.append(("auto_close", enabled))

            def setAutoReset(self, enabled):
                events.append(("auto_reset", enabled))

            def setValue(self, value):
                events.append(("value", value))

            def setLabelText(self, label_text):
                events.append(("label", label_text))

            def show(self):
                events.append("show")

            def close(self):
                events.append("close")

        class SlowYoloDetector:
            def detect_frame(
                self,
                frame,
                *,
                frame_index,
                checkpoint_path,
                confidence_threshold,
                iou_threshold,
                source_view,
            ):
                time.sleep(0.05)
                return []

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [SimpleNamespace(name="model-a.pt", path=Path("model-a.pt"))],
            yolo_detector=SlowYoloDetector(),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
        )
        self.window.set_image_series(series)

        with patch("moltrack.ui.main_window.QProgressDialog", FakeProgressDialog, create=True):
            self.window.btn_yolo_detect_all_frames.click()
            self.__class__._app.processEvents()

            self.assertIn("show", events)
            self.assertFalse(self.window.btn_yolo_detect_all_frames.isEnabled())
            self.assertFalse(self.window.action_open_stm.isEnabled())

            self.process_events_until(
                lambda: any(
                    isinstance(event, tuple) and event[0] == "label" and "frame 1 / 2" in event[1]
                    for event in events
                ),
                timeout_s=1.0,
            )
            self.process_events_until(
                lambda: "0 detections" in self.window.statusBar().currentMessage()
                and self.window.btn_yolo_detect_all_frames.isEnabled(),
                timeout_s=2.0,
            )

        self.assertIn(("title", "YOLO Detection"), events)
        self.assertIn(("value", 0), events)
        self.assertTrue(any(isinstance(event, tuple) and event == ("value", 1) for event in events))
        self.assertIn("close", events)
        self.assertTrue(self.window.action_open_stm.isEnabled())

    def test_yolo_detect_all_frames_uses_raw_inference_and_transforms_results_to_expanded_view(self) -> None:
        calls = []
        checkpoint = Path("expanded-model.pt")
        expanded_frames = (np.arange(2 * 5 * 6, dtype=np.float32).reshape(2, 5, 6) + 100.0)

        class FakeYoloDetector:
            def detect_frame(
                self,
                frame,
                *,
                frame_index,
                checkpoint_path,
                confidence_threshold,
                iou_threshold,
                source_view,
            ):
                calls.append((np.asarray(frame).copy(), frame_index, checkpoint_path, source_view))
                return [
                    MolecularDetection(
                        frame_index=frame_index,
                        bbox_xyxy=(1, 1, 3, 3),
                        confidence=0.7,
                        model_name="expanded-model.pt",
                        checkpoint_path=str(checkpoint_path),
                        source_view=source_view,
                    )
                ]

        def fake_expanded_builder(series):
            expanded_stack = SimpleNamespace(
                frames=expanded_frames,
                metadata=STMSequenceMetadata(pixels_x=6, pixels_y=5),
                padding_ltrb=(1, 1, 1, 2),
                frame_origins_xy=np.asarray(((1.0, 1.0), (2.5, 0.5)), dtype=np.float64),
            )
            series.expanded_aligned_stack = expanded_stack
            return expanded_stack

        self.window = MolTrackMainWindow(
            expanded_aligned_builder=fake_expanded_builder,
            yolo_model_discovery=lambda: [SimpleNamespace(name="expanded-model.pt", path=checkpoint)],
            yolo_detector=FakeYoloDetector(),
        )
        raw_detections = MolecularDetectionSet(frame_count=2)
        raw_detections.set_detections(
            0,
            [MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9, source_view="raw")],
            source_view="raw",
            frame_shape=(4, 4),
        )
        settings = MolTrackRegistrationSettings()
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            registration_results=MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    frame_index: MolTrackRegistrationFrameResult(
                        frame_index=frame_index,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                    )
                    for frame_index in range(2)
                },
            ),
            molecular_detections=raw_detections,
        )
        self.window.set_image_series(series)
        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.__class__._app.processEvents()

        self.window.btn_yolo_detect_all_frames.click()
        self.process_events_until(
            lambda: series.molecular_detections.detection_count == 3
            and "2 detections" in self.window.statusBar().currentMessage(),
            timeout_s=2.0,
        )

        self.assertEqual(len(calls), 2)
        for frame_index, call in enumerate(calls):
            np.testing.assert_array_equal(call[0], series.raw_frames[frame_index])
            self.assertEqual(call[1], frame_index)
            self.assertEqual(call[2], checkpoint)
            self.assertEqual(call[3], "raw")
            expanded = series.molecular_detections.get_detections(frame_index, source_view="expanded_aligned")
            self.assertEqual(len(expanded), 1)
        self.assertEqual(
            series.molecular_detections.get_detections(0, source_view="expanded_aligned")[0].bbox_xyxy,
            (2.0, 2.0, 4.0, 4.0),
        )
        self.assertEqual(
            series.molecular_detections.get_detections(1, source_view="expanded_aligned")[0].bbox_xyxy,
            (3.5, 1.5, 5.5, 3.5),
        )
        self.assertEqual(len(series.molecular_detections.get_detections(0, source_view="raw")), 1)
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, expanded_frames[0])
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertIn("current 1", self.window.lbl_yolo_status.text())
        self.assertIn("series 3", self.window.lbl_yolo_status.text())

    def test_yolo_clear_current_removes_only_active_frame_and_view_detections(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4)
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9, source_view="raw")],
            source_view="raw",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1, 1, 3, 3),
                    confidence=0.8,
                    source_view="expanded_aligned",
                )
            ],
            source_view="expanded_aligned",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            1,
            [MolecularDetection(frame_index=1, bbox_xyxy=(2, 2, 4, 4), confidence=0.7, source_view="raw")],
            source_view="raw",
            frame_shape=(4, 4),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)

        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertTrue(self.window.btn_yolo_clear_current.isEnabled())

        self.window.btn_yolo_clear_current.click()
        self.__class__._app.processEvents()

        self.assertEqual(series.molecular_detections.get_detections(0, source_view="raw"), [])
        self.assertEqual(len(series.molecular_detections.get_detections(0, source_view="expanded_aligned")), 1)
        self.assertEqual(len(series.molecular_detections.get_detections(1, source_view="raw")), 1)
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 0)
        self.assertFalse(self.window.btn_yolo_clear_current.isEnabled())
        self.assertIn("current 0", self.window.lbl_yolo_status.text())
        self.assertIn("series 2", self.window.lbl_yolo_status.text())

    def test_bbox_resize_increase_updates_raw_view_detections_and_viewer(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.arange(2 * 5 * 5, dtype=np.float32).reshape(2, 5, 5)
        detections = MolecularDetectionSet(frame_count=2)
        raw_frame_0 = MolecularDetection(frame_index=0, bbox_xyxy=(1, 1, 3, 3), confidence=0.9, source_view="raw")
        raw_frame_1 = MolecularDetection(frame_index=1, bbox_xyxy=(0, 0, 2, 2), confidence=0.7, source_view="raw")
        expanded_frame_0 = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(1, 1, 3, 3),
            confidence=0.8,
            source_view="expanded_aligned",
        )
        detections.set_detections(0, [raw_frame_0], source_view="raw", frame_shape=(5, 5))
        detections.set_detections(1, [raw_frame_1], source_view="raw", frame_shape=(5, 5))
        detections.set_detections(0, [expanded_frame_0], source_view="expanded_aligned", frame_shape=(5, 5))
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)

        self.assertTrue(self.window.btn_bbox_increase.isEnabled())
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.window.sp_bbox_resize_margin.setValue(1.0)

        self.window.btn_bbox_increase.click()
        self.__class__._app.processEvents()

        self.assertEqual(raw_frame_0.bbox_xyxy, (0.0, 0.0, 4.0, 4.0))
        self.assertEqual(raw_frame_1.bbox_xyxy, (0.0, 0.0, 4.0, 4.0))
        self.assertEqual(expanded_frame_0.bbox_xyxy, (1.0, 1.0, 3.0, 3.0))
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertIn("current 1", self.window.lbl_yolo_status.text())
        self.assertIn("series 3", self.window.lbl_yolo_status.text())
        self.assertIn("Resized 2", self.window.statusBar().currentMessage())

    def test_bbox_resize_decrease_and_reset_restore_original_raw_bbox(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.arange(25, dtype=np.float32).reshape(1, 5, 5)
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(0, 0, 5, 5),
            original_bbox_xyxy=(1, 1, 4, 4),
            confidence=0.9,
            source_view="raw",
        )
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(0, [detection], source_view="raw", frame_shape=(5, 5))
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.sp_bbox_resize_margin.setValue(1.0)

        self.window.btn_bbox_decrease.click()
        self.__class__._app.processEvents()

        self.assertEqual(detection.bbox_xyxy, (1.0, 1.0, 4.0, 4.0))
        self.assertEqual(detection.original_bbox_xyxy, (1.0, 1.0, 4.0, 4.0))
        self.assertIn("Resized 1", self.window.statusBar().currentMessage())

        self.window.btn_bbox_increase.click()
        self.__class__._app.processEvents()

        self.assertEqual(detection.bbox_xyxy, (0.0, 0.0, 5.0, 5.0))

        self.window.btn_bbox_reset.click()
        self.__class__._app.processEvents()

        self.assertEqual(detection.bbox_xyxy, (1.0, 1.0, 4.0, 4.0))
        self.assertIn("Reset 1", self.window.statusBar().currentMessage())
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)

    def test_bbox_resize_uses_expanded_aligned_view_and_frame_shape(self) -> None:
        expanded_frames = np.arange(1 * 6 * 6, dtype=np.float32).reshape(1, 6, 6)

        def fake_expanded_builder(series):
            expanded_stack = SimpleNamespace(
                frames=expanded_frames,
                metadata=STMSequenceMetadata(pixels_x=6, pixels_y=6),
                padding_ltrb=(1, 1, 1, 1),
                frame_origins_xy=np.zeros((series.frame_count, 2), dtype=np.float64),
            )
            series.expanded_aligned_stack = expanded_stack
            return expanded_stack

        self.window = MolTrackMainWindow(
            expanded_aligned_builder=fake_expanded_builder,
            yolo_model_discovery=lambda: [],
        )
        detections = MolecularDetectionSet(frame_count=1)
        raw_detection = MolecularDetection(frame_index=0, bbox_xyxy=(1, 1, 3, 3), confidence=0.9, source_view="raw")
        expanded_detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(3, 3, 5, 5),
            confidence=0.8,
            source_view="expanded_aligned",
        )
        detections.set_detections(0, [raw_detection], source_view="raw", frame_shape=(4, 4))
        detections.set_detections(0, [expanded_detection], source_view="expanded_aligned", frame_shape=(6, 6))
        settings = MolTrackRegistrationSettings()
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(1 * 4 * 4, dtype=np.float32).reshape(1, 4, 4),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            registration_results=MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    0: MolTrackRegistrationFrameResult(
                        frame_index=0,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                    )
                },
            ),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.__class__._app.processEvents()
        self.window.sp_bbox_resize_margin.setValue(1.0)

        self.window.btn_bbox_increase.click()
        self.__class__._app.processEvents()

        self.assertEqual(expanded_detection.bbox_xyxy, (2.0, 2.0, 6.0, 6.0))
        self.assertEqual(raw_detection.bbox_xyxy, (1.0, 1.0, 3.0, 3.0))
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, expanded_frames[0])
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertIn("expanded aligned", self.window.statusBar().currentMessage())

    def test_remove_current_frame_after_yolo_clears_detections_and_requires_rerun(self) -> None:
        checkpoint = Path("model-a.pt")

        class FakeYoloDetector:
            def detect_frame(
                self,
                frame,
                *,
                frame_index,
                checkpoint_path,
                confidence_threshold,
                iou_threshold,
                source_view,
            ):
                return [
                    MolecularDetection(
                        frame_index=frame_index,
                        bbox_xyxy=(0, 0, 2, 2),
                        confidence=0.8,
                        model_name="model-a.pt",
                        checkpoint_path=str(checkpoint_path),
                        source_view=source_view,
                    )
                ]

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [SimpleNamespace(name="model-a.pt", path=checkpoint)],
            yolo_detector=FakeYoloDetector(),
        )
        frames = np.arange(3 * 4 * 4, dtype=np.float32).reshape(3, 4, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
        )
        self.window.set_image_series(series)
        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()

        self.window.btn_yolo_detect_current.click()
        self.__class__._app.processEvents()

        self.assertIsNotNone(series.molecular_detections)
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertIn("series 1", self.window.lbl_yolo_status.text())
        self.window.sp_bbox_resize_margin.setValue(1.0)

        self.window.btn_bbox_increase.click()
        self.__class__._app.processEvents()

        resized_detection = series.molecular_detections.get_detections(1, source_view="raw")[0]
        self.assertEqual(resized_detection.bbox_xyxy, (0.0, 0.0, 4.0, 4.0))
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)

        self.window.btn_remove_current_frame.click()
        self.__class__._app.processEvents()

        self.assertIsNone(series.molecular_detections)
        self.assertEqual(series.frame_count, 2)
        self.assertEqual(series.active_frame_index, 1)
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 0)
        self.assertIn("current 0", self.window.lbl_yolo_status.text())
        self.assertIn("series 0", self.window.lbl_yolo_status.text())
        self.assertTrue(self.window.btn_yolo_detect_current.isEnabled())
        self.assertFalse(self.window.btn_bbox_increase.isEnabled())

    def test_yolo_status_tracks_active_registration_view(self) -> None:
        expanded_frames = np.arange(2 * 5 * 6, dtype=np.float32).reshape(2, 5, 6)

        def fake_expanded_builder(series):
            expanded_stack = SimpleNamespace(
                frames=expanded_frames,
                metadata=STMSequenceMetadata(pixels_x=6, pixels_y=5),
                padding_ltrb=(1, 1, 1, 2),
                frame_origins_xy=np.zeros((series.frame_count, 2), dtype=np.float64),
            )
            series.expanded_aligned_stack = expanded_stack
            return expanded_stack

        self.window = MolTrackMainWindow(
            expanded_aligned_builder=fake_expanded_builder,
            yolo_model_discovery=lambda: [],
        )
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9, source_view="raw")],
            source_view="raw",
            frame_shape=(4, 4),
        )
        settings = MolTrackRegistrationSettings()
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            registration_results=MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    frame_index: MolTrackRegistrationFrameResult(
                        frame_index=frame_index,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                    )
                    for frame_index in range(2)
                },
            ),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)

        self.assertIn("current 1", self.window.lbl_yolo_status.text())
        self.assertTrue(self.window.btn_yolo_clear_current.isEnabled())
        self.assertTrue(self.window.btn_bbox_increase.isEnabled())

        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.__class__._app.processEvents()

        self.assertIn("current 0", self.window.lbl_yolo_status.text())
        self.assertFalse(self.window.btn_yolo_clear_current.isEnabled())
        self.assertFalse(self.window.btn_bbox_increase.isEnabled())
        self.assertIn("expanded aligned 0", self.window.lbl_bbox_resize_status.text())

        self.window.cmb_registration_view_mode.setCurrentText("Show raw")
        self.__class__._app.processEvents()

        self.assertIn("current 1", self.window.lbl_yolo_status.text())
        self.assertTrue(self.window.btn_yolo_clear_current.isEnabled())
        self.assertTrue(self.window.btn_bbox_increase.isEnabled())

    def test_yolo_detect_current_frame_uses_raw_inference_and_transforms_result_to_expanded_view(self) -> None:
        calls = []
        checkpoint = Path("expanded-model.pt")
        expanded_frames = (np.arange(2 * 5 * 6, dtype=np.float32).reshape(2, 5, 6) + 100.0)

        class FakeYoloDetector:
            def detect_frame(
                self,
                frame,
                *,
                frame_index,
                checkpoint_path,
                confidence_threshold,
                iou_threshold,
                source_view,
            ):
                calls.append((np.asarray(frame).copy(), frame_index, checkpoint_path, source_view))
                return [
                    MolecularDetection(
                        frame_index=frame_index,
                        bbox_xyxy=(1, 1, 3, 3),
                        confidence=0.75,
                        model_name="expanded-model.pt",
                        checkpoint_path=str(checkpoint_path),
                        source_view=source_view,
                    )
                ]

        def fake_expanded_builder(series):
            expanded_stack = SimpleNamespace(
                frames=expanded_frames,
                metadata=STMSequenceMetadata(pixels_x=6, pixels_y=5),
                padding_ltrb=(1, 1, 1, 2),
                frame_origins_xy=np.asarray(((1.0, 1.0), (2.5, 1.25)), dtype=np.float64),
            )
            series.expanded_aligned_stack = expanded_stack
            return expanded_stack

        self.window = MolTrackMainWindow(
            expanded_aligned_builder=fake_expanded_builder,
            yolo_model_discovery=lambda: [SimpleNamespace(name="expanded-model.pt", path=checkpoint)],
            yolo_detector=FakeYoloDetector(),
        )
        raw_frames = np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4)
        raw_detections = MolecularDetectionSet(frame_count=2)
        raw_detections.set_detections(
            1,
            [MolecularDetection(frame_index=1, bbox_xyxy=(0, 0, 2, 2), confidence=0.9, source_view="raw")],
            source_view="raw",
            frame_shape=(4, 4),
        )
        settings = MolTrackRegistrationSettings()
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=raw_frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            registration_results=MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    frame_index: MolTrackRegistrationFrameResult(
                        frame_index=frame_index,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                    )
                    for frame_index in range(2)
                },
            ),
            molecular_detections=raw_detections,
        )
        self.window.set_image_series(series)
        self.window.slider_frame.setValue(1)
        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.__class__._app.processEvents()

        self.window.btn_yolo_detect_current.click()
        self.__class__._app.processEvents()

        self.assertEqual(len(calls), 1)
        np.testing.assert_array_equal(calls[0][0], raw_frames[1])
        self.assertEqual(calls[0][1], 1)
        self.assertEqual(calls[0][2], checkpoint)
        self.assertEqual(calls[0][3], "raw")
        self.assertEqual(len(series.molecular_detections.get_detections(1, source_view="raw")), 1)
        expanded = series.molecular_detections.get_detections(1, source_view="expanded_aligned")
        self.assertEqual(len(expanded), 1)
        self.assertEqual(expanded[0].bbox_xyxy, (3.5, 2.25, 5.5, 4.25))
        self.assertEqual(expanded[0].original_bbox_xyxy, (3.5, 2.25, 5.5, 4.25))
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, expanded_frames[1])
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertIn("current 1", self.window.lbl_yolo_status.text())
        self.assertIn("series 2", self.window.lbl_yolo_status.text())

    def test_yolo_detect_current_frame_reports_inference_errors(self) -> None:
        class FailingYoloDetector:
            def detect_frame(self, *args, **kwargs):
                raise RuntimeError("GPU inference failed")

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [SimpleNamespace(name="model-a.pt", path=Path("model-a.pt"))],
            yolo_detector=FailingYoloDetector(),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
        )
        self.window.set_image_series(series)

        with patch.object(QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok) as critical:
            self.window.btn_yolo_detect_current.click()
            self.__class__._app.processEvents()

        critical.assert_called_once()
        _parent, title, message = critical.call_args.args
        self.assertEqual(title, "YOLO detection error")
        self.assertIn("GPU inference failed", message)
        self.assertIsNone(series.molecular_detections)
        self.assertIn("YOLO detection failed", self.window.statusBar().currentMessage())

    def test_yolo_detect_all_frames_reports_inference_errors_without_partial_results(self) -> None:
        class FailingYoloDetector:
            def detect_frame(
                self,
                frame,
                *,
                frame_index,
                checkpoint_path,
                confidence_threshold,
                iou_threshold,
                source_view,
            ):
                if frame_index == 1:
                    raise RuntimeError("GPU inference failed on frame 2")
                return [
                    MolecularDetection(
                        frame_index=frame_index,
                        bbox_xyxy=(0, 0, 2, 2),
                        confidence=0.8,
                        model_name="model-a.pt",
                        checkpoint_path=str(checkpoint_path),
                        source_view=source_view,
                    )
                ]

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [SimpleNamespace(name="model-a.pt", path=Path("model-a.pt"))],
            yolo_detector=FailingYoloDetector(),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(3 * 4 * 4, dtype=np.float32).reshape(3, 4, 4),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
        )
        self.window.set_image_series(series)

        with patch.object(QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok) as critical:
            self.window.btn_yolo_detect_all_frames.click()
            self.process_events_until(
                lambda: critical.called and "YOLO detection failed" in self.window.statusBar().currentMessage(),
                timeout_s=2.0,
            )

        critical.assert_called_once()
        _parent, title, message = critical.call_args.args
        self.assertEqual(title, "YOLO detection error")
        self.assertIn("GPU inference failed on frame 2", message)
        self.assertIsNone(series.molecular_detections)
        self.assertTrue(self.window.btn_yolo_detect_all_frames.isEnabled())
        self.assertIn("YOLO detection failed", self.window.statusBar().currentMessage())

    def test_remove_current_frame_button_deletes_active_frame_from_working_series(self) -> None:
        self.window = MolTrackMainWindow()
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)
        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()

        self.window.btn_remove_current_frame.click()
        self.__class__._app.processEvents()

        self.assertEqual(series.frame_count, 2)
        self.assertEqual(series.active_frame_index, 1)
        np.testing.assert_array_equal(series.raw_frames, frames[[0, 2]])
        self.assertEqual(self.window.slider_frame.maximum(), 1)
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 2 / 2")
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, frames[2])
        self.assertIn("Frames: 2", self.window.metadata_panel.metadata_text())

    def test_remove_current_frame_button_disables_when_one_frame_remains(self) -> None:
        self.window = MolTrackMainWindow()
        frames = np.arange(16, dtype=np.float32).reshape(2, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)

        self.window.btn_remove_current_frame.click()
        self.__class__._app.processEvents()

        self.assertEqual(series.frame_count, 1)
        self.assertFalse(self.window.btn_remove_current_frame.isEnabled())
        self.assertEqual(self.window.slider_frame.maximum(), 0)
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 1 / 1")

    def test_run_registration_button_registers_current_working_series(self) -> None:
        calls = []

        def fake_registration_runner(series, *, settings):
            calls.append((series.raw_frames.copy(), settings.backend))
            result_set = MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    0: MolTrackRegistrationFrameResult(
                        frame_index=0,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                        quality_score=1.0,
                    ),
                    1: MolTrackRegistrationFrameResult(
                        frame_index=1,
                        shift_xy=(1.25, -0.5),
                        method="phase_correlation",
                        quality_score=0.8,
                    ),
                },
            )
            series.registration_results = result_set
            return result_set

        self.window = MolTrackMainWindow(registration_runner=fake_registration_runner)
        frames = np.arange(16, dtype=np.float32).reshape(2, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)

        self.window.btn_run_registration.click()
        self.process_events_until(lambda: series.registration_results is not None and self.window.btn_run_registration.isEnabled())

        self.assertEqual(len(calls), 1)
        passed_frames, backend = calls[0]
        np.testing.assert_array_equal(passed_frames, frames)
        self.assertEqual(backend, "phase_correlation")
        self.assertIsNotNone(series.registration_results)
        self.assertEqual(series.registration_results.result_count, 2)
        self.assertIn("Registered 2 frames", self.window.lbl_registration_status.text())
        self.assertIn("Registration finished", self.window.statusBar().currentMessage())

    def test_can_select_and_run_optical_flow_median_registration(self) -> None:
        calls = []

        def fake_registration_runner(series, *, settings):
            calls.append(settings.backend)
            result_set = MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    0: MolTrackRegistrationFrameResult(
                        frame_index=0,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                        quality_score=1.0,
                    ),
                    1: MolTrackRegistrationFrameResult(
                        frame_index=1,
                        shift_xy=(0.5, -1.5),
                        method="optical_flow_median",
                        quality_score=0.8,
                    ),
                },
            )
            series.registration_results = result_set
            return result_set

        self.window = MolTrackMainWindow(registration_runner=fake_registration_runner)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(16, dtype=np.float32).reshape(2, 2, 4),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)

        self.assertGreaterEqual(self.window.cmb_registration_backend.findText("optical_flow_median"), 0)
        self.window.cmb_registration_backend.setCurrentText("optical_flow_median")
        self.window.btn_run_registration.click()
        self.process_events_until(lambda: series.registration_results is not None and self.window.btn_run_registration.isEnabled())

        self.assertEqual(calls, ["optical_flow_median"])
        self.assertEqual(series.registration_results.settings.backend, "optical_flow_median")
        self.assertIn("Registered 2 frames with optical_flow_median", self.window.lbl_registration_status.text())

    def test_run_registration_uses_worker_thread_and_shows_busy_dialog_while_running(self) -> None:
        events = []
        main_thread_id = int(QThread.currentThreadId())

        class FakeProgressDialog:
            def __init__(self, label_text, cancel_button_text, minimum, maximum, parent):
                events.append(("dialog_init", label_text, cancel_button_text, minimum, maximum, parent))

            def setWindowTitle(self, title):
                events.append(("title", title))

            def setWindowModality(self, modality):
                events.append(("modality", modality))

            def setCancelButton(self, button):
                events.append(("cancel_button", button))

            def setMinimumDuration(self, duration_ms):
                events.append(("minimum_duration", duration_ms))

            def setAutoClose(self, enabled):
                events.append(("auto_close", enabled))

            def setAutoReset(self, enabled):
                events.append(("auto_reset", enabled))

            def show(self):
                events.append("show")

            def close(self):
                events.append("close")

        def fake_registration_runner(series, *, settings):
            events.append(("runner_thread", int(QThread.currentThreadId())))
            result_set = MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    frame_index: MolTrackRegistrationFrameResult(
                        frame_index=frame_index,
                        shift_xy=(0.0, 0.0),
                        method="phase_correlation",
                        quality_score=1.0,
                    )
                    for frame_index in range(series.frame_count)
                },
            )
            series.registration_results = result_set
            return result_set

        self.window = MolTrackMainWindow(registration_runner=fake_registration_runner)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(16, dtype=np.float32).reshape(2, 2, 4),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)

        with patch("moltrack.ui.main_window.QProgressDialog", FakeProgressDialog, create=True):
            self.window.btn_run_registration.click()
            self.assertIn("show", events)
            self.assertFalse(self.window.btn_run_registration.isEnabled())
            self.assertFalse(self.window.action_open_stm.isEnabled())
            self.assertFalse(self.window.action_open_stm_reverse.isEnabled())
            self.assertFalse(self.window.action_open_state.isEnabled())
            self.assertFalse(self.window.action_save_state.isEnabled())
            self.assertFalse(self.window.action_save_state_as.isEnabled())
            self.process_events_until(lambda: series.registration_results is not None and self.window.btn_run_registration.isEnabled())

        self.assertIn("show", events)
        self.assertIn("close", events)
        runner_events = [event for event in events if isinstance(event, tuple) and event[0] == "runner_thread"]
        self.assertEqual(len(runner_events), 1)
        self.assertNotEqual(runner_events[0][1], main_thread_id)
        self.assertLess(events.index("show"), events.index(runner_events[0]))
        self.assertLess(events.index(runner_events[0]), events.index("close"))
        self.assertTrue(self.window.btn_run_registration.isEnabled())
        self.assertTrue(self.window.action_open_stm.isEnabled())
        self.assertTrue(self.window.action_open_stm_reverse.isEnabled())
        self.assertTrue(self.window.action_open_state.isEnabled())
        self.assertTrue(self.window.action_save_state.isEnabled())
        self.assertTrue(self.window.action_save_state_as.isEnabled())
        self.assertIn("Registered 2 frames", self.window.lbl_registration_status.text())

    def test_run_registration_after_frame_removal_uses_shortened_working_series(self) -> None:
        calls = []

        def fake_registration_runner(series, *, settings):
            calls.append(series.raw_frames.copy())
            result_set = MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    frame_index: MolTrackRegistrationFrameResult(
                        frame_index=frame_index,
                        shift_xy=(float(frame_index), -float(frame_index)),
                        method="phase_correlation",
                        quality_score=0.8,
                    )
                    for frame_index in range(series.frame_count)
                },
            )
            series.registration_results = result_set
            return result_set

        self.window = MolTrackMainWindow(registration_runner=fake_registration_runner)
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)
        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()

        self.window.btn_remove_current_frame.click()
        self.window.btn_run_registration.click()
        self.process_events_until(lambda: series.registration_results is not None and self.window.btn_run_registration.isEnabled())

        self.assertEqual(len(calls), 1)
        np.testing.assert_array_equal(calls[0], frames[[0, 2]])
        self.assertEqual(series.registration_results.result_count, 2)
        self.assertIn("Registered 2 frames", self.window.lbl_registration_status.text())

    def test_registration_view_mode_switches_between_raw_and_expanded_aligned_frames(self) -> None:
        expanded_frames = (np.arange(2 * 3 * 5, dtype=np.float32).reshape(2, 3, 5) + 1000.0)

        def fake_registration_runner(series, *, settings):
            result_set = MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    0: MolTrackRegistrationFrameResult(
                        frame_index=0,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                        quality_score=1.0,
                    ),
                    1: MolTrackRegistrationFrameResult(
                        frame_index=1,
                        shift_xy=(2.0, -1.0),
                        method="phase_correlation",
                        quality_score=0.8,
                    ),
                },
            )
            series.registration_results = result_set
            return result_set

        def fake_expanded_builder(series):
            expanded_stack = SimpleNamespace(
                frames=expanded_frames,
                metadata=STMSequenceMetadata(pixels_x=5, pixels_y=3),
                padding_ltrb=(0, 1, 1, 0),
                frame_origins_xy=np.asarray([[0.0, 1.0], [2.0, 0.0]], dtype=np.float64),
            )
            series.expanded_aligned_stack = expanded_stack
            return expanded_stack

        self.window = MolTrackMainWindow(
            registration_runner=fake_registration_runner,
            expanded_aligned_builder=fake_expanded_builder,
        )
        frames = np.arange(16, dtype=np.float32).reshape(2, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)

        self.window.btn_run_registration.click()
        self.process_events_until(lambda: series.registration_results is not None and self.window.btn_run_registration.isEnabled())
        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.__class__._app.processEvents()

        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, expanded_frames[0])
        self.assertIn("Expanded aligned", self.window.viewer.lbl_title.text())

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()

        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, expanded_frames[1])

        self.window.cmb_registration_view_mode.setCurrentText("Show raw")
        self.__class__._app.processEvents()

        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, frames[1])
        self.assertNotIn("Expanded aligned", self.window.viewer.lbl_title.text())

    def test_remove_current_frame_disables_expanded_aligned_view_until_registration_reruns(self) -> None:
        def fake_registration_runner(series, *, settings):
            result_set = MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    frame_index: MolTrackRegistrationFrameResult(
                        frame_index=frame_index,
                        shift_xy=(float(frame_index), 0.0),
                        method="phase_correlation",
                        quality_score=0.8,
                    )
                    for frame_index in range(series.frame_count)
                },
            )
            series.registration_results = result_set
            return result_set

        def fake_expanded_builder(series):
            expanded_stack = SimpleNamespace(
                frames=np.full((series.frame_count, 3, 5), 42.0, dtype=np.float32),
                metadata=STMSequenceMetadata(pixels_x=5, pixels_y=3),
                padding_ltrb=(0, 0, 1, 1),
                frame_origins_xy=np.zeros((series.frame_count, 2), dtype=np.float64),
            )
            series.expanded_aligned_stack = expanded_stack
            return expanded_stack

        self.window = MolTrackMainWindow(
            registration_runner=fake_registration_runner,
            expanded_aligned_builder=fake_expanded_builder,
        )
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)
        self.window.btn_run_registration.click()
        self.process_events_until(lambda: series.registration_results is not None and self.window.btn_run_registration.isEnabled())
        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.__class__._app.processEvents()

        self.window.btn_remove_current_frame.click()
        self.__class__._app.processEvents()

        self.assertIsNone(series.registration_results)
        self.assertIsNone(series.expanded_aligned_stack)
        self.assertEqual(self.window.cmb_registration_view_mode.currentText(), "Show raw")
        self.assertFalse(self.window.cmb_registration_view_mode.isEnabled())
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, frames[1])

    def test_run_registration_reports_error_when_series_has_too_few_frames(self) -> None:
        self.window = MolTrackMainWindow()
        series = MolTrackImageSeries(
            source_path="single.mpp",
            raw_frames=np.zeros((1, 2, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)

        with patch.object(QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok) as critical:
            self.window.btn_run_registration.click()
            self.process_events_until(lambda: critical.called)

        critical.assert_called_once()
        _parent, title, message = critical.call_args.args
        self.assertEqual(title, "Registration failed")
        self.assertIn("at least two frames", message)
        self.assertTrue(self.window.btn_run_registration.isEnabled())
        self.assertIn("Registration failed", self.window.lbl_registration_status.text())
        self.assertIn("Registration failed", self.window.statusBar().currentMessage())

    def test_open_stm_source_uses_loader_and_displays_loaded_series(self) -> None:
        frames = np.zeros((2, 3, 4), dtype=np.float32)
        metadata = STMSequenceMetadata(pixels_x=4, pixels_y=3)
        calls = []

        def fake_loader(source_path, *, reverse_frame_order=False):
            calls.append((source_path, reverse_frame_order))
            return MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=frames,
                metadata=metadata,
                reverse_frame_order=reverse_frame_order,
            )

        self.window = MolTrackMainWindow(series_loader=fake_loader)

        self.window.open_stm_source("movie.mpp", reverse_frame_order=True)

        self.assertEqual(calls, [("movie.mpp", True)])
        self.assertTrue(self.window.slider_frame.isEnabled())
        self.assertEqual(self.window.slider_frame.maximum(), 1)
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 1 / 2")

    def test_setting_series_updates_metadata_summary(self) -> None:
        self.window = MolTrackMainWindow()
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((3, 2, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=4,
                pixels_y=2,
                size_nm_x=8.0,
                size_nm_y=1.0,
                image_type="Topo",
            ),
        )

        self.window.set_image_series(series)

        metadata_text = self.window.metadata_panel.metadata_text()
        self.assertIn("Source: movie.mpp", metadata_text)
        self.assertIn("Frames: 3", metadata_text)
        self.assertIn("Active frame: 1 / 3", metadata_text)
        self.assertIn("Shape: 4x2 px", metadata_text)
        self.assertIn("Physical size: 8 nm x 1 nm", metadata_text)
        self.assertIn("Pixel size: 2 nm/px x 0.5 nm/px", metadata_text)
        self.assertIn("Channel: Topo", metadata_text)

        self.window.slider_frame.setValue(2)
        self.__class__._app.processEvents()

        self.assertIn("Active frame: 3 / 3", self.window.metadata_panel.metadata_text())


if __name__ == "__main__":
    unittest.main()
