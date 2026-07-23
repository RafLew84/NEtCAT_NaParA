import unittest

from moltrack.analysis import (
    M6_ANALYSIS_OVERLAY_MODES,
    M6OverlayPointState,
    build_m6_point_overlay,
)


def _point(
    source_id: str,
    *,
    q6: float | None = 0.8,
    orientation_deg: float | None = 10.0,
    orientation_status: str = "defined",
    computation_status: str = "valid_order",
    assignment_status: str = "assigned",
    domain_id: int = 0,
    ordered_component_id: int = 0,
    component_type: str = "full_domain",
    q3: float | None = 0.7,
    m3_orientation_deg: float | None = 20.0,
    m3_orientation_status: str = "defined",
    symmetry_model: str | None = "trifold",
    symmetry_confidence: float | None = 0.8,
    lattice_domain_id: str | None = "lattice-domain-a",
    lattice_point_role: str = "core",
    lattice_boundary_reason: str | None = None,
) -> M6OverlayPointState:
    return M6OverlayPointState(
        source_id=source_id,
        source_xy_px=(float(len(source_id)), 2.0),
        q6=q6,
        orientation_deg=orientation_deg,
        orientation_status=orientation_status,
        computation_status=computation_status,
        assignment_status=assignment_status,
        m6_orientation_domain_id=domain_id,
        ordered_component_id=ordered_component_id,
        component_type=component_type,
        q3=q3,
        m3_orientation_deg=m3_orientation_deg,
        m3_orientation_status=m3_orientation_status,
        symmetry_model=symmetry_model,
        symmetry_confidence=symmetry_confidence,
        lattice_domain_id=lattice_domain_id,
        lattice_point_role=lattice_point_role,
        lattice_boundary_reason=lattice_boundary_reason,
    )


class M6PointOverlayTests(unittest.TestCase):
    def test_multisymmetry_overlay_modes_are_public(self) -> None:
        self.assertEqual(
            M6_ANALYSIS_OVERLAY_MODES,
            (
                "none",
                "q6",
                "orientation",
                "q3",
                "m3_orientation",
                "symmetry_evidence",
                "domain_id",
                "lattice_domains",
                "domain_boundaries",
            ),
        )

    def test_lattice_domains_color_final_ids_and_distinguish_core_from_halo(self) -> None:
        points = (
            _point("a-core", lattice_domain_id="lattice-a", lattice_point_role="core"),
            _point("a-halo", lattice_domain_id="lattice-a", lattice_point_role="halo"),
            _point("b-core", lattice_domain_id="lattice-b", lattice_point_role="core"),
            _point(
                "boundary",
                lattice_domain_id=None,
                lattice_point_role="boundary",
                lattice_boundary_reason="incompatible_domain_edge",
            ),
        )

        overlay = build_m6_point_overlay(
            points,
            mode="lattice_domains",
            opacity_percent=80,
        )

        self.assertEqual(
            overlay.point_statuses,
            (
                "lattice_domain_core",
                "lattice_domain_halo",
                "lattice_domain_core",
                "lattice_boundary",
            ),
        )
        self.assertEqual(overlay.colors_rgba[0][:3], overlay.colors_rgba[1][:3])
        self.assertGreater(overlay.colors_rgba[0][3], overlay.colors_rgba[1][3])
        self.assertNotEqual(overlay.colors_rgba[0][:3], overlay.colors_rgba[2][:3])

    def test_lattice_domains_keep_proto_seed_without_final_id_unassigned(self) -> None:
        proto_seed = _point(
            "proto-seed",
            lattice_domain_id=None,
            lattice_point_role="core",
        )

        overlay = build_m6_point_overlay(
            (proto_seed,),
            mode="lattice_domains",
            opacity_percent=100,
        )
        hidden = build_m6_point_overlay(
            (proto_seed,),
            mode="lattice_domains",
            opacity_percent=100,
            show_unassigned_points=False,
        )

        self.assertEqual(overlay.point_statuses, ("unassigned",))
        self.assertEqual(hidden.point_count, 0)

    def test_domain_boundaries_can_hide_non_boundary_points(self) -> None:
        points = (
            _point("core", lattice_domain_id="lattice-a", lattice_point_role="core"),
            _point(
                "boundary",
                lattice_domain_id=None,
                lattice_point_role="boundary",
                lattice_boundary_reason="competing_domain_claim",
            ),
            _point(
                "unassigned",
                lattice_domain_id=None,
                lattice_point_role="unassigned",
            ),
        )

        overlay = build_m6_point_overlay(
            points,
            mode="domain_boundaries",
            opacity_percent=100,
            show_unassigned_points=False,
        )

        self.assertEqual(overlay.source_ids, ("boundary",))
        self.assertEqual(overlay.point_statuses, ("lattice_boundary",))

    def test_domain_colors_are_stable_and_qc_and_unassigned_are_muted(self) -> None:
        points = (
            _point("domain-a-1", domain_id=0),
            _point("domain-a-2", domain_id=0, orientation_deg=12.0),
            _point("domain-b", domain_id=1, ordered_component_id=1),
            _point(
                "unassigned",
                assignment_status="boundary_or_disordered",
                domain_id=-1,
                ordered_component_id=-1,
                component_type="unassigned",
            ),
            _point(
                "duplicate",
                q6=None,
                orientation_deg=None,
                orientation_status="not_available",
                computation_status="duplicate_excluded",
                assignment_status="duplicate_excluded",
                domain_id=-1,
                ordered_component_id=-1,
                component_type="unassigned",
            ),
        )
        before = tuple(points)

        overlay = build_m6_point_overlay(
            points,
            mode="domain_id",
            opacity_percent=60,
            show_unassigned_points=True,
        )

        self.assertEqual(points, before)
        self.assertEqual(overlay.point_count, 5)
        self.assertEqual(overlay.colors_rgba[0], overlay.colors_rgba[1])
        self.assertNotEqual(overlay.colors_rgba[0][:3], overlay.colors_rgba[2][:3])
        self.assertNotEqual(overlay.colors_rgba[3][:3], overlay.colors_rgba[4][:3])
        self.assertTrue(all(color[3] == 153 for color in overlay.colors_rgba))
        self.assertEqual(
            overlay.point_statuses,
            ("domain", "domain", "domain", "unassigned", "duplicate_excluded"),
        )

    def test_orientation_does_not_assign_angle_color_to_undefined_orientation(self) -> None:
        points = (
            _point("defined", q6=1.0, orientation_deg=15.0),
            _point(
                "undefined",
                q6=0.0,
                orientation_deg=None,
                orientation_status="undefined_zero_magnitude",
            ),
        )

        overlay = build_m6_point_overlay(
            points,
            mode="orientation",
            opacity_percent=80,
        )

        self.assertEqual(overlay.point_statuses, ("orientation", "undefined_orientation"))
        self.assertNotEqual(overlay.colors_rgba[0][:3], overlay.colors_rgba[1][:3])
        self.assertEqual(overlay.colors_rgba[0][3], 204)
        self.assertEqual(overlay.colors_rgba[1][3], 204)

    def test_q6_maps_strength_and_none_mode_or_filter_produce_no_arbitrary_points(self) -> None:
        assigned_low = _point("low", q6=0.1)
        assigned_high = _point("high", q6=0.9, domain_id=1, ordered_component_id=1)
        unassigned = _point(
            "unassigned",
            assignment_status="insufficient_neighbors",
            computation_status="insufficient_neighbors",
            q6=None,
            orientation_deg=None,
            orientation_status="not_available",
            domain_id=-1,
            ordered_component_id=-1,
            component_type="unassigned",
        )

        overlay = build_m6_point_overlay(
            (assigned_low, assigned_high, unassigned),
            mode="q6",
            opacity_percent=100,
            show_unassigned_points=False,
        )
        hidden = build_m6_point_overlay(
            (assigned_low, assigned_high, unassigned),
            mode="none",
            opacity_percent=100,
        )

        self.assertEqual(overlay.source_ids, ("low", "high"))
        self.assertNotEqual(overlay.colors_rgba[0][:3], overlay.colors_rgba[1][:3])
        self.assertEqual(hidden.point_count, 0)

    def test_q3_and_m3_orientation_are_independent_from_m6_assignment(self) -> None:
        trifold = _point(
            "trifold",
            assignment_status="boundary_or_disordered",
            domain_id=-1,
            ordered_component_id=-1,
            component_type="unassigned",
            q3=0.9,
            m3_orientation_deg=27.0,
        )

        q3_overlay = build_m6_point_overlay(
            (trifold,),
            mode="q3",
            opacity_percent=100,
        )
        orientation_overlay = build_m6_point_overlay(
            (trifold,),
            mode="m3_orientation",
            opacity_percent=100,
        )

        self.assertEqual(q3_overlay.point_statuses, ("q3",))
        self.assertEqual(orientation_overlay.point_statuses, ("m3_orientation",))
        self.assertGreater(q3_overlay.colors_rgba[0][3], 0)
        self.assertGreater(orientation_overlay.colors_rgba[0][3], 0)

    def test_new_modes_hide_only_unavailable_qc_points_when_requested(self) -> None:
        trifold_without_m6_domain = _point(
            "trifold",
            assignment_status="boundary_or_disordered",
            domain_id=-1,
            ordered_component_id=-1,
            component_type="unassigned",
        )
        unavailable = _point(
            "unavailable",
            q3=None,
            m3_orientation_deg=None,
            m3_orientation_status="insufficient_neighbors",
            symmetry_model="unavailable",
            symmetry_confidence=None,
            computation_status="insufficient_neighbors",
            assignment_status="insufficient_neighbors",
            domain_id=-1,
            ordered_component_id=-1,
            component_type="unassigned",
        )

        for mode in ("q3", "m3_orientation", "symmetry_evidence"):
            with self.subTest(mode=mode):
                overlay = build_m6_point_overlay(
                    (trifold_without_m6_domain, unavailable),
                    mode=mode,
                    opacity_percent=100,
                    show_unassigned_points=False,
                )
                self.assertEqual(overlay.source_ids, ("trifold",))

    def test_symmetry_evidence_colors_class_and_scales_alpha_by_confidence(self) -> None:
        points = (
            _point("tri", symmetry_model="trifold", symmetry_confidence=1.0),
            _point("six", symmetry_model="sixfold", symmetry_confidence=0.5),
            _point("mixed", symmetry_model="mixed", symmetry_confidence=0.75),
            _point("amb", symmetry_model="ambiguous", symmetry_confidence=0.0),
        )

        overlay = build_m6_point_overlay(
            points,
            mode="symmetry_evidence",
            opacity_percent=100,
        )

        self.assertEqual(
            overlay.point_statuses,
            (
                "symmetry_trifold",
                "symmetry_sixfold",
                "symmetry_mixed",
                "symmetry_ambiguous",
            ),
        )
        self.assertEqual(len({color[:3] for color in overlay.colors_rgba}), 4)
        self.assertGreater(overlay.colors_rgba[0][3], overlay.colors_rgba[1][3])


if __name__ == "__main__":
    unittest.main()
