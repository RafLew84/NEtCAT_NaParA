import unittest

from moltrack.analysis import M6OverlayPointState, build_m6_point_overlay


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
    )


class M6PointOverlayTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
