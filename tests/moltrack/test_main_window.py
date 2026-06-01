import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, patch

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication, QDialog, QGroupBox, QPushButton, QScrollArea
except ImportError:  # pragma: no cover - optional outside the target GUI env
    QApplication = None
    QDialog = None
    QGroupBox = None
    QPushButton = None
    QScrollArea = None


def _project_with_frames():
    from moltrack.core import MolTrackProject, SourceImageSeries

    frames = np.asarray(
        [
            [[1.0, 2.0], [3.0, 4.0]],
            [[5.0, 6.0], [7.0, 8.0]],
            [[9.0, 10.0], [11.0, 12.0]],
        ],
        dtype=np.float32,
    )
    source = SourceImageSeries(
        source_uri="C:/data/movie.mpp",
        frame_count=3,
        display_name="movie.mpp",
        raw_frames=frames,
    )
    return MolTrackProject.from_source_series(source, reverse_frame_order=True), frames


def _trigger_menu_action(menu, action_text: str) -> None:
    for action in menu.actions():
        if action.text() == action_text:
            action.trigger()
            return
    raise AssertionError(f"Missing menu action: {action_text}")


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for MolTrack GUI tests")
class MolTrackMainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from moltrack.ui import MolTrackWorkspace

        self.window = MolTrackWorkspace()

    def tearDown(self) -> None:
        self.window.close()
        self.window.deleteLater()
        self.__class__._app.processEvents()

    def test_set_project_shows_first_working_frame_and_indices(self) -> None:
        project, frames = _project_with_frames()

        self.window.set_project(project)

        self.assertEqual(self.window.active_working_frame_index(), 0)
        self.assertEqual(self.window.active_source_frame_index(), 2)
        np.testing.assert_array_equal(self.window.displayed_frame(), frames[2])
        self.assertIn("Working 1/3", self.window.frame_index_text())
        self.assertIn("Source 3/3", self.window.frame_index_text())

    def test_slider_changes_active_working_frame(self) -> None:
        project, frames = _project_with_frames()

        self.window.set_project(project)
        self.window.frame_slider.setValue(2)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.active_working_frame_index(), 2)
        self.assertEqual(self.window.active_source_frame_index(), 0)
        np.testing.assert_array_equal(self.window.displayed_frame(), frames[0])
        self.assertIn("Working 3/3", self.window.frame_index_text())
        self.assertIn("Source 1/3", self.window.frame_index_text())

    def test_file_menu_exposes_project_save_load_actions(self) -> None:
        file_menu = None
        for action in self.window.menuBar().actions():
            if action.text() == "File":
                file_menu = action.menu()
                break

        self.assertIsNotNone(file_menu)
        self.assertEqual(
            [action.text() for action in file_menu.actions()],
            [
                "Import Image Series...",
                "Import Reversed Order",
                "Open Project...",
                "Save Project",
                "Save Project As...",
                "Export Detections CSV...",
                "Export Regional Metrics CSV...",
                "Export Project Summary CSV...",
                "Export YOLO Labels...",
            ],
        )
        self.assertTrue(file_menu.actions()[1].isCheckable())

    def test_file_menu_exports_detections_csv_for_current_project(self) -> None:
        project, _frames = _project_with_frames()
        self.window.set_project(project)
        file_menu = None
        for action in self.window.menuBar().actions():
            if action.text() == "File":
                file_menu = action.menu()
                break

        self.assertIsNotNone(file_menu)
        output_path = str(Path(tempfile.gettempdir()) / "moltrack-detections.csv")
        with (
            patch("moltrack.ui.main_window.QFileDialog.getSaveFileName", return_value=(output_path, "CSV Files (*.csv)")),
            patch("moltrack.ui.main_window.export_detections_csv") as export_mock,
        ):
            _trigger_menu_action(file_menu, "Export Detections CSV...")

        export_mock.assert_called_once_with(project, output_path)

    def test_file_menu_exports_regional_metrics_csv_for_current_project(self) -> None:
        project, _frames = _project_with_frames()
        self.window.set_project(project)
        file_menu = None
        for action in self.window.menuBar().actions():
            if action.text() == "File":
                file_menu = action.menu()
                break

        self.assertIsNotNone(file_menu)
        output_path = str(Path(tempfile.gettempdir()) / "moltrack-regional-metrics.csv")
        with (
            patch("moltrack.ui.main_window.QFileDialog.getSaveFileName", return_value=(output_path, "CSV Files (*.csv)")),
            patch("moltrack.ui.main_window.export_regional_metrics_csv") as export_mock,
        ):
            _trigger_menu_action(file_menu, "Export Regional Metrics CSV...")

        export_mock.assert_called_once_with(project, output_path)

    def test_file_menu_exports_project_summary_csv_for_current_project(self) -> None:
        project, _frames = _project_with_frames()
        self.window.set_project(project)
        file_menu = None
        for action in self.window.menuBar().actions():
            if action.text() == "File":
                file_menu = action.menu()
                break

        self.assertIsNotNone(file_menu)
        output_path = str(Path(tempfile.gettempdir()) / "moltrack-project-summary.csv")
        with (
            patch("moltrack.ui.main_window.QFileDialog.getSaveFileName", return_value=(output_path, "CSV Files (*.csv)")),
            patch("moltrack.ui.main_window.export_project_summary_csv") as export_mock,
        ):
            _trigger_menu_action(file_menu, "Export Project Summary CSV...")

        export_mock.assert_called_once_with(project, output_path)

    def test_file_menu_exports_yolo_labels_for_current_project_with_selected_mode(self) -> None:
        project, _frames = _project_with_frames()
        self.window.set_project(project)
        file_menu = None
        for action in self.window.menuBar().actions():
            if action.text() == "File":
                file_menu = action.menu()
                break

        self.assertIsNotNone(file_menu)
        output_dir = str(Path(tempfile.gettempdir()) / "moltrack-yolo-labels")
        with (
            patch(
                "moltrack.ui.main_window.YoloLabelsExportOptionsDialog.get_options",
                return_value=(output_dir, "candidate_uncertain", 2),
            ) as dialog_mock,
            patch("moltrack.ui.main_window.export_yolo_labels") as export_mock,
        ):
            _trigger_menu_action(file_menu, "Export YOLO Labels...")

        dialog_mock.assert_called_once_with(self.window)
        export_mock.assert_called_once_with(project, output_dir, mode="candidate_uncertain", class_id=2)

    def test_regions_menu_and_panel_expose_region_actions(self) -> None:
        regions_menu = None
        for action in self.window.menuBar().actions():
            if action.text() == "Regions":
                regions_menu = action.menu()
                break

        self.assertIsNotNone(regions_menu)
        self.assertEqual(
            [action.text() for action in regions_menu.actions()],
            [
                "Add Rect Region...",
                "Draw Rect ROI",
                "Draw Polyline Region",
                "Commit Drawn Region...",
                "Clear Drawn Region",
                "Apply Selected to Current Frame",
                "Copy Selected from Current to End",
                "Copy Selected to Frame Range...",
                "Edit Selected Region...",
                "Delete Selected Region",
                "Copy Selected to Series",
            ],
        )
        self.assertEqual(self.window.region_list.objectName(), "moltrack-region-list")
        self.assertEqual(self.window.region_list.count(), 0)
        self.assertEqual(self.window.expanded_region_mode_combo.itemData(0), "fixed_canvas")
        self.assertEqual(self.window.expanded_region_mode_combo.itemData(1), "move_with_image")

    def test_side_panel_groups_controls_and_adds_tooltips(self) -> None:
        scroll = self.window.findChild(QScrollArea, "moltrack-side-panel-scroll")
        self.assertIsNotNone(scroll)
        group_titles = [group.title() for group in self.window.findChildren(QGroupBox)]
        self.assertEqual(
            group_titles,
            [
                "Regions",
                "Region Actions",
                "Detections",
                "Manual Detection",
                "Review Detections",
                "Delete Current Frame",
                "Scale BBoxes",
            ],
        )
        for widget in (
            self.window.expanded_region_mode_combo,
            self.window.region_list,
            self.window.detection_list,
            self.window.assign_detection_regions_button,
            self.window.draw_manual_detection_button,
            self.window.commit_manual_detection_button,
            self.window.accept_all_current_frame_button,
            self.window.accept_all_frames_button,
            self.window.accept_confidence_threshold_spin,
            self.window.accept_above_confidence_button,
            self.window.delete_status_combo,
            self.window.delete_current_status_button,
            self.window.delete_inside_selected_region_button,
            self.window.scale_bbox_factor_spin,
            self.window.scale_current_frame_bboxes_button,
            self.window.scale_all_bboxes_button,
        ):
            self.assertTrue(widget.toolTip(), widget.objectName() or widget.__class__.__name__)

    def test_registration_menu_exposes_run_registration_action(self) -> None:
        registration_menu = None
        for action in self.window.menuBar().actions():
            if action.text() == "Registration":
                registration_menu = action.menu()
                break

        self.assertIsNotNone(registration_menu)
        self.assertEqual(
            [action.text() for action in registration_menu.actions()],
            ["Run Registration", "Show Expanded Aligned"],
        )
        self.assertTrue(registration_menu.actions()[1].isCheckable())
        self.assertEqual(
            [
                self.window.registration_backend_combo.itemData(index)
                for index in range(self.window.registration_backend_combo.count())
            ],
            ["phase_correlation", "optical_flow_median"],
        )

    def test_yolo_menu_exposes_detect_current_frame_action(self) -> None:
        yolo_menu = None
        for action in self.window.menuBar().actions():
            if action.text() == "YOLO":
                yolo_menu = action.menu()
                break

        self.assertIsNotNone(yolo_menu)
        self.assertEqual(
            [action.text() for action in yolo_menu.actions()],
            [
                "Detect Current Frame",
                "Detect Current Frame in Selected ROI",
                "Detect All Working Frames",
                "Detect Selected ROI on Frame Range...",
            ],
        )

    def test_results_menu_opens_population_metrics_dialog_for_current_project(self) -> None:
        project, _frames = _project_with_frames()
        self.window.set_project(project)
        results_menu = None
        for action in self.window.menuBar().actions():
            if action.text() == "Results":
                results_menu = action.menu()
                break

        self.assertIsNotNone(results_menu)
        self.assertEqual([action.text() for action in results_menu.actions()], ["Population Metrics..."])

        with patch("moltrack.ui.main_window.PopulationMetricsDialog.show_for_project") as show_mock:
            _trigger_menu_action(results_menu, "Population Metrics...")

        show_mock.assert_called_once_with(project, self.window)

    def test_population_metrics_dialog_plots_global_and_region_filtered_series(self) -> None:
        from moltrack.core import (
            AnalysisRegion,
            DetectionReviewStatus,
            MolTrackProject,
            MolecularDetection,
            PopulationMetrics,
            SourceImageSeries,
        )
        from moltrack.ui.main_window import PopulationMetricsDialog

        source = SourceImageSeries(
            source_uri="C:/data/series.stp",
            frame_count=2,
            raw_frames=np.zeros((2, 4, 4), dtype=np.float32),
        )
        terrace_a = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(255, 0, 0),
            rect_xyxy=(0.0, 0.0, 10.0, 10.0),
        )
        terrace_b = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace B",
            color_rgb=(0, 255, 0),
            rect_xyxy=(0.0, 0.0, 5.0, 10.0),
        )
        project = MolTrackProject.from_source_series(source).with_analysis_regions(
            (terrace_a, terrace_b),
            molecular_detections=(
                MolecularDetection(
                    detection_id="a-0",
                    working_frame_index=0,
                    source_frame_index=0,
                    bbox_xyxy=(0.0, 0.0, 1.0, 2.0),
                    confidence=0.9,
                    model_name="manual",
                    review_status=DetectionReviewStatus.ACCEPTED,
                    backend_name="manual",
                    run_mode="full_frame",
                    region_name="Terrace A",
                ),
                MolecularDetection(
                    detection_id="a-1",
                    working_frame_index=0,
                    source_frame_index=0,
                    bbox_xyxy=(0.0, 0.0, 2.0, 2.0),
                    confidence=1.0,
                    model_name="manual",
                    review_status=DetectionReviewStatus.MANUAL,
                    backend_name="manual",
                    run_mode="full_frame",
                    region_name="Terrace A",
                ),
                MolecularDetection(
                    detection_id="b-0",
                    working_frame_index=0,
                    source_frame_index=0,
                    bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
                    confidence=0.8,
                    model_name="yolo",
                    review_status=DetectionReviewStatus.EDITED,
                    backend_name="yolo",
                    run_mode="full_frame",
                    region_name="Terrace B",
                ),
                MolecularDetection(
                    detection_id="candidate-ignored",
                    working_frame_index=0,
                    source_frame_index=0,
                    bbox_xyxy=(0.0, 0.0, 10.0, 10.0),
                    confidence=0.8,
                    model_name="yolo",
                    review_status=DetectionReviewStatus.CANDIDATE,
                    backend_name="yolo",
                    run_mode="full_frame",
                    region_name="Terrace A",
                ),
                MolecularDetection(
                    detection_id="a-2",
                    working_frame_index=1,
                    source_frame_index=1,
                    bbox_xyxy=(0.0, 0.0, 2.0, 2.0),
                    confidence=0.9,
                    model_name="yolo",
                    review_status=DetectionReviewStatus.ACCEPTED,
                    backend_name="yolo",
                    run_mode="full_frame",
                    region_name="Terrace A",
                ),
            ),
        )

        dialog = PopulationMetricsDialog(PopulationMetrics.from_project(project), self.window)
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(dialog.objectName(), "moltrack-population-metrics-dialog")
        self.assertEqual(dialog.count_plot.objectName(), "moltrack-population-count-plot")
        self.assertEqual(dialog.density_plot.objectName(), "moltrack-population-density-plot")
        self.assertEqual(dialog.coverage_plot.objectName(), "moltrack-population-coverage-plot")
        self.assertEqual(
            [dialog.region_filter_combo.itemText(index) for index in range(dialog.region_filter_combo.count())],
            ["All regions", "Terrace A", "Terrace B"],
        )

        global_points = dialog.current_series_points()
        self.assertEqual(
            [(point.working_frame_index, point.detection_count) for point in global_points],
            [(0, 3), (1, 1)],
        )
        self.assertAlmostEqual(global_points[0].density_per_px2, 3.0 / 150.0)
        self.assertAlmostEqual(global_points[0].detection_footprint_coverage, 7.0 / 150.0)
        _count_x, count_y = dialog.count_plot.listDataItems()[0].getData()
        np.testing.assert_array_equal(count_y, np.asarray([3, 1]))

        dialog.region_filter_combo.setCurrentIndex(dialog.region_filter_combo.findData("Terrace A"))
        terrace_a_points = dialog.current_series_points()
        self.assertEqual(
            [(point.working_frame_index, point.detection_count) for point in terrace_a_points],
            [(0, 2), (1, 1)],
        )
        self.assertAlmostEqual(terrace_a_points[0].density_per_px2, 2.0 / 100.0)
        self.assertAlmostEqual(terrace_a_points[0].detection_footprint_coverage, 6.0 / 100.0)
        _count_x, count_y = dialog.count_plot.listDataItems()[0].getData()
        np.testing.assert_array_equal(count_y, np.asarray([2, 1]))

    def test_yolo_menu_action_opens_options_dialog_and_uses_selected_model_parameters(self) -> None:
        from moltrack.yolo import MolTrackYoloDetectionConfig, MolTrackYoloModelInfo

        model_a = MolTrackYoloModelInfo(
            name="molecule_small.pt",
            path=Path(tempfile.gettempdir()) / "molecule_small.pt",
        )
        model_b = MolTrackYoloModelInfo(
            name="molecule_large.pt",
            path=Path(tempfile.gettempdir()) / "molecule_large.pt",
        )
        config = MolTrackYoloDetectionConfig(confidence_threshold=0.37, iou_threshold=0.58, device="cuda:0")
        project, _frames = _project_with_frames()

        self.window.set_project(project)
        self.window.refresh_yolo_models([model_a, model_b])

        with (
            patch(
                "moltrack.ui.main_window.YoloDetectionOptionsDialog.get_options",
                return_value=(model_b, config),
            ) as options_mock,
            patch.object(self.window, "detect_yolo_on_current_frame", return_value=()) as detect_mock,
        ):
            self.window.detect_yolo_current_frame_action.trigger()

        self.assertFalse(hasattr(self.window, "yolo_model_combo"))
        options_mock.assert_called_once()
        self.assertEqual(options_mock.call_args.kwargs["models"], [model_a, model_b])
        self.assertEqual(options_mock.call_args.kwargs["selected_model_path"], model_a.path)
        detect_mock.assert_called_once()
        model_arg = detect_mock.call_args.args[0]
        config_arg = detect_mock.call_args.kwargs["config"]
        self.assertEqual(model_arg, model_b)
        self.assertAlmostEqual(config_arg.confidence_threshold, 0.37)
        self.assertAlmostEqual(config_arg.iou_threshold, 0.58)
        self.assertEqual(config_arg.device, "cuda:0")
        self.assertEqual(self.window.selected_yolo_model(), model_b)
        self.assertEqual(self.window.selected_yolo_detection_config(), config)

    def test_yolo_detection_options_dialog_selects_model_and_parameters(self) -> None:
        from moltrack.ui.main_window import YoloDetectionOptionsDialog
        from moltrack.yolo import MolTrackYoloDetectionConfig, MolTrackYoloModelInfo

        model_a = MolTrackYoloModelInfo(
            name="molecule_small.pt",
            path=Path(tempfile.gettempdir()) / "molecule_small.pt",
        )
        model_b = MolTrackYoloModelInfo(
            name="molecule_large.pt",
            path=Path(tempfile.gettempdir()) / "molecule_large.pt",
        )

        dialog = YoloDetectionOptionsDialog(
            self.window,
            models=[model_a, model_b],
            selected_model_path=model_a.path,
            config=MolTrackYoloDetectionConfig(confidence_threshold=0.11, iou_threshold=0.22, device="cpu"),
        )
        dialog.model_combo.setCurrentIndex(1)
        dialog.confidence_spin.setValue(0.41)
        dialog.iou_spin.setValue(0.62)
        dialog.device_combo.setCurrentIndex(dialog.device_combo.findData("cuda:0"))

        model, config = dialog.to_options()

        self.assertEqual(dialog.model_combo.objectName(), "moltrack-yolo-model-combo")
        self.assertEqual(dialog.device_combo.objectName(), "moltrack-yolo-device-combo")
        self.assertEqual(
            [
                (dialog.device_combo.itemText(index), dialog.device_combo.itemData(index))
                for index in range(dialog.device_combo.count())
            ],
            [("Auto", "auto"), ("CPU", "cpu"), ("GPU", "cuda:0")],
        )
        self.assertEqual(
            [dialog.model_combo.itemText(index) for index in range(dialog.model_combo.count())],
            ["molecule_small.pt", "molecule_large.pt"],
        )
        self.assertEqual(model, model_b)
        self.assertAlmostEqual(config.confidence_threshold, 0.41)
        self.assertAlmostEqual(config.iou_threshold, 0.62)
        self.assertEqual(config.device, "cuda:0")

    def test_detect_yolo_current_frame_uses_runtime_and_draws_candidate_detections(self) -> None:
        from moltrack.core import DetectionReviewStatus
        from moltrack.yolo import MolTrackYoloDetectionConfig, MolTrackYoloModelInfo
        from nanotrack.core import BBoxXYXY

        class FakeYoloRuntime:
            def __init__(self) -> None:
                self.calls = []

            def predict_frame(self, frame, **kwargs):
                self.calls.append((np.asarray(frame), kwargs))
                return [
                    SimpleNamespace(
                        bbox=BBoxXYXY(0.25, 0.5, 1.5, 1.75),
                        confidence=0.91,
                        model_name="moltrack_model.pt",
                    )
                ]

        project, frames = _project_with_frames()
        runtime = FakeYoloRuntime()
        config = MolTrackYoloDetectionConfig(confidence_threshold=0.31, iou_threshold=0.42, device="cpu")
        model = MolTrackYoloModelInfo(
            name="moltrack_model.pt",
            path=Path(tempfile.gettempdir()) / "moltrack_model.pt",
        )

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        with patch.object(self.window.viewer, "add_polyline_nm", return_value=object()) as add_mock:
            detections = self.window.detect_yolo_on_current_frame(model, config=config, runtime=runtime)

        self.assertEqual(len(detections), 1)
        detection = detections[0]
        self.assertEqual(detection.working_frame_index, 1)
        self.assertEqual(detection.source_frame_index, 1)
        self.assertEqual(detection.bbox_xyxy, (0.25, 0.5, 1.5, 1.75))
        self.assertEqual(detection.confidence, 0.91)
        self.assertEqual(detection.model_name, "moltrack_model.pt")
        self.assertEqual(detection.review_status, DetectionReviewStatus.CANDIDATE)
        self.assertEqual(detection.backend_name, "yolo")
        self.assertEqual(detection.run_mode, "full_frame")
        np.testing.assert_array_equal(runtime.calls[0][0], frames[1])
        self.assertEqual(runtime.calls[0][1]["model_path"], model.path)
        self.assertEqual(runtime.calls[0][1]["conf_threshold"], 0.31)
        self.assertEqual(runtime.calls[0][1]["iou_threshold"], 0.42)
        self.assertEqual(runtime.calls[0][1]["device"], "cpu")
        self.assertEqual(self.window.current_project().molecular_detections_for_working_frame(1), tuple(detections))
        overlay_points = add_mock.call_args.args[0]
        np.testing.assert_allclose(
            overlay_points,
            np.asarray(
                [
                    [0.25, 0.5],
                    [1.5, 0.5],
                    [1.5, 1.75],
                    [0.25, 1.75],
                    [0.25, 0.5],
                ],
                dtype=np.float64,
            ),
        )

    def test_detect_yolo_current_frame_replaces_only_existing_yolo_candidates(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection
        from moltrack.yolo import MolTrackYoloDetectionConfig, MolTrackYoloModelInfo
        from nanotrack.core import BBoxXYXY

        class FakeYoloRuntime:
            def predict_frame(self, _frame, **_kwargs):
                return [
                    SimpleNamespace(
                        bbox=BBoxXYXY(0.0, 0.0, 1.0, 1.0),
                        confidence=0.72,
                        model_name="moltrack_model.pt",
                    )
                ]

        project, _frames = _project_with_frames()
        old_candidate = MolecularDetection(
            detection_id="old-candidate",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.0, 0.0, 0.5, 0.5),
            confidence=0.5,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        accepted = MolecularDetection(
            detection_id="yolo-w0001-0000",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(1.0, 1.0, 1.5, 1.5),
            confidence=0.8,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="yolo",
            run_mode="full_frame",
        )
        manual = MolecularDetection(
            detection_id="manual-keep",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(1.5, 1.5, 2.0, 2.0),
            confidence=1.0,
            model_name="manual",
            review_status=DetectionReviewStatus.MANUAL,
            backend_name="manual",
            run_mode="full_frame",
        )
        project = project.with_molecular_detections((old_candidate, accepted, manual))
        model = MolTrackYoloModelInfo(
            name="moltrack_model.pt",
            path=Path(tempfile.gettempdir()) / "moltrack_model.pt",
        )

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        with patch.object(self.window.viewer, "add_polyline_nm", return_value=object()):
            new_detections = self.window.detect_yolo_on_current_frame(
                model,
                config=MolTrackYoloDetectionConfig(device="cpu"),
                runtime=FakeYoloRuntime(),
            )

        active_detections = self.window.current_project().molecular_detections_for_working_frame(1)
        self.assertNotIn(old_candidate, active_detections)
        self.assertIn(accepted, active_detections)
        self.assertIn(manual, active_detections)
        self.assertEqual(len(new_detections), 1)
        self.assertIn(new_detections[0], active_detections)
        self.assertEqual(new_detections[0].detection_id, "yolo-w0001-0000-1")
        self.assertEqual(new_detections[0].review_status, DetectionReviewStatus.CANDIDATE)

    def test_detect_yolo_current_frame_in_rect_roi_replaces_only_detections_inside_roi(self) -> None:
        from moltrack.core import AnalysisRegion, DetectionReviewStatus, MolecularDetection
        from moltrack.yolo import MolTrackYoloDetectionConfig, MolTrackYoloModelInfo
        from nanotrack.core import BBoxXYXY

        class FakeYoloRuntime:
            def __init__(self) -> None:
                self.calls = []

            def predict_frame(self, frame, **kwargs):
                self.calls.append((np.asarray(frame), kwargs))
                return [
                    SimpleNamespace(
                        bbox=BBoxXYXY(0.0, 0.0, 3.0, 3.0),
                        confidence=0.72,
                        model_name="moltrack_model.pt",
                    ),
                    SimpleNamespace(
                        bbox=BBoxXYXY(3.0, 3.0, 4.0, 4.0),
                        confidence=0.91,
                        model_name="moltrack_model.pt",
                    ),
                ]

        project, frames = _project_with_frames()
        roi = AnalysisRegion.rectangle(
            kind="terrace",
            name="ROI A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(0.0, 0.0, 2.0, 2.0),
        )
        inside_existing = MolecularDetection(
            detection_id="inside-existing",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.8,
            model_name="manual",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="manual",
            run_mode="full_frame",
        )
        outside_existing = MolecularDetection(
            detection_id="outside-existing",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(3.0, 3.0, 4.0, 4.0),
            confidence=0.8,
            model_name="manual",
            review_status=DetectionReviewStatus.MANUAL,
            backend_name="manual",
            run_mode="full_frame",
        )
        project = project.with_analysis_regions((roi,)).with_molecular_detections(
            (inside_existing, outside_existing)
        )
        runtime = FakeYoloRuntime()
        model = MolTrackYoloModelInfo(
            name="moltrack_model.pt",
            path=Path(tempfile.gettempdir()) / "moltrack_model.pt",
        )

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        with patch.object(self.window.viewer, "add_polyline_nm", return_value=object()):
            new_detections = self.window.detect_yolo_on_current_frame_in_region(
                "ROI A",
                model,
                config=MolTrackYoloDetectionConfig(device="cpu"),
                runtime=runtime,
            )

        np.testing.assert_array_equal(runtime.calls[0][0], frames[1])
        self.assertEqual(len(new_detections), 1)
        self.assertEqual(new_detections[0].bbox_xyxy, (0.0, 0.0, 3.0, 3.0))
        self.assertEqual(new_detections[0].run_mode, "roi_replace")
        self.assertEqual(new_detections[0].region_name, "ROI A")
        active_detections = self.window.current_project().molecular_detections_for_working_frame(1)
        self.assertNotIn(inside_existing, active_detections)
        self.assertIn(outside_existing, active_detections)
        self.assertIn(new_detections[0], active_detections)
        self.assertEqual(len(active_detections), 2)

    def test_detect_yolo_current_frame_in_polygon_roi_uses_centroid_membership(self) -> None:
        from moltrack.core import AnalysisRegion, DetectionReviewStatus, MolecularDetection
        from moltrack.yolo import MolTrackYoloDetectionConfig, MolTrackYoloModelInfo
        from nanotrack.core import BBoxXYXY

        class FakeYoloRuntime:
            def predict_frame(self, _frame, **_kwargs):
                return [
                    SimpleNamespace(
                        bbox=BBoxXYXY(0.0, 0.0, 1.0, 1.0),
                        confidence=0.72,
                        model_name="moltrack_model.pt",
                    ),
                    SimpleNamespace(
                        bbox=BBoxXYXY(1.5, 1.5, 2.0, 2.0),
                        confidence=0.91,
                        model_name="moltrack_model.pt",
                    ),
                ]

        project, _frames = _project_with_frames()
        roi = AnalysisRegion.polygon(
            kind="terrace",
            name="Triangle ROI",
            color_rgb=(20, 120, 240),
            vertices_xy=[(0.0, 0.0), (2.0, 0.0), (0.0, 2.0)],
        )
        inside_existing = MolecularDetection(
            detection_id="inside-existing",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.8,
            model_name="manual",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="manual",
            run_mode="full_frame",
        )
        outside_existing = MolecularDetection(
            detection_id="outside-existing",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(1.5, 1.5, 2.0, 2.0),
            confidence=0.8,
            model_name="manual",
            review_status=DetectionReviewStatus.MANUAL,
            backend_name="manual",
            run_mode="full_frame",
        )
        project = project.with_analysis_regions((roi,)).with_molecular_detections(
            (inside_existing, outside_existing)
        )
        model = MolTrackYoloModelInfo(
            name="moltrack_model.pt",
            path=Path(tempfile.gettempdir()) / "moltrack_model.pt",
        )

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        with patch.object(self.window.viewer, "add_polyline_nm", return_value=object()):
            new_detections = self.window.detect_yolo_on_current_frame_in_region(
                "Triangle ROI",
                model,
                config=MolTrackYoloDetectionConfig(device="cpu"),
                runtime=FakeYoloRuntime(),
            )

        self.assertEqual(len(new_detections), 1)
        self.assertEqual(new_detections[0].bbox_xyxy, (0.0, 0.0, 1.0, 1.0))
        active_detections = self.window.current_project().molecular_detections_for_working_frame(1)
        self.assertNotIn(inside_existing, active_detections)
        self.assertIn(outside_existing, active_detections)
        self.assertIn(new_detections[0], active_detections)

    def test_detect_yolo_all_working_frames_runs_only_working_series_and_returns_results_per_frame(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection
        from moltrack.yolo import MolTrackYoloDetectionConfig, MolTrackYoloModelInfo
        from nanotrack.core import BBoxXYXY

        class FakeYoloRuntime:
            def __init__(self) -> None:
                self.calls = []

            def predict_frame(self, frame, **kwargs):
                self.calls.append((np.asarray(frame), kwargs))
                call_index = len(self.calls) - 1
                return [
                    SimpleNamespace(
                        bbox=BBoxXYXY(call_index, call_index, call_index + 1.0, call_index + 1.0),
                        confidence=0.70 + call_index / 10.0,
                        model_name="moltrack_model.pt",
                    )
                ]

        project, frames = _project_with_frames()
        project = project.remove_working_frame(1)
        old_candidate = MolecularDetection(
            detection_id="old-candidate",
            working_frame_index=0,
            source_frame_index=2,
            bbox_xyxy=(0.0, 0.0, 0.5, 0.5),
            confidence=0.5,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        accepted = MolecularDetection(
            detection_id="accepted-keep",
            working_frame_index=0,
            source_frame_index=2,
            bbox_xyxy=(1.0, 1.0, 1.5, 1.5),
            confidence=0.8,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="yolo",
            run_mode="full_frame",
        )
        project = project.with_molecular_detections((old_candidate, accepted))
        runtime = FakeYoloRuntime()
        progress_events = []
        model = MolTrackYoloModelInfo(
            name="moltrack_model.pt",
            path=Path(tempfile.gettempdir()) / "moltrack_model.pt",
        )

        self.window.set_project(project)
        with patch.object(self.window.viewer, "add_polyline_nm", return_value=object()):
            detections_by_frame = self.window.detect_yolo_on_all_working_frames(
                model,
                config=MolTrackYoloDetectionConfig(device="cpu"),
                runtime=runtime,
                progress_callback=lambda completed, total, frame_index: progress_events.append(
                    (completed, total, frame_index)
                ),
            )

        self.assertEqual(list(detections_by_frame), [0, 1])
        np.testing.assert_array_equal(runtime.calls[0][0], frames[2])
        np.testing.assert_array_equal(runtime.calls[1][0], frames[0])
        self.assertEqual(progress_events, [(1, 2, 0), (2, 2, 1)])
        active_frame_zero = self.window.current_project().molecular_detections_for_working_frame(0)
        self.assertNotIn(old_candidate, active_frame_zero)
        self.assertIn(accepted, active_frame_zero)
        self.assertIn(detections_by_frame[0][0], active_frame_zero)
        self.assertEqual(detections_by_frame[0][0].run_mode, "full_frame")
        self.assertEqual(detections_by_frame[0][0].review_status, DetectionReviewStatus.CANDIDATE)
        self.assertEqual(detections_by_frame[1][0].source_frame_index, 0)

    def test_detect_yolo_all_working_frames_can_cancel_after_completed_frame(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection
        from moltrack.yolo import MolTrackYoloDetectionConfig, MolTrackYoloModelInfo
        from nanotrack.core import BBoxXYXY

        class FakeYoloRuntime:
            def __init__(self) -> None:
                self.calls = []

            def predict_frame(self, frame, **_kwargs):
                self.calls.append(np.asarray(frame))
                return [
                    SimpleNamespace(
                        bbox=BBoxXYXY(0.0, 0.0, 1.0, 1.0),
                        confidence=0.72,
                        model_name="moltrack_model.pt",
                    )
                ]

        project, _frames = _project_with_frames()
        unprocessed_candidate = MolecularDetection(
            detection_id="future-candidate",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(1.0, 1.0, 1.5, 1.5),
            confidence=0.5,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        project = project.with_molecular_detections((unprocessed_candidate,))
        runtime = FakeYoloRuntime()
        progress_events = []
        model = MolTrackYoloModelInfo(
            name="moltrack_model.pt",
            path=Path(tempfile.gettempdir()) / "moltrack_model.pt",
        )

        self.window.set_project(project)
        with patch.object(self.window.viewer, "add_polyline_nm", return_value=object()):
            detections_by_frame = self.window.detect_yolo_on_all_working_frames(
                model,
                config=MolTrackYoloDetectionConfig(device="cpu"),
                runtime=runtime,
                progress_callback=lambda completed, total, frame_index: progress_events.append(
                    (completed, total, frame_index)
                ),
                cancel_check=lambda: bool(progress_events),
            )

        self.assertEqual(list(detections_by_frame), [0])
        self.assertEqual(len(runtime.calls), 1)
        self.assertEqual(progress_events, [(1, 3, 0)])
        active_frame_one = self.window.current_project().molecular_detections_for_working_frame(1)
        self.assertIn(unprocessed_candidate, active_frame_one)

    def test_detect_yolo_selected_roi_on_working_frame_range_uses_frame_scoped_region_geometry(self) -> None:
        from moltrack.core import AnalysisRegion, DetectionReviewStatus, FrameScopedAnalysisRegion, MolecularDetection
        from moltrack.yolo import MolTrackYoloDetectionConfig, MolTrackYoloModelInfo
        from nanotrack.core import BBoxXYXY

        class FakeYoloRuntime:
            def __init__(self) -> None:
                self.calls = []

            def predict_frame(self, frame, **kwargs):
                self.calls.append((np.asarray(frame), kwargs))
                return [
                    SimpleNamespace(
                        bbox=BBoxXYXY(0.0, 0.0, 1.0, 1.0),
                        confidence=0.72,
                        model_name="moltrack_model.pt",
                    ),
                    SimpleNamespace(
                        bbox=BBoxXYXY(3.0, 3.0, 4.0, 4.0),
                        confidence=0.91,
                        model_name="moltrack_model.pt",
                    ),
                ]

        project, frames = _project_with_frames()
        frame_zero_region = AnalysisRegion.rectangle(
            kind="terrace",
            name="ROI A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(0.0, 0.0, 2.0, 2.0),
        )
        frame_one_region = AnalysisRegion.rectangle(
            kind="terrace",
            name="ROI A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(2.0, 2.0, 5.0, 5.0),
        )
        inside_frame_zero = MolecularDetection(
            detection_id="inside-frame-zero",
            working_frame_index=0,
            source_frame_index=2,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.8,
            model_name="manual",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="manual",
            run_mode="full_frame",
        )
        outside_frame_zero = MolecularDetection(
            detection_id="outside-frame-zero",
            working_frame_index=0,
            source_frame_index=2,
            bbox_xyxy=(3.0, 3.0, 4.0, 4.0),
            confidence=0.8,
            model_name="manual",
            review_status=DetectionReviewStatus.MANUAL,
            backend_name="manual",
            run_mode="full_frame",
        )
        outside_frame_one = MolecularDetection(
            detection_id="outside-frame-one",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.8,
            model_name="manual",
            review_status=DetectionReviewStatus.MANUAL,
            backend_name="manual",
            run_mode="full_frame",
        )
        inside_frame_one = MolecularDetection(
            detection_id="inside-frame-one",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(3.0, 3.0, 4.0, 4.0),
            confidence=0.8,
            model_name="manual",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="manual",
            run_mode="full_frame",
        )
        untouched_frame_two = MolecularDetection(
            detection_id="untouched-frame-two",
            working_frame_index=2,
            source_frame_index=0,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.8,
            model_name="manual",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="manual",
            run_mode="full_frame",
        )
        project = project.with_analysis_regions(
            (frame_zero_region,),
            frame_scoped_analysis_regions=(
                FrameScopedAnalysisRegion(region=frame_zero_region, working_frame_indices=(0,)),
                FrameScopedAnalysisRegion(region=frame_one_region, working_frame_indices=(1,)),
            ),
            molecular_detections=(
                inside_frame_zero,
                outside_frame_zero,
                outside_frame_one,
                inside_frame_one,
                untouched_frame_two,
            ),
        )
        runtime = FakeYoloRuntime()
        progress_events = []
        model = MolTrackYoloModelInfo(
            name="moltrack_model.pt",
            path=Path(tempfile.gettempdir()) / "moltrack_model.pt",
        )

        self.window.set_project(project)
        with patch.object(self.window.viewer, "add_polyline_nm", return_value=object()):
            detections_by_frame = self.window.detect_yolo_in_region_on_working_frames(
                "ROI A",
                model,
                working_frame_indices=(0, 1),
                config=MolTrackYoloDetectionConfig(device="cpu"),
                runtime=runtime,
                progress_callback=lambda completed, total, frame_index: progress_events.append(
                    (completed, total, frame_index)
                ),
            )

        self.assertEqual(list(detections_by_frame), [0, 1])
        np.testing.assert_array_equal(runtime.calls[0][0], frames[2])
        np.testing.assert_array_equal(runtime.calls[1][0], frames[1])
        self.assertEqual(progress_events, [(1, 2, 0), (2, 2, 1)])
        self.assertEqual(detections_by_frame[0][0].bbox_xyxy, (0.0, 0.0, 1.0, 1.0))
        self.assertEqual(detections_by_frame[1][0].bbox_xyxy, (3.0, 3.0, 4.0, 4.0))
        self.assertEqual(detections_by_frame[0][0].run_mode, "roi_replace")
        self.assertEqual(detections_by_frame[1][0].region_name, "ROI A")
        frame_zero_detections = self.window.current_project().molecular_detections_for_working_frame(0)
        frame_one_detections = self.window.current_project().molecular_detections_for_working_frame(1)
        frame_two_detections = self.window.current_project().molecular_detections_for_working_frame(2)
        self.assertNotIn(inside_frame_zero, frame_zero_detections)
        self.assertIn(outside_frame_zero, frame_zero_detections)
        self.assertIn(detections_by_frame[0][0], frame_zero_detections)
        self.assertIn(outside_frame_one, frame_one_detections)
        self.assertNotIn(inside_frame_one, frame_one_detections)
        self.assertIn(detections_by_frame[1][0], frame_one_detections)
        self.assertEqual(frame_two_detections, (untouched_frame_two,))

    def test_detect_yolo_selected_roi_on_working_frame_range_can_cancel_after_completed_frame(self) -> None:
        from moltrack.core import AnalysisRegion, DetectionReviewStatus, MolecularDetection
        from moltrack.yolo import MolTrackYoloDetectionConfig, MolTrackYoloModelInfo
        from nanotrack.core import BBoxXYXY

        class FakeYoloRuntime:
            def __init__(self) -> None:
                self.calls = []

            def predict_frame(self, frame, **_kwargs):
                self.calls.append(np.asarray(frame))
                return [
                    SimpleNamespace(
                        bbox=BBoxXYXY(0.0, 0.0, 1.0, 1.0),
                        confidence=0.72,
                        model_name="moltrack_model.pt",
                    )
                ]

        project, _frames = _project_with_frames()
        roi = AnalysisRegion.rectangle(
            kind="terrace",
            name="ROI A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(0.0, 0.0, 2.0, 2.0),
        )
        unprocessed_inside_roi = MolecularDetection(
            detection_id="unprocessed-inside-roi",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.8,
            model_name="manual",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="manual",
            run_mode="full_frame",
        )
        project = project.with_analysis_regions(
            (roi,),
            molecular_detections=(unprocessed_inside_roi,),
        )
        runtime = FakeYoloRuntime()
        progress_events = []
        model = MolTrackYoloModelInfo(
            name="moltrack_model.pt",
            path=Path(tempfile.gettempdir()) / "moltrack_model.pt",
        )

        self.window.set_project(project)
        with patch.object(self.window.viewer, "add_polyline_nm", return_value=object()):
            detections_by_frame = self.window.detect_yolo_in_region_on_working_frames(
                "ROI A",
                model,
                working_frame_indices=(0, 1),
                config=MolTrackYoloDetectionConfig(device="cpu"),
                runtime=runtime,
                progress_callback=lambda completed, total, frame_index: progress_events.append(
                    (completed, total, frame_index)
                ),
                cancel_check=lambda: bool(progress_events),
            )

        self.assertEqual(list(detections_by_frame), [0])
        self.assertEqual(len(runtime.calls), 1)
        self.assertEqual(progress_events, [(1, 2, 0)])
        frame_one_detections = self.window.current_project().molecular_detections_for_working_frame(1)
        self.assertEqual(frame_one_detections, (unprocessed_inside_roi,))

    def test_detection_list_shows_active_frame_detection_summary(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection

        current_detection = MolecularDetection(
            detection_id="det-current",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.876,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="roi_replace",
            region_name="Terrace A",
        )
        other_frame_detection = MolecularDetection(
            detection_id="det-other",
            working_frame_index=2,
            source_frame_index=0,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.5,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="yolo",
            run_mode="full_frame",
        )
        project, _frames = _project_with_frames()
        project = project.with_molecular_detections((current_detection, other_frame_detection))

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)

        self.assertEqual(self.window.detection_list.objectName(), "moltrack-detection-list")
        self.assertEqual(self.window.detection_list.count(), 1)
        self.assertEqual(
            self.window.detection_list.item(0).text(),
            "det-current | candidate | conf=0.876 | region=Terrace A",
        )

    def test_assign_regions_button_updates_detection_region_names_for_whole_series(self) -> None:
        from moltrack.core import AnalysisRegion, DetectionReviewStatus, FrameScopedAnalysisRegion, MolecularDetection

        frame_zero_region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(0.0, 0.0, 2.0, 2.0),
        )
        frame_one_region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(4.0, 4.0, 6.0, 6.0),
        )
        active_detection = MolecularDetection(
            detection_id="active",
            working_frame_index=0,
            source_frame_index=2,
            bbox_xyxy=(0.25, 0.25, 1.25, 1.25),
            confidence=0.9,
            model_name="manual",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="manual",
            run_mode="full_frame",
        )
        other_frame_detection = MolecularDetection(
            detection_id="other-frame",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(4.25, 4.25, 5.25, 5.25),
            confidence=0.9,
            model_name="manual",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="manual",
            run_mode="full_frame",
        )
        project, _frames = _project_with_frames()
        project = project.with_analysis_regions(
            (frame_zero_region,),
            frame_scoped_analysis_regions=(
                FrameScopedAnalysisRegion(region=frame_zero_region, working_frame_indices=(0,)),
                FrameScopedAnalysisRegion(region=frame_one_region, working_frame_indices=(1,)),
            ),
            molecular_detections=(active_detection, other_frame_detection),
        )

        self.window.set_project(project)
        self.window.set_active_working_frame_index(0)

        self.window.assign_detection_regions_button.click()

        active = self.window.current_project().molecular_detections_for_working_frame(0)[0]
        other = self.window.current_project().molecular_detections_for_working_frame(1)[0]
        self.assertEqual(active.region_name, "Terrace A")
        self.assertEqual(other.region_name, "Terrace A")
        self.assertEqual(
            self.window.detection_list.item(0).text(),
            "active | accepted | conf=0.900 | region=Terrace A",
        )

    def test_clicking_detection_list_item_highlights_detection_bbox_in_viewer(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection

        detection_a = MolecularDetection(
            detection_id="det-a",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.8,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        detection_b = MolecularDetection(
            detection_id="det-b",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(2.0, 2.0, 3.0, 3.0),
            confidence=0.9,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="yolo",
            run_mode="full_frame",
        )
        project, _frames = _project_with_frames()
        project = project.with_molecular_detections((detection_a, detection_b))

        with patch.object(self.window.viewer, "add_polyline_nm", return_value=object()) as add_mock:
            self.window.set_project(project)
            self.window.set_active_working_frame_index(1)
            add_mock.reset_mock()

            self.window.detection_list.setCurrentRow(1)

        selected_calls = [
            call
            for call in add_mock.call_args_list
            if call.kwargs.get("name") == "det-b"
        ]
        self.assertTrue(selected_calls)
        self.assertEqual(selected_calls[-1].kwargs["color"], (0, 220, 255))
        self.assertEqual(selected_calls[-1].kwargs["width"], 3.0)

    def test_detection_context_menu_replaces_selected_bbox_panel_actions(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection

        detection = MolecularDetection(
            detection_id="det-current",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.876,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        project, _frames = _project_with_frames()
        project = project.with_molecular_detections((detection,))

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        menu = self.window.build_detection_context_menu("det-current")
        self.addCleanup(menu.deleteLater)

        self.assertEqual(
            [action.text() for action in menu.actions() if not action.isSeparator()],
            ["Accept", "Reject", "Uncertain", "Edit BBox...", "Scale BBox...", "Delete"],
        )
        for object_name in (
            "moltrack-edit-selected-detection-bbox-button",
            "moltrack-commit-detection-bbox-edit-button",
            "moltrack-delete-selected-detection-button",
            "moltrack-scale-selected-bbox-button",
            "moltrack-accept-selected-detection-button",
            "moltrack-reject-selected-detection-button",
            "moltrack-mark-uncertain-detection-button",
        ):
            self.assertIsNone(self.window.findChild(QPushButton, object_name))
        for object_name in (
            "moltrack-delete-current-status-button",
            "moltrack-delete-inside-selected-region-button",
            "moltrack-scale-current-frame-bboxes-button",
            "moltrack-scale-all-bboxes-button",
            "moltrack-accept-all-current-frame-button",
            "moltrack-accept-above-confidence-button",
        ):
            self.assertIsNotNone(self.window.findChild(QPushButton, object_name))

    def test_accept_selected_detection_updates_project_list_and_keeps_selection(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection

        detection = MolecularDetection(
            detection_id="det-candidate",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.876,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        project, _frames = _project_with_frames()
        project = project.with_molecular_detections((detection,))

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        self.window.detection_list.setCurrentRow(0)

        menu = self.window.build_detection_context_menu("det-candidate")
        self.addCleanup(menu.deleteLater)
        _trigger_menu_action(menu, "Accept")

        updated = self.window.current_project().molecular_detections_for_working_frame(1)[0]
        self.assertEqual(updated.review_status, DetectionReviewStatus.ACCEPTED)
        self.assertEqual(self.window.selected_molecular_detection_id(), "det-candidate")
        self.assertEqual(
            self.window.detection_list.item(0).text(),
            "det-candidate | accepted | conf=0.876 | region=-",
        )

    def test_reject_and_uncertain_selected_detection_buttons_update_status(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection

        detection = MolecularDetection(
            detection_id="det-candidate",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.876,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        project, _frames = _project_with_frames()
        project = project.with_molecular_detections((detection,))

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        self.window.detection_list.setCurrentRow(0)
        menu = self.window.build_detection_context_menu("det-candidate")
        self.addCleanup(menu.deleteLater)

        _trigger_menu_action(menu, "Reject")
        rejected = self.window.current_project().molecular_detections_for_working_frame(1)[0]
        self.assertEqual(rejected.review_status, DetectionReviewStatus.REJECTED)
        self.assertIn("det-candidate | rejected", self.window.detection_list.item(0).text())

        _trigger_menu_action(menu, "Uncertain")
        uncertain = self.window.current_project().molecular_detections_for_working_frame(1)[0]
        self.assertEqual(uncertain.review_status, DetectionReviewStatus.UNCERTAIN)
        self.assertIn("det-candidate | uncertain", self.window.detection_list.item(0).text())

    def test_accept_all_current_frame_updates_only_active_frame_detections(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection

        active_candidate = MolecularDetection(
            detection_id="active-candidate",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.6,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        active_uncertain = MolecularDetection(
            detection_id="active-uncertain",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(1.0, 1.0, 2.0, 2.0),
            confidence=0.7,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.UNCERTAIN,
            backend_name="yolo",
            run_mode="full_frame",
        )
        other_frame_candidate = MolecularDetection(
            detection_id="other-candidate",
            working_frame_index=2,
            source_frame_index=0,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.9,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        project, _frames = _project_with_frames()
        project = project.with_molecular_detections((active_candidate, active_uncertain, other_frame_candidate))

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)

        self.window.accept_all_current_frame_button.click()

        active_statuses = [
            detection.review_status
            for detection in self.window.current_project().molecular_detections_for_working_frame(1)
        ]
        other_status = self.window.current_project().molecular_detections_for_working_frame(2)[0].review_status
        self.assertEqual(active_statuses, [DetectionReviewStatus.ACCEPTED, DetectionReviewStatus.ACCEPTED])
        self.assertEqual(other_status, DetectionReviewStatus.CANDIDATE)
        self.assertIn("active-candidate | accepted", self.window.detection_list.item(0).text())
        self.assertIn("active-uncertain | accepted", self.window.detection_list.item(1).text())

    def test_accept_all_frames_updates_every_detection_in_project(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection

        active_candidate = MolecularDetection(
            detection_id="active-candidate",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.6,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        active_uncertain = MolecularDetection(
            detection_id="active-uncertain",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(1.0, 1.0, 2.0, 2.0),
            confidence=0.7,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.UNCERTAIN,
            backend_name="yolo",
            run_mode="full_frame",
        )
        other_frame_candidate = MolecularDetection(
            detection_id="other-candidate",
            working_frame_index=2,
            source_frame_index=0,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.9,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        project, _frames = _project_with_frames()
        project = project.with_molecular_detections((active_candidate, active_uncertain, other_frame_candidate))

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)

        self.window.accept_all_frames_button.click()

        statuses = [
            detection.review_status
            for detection in self.window.current_project().molecular_detections
        ]
        self.assertEqual(
            statuses,
            [
                DetectionReviewStatus.ACCEPTED,
                DetectionReviewStatus.ACCEPTED,
                DetectionReviewStatus.ACCEPTED,
            ],
        )
        self.assertIn("active-candidate | accepted", self.window.detection_list.item(0).text())
        self.assertIn("active-uncertain | accepted", self.window.detection_list.item(1).text())

    def test_accept_all_above_confidence_updates_only_matching_active_frame_detections(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection

        high_confidence = MolecularDetection(
            detection_id="high-confidence",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.86,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        low_confidence = MolecularDetection(
            detection_id="low-confidence",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(1.0, 1.0, 2.0, 2.0),
            confidence=0.73,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        other_frame_high_confidence = MolecularDetection(
            detection_id="other-high-confidence",
            working_frame_index=2,
            source_frame_index=0,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.91,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        project, _frames = _project_with_frames()
        project = project.with_molecular_detections(
            (high_confidence, low_confidence, other_frame_high_confidence)
        )

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        self.window.accept_confidence_threshold_spin.setValue(0.80)

        self.window.accept_above_confidence_button.click()

        active_detections = self.window.current_project().molecular_detections_for_working_frame(1)
        other_detection = self.window.current_project().molecular_detections_for_working_frame(2)[0]
        self.assertEqual(active_detections[0].review_status, DetectionReviewStatus.ACCEPTED)
        self.assertEqual(active_detections[1].review_status, DetectionReviewStatus.CANDIDATE)
        self.assertEqual(other_detection.review_status, DetectionReviewStatus.CANDIDATE)
        self.assertIn("high-confidence | accepted", self.window.detection_list.item(0).text())
        self.assertIn("low-confidence | candidate", self.window.detection_list.item(1).text())

    def test_manual_detection_from_drawn_bbox_creates_manual_detection_on_active_frame(self) -> None:
        from moltrack.core import DetectionReviewStatus

        project, _frames = _project_with_frames()

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        self.window.start_manual_detection_bbox((0.25, 0.5, 1.25, 1.75))

        self.window.commit_manual_detection_button.click()

        detections = self.window.current_project().molecular_detections_for_working_frame(1)
        self.assertEqual(len(detections), 1)
        detection = detections[0]
        self.assertEqual(detection.detection_id, "manual-w0001-0000")
        self.assertEqual(detection.working_frame_index, 1)
        self.assertEqual(detection.source_frame_index, 1)
        self.assertEqual(detection.bbox_xyxy, (0.25, 0.5, 1.25, 1.75))
        self.assertEqual(detection.confidence, 1.0)
        self.assertEqual(detection.model_name, "manual")
        self.assertEqual(detection.review_status, DetectionReviewStatus.MANUAL)
        self.assertEqual(detection.backend_name, "manual")
        self.assertEqual(detection.run_mode, "full_frame")
        self.assertEqual(self.window.selected_molecular_detection_id(), "manual-w0001-0000")
        self.assertEqual(
            self.window.detection_list.item(0).text(),
            "manual-w0001-0000 | manual | conf=1.000 | region=-",
        )

    def test_manual_detection_drawn_on_expanded_aligned_view_is_saved_in_native_coordinates(self) -> None:
        from moltrack.core import DetectionReviewStatus, RegistrationShift
        from nanotrack.core import STMSequenceMetadata
        from nanotrack.registration import ExpandedAlignedStack

        project, _frames = _project_with_frames()
        project = project.with_registration_shifts(
            (
                RegistrationShift(working_frame_index=0, dx=0.0, dy=0.0, method="identity"),
                RegistrationShift(working_frame_index=1, dx=3.0, dy=-2.0, method="manual"),
                RegistrationShift(working_frame_index=2, dx=7.0, dy=1.0, method="manual"),
            )
        )
        expanded = ExpandedAlignedStack(
            frames=np.ones((3, 8, 12), dtype=np.float32),
            canvas_offset_xy=(0.0, 2.0),
            padding_ltrb=(0, 2, 7, 1),
            frame_origins_xy=np.asarray([[0.0, 2.0], [3.0, 0.0], [7.0, 3.0]], dtype=np.float64),
            metadata=STMSequenceMetadata(pixels_x=12, pixels_y=8),
        )

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        with patch("moltrack.ui.main_window.expanded_registered_working_stack", return_value=expanded):
            self.window.show_expanded_aligned_action.setChecked(True)
            self.__class__._app.processEvents()
            self.window.start_manual_detection_bbox((4.0, 2.0, 6.0, 5.0))

            self.window.commit_manual_detection_button.click()

        detections = self.window.current_project().molecular_detections_for_working_frame(1)
        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0].bbox_xyxy, (1.0, 2.0, 3.0, 5.0))
        self.assertEqual(detections[0].review_status, DetectionReviewStatus.MANUAL)

    def test_edit_selected_candidate_detection_bbox_updates_bbox_and_marks_edited(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection

        detection = MolecularDetection(
            detection_id="det-candidate",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.72,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        project, _frames = _project_with_frames()
        project = project.with_molecular_detections((detection,))

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        self.window.select_molecular_detection("det-candidate")
        menu = self.window.build_detection_context_menu("det-candidate")
        self.addCleanup(menu.deleteLater)

        with patch(
            "moltrack.ui.main_window.DetectionBBoxDialog.get_bbox",
            return_value=(0.25, 0.5, 1.5, 1.75),
        ):
            _trigger_menu_action(menu, "Edit BBox...")

        updated = self.window.current_project().molecular_detections_for_working_frame(1)[0]
        self.assertEqual(updated.bbox_xyxy, (0.25, 0.5, 1.5, 1.75))
        self.assertEqual(updated.review_status, DetectionReviewStatus.EDITED)
        self.assertEqual(updated.backend_name, "yolo")
        self.assertEqual(self.window.selected_molecular_detection_id(), "det-candidate")
        self.assertEqual(
            self.window.detection_list.item(0).text(),
            "det-candidate | edited | conf=0.720 | region=-",
        )

    def test_editing_accepted_bbox_marks_edited_but_manual_bbox_stays_manual(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection

        accepted_detection = MolecularDetection(
            detection_id="det-accepted",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.82,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="yolo",
            run_mode="full_frame",
        )
        manual_detection = MolecularDetection(
            detection_id="det-manual",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(2.0, 2.0, 3.0, 3.0),
            confidence=1.0,
            model_name="manual",
            review_status=DetectionReviewStatus.MANUAL,
            backend_name="manual",
            run_mode="full_frame",
        )
        project, _frames = _project_with_frames()
        project = project.with_molecular_detections((accepted_detection, manual_detection))

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        self.window.select_molecular_detection("det-accepted")
        self.window.start_selected_detection_bbox_edit()
        self.window.commit_selected_detection_bbox_edit((0.25, 0.5, 1.5, 1.75))

        self.window.select_molecular_detection("det-manual")
        self.window.start_selected_detection_bbox_edit()
        self.window.commit_selected_detection_bbox_edit((2.25, 2.5, 3.5, 3.75))

        detections = self.window.current_project().molecular_detections_for_working_frame(1)
        self.assertEqual(detections[0].review_status, DetectionReviewStatus.EDITED)
        self.assertEqual(detections[0].bbox_xyxy, (0.25, 0.5, 1.5, 1.75))
        self.assertEqual(detections[1].review_status, DetectionReviewStatus.MANUAL)
        self.assertEqual(detections[1].bbox_xyxy, (2.25, 2.5, 3.5, 3.75))

    def test_editing_bbox_on_expanded_aligned_view_is_saved_in_native_coordinates(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection, RegistrationShift
        from nanotrack.core import STMSequenceMetadata
        from nanotrack.registration import ExpandedAlignedStack

        detection = MolecularDetection(
            detection_id="det-candidate",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.72,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        project, _frames = _project_with_frames()
        project = project.with_molecular_detections((detection,)).with_registration_shifts(
            (
                RegistrationShift(working_frame_index=0, dx=0.0, dy=0.0, method="identity"),
                RegistrationShift(working_frame_index=1, dx=3.0, dy=-2.0, method="manual"),
                RegistrationShift(working_frame_index=2, dx=7.0, dy=1.0, method="manual"),
            )
        )
        expanded = ExpandedAlignedStack(
            frames=np.ones((3, 8, 12), dtype=np.float32),
            canvas_offset_xy=(0.0, 2.0),
            padding_ltrb=(0, 2, 7, 1),
            frame_origins_xy=np.asarray([[0.0, 2.0], [3.0, 0.0], [7.0, 3.0]], dtype=np.float64),
            metadata=STMSequenceMetadata(pixels_x=12, pixels_y=8),
        )

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        self.window.select_molecular_detection("det-candidate")
        with patch("moltrack.ui.main_window.expanded_registered_working_stack", return_value=expanded):
            self.window.show_expanded_aligned_action.setChecked(True)
            self.__class__._app.processEvents()
            self.window.start_selected_detection_bbox_edit()

            self.window.commit_selected_detection_bbox_edit((4.0, 2.0, 6.0, 5.0))

        updated = self.window.current_project().molecular_detections_for_working_frame(1)[0]
        self.assertEqual(updated.bbox_xyxy, (1.0, 2.0, 3.0, 5.0))
        self.assertEqual(updated.review_status, DetectionReviewStatus.EDITED)

    def test_delete_selected_detection_removes_only_selected_detection(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection

        selected_detection = MolecularDetection(
            detection_id="det-delete",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.72,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        kept_detection = MolecularDetection(
            detection_id="det-keep",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(2.0, 2.0, 3.0, 3.0),
            confidence=0.91,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="yolo",
            run_mode="full_frame",
        )
        project, _frames = _project_with_frames()
        project = project.with_molecular_detections((selected_detection, kept_detection))

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        self.window.select_molecular_detection("det-delete")

        menu = self.window.build_detection_context_menu("det-delete")
        self.addCleanup(menu.deleteLater)
        _trigger_menu_action(menu, "Delete")

        detections = self.window.current_project().molecular_detections_for_working_frame(1)
        self.assertEqual(detections, (kept_detection,))
        self.assertIsNone(self.window.selected_molecular_detection_id())
        self.assertEqual(self.window.detection_list.count(), 1)
        self.assertIn("det-keep | accepted", self.window.detection_list.item(0).text())

    def test_delete_current_frame_detections_by_status_removes_only_matching_active_frame_status(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection

        active_candidate = MolecularDetection(
            detection_id="active-candidate",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.72,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        active_accepted = MolecularDetection(
            detection_id="active-accepted",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(1.0, 1.0, 2.0, 2.0),
            confidence=0.91,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="yolo",
            run_mode="full_frame",
        )
        other_frame_candidate = MolecularDetection(
            detection_id="other-candidate",
            working_frame_index=2,
            source_frame_index=0,
            bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
            confidence=0.88,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        project, _frames = _project_with_frames()
        project = project.with_molecular_detections(
            (active_candidate, active_accepted, other_frame_candidate)
        )

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        self.window.delete_status_combo.setCurrentIndex(
            self.window.delete_status_combo.findData(DetectionReviewStatus.CANDIDATE.value)
        )

        self.window.delete_current_status_button.click()

        active_detections = self.window.current_project().molecular_detections_for_working_frame(1)
        other_detections = self.window.current_project().molecular_detections_for_working_frame(2)
        self.assertEqual(active_detections, (active_accepted,))
        self.assertEqual(other_detections, (other_frame_candidate,))
        self.assertEqual(self.window.detection_list.count(), 1)
        self.assertIn("active-accepted | accepted", self.window.detection_list.item(0).text())

    def test_delete_detections_inside_selected_region_removes_only_active_frame_centroid_matches(self) -> None:
        from moltrack.core import AnalysisRegion, DetectionReviewStatus, MolecularDetection

        roi = AnalysisRegion.rectangle(
            kind="terrace",
            name="ROI A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(0.0, 0.0, 2.0, 2.0),
        )
        inside_active = MolecularDetection(
            detection_id="inside-active",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.25, 0.25, 1.0, 1.0),
            confidence=0.72,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        outside_active = MolecularDetection(
            detection_id="outside-active",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(3.0, 3.0, 4.0, 4.0),
            confidence=0.91,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="yolo",
            run_mode="full_frame",
        )
        inside_other_frame = MolecularDetection(
            detection_id="inside-other-frame",
            working_frame_index=2,
            source_frame_index=0,
            bbox_xyxy=(0.25, 0.25, 1.0, 1.0),
            confidence=0.88,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        project, _frames = _project_with_frames()
        project = project.with_analysis_regions(
            (roi,),
            molecular_detections=(inside_active, outside_active, inside_other_frame),
        )

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        self.window.select_analysis_region("ROI A")

        self.window.delete_inside_selected_region_button.click()

        active_detections = self.window.current_project().molecular_detections_for_working_frame(1)
        other_detections = self.window.current_project().molecular_detections_for_working_frame(2)
        self.assertEqual(active_detections, (outside_active,))
        self.assertEqual(other_detections, (inside_other_frame,))
        self.assertEqual(self.window.detection_list.count(), 1)
        self.assertIn("outside-active | accepted", self.window.detection_list.item(0).text())

    def test_scale_selected_detection_bbox_scales_around_bbox_center_and_marks_edited(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection

        selected_detection = MolecularDetection(
            detection_id="det-scale",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(1.0, 2.0, 5.0, 6.0),
            confidence=0.72,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        kept_detection = MolecularDetection(
            detection_id="det-keep",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(10.0, 10.0, 12.0, 12.0),
            confidence=0.91,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="yolo",
            run_mode="full_frame",
        )
        project, _frames = _project_with_frames()
        project = project.with_molecular_detections((selected_detection, kept_detection))

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        self.window.select_molecular_detection("det-scale")

        menu = self.window.build_detection_context_menu("det-scale")
        self.addCleanup(menu.deleteLater)
        with patch("moltrack.ui.main_window.DetectionScaleDialog.get_scale_factor", return_value=1.5):
            _trigger_menu_action(menu, "Scale BBox...")

        scaled_detection, unchanged_detection = self.window.current_project().molecular_detections_for_working_frame(1)
        self.assertEqual(scaled_detection.detection_id, "det-scale")
        self.assertEqual(scaled_detection.bbox_xyxy, (0.0, 1.0, 6.0, 7.0))
        self.assertEqual(scaled_detection.review_status, DetectionReviewStatus.EDITED)
        self.assertEqual(unchanged_detection, kept_detection)
        self.assertEqual(self.window.selected_molecular_detection_id(), "det-scale")
        self.assertIn("det-scale | edited", self.window.detection_list.item(0).text())

    def test_scale_current_frame_detection_bboxes_scales_only_active_working_frame(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection

        active_candidate = MolecularDetection(
            detection_id="active-candidate",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(0.0, 0.0, 4.0, 4.0),
            confidence=0.72,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        active_manual = MolecularDetection(
            detection_id="active-manual",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(4.0, 4.0, 8.0, 6.0),
            confidence=1.0,
            model_name="manual",
            review_status=DetectionReviewStatus.MANUAL,
            backend_name="manual",
            run_mode="full_frame",
        )
        other_frame_accepted = MolecularDetection(
            detection_id="other-accepted",
            working_frame_index=2,
            source_frame_index=0,
            bbox_xyxy=(0.0, 0.0, 4.0, 4.0),
            confidence=0.91,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="yolo",
            run_mode="full_frame",
        )
        project, _frames = _project_with_frames()
        project = project.with_molecular_detections(
            (active_candidate, active_manual, other_frame_accepted)
        )

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        self.window.scale_bbox_factor_spin.setValue(0.5)

        self.window.scale_current_frame_bboxes_button.click()

        active_detections = self.window.current_project().molecular_detections_for_working_frame(1)
        other_detections = self.window.current_project().molecular_detections_for_working_frame(2)
        self.assertEqual(active_detections[0].bbox_xyxy, (1.0, 1.0, 3.0, 3.0))
        self.assertEqual(active_detections[0].review_status, DetectionReviewStatus.EDITED)
        self.assertEqual(active_detections[1].bbox_xyxy, (5.0, 4.5, 7.0, 5.5))
        self.assertEqual(active_detections[1].review_status, DetectionReviewStatus.MANUAL)
        self.assertEqual(other_detections, (other_frame_accepted,))
        self.assertEqual(self.window.detection_list.count(), 2)

    def test_scale_all_detection_bboxes_scales_every_working_frame(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection

        active_candidate = MolecularDetection(
            detection_id="active-candidate",
            working_frame_index=1,
            source_frame_index=1,
            bbox_xyxy=(2.0, 2.0, 4.0, 4.0),
            confidence=0.72,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
        )
        other_frame_accepted = MolecularDetection(
            detection_id="other-accepted",
            working_frame_index=2,
            source_frame_index=0,
            bbox_xyxy=(10.0, 10.0, 12.0, 16.0),
            confidence=0.91,
            model_name="moltrack_model.pt",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="yolo",
            run_mode="full_frame",
        )
        project, _frames = _project_with_frames()
        project = project.with_molecular_detections((active_candidate, other_frame_accepted))

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        self.window.select_molecular_detection("active-candidate")
        self.window.scale_bbox_factor_spin.setValue(2.0)

        self.window.scale_all_bboxes_button.click()

        active_detection = self.window.current_project().molecular_detections_for_working_frame(1)[0]
        other_detection = self.window.current_project().molecular_detections_for_working_frame(2)[0]
        self.assertEqual(active_detection.bbox_xyxy, (1.0, 1.0, 5.0, 5.0))
        self.assertEqual(active_detection.review_status, DetectionReviewStatus.EDITED)
        self.assertEqual(other_detection.bbox_xyxy, (9.0, 7.0, 13.0, 19.0))
        self.assertEqual(other_detection.review_status, DetectionReviewStatus.EDITED)
        self.assertEqual(self.window.selected_molecular_detection_id(), "active-candidate")
        self.assertIn("active-candidate | edited", self.window.detection_list.item(0).text())

    def test_add_rect_region_action_adds_dialog_region_to_project_and_list(self) -> None:
        from moltrack.core import AnalysisRegion

        project, _frames = _project_with_frames()
        region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(1.0, 2.0, 5.0, 7.0),
        )

        self.window.set_project(project)
        with (
            patch("moltrack.ui.main_window.AnalysisRegionRectDialog.get_region", return_value=region) as dialog_mock,
            patch.object(self.window.viewer, "add_polyline_nm", return_value=object()) as add_mock,
        ):
            self.window.add_rect_region_action.trigger()

        dialog_mock.assert_called_once()
        self.assertEqual(self.window.analysis_regions(), [region])
        self.assertEqual(self.window.current_project().analysis_regions, (region,))
        self.assertEqual(self.window.region_list.count(), 1)
        self.assertEqual(self.window.region_list.item(0).text(), "Terrace A")
        add_mock.assert_called_once()

    def test_rect_region_dialog_builds_region_from_form_values(self) -> None:
        from moltrack.ui.main_window import AnalysisRegionRectDialog

        dialog = AnalysisRegionRectDialog(self.window)
        self.addCleanup(dialog.deleteLater)
        dialog.kind_combo.setCurrentIndex(dialog.kind_combo.findData("ignore"))
        dialog.name_edit.setText("Ignore edge")
        dialog.red_spin.setValue(240)
        dialog.green_spin.setValue(40)
        dialog.blue_spin.setValue(20)
        dialog.x0_spin.setValue(1.0)
        dialog.y0_spin.setValue(2.0)
        dialog.x1_spin.setValue(5.0)
        dialog.y1_spin.setValue(7.0)

        region = dialog.to_region()

        self.assertEqual(region.kind.value, "ignore")
        self.assertEqual(region.name, "Ignore edge")
        self.assertEqual(region.color_rgb, (240, 40, 20))
        self.assertEqual(region.rect_xyxy, (1.0, 2.0, 5.0, 7.0))

    def test_rect_region_dialog_rejects_invalid_geometry_without_traceback(self) -> None:
        from moltrack.ui.main_window import AnalysisRegionRectDialog

        dialog = AnalysisRegionRectDialog(self.window)
        self.addCleanup(dialog.deleteLater)
        dialog.name_edit.setText("Bad rect")
        dialog.x0_spin.setValue(5.0)
        dialog.y0_spin.setValue(2.0)
        dialog.x1_spin.setValue(1.0)
        dialog.y1_spin.setValue(7.0)

        with patch("moltrack.ui.main_window.QMessageBox.warning") as warning_mock:
            dialog.accept()

        warning_mock.assert_called_once()
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)

    def test_draw_rect_roi_commit_action_adds_region_from_viewer_roi(self) -> None:
        project, _frames = _project_with_frames()

        self.window.set_project(project)
        self.window.start_rect_region_roi((1.0, 2.0, 5.0, 7.0))
        with (
            patch(
                "moltrack.ui.main_window.AnalysisRegionMetadataDialog.get_metadata",
                return_value=("terrace", "ROI Terrace", (20, 120, 240)),
            ) as dialog_mock,
            patch.object(self.window.viewer, "add_polyline_nm", return_value=object()) as add_mock,
        ):
            self.window.commit_drawn_region_action.trigger()

        dialog_mock.assert_called_once()
        self.assertEqual(self.window.analysis_regions()[0].name, "ROI Terrace")
        self.assertEqual(self.window.analysis_regions()[0].rect_xyxy, (1.0, 2.0, 5.0, 7.0))
        self.assertIsNone(self.window.active_region_roi_kind())
        add_mock.assert_called_once()

    def test_draw_polyline_region_commit_action_adds_polygon_region_from_viewer_roi(self) -> None:
        project, _frames = _project_with_frames()

        self.window.set_project(project)
        self.window.start_polyline_region_roi([(1.0, 2.0), (5.0, 2.0), (3.0, 7.0)])
        with (
            patch(
                "moltrack.ui.main_window.AnalysisRegionMetadataDialog.get_metadata",
                return_value=("ignore", "Polyline Ignore", (240, 40, 40)),
            ),
            patch.object(self.window.viewer, "add_polyline_nm", return_value=object()),
        ):
            self.window.commit_drawn_region_action.trigger()

        region = self.window.analysis_regions()[0]
        self.assertEqual(region.name, "Polyline Ignore")
        self.assertEqual(region.kind.value, "ignore")
        np.testing.assert_allclose(region.polygon_xy, np.asarray([(1.0, 2.0), (5.0, 2.0), (3.0, 7.0)]))
        self.assertIsNone(self.window.active_region_roi_kind())

    def test_edit_selected_region_action_updates_region_project_and_list(self) -> None:
        from moltrack.core import AnalysisRegion

        project, _frames = _project_with_frames()
        original = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(1.0, 2.0, 5.0, 7.0),
        )
        updated = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace moved",
            color_rgb=(20, 120, 240),
            rect_xyxy=(2.0, 3.0, 6.0, 8.0),
        )

        self.window.set_project(project)
        with (
            patch.object(self.window.viewer, "add_polyline_nm", side_effect=[object(), object()]),
            patch.object(self.window.viewer, "remove_item"),
        ):
            self.window.add_analysis_region(original)
            self.window.select_analysis_region("Terrace A")
            with patch("moltrack.ui.main_window.AnalysisRegionRectDialog.get_region", return_value=updated) as dialog_mock:
                self.window.edit_selected_region_action.trigger()

        dialog_mock.assert_called_once_with(self.window, original)
        self.assertEqual(self.window.analysis_regions(), [updated])
        self.assertEqual(self.window.current_project().analysis_regions, (updated,))
        self.assertEqual(self.window.region_list.count(), 1)
        self.assertEqual(self.window.region_list.item(0).text(), "Terrace moved")
        self.assertEqual(self.window.selected_region_name(), "Terrace moved")

    def test_delete_selected_region_action_removes_region_from_project_and_list(self) -> None:
        from moltrack.core import AnalysisRegion

        project, _frames = _project_with_frames()
        region = AnalysisRegion.rectangle(
            kind="ignore",
            name="Ignore A",
            color_rgb=(240, 40, 40),
            rect_xyxy=(1.0, 2.0, 5.0, 7.0),
        )
        overlay_item = object()

        self.window.set_project(project)
        with (
            patch.object(self.window.viewer, "add_polyline_nm", return_value=overlay_item),
            patch.object(self.window.viewer, "remove_item") as remove_mock,
        ):
            self.window.add_analysis_region(region)
            self.window.select_analysis_region("Ignore A")
            self.window.delete_selected_region_action.trigger()

        self.assertEqual(self.window.analysis_regions(), [])
        self.assertEqual(self.window.current_project().analysis_regions, ())
        self.assertEqual(self.window.region_list.count(), 0)
        remove_mock.assert_called_once_with(overlay_item)

    def test_copy_selected_region_to_series_action_marks_region_as_copied(self) -> None:
        from moltrack.core import AnalysisRegion

        project, _frames = _project_with_frames()
        region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(1.0, 2.0, 5.0, 7.0),
        )

        self.window.set_project(project)
        with patch.object(self.window.viewer, "add_polyline_nm", return_value=object()):
            self.window.add_analysis_region(region)
        self.window.select_analysis_region("Terrace A")
        self.window.copy_selected_region_to_series_action.trigger()

        self.assertEqual(len(self.window.copied_analysis_regions()), 1)
        self.assertEqual(self.window.copied_analysis_regions()[0].region.name, "Terrace A")
        self.assertEqual(self.window.copied_analysis_regions()[0].working_frame_indices, (0, 1, 2))
        self.assertEqual(len(self.window.current_project().copied_analysis_regions), 1)

    def test_run_registration_action_uses_selected_backend_and_shows_expanded_aligned_by_default(self) -> None:
        from moltrack.core import RegistrationShift
        from nanotrack.core import STMSequenceMetadata
        from nanotrack.registration import ExpandedAlignedStack

        project, _frames = _project_with_frames()
        registered_project = project.with_registration_shifts(
            (
                RegistrationShift(working_frame_index=0, dx=0.0, dy=0.0, method="identity"),
                RegistrationShift(working_frame_index=1, dx=1.25, dy=-0.5, method="optical_flow_median_adjacent"),
                RegistrationShift(working_frame_index=2, dx=1.5, dy=-0.25, method="optical_flow_median_adjacent"),
            )
        )
        expanded = ExpandedAlignedStack(
            frames=np.asarray(
                [
                    [[1.0, 1.0, 1.0]],
                    [[2.0, 2.0, 2.0]],
                    [[3.0, 3.0, 3.0]],
                ],
                dtype=np.float32,
            ),
            canvas_offset_xy=(0.0, 1.0),
            padding_ltrb=(0, 1, 1, 0),
            frame_origins_xy=np.asarray([[0.0, 1.0], [1.25, 0.5], [1.5, 0.75]], dtype=np.float64),
            metadata=STMSequenceMetadata(pixels_x=3, pixels_y=1),
        )

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        self.window.registration_backend_combo.setCurrentIndex(1)
        with (
            patch("moltrack.ui.main_window.run_project_registration", return_value=registered_project) as run_mock,
            patch("moltrack.ui.main_window.expanded_registered_working_stack", return_value=expanded) as expanded_mock,
        ):
            self.window.run_registration_action.trigger()

        run_mock.assert_called_once_with(project, backend="optical_flow_median", progress_callback=ANY)
        expanded_mock.assert_called()
        self.assertIs(self.window.current_project(), registered_project)
        self.assertEqual(self.window.active_working_frame_index(), 1)
        self.assertIn("Registration dx=1.250px dy=-0.500px", self.window.frame_index_text())
        self.assertIn("Expanded aligned view", self.window.frame_index_text())
        self.assertTrue(self.window.show_expanded_aligned_action.isChecked())
        np.testing.assert_array_equal(self.window.displayed_frame(), expanded.frames[1])

    def test_run_registration_action_shows_progress_dialog_and_updates_from_callback(self) -> None:
        from moltrack.core import RegistrationShift
        from nanotrack.core import STMSequenceMetadata
        from nanotrack.registration import ExpandedAlignedStack

        class FakeProgressDialog:
            instances = []

            def __init__(self, label, cancel_text, minimum, maximum, parent):
                self.label = label
                self.cancel_text = cancel_text
                self.minimum = minimum
                self.maximum = maximum
                self.parent = parent
                self.values = []
                self.labels = []
                self.closed = False
                FakeProgressDialog.instances.append(self)

            def setWindowTitle(self, title):
                self.window_title = title

            def setWindowModality(self, modality):
                self.modality = modality

            def setCancelButton(self, button):
                self.cancel_button = button

            def setMinimumDuration(self, duration):
                self.minimum_duration = duration

            def setAutoClose(self, auto_close):
                self.auto_close = auto_close

            def setAutoReset(self, auto_reset):
                self.auto_reset = auto_reset

            def setValue(self, value):
                self.values.append(int(value))

            def setMaximum(self, maximum):
                self.maximum = int(maximum)

            def setLabelText(self, label):
                self.labels.append(label)

            def close(self):
                self.closed = True

        project, _frames = _project_with_frames()
        registered_project = project.with_registration_shifts(
            (
                RegistrationShift(working_frame_index=0, dx=0.0, dy=0.0, method="identity"),
                RegistrationShift(working_frame_index=1, dx=1.0, dy=0.0, method="phase_correlation_adjacent"),
                RegistrationShift(working_frame_index=2, dx=2.0, dy=0.0, method="phase_correlation_adjacent"),
            )
        )
        expanded = ExpandedAlignedStack(
            frames=np.ones((3, 2, 2), dtype=np.float32),
            canvas_offset_xy=(0.0, 0.0),
            padding_ltrb=(0, 0, 0, 0),
            frame_origins_xy=np.zeros((3, 2), dtype=np.float64),
            metadata=STMSequenceMetadata(pixels_x=2, pixels_y=2),
        )

        def run_with_progress(_project, *, backend, progress_callback):
            progress_callback(1, 3, registered_project.registration_shift_for_working_frame(0))
            progress_callback(2, 3, registered_project.registration_shift_for_working_frame(1))
            progress_callback(3, 3, registered_project.registration_shift_for_working_frame(2))
            return registered_project

        self.window.set_project(project)
        with (
            patch("moltrack.ui.main_window.QProgressDialog", FakeProgressDialog),
            patch("moltrack.ui.main_window.QApplication.processEvents") as process_events_mock,
            patch("moltrack.ui.main_window.run_project_registration", side_effect=run_with_progress),
            patch("moltrack.ui.main_window.expanded_registered_working_stack", return_value=expanded),
        ):
            self.window.run_registration_action.trigger()

        progress = FakeProgressDialog.instances[0]
        self.assertEqual(progress.label, "Running Phase registration...")
        self.assertEqual(progress.maximum, 3)
        self.assertEqual(progress.values, [0, 1, 2, 3, 3])
        self.assertEqual(progress.labels[-1], "Running Phase registration... 3/3")
        self.assertTrue(progress.closed)
        self.assertEqual(process_events_mock.call_count, 3)

    def test_show_expanded_aligned_action_displays_expanded_frame_without_changing_native_project(self) -> None:
        from moltrack.core import RegistrationShift
        from nanotrack.core import STMSequenceMetadata
        from nanotrack.registration import ExpandedAlignedStack

        project, frames = _project_with_frames()
        project = project.with_registration_shifts(
            (
                RegistrationShift(working_frame_index=0, dx=0.0, dy=0.0, method="identity"),
                RegistrationShift(working_frame_index=1, dx=1.0, dy=0.0, method="manual"),
                RegistrationShift(working_frame_index=2, dx=0.0, dy=0.0, method="manual"),
            )
        )
        expanded = ExpandedAlignedStack(
            frames=np.asarray(
                [
                    [[100.0, 101.0, 102.0]],
                    [[200.0, 201.0, 202.0]],
                    [[300.0, 301.0, 302.0]],
                ],
                dtype=np.float32,
            ),
            canvas_offset_xy=(0.0, 0.0),
            padding_ltrb=(0, 0, 1, 0),
            frame_origins_xy=np.asarray([[0.0, 0.0], [1.0, 0.0], [0.0, 0.0]], dtype=np.float64),
            metadata=STMSequenceMetadata(pixels_x=3, pixels_y=1),
        )

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        native_frame = self.window.displayed_frame().copy()

        with patch("moltrack.ui.main_window.expanded_registered_working_stack", return_value=expanded) as expanded_mock:
            self.window.show_expanded_aligned_action.setChecked(True)
            self.__class__._app.processEvents()

        expanded_mock.assert_called_once_with(project)
        np.testing.assert_array_equal(self.window.displayed_frame(), expanded.frames[1])
        self.assertIn("Expanded aligned view", self.window.frame_index_text())
        np.testing.assert_array_equal(project.source_series.raw_frames, frames)

        self.window.show_expanded_aligned_action.setChecked(False)
        self.__class__._app.processEvents()

        np.testing.assert_array_equal(self.window.displayed_frame(), native_frame)
        self.assertNotIn("Expanded aligned view", self.window.frame_index_text())

    def test_expanded_aligned_view_draws_analysis_region_overlay_with_frame_origin_offset(self) -> None:
        from moltrack.core import AnalysisRegion, RegistrationShift
        from nanotrack.core import STMSequenceMetadata
        from nanotrack.registration import ExpandedAlignedStack

        project, _frames = _project_with_frames()
        project = project.with_registration_shifts(
            (
                RegistrationShift(working_frame_index=0, dx=0.0, dy=0.0, method="identity"),
                RegistrationShift(working_frame_index=1, dx=1.5, dy=-2.0, method="manual"),
                RegistrationShift(working_frame_index=2, dx=0.0, dy=0.0, method="manual"),
            )
        )
        region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(1.0, 2.0, 5.0, 7.0),
        )
        expanded = ExpandedAlignedStack(
            frames=np.ones((3, 4, 7), dtype=np.float32),
            canvas_offset_xy=(2.0, 1.0),
            padding_ltrb=(2, 1, 0, 0),
            frame_origins_xy=np.asarray([[2.0, 1.0], [3.5, -1.0], [2.0, 1.0]], dtype=np.float64),
            metadata=STMSequenceMetadata(pixels_x=7, pixels_y=4),
        )

        self.window.set_project(project)
        self.window.add_analysis_region(region)
        self.window.set_active_working_frame_index(1)
        with (
            patch("moltrack.ui.main_window.expanded_registered_working_stack", return_value=expanded),
            patch.object(self.window.viewer, "add_polyline_nm", return_value=object()) as add_mock,
        ):
            self.window.show_expanded_aligned_action.setChecked(True)
            self.__class__._app.processEvents()

        pts = add_mock.call_args.args[0]
        np.testing.assert_allclose(
            pts,
            np.asarray(
                [
                    [4.5, 1.0],
                    [8.5, 1.0],
                    [8.5, 6.0],
                    [4.5, 6.0],
                    [4.5, 1.0],
                ],
                dtype=np.float64,
            ),
        )
        self.assertEqual(region.rect_xyxy, (1.0, 2.0, 5.0, 7.0))

    def test_commit_drawn_region_in_fixed_expanded_mode_stays_fixed_when_changing_frames(self) -> None:
        from moltrack.core import RegistrationShift
        from nanotrack.core import STMSequenceMetadata
        from nanotrack.registration import ExpandedAlignedStack

        project, _frames = _project_with_frames()
        project = project.with_registration_shifts(
            (
                RegistrationShift(working_frame_index=0, dx=0.0, dy=0.0, method="identity"),
                RegistrationShift(working_frame_index=1, dx=3.0, dy=-2.0, method="manual"),
                RegistrationShift(working_frame_index=2, dx=7.0, dy=1.0, method="manual"),
            )
        )
        expanded = ExpandedAlignedStack(
            frames=np.ones((3, 8, 12), dtype=np.float32),
            canvas_offset_xy=(0.0, 2.0),
            padding_ltrb=(0, 2, 7, 1),
            frame_origins_xy=np.asarray([[0.0, 2.0], [3.0, 0.0], [7.0, 3.0]], dtype=np.float64),
            metadata=STMSequenceMetadata(pixels_x=12, pixels_y=8),
        )

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        with patch("moltrack.ui.main_window.expanded_registered_working_stack", return_value=expanded):
            self.window.show_expanded_aligned_action.setChecked(True)
            self.window.start_rect_region_roi((10.0, 20.0, 14.0, 25.0))
            with (
                patch(
                    "moltrack.ui.main_window.AnalysisRegionMetadataDialog.get_metadata",
                    return_value=("terrace", "Aligned Terrace", (20, 120, 240)),
                ),
                patch.object(self.window.viewer, "add_polyline_nm", return_value=object()) as add_mock,
            ):
                self.window.commit_drawn_region_action.trigger()

        region = self.window.analysis_regions()[0]
        self.assertEqual(region.rect_xyxy, (7.0, 20.0, 11.0, 25.0))
        self.assertEqual(len(self.window.current_project().frame_scoped_analysis_regions), 3)
        self.assertEqual(
            self.window.current_project().region_for_working_frame("Aligned Terrace", 0).rect_xyxy,
            (10.0, 18.0, 14.0, 23.0),
        )
        self.assertEqual(
            self.window.current_project().region_for_working_frame("Aligned Terrace", 1).rect_xyxy,
            (7.0, 20.0, 11.0, 25.0),
        )
        self.assertEqual(
            self.window.current_project().region_for_working_frame("Aligned Terrace", 2).rect_xyxy,
            (3.0, 17.0, 7.0, 22.0),
        )
        pts = add_mock.call_args.args[0]
        np.testing.assert_allclose(
            pts,
            np.asarray(
                [
                    [10.0, 20.0],
                    [14.0, 20.0],
                    [14.0, 25.0],
                    [10.0, 25.0],
                    [10.0, 20.0],
                ],
                dtype=np.float64,
            ),
        )
        for frame_index in range(3):
            self.window.set_active_working_frame_index(frame_index)
            region = self.window.current_project().region_for_working_frame("Aligned Terrace", frame_index)
            display_rect = self.window._region_to_expanded_canvas(region, frame_index).rect_xyxy
            self.assertEqual(display_rect, (10.0, 20.0, 14.0, 25.0))

    def test_copy_region_to_series_in_expanded_aligned_view_keeps_region_fixed_on_canvas(self) -> None:
        from moltrack.core import AnalysisRegion, RegistrationShift
        from nanotrack.core import STMSequenceMetadata
        from nanotrack.registration import ExpandedAlignedStack

        project, _frames = _project_with_frames()
        project = project.with_registration_shifts(
            (
                RegistrationShift(working_frame_index=0, dx=0.0, dy=0.0, method="identity"),
                RegistrationShift(working_frame_index=1, dx=3.0, dy=-2.0, method="manual"),
                RegistrationShift(working_frame_index=2, dx=7.0, dy=1.0, method="manual"),
            )
        )
        expanded = ExpandedAlignedStack(
            frames=np.ones((3, 8, 12), dtype=np.float32),
            canvas_offset_xy=(0.0, 2.0),
            padding_ltrb=(0, 2, 7, 1),
            frame_origins_xy=np.asarray([[0.0, 2.0], [3.0, 0.0], [7.0, 3.0]], dtype=np.float64),
            metadata=STMSequenceMetadata(pixels_x=12, pixels_y=8),
        )
        active_native_region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Aligned Terrace",
            color_rgb=(20, 120, 240),
            rect_xyxy=(7.0, 20.0, 11.0, 25.0),
        )

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        with (
            patch("moltrack.ui.main_window.expanded_registered_working_stack", return_value=expanded),
            patch.object(self.window.viewer, "add_polyline_nm", return_value=object()),
        ):
            self.window.show_expanded_aligned_action.setChecked(True)
            self.window.add_analysis_region(active_native_region)
            self.window.select_analysis_region("Aligned Terrace")
            copied = self.window.copy_analysis_region_to_series("Aligned Terrace")

        self.assertIsNone(copied)
        self.assertEqual(self.window.copied_analysis_regions(), [])
        self.assertEqual(len(self.window.current_project().frame_scoped_analysis_regions), 3)
        self.assertEqual(
            self.window.current_project().region_for_working_frame("Aligned Terrace", 0).rect_xyxy,
            (10.0, 18.0, 14.0, 23.0),
        )
        self.assertEqual(
            self.window.current_project().region_for_working_frame("Aligned Terrace", 1).rect_xyxy,
            (7.0, 20.0, 11.0, 25.0),
        )
        self.assertEqual(
            self.window.current_project().region_for_working_frame("Aligned Terrace", 2).rect_xyxy,
            (3.0, 17.0, 7.0, 22.0),
        )
        for frame_index in range(3):
            region = self.window.current_project().region_for_working_frame("Aligned Terrace", frame_index)
            display_rect = self.window._region_to_expanded_canvas(region, frame_index).rect_xyxy
            self.assertEqual(display_rect, (10.0, 20.0, 14.0, 25.0))

    def test_copy_region_to_series_in_move_with_image_mode_reuses_native_geometry(self) -> None:
        from moltrack.core import AnalysisRegion, RegistrationShift
        from nanotrack.core import STMSequenceMetadata
        from nanotrack.registration import ExpandedAlignedStack

        project, _frames = _project_with_frames()
        project = project.with_registration_shifts(
            (
                RegistrationShift(working_frame_index=0, dx=0.0, dy=0.0, method="identity"),
                RegistrationShift(working_frame_index=1, dx=3.0, dy=-2.0, method="manual"),
                RegistrationShift(working_frame_index=2, dx=7.0, dy=1.0, method="manual"),
            )
        )
        expanded = ExpandedAlignedStack(
            frames=np.ones((3, 8, 12), dtype=np.float32),
            canvas_offset_xy=(0.0, 2.0),
            padding_ltrb=(0, 2, 7, 1),
            frame_origins_xy=np.asarray([[0.0, 2.0], [3.0, 0.0], [7.0, 3.0]], dtype=np.float64),
            metadata=STMSequenceMetadata(pixels_x=12, pixels_y=8),
        )
        active_native_region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Moving Terrace",
            color_rgb=(20, 120, 240),
            rect_xyxy=(7.0, 20.0, 11.0, 25.0),
        )

        self.window.set_project(project)
        mode_index = self.window.expanded_region_mode_combo.findData("move_with_image")
        self.assertGreaterEqual(mode_index, 0)
        self.window.expanded_region_mode_combo.setCurrentIndex(mode_index)
        self.window.set_active_working_frame_index(1)
        with (
            patch("moltrack.ui.main_window.expanded_registered_working_stack", return_value=expanded),
            patch.object(self.window.viewer, "add_polyline_nm", return_value=object()),
        ):
            self.window.show_expanded_aligned_action.setChecked(True)
            self.window.add_analysis_region(active_native_region)
            self.window.select_analysis_region("Moving Terrace")
            copied = self.window.copy_analysis_region_to_series("Moving Terrace")

        self.assertIsNotNone(copied)
        self.assertEqual(copied.working_frame_indices, (0, 1, 2))
        self.assertEqual(self.window.frame_scoped_analysis_regions(), [])
        self.assertEqual(
            self.window.current_project().region_for_working_frame("Moving Terrace", 0).rect_xyxy,
            (7.0, 20.0, 11.0, 25.0),
        )
        self.assertEqual(
            self.window.current_project().region_for_working_frame("Moving Terrace", 2).rect_xyxy,
            (7.0, 20.0, 11.0, 25.0),
        )
        display_rect_0 = self.window._region_to_expanded_canvas(active_native_region, 0).rect_xyxy
        display_rect_2 = self.window._region_to_expanded_canvas(active_native_region, 2).rect_xyxy
        self.assertEqual(display_rect_0, (7.0, 22.0, 11.0, 27.0))
        self.assertEqual(display_rect_2, (14.0, 23.0, 18.0, 28.0))

    def test_apply_selected_region_to_current_frame_creates_frame_scope(self) -> None:
        from moltrack.core import AnalysisRegion

        project, _frames = _project_with_frames()
        region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(1.0, 2.0, 5.0, 7.0),
        )

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        with patch.object(self.window.viewer, "add_polyline_nm", return_value=object()):
            self.window.add_analysis_region(region)
        self.window.select_analysis_region("Terrace A")
        self.window.apply_selected_region_to_current_frame_action.trigger()

        self.assertEqual(len(self.window.current_project().frame_scoped_analysis_regions), 1)
        self.assertEqual(
            self.window.current_project().frame_scoped_analysis_regions[0].working_frame_indices,
            (1,),
        )

    def test_copy_selected_region_from_current_to_end_creates_frame_scope(self) -> None:
        from moltrack.core import AnalysisRegion

        project, _frames = _project_with_frames()
        region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(1.0, 2.0, 5.0, 7.0),
        )

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        with patch.object(self.window.viewer, "add_polyline_nm", return_value=object()):
            self.window.add_analysis_region(region)
        self.window.select_analysis_region("Terrace A")
        self.window.copy_selected_region_from_current_to_end_action.trigger()

        self.assertEqual(
            self.window.current_project().frame_scoped_analysis_regions[0].working_frame_indices,
            (1, 2),
        )

    def test_copy_selected_region_to_frame_range_uses_dialog_scope(self) -> None:
        from moltrack.core import AnalysisRegion

        project, _frames = _project_with_frames()
        region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(1.0, 2.0, 5.0, 7.0),
        )

        self.window.set_project(project)
        with patch.object(self.window.viewer, "add_polyline_nm", return_value=object()):
            self.window.add_analysis_region(region)
        self.window.select_analysis_region("Terrace A")
        with patch("moltrack.ui.main_window.AnalysisRegionFrameRangeDialog.get_working_frame_indices", return_value=(0, 2)):
            self.window.copy_selected_region_to_frame_range_action.trigger()

        self.assertEqual(
            self.window.current_project().frame_scoped_analysis_regions[0].working_frame_indices,
            (0, 2),
        )

    def test_commit_drawn_region_with_existing_name_adds_frame_scoped_geometry(self) -> None:
        from moltrack.core import AnalysisRegion

        project, _frames = _project_with_frames()
        early_region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace 1",
            color_rgb=(20, 120, 240),
            rect_xyxy=(1.0, 2.0, 5.0, 7.0),
        )

        self.window.set_project(project)
        self.window.set_active_working_frame_index(1)
        with patch.object(self.window.viewer, "add_polyline_nm", return_value=object()):
            self.window.add_analysis_region(early_region)
        self.window.start_rect_region_roi((10.0, 12.0, 15.0, 17.0))
        with (
            patch(
                "moltrack.ui.main_window.AnalysisRegionMetadataDialog.get_metadata",
                return_value=("terrace", "Terrace 1", (20, 120, 240)),
            ),
            patch(
                "moltrack.ui.main_window.AnalysisRegionFrameRangeDialog.get_working_frame_indices",
                return_value=(1, 2),
            ),
            patch.object(self.window.viewer, "add_polyline_nm", return_value=object()),
        ):
            self.window.commit_drawn_region_action.trigger()

        self.assertEqual(len(self.window.current_project().frame_scoped_analysis_regions), 1)
        self.assertEqual(
            self.window.current_project().region_for_working_frame("Terrace 1", 0).rect_xyxy,
            early_region.rect_xyxy,
        )
        self.assertEqual(
            self.window.current_project().region_for_working_frame("Terrace 1", 2).rect_xyxy,
            (10.0, 12.0, 15.0, 17.0),
        )

    def test_edit_selected_region_can_update_only_active_frame_scope(self) -> None:
        from moltrack.core import AnalysisRegion

        project, _frames = _project_with_frames()
        early_region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace 1",
            color_rgb=(20, 120, 240),
            rect_xyxy=(1.0, 2.0, 5.0, 7.0),
        )
        late_region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace 1",
            color_rgb=(20, 120, 240),
            rect_xyxy=(10.0, 12.0, 15.0, 17.0),
        )
        updated_late_region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace 1",
            color_rgb=(20, 120, 240),
            rect_xyxy=(11.0, 13.0, 16.0, 18.0),
        )

        self.window.set_project(project)
        self.window.add_analysis_region(early_region)
        self.window.apply_analysis_region_to_frames("Terrace 1", (1, 2), region=late_region)
        self.window.set_active_working_frame_index(2)
        self.window.select_analysis_region("Terrace 1")

        with (
            patch(
                "moltrack.ui.main_window.AnalysisRegionRectDialog.get_region",
                return_value=updated_late_region,
            ) as region_dialog_mock,
            patch(
                "moltrack.ui.main_window.AnalysisRegionEditScopeDialog.get_scope",
                return_value="current_scope",
            ) as scope_dialog_mock,
        ):
            self.window.edit_selected_region_action.trigger()

        region_dialog_mock.assert_called_once_with(self.window, late_region)
        scope_dialog_mock.assert_called_once_with(self.window)
        self.assertEqual(
            self.window.current_project().region_for_working_frame("Terrace 1", 0).rect_xyxy,
            early_region.rect_xyxy,
        )
        self.assertEqual(
            self.window.current_project().region_for_working_frame("Terrace 1", 2).rect_xyxy,
            updated_late_region.rect_xyxy,
        )

    def test_ui_save_and_open_project_round_trip_without_copying_source_images(self) -> None:
        from moltrack.persistence import MANIFEST_PATH

        project, _frames = _project_with_frames()
        project = project.remove_working_frame(1)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ui_round_trip.moltrack"

            self.window.set_project(project)
            self.window.save_project_to(path)

            self.assertEqual(self.window.current_project_path(), path)
            self.assertTrue(zipfile.is_zipfile(path))
            with zipfile.ZipFile(path, mode="r") as zf:
                self.assertEqual(zf.namelist(), [MANIFEST_PATH])

            self.window.open_project_file(path)

        loaded_project = self.window.current_project()
        self.assertIsNotNone(loaded_project)
        self.assertEqual(self.window.current_project_path(), path)
        self.assertEqual(loaded_project.project_name, project.project_name)
        self.assertIsNone(loaded_project.source_series.raw_frames)
        self.assertEqual(loaded_project.working_series.source_frame_indices(), [2, 0])
        self.assertEqual(self.window.active_working_frame_index(), 0)
        self.assertEqual(self.window.active_source_frame_index(), 2)
        self.assertIn("Images not loaded", self.window.frame_index_text())

    def test_ui_save_and_open_project_round_trips_analysis_regions(self) -> None:
        from moltrack.core import AnalysisRegion

        project, _frames = _project_with_frames()
        region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(1.0, 2.0, 5.0, 7.0),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ui_regions.moltrack"

            self.window.set_project(project)
            with patch.object(self.window.viewer, "add_polyline_nm", return_value=object()):
                self.window.add_analysis_region(region)
                self.window.copy_analysis_region_to_series("Terrace A")
                self.window.save_project_to(path)

            with patch.object(self.window.viewer, "add_polyline_nm", return_value=object()) as add_mock:
                self.window.open_project_file(path)

        loaded_project = self.window.current_project()
        self.assertIsNotNone(loaded_project)
        self.assertEqual([loaded_region.name for loaded_region in loaded_project.analysis_regions], ["Terrace A"])
        self.assertEqual(self.window.analysis_regions()[0].rect_xyxy, (1.0, 2.0, 5.0, 7.0))
        self.assertEqual(self.window.copied_analysis_regions()[0].working_frame_indices, (0, 1, 2))
        add_mock.assert_called_once()

    def test_import_image_series_from_paths_sets_unsaved_project_and_displays_first_frame(self) -> None:
        project, frames = _project_with_frames()

        with patch("moltrack.ui.main_window.import_image_series", return_value=project) as import_mock:
            self.window.import_image_series_from(
                ["frame_a.stp", "frame_b.s94"],
                reverse_frame_order=True,
            )

        import_mock.assert_called_once_with(["frame_a.stp", "frame_b.s94"], reverse_frame_order=True)
        self.assertIs(self.window.current_project(), project)
        self.assertIsNone(self.window.current_project_path())
        self.assertEqual(self.window.active_working_frame_index(), 0)
        self.assertEqual(self.window.active_source_frame_index(), 2)
        np.testing.assert_array_equal(self.window.displayed_frame(), frames[2])

    def test_import_action_uses_selected_files_and_reversed_order_option(self) -> None:
        project, _frames = _project_with_frames()
        self.window.import_reversed_order_action.setChecked(True)

        with (
            patch(
                "moltrack.ui.main_window.QFileDialog.getOpenFileNames",
                return_value=(["frame_a.stp", "frame_b.s94"], "Frame Series (*.stp *.s94)"),
            ) as dialog_mock,
            patch("moltrack.ui.main_window.import_image_series", return_value=project) as import_mock,
        ):
            self.window.import_image_series_action.trigger()

        dialog_mock.assert_called_once()
        import_mock.assert_called_once_with(["frame_a.stp", "frame_b.s94"], reverse_frame_order=True)
        self.assertIs(self.window.current_project(), project)
        self.assertIsNone(self.window.current_project_path())

    def test_import_action_passes_single_mpp_as_single_path(self) -> None:
        project, _frames = _project_with_frames()

        with (
            patch(
                "moltrack.ui.main_window.QFileDialog.getOpenFileNames",
                return_value=(["movie.mpp"], "MPP Movies (*.mpp)"),
            ),
            patch("moltrack.ui.main_window.import_image_series", return_value=project) as import_mock,
        ):
            self.window.import_image_series_action.trigger()

        import_mock.assert_called_once_with("movie.mpp", reverse_frame_order=False)
        self.assertIs(self.window.current_project(), project)

    def test_add_analysis_region_draws_overlay_and_stores_region(self) -> None:
        from moltrack.core import AnalysisRegion

        region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(1.0, 2.0, 5.0, 7.0),
        )
        overlay_item = object()

        with patch.object(self.window.viewer, "add_polyline_nm", return_value=overlay_item) as add_mock:
            self.window.add_analysis_region(region)

        self.assertEqual(self.window.analysis_regions(), [region])
        self.assertEqual(self.window.region_overlay_count(), 1)
        add_mock.assert_called_once()
        pts = add_mock.call_args.args[0]
        np.testing.assert_allclose(
            pts,
            np.asarray(
                [
                    [1.0, 2.0],
                    [5.0, 2.0],
                    [5.0, 7.0],
                    [1.0, 7.0],
                    [1.0, 2.0],
                ],
                dtype=np.float64,
            ),
        )
        self.assertEqual(add_mock.call_args.kwargs["color"], (20, 120, 240))

    def test_update_analysis_region_replaces_region_and_overlay(self) -> None:
        from moltrack.core import AnalysisRegion

        original = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(1.0, 2.0, 5.0, 7.0),
        )
        moved = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(3.0, 4.0, 9.0, 12.0),
        )
        old_item = object()
        new_item = object()

        with (
            patch.object(self.window.viewer, "add_polyline_nm", side_effect=[old_item, new_item]) as add_mock,
            patch.object(self.window.viewer, "remove_item") as remove_mock,
        ):
            self.window.add_analysis_region(original)
            self.window.update_analysis_region("Terrace A", moved)

        self.assertEqual(self.window.analysis_regions(), [moved])
        remove_mock.assert_called_once_with(old_item)
        self.assertEqual(add_mock.call_count, 2)
        pts = add_mock.call_args.args[0]
        np.testing.assert_allclose(
            pts,
            np.asarray(
                [
                    [3.0, 4.0],
                    [9.0, 4.0],
                    [9.0, 12.0],
                    [3.0, 12.0],
                    [3.0, 4.0],
                ],
                dtype=np.float64,
            ),
        )

    def test_remove_analysis_region_removes_region_and_overlay(self) -> None:
        from moltrack.core import AnalysisRegion

        region = AnalysisRegion.rectangle(
            kind="ignore",
            name="Ignore A",
            color_rgb=(240, 40, 40),
            rect_xyxy=(0.0, 0.0, 2.0, 2.0),
        )
        overlay_item = object()

        with (
            patch.object(self.window.viewer, "add_polyline_nm", return_value=overlay_item),
            patch.object(self.window.viewer, "remove_item") as remove_mock,
        ):
            self.window.add_analysis_region(region)
            removed = self.window.remove_analysis_region("Ignore A")

        self.assertEqual(removed, region)
        self.assertEqual(self.window.analysis_regions(), [])
        self.assertEqual(self.window.region_overlay_count(), 0)
        remove_mock.assert_called_once_with(overlay_item)

    def test_add_polygon_analysis_region_draws_closed_polygon_overlay(self) -> None:
        from moltrack.core import AnalysisRegion

        region = AnalysisRegion.polygon(
            kind="step_edge",
            name="Step edge band",
            color_rgb=(20, 220, 220),
            vertices_xy=[(1.0, 1.0), (5.0, 2.0), (4.0, 6.0)],
        )

        with patch.object(self.window.viewer, "add_polyline_nm", return_value=object()) as add_mock:
            self.window.add_analysis_region(region)

        pts = add_mock.call_args.args[0]
        np.testing.assert_allclose(
            pts,
            np.asarray(
                [
                    [1.0, 1.0],
                    [5.0, 2.0],
                    [4.0, 6.0],
                    [1.0, 1.0],
                ],
                dtype=np.float64,
            ),
        )
        self.assertEqual(add_mock.call_args.kwargs["color"], (20, 220, 220))

    def test_copy_analysis_region_to_series_reuses_native_geometry_on_each_working_frame(self) -> None:
        from moltrack.core import AnalysisRegion

        project, _frames = _project_with_frames()
        region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(1.0, 2.0, 5.0, 7.0),
        )

        self.window.set_project(project)
        with patch.object(self.window.viewer, "add_polyline_nm", return_value=object()):
            self.window.add_analysis_region(region)
        copied = self.window.copy_analysis_region_to_series("Terrace A")

        self.assertEqual(copied.working_frame_indices, (0, 1, 2))
        self.assertIs(copied.region_for_working_frame(0), region)
        self.assertIs(copied.region_for_working_frame(2), region)
        self.assertEqual(self.window.copied_analysis_regions(), [copied])


if __name__ == "__main__":
    unittest.main()
