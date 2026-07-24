import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.validate_molecular_order_types_ttmapp import (
    build_validation_report,
    validate,
)


def _prior_report():
    return {
        "source_view": "expanded_aligned",
        "source_mpp": "movie.mpp",
        "ranges": [{"name": "before"}, {"name": "after"}],
        "classification_runs": {
            "baseline": {
                "summary": {
                    "observation_count": 187,
                    "classified_observation_count": 77,
                    "unclassified_observation_count": 110,
                    "domain_type_count": 6,
                },
            },
        },
        "manual_review": {"status": "reviewed_with_caution"},
    }


class ValidateMolecularOrderTypesTtmappTests(unittest.TestCase):
    def test_missing_hierarchy_inputs_are_reported_without_false_claims(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            session_path = root / "state.moltrack.json"
            prior_path = root / "prior.json"
            overlay = root / "representative.png"
            session_path.write_text("{}", encoding="utf-8")
            prior_path.write_text(
                json.dumps(_prior_report()),
                encoding="utf-8",
            )
            overlay.write_bytes(b"png")
            session = SimpleNamespace(
                source_path="movie.mpp",
                molecular_orientations=None,
                molecular_stacking_state=None,
                molecular_order_type_analysis_state=None,
            )

            report = build_validation_report(
                session,
                _prior_report(),
                session_path=session_path,
                prior_report_path=prior_path,
                representative_paths=(overlay,),
            )

        self.assertEqual(
            report["status"],
            "partial_insufficient_hierarchical_inputs",
        )
        self.assertEqual(
            report["layer_conclusions"]["geometry"],
            "reviewed_with_caution",
        )
        self.assertEqual(
            report["layer_conclusions"]["molecular_orientation"],
            "not_evaluable_missing_orientation_measurements",
        )
        self.assertEqual(
            report["source_session_sha256"],
            hashlib.sha256(b"{}").hexdigest(),
        )
        self.assertEqual(
            report["prior_geometry_validation"]["representative_overlays"],
            [
                {
                    "path": str(overlay.resolve()),
                    "sha256": hashlib.sha256(b"png").hexdigest(),
                }
            ],
        )
        self.assertFalse(
            report["hierarchical_input_readiness"][
                "ready_for_full_hierarchy_validation"
            ]
        )
        self.assertFalse(
            report["hierarchical_input_readiness"][
                "cache_dependency_match_verified"
            ]
        )
        self.assertIn(
            "No conclusion",
            report["false_confidence_guard"],
        )

    def test_layer_readiness_is_reported_independently(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            session_path = root / "state.moltrack.json"
            prior_path = root / "prior.json"
            overlay = root / "representative.png"
            session_path.write_text("{}", encoding="utf-8")
            prior_path.write_text(
                json.dumps(_prior_report()),
                encoding="utf-8",
            )
            overlay.write_bytes(b"png")
            session = SimpleNamespace(
                source_path="movie.mpp",
                molecular_orientations=SimpleNamespace(
                    measurements=(object(),)
                ),
                molecular_stacking_state=None,
                molecular_order_type_analysis_state=None,
            )

            report = build_validation_report(
                session,
                _prior_report(),
                session_path=session_path,
                prior_report_path=prior_path,
                representative_paths=(overlay,),
            )

        self.assertEqual(
            report["layer_conclusions"]["molecular_orientation"],
            "available_pending_visual_review",
        )
        self.assertEqual(
            report["layer_conclusions"]["stacking"],
            "not_evaluable_missing_stacking_analysis",
        )
        self.assertFalse(
            report["hierarchical_input_readiness"][
                "ready_for_full_hierarchy_validation"
            ]
        )

    def test_validate_skips_full_session_load_when_hierarchy_keys_are_absent(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            session_path = root / "state.moltrack.json"
            prior_dir = root / "prior"
            representatives_dir = prior_dir / "representatives"
            output_dir = root / "output"
            prior_dir.mkdir()
            representatives_dir.mkdir()
            prior_path = prior_dir / "validation_report.json"
            session_path.write_text(
                json.dumps(
                    {
                        "source_path": "ignored.mpp",
                        "segmentations": [{"large": "payload"}],
                    }
                ),
                encoding="utf-8",
            )
            prior_path.write_text(
                json.dumps(_prior_report()),
                encoding="utf-8",
            )
            (representatives_dir / "domain.png").write_bytes(b"png")

            with patch(
                "scripts.validate_molecular_order_types_ttmapp."
                "load_moltrack_session",
                side_effect=AssertionError("full session must not be loaded"),
            ):
                report = validate(session_path, prior_path, output_dir)
            json_report_exists = (
                output_dir / "validation_report.json"
            ).is_file()
            markdown_report_exists = (
                output_dir / "validation_report.md"
            ).is_file()

        self.assertEqual(report["source_mpp"], "movie.mpp")
        self.assertEqual(
            report["status"],
            "partial_insufficient_hierarchical_inputs",
        )
        self.assertTrue(json_report_exists)
        self.assertTrue(markdown_report_exists)


if __name__ == "__main__":
    unittest.main()
