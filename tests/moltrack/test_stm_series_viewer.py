import os
import time
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from moltrack.analysis import M6PointOverlay, MolecularOrientationAxis

from moltrack.core import (
    MolecularDetection,
    MolecularDetectionSet,
    MolecularSegmentation,
    MolecularSegmentationSet,
    MolTrackImageSeries,
)
from nanotrack.core import STMSequenceMetadata
from moltrack.sam3 import MolTrackSam3Proposal, build_moltrack_sam3_preview

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.widgets import STMSeriesViewer
else:  # pragma: no cover - optional outside target GUI env
    STMSeriesViewer = None


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for MolTrack viewer tests")
class STMSeriesViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        if hasattr(self, "viewer"):
            self.viewer.close()
            self.viewer.deleteLater()
            self.__class__._app.processEvents()

    def test_viewer_displays_active_frame_with_series_context(self) -> None:
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(
                pixels_x=4,
                pixels_y=2,
                size_nm_x=8.0,
                size_nm_y=1.0,
                image_type="Topo",
            ),
            active_frame_index=1,
        )
        self.viewer = STMSeriesViewer()

        self.viewer.set_image_series(series)

        np.testing.assert_array_equal(self.viewer.viewer.image_item.image, frames[1])
        self.assertEqual(self.viewer.lbl_title.text(), "movie.mpp | Frame 2/3")
        self.assertIn("Shape: 4x2 px", self.viewer.lbl_meta.text())
        self.assertIn("Channel: Topo", self.viewer.lbl_meta.text())

    def test_navigation_with_many_sam2_masks_stays_interactive(self) -> None:
        frame_count = 2
        segmentation_count = 300
        height = width = 128
        segmentations = MolecularSegmentationSet(frame_count=frame_count)
        for frame_index in range(frame_count):
            for segmentation_index in range(segmentation_count):
                x = 1 + (segmentation_index % 20) * 6
                y = 1 + ((segmentation_index // 20) % 15) * 8
                mask = np.zeros((height, width), dtype=bool)
                mask[y : y + 4, x : x + 4] = True
                segmentations.add_segmentation(
                    MolecularSegmentation(
                        frame_index=frame_index,
                        source_view="raw",
                        mask=mask,
                        bbox_xyxy=(x, y, x + 4, y + 4),
                        origin="sam2",
                        segmentation_id=f"sam2-{frame_index}-{segmentation_index}",
                    )
                )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((frame_count, height, width), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=width, pixels_y=height),
            molecular_segmentations=segmentations,
        )
        self.viewer = STMSeriesViewer()
        self.viewer.set_image_series(series)
        self.__class__._app.processEvents()

        started_at = time.perf_counter()
        self.viewer.show_frame(1)
        self.__class__._app.processEvents()
        elapsed = time.perf_counter() - started_at

        self.assertLess(elapsed, 0.12)
        self.assertEqual(self.viewer.visible_molecular_segmentation_count(), 300)
        self.assertEqual(len(self.viewer.visible_molecular_segmentation_ids()), 300)

    def test_m6_overlay_renders_hundreds_of_colored_points_as_one_independent_batch(self) -> None:
        point_count = 600
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1, 1, 4, 4),
                    confidence=0.9,
                    detection_id="bbox-independent",
                )
            ],
            source_view="raw",
            frame_shape=(128, 128),
        )
        segmentations = MolecularSegmentationSet(frame_count=1)
        mask = np.zeros((128, 128), dtype=bool)
        mask[1:4, 1:4] = True
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                mask=mask,
                bbox_xyxy=(1, 1, 4, 4),
                prompt_detection_ids=("bbox-independent",),
                origin="sam2",
                segmentation_id="mask-independent",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 128, 128), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=128, pixels_y=128),
            molecular_detections=detections,
            molecular_segmentations=segmentations,
        )
        self.viewer = STMSeriesViewer()
        self.viewer.set_image_series(series)
        overlay = M6PointOverlay(
            mode="domain_type",
            source_ids=tuple(f"point-{index}" for index in range(point_count)),
            points_xy_px=tuple(
                (float(index % 100), float(index // 100))
                for index in range(point_count)
            ),
            colors_rgba=tuple(
                (20 + index % 200, 100, 180, 153) for index in range(point_count)
            ),
            point_statuses=("domain_type",) * point_count,
        )

        started_at = time.perf_counter()
        self.viewer.show_m6_point_overlay(overlay)
        self.__class__._app.processEvents()
        elapsed = time.perf_counter() - started_at

        self.assertLess(elapsed, 0.5)
        self.assertEqual(self.viewer.visible_m6_overlay_count(), point_count)
        self.assertEqual(self.viewer.m6_overlay_graphics_item_count(), 1)
        self.assertEqual(self.viewer.visible_m6_overlay_colors()[0], (20, 100, 180, 153))
        self.assertEqual(self.viewer.visible_molecular_detection_count(), 1)
        self.assertEqual(self.viewer.visible_molecular_segmentation_count(), 1)

        graphics_item = self.viewer._m6_point_overlay_item
        recolored = M6PointOverlay(
            mode=overlay.mode,
            source_ids=overlay.source_ids,
            points_xy_px=overlay.points_xy_px,
            colors_rgba=tuple((*color[:3], 77) for color in overlay.colors_rgba),
            point_statuses=overlay.point_statuses,
        )
        self.assertTrue(self.viewer.update_m6_point_overlay_colors(recolored))
        self.assertIs(self.viewer._m6_point_overlay_item, graphics_item)
        self.assertTrue(
            all(color[3] == 77 for color in self.viewer.visible_m6_overlay_colors())
        )

        self.viewer.clear_m6_point_overlay()

        self.assertEqual(self.viewer.visible_m6_overlay_count(), 0)
        self.assertEqual(self.viewer.m6_overlay_graphics_item_count(), 0)
        self.assertEqual(self.viewer.visible_molecular_detection_count(), 1)
        self.assertEqual(self.viewer.visible_molecular_segmentation_count(), 1)

    def test_molecular_orientation_axes_render_as_batched_overlay(self) -> None:
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=32,
                pixels_y=32,
                size_nm_x=64.0,
                size_nm_y=64.0,
            ),
        )
        self.viewer = STMSeriesViewer()
        self.viewer.set_image_series(series)
        axes = tuple(
            MolecularOrientationAxis(
                source_id=f"mask-{index}",
                center_xy_px=(float(index + 5), 10.0),
                endpoints_xy_px=(
                    (float(index + 2), 10.0),
                    (float(index + 8), 10.0),
                ),
                angle_deg=0.0,
                confidence=0.9,
                method="mask_principal_axis",
                selected=index == 3,
            )
            for index in range(20)
        )

        self.viewer.show_molecular_orientation_axes(axes)

        self.assertEqual(self.viewer.visible_molecular_orientation_axis_count(), 20)
        self.assertEqual(
            self.viewer.molecular_orientation_axis_graphics_item_count(),
            2,
        )

    def test_domain_type_overlay_exposes_non_tracking_tooltip(self) -> None:
        self.viewer = STMSeriesViewer()
        overlay = M6PointOverlay(
            mode="domain_type",
            source_ids=("molecule-a",),
            points_xy_px=((1.0, 2.0),),
            colors_rgba=((20, 100, 180, 153),),
            point_statuses=("domain_type",),
        )

        self.viewer.show_m6_point_overlay(overlay)

        self.assertIn("structural type", self.viewer.m6_overlay_tooltip().lower())
        self.assertIn("domain id", self.viewer.m6_overlay_tooltip().lower())

    def test_many_small_sam2_masks_use_bbox_regions_on_large_frame(self) -> None:
        size = 1024
        segmentation_count = 300
        segmentations = MolecularSegmentationSet(frame_count=1)
        for segmentation_index in range(segmentation_count):
            x = 1 + (segmentation_index % 20) * 24
            y = 1 + (segmentation_index // 20) * 32
            mask = np.zeros((size, size), dtype=bool)
            mask[y : y + 8, x : x + 8] = True
            segmentations.add_segmentation(
                MolecularSegmentation(
                    frame_index=0,
                    source_view="raw",
                    mask=mask,
                    bbox_xyxy=(x, y, x + 8, y + 8),
                    origin="sam2",
                    segmentation_id=f"sam2-large-{segmentation_index}",
                )
            )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, size, size), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=size, pixels_y=size),
            molecular_segmentations=segmentations,
        )
        self.viewer = STMSeriesViewer()
        self.viewer.set_image_series(series)
        self.__class__._app.processEvents()

        started_at = time.perf_counter()
        self.viewer.show_frame(0)
        self.__class__._app.processEvents()
        elapsed = time.perf_counter() - started_at

        self.assertLess(elapsed, 0.03)
        self.assertEqual(self.viewer.visible_molecular_segmentation_count(), segmentation_count)
        self.assertEqual(len(self.viewer.visible_molecular_segmentation_ids()), segmentation_count)

    def test_navigation_skips_rendering_when_bbox_overlay_is_hidden(self) -> None:
        frame_count = 2
        detection_count = 300
        height = width = 128
        detections = MolecularDetectionSet(frame_count=frame_count)
        for frame_index in range(frame_count):
            frame_detections = []
            for detection_index in range(detection_count):
                x = 1 + (detection_index % 20) * 6
                y = 1 + (detection_index // 20) * 8
                frame_detections.append(
                    MolecularDetection(
                        frame_index=frame_index,
                        bbox_xyxy=(x, y, x + 4, y + 4),
                        confidence=0.9,
                        source_view="raw",
                        detection_id=f"bbox-{frame_index}-{detection_index}",
                    )
                )
            detections.set_detections(
                frame_index,
                frame_detections,
                source_view="raw",
                frame_shape=(height, width),
            )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((frame_count, height, width), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=width, pixels_y=height),
            molecular_detections=detections,
        )
        self.viewer = STMSeriesViewer()
        self.viewer.set_molecular_detection_overlay_visible(False)
        self.viewer.set_image_series(series)
        self.__class__._app.processEvents()

        started_at = time.perf_counter()
        self.viewer.show_frame(1)
        self.__class__._app.processEvents()
        elapsed = time.perf_counter() - started_at

        self.assertLess(elapsed, 0.08)
        self.assertEqual(self.viewer.visible_molecular_detection_count(), 0)
        self.assertEqual(detections.detection_count, frame_count * detection_count)

    def test_viewer_maps_pixels_to_physical_nanometers(self) -> None:
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 2, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=4,
                pixels_y=2,
                size_nm_x=8.0,
                size_nm_y=1.0,
            ),
        )
        self.viewer = STMSeriesViewer()

        self.viewer.set_image_series(series)

        transform = self.viewer.viewer.image_item.transform()
        self.assertAlmostEqual(transform.m11(), 2.0)
        self.assertAlmostEqual(transform.m22(), 0.5)

    def test_viewer_shows_active_frame_segmentations_without_hiding_bbox_overlay(self) -> None:
        frames = np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4)
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1, 1, 3, 3),
                    confidence=0.9,
                    source_view="raw",
                    detection_id="bbox-active",
                )
            ],
            source_view="raw",
            frame_shape=(4, 4),
        )
        segmentations = MolecularSegmentationSet(frame_count=2)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(1, 1, 3, 3),
                mask=np.asarray(
                    [
                        [False, False, False, False],
                        [False, True, True, False],
                        [False, True, True, False],
                        [False, False, False, False],
                    ],
                    dtype=bool,
                ),
                polygon_xy=[(1, 1), (3, 1), (3, 3), (1, 3)],
                prompt_detection_ids=("bbox-active",),
                origin="sam2",
                segmentation_id="seg-active",
            )
        )
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="expanded_aligned",
                mask=np.ones((4, 4), dtype=bool),
                segmentation_id="seg-other-view",
            )
        )
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=1,
                source_view="raw",
                mask=np.ones((4, 4), dtype=bool),
                segmentation_id="seg-other-frame",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
            molecular_segmentations=segmentations,
        )
        self.viewer = STMSeriesViewer()

        self.viewer.set_image_series(series)

        self.assertEqual(self.viewer.visible_molecular_detection_count(), 1)
        self.assertEqual(self.viewer.visible_molecular_segmentation_count(), 1)
        self.assertEqual(self.viewer.visible_molecular_segmentation_ids(), ["seg-active"])

        self.viewer.select_molecular_detection_by_id("bbox-active")

        self.assertEqual(self.viewer.highlighted_molecular_detection_ids(), ["bbox-active"])
        self.assertEqual(self.viewer.highlighted_molecular_segmentation_ids(), ["seg-active"])

        self.viewer.show_frame(1)

        self.assertEqual(self.viewer.visible_molecular_detection_count(), 0)
        self.assertEqual(self.viewer.visible_molecular_segmentation_ids(), ["seg-other-frame"])

    def test_viewer_selects_specific_segmentation_by_mask_pixel(self) -> None:
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
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(1, 1, 2, 2),
                mask=first_mask,
                origin="sam2",
                prompt_detection_ids=("bbox-1",),
                segmentation_id="seg-first",
            )
        )
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(3, 3, 4, 4),
                mask=second_mask,
                origin="sam2",
                prompt_detection_ids=("bbox-1",),
                segmentation_id="seg-second",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_detections=detections,
            molecular_segmentations=segmentations,
        )
        self.viewer = STMSeriesViewer()
        self.viewer.set_image_series(series)

        selected_id = self.viewer.select_molecular_segmentation_at_pixel(3.0, 3.0)

        self.assertEqual(selected_id, "seg-second")
        self.assertEqual(self.viewer.selected_molecular_segmentation_id(), "seg-second")
        self.assertEqual(self.viewer.highlighted_molecular_segmentation_ids(), ["seg-second"])
        self.assertIsNone(self.viewer.selected_molecular_detection_id())

    def test_viewer_shows_sam3_preview_and_clears_it_when_frame_or_view_changes(self) -> None:
        frames = np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4)
        preview = build_moltrack_sam3_preview(
            [
                MolTrackSam3Proposal(
                    frame_index=0,
                    source_view="raw",
                    bbox_xyxy=(1, 1, 3, 3),
                    score=0.81,
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
                    prompt_detection_ids=("bbox-1",),
                    model_name="facebook/sam3",
                )
            ],
            frame_index=0,
            source_view="raw",
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            sam3_preview=preview,
        )
        self.viewer = STMSeriesViewer()

        self.viewer.set_image_series(series)

        self.assertEqual(self.viewer.visible_sam3_preview_count(), 1)
        self.assertEqual(
            self.viewer.visible_sam3_preview_ids(),
            [preview.proposals[0].proposal_id],
        )
        self.assertEqual(self.viewer.visible_molecular_detection_count(), 0)
        self.assertIsNotNone(series.sam3_preview)

        self.viewer.show_frame(1)

        self.assertIsNone(series.sam3_preview)
        self.assertEqual(self.viewer.visible_sam3_preview_count(), 0)

        series.sam3_preview = preview
        expanded_stack = SimpleNamespace(
            frames=frames + 100.0,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            padding_ltrb=(0, 0, 0, 0),
        )

        self.viewer.show_expanded_aligned_frame(series, expanded_stack, 0)

        self.assertIsNone(series.sam3_preview)
        self.assertEqual(self.viewer.visible_sam3_preview_count(), 0)

    def test_viewer_applies_shared_opacity_to_committed_and_sam3_preview_masks(self) -> None:
        mask = np.zeros((4, 4), dtype=bool)
        mask[1:3, 1:3] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                mask=mask,
                origin="sam2",
                segmentation_id="sam2-mask",
            )
        )
        preview = build_moltrack_sam3_preview(
            [
                MolTrackSam3Proposal(
                    frame_index=0,
                    source_view="raw",
                    bbox_xyxy=(1, 1, 3, 3),
                    score=0.9,
                    mask=mask,
                )
            ],
            frame_index=0,
            source_view="raw",
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 4, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_segmentations=segmentations,
            sam3_preview=preview,
        )
        self.viewer = STMSeriesViewer()

        self.viewer.set_molecular_segmentation_overlay_opacity(0.15)
        self.viewer.set_image_series(series)

        self.assertEqual(self.viewer.visible_molecular_segmentation_opacities(), [0.15])
        self.assertEqual(self.viewer.visible_sam3_preview_opacities(), [0.15])


if __name__ == "__main__":
    unittest.main()
