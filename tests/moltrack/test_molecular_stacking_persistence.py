import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from moltrack.analysis import (
    MolecularOrientationStore,
    MolecularStackingSessionState,
    restore_molecular_stacking_display_result,
)
from moltrack.analysis.molecular_stacking_overlay import (
    MolecularStackingDisplayResult,
)
from moltrack.core import MolTrackImageSeries
from moltrack.persistence import load_moltrack_session, save_moltrack_session
from nanotrack.core import STMSequenceMetadata
from test_molecular_stacking_analysis import _prototype_analysis


def _display_result() -> MolecularStackingDisplayResult:
    from moltrack.analysis import analyze_molecular_stacking

    frames, prototypes = _prototype_analysis(
        state_for_site=lambda row, column: (row + column) % 2,
    )
    return MolecularStackingDisplayResult(
        frames=frames,
        prototype_analysis=prototypes,
        stacking_analysis=analyze_molecular_stacking(frames, prototypes),
    )


class MolecularStackingPersistenceTests(unittest.TestCase):
    def test_computed_state_round_trip_restores_exact_display_result(self) -> None:
        display = _display_result()
        state = MolecularStackingSessionState.from_display_result(display)

        restored_state = MolecularStackingSessionState.from_dict(
            json.loads(json.dumps(state.to_dict()))
        )
        restored_display = restore_molecular_stacking_display_result(
            restored_state,
            display.frames[0].measurements + display.frames[1].measurements,
        )

        self.assertEqual(restored_state, state)
        self.assertEqual(restored_display, display)
        self.assertEqual(restored_state.status, "computed")
        self.assertEqual(
            restored_state.stacking_analysis_fingerprint,
            state.stacking_analysis_fingerprint,
        )

    def test_changed_orientation_dependency_rejects_restored_cache(self) -> None:
        from dataclasses import replace

        display = _display_result()
        state = MolecularStackingSessionState.from_display_result(display)
        measurements = list(
            display.frames[0].measurements + display.frames[1].measurements
        )
        measurements[0] = replace(
            measurements[0],
            angle_deg=measurements[0].angle_deg + 1.0,
        )

        self.assertIsNone(
            restore_molecular_stacking_display_result(
                state,
                tuple(measurements),
            )
        )

    def test_session_file_round_trip_preserves_complete_stacking_cache(
        self,
    ) -> None:
        display = _display_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "movie.mpp"
            source_path.write_bytes(b"stacking source")
            state_path = root / "stacking.moltrack.json"
            series = MolTrackImageSeries(
                source_path=source_path,
                raw_frames=np.zeros((2, 20, 20), dtype=np.float32),
                metadata=STMSequenceMetadata(
                    pixels_x=20,
                    pixels_y=20,
                    size_nm_x=40.0,
                    size_nm_y=40.0,
                ),
                molecular_orientations=MolecularOrientationStore(
                    frame_count=2,
                    measurements=tuple(
                        measurement
                        for frame in display.frames
                        for measurement in frame.measurements
                    ),
                ),
                molecular_stacking_state=(
                    MolecularStackingSessionState.from_display_result(display)
                ),
            )

            save_moltrack_session(state_path, series)
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            loaded = load_moltrack_session(state_path)

        self.assertEqual(
            payload["molecular_stacking_analysis"]["status"],
            "computed",
        )
        self.assertEqual(
            loaded.molecular_stacking_state,
            series.molecular_stacking_state,
        )

    def test_legacy_session_without_stacking_payload_is_not_computed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "movie.mpp"
            source_path.write_bytes(b"legacy stacking source")
            state_path = root / "legacy.moltrack.json"
            series = MolTrackImageSeries(
                source_path=source_path,
                raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
                metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
            )
            save_moltrack_session(state_path, series)
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            payload.pop("molecular_stacking_analysis", None)
            state_path.write_text(json.dumps(payload), encoding="utf-8")

            loaded = load_moltrack_session(state_path)

        self.assertEqual(loaded.molecular_stacking_state.status, "not_computed")


if __name__ == "__main__":
    unittest.main()
