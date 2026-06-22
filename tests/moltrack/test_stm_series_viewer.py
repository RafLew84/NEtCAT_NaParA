import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

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


if __name__ == "__main__":
    unittest.main()
