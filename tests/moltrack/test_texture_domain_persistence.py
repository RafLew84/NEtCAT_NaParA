import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

from moltrack.analysis import (
    TTMAPP_TEXTURE_DOMAIN_PRESET,
    TextureDomainPointInput,
    TextureDomainSessionState,
    TextureDomainViewSettings,
    analyze_texture_domain_descriptors,
    texture_domain_frame_fingerprint,
)
from moltrack.core import (
    MolecularDetection,
    MolecularDetectionSet,
    MolecularSegmentation,
    MolecularSegmentationSet,
    MolTrackImageSeries,
)
from moltrack.persistence import (
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
    save_moltrack_session,
)
from nanotrack.core import STMSequenceMetadata


def _texture_state() -> TextureDomainSessionState:
    settings = TTMAPP_TEXTURE_DOMAIN_PRESET
    frame_result = analyze_texture_domain_descriptors(
        frame_index=0,
        source_view="raw",
        points=tuple(
            TextureDomainPointInput(
                f"point-{index}",
                10.0 + index * 10.0,
                20.0,
            )
            for index in range(5)
        ),
        descriptors=np.asarray(
            (settings.prototype_histograms[0],) * 5,
            dtype=np.float64,
        ),
        settings=settings,
        frame_fingerprint=texture_domain_frame_fingerprint(
            np.zeros((64, 64), dtype=np.float32)
        ),
    )
    return TextureDomainSessionState(
        settings=settings,
        view_settings=TextureDomainViewSettings(
            show_overlay=True,
            opacity_percent=63,
            show_unknown=True,
        ),
        frame_results=(frame_result,),
        range_start_frame=0,
        range_end_frame=0,
    )


def _detections(*, x_offset: float = 0.0) -> MolecularDetectionSet:
    result = MolecularDetectionSet(frame_count=1)
    result.set_detections(
        0,
        [
            MolecularDetection(
                frame_index=0,
                bbox_xyxy=(
                    8.0 + index * 10.0 + x_offset,
                    18.0,
                    12.0 + index * 10.0 + x_offset,
                    22.0,
                ),
                confidence=0.9,
                detection_id=f"point-{index}",
            )
            for index in range(5)
        ],
        source_view="raw",
        frame_shape=(64, 64),
    )
    return result


def _segmentation_texture_state() -> TextureDomainSessionState:
    settings = TTMAPP_TEXTURE_DOMAIN_PRESET
    frame_result = analyze_texture_domain_descriptors(
        frame_index=0,
        source_view="raw",
        points=(TextureDomainPointInput("seg-1", 10.5, 20.5),),
        descriptors=np.asarray(
            (settings.prototype_histograms[0],),
            dtype=np.float64,
        ),
        settings=settings,
        frame_fingerprint=texture_domain_frame_fingerprint(
            np.zeros((64, 64), dtype=np.float32)
        ),
    )
    return TextureDomainSessionState(
        settings=settings,
        frame_results=(frame_result,),
        range_start_frame=0,
        range_end_frame=0,
    )


def _segmentations() -> MolecularSegmentationSet:
    mask = np.zeros((64, 64), dtype=bool)
    mask[19:22, 9:12] = True
    result = MolecularSegmentationSet(frame_count=1)
    result.add_segmentation(
        MolecularSegmentation(
            frame_index=0,
            source_view="raw",
            bbox_xyxy=(9.0, 19.0, 12.0, 22.0),
            mask=mask,
            segmentation_id="seg-1",
        )
    )
    return result


class TextureDomainPersistenceTests(unittest.TestCase):
    def test_save_load_and_restore_preserve_texture_domain_result(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "movie.mpp"
            source_path.write_bytes(b"texture-domain-source")
            state_path = root / "state.moltrack.json"
            metadata = STMSequenceMetadata(pixels_x=64, pixels_y=64)
            series = MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=np.zeros((1, 64, 64), dtype=np.float32),
                metadata=metadata,
                molecular_detections=_detections(),
                texture_domain_state=_texture_state(),
            )

            save_moltrack_session(state_path, series)
            loaded = load_moltrack_session(state_path)
            restored = restore_moltrack_image_series_from_session(
                loaded,
                series_loader=lambda *_args, **_kwargs: MolTrackImageSeries(
                    source_path=str(source_path),
                    raw_frames=np.zeros((1, 64, 64), dtype=np.float32),
                    metadata=metadata,
                    molecular_detections=_detections(),
                ),
            )
            payload = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual(loaded.texture_domain_analysis_state, _texture_state())
        self.assertEqual(restored.texture_domain_state, _texture_state())
        self.assertEqual(
            payload["texture_domain_analysis"]["view_settings"][
                "opacity_percent"
            ],
            63,
        )

    def test_missing_or_invalid_optional_texture_state_does_not_block_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "movie.mpp"
            source_path.write_bytes(b"legacy-texture-domain-source")
            state_path = root / "state.moltrack.json"
            series = MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=np.zeros((1, 8, 8), dtype=np.float32),
                metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
            )
            save_moltrack_session(state_path, series)
            payload = json.loads(state_path.read_text(encoding="utf-8"))

            payload.pop("texture_domain_analysis", None)
            state_path.write_text(json.dumps(payload), encoding="utf-8")
            legacy = load_moltrack_session(state_path)

            payload["texture_domain_analysis"] = _texture_state().to_dict()
            payload["texture_domain_analysis"]["range_end_frame"] = 7
            state_path.write_text(json.dumps(payload), encoding="utf-8")
            out_of_range = load_moltrack_session(state_path)

            payload["texture_domain_analysis"] = {
                "schema_version": 999,
                "algorithm_version": "unsupported",
            }
            state_path.write_text(json.dumps(payload), encoding="utf-8")
            invalid = load_moltrack_session(state_path)

        self.assertIsNone(legacy.texture_domain_analysis_state)
        self.assertIsNone(out_of_range.texture_domain_analysis_state)
        self.assertIsNone(invalid.texture_domain_analysis_state)

    def test_restore_drops_texture_result_when_detection_positions_changed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "movie.mpp"
            source_path.write_bytes(b"changed-texture-domain-source")
            state_path = root / "state.moltrack.json"
            metadata = STMSequenceMetadata(pixels_x=64, pixels_y=64)
            series = MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=np.zeros((1, 64, 64), dtype=np.float32),
                metadata=metadata,
                molecular_detections=_detections(),
                texture_domain_state=_texture_state(),
            )
            save_moltrack_session(state_path, series)
            loaded = load_moltrack_session(state_path)
            loaded = replace(
                loaded,
                molecular_detections=_detections(x_offset=1.0),
            )

            restored = restore_moltrack_image_series_from_session(
                loaded,
                series_loader=lambda *_args, **_kwargs: MolTrackImageSeries(
                    source_path=str(source_path),
                    raw_frames=np.zeros((1, 64, 64), dtype=np.float32),
                    metadata=metadata,
                    molecular_detections=_detections(),
                ),
            )

        self.assertIsNone(restored.texture_domain_state)

    def test_restore_checks_saved_mask_centroid_without_rescanning_full_mask(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "movie.mpp"
            source_path.write_bytes(b"mask-centroid-source")
            state_path = root / "state.moltrack.json"
            metadata = STMSequenceMetadata(pixels_x=64, pixels_y=64)
            series = MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=np.zeros((1, 64, 64), dtype=np.float32),
                metadata=metadata,
                molecular_segmentations=_segmentations(),
                texture_domain_state=_segmentation_texture_state(),
            )
            save_moltrack_session(state_path, series)
            loaded = load_moltrack_session(state_path)
            loader = lambda *_args, **_kwargs: MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=np.zeros((1, 64, 64), dtype=np.float32),
                metadata=metadata,
            )

            valid = restore_moltrack_image_series_from_session(
                loaded,
                series_loader=loader,
            )
            loaded_segmentation = (
                loaded.molecular_segmentations.get_segmentation("seg-1")
            )
            loaded_segmentation.metadata[
                "_moltrack_loaded_mask_centroid_x_px"
            ] = 11.5
            stale = restore_moltrack_image_series_from_session(
                loaded,
                series_loader=loader,
            )

        self.assertIsNotNone(valid.texture_domain_state)
        self.assertIsNone(stale.texture_domain_state)


if __name__ == "__main__":
    unittest.main()
