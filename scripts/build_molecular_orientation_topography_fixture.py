"""Build the compact TTMAPP topography fixture used by orientation tests."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from moltrack.analysis import load_molecular_orientation_reference
from moltrack.core import build_moltrack_expanded_aligned_stack
from moltrack.persistence.session_store import (
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_fixture(
    *,
    reference_path: Path,
    session_path: Path,
    output_path: Path,
) -> None:
    reference = load_molecular_orientation_reference(reference_path)
    session = load_moltrack_session(session_path)
    source_path = Path(session.source_path)
    if _sha256(source_path) != reference.source_file_sha256:
        raise ValueError("Source MPP does not match the orientation reference.")
    if _sha256(session_path) != reference.source_session_sha256:
        raise ValueError("MolTrack state does not match the orientation reference.")

    series = restore_moltrack_image_series_from_session(session)
    expanded = build_moltrack_expanded_aligned_stack(series)
    segmentations = {
        segmentation.segmentation_id: segmentation
        for frame_index in range(series.frame_count)
        for segmentation in series.molecular_segmentations.get_segmentations(
            frame_index
        )
    }

    topography_patches = []
    masks = []
    valid_fov_masks = []
    for sample in reference.samples:
        measurement = sample.measurement
        provenance = measurement.provenance
        segmentation = segmentations[provenance.source_id]
        if (
            segmentation.frame_index != provenance.frame_index
            or segmentation.source_view != provenance.source_view
        ):
            raise ValueError(
                f"Segmentation identity does not match reference sample "
                f"{sample.sample_id}."
            )
        x0, y0, x1, y1 = (
            int(value) for value in provenance.patch_bbox_xyxy
        )
        patch = np.asarray(
            expanded.frames[provenance.frame_index, y0:y1, x0:x1],
            dtype=np.float32,
        )
        mask = np.asarray(
            segmentation.mask[y0:y1, x0:x1],
            dtype=bool,
        )
        if patch.shape != measurement.patch_shape_px or mask.shape != patch.shape:
            raise ValueError(
                f"Patch shape does not match reference sample {sample.sample_id}."
            )
        topography_patches.append(patch)
        masks.append(mask)
        valid_fov_masks.append(np.isfinite(patch))

    frame_height, frame_width = series.raw_frames.shape[1:]
    pixel_size_nm_xy = np.asarray(
        (
            series.metadata.size_nm_x / frame_width,
            series.metadata.size_nm_y / frame_height,
        ),
        dtype=np.float64,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_path,
        fixture_schema_version=np.asarray(1, dtype=np.int64),
        reference_fingerprint=np.asarray(reference.fingerprint),
        source_file_sha256=np.asarray(reference.source_file_sha256),
        source_session_sha256=np.asarray(reference.source_session_sha256),
        sample_ids=np.asarray(
            [sample.sample_id for sample in reference.samples]
        ),
        topography=np.stack(topography_patches),
        masks=np.stack(masks),
        valid_fov_masks=np.stack(valid_fov_masks),
        pixel_size_nm_xy=pixel_size_nm_xy,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reference",
        type=Path,
        default=Path(
            "tests/moltrack/fixtures/"
            "molecular_orientation_reference_ttmapp_v1.json"
        ),
    )
    parser.add_argument(
        "--session",
        type=Path,
        default=Path("data/TTMAPP/m6_state.moltrack.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "tests/moltrack/fixtures/"
            "molecular_orientation_topography_ttmapp_v1.npz"
        ),
    )
    arguments = parser.parse_args()
    build_fixture(
        reference_path=arguments.reference,
        session_path=arguments.session,
        output_path=arguments.output,
    )


if __name__ == "__main__":
    main()
