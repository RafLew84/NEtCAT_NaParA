import unittest
from dataclasses import FrozenInstanceError, replace

from moltrack.analysis import (
    LatticeOrientationDomain,
    M6OrientationDomainSegmentation,
    MolecularM6OrientationAnalysisSettings,
)


def _settings() -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings(
        min_ordered_component_size=2,
        min_seed_size=2,
        min_domain_size=3,
    )


def _full_domain(
    *,
    point_indices: tuple[int, ...] = (0, 1, 2),
    source_ids: tuple[str, ...] = ("a", "b", "c"),
    ordered_component_id: int = 0,
    m6_orientation_domain_id: int | None = 0,
    molecule_count: int = 3,
    centroid_x_nm: float = 1.0,
    centroid_y_nm: float = 2.0,
    orientation_deg: float = 61.0,
) -> LatticeOrientationDomain:
    return LatticeOrientationDomain(
        ordered_component_id=ordered_component_id,
        m6_orientation_domain_id=m6_orientation_domain_id,
        component_type="full_domain",
        point_indices=point_indices,
        source_ids=source_ids,
        molecule_count=molecule_count,
        centroid_x_nm=centroid_x_nm,
        centroid_y_nm=centroid_y_nm,
        orientation_deg=orientation_deg,
    )


def _small_island(
    *,
    point_indices: tuple[int, ...] = (3, 4),
    source_ids: tuple[str, ...] = ("d", "e"),
    ordered_component_id: int = 1,
) -> LatticeOrientationDomain:
    return LatticeOrientationDomain(
        ordered_component_id=ordered_component_id,
        m6_orientation_domain_id=None,
        component_type="small_ordered_island",
        point_indices=point_indices,
        source_ids=source_ids,
        molecule_count=2,
        centroid_x_nm=10.0,
        centroid_y_nm=2.0,
        orientation_deg=5.0,
    )


def _segmentation(**overrides: object) -> M6OrientationDomainSegmentation:
    payload: dict[str, object] = {
        "source_ids": ("a", "b", "c", "d", "e", "boundary", "low-degree", "duplicate", "invalid"),
        "point_count": 9,
        "ordered_component_id": (0, 0, 0, 1, 1, -1, -1, -1, -1),
        "m6_orientation_domain_id": (0, 0, 0, -1, -1, -1, -1, -1, -1),
        "component_type": (
            "full_domain",
            "full_domain",
            "full_domain",
            "small_ordered_island",
            "small_ordered_island",
            "unassigned",
            "unassigned",
            "unassigned",
            "unassigned",
        ),
        "assignment_status": (
            "assigned",
            "assigned",
            "assigned",
            "assigned",
            "assigned",
            "boundary_or_disordered",
            "insufficient_neighbors",
            "duplicate_excluded",
            "invalid_position",
        ),
        "edge_truncated_neighborhood": (False, True, False, False, False, True, False, False, False),
        "physical_duplicate_qc": (False, False, False, False, False, False, False, True, False),
        "geometry_duplicate_qc": (False,) * 9,
        "components": (_full_domain(), _small_island()),
        "settings": _settings(),
        "coordinate_frame": "sample_nm",
        "orientation_reference": "+x_sample_axis",
        "spatial_calibration_fingerprint": "calibration-v1",
        "registration_fingerprint": "registration-v1",
    }
    payload.update(overrides)
    return M6OrientationDomainSegmentation(**payload)


class OrientationDomainModelTests(unittest.TestCase):
    def test_models_full_domain_and_small_island_semantics(self) -> None:
        full = _full_domain()
        island = _small_island()

        self.assertEqual(full.orientation_deg, 1.0)
        self.assertEqual(full.smallest_source_id, "a")
        self.assertEqual(full.stable_sort_key, (-3, 1.0, 2.0, 1.0, "a"))
        self.assertEqual(full.m6_orientation_domain_id, 0)
        self.assertIsNone(island.m6_orientation_domain_id)
        self.assertEqual(island.component_type, "small_ordered_island")

        with self.assertRaises(FrozenInstanceError):
            full.orientation_deg = 2.0

    def test_segmentation_preserves_point_mapping_parameters_and_independent_qc(self) -> None:
        result = _segmentation()

        self.assertEqual(result.source_ids[1], "b")
        self.assertEqual(result.ordered_component_id[1], 0)
        self.assertEqual(result.m6_orientation_domain_id[4], -1)
        self.assertEqual(result.assignment_status[1], "assigned")
        self.assertTrue(result.edge_truncated_neighborhood[1])
        self.assertEqual(result.assignment_status[7], "duplicate_excluded")
        self.assertTrue(result.physical_duplicate_qc[7])
        self.assertEqual(result.full_domain_count, 1)
        self.assertEqual(result.small_ordered_island_count, 1)
        self.assertEqual(result.ordered_component_count, 2)
        self.assertEqual(result.settings, _settings())
        self.assertEqual(result.coordinate_frame, "sample_nm")
        self.assertEqual(result.orientation_reference, "+x_sample_axis")
        self.assertEqual(result.component_for_source_id("b"), result.components[0])
        self.assertIsNone(result.component_for_source_id("boundary"))
        with self.assertRaises(KeyError):
            result.component_for_source_id("missing")

    def test_validates_parallel_array_shapes_and_source_mapping(self) -> None:
        per_point_fields = (
            "ordered_component_id",
            "m6_orientation_domain_id",
            "component_type",
            "assignment_status",
            "edge_truncated_neighborhood",
            "physical_duplicate_qc",
            "geometry_duplicate_qc",
        )
        for field_name in per_point_fields:
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(ValueError, field_name):
                    _segmentation(**{field_name: ()})

        invalid_payloads = (
            {"point_count": 8},
            {"source_ids": ("a",) * 9},
            {"components": (_full_domain(source_ids=("a", "b", "missing")), _small_island())},
            {"components": (_full_domain(point_indices=(0, 1, 3)), _small_island())},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises((TypeError, ValueError)):
                    _segmentation(**payload)

    def test_rejects_inconsistent_assignment_status_labels_and_qc(self) -> None:
        invalid_payloads = (
            {"assignment_status": ("unknown",) + _segmentation().assignment_status[1:]},
            {"ordered_component_id": (-1,) + _segmentation().ordered_component_id[1:]},
            {"m6_orientation_domain_id": (-1,) + _segmentation().m6_orientation_domain_id[1:]},
            {"component_type": ("unassigned",) + _segmentation().component_type[1:]},
            {"m6_orientation_domain_id": (0, 0, 0, 1, -1, -1, -1, -1, -1)},
            {"physical_duplicate_qc": (False,) * 9},
            {
                "geometry_duplicate_qc": (False, False, False, False, False, False, False, True, False),
                "physical_duplicate_qc": (False, False, False, False, False, False, False, True, False),
            },
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises((TypeError, ValueError)):
                    _segmentation(**payload)

    def test_validates_domain_component_type_sizes_and_ids(self) -> None:
        invalid_domain_changes = (
            (_full_domain(), {"m6_orientation_domain_id": None}),
            (_small_island(), {"m6_orientation_domain_id": 1}),
            (_small_island(), {"component_type": "full_domain"}),
            (_full_domain(), {"point_indices": (0, 0, 2)}),
            (_full_domain(), {"orientation_deg": float("nan")}),
        )
        for domain, changes in invalid_domain_changes:
            with self.subTest(changes=changes):
                with self.assertRaises((TypeError, ValueError)):
                    replace(domain, **changes)

    def test_enforces_lexicographic_stable_ids(self) -> None:
        settings = MolecularM6OrientationAnalysisSettings(
            min_ordered_component_size=1,
            min_seed_size=1,
            min_domain_size=1,
        )
        components = (
            _full_domain(
                point_indices=(0,),
                source_ids=("z",),
                molecule_count=1,
                ordered_component_id=0,
                m6_orientation_domain_id=0,
                centroid_x_nm=0.0,
                centroid_y_nm=0.0,
                orientation_deg=0.0,
            ),
            _full_domain(
                point_indices=(1,),
                source_ids=("a",),
                molecule_count=1,
                ordered_component_id=1,
                m6_orientation_domain_id=1,
                centroid_x_nm=0.0,
                centroid_y_nm=0.0,
                orientation_deg=0.0,
            ),
        )
        common = {
            "source_ids": ("z", "a"),
            "point_count": 2,
            "ordered_component_id": (0, 1),
            "m6_orientation_domain_id": (0, 1),
            "component_type": ("full_domain", "full_domain"),
            "assignment_status": ("assigned", "assigned"),
            "edge_truncated_neighborhood": (False, False),
            "physical_duplicate_qc": (False, False),
            "geometry_duplicate_qc": (False, False),
            "components": components,
            "settings": settings,
            "coordinate_frame": "sample_nm",
            "orientation_reference": "+x_sample_axis",
            "spatial_calibration_fingerprint": "calibration-v1",
            "registration_fingerprint": "registration-v1",
        }

        with self.assertRaisesRegex(ValueError, "stable"):
            M6OrientationDomainSegmentation(**common)

    def test_stable_ids_do_not_depend_on_input_point_order(self) -> None:
        original = _segmentation()
        permuted = _segmentation(
            source_ids=("invalid", "duplicate", "low-degree", "boundary", "e", "d", "c", "b", "a"),
            ordered_component_id=(-1, -1, -1, -1, 1, 1, 0, 0, 0),
            m6_orientation_domain_id=(-1, -1, -1, -1, -1, -1, 0, 0, 0),
            component_type=(
                "unassigned",
                "unassigned",
                "unassigned",
                "unassigned",
                "small_ordered_island",
                "small_ordered_island",
                "full_domain",
                "full_domain",
                "full_domain",
            ),
            assignment_status=(
                "invalid_position",
                "duplicate_excluded",
                "insufficient_neighbors",
                "boundary_or_disordered",
                "assigned",
                "assigned",
                "assigned",
                "assigned",
                "assigned",
            ),
            edge_truncated_neighborhood=(False, False, False, True, False, False, False, True, False),
            physical_duplicate_qc=(False, True, False, False, False, False, False, False, False),
            geometry_duplicate_qc=(False,) * 9,
            components=(
                _full_domain(point_indices=(6, 7, 8), source_ids=("c", "b", "a")),
                _small_island(point_indices=(4, 5), source_ids=("e", "d")),
            ),
        )

        self.assertEqual(
            {domain.smallest_source_id: domain.ordered_component_id for domain in original.components},
            {domain.smallest_source_id: domain.ordered_component_id for domain in permuted.components},
        )
        self.assertEqual(
            {domain.smallest_source_id: domain.m6_orientation_domain_id for domain in original.components},
            {domain.smallest_source_id: domain.m6_orientation_domain_id for domain in permuted.components},
        )

    def test_documents_scientific_scope_of_orientation_domains(self) -> None:
        documentation = (LatticeOrientationDomain.__doc__ or "").lower()

        self.assertIn("psi6", documentation)
        self.assertIn("not", documentation)
        self.assertIn("phase", documentation)
        self.assertIn("translational", documentation)
        self.assertIn("row", documentation)


if __name__ == "__main__":
    unittest.main()
