import json
import tempfile
import unittest
import zipfile

import numpy as np

from nanotrack.core import (
    AnnotationSource,
    BBoxXYXY,
    EdgeAnnotationSource,
    EdgeFrameAnnotation,
    EdgeGeometryQuality,
    EdgeMetrics,
    EdgeTrack,
    FrameVisibility,
    ParticleMetrics,
    ParticleTrack,
    PolygonROI,
    RegistrationFrameResult,
    RegistrationResultSet,
    RegistrationSettings,
    STMSequence,
    STMSequenceMetadata,
    TrackFrameAnnotation,
    TrackQuality,
    YoloDetection,
    YoloDetectionSet,
)
from nanotrack.mask_trackers import MaskTrackerKind
from nanotrack.persistence import NanoTrackSessionSnapshot, load_session_snapshot, save_session_snapshot


class SessionStoreTests(unittest.TestCase):
    def test_roundtrip_preserves_tracks_masks_metrics_and_preprocessing(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/source.mpp",
            raw_frames=np.arange(3 * 4 * 5, dtype=np.float32).reshape(3, 4, 5),
            metadata=STMSequenceMetadata(
                pixels_x=5,
                pixels_y=4,
                size_nm_x=10.0,
                size_nm_y=8.0,
                frame_interval_s=0.5,
            ),
            active_frame_index=2,
            reverse_frame_order=True,
        )
        sequence.set_frame_excluded(1, True)
        track = ParticleTrack(
            track_id=7,
            seed_frame_index=1,
            seed_bbox=BBoxXYXY(1.0, 1.0, 4.0, 3.0),
            quality=TrackQuality.NEEDS_REVIEW,
            label="NP-7",
        )
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=2,
                bbox=BBoxXYXY(1.5, 1.0, 4.5, 3.5),
                mask=np.asarray(
                    [
                        [False, True, True, False, False],
                        [False, True, True, False, False],
                        [False, False, False, False, False],
                        [False, False, False, False, False],
                    ],
                    dtype=bool,
                ),
                visibility=FrameVisibility.VISIBLE,
                source=AnnotationSource.SAM2,
                metrics=ParticleMetrics(
                    area_px=4.0,
                    perimeter_px=8.0,
                    area_nm2=32.0,
                    perimeter_nm=14.0,
                    intensity_sum=18.0,
                    intensity_mean=4.5,
                    intensity_max=7.0,
                ),
            )
        )
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=3,
                mask=np.zeros((4, 5), dtype=bool),
                visibility=FrameVisibility.LOST,
                source=AnnotationSource.RESUME,
            )
        )
        alternative_tracker_track = ParticleTrack(
            track_id=8,
            seed_frame_index=0,
            seed_bbox=BBoxXYXY(0.5, 0.5, 3.0, 2.5),
            label="NP-8",
        )
        alternative_tracker_track.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(0.75, 0.75, 3.25, 2.75),
                mask=np.asarray(
                    [
                        [False, False, False, False, False],
                        [False, True, True, False, False],
                        [False, True, True, False, False],
                        [False, False, False, False, False],
                    ],
                    dtype=bool,
                ),
                visibility=FrameVisibility.VISIBLE,
                source=AnnotationSource.DAM4SAM,
            )
        )
        alternative_tracker_track.add_annotation(
            TrackFrameAnnotation(
                frame_index=2,
                bbox=BBoxXYXY(1.0, 1.0, 3.5, 3.0),
                mask=np.asarray(
                    [
                        [False, False, False, False, False],
                        [False, False, True, True, False],
                        [False, False, True, True, False],
                        [False, False, False, False, False],
                    ],
                    dtype=bool,
                ),
                visibility=FrameVisibility.VISIBLE,
                source=AnnotationSource.SAMURAI,
            )
        )
        polygon = PolygonROI(np.asarray([[0.0, 0.0], [4.0, 0.0], [4.0, 3.0], [0.0, 3.0]], dtype=np.float64))
        edge_track = EdgeTrack(
            edge_track_id=3,
            seed_frame_index=1,
            polygon_roi=polygon,
            seed_polyline=np.asarray([[0.0, 1.0], [4.0, 1.0]], dtype=np.float64),
            quality=TrackQuality.ACCEPTED,
            label="Edge-3",
        )
        edge_mask = np.zeros((4, 5), dtype=bool)
        edge_mask[1, 1:4] = True
        edge_track.add_annotation(
            EdgeFrameAnnotation(
                frame_index=2,
                polyline=np.asarray([[0.5, 1.5], [4.0, 1.5]], dtype=np.float64),
                edge_mask=edge_mask,
                visibility=FrameVisibility.VISIBLE,
                source=EdgeAnnotationSource.TRACKER_REFINE,
                metrics=EdgeMetrics(
                    length_px=3.5,
                    length_nm=7.0,
                    roughness_rms_px=0.25,
                    roughness_rms_nm=0.5,
                    mean_curvature=0.1,
                    max_curvature=0.2,
                    waviness_amplitude_px=0.4,
                    waviness_amplitude_nm=0.8,
                ),
                geometry_quality=EdgeGeometryQuality(
                    confidence=0.82,
                    review_status="ok",
                    warnings=(),
                    polyline_method="graph",
                    extraction_mode="graph_path",
                    method_explicit=True,
                    coarse_score=4.2,
                    refinement_score=0.74,
                    refinement_stability=0.91,
                    mean_shift_px=1.25,
                    refinement_mode="normal_dp_combined",
                ),
            )
        )
        registration_results = RegistrationResultSet(
            settings=RegistrationSettings(
                backend="phase_correlation",
                reference_strategy="adjacent",
                registration_view="normalized",
                roi_mask=np.asarray(
                    [
                        [True, True, True, False, False],
                        [True, True, True, False, False],
                        [True, True, True, False, False],
                        [True, True, True, False, False],
                    ],
                    dtype=bool,
                ),
                backend_params={"upsample_factor": np.int64(20), "window": "hann"},
            ),
            results_by_frame={
                0: RegistrationFrameResult(
                    frame_index=0,
                    shift_xy=(0.0, 0.0),
                    method="identity",
                    quality_score=1.0,
                    status="ok",
                ),
                1: RegistrationFrameResult(
                    frame_index=1,
                    shift_xy=(1.25, -0.5),
                    method="phase_correlation_adjacent",
                    quality_score=0.75,
                    phase_peak_ratio=2.8,
                    status="low_confidence",
                ),
                2: RegistrationFrameResult(
                    frame_index=2,
                    shift_xy=(2.0, -1.0),
                    method="phase_correlation_adjacent",
                    quality_score=0.7,
                    phase_peak_ratio=3.1,
                    ecc_score=0.91,
                    num_inlier_tiles=7,
                    num_total_tiles=9,
                    median_tile_residual=0.2,
                    flow_mad=0.15,
                    status="ok",
                ),
            },
            reference_frame_index=0,
            template_frame_indices=(0,),
        )
        snapshot = NanoTrackSessionSnapshot(
            sequence=sequence,
            tracks=[track, alternative_tracker_track],
            edge_tracks=[edge_track],
            yolo_detections=YoloDetectionSet(
                model_name="yolo11s_v2.0",
                source_path=sequence.source_path,
                detections_by_frame={
                    0: [
                        YoloDetection(
                            frame_index=0,
                            bbox=BBoxXYXY(0.5, 0.5, 2.5, 2.0),
                            confidence=0.91,
                            selected=True,
                            model_name="yolo11s_v2.0",
                        )
                    ],
                    2: [
                        YoloDetection(
                            frame_index=2,
                            bbox=BBoxXYXY(1.0, 1.5, 4.5, 3.5),
                            confidence=0.66,
                            selected=False,
                            model_name="yolo11s_v2.0",
                        )
                    ],
                },
            ),
            selected_track_id=7,
            selected_edge_track_id=3,
            selected_mask_tracker_kind=MaskTrackerKind.SAMURAI.value,
            draft_bboxes_by_frame={2: BBoxXYXY(0.0, 0.0, 3.0, 2.0)},
            draft_polygons_by_frame={2: polygon},
            draft_edge_polylines_by_frame={2: np.asarray([[0.0, 2.0], [4.0, 2.0]], dtype=np.float64)},
            repair_frames=np.full_like(sequence.raw_frames, 0.25, dtype=np.float32),
            repair_params={"threshold_sigma": 3.0, "repair_mode": "vertical_interp"},
            denoised_frames=np.full_like(sequence.raw_frames, 0.75, dtype=np.float32),
            denoised_sigma_factor=1.4,
            show_denoised_in_viewer=True,
            registration_results=registration_results,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = f"{tmpdir}/roundtrip.nanotrack"
            save_session_snapshot(session_path, snapshot)

            loaded = load_session_snapshot(
                session_path,
                sequence_loader=lambda _path, reverse_frame_order=False: STMSequence(
                    source_path="/tmp/source.mpp",
                    raw_frames=np.arange(3 * 4 * 5, dtype=np.float32).reshape(3, 4, 5),
                    metadata=STMSequenceMetadata(
                        pixels_x=5,
                        pixels_y=4,
                        size_nm_x=10.0,
                        size_nm_y=8.0,
                        frame_interval_s=0.5,
                    ),
                    reverse_frame_order=reverse_frame_order,
                ),
            )

        self.assertEqual(loaded.sequence.source_path, "/tmp/source.mpp")
        self.assertEqual(loaded.sequence.active_frame_index, 2)
        self.assertTrue(loaded.sequence.reverse_frame_order)
        self.assertTrue(loaded.sequence.is_frame_excluded(1))
        self.assertEqual(loaded.selected_track_id, 7)
        self.assertEqual(loaded.selected_edge_track_id, 3)
        self.assertEqual(loaded.selected_mask_tracker_kind, MaskTrackerKind.SAMURAI.value)
        self.assertTrue(loaded.show_denoised_in_viewer)
        self.assertIsNotNone(loaded.yolo_detections)
        self.assertEqual(loaded.draft_bboxes_by_frame[2], BBoxXYXY(0.0, 0.0, 3.0, 2.0))
        np.testing.assert_array_equal(loaded.draft_polygons_by_frame[2].as_array(), polygon.as_array())
        np.testing.assert_array_equal(
            loaded.draft_edge_polylines_by_frame[2],
            np.asarray([[0.0, 2.0], [4.0, 2.0]], dtype=np.float64),
        )
        np.testing.assert_array_equal(loaded.repair_frames, snapshot.repair_frames)
        np.testing.assert_array_equal(loaded.denoised_frames, snapshot.denoised_frames)
        self.assertEqual(loaded.repair_params, snapshot.repair_params)
        self.assertEqual(loaded.denoised_sigma_factor, 1.4)
        self.assertIsNotNone(loaded.registration_results)
        loaded_registration = loaded.registration_results
        assert loaded_registration is not None
        self.assertEqual(loaded_registration.reference_frame_index, 0)
        self.assertEqual(loaded_registration.template_frame_indices, (0,))
        self.assertEqual(loaded_registration.frame_indices, [0, 1, 2])
        self.assertEqual(loaded_registration.settings.registration_view, "normalized")
        self.assertEqual(loaded_registration.settings.backend_params["upsample_factor"], 20)
        np.testing.assert_array_equal(
            loaded_registration.settings.roi_mask,
            registration_results.settings.roi_mask,
        )
        np.testing.assert_allclose(
            loaded_registration.shifts_xy_array(),
            np.asarray([[0.0, 0.0], [1.25, -0.5], [2.0, -1.0]], dtype=np.float64),
        )
        self.assertEqual(loaded_registration.get_result(1).status, "low_confidence")
        self.assertAlmostEqual(loaded_registration.get_result(1).phase_peak_ratio, 2.8)
        self.assertAlmostEqual(loaded_registration.get_result(2).ecc_score, 0.91)
        self.assertEqual(loaded_registration.get_result(2).num_inlier_tiles, 7)
        self.assertEqual(loaded_registration.get_result(2).num_total_tiles, 9)
        self.assertAlmostEqual(loaded_registration.get_result(2).median_tile_residual, 0.2)
        self.assertAlmostEqual(loaded_registration.get_result(2).flow_mad, 0.15)

        restored_track = loaded.tracks[0]
        self.assertEqual(restored_track.track_id, 7)
        self.assertEqual(restored_track.label, "NP-7")
        self.assertEqual(restored_track.quality, TrackQuality.NEEDS_REVIEW)
        restored_visible = restored_track.get_annotation(2)
        self.assertEqual(restored_visible.source, AnnotationSource.SAM2)
        np.testing.assert_array_equal(restored_visible.mask, track.get_annotation(2).mask)
        self.assertEqual(restored_visible.metrics.area_px, 4.0)
        self.assertEqual(restored_visible.metrics.perimeter_px, 8.0)
        self.assertEqual(restored_visible.metrics.area_nm2, 32.0)
        self.assertEqual(restored_visible.metrics.perimeter_nm, 14.0)
        self.assertEqual(restored_visible.metrics.intensity_sum, 18.0)
        restored_lost = restored_track.get_annotation(3)
        self.assertEqual(restored_lost.visibility, FrameVisibility.LOST)
        np.testing.assert_array_equal(restored_lost.mask, np.zeros((4, 5), dtype=bool))
        restored_alternative_track = loaded.tracks[1]
        self.assertEqual(restored_alternative_track.track_id, 8)
        self.assertEqual(restored_alternative_track.label, "NP-8")
        restored_dam4sam_annotation = restored_alternative_track.get_annotation(1)
        self.assertEqual(restored_dam4sam_annotation.source, AnnotationSource.DAM4SAM)
        np.testing.assert_array_equal(
            restored_dam4sam_annotation.mask,
            alternative_tracker_track.get_annotation(1).mask,
        )
        restored_samurai_annotation = restored_alternative_track.get_annotation(2)
        self.assertEqual(restored_samurai_annotation.source, AnnotationSource.SAMURAI)
        np.testing.assert_array_equal(
            restored_samurai_annotation.mask,
            alternative_tracker_track.get_annotation(2).mask,
        )

        restored_edge_track = loaded.edge_tracks[0]
        self.assertEqual(restored_edge_track.edge_track_id, 3)
        self.assertEqual(restored_edge_track.label, "Edge-3")
        self.assertEqual(restored_edge_track.quality, TrackQuality.ACCEPTED)
        np.testing.assert_array_equal(restored_edge_track.polygon_roi.as_array(), polygon.as_array())
        restored_edge_annotation = restored_edge_track.get_annotation(2)
        self.assertEqual(restored_edge_annotation.source, EdgeAnnotationSource.TRACKER_REFINE)
        np.testing.assert_array_equal(restored_edge_annotation.edge_mask, edge_mask)
        self.assertEqual(restored_edge_annotation.metrics.length_px, 3.5)
        self.assertEqual(restored_edge_annotation.metrics.length_nm, 7.0)
        self.assertIsNotNone(restored_edge_annotation.geometry_quality)
        self.assertAlmostEqual(restored_edge_annotation.geometry_quality.confidence, 0.82)
        self.assertEqual(restored_edge_annotation.geometry_quality.review_status, "ok")
        self.assertEqual(restored_edge_annotation.geometry_quality.polyline_method, "graph")
        self.assertEqual(restored_edge_annotation.geometry_quality.extraction_mode, "graph_path")
        self.assertAlmostEqual(restored_edge_annotation.geometry_quality.refinement_stability, 0.91)
        restored_yolo_detections = loaded.yolo_detections
        self.assertEqual(restored_yolo_detections.model_name, "yolo11s_v2.0")
        self.assertEqual(restored_yolo_detections.source_path, "/tmp/source.mpp")
        self.assertEqual(restored_yolo_detections.detection_count, 2)
        restored_selected = restored_yolo_detections.get_detections(0)[0]
        self.assertTrue(restored_selected.selected)
        self.assertAlmostEqual(restored_selected.confidence, 0.91)
        self.assertEqual(restored_selected.bbox, BBoxXYXY(0.5, 0.5, 2.5, 2.0))
        restored_unselected = restored_yolo_detections.get_detections(2)[0]
        self.assertFalse(restored_unselected.selected)
        self.assertAlmostEqual(restored_unselected.confidence, 0.66)
        self.assertEqual(restored_unselected.bbox, BBoxXYXY(1.0, 1.5, 4.5, 3.5))

    def test_load_session_without_mask_tracker_kind_defaults_to_sam2(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = f"{tmpdir}/legacy.nanotrack"
            manifest = {
                "schema": "nanotrack.session.v1",
                "sequence": {
                    "source_path": "/tmp/legacy.mpp",
                    "active_frame_index": 0,
                    "reverse_frame_order": False,
                    "excluded_frame_indices": [],
                },
                "selected_track_id": None,
                "selected_edge_track_id": None,
                "show_denoised_in_viewer": False,
                "yolo_detections": None,
                "registration_results": None,
                "draft_bboxes": [],
                "draft_polygons": [],
                "draft_edge_polylines": [],
                "preprocessing": {"repair_params": None, "denoised_sigma_factor": None},
                "tracks": [],
                "edge_tracks": [],
            }
            with zipfile.ZipFile(session_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

            loaded = load_session_snapshot(
                session_path,
                sequence_loader=lambda _path, reverse_frame_order=False: STMSequence(
                    source_path="/tmp/legacy.mpp",
                    raw_frames=np.zeros((1, 4, 5), dtype=np.float32),
                    metadata=STMSequenceMetadata(pixels_x=5, pixels_y=4, size_nm_x=10.0, size_nm_y=8.0),
                    reverse_frame_order=reverse_frame_order,
                ),
            )

        self.assertEqual(loaded.selected_mask_tracker_kind, MaskTrackerKind.SAM2.value)


if __name__ == "__main__":
    unittest.main()
