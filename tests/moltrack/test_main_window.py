import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import ANY, patch

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication, QDialog
except ImportError:  # pragma: no cover - optional outside the target GUI env
    QApplication = None
    QDialog = None


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
            ["Import Image Series...", "Import Reversed Order", "Open Project...", "Save Project", "Save Project As..."],
        )
        self.assertTrue(file_menu.actions()[1].isCheckable())

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
