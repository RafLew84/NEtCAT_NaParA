import unittest

import numpy as np

from nanotrack.core.data_models import (
    EdgeAnnotationSource,
    EdgeFrameAnnotation,
    EdgeGeometryQuality,
    EdgeMetrics,
    EdgeTrack,
    FrameVisibility,
    PolygonROI,
    TrackQuality,
)


class PolygonROITests(unittest.TestCase):
    def test_exposes_vertex_count_and_bounds(self) -> None:
        polygon = PolygonROI(
            np.array(
                [
                    [2.0, 4.0],
                    [8.0, 1.0],
                    [11.0, 6.0],
                    [4.0, 9.0],
                ],
                dtype=np.float32,
            )
        )

        self.assertEqual(polygon.vertex_count, 4)
        self.assertEqual(polygon.bounds_xyxy, (2.0, 1.0, 11.0, 9.0))
        np.testing.assert_array_equal(
            polygon.as_array(),
            np.asarray([[2.0, 4.0], [8.0, 1.0], [11.0, 6.0], [4.0, 9.0]], dtype=np.float64),
        )

    def test_rejects_polygon_with_too_few_vertices(self) -> None:
        with self.assertRaises(ValueError):
            PolygonROI(np.asarray([[0.0, 0.0], [1.0, 1.0]], dtype=np.float32))


class EdgeMetricsTests(unittest.TestCase):
    def test_rejects_negative_roughness(self) -> None:
        with self.assertRaises(ValueError):
            EdgeMetrics(roughness_rms_px=-1.0)

    def test_rejects_negative_curvature(self) -> None:
        with self.assertRaises(ValueError):
            EdgeMetrics(max_curvature=-0.5)


class EdgeFrameAnnotationTests(unittest.TestCase):
    def test_normalizes_polyline_and_edge_mask(self) -> None:
        geometry_quality = EdgeGeometryQuality(
            confidence=0.75,
            review_status="ok",
            warnings=("minor_shift",),
            polyline_method="graph",
            extraction_mode="graph_path",
            coarse_score=2.0,
            refinement_score=0.7,
            refinement_stability=0.8,
            mean_shift_px=1.0,
            refinement_mode="normal_dp_combined",
        )
        annotation = EdgeFrameAnnotation(
            frame_index=3,
            polyline=np.asarray([[1, 2], [2, 4], [4, 6]], dtype=np.int32),
            edge_mask=np.asarray([[0, 1], [2, 0]], dtype=np.uint8),
            geometry_quality=geometry_quality,
        )

        self.assertTrue(annotation.has_geometry)
        self.assertTrue(annotation.has_edge_mask)
        self.assertIs(annotation.geometry_quality, geometry_quality)
        self.assertEqual(annotation.polyline.dtype, np.float64)
        self.assertEqual(annotation.polyline_point_count, 3)
        self.assertEqual(annotation.edge_mask.dtype, np.bool_)
        np.testing.assert_array_equal(annotation.edge_mask, [[False, True], [True, False]])

    def test_visible_edge_annotation_requires_geometry(self) -> None:
        with self.assertRaises(ValueError):
            EdgeFrameAnnotation(frame_index=0)

    def test_hidden_annotation_can_exist_without_geometry(self) -> None:
        annotation = EdgeFrameAnnotation(
            frame_index=5,
            visibility=FrameVisibility.LOST,
            source=EdgeAnnotationSource.TRACKER_REFINE,
        )

        self.assertFalse(annotation.has_geometry)
        self.assertEqual(annotation.visibility, FrameVisibility.LOST)

    def test_rejects_polyline_with_too_few_points(self) -> None:
        with self.assertRaises(ValueError):
            EdgeFrameAnnotation(
                frame_index=1,
                polyline=np.asarray([[1.0, 2.0]], dtype=np.float32),
            )

    def test_rejects_invalid_geometry_quality_payload(self) -> None:
        with self.assertRaises(ValueError):
            EdgeGeometryQuality(confidence=1.5)
        with self.assertRaises(ValueError):
            EdgeFrameAnnotation(
                frame_index=1,
                polyline=np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32),
                geometry_quality={"confidence": 0.5},
            )


class EdgeTrackTests(unittest.TestCase):
    def test_seed_annotation_is_inserted_automatically(self) -> None:
        polygon = PolygonROI(np.asarray([[0.0, 0.0], [8.0, 0.0], [6.0, 4.0]], dtype=np.float32))
        seed_polyline = np.asarray([[1.0, 2.0], [3.0, 4.0], [5.0, 5.5]], dtype=np.float32)

        track = EdgeTrack(
            edge_track_id=7,
            seed_frame_index=2,
            polygon_roi=polygon,
            seed_polyline=seed_polyline,
        )

        seed = track.get_annotation(2)

        self.assertIsNotNone(seed)
        np.testing.assert_array_equal(seed.polyline, np.asarray(seed_polyline, dtype=np.float64))
        self.assertEqual(seed.source, EdgeAnnotationSource.MANUAL)
        self.assertEqual(track.visible_frame_indices, [2])
        self.assertEqual(track.end_frame_index, 2)
        self.assertEqual(track.quality, TrackQuality.UNREVIEWED)

    def test_rejects_mismatched_annotation_key(self) -> None:
        polygon = PolygonROI(np.asarray([[0.0, 0.0], [5.0, 0.0], [4.0, 4.0]], dtype=np.float32))
        seed_polyline = np.asarray([[0.0, 1.0], [4.0, 2.0]], dtype=np.float32)

        with self.assertRaises(ValueError):
            EdgeTrack(
                edge_track_id=1,
                seed_frame_index=0,
                polygon_roi=polygon,
                seed_polyline=seed_polyline,
                annotations={
                    3: EdgeFrameAnnotation(
                        frame_index=2,
                        polyline=np.asarray([[1.0, 1.0], [2.0, 2.0]], dtype=np.float32),
                    )
                },
            )

    def test_add_annotation_keeps_frame_order_and_visible_subset(self) -> None:
        polygon = PolygonROI(np.asarray([[0.0, 0.0], [5.0, 0.0], [4.0, 4.0]], dtype=np.float32))
        track = EdgeTrack(
            edge_track_id=3,
            seed_frame_index=1,
            polygon_roi=polygon,
            seed_polyline=np.asarray([[1.0, 2.0], [3.0, 3.0]], dtype=np.float32),
        )

        track.add_annotation(
            EdgeFrameAnnotation(
                frame_index=4,
                polyline=np.asarray([[2.0, 3.0], [4.5, 5.0]], dtype=np.float32),
                visibility=FrameVisibility.VISIBLE,
                source=EdgeAnnotationSource.DEXINED,
            )
        )
        track.add_annotation(
            EdgeFrameAnnotation(
                frame_index=3,
                visibility=FrameVisibility.HIDDEN,
                source=EdgeAnnotationSource.TRACKER_REFINE,
            )
        )

        self.assertEqual(track.frame_indices, [1, 3, 4])
        self.assertEqual(track.visible_frame_indices, [1, 4])
        self.assertEqual(track.end_frame_index, 4)

    def test_drop_annotations_after_preserves_prefix(self) -> None:
        polygon = PolygonROI(np.asarray([[0.0, 0.0], [6.0, 0.0], [4.0, 5.0]], dtype=np.float32))
        track = EdgeTrack(
            edge_track_id=5,
            seed_frame_index=0,
            polygon_roi=polygon,
            seed_polyline=np.asarray([[0.0, 1.0], [3.0, 2.0]], dtype=np.float32),
        )
        track.add_annotation(
            EdgeFrameAnnotation(
                frame_index=1,
                polyline=np.asarray([[1.0, 1.5], [4.0, 2.5]], dtype=np.float32),
                source=EdgeAnnotationSource.DEXINED,
            )
        )
        track.add_annotation(
            EdgeFrameAnnotation(
                frame_index=2,
                polyline=np.asarray([[2.0, 2.0], [5.0, 3.0]], dtype=np.float32),
                source=EdgeAnnotationSource.DEXINED,
            )
        )
        track.add_annotation(
            EdgeFrameAnnotation(
                frame_index=3,
                polyline=np.asarray([[3.0, 2.5], [6.0, 3.5]], dtype=np.float32),
                source=EdgeAnnotationSource.DEXINED,
            )
        )

        track.drop_annotations_after(1)

        self.assertEqual(track.frame_indices, [0, 1])
        self.assertEqual(track.end_frame_index, 1)
        self.assertIsNone(track.get_annotation(2))
        self.assertIsNone(track.get_annotation(3))


if __name__ == "__main__":
    unittest.main()
