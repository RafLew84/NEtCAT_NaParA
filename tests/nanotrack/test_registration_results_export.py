import csv
import tempfile
import unittest

import numpy as np

from nanotrack.core import (
    RegistrationFrameResult,
    RegistrationResultSet,
    RegistrationSettings,
    STMSequence,
    STMSequenceMetadata,
)
from nanotrack.persistence import export_registration_results_csv


class RegistrationResultsExportTests(unittest.TestCase):
    def test_export_registration_results_csv_writes_metrics_and_summary_files(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/registration_export.mpp",
            raw_frames=np.zeros((3, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8, frame_interval_s=0.25),
        )
        sequence.set_frame_excluded(2, True)
        result_set = RegistrationResultSet(
            settings=RegistrationSettings(
                backend="ecc_translation",
                reference_strategy="adjacent",
                registration_view="normalized",
            ),
            results_by_frame={
                0: RegistrationFrameResult(0, (0.0, 0.0), "identity", quality_score=1.0),
                1: RegistrationFrameResult(
                    1,
                    (2.0, -1.0),
                    "ecc_translation_adjacent",
                    quality_score=0.8,
                    phase_peak_ratio=3.5,
                    ecc_score=0.91,
                    status="ok",
                ),
                2: RegistrationFrameResult(
                    2,
                    (4.0, -1.5),
                    "tile_correlation_ransac_adjacent",
                    quality_score=0.6,
                    num_inlier_tiles=7,
                    num_total_tiles=9,
                    median_tile_residual=0.2,
                    flow_mad=0.15,
                    status="low_confidence",
                ),
            },
            reference_frame_index=0,
            template_frame_indices=(0,),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            exported = export_registration_results_csv(f"{tmpdir}/registration.csv", sequence, result_set)
            with open(exported["metrics_csv"], newline="", encoding="utf-8") as handle:
                metrics_rows = list(csv.DictReader(handle))
            with open(exported["summary_csv"], newline="", encoding="utf-8") as handle:
                summary_rows = list(csv.DictReader(handle))

        self.assertEqual(len(metrics_rows), 3)
        self.assertEqual(metrics_rows[1]["frame_number"], "2")
        self.assertEqual(metrics_rows[1]["time_s"], "0.25")
        self.assertEqual(metrics_rows[1]["dx_px"], "2.0")
        self.assertEqual(metrics_rows[1]["dy_px"], "-1.0")
        self.assertEqual(metrics_rows[1]["phase_peak_ratio"], "3.5")
        self.assertEqual(metrics_rows[1]["quality_score"], "0.8")
        self.assertEqual(metrics_rows[1]["method"], "ecc_translation_adjacent")
        self.assertEqual(metrics_rows[1]["ecc_score"], "0.91")
        self.assertEqual(metrics_rows[2]["frame_excluded"], "True")
        self.assertEqual(metrics_rows[2]["status"], "low_confidence")
        self.assertEqual(metrics_rows[2]["num_inlier_tiles"], "7")
        self.assertEqual(metrics_rows[2]["num_total_tiles"], "9")
        self.assertEqual(metrics_rows[2]["median_tile_residual"], "0.2")
        self.assertEqual(metrics_rows[2]["flow_mad"], "0.15")

        self.assertEqual(len(summary_rows), 1)
        self.assertEqual(summary_rows[0]["backend"], "ecc_translation")
        self.assertEqual(summary_rows[0]["result_count"], "3")
        self.assertEqual(summary_rows[0]["ok_count"], "2")
        self.assertEqual(summary_rows[0]["low_confidence_count"], "1")
        self.assertEqual(summary_rows[0]["template_frame_numbers"], "1")


if __name__ == "__main__":
    unittest.main()
