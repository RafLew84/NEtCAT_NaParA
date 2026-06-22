import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from moltrack.core import (
    MolecularDetection,
    MolecularDetectionSet,
    MolecularSegmentation,
    MolecularSegmentationSet,
    MolTrackImageSeries,
    MolTrackRegistrationFrameResult,
    MolTrackRegistrationResultSet,
    MolTrackRegistrationSettings,
)
from moltrack.persistence import save_moltrack_session
from moltrack.sam3 import MolTrackSam3Preview, MolTrackSam3PreviewProposal, MolTrackSam3Proposal
from nanotrack.core import STMSequenceMetadata

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from PyQt6.QtCore import QThread
    from PyQt6.QtWidgets import QFileDialog, QGroupBox, QMessageBox, QDialog, QScrollArea

    from moltrack.ui import MolTrackMainWindow
else:  # pragma: no cover - optional outside target GUI env
    QFileDialog = None
    QMessageBox = None
    MolTrackMainWindow = None


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

        dialog.assert_called_once()
        self.assertEqual(saved, [("state.moltrack.json", series, {"registration_view_mode": "Show raw"})])
        self.assertIn("Saved state state.moltrack.json", self.window.statusBar().currentMessage())

        saved.clear()
        with patch.object(QFileDialog, "getSaveFileName", return_value=("other.moltrack.json", "")) as dialog:
            self.window.action_save_state.trigger()
            self.__class__._app.processEvents()

        dialog.assert_not_called()
        self.assertEqual(saved, [("state.moltrack.json", series, {"registration_view_mode": "Show raw"})])

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

        dialog.assert_called_once()
        self.assertEqual(load_calls, ["state.moltrack.json"])
        self.assertEqual(restore_calls, [loaded_session])
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 2 / 3")
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, frames[1])
        self.assertIn("Source: movie.mpp", self.window.metadata_panel.metadata_text())
        self.assertIn("Loaded state state.moltrack.json", self.window.statusBar().currentMessage())
        self.assertTrue(self.window.action_save_state.isEnabled())

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
            ):
                calls.append(
                    {
                        "frame": np.asarray(frame).copy(),
                        "frame_index": frame_index,
                        "checkpoint_path": checkpoint_path,
                        "confidence_threshold": confidence_threshold,
                        "iou_threshold": iou_threshold,
                        "source_view": source_view,
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

    def test_yolo_detect_all_frames_uses_expanded_aligned_active_view(self) -> None:
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
                        bbox_xyxy=(1, 1, 5, 4),
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
                frame_origins_xy=np.zeros((series.frame_count, 2), dtype=np.float64),
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
            np.testing.assert_array_equal(call[0], expanded_frames[frame_index])
            self.assertEqual(call[1], frame_index)
            self.assertEqual(call[2], checkpoint)
            self.assertEqual(call[3], "expanded_aligned")
            self.assertEqual(
                len(series.molecular_detections.get_detections(frame_index, source_view="expanded_aligned")),
                1,
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

    def test_yolo_detect_current_frame_uses_expanded_aligned_active_view(self) -> None:
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
                        bbox_xyxy=(1, 1, 5, 4),
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
                frame_origins_xy=np.zeros((series.frame_count, 2), dtype=np.float64),
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
        np.testing.assert_array_equal(calls[0][0], expanded_frames[1])
        self.assertEqual(calls[0][1], 1)
        self.assertEqual(calls[0][2], checkpoint)
        self.assertEqual(calls[0][3], "expanded_aligned")
        self.assertEqual(len(series.molecular_detections.get_detections(1, source_view="raw")), 1)
        self.assertEqual(len(series.molecular_detections.get_detections(1, source_view="expanded_aligned")), 1)
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
