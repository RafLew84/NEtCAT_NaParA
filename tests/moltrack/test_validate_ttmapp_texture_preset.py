import csv
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image

from moltrack.analysis import (
    TTMAPP_TEXTURE_DOMAIN_PRESET,
    TextureDomainPointInput,
    TextureDomainSessionState,
    analyze_texture_domain_descriptors,
)
from scripts.validate_ttmapp_texture_preset import (
    _collect_centroid_source_kinds,
    validate_independent_frame_range,
    write_texture_preset_validation_package,
)


def _frame_result(
    frame_index: int,
    *,
    unknown: bool = False,
    source_view: str = "expanded_aligned",
    settings=TTMAPP_TEXTURE_DOMAIN_PRESET,
):
    points = tuple(
        TextureDomainPointInput(
            source_id=f"point-{frame_index}-{index}",
            x_px=12.0 + index * 10.0,
            y_px=24.0,
        )
        for index in range(5)
    )
    descriptors = np.asarray(
        (
            (np.full(settings.histogram_bin_count, np.nan),) * 5
            if unknown
            else (settings.prototype_histograms[0],) * 5
        ),
        dtype=np.float64,
    )
    return analyze_texture_domain_descriptors(
        frame_index=frame_index,
        source_view=source_view,
        points=points,
        descriptors=descriptors,
        settings=settings,
    )


def _protocol_state(
    *,
    source_view: str = "expanded_aligned",
    settings=TTMAPP_TEXTURE_DOMAIN_PRESET,
) -> TextureDomainSessionState:
    return TextureDomainSessionState(
        settings=settings,
        source_view=source_view,
        frame_results=tuple(
            _frame_result(
                frame_index,
                unknown=frame_index == 210,
                source_view=source_view,
                settings=settings,
            )
            for frame_index in range(209, 249)
        ),
        range_start_frame=209,
        range_end_frame=248,
    )


def _protocol_frames() -> dict[int, np.ndarray]:
    base = np.arange(64 * 64, dtype=np.float32).reshape(64, 64)
    return {
        frame_index: base + float(frame_index)
        for frame_index in range(209, 249)
    }


def _segmentation_source_kinds(
    state: TextureDomainSessionState,
) -> dict[tuple[int, str], str]:
    return {
        (frame_result.frame_index, point.source_id): "segmentation"
        for frame_result in state.frame_results
        for point in frame_result.points
    }


class TtmappTexturePresetValidationTests(unittest.TestCase):
    def test_centroid_source_kind_collection_preserves_frame_and_source(self):
        state = TextureDomainSessionState(
            settings=TTMAPP_TEXTURE_DOMAIN_PRESET,
            source_view="expanded_aligned",
            frame_results=(_frame_result(209),),
            range_start_frame=209,
            range_end_frame=209,
        )
        segmentations = [
            SimpleNamespace(
                segmentation_id=point.source_id,
                mask=np.ones((4, 4), dtype=bool),
            )
            for point in state.frame_results[0].points
        ]
        segmentation_set = Mock()
        segmentation_set.get_segmentations.return_value = segmentations
        source_kinds = _collect_centroid_source_kinds(
            SimpleNamespace(molecular_segmentations=segmentation_set),
            state,
        )

        self.assertEqual(
            source_kinds,
            {
                (209, point.source_id): "segmentation"
                for point in state.frame_results[0].points
            },
        )
        segmentation_set.get_segmentations.assert_called_once_with(
            209,
            source_view="expanded_aligned",
        )

    def test_independent_range_is_fixed_and_rejects_calibration_overlap(self):
        self.assertEqual(
            validate_independent_frame_range(210, 249),
            tuple(range(210, 250)),
        )

        with self.assertRaisesRegex(ValueError, "250-268"):
            validate_independent_frame_range(249, 250)
        with self.assertRaisesRegex(ValueError, "210-249"):
            validate_independent_frame_range(209, 249)
        with self.assertRaisesRegex(ValueError, "210-249"):
            validate_independent_frame_range(210, 248)

    def test_package_is_review_ready_without_claiming_accuracy(self):
        state = _protocol_state()
        frames = _protocol_frames()
        centroid_source_kinds = _segmentation_source_kinds(state)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "validation"
            report = write_texture_preset_validation_package(
                state=state,
                frames_by_index=frames,
                centroid_source_kinds=centroid_source_kinds,
                output_dir=output_dir,
                source_session=Path("sam_full_075.moltrack.json"),
            )
            saved_report = json.loads(
                (output_dir / "validation_report.json").read_text(
                    encoding="utf-8"
                )
            )
            with (output_dir / "predictions.csv").open(
                "r",
                encoding="utf-8",
                newline="",
            ) as handle:
                predictions = list(csv.DictReader(handle))
            with (output_dir / "manual_review.csv").open(
                "r",
                encoding="utf-8",
                newline="",
            ) as handle:
                review_rows = list(csv.DictReader(handle))
            with (output_dir / "frames.csv").open(
                "r",
                encoding="utf-8",
                newline="",
            ) as handle:
                frame_rows = list(csv.DictReader(handle))
            with Image.open(
                output_dir / "review_contact_sheet.png"
            ) as contact_sheet:
                contact_sheet_size = contact_sheet.size

            self.assertEqual(report, saved_report)
            self.assertEqual(report["status"], "awaiting_manual_reference")
            self.assertFalse(report["protocol"]["tuning_performed"])
            self.assertTrue(
                report["protocol"]["all_points_from_segmentations"]
            )
            self.assertEqual(
                report["centroid_source_counts"],
                {"segmentation": 200, "bbox_center": 0},
            )
            self.assertEqual(
                report["frame_numbers"],
                list(range(210, 250)),
            )
            self.assertNotIn("accuracy", report)
            self.assertNotIn("macro_f1", report)
            self.assertEqual(len(predictions), 200)
            self.assertTrue(
                all(
                    row["centroid_source_kind"] == "segmentation"
                    for row in predictions
                )
            )
            self.assertEqual(
                [row["review_id"] for row in predictions[:5]],
                [f"210:{index}" for index in range(1, 6)],
            )
            self.assertEqual(len(review_rows), 200)
            self.assertTrue(
                all(row["manual_class"] == "" for row in review_rows)
            )
            self.assertEqual(len(frame_rows), 40)
            self.assertEqual(frame_rows[0]["orientation_a_count"], "5")
            self.assertEqual(frame_rows[1]["unknown_count"], "5")
            self.assertGreater(contact_sheet_size[0], 0)
            self.assertGreater(contact_sheet_size[1], 0)
            self.assertTrue(
                (output_dir / "clean" / "frame_210_clean.png").is_file()
            )
            self.assertTrue(
                (
                    output_dir
                    / "overlays"
                    / "frame_210_texture_domains.png"
                ).is_file()
            )
            self.assertTrue(
                (
                    output_dir
                    / "indexed"
                    / "frame_210_review_ids.png"
                ).is_file()
            )
            self.assertTrue(
                (output_dir / "validation_report.md").is_file()
            )
            markdown_report = (
                output_dir / "validation_report.md"
            ).read_text(encoding="utf-8")
            self.assertIn("tuning_performed=false", markdown_report)
            self.assertIn(
                "all_points_from_segmentations=true",
                markdown_report,
            )

    def test_package_rejects_non_protocol_state(self):
        state = _protocol_state()
        frames = _protocol_frames()
        source_kinds = _segmentation_source_kinds(state)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "validation"
            raw_state = _protocol_state(source_view="raw")
            other_settings = replace(
                TTMAPP_TEXTURE_DOMAIN_PRESET,
                preset_id="not-the-frozen-preset",
            )
            other_preset_state = _protocol_state(settings=other_settings)
            for invalid_state in (
                raw_state,
                replace(state, use_segmentation_centroids=False),
                other_preset_state,
            ):
                with self.subTest(state=invalid_state):
                    with self.assertRaises(ValueError):
                        write_texture_preset_validation_package(
                            state=invalid_state,
                            frames_by_index=frames,
                            centroid_source_kinds=source_kinds,
                            output_dir=output_dir,
                            source_session=Path("session.moltrack.json"),
                        )
            invalid_source_kinds = dict(source_kinds)
            invalid_source_kinds[next(iter(invalid_source_kinds))] = (
                "bbox_center"
            )
            with self.assertRaisesRegex(
                ValueError,
                "segmentation centroid",
            ):
                write_texture_preset_validation_package(
                    state=state,
                    frames_by_index=frames,
                    centroid_source_kinds=invalid_source_kinds,
                    output_dir=output_dir,
                    source_session=Path("session.moltrack.json"),
                )
            self.assertFalse(output_dir.exists())

    def test_package_does_not_overwrite_existing_manual_review(self):
        state = _protocol_state()
        source_kinds = _segmentation_source_kinds(state)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "validation"
            output_dir.mkdir()
            manual_review = output_dir / "manual_review.csv"
            manual_review.write_text("reviewed data", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "not empty"):
                write_texture_preset_validation_package(
                    state=state,
                    frames_by_index=_protocol_frames(),
                    centroid_source_kinds=source_kinds,
                    output_dir=output_dir,
                    source_session=Path("session.moltrack.json"),
                )

            self.assertEqual(
                manual_review.read_text(encoding="utf-8"),
                "reviewed data",
            )

    def test_package_failure_does_not_publish_partial_output(self):
        state = _protocol_state()
        source_kinds = _segmentation_source_kinds(state)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "validation"
            with patch(
                "scripts.validate_ttmapp_texture_preset._render_frame_pair",
                side_effect=RuntimeError("render failed"),
            ):
                with self.assertRaisesRegex(RuntimeError, "render failed"):
                    write_texture_preset_validation_package(
                        state=state,
                        frames_by_index=_protocol_frames(),
                        centroid_source_kinds=source_kinds,
                        output_dir=output_dir,
                        source_session=Path("session.moltrack.json"),
                    )

            self.assertFalse(output_dir.exists())
            self.assertEqual(list(Path(tmpdir).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
