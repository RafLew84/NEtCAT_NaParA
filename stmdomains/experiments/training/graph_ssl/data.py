"""Label-free, bounded ego graphs for the throwaway issue-24 trial.

Each annotated center is one root. Every feature and every graph edge is
computed inside its finite 72x72 reference-pixel crop. No full-frame descriptor
is imported into a crop. Node positions are retained for auditing, never as
additional encoder input. The root is always padded-node index zero.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile
import time

import numpy as np

from ...bundle import file_hash, load_sample, write_arrays, write_json
from ..data import SPLIT_SPEC, support_available, transfer_membership
from . import controls


SUPPORT_SIZE = 72.
MAX_NODES = 128
FEATURE_DIM = 57
CONFIG = dict(
    support_reference_px=SUPPORT_SIZE, maximum_nodes=MAX_NODES,
    augmentation_context_margin_reference_px=0., root_index=0,
    histogram=dict(radial_centers_reference_px=[6., 12., 18., 24.], radial_sigma=3.,
                   angle_centers_radians=(np.arange(12) * (2 * np.pi / 12)).tolist(),
                   angle_sigma_radians=float(np.pi / 12), radius_reference_px=24.,
                   aggregation="sum; no per-node count, length or histogram normalization"),
    feature_layout=dict(polar_histogram=[0, 48], nearest_distances_divided_by_24=[48, 52],
                        neighbor_count_divided_by_10=52, nearest_presence=[53, 57]),
    adjacency="distance <= min(24, 1.65*median(positive nearest neighbor within ego)); includes self loops",
    duplicate_policy="Exclude self only from descriptors; duplicate nodes remain. Exact zero distances are excluded only from adjacency radius calibration.",
    overflow_policy="Entire root unavailable; no truncation or density-dependent subsampling",
    crop_boundary_policy="Closed 72x72 reference box; all descriptors and adjacency computed after cropping",
    graph_input="x, binary adjacency and valid padding mask only; no positions, edge vectors, sample IDs or labels",
    intensity_policy="No image intensity enters graph descriptors or training",
    split_policy="All finite crop support inside measured field and existing issue20 guarded expanded-coordinate band",
)


def descriptor(points: np.ndarray) -> np.ndarray:
    """The 57 raw geometry features for every node in one bounded ego graph."""
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
        raise ValueError("Expected finite reference-coordinate nodes")
    count = len(points)
    result = np.zeros((count, FEATURE_DIM), np.float32)
    if not count:
        return result
    delta = points[None, :, :] - points[:, None, :]
    distance = np.linalg.norm(delta, axis=2)
    neighbors = ~np.eye(count, dtype=bool) & (distance <= 24. + 1e-10)
    theta = np.arctan2(delta[:, :, 1], delta[:, :, 0])
    radial = np.exp(-.5 * ((distance[:, :, None] - np.array([6., 12., 18., 24.])) / 3.) ** 2)
    angular_delta = theta[:, :, None] - np.arange(12) * (2 * np.pi / 12)
    angular_delta = (angular_delta + np.pi) % (2 * np.pi) - np.pi
    angular = np.exp(-.5 * (angular_delta / (np.pi / 12)) ** 2)
    hist = np.einsum("ij,ijr,ija->ira", neighbors, radial, angular)
    result[:, :48] = hist.reshape(count, 48)
    for index in range(count):
        near = np.sort(distance[index, neighbors[index]])[:4]
        result[index, 48:48 + len(near)] = near / 24.
        result[index, 53:53 + len(near)] = 1.
    result[:, 52] = neighbors.sum(1) / 10.
    return result


def adjacency(points: np.ndarray) -> tuple[np.ndarray, float]:
    points = np.asarray(points, dtype=np.float64)
    count = len(points)
    distance = np.linalg.norm(points[None, :, :] - points[:, None, :], axis=2)
    positive = np.where(distance > 1e-10, distance, np.inf)
    nearest = positive.min(1) if count else np.empty(0)
    finite = nearest[np.isfinite(nearest)]
    radius = min(24., 1.65 * float(np.median(finite))) if len(finite) else 24.
    return distance <= radius + 1e-10, radius


def prepare_sample(record: dict, arrays: dict) -> tuple[dict, list[dict]]:
    xyraw = np.asarray(arrays["centers_xy"], dtype=np.float64)
    spacing = np.asarray(record["pixel_spacing_xy"], dtype=np.float64)
    if spacing.shape != (2,) or not np.isfinite(spacing).all() or np.any(spacing <= 0):
        raise ValueError("Invalid reference-pixel spacing")
    xyref = xyraw * spacing
    ids = arrays["object_ids"].astype("U64")
    count = len(ids)
    packed = dict(
        x=np.zeros((count, MAX_NODES, FEATURE_DIM), np.float32),
        adj=np.zeros((count, MAX_NODES, MAX_NODES), bool),
        valid=np.zeros((count, MAX_NODES), bool),
        node_indices=np.full((count, MAX_NODES), -1, np.int32),
        eligible=np.zeros(count, bool), xyref=xyref, xyraw=xyraw, ids=ids,
        split=np.full(count, "excluded", dtype="U12"),
        adjacency_radius=np.full(count, np.nan, np.float64),
        node_count=np.zeros(count, np.int32),
    )
    rows = []
    for index, (ident, center) in enumerate(zip(ids, xyraw)):
        half = SUPPORT_SIZE / 2 / spacing
        support = np.r_[center - half, center + half]
        measured = support_available(support, arrays["measured"])
        candidates = np.flatnonzero(np.all(np.abs(xyref - xyref[index]) <= SUPPORT_SIZE / 2 + 1e-10, axis=1))
        others = sorted((int(node) for node in candidates if node != index), key=lambda node: str(ids[node]))
        nodes = np.asarray([index, *others], dtype=np.int32)
        node_count = len(nodes)
        available = measured and node_count <= MAX_NODES
        reason = None if available else ("incomplete_measured_support" if not measured else "ego_node_overflow")
        membership, exclusion = (transfer_membership(record, support) if record["kind"] == "measurement" else (None, None))
        if not available:
            membership, exclusion = None, reason
        packed["node_count"][index] = node_count
        if available:
            points = xyref[nodes]
            features = descriptor(points)
            adjacent, radius = adjacency(points)
            packed["x"][index, :node_count] = features
            packed["adj"][index, :node_count, :node_count] = adjacent
            packed["valid"][index, :node_count] = True
            packed["node_indices"][index, :node_count] = nodes
            packed["eligible"][index] = True
            packed["adjacency_radius"][index] = radius
        if membership:
            packed["split"][index] = membership
        origin = np.asarray(record.get("origin_in_expanded_xy", [0., 0.]), dtype=float)
        rows.append(dict(
            window_id=f'{record["sample_id"]}/centers/{ident}/s72',
            sample_id=record["sample_id"], element_id=str(ident), sampler="centers",
            raw_edge_xy=center.tolist(), reference_xy=xyref[index].tolist(),
            scale_px=72, scale_raw_px=72 if np.array_equal(spacing, [1., 1.]) else None,
            feature_support_xyxy=support.tolist(), support_xyxy=support.tolist(),
            effective_support_xyxy=support.tolist(),
            expanded_support_xyxy=(support + np.tile(origin, 2)).tolist(),
            available=bool(available), availability="available" if available else "unavailable",
            unavailable_reason=reason, transfer_split=membership,
            transfer_exclusion_reason=exclusion,
            transductive_split="fit" if available else None,
            frame_number=record.get("frame_number"), root_index=0,
            observed_ego_nodes=node_count,
            units=dict(raw_edge_xy="raw_px", reference_xy=record["position_unit"],
                       support_xyxy="raw_px", effective_support_xyxy="raw_px", scale_px=record["position_unit"])))
    return packed, rows


def prepare(data_root: Path, output: Path) -> dict:
    """Cache immutable, label-free graphs; output may already contain a plan."""
    data_root, output = Path(data_root).resolve(), Path(output).resolve()
    destination = output / "prepared"
    if destination.exists():
        raise FileExistsError(f"Prepared graphs already exist: {destination}")
    output.mkdir(parents=True, exist_ok=True)
    control_directory = output / "controls"
    if not control_directory.exists():
        controls.prepare(control_directory)
    started = time.perf_counter()
    sources = [data_root / "analysis", control_directory / "analysis"]
    records, counts = [], Counter()
    with tempfile.TemporaryDirectory(prefix=".graph24-data-", dir=output) as temporary:
        staging = Path(temporary) / "prepared"
        staging.mkdir()
        for source in sources:
            manifest = json.loads((source / "manifest.json").read_text())
            for item in manifest["samples"]:
                if source == sources[0] and item["kind"] != "measurement":
                    continue
                record, arrays = load_sample(source, item["sample_id"])
                packed, rows = prepare_sample(record, arrays)
                relative = f'samples/{record["sample_id"]}.npz'
                row_relative = f'rows/{record["sample_id"]}.json'
                hashes = write_arrays(staging / relative, packed)
                write_json(staging / row_relative, rows)
                records.append(dict(record=record, sample_id=record["sample_id"], kind=record["kind"],
                                    source_analysis=str(source), source_manifest_sha256=file_hash(source / "manifest.json"),
                                    cache_file=relative, rows_file=row_relative,
                                    rows_sha256=file_hash(staging / row_relative), **hashes))
                counts[f'{record["kind"]}/anchors'] += len(rows)
                counts[f'{record["kind"]}/eligible'] += int(packed["eligible"].sum())
                for row in rows:
                    counts[f'{record["kind"]}/{row["transfer_split"] or "excluded"}'] += 1
                    if not row["available"]:
                        counts[f'{record["kind"]}/{row["unavailable_reason"]}'] += 1
        source_hashes = {str(Path(__file__).resolve()): file_hash(Path(__file__)),
                         str(Path(controls.__file__).resolve()): file_hash(Path(controls.__file__))}
        manifest = dict(schema="stmdomains-graph24-prepared-v1", config=CONFIG, samples=records,
                        split_spec=SPLIT_SPEC, source_split_sha256=file_hash(data_root / "split.json"),
                        source_preparation_sha256=file_hash(data_root / "manifest.json"),
                        source_sha256=source_hashes, counts=dict(counts),
                        total_samples=len(records), reference_access=False,
                        preparation_wall_seconds=time.perf_counter() - started)
        write_json(staging / "manifest.json", manifest)
        staging.rename(destination)
    return manifest


def _prepared_root(root: Path) -> Path:
    root = Path(root)
    return root / "prepared" if (root / "prepared/manifest.json").exists() else root


def iter_prepared(root: Path, *, kind: str | None = None):
    """Yield one verified sample at a time, without retaining the full cache."""
    root = _prepared_root(root)
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest["schema"] != "stmdomains-graph24-prepared-v1" or manifest["config"] != CONFIG:
        raise ValueError("Prepared graph schema or feature protocol differs")
    for row in manifest["samples"]:
        if kind is not None and row["kind"] != kind:
            continue
        path = root / row["cache_file"]
        if file_hash(path) != row["sha256"] or file_hash(root / row["rows_file"]) != row["rows_sha256"]:
            raise ValueError("Prepared graph artifact changed")
        with np.load(path, allow_pickle=False) as archive:
            packed = {name: archive[name] for name in archive.files}
        record, arrays = load_sample(Path(row["source_analysis"]), row["sample_id"])
        yield dict(record=record, sample_id=row["sample_id"], kind=row["kind"], arrays=arrays,
                   rows=json.loads((root / row["rows_file"]).read_text()), **packed)


def load_prepared(root: Path, *, kind: str | None = None) -> list[dict]:
    return list(iter_prepared(root, kind=kind))


def load_training_graphs(root: Path, regime: str, split: str) -> list[dict]:
    if regime not in {"transfer", "transductive"} or split not in {"train", "validation", "test"}:
        raise ValueError("Unknown graph training scope")
    graphs = []
    for sample in iter_prepared(root, kind="measurement"):
        for index, row in enumerate(sample["rows"]):
            if not sample["eligible"][index]:
                continue
            selected = (row["transfer_split"] == split if regime == "transfer" else split == "train")
            if selected:
                graphs.append(dict(x=sample["x"][index], adj=sample["adj"][index], valid=sample["valid"][index],
                                   root_index=0, sample_id=sample["sample_id"], frame_id=row["frame_number"],
                                   element_id=row["element_id"], graph_id=row["window_id"],
                                   split=split))
    return graphs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path(".scratch/training-20/data"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.data_root, args.output)
    print(json.dumps(dict(samples=result["total_samples"], counts=result["counts"])))


if __name__ == "__main__":
    main()
