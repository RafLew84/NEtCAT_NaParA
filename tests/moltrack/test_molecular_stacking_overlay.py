import unittest
from dataclasses import replace

from moltrack.analysis import (
    MolecularStackingDisplayResult,
    MolecularStackingFrameGeometry,
    analyze_molecular_stacking,
    build_molecular_orientation_prototype_analysis,
    build_molecular_stacking_inspection,
    build_molecular_stacking_point_overlay,
)
from test_molecular_stacking_analysis import _prototype_analysis


def _display_result(
    *,
    state_for_site,
    angles: tuple[float, ...] = (20.0, 80.0),
):
    frames, prototypes = _prototype_analysis(
        state_for_site=state_for_site,
        angles=angles,
    )
    return MolecularStackingDisplayResult(
        frames=frames,
        prototype_analysis=prototypes,
        stacking_analysis=analyze_molecular_stacking(
            frames,
            prototypes,
        ),
    )


def _geometry(display, frame_index: int = 0):
    frame = display.frame_data(frame_index)
    source_ids = frame.row_assignment.source_ids
    return MolecularStackingFrameGeometry(
        frame_index=frame_index,
        source_ids=source_ids,
        points_xy_px=tuple(
            (
                float(int(source_id.rsplit("c", 1)[1])),
                float(int(source_id.split("-r", 1)[1].split("-", 1)[0])),
            )
            for source_id in source_ids
        ),
    )


class MolecularStackingOverlayTests(unittest.TestCase):
    def test_ab_state_overlay_uses_saved_assignments_and_independent_opacity(
        self,
    ) -> None:
        display = _display_result(
            state_for_site=lambda row, column: (row + column) % 2,
        )
        geometry = _geometry(display)

        overlay = build_molecular_stacking_point_overlay(
            display,
            geometry,
            layer="ab_states",
            opacity_percent=50,
        )

        self.assertEqual(overlay.layer, "ab_states")
        self.assertEqual(
            overlay.point_count,
            display.stacking_analysis.order_for_domain(
                0,
                "domain-0",
            ).ordered_molecule_count,
        )
        self.assertEqual(set(overlay.point_statuses), {"A", "B"})
        self.assertEqual(
            {color[3] for color in overlay.colors_rgba},
            {128},
        )
        color_by_state = {
            state: color[:3]
            for state, color in zip(
                overlay.point_statuses,
                overlay.colors_rgba,
            )
        }
        self.assertNotEqual(color_by_state["A"], color_by_state["B"])

    def test_stacking_subdomains_keep_phase_boundary_and_parent(self) -> None:
        display = _display_result(
            state_for_site=lambda row, column: (
                (row + column) % 2
                if column < 4
                else 1 - (row + column) % 2
            ),
        )
        geometry = _geometry(display)

        overlay = build_molecular_stacking_point_overlay(
            display,
            geometry,
            layer="stacking_subdomains",
            opacity_percent=25,
        )
        subdomains = display.stacking_analysis.subdomains
        left = build_molecular_stacking_inspection(
            display,
            frame_index=0,
            source_id=subdomains[0].source_ids[0],
        )
        right = build_molecular_stacking_inspection(
            display,
            frame_index=0,
            source_id=subdomains[1].source_ids[0],
        )

        self.assertEqual(
            overlay.point_count,
            display.stacking_analysis.order_for_domain(
                0,
                "domain-0",
            ).ordered_molecule_count,
        )
        self.assertEqual(
            {
                status.split(" | ", 1)[1]
                for status in overlay.point_statuses
            },
            {"checkerboard/ABAB", "checkerboard/BABA"},
        )
        self.assertEqual(
            len(
                {
                    color[:3]
                    for color in overlay.colors_rgba
                }
            ),
            2,
        )
        self.assertEqual({color[3] for color in overlay.colors_rgba}, {64})
        self.assertEqual(left.parent_lattice_domain_id, "domain-0")
        self.assertEqual(right.parent_lattice_domain_id, "domain-0")
        self.assertNotEqual(left.subdomain_id, right.subdomain_id)
        self.assertEqual({left.phase, right.phase}, {"ABAB", "BABA"})
        self.assertEqual(left.parent_pattern, "mixed")
        self.assertIn("phase_boundary", left.parent_qc_reasons)
        self.assertIn("phase_boundary", right.parent_qc_reasons)

    def test_selected_molecule_inspection_exposes_complete_audit_result(
        self,
    ) -> None:
        display = _display_result(
            state_for_site=lambda row, column: (row + column) % 2,
        )

        inspection = build_molecular_stacking_inspection(
            display,
            frame_index=0,
            source_id="f00-r00-c00",
        )

        self.assertEqual(inspection.state_label, "A")
        self.assertEqual(inspection.pattern, "ABAB")
        self.assertEqual(inspection.mode, "checkerboard")
        self.assertEqual(inspection.phase, "ABAB")
        self.assertEqual(inspection.axis_candidate_index, 0)
        self.assertAlmostEqual(inspection.axis_angle_deg, 0.0)
        self.assertAlmostEqual(inspection.prototype_a_angle_deg, 20.0)
        self.assertAlmostEqual(inspection.prototype_b_angle_deg, 80.0)
        self.assertGreater(inspection.score, 0.95)
        self.assertGreater(inspection.confidence, 0.9)
        self.assertAlmostEqual(inspection.coverage_fraction, 1.0)
        self.assertEqual(inspection.qc_reasons, ())
        self.assertEqual(inspection.parent_pattern, "ABAB")
        self.assertGreater(inspection.parent_score, 0.95)
        self.assertEqual(inspection.parent_qc_reasons, ())

    def test_missing_frame_or_source_returns_empty_projection(self) -> None:
        display = _display_result(
            state_for_site=lambda row, column: (row + column) % 2,
        )
        empty_geometry = MolecularStackingFrameGeometry(
            frame_index=9,
            source_ids=("outside",),
            points_xy_px=((1.0, 2.0),),
        )

        overlay = build_molecular_stacking_point_overlay(
            display,
            empty_geometry,
            layer="ab_states",
            opacity_percent=100,
        )

        self.assertEqual(overlay.point_count, 0)
        self.assertIsNone(
            build_molecular_stacking_inspection(
                display,
                frame_index=0,
                source_id="outside",
            )
        )

    def test_display_rejects_frames_from_another_orientation_run(
        self,
    ) -> None:
        display = _display_result(
            state_for_site=lambda row, column: (row + column) % 2,
        )
        first_frame = display.frames[0]
        changed_measurement = replace(
            first_frame.measurements[0],
            angle_deg=first_frame.measurements[0].angle_deg + 1.0,
        )
        changed_frames = (
            replace(
                first_frame,
                measurements=(
                    changed_measurement,
                    *first_frame.measurements[1:],
                ),
            ),
            *display.frames[1:],
        )

        with self.assertRaisesRegex(
            ValueError,
            "analyzed orientations",
        ):
            MolecularStackingDisplayResult(
                frames=changed_frames,
                prototype_analysis=display.prototype_analysis,
                stacking_analysis=display.stacking_analysis,
            )

    def test_uniform_order_uses_parent_lattice_row_axis(self) -> None:
        frames, _prototypes = _prototype_analysis(
            state_for_site=lambda _row, _column: 0,
            angles=(35.0,),
        )
        frames = tuple(
            replace(
                frame,
                row_assignment=replace(
                    frame.row_assignment,
                    domain_assignments=(
                        replace(
                            frame.row_assignment.domain_assignments[0],
                            status="available",
                            selected_candidate_index=0,
                            selection_margin=0.2,
                            reason="unique_best_axis",
                        ),
                    ),
                ),
            )
            for frame in frames
        )
        prototypes = build_molecular_orientation_prototype_analysis(frames)
        display = MolecularStackingDisplayResult(
            frames=frames,
            prototype_analysis=prototypes,
            stacking_analysis=analyze_molecular_stacking(
                frames,
                prototypes,
            ),
        )

        inspection = build_molecular_stacking_inspection(
            display,
            frame_index=0,
            source_id="f00-r00-c00",
        )

        self.assertEqual(inspection.pattern, "uniform")
        self.assertEqual(inspection.axis_candidate_index, 0)
        self.assertAlmostEqual(inspection.axis_angle_deg, 0.0)


if __name__ == "__main__":
    unittest.main()
