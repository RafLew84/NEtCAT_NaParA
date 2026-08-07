import unittest
from dataclasses import replace

import numpy as np

from moltrack.analysis import (
    TTMAPP_TEXTURE_DOMAIN_PRESET,
    TextureDomainAnalysisSettings,
    TextureDomainClassDefinition,
    TextureDomainPointInput,
    TextureDomainViewSettings,
    analyze_texture_domain_descriptors,
    build_texture_domain_point_overlay,
    texture_domain_frame_fingerprint,
)


def _settings(*, minimum_component_size=2):
    return TextureDomainAnalysisSettings(
        preset_id="synthetic-v1",
        classes=(
            TextureDomainClassDefinition(
                key="orientation_a",
                short_label="A",
                display_name="Orientation A",
                reference_name="BLACK",
                color_rgb=(0, 180, 255),
            ),
            TextureDomainClassDefinition(
                key="orientation_b",
                short_label="B",
                display_name="Orientation B",
                reference_name="RED",
                color_rgb=(240, 45, 40),
            ),
            TextureDomainClassDefinition(
                key="orientation_c",
                short_label="C",
                display_name="Orientation C",
                reference_name="YELLOW",
                color_rgb=(245, 205, 0),
            ),
        ),
        prototype_histograms=(
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        ),
        distance_thresholds=(0.4, 0.4, 0.4),
        minimum_margin=0.05,
        render_scale=2,
        local_radius_rendered_px=24,
        high_pass_sigma_rendered_px=12.0,
        histogram_sigma_bins=1.5,
        neighbor_min_distance_source_px=0.0,
        neighbor_max_distance_source_px=1.5,
        neighbor_weight=0.0,
        smoothing_rounds=1,
        minimum_component_size=minimum_component_size,
    )


class TextureDomainAnalysisTests(unittest.TestCase):
    def test_ttmapp_preset_has_calibrated_prototypes_and_provenance(self):
        settings = TTMAPP_TEXTURE_DOMAIN_PRESET

        self.assertEqual(settings.preset_id, "ttmapp-local-texture-v1")
        self.assertEqual(
            tuple(value.reference_name for value in settings.classes),
            ("BLACK", "RED", "YELLOW"),
        )
        self.assertEqual(np.asarray(settings.prototype_histograms).shape, (3, 90))
        self.assertEqual(settings.minimum_component_size, 5)
        self.assertTrue(settings.experimental)
        self.assertEqual(len(settings.fingerprint), 64)

    def test_descriptor_classification_builds_same_class_components(self):
        points = tuple(
            TextureDomainPointInput(
                source_id=f"point-{index}",
                x_px=x,
                y_px=y,
            )
            for index, (x, y) in enumerate(
                (
                    (0.0, 0.0),
                    (1.0, 0.0),
                    (10.0, 0.0),
                    (11.0, 0.0),
                    (20.0, 0.0),
                    (21.0, 0.0),
                )
            )
        )
        descriptors = np.asarray(
            (
                (1.0, 0.0, 0.0),
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
                (0.0, 1.0, 0.0),
                (0.0, 0.0, 1.0),
                (0.0, 0.0, 1.0),
            ),
            dtype=np.float64,
        )

        frame = analyze_texture_domain_descriptors(
            frame_index=7,
            source_view="expanded_aligned",
            points=points,
            descriptors=descriptors,
            settings=_settings(),
        )

        self.assertEqual(
            tuple(value.class_key for value in frame.points),
            (
                "orientation_a",
                "orientation_a",
                "orientation_b",
                "orientation_b",
                "orientation_c",
                "orientation_c",
            ),
        )
        self.assertEqual(
            tuple(value.component_id for value in frame.points),
            ("A01", "A01", "B01", "B01", "C01", "C01"),
        )
        self.assertEqual(
            tuple(value.component_id for value in frame.components),
            ("A01", "B01", "C01"),
        )

    def test_ambiguous_descriptor_and_small_component_become_unknown(self):
        points = (
            TextureDomainPointInput("ambiguous", 0.0, 0.0),
            TextureDomainPointInput("small-a", 10.0, 0.0),
        )
        descriptors = np.asarray(
            (
                (1.0, 1.0, 0.0),
                (1.0, 0.0, 0.0),
            ),
            dtype=np.float64,
        )

        frame = analyze_texture_domain_descriptors(
            frame_index=0,
            source_view="raw",
            points=points,
            descriptors=descriptors,
            settings=_settings(minimum_component_size=2),
        )

        self.assertEqual(
            tuple(value.class_key for value in frame.points),
            ("unknown", "unknown"),
        )
        self.assertEqual(frame.components, ())

    def test_overlay_is_one_projection_with_configured_opacity(self):
        frame = analyze_texture_domain_descriptors(
            frame_index=0,
            source_view="raw",
            points=(
                TextureDomainPointInput("a", 0.0, 0.0),
                TextureDomainPointInput("b", 1.0, 0.0),
            ),
            descriptors=np.asarray(((1.0, 0.0, 0.0),) * 2),
            settings=_settings(),
        )

        overlay = build_texture_domain_point_overlay(
            frame,
            settings=_settings(),
            view_settings=TextureDomainViewSettings(
                show_overlay=True,
                opacity_percent=50,
                show_unknown=False,
            ),
        )

        self.assertEqual(overlay.source_ids, ("a", "b"))
        self.assertEqual(overlay.points_xy_px, ((0.0, 0.0), (1.0, 0.0)))
        self.assertEqual(overlay.colors_rgba[0], (0, 180, 255, 128))
        self.assertEqual(overlay.colors_rgba[1], (0, 180, 255, 128))

    def test_settings_fingerprint_changes_with_graph_parameter(self):
        settings = _settings()

        modified = replace(settings, neighbor_weight=0.05)

        self.assertNotEqual(settings.fingerprint, modified.fingerprint)

    def test_frame_fingerprint_changes_with_image_texture(self):
        first = np.zeros((8, 8), dtype=np.float32)
        second = first.copy()
        second[3, 4] = 1.0

        self.assertNotEqual(
            texture_domain_frame_fingerprint(first),
            texture_domain_frame_fingerprint(second),
        )

    def test_loaded_point_change_is_rejected_by_input_fingerprint(self):
        frame = analyze_texture_domain_descriptors(
            frame_index=0,
            source_view="raw",
            points=(
                TextureDomainPointInput("a", 0.0, 0.0),
                TextureDomainPointInput("b", 1.0, 0.0),
            ),
            descriptors=np.asarray(((1.0, 0.0, 0.0),) * 2),
            settings=_settings(),
        )
        payload = frame.to_dict()
        payload["points"][0]["x_px"] = 5.0

        with self.assertRaisesRegex(ValueError, "fingerprint"):
            type(frame).from_dict(payload)


if __name__ == "__main__":
    unittest.main()
