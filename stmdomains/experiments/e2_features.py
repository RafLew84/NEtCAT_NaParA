"""Frozen E2 readouts and historical-training-only feature adapters.

Reads issue21 and E1 artifacts; never writes either tree, runs an encoder, or
opens reference labels. Baseline arrays/adapters are returned unchanged. New
adapters use the old FFT adapter's exact sampler-specific training membership.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np

from .bundle import file_hash
from .e1_inputs import Inputs, REGIMES, SAMPLERS, SEEDS
from .training.partition import fit_feature_adapter, neighbor_edges


def readout_runs() -> list[dict]:
    result = []
    for regime in REGIMES:
        for family in ("ae", "rvae_full", "rvae_content", "rvae_angle"):
            source_family = "ae" if family == "ae" else "rvae"
            for seed in SEEDS:
                result.append(dict(run_id=f"{regime}/{family}/z32/seed-{seed}",
                                   regime=regime, family=family, seed=seed,
                                   source_run_id=f"{regime}/{source_family}/z32/seed-{seed}",
                                   baseline=family in ("ae", "rvae_full")))
        for family in ("fft", "photometry", "geometry"):
            result.append(dict(run_id=f"{regime}/{family}", regime=regime,
                               family=family, seed=None,
                               source_run_id=f"{regime}/fft" if family == "fft" else None,
                               baseline=family == "fft"))
    return result


def photometry_features(cache: dict, count: int) -> np.ndarray:
    """Constant anchor, mean and population std of frozen normalized64 inputs."""
    indices, patches = cache["available_indices"], cache["patches"]
    if (indices.ndim != 1 or indices.dtype.kind not in "iu"
            or patches.shape != (len(indices), 64, 64)
            or np.any(indices < 0) or np.any(indices >= count)
            or len(np.unique(indices)) != len(indices)):
        raise ValueError("Invalid photometry cache alignment")
    result = np.full((count, 3), np.nan)
    pixels = patches.astype(np.float64)
    result[indices] = np.column_stack((np.ones(len(indices)), pixels.mean((1, 2)),
                                      pixels.std((1, 2))))
    return result


def geometry_features(description: dict) -> np.ndarray:
    """Eight diagnostics invariant to ACF-vector sign and pair permutation.

    ACF displacement axes are axial by construction, unlike the rVAE pose.
    Even angular moments describe the unordered pair without calling either
    vector a validated primitive lattice vector or physical molecular angle.
    Missing axes remain unavailable; no imputation or order threshold is used.
    """
    vectors = np.asarray(description["basis_vectors"], float)
    count = len(description["acf_score"])
    if vectors.shape != (count, 2, 2):
        raise ValueError("ACF basis vectors must have shape N-by-2-by-2")
    lengths = np.linalg.norm(vectors, axis=2)
    valid = (np.asarray(description["available"], bool)
             & np.asarray(description["valid"], bool)
             & np.isfinite(vectors).all((1, 2)) & (lengths > 0).all(1)
             & np.isfinite(description["acf_score"])
             & np.isfinite(description["second_direction_ratio"]))
    result = np.full((count, 8), np.nan)
    phi = np.arctan2(vectors[valid, :, 1], vectors[valid, :, 0])
    result[valid] = np.column_stack((
        np.cos(2 * phi).mean(1), np.sin(2 * phi).mean(1),
        np.cos(4 * phi).mean(1), np.sin(4 * phi).mean(1),
        np.sort(lengths[valid], axis=1) / 48,
        np.asarray(description["acf_score"])[valid],
        np.asarray(description["second_direction_ratio"])[valid],
    ))
    return result


class FeatureBank:
    """Verified lazy readouts; all public array outputs are read-only.

    ``run`` accepts a member of ``runs`` or its run_id. ``group`` accepts an
    Inputs group/entry/group_id. training_graph() exposes historical fit IDs,
    within-frame edges and segments linking those rows to cached group arrays.
    audit() returns serializable provenance and performs no writes.
    """

    def __init__(self, source_root, e1_root):
        self.inputs = Inputs(source_root, e1_root)
        self.runs = readout_runs()
        self._runs = {run["run_id"]: run for run in self.runs}
        self._features, self._adapters, self._graphs = {}, {}, {}
        self._descriptor_hashes = {}
        self._fit_audits = {}
        self._provenance = self.inputs.verify_provenance()
        self._e1_audit_hash = file_hash(self.inputs.output_root / "input-audit.json")

    def _run(self, run):
        key = run if isinstance(run, str) else run["run_id"]
        if key not in self._runs:
            raise ValueError(f"Unknown E2 readout: {key}")
        if isinstance(run, dict) and run != self._runs[key]:
            raise ValueError("Readout metadata differs from its frozen specification")
        return self._runs[key]

    def features(self, run, group) -> np.ndarray:
        run, group = self._run(run), self.inputs.group(group)
        key = (run["run_id"], group["group_id"])
        if key in self._features:
            return self._features[key]
        family, regime = run["family"], run["regime"]
        rows = self.inputs.rows(group)
        if family in ("fft", "photometry"):
            cache = self.inputs.load_npz(f"cache/{group['group_id']}/{regime}.npz")
            if not np.array_equal(cache["available_indices"],
                                  np.flatnonzero([row["available"] for row in rows])):
                raise ValueError("Patch cache differs from row availability")
            values = cache["fft"] if family == "fft" else photometry_features(cache, len(rows))
        elif family == "geometry":
            description = self.inputs.descriptor(group, regime)
            relative = f"descriptors/{group['group_id']}/{regime}.npz"
            self._descriptor_hashes[relative] = self.inputs.descriptor_records[relative]["sha256"]
            values = geometry_features(description)
        else:
            archive = self.inputs.load_npz(f"features/{run['source_run_id']}/{group['group_id']}.npz")
            if family in ("ae", "rvae_full"):
                values = archive["features"]
            elif family == "rvae_content":
                values = archive["content"]
            else:
                theta = archive["angle_radians"]
                values = np.column_stack((np.cos(theta), np.sin(theta)))
        dimensions = dict(ae=32, rvae_full=34, rvae_content=32, rvae_angle=2,
                          fft=216, photometry=3, geometry=8)
        if values.shape != (len(rows), dimensions[family]):
            raise ValueError("Feature shape differs from its E2 specification")
        values.setflags(write=False)
        self._features[key] = values
        return values

    def training_graph(self, regime: str, sampler: str) -> dict:
        """Exact old fit membership/row order, rebuilding only its training graph."""
        if regime not in REGIMES or sampler not in SAMPLERS:
            raise ValueError("Unknown adapter scope")
        key = (regime, sampler)
        if key in self._graphs:
            return self._graphs[key]
        relative = f"predictions/{regime}/fft/{sampler}/s48/adapter.json"
        original = self.inputs.read_json(relative)
        expected = original["fit_window_ids"]
        if len(set(expected)) != len(expected):
            raise ValueError("Repeated historical fit window ID")
        segments, ids, edges = [], [], []
        for group in self.inputs.groups.values():
            if group["sampler"] != sampler or group["record"]["kind"] != "measurement":
                continue
            rows = self.inputs.rows(group)
            selected = np.array([i for i, row in enumerate(rows) if row["available"]
                                 and (regime == "transductive" or row["transfer_split"] == "train")], dtype=np.int64)
            if not len(selected):
                continue
            local_ids = [rows[i]["window_id"] for i in selected]
            xy = np.array([rows[i]["raw_edge_xy"] for i in selected])
            local_edges = neighbor_edges(xy, local_ids, mode=sampler, stride=16.)
            start = len(ids)
            edges.extend((local_edges + start).tolist())
            ids.extend(local_ids)
            selected.setflags(write=False)
            segments.append(dict(group_id=group["group_id"], row_indices=selected,
                                 start=start, stop=len(ids)))
        digest = hashlib.sha256(json.dumps(sorted(ids)).encode()).hexdigest()
        if (ids != expected or digest != original["training_ids_sha256"]
                or len(ids) != original["training_elements"]
                or len(edges) != original["valid_training_edges"]):
            raise ValueError("Rebuilt training graph differs from historical FFT fit")
        pairs = np.asarray(edges, dtype=np.int64).reshape(-1, 2)
        pairs.setflags(write=False)
        graph = dict(window_ids=tuple(ids), edges=pairs, segments=tuple(segments),
                     membership_source=relative, training_ids_sha256=digest)
        self._graphs[key] = graph
        return graph

    def adapter(self, run, sampler: str) -> dict:
        run = self._run(run)
        key = (run["run_id"], sampler)
        if key in self._adapters:
            return self._adapters[key]
        graph = self.training_graph(run["regime"], sampler)
        if run["baseline"]:
            relative = f"predictions/{run['source_run_id']}/{sampler}/s48/adapter.json"
            adapter = self.inputs.read_json(relative)
            if (adapter["fit_window_ids"] != list(graph["window_ids"])
                    or adapter["training_ids_sha256"] != graph["training_ids_sha256"]):
                raise ValueError("Baseline adapter used different training membership")
            audit = dict(reused_exact=True, source=relative)
        else:
            chunks = [self.features(run, segment["group_id"])[segment["row_indices"]]
                      for segment in graph["segments"]]
            adapter = fit_feature_adapter(np.concatenate(chunks), graph["edges"],
                                          graph["window_ids"], scope=dict(
                                              regime=run["regime"], sampler=sampler,
                                              scale_px=48, feature_id=run["run_id"]))
            adapter["fit_window_ids"] = list(graph["window_ids"])
            audit = dict(reused_exact=False, membership_source=graph["membership_source"])
        audit.update(training_ids_sha256=graph["training_ids_sha256"],
                     training_elements=len(graph["window_ids"]),
                     training_edges=len(graph["edges"]),
                     valid_training_elements=adapter["valid_training_elements"],
                     valid_training_edges=adapter["valid_training_edges"])
        self._fit_audits[f"{run['run_id']}/{sampler}"] = audit
        self._adapters[key] = adapter
        return adapter

    def audit(self) -> dict:
        """No writes; distinguish this process's verified reads from inherited E1."""
        verified = {name: self.inputs.source_hashes[name]
                    for name in self.inputs._verified_stats}
        return deepcopy(dict(
            schema="stmdomains-e2-feature-bank-v1", runs=self.runs,
            source_root=str(self.inputs.source_root), e1_root=str(self.inputs.output_root),
            source_freeze_sha256=self.inputs.freeze_hash,
            source_hashes=dict(sorted(verified.items())),
            inherited_e1_source_hashes=self.inputs.source_hashes,
            e1_input_audit_sha256=self._e1_audit_hash,
            e1_descriptor_hashes=dict(sorted(self._descriptor_hashes.items())),
            checkpoint_lineage=self._provenance,
            external_hashes=self.inputs.external_hashes, adapters=self._fit_audits,
            feature_arrays_read=len(self._features), code_sha256=file_hash(Path(__file__)),
            no_encoder_inference=True, no_encoder_training=True,
            helper_no_truth_access=True, writes_source_or_e1=False,
            photometry="[1,mean,std(ddof=0)] of normalized resized64 cache; no extra scaler",
            geometry="mean cos2/sin2/cos4/sin4 of two ACF axes, sorted lengths/48, ACF score, spectral ratio; missing stays NaN",
            fit_policy="exact original sampler-specific FFT adapter IDs; transfer train only, transductive all available real fields",
        ))
