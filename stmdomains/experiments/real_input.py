"""Strict TTMAPP adapter; intentionally not a general MolTrack importer."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .bundle import file_hash, validate_input

MPP_SHA = "8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66"
SESSION_SHA = "d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e"
PILOT_NUMBERS = (1, 50, 100, 150, 200, *range(250, 269))


def convert_detections(records: list[dict], origins: np.ndarray, shape: tuple) -> tuple[dict, list]:
    """Current boxes only; never clipped, never historical labels or masks."""
    height, width = shape
    by_frame = {i: [] for i in range(len(origins))}
    excluded = []
    seen = set()
    for record in records:
        index, ident = record["frame_index"], record["detection_id"]
        if index not in by_frame or ident in seen:
            raise ValueError("Invalid frame index or duplicate detection ID")
        seen.add(ident)
        box = np.asarray(record["bbox_xyxy"], dtype=np.float64)
        if box.shape != (4,) or not np.isfinite(box).all() or np.any(box[2:] <= box[:2]):
            raise ValueError("Invalid current detection box")
        view = record["source_view"]
        if view == "expanded_aligned":
            box = box - np.tile(origins[index], 2)
        elif view != "raw":
            raise ValueError(f"Unsupported detection coordinates: {view}")
        center = (box[:2] + box[2:]) / 2
        if np.any(center < 0) or np.any(center >= [width, height]):
            excluded.append({"frame_index": index, "object_id": ident, "reason": "center_outside_field"})
        else:
            by_frame[index].append((ident, box))
    return by_frame, excluded


def load_ttmapp(mpp: Path, session: Path, frame_numbers=PILOT_NUMBERS) -> tuple[list, dict, dict]:
    from nanotrack.io.mpp_loader import load_mpp_sequence

    if file_hash(mpp) != MPP_SHA or file_hash(session) != SESSION_SHA:
        raise ValueError("TTMAPP source hash differs from the audited input; re-audit before use")
    data = json.loads(session.read_text())
    sequence = load_mpp_sequence(str(mpp))
    raw = sequence.raw_frames
    ids = data["working_series"]["source_frame_indices"]
    if raw.shape != (268, 256, 256) or ids != list(range(268)):
        raise ValueError("Unexpected TTMAPP frame geometry/order")
    if data["working_series"]["reverse_frame_order"] or not np.isfinite(raw).all():
        raise ValueError("Unexpected frame order or non-finite image")
    if data["molecular_detections"]["frame_count"] != len(raw):
        raise ValueError("Detection frame count mismatch")
    registrations = data["registration"]["results_by_frame"]
    if sorted(r["frame_index"] for r in registrations) != list(range(268)):
        raise ValueError("Registration must contain each frame once")
    registrations = sorted(registrations, key=lambda r: r["frame_index"])
    shifts = np.array([r["shift_xy"] for r in registrations], dtype=float)
    if shifts.shape != (268, 2) or not np.isfinite(shifts).all():
        raise ValueError("Invalid saved shifts")
    left_top = np.ceil(np.maximum(-shifts.min(axis=0), 0)).astype(int)
    right_bottom = np.ceil(np.maximum(shifts.max(axis=0), 0)).astype(int)
    origins = left_top + shifts
    canvas_wh = np.array(raw.shape[:0:-1]) + left_top + right_bottom
    if list(canvas_wh) != [480, 408] or list(left_top) != [224, 139]:
        raise ValueError("Expanded geometry differs from the audited input")
    by_frame, excluded = convert_detections(data["molecular_detections"]["detections"], origins, raw.shape[1:])
    samples = []
    if len(set(frame_numbers)) != len(frame_numbers):
        raise ValueError("Repeated frame number")
    for number in frame_numbers:
        if number not in range(1, 269):
            raise ValueError("Frame number outside TTMAPP")
        index = number - 1
        objects = by_frame[index]
        boxes = np.array([b for _, b in objects], dtype=float).reshape(-1, 4)
        arrays = dict(image=raw[index].copy(), measured=np.ones(raw.shape[1:], bool),
                      centers_xy=(boxes[:, :2] + boxes[:, 2:]) / 2, boxes_xyxy=boxes,
                      object_ids=np.array([i for i, _ in objects], dtype="U64"))
        validate_input(arrays)
        samples.append((dict(sample_id=f"ttmapp-{number:03}", kind="measurement",
                             frame_number=number, frame_index=index, source_frame_index=ids[index],
                             coordinate_system="raw_edge_xy", shape_hw=list(raw.shape[1:]),
                             pixel_spacing_xy=[1., 1.], position_unit="px", calibration_trusted=False,
                             origin_in_expanded_xy=origins[index].tolist(), expanded_shape_hw=canvas_wh[::-1].tolist(),
                             registration_status=registrations[index]["status"],
                             registration_quality=registrations[index]["quality_score"],
                             annotation_count=len(objects)), arrays))
    geometry = dict(origins=origins, canvas_hw=tuple(canvas_wh[::-1]), raw=raw)
    audit = dict(source_mpp_sha256=MPP_SHA, source_session_sha256=SESSION_SHA,
                 source_frame_count=268, selected_frame_numbers=list(frame_numbers),
                 total_detections=len(data["molecular_detections"]["detections"]), excluded=excluded,
                 no_detection_frame_numbers=[i+1 for i, rows in by_frame.items() if not rows],
                 missing_detection_semantics="not evidence of substrate or disorder",
                 raw_shape_hw=[256, 256], expanded_shape_hw=canvas_wh[::-1].tolist(),
                 padding_ltrb=[int(left_top[0]), int(left_top[1]), int(right_bottom[0]), int(right_bottom[1])],
                 reader="nanotrack.io.mpp_loader.load_mpp_sequence; 180-degree orientation; no display gamma",
                 units="px; physical calibration and frame times are placeholders",
                 source_size_bytes=mpp.stat().st_size, source_mtime_ns=mpp.stat().st_mtime_ns,
                 saved_mtime_ns=data["source"]["mtime_ns"],
                 identity_check="exact audited SHA-256, not modification time")
    return samples, geometry, audit
