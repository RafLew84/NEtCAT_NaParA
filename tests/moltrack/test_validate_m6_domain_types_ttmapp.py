from pathlib import Path
import tempfile
import unittest

import numpy as np

from moltrack.analysis import M6DomainTypeClassificationSettings
from scripts.validate_m6_domain_types_ttmapp import (
    _normalize_image_to_uint8,
    build_classification_summary,
    build_tolerance_sweep,
    compare_classification_partitions,
    _export_scatter_plot,
)
from test_m6_domain_type_range_comparison import (
    BEFORE,
    _classification,
    _observation,
)


class ValidateM6DomainTypesTtmappTests(unittest.TestCase):
    def test_tolerance_sweep_changes_one_parameter_at_a_time(self) -> None:
        baseline = M6DomainTypeClassificationSettings()

        sweep = build_tolerance_sweep(baseline)

        self.assertEqual(tuple(sweep), (
            "baseline",
            "orientation_narrow",
            "orientation_wide",
            "bond_length_narrow",
            "bond_length_wide",
        ))
        self.assertEqual(sweep["baseline"], baseline)
        self.assertEqual(
            sweep["orientation_narrow"].orientation_tolerance_deg,
            4.5,
        )
        self.assertEqual(
            sweep["orientation_wide"].orientation_tolerance_deg,
            5.5,
        )
        self.assertEqual(
            sweep["bond_length_narrow"].bond_length_tolerance_value,
            9.0,
        )
        self.assertEqual(
            sweep["bond_length_wide"].bond_length_tolerance_value,
            11.0,
        )
        for name, settings in sweep.items():
            if name.startswith("orientation_"):
                self.assertEqual(
                    settings.bond_length_tolerance_value,
                    baseline.bond_length_tolerance_value,
                )
            if name.startswith("bond_length_"):
                self.assertEqual(
                    settings.orientation_tolerance_deg,
                    baseline.orientation_tolerance_deg,
                )

    def test_summary_and_stability_are_label_permutation_independent(self) -> None:
        classification = _classification()

        summary = build_classification_summary(classification)
        stability = compare_classification_partitions(
            classification,
            classification,
        )

        self.assertEqual(summary["observation_count"], 8)
        self.assertEqual(summary["domain_type_count"], 3)
        self.assertEqual(len(summary["representative_domains"]), 3)
        self.assertTrue(all(
            item["normalized_distance_to_prototype"] >= 0.0
            for item in summary["representative_domains"]
        ))
        self.assertEqual(stability["shared_observation_count"], 8)
        self.assertEqual(stability["classification_status_agreement_percent"], 100.0)
        self.assertEqual(stability["classified_pair_partition_agreement_percent"], 100.0)

    def test_partition_agreement_is_undefined_without_an_observation_pair(self) -> None:
        observation = _observation(
            0,
            1,
            10.0,
            2.0,
            frame_range=BEFORE,
            molecule_count=10,
            molecule_fraction=0.1,
            footprint_area_nm2=10.0,
            footprint_fraction=0.1,
            coherent_q6=0.7,
        )
        classification = _classification(
            (observation,),
            settings=M6DomainTypeClassificationSettings(
                minimum_observations_per_type=1,
            ),
        )

        stability = compare_classification_partitions(
            classification,
            classification,
        )

        self.assertIsNone(
            stability["classified_pair_partition_agreement_percent"]
        )

    def test_empty_classification_exports_controlled_scatter(self) -> None:
        classification = _classification(())
        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "scatter.png"

            result = _export_scatter_plot(classification, destination)

            self.assertEqual(result, destination)
            self.assertTrue(destination.is_file())
            self.assertGreater(destination.stat().st_size, 0)

    def test_image_normalization_maps_non_finite_canvas_to_black(self) -> None:
        image = np.asarray([[np.nan, 1.0], [2.0, np.inf]])

        normalized = _normalize_image_to_uint8(image)

        self.assertEqual(normalized.dtype, np.uint8)
        self.assertEqual(normalized[0, 0], 0)
        self.assertEqual(normalized[1, 1], 0)


if __name__ == "__main__":
    unittest.main()
