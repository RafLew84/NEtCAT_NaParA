from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from moltrack.analysis.molecular_m6_analysis import MolecularM6OrientationAnalysis
from test_m6_single_range_domain_type_summary import (
    _classification,
    _observation,
)
from test_m6_domain_type_range_comparison import (
    _classification as _comparison_classification,
)


def _domain_type_classification():
    observations = (
        _observation(
            0,
            0,
            1.0,
            2.0,
            range_end=2,
            molecule_fraction=0.2,
            footprint_fraction=0.1,
        ),
        _observation(
            1,
            0,
            2.0,
            2.1,
            range_end=2,
            molecule_fraction=0.3,
            footprint_fraction=0.2,
        ),
        _observation(
            1,
            1,
            30.0,
            None,
            range_end=2,
            molecule_fraction=0.1,
            footprint_fraction=0.1,
            qualification_status="unclassified",
            unclassified_reason="missing_bond_length_statistics",
        ),
    )
    return _classification(observations, frame_count=3)


def _analysis(*components):
    source_ids = tuple(
        source_id for component in components for source_id in component.source_ids
    )
    analysis = Mock(spec=MolecularM6OrientationAnalysis)
    analysis.sample_coordinates = SimpleNamespace(
        point_source_ids=source_ids,
        source_points_xy_px=tuple(
            (float(index + 1), float(index + 2))
            for index in range(len(source_ids))
        ),
    )
    analysis.frame_aggregates = SimpleNamespace(
        domain_metrics=SimpleNamespace(components=tuple(components))
    )
    return analysis


def _component(component_id: int, *source_ids: str):
    return SimpleNamespace(
        ordered_component_id=component_id,
        source_ids=tuple(source_ids),
    )


class M6DomainTypeOverlayTests(unittest.TestCase):
    def test_colors_are_stable_and_unclassified_is_neutral_and_selectable(self) -> None:
        from moltrack.ui.m6_domain_type_overlay import (
            M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR,
            build_m6_domain_type_overlay_index,
            build_m6_domain_type_frame_overlay,
        )
        from moltrack.ui.m6_domain_type_selection import M6DomainTypeSelection

        classification = _domain_type_classification()
        index = build_m6_domain_type_overlay_index(classification)
        frame_zero = build_m6_domain_type_frame_overlay(
            _analysis(_component(0, "frame-0-a", "frame-0-b")),
            index,
            frame_index=0,
            opacity_percent=60,
            selection=M6DomainTypeSelection.classified(0),
        )
        frame_one = build_m6_domain_type_frame_overlay(
            _analysis(
                _component(0, "frame-1-a", "frame-1-b"),
                _component(1, "frame-1-unclassified"),
            ),
            index,
            frame_index=1,
            opacity_percent=60,
            selection=M6DomainTypeSelection.unclassified(),
        )

        self.assertEqual(frame_zero.overlay.mode, "domain_type")
        self.assertEqual(frame_zero.overlay.colors_rgba[0], frame_one.overlay.colors_rgba[0])
        self.assertEqual(frame_zero.highlighted_source_ids, ("frame-0-a", "frame-0-b"))
        self.assertEqual(
            frame_one.overlay.colors_rgba[-1][:3],
            M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR[:3],
        )
        self.assertEqual(frame_one.overlay.point_statuses[-1], "unclassified_domain")
        self.assertEqual(
            frame_one.highlighted_source_ids,
            ("frame-1-unclassified",),
        )

    def test_frame_outside_scope_has_no_false_type_and_inputs_are_not_mutated(self) -> None:
        from moltrack.ui.m6_domain_type_overlay import (
            build_m6_domain_type_overlay_index,
            build_m6_domain_type_frame_overlay,
        )

        classification = _domain_type_classification()
        analysis = _analysis(_component(0, "outside-a", "outside-b"))
        observations_before = classification.observations
        assignments_before = classification.assignments

        projection = build_m6_domain_type_frame_overlay(
            analysis,
            build_m6_domain_type_overlay_index(classification),
            frame_index=9,
            opacity_percent=80,
        )

        self.assertEqual(projection.overlay.point_count, 0)
        self.assertEqual(projection.highlighted_source_ids, ())
        self.assertIs(classification.observations, observations_before)
        self.assertIs(classification.assignments, assignments_before)

    def test_shared_type_keeps_color_between_comparison_ranges(self) -> None:
        from moltrack.ui.m6_domain_type_overlay import (
            build_m6_domain_type_overlay_index,
            build_m6_domain_type_frame_overlay,
        )

        classification = _comparison_classification()
        index = build_m6_domain_type_overlay_index(classification)
        before = build_m6_domain_type_frame_overlay(
            _analysis(
                _component(31, "before-type-b-1"),
                _component(32, "before-type-b-2"),
            ),
            index,
            frame_index=2,
            opacity_percent=100,
        )
        after = build_m6_domain_type_frame_overlay(
            _analysis(
                _component(71, "after-type-b"),
                _component(91, "after-type-c"),
            ),
            index,
            frame_index=3,
            opacity_percent=100,
        )

        self.assertEqual(
            before.overlay.colors_rgba[0],
            after.overlay.colors_rgba[0],
        )
        self.assertEqual(
            before.overlay.colors_rgba[0],
            before.overlay.colors_rgba[1],
        )
        self.assertNotEqual(
            after.overlay.colors_rgba[0],
            after.overlay.colors_rgba[1],
        )


if __name__ == "__main__":
    unittest.main()
