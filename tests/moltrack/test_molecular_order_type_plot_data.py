import unittest

from moltrack.analysis import build_molecular_order_type_summary
from moltrack.visualization.molecular_order_type_plot_data import (
    build_molecular_order_geometry_scatter_data,
    build_molecular_order_orientation_distribution_data,
    build_molecular_order_stacking_share_data,
)
from test_molecular_order_type_summary import _comparison_classification


class MolecularOrderTypePlotDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.classification = _comparison_classification()
        self.summary = build_molecular_order_type_summary(
            self.classification
        )

    def test_geometry_scatter_keeps_m3_and_m6_channels_separate(self) -> None:
        data = build_molecular_order_geometry_scatter_data(
            self.classification
        )

        self.assertEqual(data.axis_labels, ("Lattice angle [deg]", "Molecules"))
        self.assertEqual(len(data.m3_points), 2)
        self.assertEqual(len(data.m6_points), 2)
        self.assertEqual(
            {point.range_name for point in data.m3_points},
            {"before"},
        )
        self.assertEqual(
            {point.range_name for point in data.m6_points},
            {"after"},
        )
        self.assertTrue(
            all(point.geometry_type_label == "A" for point in data.m3_points)
        )
        self.assertTrue(
            all(point.geometry_type_label == "B" for point in data.m6_points)
        )
        self.assertEqual(data.omitted_m3_count, 2)
        self.assertEqual(data.omitted_m6_count, 2)

    def test_orientation_distribution_excludes_unclassified_observations(
        self,
    ) -> None:
        data = build_molecular_order_orientation_distribution_data(
            self.classification,
            bin_width_deg=10.0,
        )

        self.assertEqual(data.axis_labels, ("Molecular orientation [deg]", "Count"))
        self.assertEqual(
            tuple(series.range_name for series in data.series),
            ("before", "after"),
        )
        self.assertEqual(sum(data.series[0].counts), 4)
        self.assertEqual(sum(data.series[1].counts), 1)
        self.assertEqual(data.excluded_observation_count, 1)
        self.assertEqual(data.distribution_basis, "domain_prototypes")
        self.assertEqual(data.bin_edges_deg[0], 0.0)
        self.assertEqual(data.bin_edges_deg[-1], 180.0)

    def test_stacking_share_values_reuse_reliable_summary_denominators(
        self,
    ) -> None:
        data = build_molecular_order_stacking_share_data(self.summary)

        self.assertEqual(data.type_labels, ("S:A", "S:B"))
        self.assertEqual(
            tuple(series.range_name for series in data.series),
            ("before", "after"),
        )
        self.assertEqual(data.series[0].values_percent, (100.0, 0.0))
        self.assertEqual(data.series[1].values_percent, (0.0, 100.0))
        self.assertEqual(data.reliable_denominators, (2, 1))
        self.assertEqual(data.excluded_counts, (0, 1))


if __name__ == "__main__":
    unittest.main()
