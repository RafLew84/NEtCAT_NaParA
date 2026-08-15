import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

from moltrack.analysis import (
    MolecularOrientationMeasurement,
    assess_molecular_orientation_method_merge,
    estimate_molecular_orientation_from_topography,
    evaluate_molecular_orientation_method_against_reference,
    load_molecular_orientation_reference,
)


_REFERENCE_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "molecular_orientation_reference_ttmapp_v1.json"
)
_TOPOGRAPHY_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "molecular_orientation_topography_ttmapp_v1.npz"
)


def _automatic_measurements(reference, *, method: str, offset_deg: float):
    measurements = []
    for sample in reference.samples:
        manual = sample.measurement
        if manual.status == "available":
            status = "available"
            angle_deg = manual.angle_deg + offset_deg
            confidence = 0.8
        else:
            status = "unavailable"
            angle_deg = None
            confidence = None
        measurements.append(
            MolecularOrientationMeasurement(
                measurement_id=f"{method}-{sample.sample_id}",
                status=status,
                angle_deg=angle_deg,
                periodicity_deg=manual.periodicity_deg,
                confidence=confidence,
                method=method,
                patch_shape_px=manual.patch_shape_px,
                provenance=manual.provenance,
            )
        )
    return tuple(measurements)


def _replace_measurement(measurements, source_id: str, **changes):
    return tuple(
        replace(measurement, **changes)
        if measurement.provenance.source_id == source_id
        else measurement
        for measurement in measurements
    )


class MolecularOrientationMethodValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reference = load_molecular_orientation_reference(_REFERENCE_FIXTURE)

    def test_legacy_v1_reference_cannot_authorize_method_validation(self) -> None:
        payload = self.reference.to_dict()
        payload.update(schema_version=1, reviewed=True, reviewed_by="legacy-user")
        legacy = type(self.reference).from_dict(payload)
        estimates = _automatic_measurements(
            self.reference, method="mask_principal_axis", offset_deg=0.0
        )

        with self.assertRaisesRegex(ValueError, "audit-only"):
            evaluate_molecular_orientation_method_against_reference(
                legacy, estimates, method="mask_principal_axis"
            )

    def test_accurate_method_agrees_with_holdout_ground_truth(self) -> None:
        estimates = _automatic_measurements(
            self.reference,
            method="stm_topography",
            offset_deg=2.0,
        )

        report = evaluate_molecular_orientation_method_against_reference(
            self.reference,
            estimates,
            method="stm_topography",
            split="holdout",
            tolerance_deg=10.0,
            min_comparable_count=2,
        )

        self.assertEqual(report.reference_dataset_id, self.reference.dataset_id)
        self.assertEqual(report.reference_fingerprint, self.reference.fingerprint)
        self.assertEqual(report.method, "stm_topography")
        self.assertEqual(report.split, "holdout")
        self.assertEqual(report.comparable_count, 2)
        self.assertEqual(report.agreement_status, "agrees")
        self.assertTrue(report.automatic_merge_eligible)
        self.assertAlmostEqual(report.median_error_deg, 2.0)
        self.assertEqual(len(report.source_ids), len(report.errors_deg))

    def test_systematic_error_blocks_method_from_automatic_merge(self) -> None:
        estimates = _automatic_measurements(
            self.reference,
            method="stm_topography",
            offset_deg=40.0,
        )

        report = evaluate_molecular_orientation_method_against_reference(
            self.reference,
            estimates,
            method="stm_topography",
            split="holdout",
            tolerance_deg=10.0,
            min_comparable_count=2,
        )

        self.assertEqual(report.agreement_status, "systematic_disagreement")
        self.assertFalse(report.automatic_merge_eligible)
        self.assertAlmostEqual(report.median_error_deg, 40.0)

    def test_pairwise_method_disagreement_blocks_automatic_merge(self) -> None:
        mask_estimates = _automatic_measurements(
            self.reference,
            method="mask_principal_axis",
            offset_deg=0.0,
        )
        topography_estimates = _automatic_measurements(
            self.reference,
            method="stm_topography",
            offset_deg=40.0,
        )

        assessment = assess_molecular_orientation_method_merge(
            self.reference,
            mask_estimates,
            topography_estimates,
            split="holdout",
            tolerance_deg=10.0,
            min_comparable_count=2,
        )

        self.assertEqual(assessment.first.method, "mask_principal_axis")
        self.assertEqual(assessment.second.method, "stm_topography")
        self.assertEqual(assessment.paired_count, 2)
        self.assertAlmostEqual(assessment.pairwise_median_error_deg, 40.0)
        self.assertEqual(
            assessment.merge_status,
            "systematic_method_disagreement",
        )
        self.assertFalse(assessment.automatic_merge_allowed)

    def test_methods_can_merge_only_when_both_match_reference_and_each_other(
        self,
    ) -> None:
        mask_estimates = _automatic_measurements(
            self.reference,
            method="mask_principal_axis",
            offset_deg=2.0,
        )
        topography_estimates = _automatic_measurements(
            self.reference,
            method="stm_topography",
            offset_deg=4.0,
        )

        assessment = assess_molecular_orientation_method_merge(
            self.reference,
            mask_estimates,
            topography_estimates,
            split="holdout",
            tolerance_deg=10.0,
            min_comparable_count=2,
        )

        self.assertEqual(assessment.merge_status, "agrees")
        self.assertTrue(assessment.automatic_merge_allowed)
        self.assertAlmostEqual(assessment.pairwise_median_error_deg, 2.0)

    def test_too_few_comparable_labels_never_allows_merge(self) -> None:
        estimates = _automatic_measurements(
            self.reference,
            method="stm_topography",
            offset_deg=0.0,
        )

        report = evaluate_molecular_orientation_method_against_reference(
            self.reference,
            estimates,
            method="stm_topography",
            split="holdout",
            tolerance_deg=10.0,
            min_comparable_count=3,
        )

        self.assertEqual(report.agreement_status, "insufficient_data")
        self.assertFalse(report.automatic_merge_eligible)

    def test_sparse_correct_predictions_do_not_authorize_merge(self) -> None:
        estimates = _automatic_measurements(
            self.reference,
            method="stm_topography",
            offset_deg=0.0,
        )
        one_available_id = next(
            measurement.provenance.source_id
            for measurement in estimates
            if measurement.status == "available"
            and measurement.provenance.frame_index == 258
        )
        sparse = tuple(
            measurement
            for measurement in estimates
            if measurement.status != "available"
            or measurement.provenance.source_id == one_available_id
        )

        report = evaluate_molecular_orientation_method_against_reference(
            self.reference,
            sparse,
            method="stm_topography",
            split="holdout",
            tolerance_deg=10.0,
            min_comparable_count=1,
        )

        self.assertEqual(report.comparable_count, 1)
        self.assertAlmostEqual(report.reference_coverage_fraction, 0.5)
        self.assertEqual(report.agreement_status, "insufficient_data")
        self.assertFalse(report.automatic_merge_eligible)

    def test_coordinate_reference_and_patch_must_match_ground_truth(self) -> None:
        estimates = _automatic_measurements(
            self.reference,
            method="stm_topography",
            offset_deg=0.0,
        )
        target = next(
            measurement
            for measurement in estimates
            if measurement.status == "available"
            and measurement.provenance.frame_index == 258
        )
        incompatible_reference = _replace_measurement(
            estimates,
            target.provenance.source_id,
            provenance=replace(
                target.provenance,
                orientation_reference="sample_x_axis_counterclockwise",
            ),
        )
        incompatible_patch = _replace_measurement(
            estimates,
            target.provenance.source_id,
            provenance=replace(
                target.provenance,
                patch_bbox_xyxy=(0.0, 0.0, 31.0, 31.0),
            ),
        )

        with self.assertRaisesRegex(ValueError, "orientation_reference"):
            evaluate_molecular_orientation_method_against_reference(
                self.reference,
                incompatible_reference,
                method="stm_topography",
            )
        with self.assertRaisesRegex(ValueError, "patch_bbox_xyxy"):
            evaluate_molecular_orientation_method_against_reference(
                self.reference,
                incompatible_patch,
                method="stm_topography",
            )

    def test_one_outlier_blocks_automatic_merge_eligibility(self) -> None:
        estimates = _automatic_measurements(
            self.reference,
            method="stm_topography",
            offset_deg=0.0,
        )
        outlier = next(
            measurement
            for measurement in estimates
            if measurement.status == "available"
            and measurement.provenance.frame_index == 259
        )
        estimates = _replace_measurement(
            estimates,
            outlier.provenance.source_id,
            angle_deg=outlier.angle_deg + 20.0,
        )

        report = evaluate_molecular_orientation_method_against_reference(
            self.reference,
            estimates,
            method="stm_topography",
            tolerance_deg=10.0,
            min_comparable_count=2,
        )

        self.assertAlmostEqual(report.median_error_deg, 10.0)
        self.assertAlmostEqual(report.max_error_deg, 20.0)
        self.assertAlmostEqual(report.within_tolerance_fraction, 0.5)
        self.assertEqual(report.agreement_status, "systematic_disagreement")
        self.assertFalse(report.automatic_merge_eligible)

    def test_available_estimate_on_unresolved_reference_blocks_merge(self) -> None:
        estimates = _automatic_measurements(
            self.reference,
            method="stm_topography",
            offset_deg=0.0,
        )
        unresolved = next(
            measurement
            for measurement in estimates
            if measurement.provenance.frame_index == 259
            and measurement.status == "unavailable"
        )
        estimates = _replace_measurement(
            estimates,
            unresolved.provenance.source_id,
            status="available",
            angle_deg=0.0,
            confidence=0.8,
        )

        report = evaluate_molecular_orientation_method_against_reference(
            self.reference,
            estimates,
            method="stm_topography",
            tolerance_deg=10.0,
            min_comparable_count=2,
        )

        self.assertEqual(report.reference_unresolved_count, 1)
        self.assertEqual(report.estimate_available_on_unresolved_count, 1)
        self.assertEqual(report.agreement_status, "systematic_disagreement")
        self.assertFalse(report.automatic_merge_eligible)

    def test_manual_method_cannot_be_an_automatic_merge_candidate(self) -> None:
        manual = tuple(sample.measurement for sample in self.reference.samples)

        with self.assertRaisesRegex(ValueError, "automatic"):
            evaluate_molecular_orientation_method_against_reference(
                self.reference,
                manual,
                method="manual",
            )

    def test_pairwise_outlier_blocks_merge_even_when_medians_pass(self) -> None:
        first = _automatic_measurements(
            self.reference,
            method="mask_principal_axis",
            offset_deg=0.0,
        )
        second = _automatic_measurements(
            self.reference,
            method="stm_topography",
            offset_deg=0.0,
        )
        first_target = next(
            value
            for value in first
            if value.status == "available"
            and value.provenance.frame_index == 259
        )
        second_target = next(
            value
            for value in second
            if value.status == "available"
            and value.provenance.frame_index == 259
        )
        first = _replace_measurement(
            first,
            first_target.provenance.source_id,
            angle_deg=first_target.angle_deg - 10.0,
        )
        second = _replace_measurement(
            second,
            second_target.provenance.source_id,
            angle_deg=second_target.angle_deg + 10.0,
        )

        assessment = assess_molecular_orientation_method_merge(
            self.reference,
            first,
            second,
            tolerance_deg=10.0,
            min_comparable_count=2,
        )

        self.assertAlmostEqual(assessment.pairwise_median_error_deg, 10.0)
        self.assertAlmostEqual(assessment.pairwise_max_error_deg, 20.0)
        self.assertEqual(
            assessment.merge_status,
            "systematic_method_disagreement",
        )
        self.assertFalse(assessment.automatic_merge_allowed)

    def test_real_ttmapp_patches_are_evaluated_and_not_approved_yet(self) -> None:
        with np.load(_TOPOGRAPHY_FIXTURE, allow_pickle=False) as fixture:
            self.assertEqual(int(fixture["fixture_schema_version"]), 1)
            self.assertEqual(
                str(fixture["reference_fingerprint"]),
                self.reference.fingerprint,
            )
            self.assertEqual(
                str(fixture["source_file_sha256"]),
                self.reference.source_file_sha256,
            )
            self.assertEqual(
                str(fixture["source_session_sha256"]),
                self.reference.source_session_sha256,
            )
            self.assertEqual(
                tuple(str(value) for value in fixture["sample_ids"]),
                tuple(sample.sample_id for sample in self.reference.samples),
            )
            measurements = tuple(
                estimate_molecular_orientation_from_topography(
                    fixture["topography"][index],
                    fixture["masks"][index],
                    measurement_id=f"stm-topography-{sample.sample_id}",
                    provenance=sample.measurement.provenance,
                    pixel_size_nm_xy=tuple(
                        float(value)
                        for value in fixture["pixel_size_nm_xy"]
                    ),
                    scan_angle_deg=None,
                    valid_fov_mask=fixture["valid_fov_masks"][index],
                ).measurement
                for index, sample in enumerate(self.reference.samples)
            )

        report = evaluate_molecular_orientation_method_against_reference(
            self.reference,
            measurements,
            method="stm_topography",
            split="holdout",
            tolerance_deg=10.0,
            min_comparable_count=2,
        )

        self.assertEqual(report.reference_available_count, 2)
        self.assertEqual(report.reference_unresolved_count, 1)
        self.assertGreaterEqual(report.comparable_count, 1)
        self.assertLess(report.reference_coverage_fraction, 1.0)
        self.assertNotEqual(report.agreement_status, "agrees")
        self.assertFalse(report.automatic_merge_eligible)

        development_report = (
            evaluate_molecular_orientation_method_against_reference(
                self.reference,
                measurements,
                method="stm_topography",
                split="development",
                tolerance_deg=10.0,
                min_comparable_count=2,
            )
        )
        self.assertEqual(development_report.comparable_count, 2)
        self.assertGreater(development_report.max_error_deg, 10.0)
        self.assertEqual(
            development_report.agreement_status,
            "systematic_disagreement",
        )
        self.assertFalse(development_report.automatic_merge_eligible)

    def test_repeated_source_id_on_different_frames_is_reportable(self) -> None:
        shared_source_id = "same-id-on-distinct-frames"
        holdout_available_ids = {
            sample.sample_id
            for sample in self.reference.samples
            if sample.split == "holdout"
            and sample.measurement.status == "available"
        }
        samples = tuple(
            replace(
                sample,
                measurement=replace(
                    sample.measurement,
                    provenance=replace(
                        sample.measurement.provenance,
                        source_id=shared_source_id,
                    ),
                ),
            )
            if sample.sample_id in holdout_available_ids
            else sample
            for sample in self.reference.samples
        )
        reference = replace(self.reference, samples=samples)
        estimates = _automatic_measurements(
            reference,
            method="stm_topography",
            offset_deg=0.0,
        )

        report = evaluate_molecular_orientation_method_against_reference(
            reference,
            estimates,
            method="stm_topography",
            split="holdout",
            tolerance_deg=10.0,
            min_comparable_count=2,
        )

        self.assertEqual(
            report.source_ids,
            (shared_source_id, shared_source_id),
        )
        self.assertEqual(len(set(report.source_keys)), 2)
        self.assertEqual(report.agreement_status, "agrees")


if __name__ == "__main__":
    unittest.main()
