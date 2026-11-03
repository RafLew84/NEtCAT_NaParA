import unittest
from dataclasses import replace

from moltrack.analysis import (
    MolecularOrderLatticeDomain,
    MolecularOrderFrame,
    MolecularOrderOrientationalSubdomain,
    MolecularOrderStacking,
    MolecularStackingAnalysis,
    MolecularStackingSettings,
    OrientationalSubdomain,
    StackingOrder,
    build_lattice_row_assignment_analysis,
    build_molecular_order_hierarchy,
    lattice_row_assignment_analysis_fingerprint,
    molecular_order_hierarchy_fingerprint,
    molecular_stacking_settings_fingerprint,
)
from test_lattice_row_assignment import _triangular_analysis


def _trifold_lattice_analysis():
    analysis = _triangular_analysis(row_count=3, column_count=4)
    domain = replace(
        analysis.domains[0],
        theta3_lattice_prototype_deg=12.0,
        theta6_prototype_deg=None,
        theta3_lattice_spread_deg=1.5,
        theta6_spread_deg=None,
        dominant_symmetry="trifold",
        orientation_reference_channel="m3_lattice",
    )
    return replace(analysis, domains=(domain,))


def _stacking_analysis(
    *,
    frame_index,
    domain,
    row_assignment,
    ordered_source_ids=None,
):
    source_ids = (
        domain.source_ids
        if ordered_source_ids is None
        else tuple(sorted(ordered_source_ids))
    )
    subdomain_id = f"{domain.lattice_domain_id}:orient-0001"
    subdomain = OrientationalSubdomain(
        subdomain_id=subdomain_id,
        frame_index=frame_index,
        parent_lattice_domain_id=domain.lattice_domain_id,
        pattern="ABAB",
        axis_candidate_index=0,
        axis_angle_deg=0.0,
        mode="checkerboard",
        phase="ABAB",
        source_ids=source_ids,
        molecule_count=len(source_ids),
        parent_molecule_count=domain.molecule_count,
        coverage_fraction=len(source_ids) / domain.molecule_count,
        score=0.94,
        confidence=0.91,
        qc_reasons=(),
    )
    incomplete = len(source_ids) != domain.molecule_count
    order = StackingOrder(
        frame_index=frame_index,
        lattice_domain_id=domain.lattice_domain_id,
        pattern="ABAB",
        axis_candidate_index=0,
        axis_angle_deg=0.0,
        mode="checkerboard",
        phase="ABAB",
        prototype_a_angle_deg=20.0,
        prototype_b_angle_deg=80.0,
        periodicity_deg=180.0,
        score=0.94,
        confidence=0.91,
        domain_molecule_count=domain.molecule_count,
        usable_molecule_count=domain.molecule_count,
        ordered_molecule_count=len(source_ids),
        coverage_fraction=1.0,
        ordered_fraction=len(source_ids) / domain.molecule_count,
        subdomain_ids=(subdomain_id,),
        qc_reasons=("incomplete_coverage",) if incomplete else (),
    )
    settings = MolecularStackingSettings()
    return MolecularStackingAnalysis(
        orders=(order,),
        subdomains=(subdomain,),
        input_frame_indices=(frame_index,),
        source_file_sha256=None,
        source_view="expanded_aligned",
        prototype_analysis_fingerprint="a" * 64,
        row_assignment_fingerprints=(
            (
                frame_index,
                lattice_row_assignment_analysis_fingerprint(row_assignment),
            ),
        ),
        settings=settings,
        settings_fingerprint=molecular_stacking_settings_fingerprint(settings),
    )


def _inputs(*, frame_index=7, ordered_source_ids=None):
    lattice = _trifold_lattice_analysis()
    rows = build_lattice_row_assignment_analysis(lattice)
    stacking = _stacking_analysis(
        frame_index=frame_index,
        domain=lattice.domains[0],
        row_assignment=rows,
        ordered_source_ids=ordered_source_ids,
    )
    return lattice, rows, stacking


class MolecularOrderHierarchyTests(unittest.TestCase):
    def test_keeps_trifold_geometry_and_abab_stacking_as_independent_axes(
        self,
    ) -> None:
        lattice, rows, stacking = _inputs()

        result = build_molecular_order_hierarchy(
            {7: lattice},
            {7: rows},
            stacking,
        )

        self.assertFalse(result.uses_tracking)
        self.assertEqual(result.input_frame_indices, (7,))
        frame = result.frames[0]
        domain = frame.lattice_domains[0]
        orientational = domain.orientational_subdomains[0]
        local_stacking = orientational.stacking_order
        self.assertEqual(domain.dominant_symmetry, "trifold")
        self.assertEqual(domain.stacking_pattern, "ABAB")
        self.assertEqual(local_stacking.pattern, "ABAB")
        self.assertEqual(
            domain.stable_key,
            (7, lattice.domains[0].lattice_domain_id),
        )
        self.assertEqual(
            orientational.stable_key,
            (
                7,
                lattice.domains[0].lattice_domain_id,
                stacking.subdomains[0].subdomain_id,
            ),
        )
        self.assertEqual(
            local_stacking.stable_key,
            (*orientational.stable_key, "stacking"),
        )
        self.assertEqual(domain.unresolved_source_ids, ())
        self.assertEqual(frame.unassigned_source_ids, ())

    def test_explicit_unresolved_members_complete_the_domain_partition(
        self,
    ) -> None:
        lattice, rows, _stacking = _inputs()
        ordered = lattice.domains[0].source_ids[:-1]
        stacking = _stacking_analysis(
            frame_index=7,
            domain=lattice.domains[0],
            row_assignment=rows,
            ordered_source_ids=ordered,
        )

        result = build_molecular_order_hierarchy(
            {7: lattice},
            {7: rows},
            stacking,
        )

        domain = result.frames[0].lattice_domains[0]
        self.assertEqual(
            domain.unresolved_source_ids,
            (lattice.domains[0].source_ids[-1],),
        )
        with self.assertRaisesRegex(ValueError, "partition"):
            replace(domain, unresolved_source_ids=())

    def test_ambiguous_order_keeps_all_members_as_unresolved(self) -> None:
        lattice, rows, stacking = _inputs()
        ambiguous_order = replace(
            stacking.orders[0],
            pattern="ambiguous",
            axis_candidate_index=None,
            axis_angle_deg=None,
            mode=None,
            phase=None,
            subdomain_ids=(),
            qc_reasons=("axis_selection_ambiguous",),
        )
        stacking = replace(
            stacking,
            orders=(ambiguous_order,),
            subdomains=(),
        )

        result = build_molecular_order_hierarchy(
            {7: lattice},
            {7: rows},
            stacking,
        )

        domain = result.frames[0].lattice_domains[0]
        self.assertEqual(domain.orientational_subdomains, ())
        self.assertEqual(
            domain.unresolved_source_ids,
            lattice.domains[0].source_ids,
        )

    def test_rejects_overlapping_orientational_siblings(self) -> None:
        lattice, rows, stacking = _inputs()
        hierarchy = build_molecular_order_hierarchy(
            {7: lattice},
            {7: rows},
            stacking,
        )
        domain = hierarchy.frames[0].lattice_domains[0]
        first = domain.orientational_subdomains[0]
        second_id = f"{domain.lattice_domain.lattice_domain_id}:orient-0002"
        second_evidence = replace(
            first.stacking_order.subdomain,
            subdomain_id=second_id,
        )
        parent_order = replace(
            domain.stacking_order,
            pattern="mixed",
            phase=None,
            subdomain_ids=tuple(
                sorted(
                    (
                        first.orientational_subdomain_id,
                        second_id,
                    )
                )
            ),
            qc_reasons=("phase_boundary",),
        )
        second_stacking = MolecularOrderStacking(
            frame_index=7,
            parent_lattice_domain_id=domain.lattice_domain.lattice_domain_id,
            parent_orientational_subdomain_id=second_id,
            subdomain=second_evidence,
        )
        second = MolecularOrderOrientationalSubdomain(
            frame_index=7,
            parent_lattice_domain_id=domain.lattice_domain.lattice_domain_id,
            orientational_subdomain_id=second_id,
            source_ids=second_evidence.source_ids,
            stacking_order=second_stacking,
        )

        with self.assertRaisesRegex(ValueError, "overlap"):
            MolecularOrderLatticeDomain(
                frame_index=7,
                lattice_domain=domain.lattice_domain,
                stacking_order=parent_order,
                orientational_subdomains=tuple(
                    sorted(
                        (first, second),
                        key=lambda value: value.stable_key,
                    )
                ),
                unresolved_source_ids=(),
            )

    def test_frame_partition_preserves_explicit_unassigned_members(
        self,
    ) -> None:
        lattice, rows, stacking = _inputs()
        hierarchy = build_molecular_order_hierarchy(
            {7: lattice},
            {7: rows},
            stacking,
        )
        frame = hierarchy.frames[0]
        with_unassigned = MolecularOrderFrame(
            frame_index=frame.frame_index,
            source_ids=frame.source_ids + ("unassigned-molecule",),
            lattice_domains=frame.lattice_domains,
            unassigned_source_ids=("unassigned-molecule",),
            lattice_domain_analysis_fingerprint=(
                frame.lattice_domain_analysis_fingerprint
            ),
            row_assignment_fingerprint=(
                frame.row_assignment_fingerprint
            ),
        )

        self.assertEqual(
            with_unassigned.unassigned_source_ids,
            ("unassigned-molecule",),
        )
        with self.assertRaisesRegex(ValueError, "partition"):
            replace(with_unassigned, unassigned_source_ids=())

    def test_rejects_row_assignment_from_another_lattice_analysis(self) -> None:
        lattice, rows, stacking = _inputs()
        mismatched_rows = replace(
            rows,
            lattice_domain_analysis_fingerprint="wrong-lattice-result",
        )
        stacking = replace(
            stacking,
            row_assignment_fingerprints=(
                (
                    7,
                    lattice_row_assignment_analysis_fingerprint(
                        mismatched_rows
                    ),
                ),
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "lattice-domain provenance",
        ):
            build_molecular_order_hierarchy(
                {7: lattice},
                {7: mismatched_rows},
                stacking,
            )

    def test_rejects_stacking_from_another_row_assignment(self) -> None:
        lattice, rows, stacking = _inputs()
        stacking = replace(
            stacking,
            row_assignment_fingerprints=((7, "b" * 64),),
        )

        with self.assertRaisesRegex(
            ValueError,
            "row-assignment provenance",
        ):
            build_molecular_order_hierarchy(
                {7: lattice},
                {7: rows},
                stacking,
            )

    def test_result_and_fingerprint_are_deterministic(self) -> None:
        lattice, rows, stacking = _inputs()

        first = build_molecular_order_hierarchy(
            {7: lattice},
            {7: rows},
            stacking,
        )
        second = build_molecular_order_hierarchy(
            {7: lattice},
            {7: rows},
            stacking,
        )

        self.assertEqual(first, second)
        self.assertEqual(
            molecular_order_hierarchy_fingerprint(first),
            molecular_order_hierarchy_fingerprint(second),
        )


if __name__ == "__main__":
    unittest.main()
