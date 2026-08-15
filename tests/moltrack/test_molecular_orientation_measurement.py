import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from moltrack.analysis import (
    MolecularOrientationDomainContext,
    MolecularOrientationMeasurement,
    MolecularOrientationProvenance,
    MolecularOrientationReferenceDataset,
    MolecularOrientationReferenceSample,
    load_molecular_orientation_reference,
    save_molecular_orientation_reference,
)


def _provenance(
    *,
    frame_index: int = 258,
    source_id: str = "segmentation-1",
) -> MolecularOrientationProvenance:
    return MolecularOrientationProvenance(
        source_file_name="MOVIE_23raw_TTMAPP_I_AU111.MPP",
        source_file_sha256="a" * 64,
        source_session_file_name="m6_state.moltrack.json",
        source_session_sha256="b" * 64,
        frame_index=frame_index,
        source_view="expanded_aligned",
        source_kind="segmentation",
        source_id=source_id,
        patch_bbox_xyxy=(120.0, 80.0, 151.0, 111.0),
        orientation_reference="sample_x_axis_counterclockwise",
    )


class MolecularOrientationMeasurementTests(unittest.TestCase):
    def test_available_measurement_normalizes_angle_to_molecular_periodicity(
        self,
    ) -> None:
        measurement = MolecularOrientationMeasurement(
            measurement_id="ttmapp-frame-259-molecule-1",
            status="available",
            angle_deg=191.5,
            periodicity_deg=180.0,
            confidence=0.9,
            method="manual",
            patch_shape_px=(31, 31),
            provenance=_provenance(),
        )

        self.assertEqual(measurement.status, "available")
        self.assertAlmostEqual(measurement.angle_deg, 11.5)
        self.assertEqual(measurement.periodicity_deg, 180.0)
        self.assertEqual(measurement.confidence, 0.9)
        self.assertEqual(measurement.method, "manual")
        self.assertEqual(measurement.patch_shape_px, (31, 31))
        self.assertEqual(measurement.provenance.source_id, "segmentation-1")

    def test_manual_correction_can_be_reset_to_the_original_result(self) -> None:
        automatic = MolecularOrientationMeasurement(
            measurement_id="ttmapp-frame-259-molecule-2",
            status="ambiguous",
            angle_deg=74.0,
            periodicity_deg=180.0,
            confidence=0.35,
            method="stm_topography",
            patch_shape_px=(31, 31),
            provenance=_provenance(),
        )

        corrected = automatic.with_manual_correction(
            status="available",
            angle_deg=205.0,
            confidence=1.0,
            reviewer="rlewa",
            note="Axis checked against the STM patch.",
        )

        self.assertEqual(corrected.status, "available")
        self.assertAlmostEqual(corrected.angle_deg, 25.0)
        self.assertEqual(corrected.confidence, 1.0)
        self.assertEqual(corrected.method, "manual_correction")
        self.assertTrue(corrected.is_manually_corrected)
        self.assertEqual(corrected.manual_correction.reviewer, "rlewa")
        self.assertEqual(corrected.reset_manual_correction(), automatic)

        restored = MolecularOrientationMeasurement.from_dict(
            corrected.to_dict()
        )
        self.assertEqual(restored, corrected)
        self.assertEqual(restored.reset_manual_correction(), automatic)

    def test_unavailable_orientation_is_not_encoded_as_zero_degrees(self) -> None:
        unavailable = MolecularOrientationMeasurement(
            measurement_id="ttmapp-frame-259-unavailable",
            status="unavailable",
            angle_deg=None,
            periodicity_deg=180.0,
            confidence=None,
            method="manual",
            patch_shape_px=(31, 31),
            provenance=_provenance(),
        )

        self.assertIsNone(unavailable.angle_deg)
        self.assertIsNone(unavailable.confidence)
        with self.assertRaisesRegex(ValueError, "must not contain angle_deg"):
            MolecularOrientationMeasurement(
                measurement_id="invalid-zero-angle",
                status="unavailable",
                angle_deg=0.0,
                periodicity_deg=180.0,
                confidence=None,
                method="manual",
                patch_shape_px=(31, 31),
                provenance=_provenance(),
            )

    def test_manual_correction_json_rejects_invalid_original_result(self) -> None:
        automatic = MolecularOrientationMeasurement(
            measurement_id="automatic-before-corruption",
            status="available",
            angle_deg=20.0,
            periodicity_deg=180.0,
            confidence=0.8,
            method="mask_principal_axis",
            patch_shape_px=(31, 31),
            provenance=_provenance(),
        )
        payload = automatic.with_manual_correction(
            status="available",
            angle_deg=30.0,
            confidence=1.0,
            reviewer="rlewa",
        ).to_dict()
        payload["manual_correction"]["original_result"]["status"] = "unavailable"

        with self.assertRaisesRegex(ValueError, "original result"):
            MolecularOrientationMeasurement.from_dict(payload)

    def test_manual_correction_json_rejects_unnormalized_original_angle(
        self,
    ) -> None:
        automatic = MolecularOrientationMeasurement(
            measurement_id="automatic-before-angle-corruption",
            status="available",
            angle_deg=10.0,
            periodicity_deg=180.0,
            confidence=0.8,
            method="mask_principal_axis",
            patch_shape_px=(31, 31),
            provenance=_provenance(),
        )
        payload = automatic.with_manual_correction(
            status="available",
            angle_deg=30.0,
            confidence=1.0,
            reviewer="rlewa",
        ).to_dict()
        payload["manual_correction"]["original_result"]["angle_deg"] = 190.0

        with self.assertRaisesRegex(ValueError, "original result angle"):
            MolecularOrientationMeasurement.from_dict(payload)

    def test_patch_shape_must_match_provenance_bbox(self) -> None:
        with self.assertRaisesRegex(ValueError, "patch_shape_px"):
            MolecularOrientationMeasurement(
                measurement_id="invalid-patch-shape",
                status="available",
                angle_deg=10.0,
                periodicity_deg=180.0,
                confidence=0.8,
                method="manual",
                patch_shape_px=(10, 20),
                provenance=_provenance(),
            )

    def test_constructor_rejects_non_integer_schema_version(self) -> None:
        with self.assertRaisesRegex(TypeError, "schema_version"):
            MolecularOrientationMeasurement(
                measurement_id="invalid-schema-version",
                status="available",
                angle_deg=10.0,
                periodicity_deg=180.0,
                confidence=0.8,
                method="manual",
                patch_shape_px=(31, 31),
                provenance=_provenance(),
                schema_version=True,
            )

    def test_reference_json_keeps_molecule_orientation_separate_from_domain_context(
        self,
    ) -> None:
        contexts = (
            MolecularOrientationDomainContext(
                domain_id="domain-trifold",
                lattice_symmetry="trifold",
                lattice_rotation="reference",
                stacking="unknown",
            ),
            MolecularOrientationDomainContext(
                domain_id="domain-rotated",
                lattice_symmetry="sixfold",
                lattice_rotation="rotated",
                stacking="uniform",
            ),
            MolecularOrientationDomainContext(
                domain_id="domain-abab",
                lattice_symmetry="trifold",
                lattice_rotation="rotated",
                stacking="abab",
            ),
        )
        samples = tuple(
            MolecularOrientationReferenceSample(
                sample_id=f"sample-{index}",
                split="development" if index < 2 else "holdout",
                measurement=MolecularOrientationMeasurement(
                    measurement_id=f"measurement-{index}",
                    status="available",
                    angle_deg=15.0 + index * 30.0,
                    periodicity_deg=180.0,
                    confidence=1.0,
                    method="manual",
                    patch_shape_px=(31, 31),
                    provenance=_provenance(
                        frame_index=258 + index,
                        source_id=f"segmentation-{index}",
                    ),
                ),
                domain_context=context,
            )
            for index, context in enumerate(contexts)
        )
        reference = MolecularOrientationReferenceDataset(
            dataset_id="ttmapp-molecular-orientation-v1",
            source_file_name="MOVIE_23raw_TTMAPP_I_AU111.MPP",
            source_file_sha256="a" * 64,
            source_session_file_name="m6_state.moltrack.json",
            source_session_sha256="b" * 64,
            samples=samples,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "reference.json"
            save_molecular_orientation_reference(reference, path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            restored = load_molecular_orientation_reference(path)

        self.assertEqual(restored, reference)
        self.assertEqual(payload["schema_version"], 2)
        self.assertTrue(reference.has_required_ttmapp_contexts)
        self.assertEqual(
            restored.samples[2].measurement.angle_deg,
            75.0,
        )
        self.assertEqual(
            restored.samples[2].domain_context.stacking,
            "abab",
        )
        self.assertNotIn(
            "angle_deg",
            payload["samples"][2]["domain_context"],
        )
        self.assertEqual(len(reference.fingerprint), 64)
        with self.assertRaisesRegex(TypeError, "schema_version"):
            replace(reference, schema_version=1.0)

        legacy = reference.to_dict()
        legacy.update(schema_version=1, reviewed=True, reviewed_by="legacy-user")
        migrated = MolecularOrientationReferenceDataset.from_dict(legacy)
        self.assertEqual(migrated.schema_version, 2)
        self.assertFalse(migrated.has_required_ttmapp_contexts)
        with self.assertRaisesRegex(ValueError, "cannot be saved"):
            migrated.to_dict()

    def test_versioned_ttmapp_reference_covers_required_domain_contexts(
        self,
    ) -> None:
        fixture = (
            Path(__file__).parent
            / "fixtures"
            / "molecular_orientation_reference_ttmapp_v1.json"
        )

        reference = load_molecular_orientation_reference(fixture)

        self.assertEqual(reference.dataset_id, "ttmapp-molecular-orientation-v1")
        self.assertFalse(reference.uses_tracking)
        self.assertTrue(reference.has_required_ttmapp_contexts)
        self.assertEqual(
            reference.source_file_sha256,
            "8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66",
        )
        self.assertEqual(
            {sample.split for sample in reference.samples},
            {"development", "holdout"},
        )
        self.assertEqual(
            {sample.measurement.status for sample in reference.samples},
            {"available", "ambiguous", "unavailable"},
        )
        self.assertTrue(
            all(
                sample.measurement.method == "manual"
                for sample in reference.samples
            )
        )
        self.assertEqual(
            reference.fingerprint,
            "ec7459c4c977c2dbe92f68a3457cb5cbe80daf290e74c4945b48cc7e83c031db",
        )


if __name__ == "__main__":
    unittest.main()
