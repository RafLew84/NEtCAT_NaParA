import json
import unittest
from dataclasses import replace

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularFrameRangeAnalysisScope,
    MolecularOrderTypeClassificationSettings,
    MolecularOrderTypeSessionState,
    analyze_molecular_stacking,
    classify_molecular_order_types,
)
from moltrack.persistence import build_molecular_order_type_export_data
from test_molecular_order_type_classifier import _domain_frame, _hierarchy
from test_molecular_stacking_analysis import _prototype_analysis


def _centroid_alias_frame(frame_index: int):
    frame = _domain_frame(frame_index)
    domain = frame.lattice_domains[0]
    lattice = replace(
        domain.lattice_domain,
        theta3_lattice_prototype_deg=None,
        theta6_prototype_deg=None,
        theta3_lattice_spread_deg=None,
        theta6_spread_deg=None,
        dominant_symmetry="ambiguous",
        orientation_reference_channel="unavailable",
        m3_m6_orientation_relation_status=(
            "symmetry_alias_unresolvable_from_centroids"
        ),
        m3_m6_orientation_offset_deg=None,
        qc=replace(
            domain.lattice_domain.qc,
            symmetry_alias_unresolvable_from_centroids=True,
        ),
    )
    return replace(
        frame,
        lattice_domains=(
            replace(domain, lattice_domain=lattice),
        ),
    )


def _relocated_domain(domain, *, frame_index: int, domain_id: str, prefix: str):
    source_id_map = {
        source_id: f"{prefix}{source_id}"
        for source_id in domain.lattice_domain.source_ids
    }

    def renamed(source_ids):
        return tuple(source_id_map[value] for value in source_ids)

    geometry = replace(
        domain.lattice_domain.geometry,
        internal_first_shell_bonds=tuple(
            replace(bond, source_ids=renamed(bond.source_ids))
            for bond in domain.lattice_domain.geometry.internal_first_shell_bonds
        ),
    )
    lattice = replace(
        domain.lattice_domain,
        lattice_domain_id=domain_id,
        source_component_id=1,
        source_ids=renamed(domain.lattice_domain.source_ids),
        core_source_ids=renamed(domain.lattice_domain.core_source_ids),
        halo_source_ids=renamed(domain.lattice_domain.halo_source_ids),
        adjacent_boundary_source_ids=renamed(
            domain.lattice_domain.adjacent_boundary_source_ids
        ),
        molecule_fraction_of_valid_representatives=0.5,
        geometry=geometry,
    )
    orientational_subdomains = []
    subdomain_ids = []
    for index, value in enumerate(domain.orientational_subdomains, start=1):
        subdomain_id = f"{domain_id}:orient-{index:04d}"
        source_subdomain = replace(
            value.stacking_order.subdomain,
            subdomain_id=subdomain_id,
            frame_index=frame_index,
            parent_lattice_domain_id=domain_id,
            source_ids=renamed(value.source_ids),
        )
        local_stacking = replace(
            value.stacking_order,
            frame_index=frame_index,
            parent_lattice_domain_id=domain_id,
            parent_orientational_subdomain_id=subdomain_id,
            subdomain=source_subdomain,
        )
        orientational_subdomains.append(
            replace(
                value,
                frame_index=frame_index,
                parent_lattice_domain_id=domain_id,
                orientational_subdomain_id=subdomain_id,
                source_ids=source_subdomain.source_ids,
                stacking_order=local_stacking,
            )
        )
        subdomain_ids.append(subdomain_id)
    stacking_order = replace(
        domain.stacking_order,
        frame_index=frame_index,
        lattice_domain_id=domain_id,
        subdomain_ids=tuple(subdomain_ids),
    )
    return replace(
        domain,
        frame_index=frame_index,
        lattice_domain=lattice,
        stacking_order=stacking_order,
        orientational_subdomains=tuple(orientational_subdomains),
        unresolved_source_ids=renamed(domain.unresolved_source_ids),
    )


def _two_rotated_domains_frame():
    first_frame = _domain_frame(0, theta3_deg=3.0)
    first_domain = first_frame.lattice_domains[0]
    first_domain = replace(
        first_domain,
        lattice_domain=replace(
            first_domain.lattice_domain,
            molecule_fraction_of_valid_representatives=0.5,
        ),
    )
    second_domain = _relocated_domain(
        _domain_frame(1, theta3_deg=33.0).lattice_domains[0],
        frame_index=0,
        domain_id="lattice-rotated-b",
        prefix="rotated-b-",
    )
    domains = tuple(
        sorted(
            (first_domain, second_domain),
            key=lambda value: value.stable_key,
        )
    )
    return replace(
        first_frame,
        source_ids=tuple(
            sorted(
                source_id
                for domain in domains
                for source_id in domain.lattice_domain.source_ids
            )
        ),
        lattice_domains=domains,
    )


class MolecularOrderTypeEndToEndTests(unittest.TestCase):
    def test_two_rotated_domains_in_one_frame_survive_save_and_export(
        self,
    ) -> None:
        hierarchy = _hierarchy(_two_rotated_domains_frame())
        classification = classify_molecular_order_types(
            hierarchy,
            analysis_scope=MolecularFrameRangeAnalysisScope(
                analysis_mode="single_range",
                frame_count=1,
                source_view="expanded_aligned",
                ranges=(MolecularFrameRange("two domains", 0, 0),),
            ),
            settings=MolecularOrderTypeClassificationSettings(
                lattice_orientation_tolerance_deg=5.0,
            ),
        )
        restored = MolecularOrderTypeSessionState.from_dict(
            json.loads(
                json.dumps(
                    MolecularOrderTypeSessionState.from_classification(
                        classification
                    ).to_dict()
                )
            )
        ).restore_classification_for(hierarchy)
        export = build_molecular_order_type_export_data(
            hierarchy,
            classification,
            frame_indices=(0,),
            tables_included=True,
        )

        self.assertEqual(len(classification.observations), 2)
        self.assertEqual(len(classification.geometry_types), 2)
        self.assertEqual(restored, classification)
        self.assertEqual(len(export.assignment_rows), 2)
        self.assertEqual(
            {
                row["representative_source_ids_json"]
                for row in export.assignment_rows
            },
            {
                json.dumps(
                    domain.lattice_domain.source_ids,
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
                for domain in hierarchy.frames[0].lattice_domains
            },
        )

    def test_classification_and_export_do_not_clip_long_frame_ranges(
        self,
    ) -> None:
        frame_count = 64
        hierarchy = _hierarchy(
            *(_domain_frame(frame_index) for frame_index in range(frame_count))
        )
        classification = classify_molecular_order_types(
            hierarchy,
            analysis_scope=MolecularFrameRangeAnalysisScope(
                analysis_mode="single_range",
                frame_count=frame_count,
                source_view="expanded_aligned",
                ranges=(
                    MolecularFrameRange(
                        "all synthetic frames",
                        0,
                        frame_count - 1,
                    ),
                ),
            ),
            settings=MolecularOrderTypeClassificationSettings(),
        )
        export = build_molecular_order_type_export_data(
            hierarchy,
            classification,
            frame_indices=hierarchy.input_frame_indices,
            tables_included=True,
        )

        self.assertEqual(len(classification.observations), frame_count)
        self.assertEqual(len(classification.assignments), frame_count)
        self.assertEqual(len(export.hierarchy_rows), frame_count)
        self.assertEqual(len(export.assignment_rows), frame_count)

    def test_synthetic_scientific_cases_remain_auditable_end_to_end(
        self,
    ) -> None:
        hierarchy = _hierarchy(
            _domain_frame(0, theta3_deg=3.0),
            _domain_frame(1, theta3_deg=33.0),
            _domain_frame(
                2,
                symmetry="sixfold",
                theta3_deg=None,
                theta6_deg=28.0,
            ),
            _domain_frame(
                3,
                symmetry="mixed",
                theta3_deg=12.0,
                theta6_deg=12.0,
            ),
            _centroid_alias_frame(4),
            _domain_frame(
                5,
                stacking_pattern="mixed",
                stacking_mode="checkerboard",
                stacking_phase="ABAB",
            ),
        )
        scope = MolecularFrameRangeAnalysisScope(
            analysis_mode="single_range",
            frame_count=6,
            source_view="expanded_aligned",
            ranges=(MolecularFrameRange("synthetic", 0, 5),),
        )
        classification = classify_molecular_order_types(
            hierarchy,
            analysis_scope=scope,
            settings=MolecularOrderTypeClassificationSettings(
                lattice_orientation_tolerance_deg=5.0,
            ),
        )

        by_frame = {
            value.observation_key[3]: value
            for value in classification.assignments
        }
        self.assertEqual(len(classification.geometry_types), 5)
        self.assertNotEqual(
            by_frame[0].geometry.type_id,
            by_frame[1].geometry.type_id,
        )
        self.assertEqual(by_frame[4].geometry.status, "unclassified")
        self.assertEqual(
            by_frame[4].geometry.unclassified_reason,
            "geometry_ambiguous",
        )
        self.assertEqual(by_frame[0].stacking.status, "classified")
        self.assertEqual(by_frame[5].stacking.status, "classified")
        self.assertNotEqual(
            by_frame[0].stacking.type_id,
            by_frame[5].stacking.type_id,
        )

        state = MolecularOrderTypeSessionState.from_classification(
            classification
        )
        restored = MolecularOrderTypeSessionState.from_dict(
            json.loads(json.dumps(state.to_dict()))
        ).restore_classification_for(hierarchy)
        self.assertEqual(restored, classification)

        export = build_molecular_order_type_export_data(
            hierarchy,
            classification,
            frame_indices=hierarchy.input_frame_indices,
            tables_included=True,
        )
        alias_row = next(
            value
            for value in export.assignment_rows
            if value["working_frame_index"] == 4
        )
        self.assertEqual(alias_row["geometry_status"], "unclassified")
        self.assertEqual(
            alias_row["geometry_unclassified_reason"],
            "geometry_ambiguous",
        )
        self.assertTrue(alias_row["representative_source_ids_json"])
        boundary_row = next(
            value
            for value in export.assignment_rows
            if value["working_frame_index"] == 5
        )
        self.assertEqual(boundary_row["stacking_pattern"], "mixed")
        self.assertEqual(boundary_row["stacking_status"], "classified")

        abab_frames, abab_prototypes = _prototype_analysis(
            state_for_site=lambda row, column: (row + column) % 2,
        )
        abab = analyze_molecular_stacking(abab_frames, abab_prototypes)
        self.assertTrue(
            all(value.pattern == "ABAB" for value in abab.orders)
        )

        boundary_frames, boundary_prototypes = _prototype_analysis(
            state_for_site=lambda row, column: (
                (row + column) % 2
                if column < 4
                else 1 - (row + column) % 2
            ),
        )
        boundary = analyze_molecular_stacking(
            boundary_frames,
            boundary_prototypes,
        )
        self.assertTrue(
            all(value.pattern == "mixed" for value in boundary.orders)
        )
        self.assertTrue(
            all(
                "phase_boundary" in value.qc_reasons
                for value in boundary.orders
            )
        )


if __name__ == "__main__":
    unittest.main()
