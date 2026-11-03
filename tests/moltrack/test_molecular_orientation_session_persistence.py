import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from moltrack.analysis import (
    MolecularOrientationMeasurement,
    MolecularOrientationProvenance,
    MolecularOrientationStore,
)
from moltrack.core import MolTrackImageSeries
from moltrack.persistence import (
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
    save_moltrack_session,
)
from nanotrack.core import STMSequenceMetadata


def _corrected_measurement() -> MolecularOrientationMeasurement:
    automatic = MolecularOrientationMeasurement(
        measurement_id="orientation:segmentation:mask-1",
        status="available",
        angle_deg=20.0,
        periodicity_deg=180.0,
        confidence=0.75,
        method="mask_principal_axis",
        patch_shape_px=(12, 14),
        provenance=MolecularOrientationProvenance(
            source_file_name="movie.mpp",
            source_file_sha256="a" * 64,
            source_session_file_name=None,
            source_session_sha256=None,
            frame_index=0,
            source_view="raw",
            source_kind="segmentation",
            source_id="mask-1",
            patch_bbox_xyxy=(3.0, 4.0, 17.0, 16.0),
            orientation_reference="sample_x_axis_counterclockwise",
        ),
    )
    return automatic.with_manual_correction(
        status="available",
        angle_deg=35.0,
        confidence=1.0,
        reviewer="MolTrack user",
        note="Checked in viewer.",
    )


class MolecularOrientationSessionPersistenceTests(unittest.TestCase):
    def test_round_trip_preserves_automatic_and_manual_orientation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "movie.mpp"
            source_path.write_bytes(b"orientation source")
            state_path = root / "orientation.moltrack.json"
            series = MolTrackImageSeries(
                source_path=source_path,
                raw_frames=np.zeros((1, 20, 20), dtype=np.float32),
                metadata=STMSequenceMetadata(
                    pixels_x=20,
                    pixels_y=20,
                    size_nm_x=40.0,
                    size_nm_y=40.0,
                ),
                molecular_orientations=MolecularOrientationStore(
                    frame_count=1,
                    measurements=(_corrected_measurement(),),
                ),
            )

            save_moltrack_session(state_path, series)
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            loaded = load_moltrack_session(state_path)
            restored_series = restore_moltrack_image_series_from_session(
                loaded,
                series_loader=lambda _path, **_kwargs: MolTrackImageSeries(
                    source_path=source_path,
                    raw_frames=np.zeros((1, 20, 20), dtype=np.float32),
                    metadata=STMSequenceMetadata(
                        pixels_x=20,
                        pixels_y=20,
                        size_nm_x=40.0,
                        size_nm_y=40.0,
                    ),
                ),
            )

        self.assertIn("molecular_orientations", payload)
        restored = loaded.molecular_orientations.get(
            "segmentation",
            "mask-1",
        )
        self.assertTrue(restored.is_manually_corrected)
        self.assertAlmostEqual(restored.angle_deg, 35.0)
        self.assertAlmostEqual(
            restored.manual_correction.original_result.angle_deg,
            20.0,
        )
        restored_from_series = restored_series.molecular_orientations.get(
            "segmentation",
            "mask-1",
        )
        self.assertEqual(restored_from_series, restored)

    def test_state_without_orientation_payload_remains_loadable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "movie.mpp"
            source_path.write_bytes(b"legacy orientation source")
            state_path = root / "legacy.moltrack.json"
            series = MolTrackImageSeries(
                source_path=source_path,
                raw_frames=np.zeros((1, 8, 8), dtype=np.float32),
                metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
            )
            save_moltrack_session(state_path, series)
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            payload.pop("molecular_orientations")
            state_path.write_text(json.dumps(payload), encoding="utf-8")

            loaded = load_moltrack_session(state_path)

        self.assertIsNone(loaded.molecular_orientations)

    def test_malformed_orientation_measurements_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "movie.mpp"
            source_path.write_bytes(b"malformed orientation source")
            state_path = root / "malformed.moltrack.json"
            series = MolTrackImageSeries(
                source_path=source_path,
                raw_frames=np.zeros((1, 8, 8), dtype=np.float32),
                metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
            )
            save_moltrack_session(state_path, series)
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            payload["molecular_orientations"] = {
                "frame_count": 1,
                "measurements": "not-a-list",
            }
            state_path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError,
                "molecular_orientations.measurements must be a list",
            ):
                load_moltrack_session(state_path)


if __name__ == "__main__":
    unittest.main()
