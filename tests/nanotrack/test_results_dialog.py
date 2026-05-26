import tempfile
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside the target GUI env
    QApplication = None

from nanotrack.core import BBoxXYXY, ParticleMetrics, ParticleTrack, STMSequence, STMSequenceMetadata, TrackFrameAnnotation

if QApplication is not None:
    from nanotrack.ui.dialogs import TrackResultsDialog
else:  # pragma: no cover - optional outside the target GUI env
    TrackResultsDialog = None


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for NanoTrack dialog tests")
class TrackResultsDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.dialog = TrackResultsDialog()

    def tearDown(self) -> None:
        self.dialog.close()
        self.dialog.deleteLater()
        self.__class__._app.processEvents()

    def test_set_context_populates_selector_and_plots_metric_series(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/results.mpp",
            raw_frames=np.zeros((4, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        track1 = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0))
        track1.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
                metrics=ParticleMetrics(area_px=12.0, perimeter_px=16.0, intensity_sum=24.0, intensity_mean=2.0, intensity_max=3.0),
                source_view="raw+registration",
            )
        )
        track1.add_annotation(
            TrackFrameAnnotation(
                frame_index=2,
                bbox=BBoxXYXY(3.0, 3.0, 6.0, 6.0),
                metrics=ParticleMetrics(area_px=14.0, perimeter_px=18.0, intensity_sum=30.0, intensity_mean=2.14, intensity_max=4.0),
            )
        )
        track2 = ParticleTrack(track_id=2, seed_frame_index=2, seed_bbox=BBoxXYXY(2.0, 2.0, 6.0, 6.0))
        track2.add_annotation(
            TrackFrameAnnotation(
                frame_index=3,
                bbox=BBoxXYXY(3.0, 3.0, 7.0, 7.0),
                metrics=ParticleMetrics(area_px=21.0, perimeter_px=24.0, intensity_sum=55.0, intensity_mean=2.62, intensity_max=5.0),
            )
        )

        self.dialog.set_context(sequence, [track1, track2], selected_track_id=1)

        self.assertEqual(self.dialog.cmb_tracks.count(), 3)
        self.assertEqual(self.dialog.current_track_id(), 1)
        area_items = self.dialog.plot_area.plotItem.listDataItems()
        self.assertEqual(len(area_items), 1)
        x_data, y_data = area_items[0].getData()
        np.testing.assert_array_equal(x_data, np.asarray([2.0, 3.0], dtype=np.float32))
        np.testing.assert_array_equal(y_data, np.asarray([12.0, 14.0], dtype=np.float32))
        coverage_items = self.dialog.plot_coverage.plotItem.listDataItems()
        self.assertEqual(len(coverage_items), 1)
        _, coverage_data = coverage_items[0].getData()
        np.testing.assert_allclose(coverage_data, np.asarray([18.75, 21.875], dtype=np.float32))
        self.assertIn("measured frames: 2 / 4", self.dialog.lbl_summary.text())
        self.assertIn("source views: raw+registration", self.dialog.lbl_summary.text())
        self.assertTrue(self.dialog.btn_export.isEnabled())

    def test_changing_track_updates_plots_and_emits_selection(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/results.mpp",
            raw_frames=np.zeros((4, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        track1 = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0))
        track1.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
                metrics=ParticleMetrics(area_px=12.0, perimeter_px=16.0, intensity_sum=24.0, intensity_mean=2.0, intensity_max=3.0),
            )
        )
        track2 = ParticleTrack(track_id=2, seed_frame_index=2, seed_bbox=BBoxXYXY(2.0, 2.0, 6.0, 6.0))
        track2.add_annotation(
            TrackFrameAnnotation(
                frame_index=3,
                bbox=BBoxXYXY(3.0, 3.0, 7.0, 7.0),
                metrics=ParticleMetrics(area_px=21.0, perimeter_px=24.0, intensity_sum=55.0, intensity_mean=2.62, intensity_max=5.0),
            )
        )
        selected = []
        self.dialog.track_selected.connect(selected.append)
        self.dialog.set_context(sequence, [track1, track2], selected_track_id=1)

        self.dialog.cmb_tracks.setCurrentIndex(2)
        self.__class__._app.processEvents()

        self.assertEqual(selected[-1], 2)
        area_items = self.dialog.plot_area.plotItem.listDataItems()
        x_data, y_data = area_items[0].getData()
        np.testing.assert_array_equal(x_data, np.asarray([4.0], dtype=np.float32))
        np.testing.assert_array_equal(y_data, np.asarray([21.0], dtype=np.float32))

    def test_all_tracks_and_nanometer_units_aggregate_plots(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/results.mpp",
            raw_frames=np.zeros((4, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8, size_nm_x=80.0, size_nm_y=40.0),
        )
        track1 = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0))
        track1.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
                metrics=ParticleMetrics(
                    area_px=4.0,
                    perimeter_px=8.0,
                    area_nm2=200.0,
                    perimeter_nm=60.0,
                    intensity_sum=20.0,
                    intensity_mean=5.0,
                    intensity_max=7.0,
                ),
            )
        )
        track2 = ParticleTrack(track_id=2, seed_frame_index=0, seed_bbox=BBoxXYXY(2.0, 2.0, 6.0, 6.0))
        track2.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(3.0, 3.0, 7.0, 7.0),
                metrics=ParticleMetrics(
                    area_px=3.0,
                    perimeter_px=10.0,
                    area_nm2=150.0,
                    perimeter_nm=70.0,
                    intensity_sum=30.0,
                    intensity_mean=10.0,
                    intensity_max=12.0,
                ),
            )
        )

        self.dialog.set_context(sequence, [track1, track2], selected_track_id=None)
        self.dialog.cmb_units.setCurrentIndex(1)
        self.__class__._app.processEvents()

        self.assertIsNone(self.dialog.current_track_id())
        self.assertEqual(self.dialog.cmb_tracks.currentIndex(), 0)
        area_items = self.dialog.plot_area.plotItem.listDataItems()
        x_data, y_data = area_items[0].getData()
        np.testing.assert_array_equal(x_data, np.asarray([2.0], dtype=np.float32))
        np.testing.assert_array_equal(y_data, np.asarray([350.0], dtype=np.float32))
        coverage_items = self.dialog.plot_coverage.plotItem.listDataItems()
        self.assertEqual(len(coverage_items), 1)
        _, coverage_data = coverage_items[0].getData()
        np.testing.assert_allclose(coverage_data, np.asarray([(7.0 / 64.0) * 100.0], dtype=np.float32))
        self.assertIn("All tracks", self.dialog.lbl_summary.text())
        self.assertFalse(self.dialog.btn_delete.isEnabled())

    def test_all_tracks_coverage_uses_union_of_masks_instead_of_summed_areas(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/results_union_coverage.mpp",
            raw_frames=np.zeros((3, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        mask1 = np.zeros((8, 8), dtype=bool)
        mask1[1:4, 1:4] = True
        mask2 = np.zeros((8, 8), dtype=bool)
        mask2[2:5, 2:5] = True
        track1 = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0))
        track1.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0),
                mask=mask1,
                metrics=ParticleMetrics(
                    area_px=float(np.count_nonzero(mask1)),
                    perimeter_px=12.0,
                    intensity_sum=18.0,
                    intensity_mean=2.0,
                    intensity_max=3.0,
                ),
            )
        )
        track2 = ParticleTrack(track_id=2, seed_frame_index=0, seed_bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0))
        track2.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
                mask=mask2,
                metrics=ParticleMetrics(
                    area_px=float(np.count_nonzero(mask2)),
                    perimeter_px=12.0,
                    intensity_sum=27.0,
                    intensity_mean=3.0,
                    intensity_max=4.0,
                ),
            )
        )

        self.dialog.set_context(sequence, [track1, track2], selected_track_id=None)

        area_items = self.dialog.plot_area.plotItem.listDataItems()
        _x_area, area_data = area_items[0].getData()
        np.testing.assert_array_equal(area_data, np.asarray([18.0], dtype=np.float32))
        coverage_items = self.dialog.plot_coverage.plotItem.listDataItems()
        _x_coverage, coverage_data = coverage_items[0].getData()
        expected_union_area = float(np.count_nonzero(mask1 | mask2))
        np.testing.assert_allclose(coverage_data, np.asarray([(expected_union_area / 64.0) * 100.0], dtype=np.float32))

    def test_boundary_correction_half_counts_boundary_pixels_for_selected_track(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/results_boundary_exclusion.mpp",
            raw_frames=np.ones((2, 7, 7), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=7, pixels_y=7),
        )
        mask = np.zeros((7, 7), dtype=bool)
        mask[1:6, 1:6] = True
        track = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(1.0, 1.0, 6.0, 6.0))
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(1.0, 1.0, 6.0, 6.0),
                mask=mask,
                metrics=ParticleMetrics(
                    area_px=25.0,
                    perimeter_px=20.0,
                    intensity_sum=25.0,
                    intensity_mean=1.0,
                    intensity_max=1.0,
                ),
            )
        )

        self.dialog.set_context(sequence, [track], selected_track_id=1)
        self.assertFalse(self.dialog.chk_exclude_boundary_pixels.isChecked())
        self.assertEqual(self.dialog.spn_boundary_pixel_weight.value(), 0.5)
        self.assertFalse(self.dialog.spn_boundary_pixel_weight.isEnabled())

        area_items = self.dialog.plot_area.plotItem.listDataItems()
        _x_area, area_data = area_items[0].getData()
        np.testing.assert_array_equal(area_data, np.asarray([25.0], dtype=np.float32))

        self.dialog.chk_exclude_boundary_pixels.setChecked(True)
        self.__class__._app.processEvents()

        self.assertTrue(self.dialog.spn_boundary_pixel_weight.isEnabled())
        area_items = self.dialog.plot_area.plotItem.listDataItems()
        _x_area, area_data = area_items[0].getData()
        np.testing.assert_array_equal(area_data, np.asarray([17.0], dtype=np.float32))
        perimeter_items = self.dialog.plot_perimeter.plotItem.listDataItems()
        _x_perimeter, perimeter_data = perimeter_items[0].getData()
        np.testing.assert_array_equal(perimeter_data, np.asarray([20.0], dtype=np.float32))
        coverage_items = self.dialog.plot_coverage.plotItem.listDataItems()
        _x_coverage, coverage_data = coverage_items[0].getData()
        np.testing.assert_allclose(coverage_data, np.asarray([(17.0 / 49.0) * 100.0], dtype=np.float32))
        self.assertIn("boundary correction 0.50x", self.dialog.lbl_summary.text())

        self.dialog.spn_boundary_pixel_weight.setValue(0.0)
        self.__class__._app.processEvents()

        area_items = self.dialog.plot_area.plotItem.listDataItems()
        _x_area, area_data = area_items[0].getData()
        np.testing.assert_array_equal(area_data, np.asarray([9.0], dtype=np.float32))
        perimeter_items = self.dialog.plot_perimeter.plotItem.listDataItems()
        _x_perimeter, perimeter_data = perimeter_items[0].getData()
        np.testing.assert_array_equal(perimeter_data, np.asarray([12.0], dtype=np.float32))
        coverage_items = self.dialog.plot_coverage.plotItem.listDataItems()
        _x_coverage, coverage_data = coverage_items[0].getData()
        np.testing.assert_allclose(coverage_data, np.asarray([(9.0 / 49.0) * 100.0], dtype=np.float32))
        self.assertIn("boundary correction 0.00x", self.dialog.lbl_summary.text())

    def test_boundary_correction_uses_weighted_union_for_all_tracks_coverage(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/results_boundary_union_coverage.mpp",
            raw_frames=np.ones((2, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        mask1 = np.zeros((8, 8), dtype=bool)
        mask1[1:4, 1:4] = True
        mask2 = np.zeros((8, 8), dtype=bool)
        mask2[2:5, 2:5] = True
        track1 = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0))
        track1.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0),
                mask=mask1,
                metrics=ParticleMetrics(
                    area_px=9.0,
                    perimeter_px=12.0,
                    intensity_sum=9.0,
                    intensity_mean=1.0,
                    intensity_max=1.0,
                ),
            )
        )
        track2 = ParticleTrack(track_id=2, seed_frame_index=0, seed_bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0))
        track2.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
                mask=mask2,
                metrics=ParticleMetrics(
                    area_px=9.0,
                    perimeter_px=12.0,
                    intensity_sum=9.0,
                    intensity_mean=1.0,
                    intensity_max=1.0,
                ),
            )
        )

        self.dialog.set_context(sequence, [track1, track2], selected_track_id=None)
        self.dialog.chk_exclude_boundary_pixels.setChecked(True)
        self.__class__._app.processEvents()

        area_items = self.dialog.plot_area.plotItem.listDataItems()
        _x_area, area_data = area_items[0].getData()
        np.testing.assert_array_equal(area_data, np.asarray([10.0], dtype=np.float32))
        coverage_items = self.dialog.plot_coverage.plotItem.listDataItems()
        _x_coverage, coverage_data = coverage_items[0].getData()
        np.testing.assert_allclose(coverage_data, np.asarray([(8.0 / 64.0) * 100.0], dtype=np.float32))

    def test_exclude_boundary_pixels_falls_back_to_saved_metrics_when_masks_are_missing(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/results_boundary_saved_session.mpp",
            raw_frames=np.ones((2, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        track = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0))
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0),
                metrics=ParticleMetrics(
                    area_px=12.0,
                    perimeter_px=16.0,
                    intensity_sum=24.0,
                    intensity_mean=2.0,
                    intensity_max=3.0,
                ),
            )
        )

        self.dialog.set_context(sequence, [track], selected_track_id=1)
        self.dialog.chk_exclude_boundary_pixels.setChecked(True)
        self.__class__._app.processEvents()

        area_items = self.dialog.plot_area.plotItem.listDataItems()
        _x_area, area_data = area_items[0].getData()
        np.testing.assert_array_equal(area_data, np.asarray([12.0], dtype=np.float32))
        coverage_items = self.dialog.plot_coverage.plotItem.listDataItems()
        _x_coverage, coverage_data = coverage_items[0].getData()
        np.testing.assert_allclose(coverage_data, np.asarray([(12.0 / 64.0) * 100.0], dtype=np.float32))

    def test_results_ignore_excluded_frames(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/results_excluded_frame.mpp",
            raw_frames=np.zeros((4, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        sequence.set_frame_excluded(1, True)
        track = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0))
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0),
                metrics=ParticleMetrics(area_px=12.0, perimeter_px=12.0, intensity_sum=24.0, intensity_mean=2.0, intensity_max=3.0),
            )
        )
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=2,
                bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
                metrics=ParticleMetrics(area_px=8.0, perimeter_px=10.0, intensity_sum=16.0, intensity_mean=2.0, intensity_max=4.0),
            )
        )

        self.dialog.set_context(sequence, [track], selected_track_id=1)

        area_items = self.dialog.plot_area.plotItem.listDataItems()
        x_data, y_data = area_items[0].getData()
        np.testing.assert_array_equal(x_data, np.asarray([3.0], dtype=np.float32))
        np.testing.assert_array_equal(y_data, np.asarray([8.0], dtype=np.float32))
        coverage_items = self.dialog.plot_coverage.plotItem.listDataItems()
        _x_coverage, coverage_data = coverage_items[0].getData()
        np.testing.assert_allclose(coverage_data, np.asarray([(8.0 / 64.0) * 100.0], dtype=np.float32))

    def test_coverage_uses_original_frame_area_for_expanded_registration_source_view(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/results_expanded_registration.mpp",
            raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        track = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(1.0, 1.0, 5.0, 5.0))
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(1.0, 1.0, 5.0, 5.0),
                metrics=ParticleMetrics(
                    area_px=16.0,
                    perimeter_px=16.0,
                    intensity_sum=32.0,
                    intensity_mean=2.0,
                    intensity_max=4.0,
                ),
                source_view="bm3d+expanded_registration",
            )
        )

        self.dialog.set_context(sequence, [track], selected_track_id=1)

        coverage_items = self.dialog.plot_coverage.plotItem.listDataItems()
        self.assertEqual(len(coverage_items), 1)
        x_data, coverage_data = coverage_items[0].getData()
        np.testing.assert_array_equal(x_data, np.asarray([2.0], dtype=np.float32))
        np.testing.assert_allclose(coverage_data, np.asarray([25.0], dtype=np.float32))
        self.assertIn("source views: bm3d+expanded_registration", self.dialog.lbl_summary.text())

    def test_delete_button_emits_selected_track_request(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/results.mpp",
            raw_frames=np.zeros((4, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        track1 = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0))
        track1.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
                metrics=ParticleMetrics(area_px=12.0, perimeter_px=16.0, intensity_sum=24.0, intensity_mean=2.0, intensity_max=3.0),
            )
        )
        track2 = ParticleTrack(track_id=2, seed_frame_index=2, seed_bbox=BBoxXYXY(2.0, 2.0, 6.0, 6.0))
        track2.add_annotation(
            TrackFrameAnnotation(
                frame_index=3,
                bbox=BBoxXYXY(3.0, 3.0, 7.0, 7.0),
                metrics=ParticleMetrics(area_px=21.0, perimeter_px=24.0, intensity_sum=55.0, intensity_mean=2.62, intensity_max=5.0),
            )
        )
        deleted_track_ids: list[int] = []
        self.dialog.track_delete_requested.connect(deleted_track_ids.append)

        self.dialog.set_context(sequence, [track1, track2], selected_track_id=None)
        self.assertFalse(self.dialog.btn_delete.isEnabled())

        self.dialog.cmb_tracks.setCurrentIndex(1)
        self.__class__._app.processEvents()

        self.assertEqual(self.dialog.current_track_id(), 1)
        self.assertTrue(self.dialog.btn_delete.isEnabled())

        self.dialog.btn_delete.click()

        self.assertEqual(deleted_track_ids, [1])

    def test_export_results_to_path_writes_csv_pair(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/results.mpp",
            raw_frames=np.zeros((4, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8, size_nm_x=80.0, size_nm_y=40.0, frame_interval_s=0.5),
        )
        track1 = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0))
        track1.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
                metrics=ParticleMetrics(area_px=12.0, perimeter_px=16.0, area_nm2=600.0, perimeter_nm=120.0, intensity_sum=24.0, intensity_mean=2.0, intensity_max=3.0),
            )
        )
        self.dialog.set_context(sequence, [track1], selected_track_id=1)

        with tempfile.TemporaryDirectory() as tmpdir:
            exported = self.dialog.export_results_to_path(f"{tmpdir}/results.csv")

            self.assertTrue(os.path.exists(exported["metrics_csv"]))
            self.assertTrue(os.path.exists(exported["summary_csv"]))


if __name__ == "__main__":
    unittest.main()
