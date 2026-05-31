import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside the target GUI env
    QApplication = None


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


if __name__ == "__main__":
    unittest.main()
