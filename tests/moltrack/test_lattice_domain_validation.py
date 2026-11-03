import unittest

from moltrack.analysis import (
    LatticeDomainPartitionLabels,
    evaluate_lattice_domain_partition,
)


def _labels(
    domain_labels,
    *,
    boundary=(False, False, False, False, False, False),
    confidence=(0.9, 0.9, 0.8, 0.8, 0.8, 0.8),
):
    return LatticeDomainPartitionLabels(
        source_ids=("a", "b", "c", "d", "e", "f"),
        domain_labels=tuple(domain_labels),
        boundary=tuple(boundary),
        confidence=tuple(confidence),
    )


class LatticeDomainValidationTests(unittest.TestCase):
    def test_permuted_domain_names_are_a_perfect_partition(self) -> None:
        reference = _labels(
            ("manual-a", "manual-a", "manual-b", "manual-b", "manual-b", None),
            boundary=(False, False, False, False, False, True),
            confidence=(None,) * 6,
        )
        predicted = _labels(
            ("lattice-9", "lattice-9", "lattice-2", "lattice-2", "lattice-2", None),
            boundary=(False, False, False, False, False, True),
        )

        report = evaluate_lattice_domain_partition(
            predicted,
            reference,
            stability_reference=predicted,
        )

        self.assertAlmostEqual(report.adjusted_rand_index, 1.0)
        self.assertAlmostEqual(report.variation_of_information_nats, 0.0)
        self.assertAlmostEqual(report.boundary_precision, 1.0)
        self.assertAlmostEqual(report.boundary_recall, 1.0)
        self.assertEqual(report.domain_count_error, 0)
        self.assertEqual(report.over_segmentation_count, 0)
        self.assertEqual(report.under_segmentation_count, 0)
        self.assertAlmostEqual(report.correctly_assigned_molecule_fraction, 1.0)
        self.assertIsNotNone(report.confidence_brier_score)
        self.assertAlmostEqual(report.partition_stability_ari, 1.0)

    def test_split_domain_and_boundary_errors_are_reported(self) -> None:
        reference = _labels(
            ("a", "a", "b", "b", "b", None),
            boundary=(False, False, False, False, False, True),
            confidence=(None,) * 6,
        )
        predicted = _labels(
            ("x", "y", "z", "z", "z", None),
            boundary=(False, True, False, False, False, False),
        )

        report = evaluate_lattice_domain_partition(predicted, reference)

        self.assertLess(report.adjusted_rand_index, 1.0)
        self.assertGreater(report.variation_of_information_nats, 0.0)
        self.assertEqual(report.predicted_domain_count, 3)
        self.assertEqual(report.reference_domain_count, 2)
        self.assertEqual(report.domain_count_error, 1)
        self.assertEqual(report.over_segmentation_count, 1)
        self.assertEqual(report.under_segmentation_count, 0)
        self.assertEqual(report.boundary_true_positive_count, 0)
        self.assertEqual(report.boundary_false_positive_count, 1)
        self.assertEqual(report.boundary_false_negative_count, 1)
        self.assertAlmostEqual(report.boundary_precision, 0.0)
        self.assertAlmostEqual(report.boundary_recall, 0.0)
        self.assertLess(report.correctly_assigned_molecule_fraction, 1.0)
        self.assertIsNone(report.partition_stability_ari)

    def test_missing_and_extra_molecules_are_not_dropped_from_validation(self) -> None:
        reference = LatticeDomainPartitionLabels(
            source_ids=("a", "b", "c"),
            domain_labels=("manual", "manual", None),
            boundary=(False, False, True),
            confidence=(None, None, None),
        )
        predicted = LatticeDomainPartitionLabels(
            source_ids=("a", "b", "extra"),
            domain_labels=("predicted", "predicted", "false-positive"),
            boundary=(False, False, False),
            confidence=(0.9, 0.9, 0.95),
        )

        report = evaluate_lattice_domain_partition(predicted, reference)

        self.assertEqual(report.evaluated_molecule_count, 4)
        self.assertEqual(report.missing_prediction_molecule_count, 1)
        self.assertEqual(report.unexpected_prediction_molecule_count, 1)
        self.assertEqual(report.boundary_false_negative_count, 1)
        self.assertLess(report.correctly_assigned_molecule_fraction, 1.0)
        self.assertGreater(report.confidence_brier_score, 0.0)
        self.assertGreaterEqual(report.over_segmentation_count, 1)

    def test_simultaneous_split_and_merge_are_reported_when_counts_cancel(self) -> None:
        reference = _labels(("a", "a", "b", "b", "c", "c"), confidence=(None,) * 6)
        predicted = _labels(("x", "y", "z", "z", "x", "x"))

        report = evaluate_lattice_domain_partition(predicted, reference)

        self.assertEqual(report.predicted_domain_count, report.reference_domain_count)
        self.assertEqual(report.domain_count_error, 0)
        self.assertEqual(report.over_segmentation_count, 1)
        self.assertEqual(report.under_segmentation_count, 1)

    def test_false_domain_on_reference_unassigned_point_hurts_confidence(self) -> None:
        reference = _labels(
            ("a", "a", "b", "b", "b", None),
            confidence=(None,) * 6,
        )
        predicted = _labels(
            ("x", "x", "y", "y", "y", "false-positive"),
            confidence=(1.0, 1.0, 1.0, 1.0, 1.0, 0.99),
        )

        report = evaluate_lattice_domain_partition(predicted, reference)

        self.assertAlmostEqual(report.correctly_assigned_molecule_fraction, 5 / 6)
        self.assertGreater(report.confidence_brier_score, 0.15)


if __name__ == "__main__":
    unittest.main()
