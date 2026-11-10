"""Verified issue-21 inputs and native-patch gate diagnostics for E1.

This helper reads frozen models/results as provenance, never performs model
inference, fits an adapter, calibrates a threshold, or reads evaluation truth.
New files are confined to a separate E1 output directory. Call preparation only
after freezing the E1 protocol; constructing Inputs alone does not prepare data.
"""
from __future__ import annotations

from pathlib import Path
import platform
import sys

import numpy as np
import scipy

from .bundle import file_hash, load_sample, write_json
from .training.data import extract_patch, synthetic_in_normalizer_units
from .training.predict import read_json
from .training.texture import describe_patches, order_mask

REGIMES = ("transfer", "transductive")
SAMPLERS = ("grid", "centers")
SEEDS = (20261101, 20261102, 20261103)
ACF_RTOL = 1e-12
ACF_ATOL = 1e-14


def _selected(entry: dict) -> bool:
    return (entry["scale_px"] == 48 and entry["sampler"] in SAMPLERS
            and entry["regime"] in REGIMES and entry["partition"] in ("fh4", "mws")
            and (entry["family"] == "fft" or
                 (entry["family"] in ("ae", "rvae") and entry["latent"] == 32
                  and entry["seed"] in SEEDS)))


def _within(root: Path, relative: str | Path) -> Path:
    relative = Path(relative)
    path = (root / relative).resolve()
    if relative.is_absolute() or not path.is_relative_to(root):
        raise ValueError(f"Path escapes its declared root: {relative}")
    return path


def _readonly(arrays: dict) -> dict:
    for value in arrays.values():
        value.setflags(write=False)
    return arrays


def _check_close(actual: np.ndarray, expected: np.ndarray, name: str) -> float:
    if actual.shape != expected.shape or not np.allclose(
            actual, expected, rtol=ACF_RTOL, atol=ACF_ATOL, equal_nan=True):
        raise ValueError(f"Recomputed {name} differs from the frozen cache")
    finite = np.isfinite(actual) & np.isfinite(expected)
    return float(np.max(np.abs(actual[finite] - expected[finite]))) if finite.any() else 0.


def native_descriptor(arrays: dict, rows: list[dict], normalizer: dict,
                      cache: dict, threshold: float, *, synthetic: bool) -> tuple[dict, dict]:
    """Recreate the original native48 calculation, preserving all planned rows.

    Cached 64x64 encoder inputs must not be resized back to48: that would add an
    interpolation absent from the original texture calculation. Unavailable rows
    remain NaN/False; finite flat measurements remain valid with zero energy.
    """
    available = np.asarray([row["available"] for row in rows], dtype=bool)
    indices = np.flatnonzero(available)
    if not np.array_equal(indices, cache["available_indices"]):
        raise ValueError("Cached availability differs from row geometry")
    source = synthetic_in_normalizer_units(arrays, normalizer) if synthetic else arrays
    native = (np.stack([extract_patch(source, rows[i], normalizer, size=48) for i in indices])
              if len(indices) else np.empty((0, 48, 48), np.float32))
    local = describe_patches(native)
    count = len(rows)
    descriptor = {
        "available": available, "valid": np.zeros(count, bool),
        "acf_score": np.full(count, np.nan),
        "second_direction_ratio": np.full(count, np.nan),
        "energy": np.full(count, np.nan),
        "basis_vectors": np.full((count, 2, 2), np.nan),
        "order_pass": np.zeros(count, bool),
    }
    for name in ("valid", "acf_score", "second_direction_ratio", "energy", "basis_vectors"):
        descriptor[name][indices] = local[name]
    descriptor["order_pass"][indices] = order_mask(local, threshold)
    fft = np.full((count, 216), np.nan)
    fft[indices] = local["features"]
    comparison = {
        "acf_max_abs_difference": _check_close(descriptor["acf_score"], cache["acf_score"], "ACF"),
        "fft_max_abs_difference": _check_close(fft, cache["fft"], "FFT"),
        "order_pass_exact": bool(np.array_equal(descriptor["order_pass"], cache["order_pass"])),
        "rows": count, "available": int(available.sum()),
        "passed": int(descriptor["order_pass"].sum()),
    }
    if not comparison["order_pass_exact"]:
        raise ValueError("Recomputed order_pass differs from the frozen cache")
    return descriptor, comparison


class Inputs:
    """Lazy verified source reader plus cached rows/new descriptors for one E1 run.

    `entries` contains selected baseline prediction-index entries; `groups` maps
    cache_group IDs to metadata. rows()/descriptor()/sample() accept either an
    entry, a group, or its group-ID string. A string/group needs an explicit
    regime for descriptor(). Cached arrays are read-only; copy before editing.
    `strict=False` is solely for miniature unit fixtures, never full preparation.
    """

    def __init__(self, source_root: str | Path, output_root: str | Path, *, strict=True):
        self.source_root = Path(source_root).resolve()
        self.output_root = Path(output_root).resolve()
        if (self.output_root.is_relative_to(self.source_root)
                or self.source_root.is_relative_to(self.output_root)):
            raise ValueError("E1 output must be separate from the original artifact tree")
        frozen_path = self.source_root / "frozen-predictions.json"
        self.frozen = read_json(frozen_path)
        self.freeze_hash = file_hash(frozen_path)
        if (self.frozen.get("schema") != "stmdomains-frozen-predictions-v1"
                or self.frozen.get("evaluation_opened") is not False):
            raise ValueError("A valid issue-21 prediction freeze is required")
        self.source_hashes = {"frozen-predictions.json": self.freeze_hash}
        self.external_hashes = {}
        self.descriptor_records = {}
        self.provenance = {}
        self.replay_code_hashes = {}
        self._verified_stats = {}
        self._rows = {}
        self._descriptors = {}
        self._samples = {}
        self._normalizers = None
        self._strict = strict
        audit_path = self.output_root / "input-audit.json"
        if audit_path.exists():
            prior = read_json(audit_path)
            if (prior.get("source_root") != str(self.source_root)
                    or prior.get("source_freeze_sha256") != self.freeze_hash):
                raise ValueError("Existing E1 audit belongs to different frozen inputs")
            self.source_hashes.update(prior.get("source_hashes", {}))
            self.external_hashes.update(prior.get("external_hashes", {}))
            self.descriptor_records.update(prior.get("descriptors", {}))
            self.provenance.update(prior.get("provenance", {}))
        self.entries = [item for item in self.read_json("predictions/index.json") if _selected(item)]
        selected_groups = [group for group in self.read_json("cache/index.json")
                           if group["scale_px"] == 48 and group["sampler"] in SAMPLERS]
        self.groups = {group["group_id"]: group for group in selected_groups}
        if len(self.groups) != len(selected_groups):
            raise ValueError("Repeated s48 cache group")
        self.threshold = float(self.read_json("cache/order-thresholds.json")["scales"]["48"]["threshold"])
        self._check_catalogue(strict)
        if strict:
            self._verify_replay_code()

    def _verify_replay_code(self):
        for function in (extract_patch, describe_patches):
            path = Path(function.__code__.co_filename).resolve()
            suffix = f"stmdomains/experiments/training/{path.name}"
            matches = [expected for name, expected in self.frozen.get("code_sha256", {}).items()
                       if Path(name).as_posix().endswith(suffix)]
            observed = file_hash(path)
            if matches != [observed]:
                raise ValueError(f"Native-patch replay code differs from the frozen implementation: {suffix}")
            self.replay_code_hashes[suffix] = observed

    def _check_catalogue(self, strict):
        keys = [(item["run_id"], item["cache_group"], item["partition"]) for item in self.entries]
        if len(keys) != len(set(keys)) or any(item["cache_group"] not in self.groups for item in self.entries):
            raise ValueError("Duplicate predictions or unknown cache groups")
        if not strict:
            return
        run_ids = {f"{regime}/{family}/z32/seed-{seed}"
                   for regime in REGIMES for family in ("ae", "rvae") for seed in SEEDS}
        run_ids.update(f"{regime}/fft" for regime in REGIMES)
        expected = {(run, group, method) for run in run_ids for group in self.groups for method in ("fh4", "mws")}
        samples = {group["record"]["sample_id"] for group in self.groups.values()}
        real = {group["record"]["sample_id"] for group in self.groups.values()
                if group["record"]["kind"] == "measurement"}
        if len(self.groups) != 210 or len(samples) != 105 or len(real) != 24 or set(keys) != expected:
            raise ValueError("E1 needs all105 samples, both s48 samplers and14 frozen feature sets")

    def verify(self, relative: str | Path) -> Path:
        """Verify a used source file against the original freeze, without writing."""
        relative = str(Path(relative))
        if relative not in self.frozen["files"]:
            raise ValueError(f"Source file is not in the prediction freeze: {relative}")
        path = _within(self.source_root, relative)
        stat = path.stat()
        signature = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        if self._verified_stats.get(relative) != signature:
            observed = file_hash(path)
            if observed != self.frozen["files"][relative]:
                raise ValueError(f"Frozen source file changed: {relative}")
            self.source_hashes[relative] = observed
            self._verified_stats[relative] = signature
        return path

    def read_json(self, relative: str | Path):
        return read_json(self.verify(relative))

    def load_npz(self, relative: str | Path) -> dict:
        with np.load(self.verify(relative), allow_pickle=False) as archive:
            return _readonly({name: archive[name] for name in archive.files})

    def group(self, value: dict | str) -> dict:
        key = value if isinstance(value, str) else value.get("cache_group", value.get("group_id"))
        return self.groups[key]

    def rows(self, value: dict | str) -> list[dict]:
        key = self.group(value)["group_id"]
        if key not in self._rows:
            self._rows[key] = self.read_json(f"cache/{key}/rows.json.gz")
        return self._rows[key]

    def sample(self, value: dict | str) -> tuple[dict, dict]:
        """Read clean source arrays with hash checks; no reference tree is opened."""
        group = self.group(value)
        analysis = Path(group["analysis"]).resolve()
        sample_id = group["record"]["sample_id"]
        key = (str(analysis), sample_id)
        if key not in self._samples:
            record, arrays = load_sample(analysis, sample_id)
            if record != group["record"]:
                raise ValueError("Source sample metadata differs from the frozen cache index")
            for path in (analysis / "manifest.json", _within(analysis, record["file"])):
                self.external_hashes[str(path)] = file_hash(path)
            self._samples[key] = (record, _readonly(arrays))
        return self._samples[key]

    def _descriptor_relative(self, value, regime=None) -> str:
        group = self.group(value)
        regime = regime or (value.get("regime") if isinstance(value, dict) else None)
        if regime not in REGIMES:
            raise ValueError("A descriptor requires transfer or transductive regime")
        return f"descriptors/{group['group_id']}/{regime}.npz"

    def descriptor(self, value: dict | str, regime: str | None = None) -> dict:
        relative = self._descriptor_relative(value, regime)
        if relative not in self._descriptors:
            record = self.descriptor_records.get(relative)
            if record is None:
                raise ValueError("Descriptor is not prepared/audited; run prepare_descriptors first")
            path = _within(self.output_root, relative)
            if file_hash(path) != record["sha256"]:
                raise ValueError(f"Prepared descriptor changed: {relative}")
            with np.load(path, allow_pickle=False) as archive:
                self._descriptors[relative] = _readonly({key: archive[key] for key in archive.files})
        return self._descriptors[relative]

    def verify_provenance(self) -> dict:
        """Hash selected checkpoint/config/adapter files; never load model weights."""
        runs, adapters, normalizers, normalization_hashes = {}, {}, {}, set()
        for run_id in sorted({item["run_id"] for item in self.entries if item["family"] != "fft"}):
            directory = f"training/{run_id}"
            run = self.read_json(f"{directory}/run.json")
            config_path = self.verify(f"{directory}/config.json")
            config = read_json(config_path)
            checkpoint_relative = f"{directory}/{run['selected_checkpoint']}"
            checkpoint = self.verify(checkpoint_relative)
            if (run["status"] != "completed" or file_hash(checkpoint) != run["selected_checkpoint_sha256"]
                    or file_hash(config_path) != run["config_file_sha256"]):
                raise ValueError("Selected checkpoint/config provenance is inconsistent")
            regime = config["regime"]
            normalizer = config["data"]["normalizer"]
            if regime in normalizers and normalizers[regime] != normalizer:
                raise ValueError("Same-regime models used different normalizers")
            normalizers[regime] = normalizer
            normalization_hashes.add(config["data"]["normalization_sha256"])
            runs[run_id] = {"checkpoint": checkpoint_relative,
                            "checkpoint_sha256": run["selected_checkpoint_sha256"],
                            "selected_step": run["selected_step"],
                            "config": f"{directory}/config.json"}
        normalizer_paths = {Path(group["analysis"]).resolve().parent / "normalization.json"
                            for group in self.groups.values() if group["record"]["kind"] == "measurement"}
        if len(normalization_hashes) != 1 or len(normalizer_paths) != 1:
            raise ValueError("Cannot identify the single frozen preparation normalizer")
        normalizer_path = normalizer_paths.pop()
        observed = file_hash(normalizer_path)
        if observed not in normalization_hashes or read_json(normalizer_path) != normalizers:
            raise ValueError("Original normalizer differs from frozen model configurations")
        self.external_hashes[str(normalizer_path)] = observed
        self._normalizers = normalizers
        adapter_paths = {f"predictions/{item['run_id']}/{item['sampler']}/s48/adapter.json" for item in self.entries}
        for relative in sorted(adapter_paths):
            self.verify(relative)
            adapters[relative] = self.source_hashes[relative]
        self.provenance = {"runs": runs, "adapters": adapters,
                           "normalization_path": str(normalizer_path),
                           "normalization_sha256": observed}
        return self.provenance

    def verify_selected_predictions(self, *, progress_every=1000, check_budget=None):
        """Verify only the metrics, payload and relations used by selected entries."""
        for number, entry in enumerate(self.entries, 1):
            if check_budget is not None and (number == 1 or number % 100 == 0):
                check_budget()
            heldout = entry["kind"] == "measurement" and entry["regime"] == "transfer"
            prefix = "heldout-" if heldout else ""
            if entry["evaluation_input"] != prefix + "metrics-input.npz":
                raise ValueError("Wrong graph context in selected prediction index")
            for filename in (prefix + "metrics-input.npz", prefix + "result.json.gz", prefix + "relations.json.gz"):
                self.verify(f"{entry['directory']}/{filename}")
            if progress_every and (number % progress_every == 0 or number == len(self.entries)):
                print(f"E1 inputs: verified {number}/{len(self.entries)} prediction entries", flush=True)

    def save_audit(self) -> dict:
        """Persist cumulative evidence in the NEW E1 output, including later reads."""
        result = {
            "schema": "stmdomains-e1-input-audit-v1",
            "source_root": str(self.source_root), "output_root": str(self.output_root),
            "source_freeze_sha256": self.freeze_hash,
            "source_hashes": dict(sorted(self.source_hashes.items())),
            "external_hashes": dict(sorted(self.external_hashes.items())),
            "provenance": self.provenance,
            "descriptors": self.descriptor_records,
            "scope": {"prediction_entries": len(self.entries), "groups": len(self.groups),
                      "descriptor_count": len(self.descriptor_records), "strict_catalogue_check": self._strict,
                      "descriptors_complete": len(self.descriptor_records) == 2 * len(self.groups)},
            "threshold": self.threshold, "comparison_rtol": ACF_RTOL, "comparison_atol": ACF_ATOL,
            "environment": {"python": platform.python_version(), "executable": sys.executable,
                            "prefix": sys.prefix, "numpy": np.__version__, "scipy": scipy.__version__},
            "code_sha256": file_hash(Path(__file__)),
            "replay_code_sha256": self.replay_code_hashes,
            "no_model_inference": True, "no_training": True, "helper_no_truth_access": True,
        }
        write_json(self.output_root / "input-audit.json", result)
        return result


def prepare_descriptors(source_root: str | Path, output_root: str | Path,
                        *, progress_every: int = 30, check_budget=None) -> dict:
    """Prepare all420 descriptors after caller's protocol freeze; no automatic retry."""
    if check_budget is not None:
        check_budget()
    inputs = Inputs(source_root, output_root)
    target = inputs.output_root / "descriptors"
    if target.exists():
        raise FileExistsError("Descriptor preparation needs a fresh output/descriptors directory")
    inputs.verify_provenance()
    inputs.verify_selected_predictions(check_budget=check_budget)
    target.mkdir(parents=True)
    inputs.save_audit()
    total = len(inputs.groups) * len(REGIMES)
    number = 0
    for group_id in sorted(inputs.groups):
        group = inputs.groups[group_id]
        rows = inputs.rows(group)
        _, arrays = inputs.sample(group)
        for regime in REGIMES:
            if check_budget is not None:
                check_budget()
            cache = inputs.load_npz(f"cache/{group_id}/{regime}.npz")
            descriptor, comparison = native_descriptor(
                arrays, rows, inputs._normalizers[regime], cache, inputs.threshold,
                synthetic=group["record"]["kind"] == "synthetic")
            relative = inputs._descriptor_relative(group, regime)
            path = _within(inputs.output_root, relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                np.savez_compressed(stream, **descriptor)
            inputs.descriptor_records[relative] = {
                "sha256": file_hash(path), "group_id": group_id, "regime": regime,
                **comparison,
            }
            number += 1
            if progress_every and (number % progress_every == 0 or number == total):
                print(f"E1 inputs: native48 descriptors {number}/{total}", flush=True)
    return inputs.save_audit()
