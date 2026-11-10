"""Complete exported element metadata after partitioning, before prediction freeze.

This migration never recomputes descriptors, graph relations or assignments.
Cached sampler rows retain their original schema. The result extension names
the feature support and maximum effective support explicitly, in raw pixels.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

from ..bundle import file_hash, write_json
from ..results import validate_result
from .predict import read_json, write_gzip


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def normalize_element(row: dict, *, kind: str) -> dict:
    """Return an idempotent export row; preserve original sampler metadata."""
    if kind not in {"measurement", "synthetic"}:
        raise ValueError("Unknown sample kind in completed prediction index")
    feature = list(row["feature_support_xyxy"])
    effective = list(row.get("effective_support_xyxy", row["support_xyxy"]))
    xy = row["raw_edge_xy"]
    if len(feature) != 4 or len(effective) != 4 or len(xy) != 2:
        raise ValueError("Invalid exported element geometry")
    if not all(math.isfinite(v) for v in feature + effective + list(xy)):
        raise ValueError("Nonfinite exported element geometry")
    if any(feature[i] >= feature[i + 2] or effective[i] > feature[i]
           or effective[i + 2] < feature[i + 2] or not feature[i] <= xy[i] <= feature[i + 2]
           for i in range(2)):
        raise ValueError("Effective support must contain feature support and center")
    if not isinstance(row["available"], bool):
        raise ValueError("Element availability must be an explicit boolean")
    units = dict(raw_edge_xy="raw_px", support_xyxy="raw_px",
                 effective_support_xyxy="raw_px",
                 scale_px="px" if kind == "measurement" else "reference_px")
    return dict(row, support_xyxy=feature, effective_support_xyxy=effective,
                availability="available" if row["available"] else "unavailable", units=units)


def _other_payload(payload: dict) -> dict:
    extension = dict(payload["extensions"]["training_v1"])
    extension.pop("elements")
    return dict(payload, extensions=dict(payload["extensions"], training_v1=extension))


def _protected_files(output: Path) -> dict:
    return {str(path.relative_to(output)): file_hash(path)
            for path in sorted((output / "predictions").rglob("*"))
            if path.is_file() and (path.suffix == ".npz" or path.name.endswith("relations.json.gz"))}


def finalize(output: str | Path) -> dict:
    """Finalize only a completed, unfrozen prediction tree and write its audit.

    The final index is written by partition_all only after its last output. All
    indexed results must exist; every result in the tree must be indexed. The
    caller must finish the partition process before invoking this function.
    """
    output = Path(output).resolve()
    if (output / "frozen-predictions.json").exists():
        raise ValueError("Cannot migrate already frozen predictions")
    index_path = output / "predictions/index.json"
    if not index_path.is_file():
        raise ValueError("Completed partition index required before export finalization")
    index_hash = file_hash(index_path)
    entries = read_json(index_path)
    kinds, required = {}, set()
    for entry in entries:
        directory = (output / entry["directory"]).resolve()
        if not directory.is_relative_to(output / "predictions"):
            raise ValueError("Prediction directory escapes its output tree")
        if directory in kinds:
            raise ValueError("Duplicate prediction directory in index")
        kinds[directory] = entry["kind"]
        required.add(directory / "result.json.gz")
        if entry.get("evaluation_input") == "heldout-metrics-input.npz":
            required.add(directory / "heldout-result.json.gz")
    results = {path for path in (output / "predictions").rglob("*result.json.gz")
               if path.name in {"result.json.gz", "heldout-result.json.gz"}}
    if not required or results != required:
        raise ValueError("Completed prediction index and result files disagree")
    protected_before = _protected_files(output)
    changed = elements = 0
    payload_before, payload_after = {}, {}
    for path in sorted(results):
        payload = read_json(path)
        validate_result(payload)
        relative = str(path.relative_to(output))
        payload_before[relative] = _digest(_other_payload(payload))
        old_rows = payload["extensions"]["training_v1"]["elements"]
        rows = [normalize_element(row, kind=kinds[path.parent]) for row in old_rows]
        elements += len(rows)
        if rows != old_rows:
            payload["extensions"]["training_v1"]["elements"] = rows
            validate_result(payload)
            temporary = path.with_name(path.name + ".tmp")
            write_gzip(temporary, payload, compresslevel=1)
            os.replace(temporary, path)
            changed += 1
        saved = read_json(path)
        validate_result(saved)
        payload_after[relative] = _digest(_other_payload(saved))
        if saved["extensions"]["training_v1"]["elements"] != rows:
            raise ValueError("Exported metadata changed during serialization")
    protected_after = _protected_files(output)
    if protected_before != protected_after or payload_before != payload_after:
        raise ValueError("Export metadata migration changed prediction data")
    if file_hash(index_path) != index_hash:
        raise ValueError("Prediction index changed during export finalization")
    report = dict(schema="stmdomains-export-contract-audit-v1", passed=True,
                  results_checked=len(results), results_updated=changed,
                  elements_checked=elements, protected_files_checked=len(protected_before),
                  partition_index_sha256=index_hash,
                  protected_files_before_sha256=_digest(protected_before),
                  protected_files_after_sha256=_digest(protected_after),
                  non_element_payload_before_sha256=_digest(payload_before),
                  non_element_payload_after_sha256=_digest(payload_after),
                  unchanged=["NPZ bytes", "relation artifact bytes", "assignments", "proposals",
                             "all result fields outside extensions.training_v1.elements"],
                  changes="Only explicit support, effective support, units and availability metadata",
                  idempotent=True)
    write_json(output / "export-contract-audit.json", report)
    return report
