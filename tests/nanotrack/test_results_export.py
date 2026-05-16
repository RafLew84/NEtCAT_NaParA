import csv
import tempfile
import unittest

import numpy as np

from nanotrack.core import BBoxXYXY, ParticleMetrics, ParticleTrack, STMSequence, STMSequenceMetadata, TrackFrameAnnotation
from nanotrack.persistence import export_results_csv


class ResultsExportTests(unittest.TestCase):
    def test_export_results_csv_writes_metrics_and_summary_files(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/results.mpp",
            raw_frames=np.zeros((4, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8, size_nm_x=80.0, size_nm_y=40.0, frame_interval_s=0.5),
        )
        sequence.set_frame_excluded(1, True)
        track1 = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0), label="NP-1")
        track1.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
                metrics=ParticleMetrics(area_px=12.0, perimeter_px=16.0, area_nm2=600.0, perimeter_nm=120.0, intensity_sum=24.0, intensity_mean=2.0, intensity_max=3.0),
            )
        )
        track2 = ParticleTrack(track_id=2, seed_frame_index=2, seed_bbox=BBoxXYXY(2.0, 2.0, 6.0, 6.0), label="NP-2")
        track2.add_annotation(
            TrackFrameAnnotation(
                frame_index=3,
                bbox=BBoxXYXY(3.0, 3.0, 7.0, 7.0),
                metrics=ParticleMetrics(area_px=21.0, perimeter_px=24.0, area_nm2=1050.0, perimeter_nm=180.0, intensity_sum=55.0, intensity_mean=2.62, intensity_max=5.0),
                source_view="bm3d+expanded_registration",
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            exported = export_results_csv(f"{tmpdir}/nanotrack_results.csv", sequence, [track1, track2])

            with open(exported["metrics_csv"], newline="", encoding="utf-8") as handle:
                metrics_rows = list(csv.DictReader(handle))
            with open(exported["summary_csv"], newline="", encoding="utf-8") as handle:
                summary_rows = list(csv.DictReader(handle))

        self.assertEqual(len(metrics_rows), 1)
        self.assertEqual(metrics_rows[0]["track_id"], "2")
        self.assertEqual(metrics_rows[0]["label"], "NP-2")
        self.assertEqual(metrics_rows[0]["frame_number"], "4")
        self.assertEqual(metrics_rows[0]["time_s"], "1.5")
        self.assertEqual(metrics_rows[0]["source_view"], "bm3d+expanded_registration")
        self.assertEqual(metrics_rows[0]["intensity_max"], "5.0")

        self.assertEqual(len(summary_rows), 2)
        self.assertEqual(summary_rows[0]["track_id"], "1")
        self.assertEqual(summary_rows[0]["measured_frames"], "0")
        self.assertEqual(summary_rows[0]["mean_area_px"], "")
        self.assertEqual(summary_rows[0]["mean_area_nm2"], "")
        self.assertEqual(summary_rows[0]["mean_perimeter_nm"], "")
        self.assertEqual(summary_rows[1]["track_id"], "2")
        self.assertEqual(summary_rows[1]["source_views"], "bm3d+expanded_registration")
        self.assertEqual(summary_rows[1]["max_intensity_max"], "5.0")


if __name__ == "__main__":
    unittest.main()
