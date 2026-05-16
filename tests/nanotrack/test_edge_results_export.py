import csv
import tempfile
import unittest

import numpy as np

from nanotrack.core import EdgeFrameAnnotation, EdgeMetrics, EdgeTrack, PolygonROI, STMSequence, STMSequenceMetadata
from nanotrack.persistence import export_edge_results_csv


class EdgeResultsExportTests(unittest.TestCase):
    def test_export_edge_results_csv_writes_metrics_and_summary_files(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_results.mpp",
            raw_frames=np.zeros((4, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8, size_nm_x=80.0, size_nm_y=40.0, frame_interval_s=0.5),
        )
        sequence.set_frame_excluded(1, True)
        polygon = PolygonROI(np.asarray([[1.0, 1.0], [6.0, 1.0], [6.0, 6.0], [1.0, 6.0]], dtype=np.float64))
        track1 = EdgeTrack(edge_track_id=1, seed_frame_index=0, polygon_roi=polygon, seed_polyline=np.asarray([[1.0, 2.0], [6.0, 2.0]], dtype=np.float64), label="Edge-A")
        track1.add_annotation(
            EdgeFrameAnnotation(
                frame_index=1,
                polyline=np.asarray([[1.0, 2.0], [6.0, 2.0]], dtype=np.float64),
                metrics=EdgeMetrics(
                    length_px=5.0,
                    length_nm=50.0,
                    roughness_rms_px=0.2,
                    roughness_rms_nm=2.0,
                    mean_curvature=0.05,
                    max_curvature=0.08,
                    waviness_amplitude_px=0.4,
                    waviness_amplitude_nm=4.0,
                ),
            )
        )
        track2 = EdgeTrack(edge_track_id=2, seed_frame_index=2, polygon_roi=polygon, seed_polyline=np.asarray([[1.0, 3.0], [6.0, 3.0]], dtype=np.float64), label="Edge-B")
        track2.add_annotation(
            EdgeFrameAnnotation(
                frame_index=3,
                polyline=np.asarray([[1.0, 3.0], [6.0, 3.0]], dtype=np.float64),
                metrics=EdgeMetrics(
                    length_px=6.0,
                    length_nm=60.0,
                    roughness_rms_px=0.3,
                    roughness_rms_nm=3.0,
                    mean_curvature=0.06,
                    max_curvature=0.10,
                    waviness_amplitude_px=0.5,
                    waviness_amplitude_nm=5.0,
                ),
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            exported = export_edge_results_csv(f"{tmpdir}/nanotrack_edge_results.csv", sequence, [track1, track2])

            with open(exported["metrics_csv"], newline="", encoding="utf-8") as handle:
                metrics_rows = list(csv.DictReader(handle))
            with open(exported["summary_csv"], newline="", encoding="utf-8") as handle:
                summary_rows = list(csv.DictReader(handle))

        self.assertEqual(len(metrics_rows), 1)
        self.assertEqual(metrics_rows[0]["edge_track_id"], "2")
        self.assertEqual(metrics_rows[0]["label"], "Edge-B")
        self.assertEqual(metrics_rows[0]["frame_number"], "4")
        self.assertEqual(metrics_rows[0]["time_s"], "1.5")
        self.assertEqual(metrics_rows[0]["max_curvature"], "0.1")

        self.assertEqual(len(summary_rows), 2)
        self.assertEqual(summary_rows[0]["edge_track_id"], "1")
        self.assertEqual(summary_rows[0]["measured_frames"], "0")
        self.assertEqual(summary_rows[0]["mean_length_px"], "")
        self.assertEqual(summary_rows[0]["mean_length_nm"], "")
        self.assertEqual(summary_rows[0]["mean_roughness_rms_nm"], "")
        self.assertEqual(summary_rows[1]["edge_track_id"], "2")
        self.assertEqual(summary_rows[1]["max_max_curvature"], "0.1")


if __name__ == "__main__":
    unittest.main()
