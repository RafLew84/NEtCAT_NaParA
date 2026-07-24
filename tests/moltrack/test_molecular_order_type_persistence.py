import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

from moltrack.analysis import (
    MolecularOrderTypeClassificationSettings,
    MolecularOrderTypeSessionState,
    classify_molecular_order_types,
)
from moltrack.core import MolTrackImageSeries
from moltrack.persistence import load_moltrack_session, save_moltrack_session
from nanotrack.core import STMSequenceMetadata
from test_molecular_order_type_classifier import (
    _compare_scope,
    _domain_frame,
    _hierarchy,
)


def _classification_state():
    hierarchy = _hierarchy(
        _domain_frame(0),
        _domain_frame(
            2,
            symmetry="sixfold",
            theta3_deg=None,
            theta6_deg=30.0,
            orientation_angles=(40.0,),
            stacking_pattern="uniform",
        ),
    )
    classification = classify_molecular_order_types(
        hierarchy,
        analysis_scope=_compare_scope(),
        settings=MolecularOrderTypeClassificationSettings(
            stacking_features=("pattern", "mode"),
        ),
    )
    return (
        hierarchy,
        MolecularOrderTypeSessionState.from_classification(classification),
    )


class MolecularOrderTypePersistenceTests(unittest.TestCase):
    def test_state_round_trip_restores_exact_classification(self) -> None:
        hierarchy, state = _classification_state()

        restored_state = MolecularOrderTypeSessionState.from_dict(
            json.loads(json.dumps(state.to_dict()))
        )

        self.assertEqual(restored_state, state)
        self.assertEqual(
            restored_state.restore_classification_for(hierarchy),
            state.cache_record.classification,
        )
        self.assertFalse(restored_state.uses_tracking)

    def test_changed_hierarchy_rejects_cached_classification(self) -> None:
        hierarchy, state = _classification_state()
        changed_frame = replace(
            hierarchy.frames[0],
            row_assignment_fingerprint="c" * 64,
        )
        changed_hierarchy = replace(
            hierarchy,
            frames=(changed_frame, hierarchy.frames[1]),
        )

        self.assertIsNone(
            state.restore_classification_for(changed_hierarchy)
        )

    def test_corrupt_optional_cache_preserves_scope_and_settings(self) -> None:
        _hierarchy_value, state = _classification_state()
        payload = state.to_dict()
        payload["reproducible_cache"]["classification_fingerprint"] = "bad"

        restored = MolecularOrderTypeSessionState.from_dict(payload)

        self.assertEqual(restored.analysis_scope, state.analysis_scope)
        self.assertEqual(
            restored.classification_settings,
            state.classification_settings,
        )
        self.assertIsNone(restored.cache_record)

    def test_session_round_trip_and_legacy_file_are_supported(self) -> None:
        _hierarchy_value, state = _classification_state()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "movie.mpp"
            source_path.write_bytes(b"molecular order persistence source")
            state_path = root / "state.moltrack.json"
            series = MolTrackImageSeries(
                source_path=source_path,
                raw_frames=np.zeros((3, 8, 8), dtype=np.float32),
                metadata=STMSequenceMetadata(
                    pixels_x=8,
                    pixels_y=8,
                    size_nm_x=80.0,
                    size_nm_y=80.0,
                ),
            )

            save_moltrack_session(
                state_path,
                series,
                {"molecular_order_type_analysis": state},
            )
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            loaded = load_moltrack_session(state_path)

            self.assertEqual(
                loaded.molecular_order_type_analysis_state,
                state,
            )
            self.assertFalse(
                payload["molecular_order_type_analysis"]["uses_tracking"]
            )

            payload.pop("molecular_order_type_analysis")
            state_path.write_text(json.dumps(payload), encoding="utf-8")
            legacy = load_moltrack_session(state_path)

        self.assertIsNone(legacy.molecular_order_type_analysis_state)


if __name__ == "__main__":
    unittest.main()
