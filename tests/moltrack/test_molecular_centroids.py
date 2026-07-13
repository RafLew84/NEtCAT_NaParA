import unittest
from types import SimpleNamespace

import numpy as np

from moltrack.core import (
    MolecularCentroid,
    MolecularDetection,
    MolecularDetectionSet,
    MolecularSegmentation,
    MolecularSegmentationSet,
    MolTrackImageSeries,
    build_molecular_centroids,
)
from nanotrack.core import STMSequenceMetadata


class MolecularCentroidModelTests(unittest.TestCase):
    def test_centroid_from_segmentation_uses_active_pixel_centers_and_mask_metadata(self) -> None:
        mask = np.zeros((5, 5), dtype=bool)
        mask[1, 1] = True
        mask[3, 3] = True
        segmentation = MolecularSegmentation(
            frame_index=2,
            source_view="expanded_aligned",
            mask=mask,
            origin="sam2",
            segmentation_id="seg-1",
        )

        centroid = MolecularCentroid.from_segmentation(
            segmentation,
            frame_shape=(5, 5),
            scale_nm_per_px=(0.2, 0.4),
        )

        self.assertEqual(centroid.frame_index, 2)
        self.assertEqual(centroid.source_view, "expanded_aligned")
        self.assertEqual((centroid.x_px, centroid.y_px), (2.5, 2.5))
        self.assertEqual((centroid.x_nm, centroid.y_nm), (0.5, 1.0))
        self.assertEqual(centroid.source_kind, "segmentation")
        self.assertEqual(centroid.source_id, "seg-1")
        self.assertEqual(centroid.area_px, 2)
        self.assertEqual(centroid.origin, "sam2")

    def test_centroid_from_detection_uses_bbox_center_as_fallback(self) -> None:
        detection = MolecularDetection(
            frame_index=1,
            bbox_xyxy=(1, 2, 5, 6),
            confidence=0.9,
            source_view="raw",
            detection_id="bbox-1",
            origin="yolo",
        )

        centroid = MolecularCentroid.from_detection(
            detection,
            frame_shape=(8, 9),
        )

        self.assertEqual(centroid.frame_index, 1)
        self.assertEqual(centroid.source_view, "raw")
        self.assertEqual((centroid.x_px, centroid.y_px), (3.0, 4.0))
        self.assertEqual((centroid.x_nm, centroid.y_nm), (None, None))
        self.assertEqual(centroid.source_kind, "bbox_center")
        self.assertEqual(centroid.source_id, "bbox-1")
        self.assertIsNone(centroid.area_px)
        self.assertEqual(centroid.origin, "yolo")

    def test_centroid_factories_reject_sources_incompatible_with_frame_shape(self) -> None:
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(4, 4, 6, 6),
            confidence=0.9,
            detection_id="outside",
        )
        segmentation = MolecularSegmentation(
            frame_index=0,
            mask=np.ones((3, 3), dtype=bool),
            segmentation_id="wrong-shape",
        )

        with self.assertRaisesRegex(ValueError, "within frame"):
            MolecularCentroid.from_detection(detection, frame_shape=(5, 5))
        with self.assertRaisesRegex(ValueError, "mask shape"):
            MolecularCentroid.from_segmentation(segmentation, frame_shape=(5, 5))

    def test_build_centroids_prefers_linked_segmentation_and_keeps_unsegmented_bbox_fallback(self) -> None:
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(0, 0, 3, 3),
                    confidence=0.9,
                    detection_id="bbox-with-mask",
                ),
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(4, 0, 6, 2),
                    confidence=0.8,
                    detection_id="bbox-fallback",
                ),
            ],
            source_view="raw",
            frame_shape=(6, 6),
        )
        mask = np.zeros((6, 6), dtype=bool)
        mask[1:3, 1:3] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                mask=mask,
                prompt_detection_ids=("bbox-with-mask",),
                segmentation_id="seg-1",
                origin="sam2",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 6, 6), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=6, pixels_y=6),
            molecular_detections=detections,
            molecular_segmentations=segmentations,
        )

        centroids = build_molecular_centroids(series, source_view="raw")

        self.assertEqual(
            [(centroid.source_kind, centroid.source_id) for centroid in centroids],
            [("segmentation", "seg-1"), ("bbox_center", "bbox-fallback")],
        )
        self.assertEqual([centroid.area_px for centroid in centroids], [4.0, None])

    def test_build_centroids_can_use_bbox_centers_even_when_linked_masks_exist(self) -> None:
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(0, 0, 4, 4),
                    confidence=0.9,
                    detection_id="bbox-with-mask",
                ),
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(4, 0, 6, 2),
                    confidence=0.8,
                    detection_id="bbox-only",
                ),
            ],
            source_view="raw",
            frame_shape=(6, 6),
        )
        mask = np.zeros((6, 6), dtype=bool)
        mask[0, 0] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                mask=mask,
                prompt_detection_ids=("bbox-with-mask",),
                segmentation_id="seg-1",
                origin="sam2",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 6, 6), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=6, pixels_y=6),
            molecular_detections=detections,
            molecular_segmentations=segmentations,
        )

        centroids = build_molecular_centroids(
            series,
            source_view="raw",
            use_segmentation_centroids=False,
        )

        self.assertEqual(
            [(centroid.source_kind, centroid.source_id) for centroid in centroids],
            [("bbox_center", "bbox-with-mask"), ("bbox_center", "bbox-only")],
        )
        self.assertEqual(
            [(centroid.x_px, centroid.y_px) for centroid in centroids],
            [(2.0, 2.0), (5.0, 1.0)],
        )

    def test_build_centroids_isolates_frame_and_expanded_view_and_uses_physical_scale(self) -> None:
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(0, 0, 2, 2),
                    confidence=0.7,
                    source_view="raw",
                    detection_id="raw-other-view",
                )
            ],
            source_view="raw",
            frame_shape=(6, 6),
        )
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1, 1, 5, 4),
                    confidence=0.9,
                    source_view="expanded_aligned",
                    detection_id="expanded-linked",
                )
            ],
            source_view="expanded_aligned",
            frame_shape=(8, 8),
        )
        detections.set_detections(
            1,
            [
                MolecularDetection(
                    frame_index=1,
                    bbox_xyxy=(5, 5, 7, 7),
                    confidence=0.8,
                    source_view="expanded_aligned",
                    detection_id="other-frame",
                )
            ],
            source_view="expanded_aligned",
            frame_shape=(8, 8),
        )
        expanded_mask = np.zeros((8, 8), dtype=bool)
        expanded_mask[1:3, 2:4] = True
        segmentations = MolecularSegmentationSet(frame_count=2)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="expanded_aligned",
                mask=expanded_mask,
                prompt_detection_ids=("expanded-linked",),
                segmentation_id="expanded-seg",
                origin="sam3",
            )
        )
        metadata = STMSequenceMetadata(
            pixels_x=6,
            pixels_y=6,
            size_nm_x=12.0,
            size_nm_y=6.0,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 6, 6), dtype=np.float32),
            metadata=metadata,
            active_frame_index=1,
            molecular_detections=detections,
            molecular_segmentations=segmentations,
            expanded_aligned_stack=SimpleNamespace(
                frames=np.zeros((2, 8, 8), dtype=np.float32),
                metadata=metadata,
            ),
        )

        centroids = build_molecular_centroids(
            series,
            frame_index=0,
            source_view="expanded_aligned",
        )

        self.assertEqual([centroid.source_id for centroid in centroids], ["expanded-seg"])
        self.assertEqual((centroids[0].x_px, centroids[0].y_px), (3.0, 2.0))
        self.assertEqual((centroids[0].x_nm, centroids[0].y_nm), (6.0, 2.0))


if __name__ == "__main__":
    unittest.main()
