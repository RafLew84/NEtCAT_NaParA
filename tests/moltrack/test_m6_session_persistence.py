import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import numpy as np

from moltrack.analysis import (
    MolecularM6OrientationAnalysisSettings,
    MolecularM6SessionState,
    MolecularM6ViewSettings,
    analyze_molecular_m6_orientation,
    build_molecular_sample_coordinates,
    build_structural_analysis_cache_key,
)
from moltrack.analysis.structural_analysis_cache import (
    _get_or_compute_molecular_m6_orientation,
)
from moltrack.core import (
    MolecularDetection,
    MolecularDetectionSet,
    MolTrackImageSeries,
    build_molecular_centroids,
)
from moltrack.persistence import (
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
    save_moltrack_session,
)
from nanotrack.core import STMSequenceMetadata


def _triangular_patch(
    angle_deg: float,
    shift_xy_nm: tuple[float, float],
    *,
    width: int = 5,
    height: int = 5,
) -> np.ndarray:
    points = np.asarray(
        [
            (2.0 * (column + 0.5 * (row % 2)), math.sqrt(3.0) * row)
            for row in range(height)
            for column in range(width)
        ],
        dtype=np.float64,
    )
    angle = math.radians(angle_deg)
    rotation = np.asarray(
        ((math.cos(angle), -math.sin(angle)), (math.sin(angle), math.cos(angle))),
        dtype=np.float64,
    )
    return points @ rotation.T + np.asarray(shift_xy_nm)


def _settings() -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings(
        first_shell_r_min_nm=1.5,
        first_shell_r_max_nm=2.3,
        min_ordered_component_size=3,
        min_seed_size=5,
        min_domain_size=8,
        footprint_support_radius_nm=1.2,
        gr_bin_width_nm=0.25,
        gr_max_nm=30.0,
        gr_min_expected_pair_exposure=0.1,
    )


def _series(source_path: Path) -> MolTrackImageSeries:
    frame_size = 80
    points = np.vstack(
        (
            _triangular_patch(0.0, (6.0, 8.0)),
            _triangular_patch(22.0, (42.0, 8.0)),
        )
    )
    detections = MolecularDetectionSet(frame_count=1)
    detections.set_detections(
        0,
        [
            MolecularDetection(
                frame_index=0,
                bbox_xyxy=(
                    x - 0.2,
                    frame_size - y - 0.2,
                    x + 0.2,
                    frame_size - y + 0.2,
                ),
                confidence=0.9,
                detection_id=f"molecule-{index}",
            )
            for index, (x, y) in enumerate(points)
        ],
        source_view="raw",
        frame_shape=(frame_size, frame_size),
    )
    return MolTrackImageSeries(
        source_path=str(source_path),
        raw_frames=np.zeros((1, frame_size, frame_size), dtype=np.float32),
        metadata=STMSequenceMetadata(
            raw_header={"General Info": {"Angle": "0.0"}},
            pixels_x=frame_size,
            pixels_y=frame_size,
            size_nm_x=float(frame_size),
            size_nm_y=float(frame_size),
            scan_angle_deg=0.0,
        ),
        molecular_detections=detections,
    )


def _sample(series: MolTrackImageSeries):
    centroids = build_molecular_centroids(
        series,
        frame_index=0,
        source_view="raw",
        use_segmentation_centroids=True,
    )
    return build_molecular_sample_coordinates(
        series,
        centroids,
        frame_index=0,
        source_view="raw",
    )


class MolecularM6SessionPersistenceTests(unittest.TestCase):
    def test_round_trip_restores_settings_view_and_reproducible_multi_domain_cache(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            source_path = directory / "movie.mpp"
            source_path.write_bytes(b"M6 persistence source")
            session_path = directory / "state.moltrack.json"
            series = _series(source_path)
            settings = _settings()
            sample = _sample(series)
            original = _get_or_compute_molecular_m6_orientation(
                series,
                sample,
                use_segmentation_centroids=True,
                settings=settings,
            )
            self.assertEqual(original.segmentation.full_domain_count, 2)
            series.m6_analysis_state = MolecularM6SessionState(
                enabled=True,
                source_view="raw",
                use_segmentation_centroids=True,
                settings=settings,
                view_settings=MolecularM6ViewSettings(
                    show_domain_overlay=True,
                    overlay_mode="symmetry_evidence",
                    show_first_shell_graph=True,
                    show_unassigned_points=False,
                    overlay_opacity_percent=47,
                ),
            )

            save_moltrack_session(session_path, series)
            payload = json.loads(session_path.read_text(encoding="utf-8"))
            loaded = load_moltrack_session(session_path)

            m6_payload = payload["molecular_m6_analysis"]
            self.assertTrue(m6_payload["enabled"])
            self.assertEqual(m6_payload["settings"]["gr_bin_width_nm"], 0.25)
            self.assertEqual(m6_payload["settings"]["gr_max_nm"], 30.0)
            self.assertEqual(
                m6_payload["settings"]["delaunay_degeneracy_policy"],
                "exclude_ambiguous_edges",
            )
            cache_payload = m6_payload["reproducible_cache"]
            self.assertEqual(len(cache_payload), 1)
            self.assertEqual(cache_payload[0]["cache_key"]["coordinate_transform_fingerprint"], sample.coordinate_transform_fingerprint)
            self.assertEqual(cache_payload[0]["cache_key"]["spatial_calibration_fingerprint"], sample.spatial_calibration_fingerprint)
            self.assertEqual(cache_payload[0]["cache_key"]["registration_fingerprint"], "unregistered")
            self.assertEqual(cache_payload[0]["sample_coordinates"]["coordinate_frame"], "sample_nm")
            self.assertEqual(cache_payload[0]["sample_coordinates"]["orientation_reference"], "+x_sample_axis")
            self.assertEqual(cache_payload[0]["sample_coordinates"]["valid_fov_polygon_xy_nm"], [list(point) for point in sample.valid_fov_polygon_xy_nm])
            self.assertTrue(loaded.m6_analysis_state.enabled)
            self.assertEqual(loaded.m6_analysis_state.view_settings.overlay_opacity_percent, 47)
            self.assertEqual(
                loaded.m6_analysis_state.view_settings.overlay_mode,
                "symmetry_evidence",
            )

            m6_payload["view_settings"].pop("overlay_mode")
            session_path.write_text(json.dumps(payload), encoding="utf-8")
            legacy_view = load_moltrack_session(session_path)
            self.assertEqual(
                legacy_view.m6_analysis_state.view_settings.overlay_mode,
                "domain_id",
            )

            def loader(path, *, reverse_frame_order=False):
                restored_source = _series(Path(path))
                restored_source.reverse_frame_order = reverse_frame_order
                return restored_source

            restored_series = restore_moltrack_image_series_from_session(
                loaded,
                series_loader=loader,
            )
            restored_sample = _sample(restored_series)
            restored_key = build_structural_analysis_cache_key(
                restored_series,
                restored_sample,
                use_segmentation_centroids=True,
                settings=settings,
            )
            self.assertEqual(
                restored_series.structural_analysis_cache.keys(),
                (restored_key,),
            )
            recompute = Mock(wraps=analyze_molecular_m6_orientation)
            restored = _get_or_compute_molecular_m6_orientation(
                restored_series,
                restored_sample,
                use_segmentation_centroids=True,
                settings=settings,
                analysis_factory=recompute,
            )
            repeated = _get_or_compute_molecular_m6_orientation(
                restored_series,
                restored_sample,
                use_segmentation_centroids=True,
                settings=settings,
                analysis_factory=recompute,
            )

        self.assertIsNotNone(restored)
        self.assertIs(repeated, restored)
        self.assertEqual(recompute.call_count, 1)
        self.assertIsNotNone(restored.local_multisymmetry_order)
        self.assertIsNotNone(restored.local_symmetry_evidence)
        self.assertEqual(restored.segmentation.full_domain_count, 2)
        self.assertEqual(restored.segmentation.domains, original.segmentation.domains)
        self.assertEqual(
            restored.pair_correlation.observed_unordered_pair_count,
            original.pair_correlation.observed_unordered_pair_count,
        )
        np.testing.assert_allclose(
            restored.pair_correlation.g_r,
            original.pair_correlation.g_r,
            equal_nan=True,
        )

    def test_old_payload_without_m6_fields_loads_with_disabled_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            source_path = directory / "movie.mpp"
            source_path.write_bytes(b"old M6 state source")
            source_stat = source_path.stat()
            session_path = directory / "old-state.moltrack.json"
            session_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source": {
                            "path": str(source_path),
                            "size_bytes": source_stat.st_size,
                            "mtime_ns": source_stat.st_mtime_ns,
                        },
                        "working_series": {
                            "source_frame_indices": [0],
                            "active_frame_index": 0,
                            "reverse_frame_order": False,
                        },
                        "ui": {"registration_view_mode": "Show raw"},
                        "registration": None,
                        "molecular_detections": None,
                        "molecular_segmentations": None,
                    }
                ),
                encoding="utf-8",
            )

            loaded = load_moltrack_session(session_path)

        self.assertFalse(loaded.m6_analysis_state.enabled)
        self.assertEqual(
            loaded.m6_analysis_state.settings,
            MolecularM6OrientationAnalysisSettings(),
        )
        self.assertEqual(loaded.structural_analysis_cache_records, ())

    def test_incompatible_saved_fingerprint_recomputes_current_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            source_path = directory / "movie.mpp"
            source_path.write_bytes(b"stale M6 cache source")
            session_path = directory / "state.moltrack.json"
            series = _series(source_path)
            settings = _settings()
            sample = _sample(series)
            _get_or_compute_molecular_m6_orientation(
                series,
                sample,
                use_segmentation_centroids=True,
                settings=settings,
            )
            save_moltrack_session(session_path, series)
            payload = json.loads(session_path.read_text(encoding="utf-8"))
            stale_key = payload["molecular_m6_analysis"]["reproducible_cache"][0]["cache_key"]
            stale_key["annotation_fingerprint"] = "0" * 64
            session_path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = load_moltrack_session(session_path)

            def loader(path, *, reverse_frame_order=False):
                restored_source = _series(Path(path))
                restored_source.reverse_frame_order = reverse_frame_order
                return restored_source

            restored_series = restore_moltrack_image_series_from_session(
                loaded,
                series_loader=loader,
            )

            current_sample = _sample(restored_series)
            current_key = build_structural_analysis_cache_key(
                restored_series,
                current_sample,
                use_segmentation_centroids=True,
                settings=settings,
            )
            self.assertEqual(restored_series.structural_analysis_cache.keys(), ())
            recompute = Mock(wraps=analyze_molecular_m6_orientation)
            _get_or_compute_molecular_m6_orientation(
                restored_series,
                current_sample,
                use_segmentation_centroids=True,
                settings=settings,
                analysis_factory=recompute,
            )

        self.assertEqual(recompute.call_count, 1)
        self.assertNotEqual(
            current_key.annotation_fingerprint,
            loaded.structural_analysis_cache_records[0].cache_key.annotation_fingerprint,
        )
        self.assertEqual(restored_series.structural_analysis_cache.keys(), (current_key,))

    def test_invalid_optional_cache_record_does_not_block_session_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            source_path = directory / "movie.mpp"
            source_path.write_bytes(b"discardable M6 cache source")
            session_path = directory / "state.moltrack.json"
            series = _series(source_path)
            settings = _settings()
            _get_or_compute_molecular_m6_orientation(
                series,
                _sample(series),
                use_segmentation_centroids=True,
                settings=settings,
            )
            save_moltrack_session(session_path, series)
            payload = json.loads(session_path.read_text(encoding="utf-8"))
            cache_record = payload["molecular_m6_analysis"]["reproducible_cache"][0]
            cache_record["cache_record_schema_version"] = 999
            session_path.write_text(json.dumps(payload), encoding="utf-8")

            loaded = load_moltrack_session(session_path)

        self.assertFalse(loaded.m6_analysis_state.enabled)
        self.assertIsNotNone(loaded.molecular_detections)
        self.assertEqual(loaded.structural_analysis_cache_records, ())


if __name__ == "__main__":
    unittest.main()
