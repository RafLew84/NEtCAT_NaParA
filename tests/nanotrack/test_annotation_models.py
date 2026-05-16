import unittest

import numpy as np

from nanotrack.core.data_models import (
    AnnotationSource,
    BBoxXYXY,
    FrameVisibility,
    ParticleMetrics,
    ParticleTrack,
    TrackFrameAnnotation,
    TrackQuality,
)


class BBoxXYXYTests(unittest.TestCase):
    def test_exposes_size_and_center(self) -> None:
        bbox = BBoxXYXY(2.0, 4.0, 10.0, 16.0)

        self.assertEqual(bbox.width, 8.0)
        self.assertEqual(bbox.height, 12.0)
        self.assertEqual(bbox.center_xy, (6.0, 10.0))
        self.assertEqual(bbox.as_tuple(), (2.0, 4.0, 10.0, 16.0))

    def test_rejects_non_positive_extent(self) -> None:
        with self.assertRaises(ValueError):
            BBoxXYXY(1.0, 2.0, 1.0, 5.0)


class ParticleMetricsTests(unittest.TestCase):
    def test_rejects_negative_area(self) -> None:
        with self.assertRaises(ValueError):
            ParticleMetrics(area_px=-1.0)

    def test_rejects_negative_physical_perimeter(self) -> None:
        with self.assertRaises(ValueError):
            ParticleMetrics(perimeter_nm=-1.0)


class TrackFrameAnnotationTests(unittest.TestCase):
    def test_annotation_source_includes_optional_mask_trackers(self) -> None:
        self.assertEqual(AnnotationSource.DAM4SAM.value, "dam4sam")
        self.assertEqual(AnnotationSource.SAMURAI.value, "samurai")
        self.assertEqual(AnnotationSource("dam4sam"), AnnotationSource.DAM4SAM)
        self.assertEqual(AnnotationSource("samurai"), AnnotationSource.SAMURAI)

    def test_normalizes_mask_to_bool(self) -> None:
        annotation = TrackFrameAnnotation(
            frame_index=3,
            mask=np.array([[0, 1], [2, 0]], dtype=np.uint8),
        )

        self.assertTrue(annotation.has_mask)
        self.assertEqual(annotation.mask.dtype, np.bool_)
        np.testing.assert_array_equal(annotation.mask, [[False, True], [True, False]])

    def test_visible_annotation_requires_geometry(self) -> None:
        with self.assertRaises(ValueError):
            TrackFrameAnnotation(frame_index=0)

    def test_hidden_annotation_can_exist_without_geometry(self) -> None:
        annotation = TrackFrameAnnotation(
            frame_index=5,
            visibility=FrameVisibility.LOST,
            source=AnnotationSource.RESUME,
        )

        self.assertFalse(annotation.has_geometry)
        self.assertEqual(annotation.visibility, FrameVisibility.LOST)


class ParticleTrackTests(unittest.TestCase):
    def test_seed_annotation_is_inserted_automatically(self) -> None:
        track = ParticleTrack(
            track_id=7,
            seed_frame_index=2,
            seed_bbox=BBoxXYXY(1.0, 1.0, 5.0, 6.0),
        )

        seed = track.get_annotation(2)

        self.assertIsNotNone(seed)
        self.assertEqual(seed.bbox, BBoxXYXY(1.0, 1.0, 5.0, 6.0))
        self.assertEqual(seed.source, AnnotationSource.MANUAL)
        self.assertEqual(track.visible_frame_indices, [2])
        self.assertEqual(track.end_frame_index, 2)
        self.assertEqual(track.quality, TrackQuality.UNREVIEWED)

    def test_rejects_mismatched_annotation_key(self) -> None:
        with self.assertRaises(ValueError):
            ParticleTrack(
                track_id=1,
                seed_frame_index=0,
                seed_bbox=BBoxXYXY(0.0, 0.0, 2.0, 2.0),
                annotations={
                    3: TrackFrameAnnotation(
                        frame_index=2,
                        bbox=BBoxXYXY(0.0, 0.0, 2.0, 2.0),
                    )
                },
            )

    def test_add_annotation_keeps_frame_order_and_visible_subset(self) -> None:
        track = ParticleTrack(
            track_id=3,
            seed_frame_index=1,
            seed_bbox=BBoxXYXY(1.0, 2.0, 4.0, 5.0),
        )

        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=4,
                bbox=BBoxXYXY(2.0, 3.0, 6.0, 7.0),
                visibility=FrameVisibility.VISIBLE,
                source=AnnotationSource.SAM2,
            )
        )
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=3,
                visibility=FrameVisibility.HIDDEN,
                source=AnnotationSource.SAM2,
            )
        )

        self.assertEqual(track.frame_indices, [1, 3, 4])
        self.assertEqual(track.visible_frame_indices, [1, 4])
        self.assertEqual(track.end_frame_index, 4)

    def test_drop_annotations_after_preserves_prefix_of_track(self) -> None:
        track = ParticleTrack(
            track_id=5,
            seed_frame_index=0,
            seed_bbox=BBoxXYXY(0.0, 0.0, 3.0, 3.0),
        )
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0),
                source=AnnotationSource.SAM2,
            )
        )
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=2,
                bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
                source=AnnotationSource.SAM2,
            )
        )
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=3,
                bbox=BBoxXYXY(3.0, 3.0, 6.0, 6.0),
                source=AnnotationSource.SAM2,
            )
        )

        track.drop_annotations_after(1)

        self.assertEqual(track.frame_indices, [0, 1])
        self.assertEqual(track.end_frame_index, 1)
        self.assertIsNone(track.get_annotation(2))
        self.assertIsNone(track.get_annotation(3))


if __name__ == "__main__":
    unittest.main()
