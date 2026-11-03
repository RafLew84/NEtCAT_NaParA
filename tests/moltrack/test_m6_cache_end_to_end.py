import unittest

import numpy as np

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularM6OrientationAnalysisSettings,
    analyze_molecular_frame_range,
)
from moltrack.core import (
    MolTrackImageSeries,
    MolecularDetection,
    MolecularDetectionSet,
)
from nanotrack.core import STMSequenceMetadata


class M6CacheEndToEndTests(unittest.TestCase):
    def test_public_multi_frame_analysis_keeps_default_cache_bounded(self) -> None:
        frame_count = 70
        detections = MolecularDetectionSet(frame_count=frame_count)
        for frame_index in range(frame_count):
            detections.set_detections(
                frame_index,
                [
                    MolecularDetection(
                        frame_index=frame_index,
                        bbox_xyxy=(1.0, 1.0, 2.0, 2.0),
                        confidence=0.9,
                        detection_id=f"frame-{frame_index}",
                    )
                ],
                source_view="raw",
                frame_shape=(4, 4),
            )
        series = MolTrackImageSeries(
            source_path="cache-navigation.mpp",
            raw_frames=np.zeros((frame_count, 4, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=4,
                pixels_y=4,
                size_nm_x=4.0,
                size_nm_y=4.0,
                scan_angle_deg=0.0,
            ),
            molecular_detections=detections,
        )
        settings = MolecularM6OrientationAnalysisSettings(
            duplicate_max_distance_nm=0.1,
            first_shell_r_min_nm=0.5,
            first_shell_r_max_nm=1.5,
            footprint_support_radius_nm=1.0,
            gr_bin_width_nm=0.5,
            gr_max_nm=4.0,
            gr_min_expected_pair_exposure=0.1,
        )

        analysis = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("navigation", 0, frame_count - 1),
            source_view="raw",
            m6_orientation_settings=settings,
        )
        last_result = analysis.frame_results[-1].m6_orientation_analysis
        stats = series.structural_analysis_cache.stats()

        self.assertEqual(len(analysis.frame_results), frame_count)
        self.assertEqual(stats.entry_count, stats.max_entries)
        self.assertGreaterEqual(
            stats.eviction_count,
            frame_count - stats.max_entries,
        )
        self.assertLessEqual(stats.estimated_bytes, stats.max_bytes)

        repeated_last = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("last", frame_count - 1, frame_count - 1),
            source_view="raw",
            m6_orientation_settings=settings,
        ).frame_results[0].m6_orientation_analysis
        self.assertIs(repeated_last, last_result)
        self.assertLessEqual(
            series.structural_analysis_cache.stats().entry_count,
            series.structural_analysis_cache.stats().max_entries,
        )


if __name__ == "__main__":
    unittest.main()
