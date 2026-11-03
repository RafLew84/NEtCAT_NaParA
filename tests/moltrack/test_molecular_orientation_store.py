import unittest
from dataclasses import replace
from math import atan2, degrees

import numpy as np

from moltrack.analysis import (
    MolecularOrientationEstimationCancelled,
    MolecularOrientationMeasurement,
    MolecularOrientationProvenance,
    MolecularOrientationStore,
    build_molecular_orientation_axes,
    estimate_series_molecular_orientations,
)
from moltrack.core import (
    MolecularSegmentation,
    MolecularSegmentationSet,
    MolTrackImageSeries,
)
from nanotrack.core import STMSequenceMetadata


def _measurement(
    *,
    source_id: str = "mask-1",
    frame_index: int = 0,
    angle_deg: float = 25.0,
) -> MolecularOrientationMeasurement:
    return MolecularOrientationMeasurement(
        measurement_id=f"orientation:segmentation:{source_id}",
        status="available",
        angle_deg=angle_deg,
        periodicity_deg=180.0,
        confidence=0.8,
        method="mask_principal_axis",
        patch_shape_px=(12, 14),
        provenance=MolecularOrientationProvenance(
            source_file_name="movie.mpp",
            source_file_sha256="a" * 64,
            source_session_file_name=None,
            source_session_sha256=None,
            frame_index=frame_index,
            source_view="raw",
            source_kind="segmentation",
            source_id=source_id,
            patch_bbox_xyxy=(3.0, 4.0, 17.0, 16.0),
            orientation_reference="sample_x_axis_counterclockwise",
        ),
    )


def _series_with_elliptical_masks() -> MolTrackImageSeries:
    frame_count = 2
    height = width = 40
    yy, xx = np.ogrid[:height, :width]
    mask = ((xx - 20.0) / 8.0) ** 2 + ((yy - 20.0) / 3.0) ** 2 <= 1.0
    segmentations = MolecularSegmentationSet(frame_count=frame_count)
    for frame_index in range(frame_count):
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=frame_index,
                source_view="raw",
                bbox_xyxy=(12.0, 17.0, 29.0, 24.0),
                mask=mask,
                origin="sam2",
                segmentation_id=f"mask-{frame_index}",
            )
        )
    frames = np.stack(
        [
            np.linspace(0.0, 1.0, height * width, dtype=np.float32).reshape(
                height,
                width,
            )
            for _ in range(frame_count)
        ]
    )
    return MolTrackImageSeries(
        source_path="movie.mpp",
        raw_frames=frames,
        metadata=STMSequenceMetadata(
            pixels_x=width,
            pixels_y=height,
            size_nm_x=80.0,
            size_nm_y=80.0,
            scan_angle_deg=10.0,
        ),
        molecular_segmentations=segmentations,
    )


class MolecularOrientationStoreTests(unittest.TestCase):
    def test_manual_set_rotate_and_reset_preserve_the_automatic_result(self) -> None:
        automatic = _measurement()
        store = MolecularOrientationStore(frame_count=2)
        store.put(automatic)

        corrected = store.set_manual_angle(
            "segmentation",
            "mask-1",
            angle_deg=40.0,
            reviewer="MolTrack user",
        )
        rotated = store.rotate_manual_angle(
            "segmentation",
            "mask-1",
            delta_deg=-5.0,
            reviewer="MolTrack user",
        )

        self.assertTrue(corrected.is_manually_corrected)
        self.assertAlmostEqual(rotated.angle_deg, 35.0)
        self.assertEqual(
            rotated.manual_correction.original_result.angle_deg,
            automatic.angle_deg,
        )
        self.assertEqual(
            store.reset_manual_angle("segmentation", "mask-1"),
            automatic,
        )

    def test_series_estimation_returns_measurements_and_progress_for_each_mask(
        self,
    ) -> None:
        series = _series_with_elliptical_masks()
        progress = []

        result = estimate_series_molecular_orientations(
            series,
            frame_indices=(0, 1),
            source_view="raw",
            source_file_sha256="b" * 64,
            progress_callback=progress.append,
        )

        self.assertEqual(result.total_count, 2)
        self.assertEqual(result.completed_count, 2)
        self.assertEqual(result.failure_count, 0)
        self.assertEqual(len(result.measurements), 2)
        self.assertEqual([event.completed_count for event in progress], [0, 1, 2])
        self.assertTrue(
            all(item.status == "available" for item in result.measurements)
        )
        self.assertEqual(
            result.measurements[1].provenance.source_id,
            "mask-1",
        )
        self.assertLess(result.measurements[0].patch_shape_px[0], 40)

    def test_series_estimation_reports_one_invalid_mask_and_continues(
        self,
    ) -> None:
        series = _series_with_elliptical_masks()
        series.molecular_segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(2.0, 2.0, 6.0, 6.0),
                polygon_xy=np.asarray(
                    ((2.0, 2.0), (6.0, 2.0), (6.0, 6.0), (2.0, 6.0)),
                ),
                origin="manual",
                segmentation_id="polygon-only",
            )
        )

        result = estimate_series_molecular_orientations(
            series,
            frame_indices=(0,),
            source_view="raw",
            source_file_sha256="b" * 64,
        )

        self.assertEqual(result.completed_count, 2)
        self.assertEqual(len(result.measurements), 1)
        self.assertEqual(result.failure_count, 1)
        self.assertEqual(result.failures[0].source_id, "polygon-only")
        self.assertIn("segmentation mask", result.failures[0].message)

    def test_series_estimation_can_be_canceled_between_masks(self) -> None:
        series = _series_with_elliptical_masks()

        with self.assertRaises(MolecularOrientationEstimationCancelled):
            estimate_series_molecular_orientations(
                series,
                frame_indices=(0, 1),
                source_view="raw",
                source_file_sha256="b" * 64,
                should_cancel=lambda: True,
            )

    def test_new_automatic_result_preserves_manual_angle_and_updates_baseline(
        self,
    ) -> None:
        store = MolecularOrientationStore(
            frame_count=2,
            measurements=(_measurement(angle_deg=25.0),),
        )
        store.set_manual_angle(
            "segmentation",
            "mask-1",
            angle_deg=40.0,
            reviewer="MolTrack user",
        )

        store.put_automatic_measurements_preserving_manual(
            (_measurement(angle_deg=30.0),)
        )

        current = store.get("segmentation", "mask-1")
        self.assertAlmostEqual(current.angle_deg, 40.0)
        self.assertTrue(current.is_manually_corrected)
        self.assertAlmostEqual(
            current.manual_correction.original_result.angle_deg,
            30.0,
        )

    def test_first_manual_result_becomes_correction_when_automatic_arrives(
        self,
    ) -> None:
        manual = replace(
            _measurement(angle_deg=40.0),
            method="manual",
            confidence=1.0,
        )
        store = MolecularOrientationStore(
            frame_count=2,
            measurements=(manual,),
        )

        store.put_automatic_measurements_preserving_manual(
            (_measurement(angle_deg=30.0),)
        )

        current = store.get("segmentation", "mask-1")
        self.assertAlmostEqual(current.angle_deg, 40.0)
        self.assertTrue(current.is_manually_corrected)
        self.assertAlmostEqual(
            current.manual_correction.original_result.angle_deg,
            30.0,
        )

    def test_axis_overlay_uses_stored_angle_and_selected_source(self) -> None:
        series = _series_with_elliptical_masks()
        series.molecular_orientations = MolecularOrientationStore(
            frame_count=series.frame_count,
            measurements=(_measurement(source_id="mask-0", angle_deg=10.0),),
        )

        axes = build_molecular_orientation_axes(
            series,
            frame_index=0,
            source_view="raw",
            selected_source_id="mask-0",
        )

        self.assertEqual(len(axes), 1)
        self.assertEqual(axes[0].source_id, "mask-0")
        self.assertTrue(axes[0].selected)
        self.assertAlmostEqual(axes[0].angle_deg, 10.0)
        self.assertAlmostEqual(axes[0].center_xy_px[0], 20.0)
        self.assertAlmostEqual(axes[0].center_xy_px[1], 20.0)

    def test_axis_overlay_preserves_physical_angle_for_anisotropic_pixels(
        self,
    ) -> None:
        series = _series_with_elliptical_masks()
        series.metadata = STMSequenceMetadata(
            pixels_x=40,
            pixels_y=40,
            size_nm_x=80.0,
            size_nm_y=40.0,
            scan_angle_deg=0.0,
        )
        series.molecular_orientations = MolecularOrientationStore(
            frame_count=series.frame_count,
            measurements=(_measurement(source_id="mask-0", angle_deg=45.0),),
        )

        axis = build_molecular_orientation_axes(
            series,
            frame_index=0,
            source_view="raw",
        )[0]
        start, end = axis.endpoints_xy_px
        dx_nm = (end[0] - start[0]) * 2.0
        dy_nm = -(end[1] - start[1]) * 1.0

        self.assertAlmostEqual(degrees(atan2(dy_nm, dx_nm)), 45.0)


if __name__ == "__main__":
    unittest.main()
