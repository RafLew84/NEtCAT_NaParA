"""Small, label-free input boundary for all domain discovery experiments."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

INPUT_KEYS = {"image", "measured", "centers_xy", "boxes_xyxy", "object_ids"}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def arrays_hash(arrays: dict[str, np.ndarray]) -> str:
    """Hash contents, independent of ZIP timestamps/compression."""
    digest = hashlib.sha256()
    for key, value in sorted(arrays.items()):
        array = np.ascontiguousarray(value)
        if array.dtype.hasobject:
            raise ValueError("Object arrays are forbidden")
        digest.update(json.dumps([key, array.dtype.str, array.shape]).encode())
        digest.update(array.tobytes())
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def validate_input(arrays: dict[str, np.ndarray]) -> None:
    if set(arrays) != INPUT_KEYS:
        raise ValueError(f"Unexpected analysis fields: {set(arrays) ^ INPUT_KEYS}")
    image, measured = arrays["image"], arrays["measured"]
    centers, boxes, ids = (arrays[k] for k in ("centers_xy", "boxes_xyxy", "object_ids"))
    if image.ndim != 2 or measured.shape != image.shape or measured.dtype != bool:
        raise ValueError("Invalid image/measurement mask")
    if not measured.any() or not np.isfinite(image[measured]).all():
        raise ValueError("Missing or non-finite measured image")
    if centers.shape != (len(ids), 2) or boxes.shape != (len(ids), 4):
        raise ValueError("Invalid object array shapes")
    if ids.dtype.kind != "U" or len(np.unique(ids)) != len(ids):
        raise ValueError("Object IDs must be unique strings within the frame")
    if not np.isfinite(centers).all() or not np.isfinite(boxes).all():
        raise ValueError("Non-finite object geometry")
    if np.any(boxes[:, 2:] <= boxes[:, :2]):
        raise ValueError("Non-positive bounding box")
    if not np.allclose(centers, (boxes[:, :2] + boxes[:, 2:]) / 2, atol=1e-10):
        raise ValueError("Centers do not match boxes")
    height, width = image.shape
    if np.any(centers < 0) or np.any(centers >= [width, height]):
        raise ValueError("Center outside original measurement field")
    ij = np.floor(centers).astype(int)
    if len(ij) and not measured[ij[:, 1], ij[:, 0]].all():
        raise ValueError("Center outside measured pixels")


def write_arrays(path: Path, arrays: dict[str, np.ndarray]) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)
    return {"sha256": file_hash(path), "content_sha256": arrays_hash(arrays)}


def load_sample(analysis_dir: Path, sample_id: str) -> tuple[dict, dict[str, np.ndarray]]:
    """Load only the analysis tree. No reference directory or labels are accepted."""
    manifest = json.loads((analysis_dir / "manifest.json").read_text())
    if manifest.get("schema") != "stmdomains-input-v1":
        raise ValueError("Unsupported analysis schema")
    records = [r for r in manifest["samples"] if r["sample_id"] == sample_id]
    if len(records) != 1:
        raise ValueError(f"Unknown or duplicate sample: {sample_id}")
    record = records[0]
    path = (analysis_dir / record["file"]).resolve()
    if not path.is_relative_to(analysis_dir.resolve()):
        raise ValueError("Sample path escapes analysis directory")
    if file_hash(path) != record["sha256"]:
        raise ValueError("Sample file hash mismatch")
    with np.load(path, allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files}
    validate_input(arrays)
    if arrays_hash(arrays) != record["content_sha256"]:
        raise ValueError("Sample content hash mismatch")
    return record, arrays
