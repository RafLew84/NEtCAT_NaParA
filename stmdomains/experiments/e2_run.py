"""Execute the predeclared E2 readout experiment in netcat, without encoders."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import shutil
import sys
import time

import numpy as np
from threadpoolctl import threadpool_limits

from .bundle import file_hash, write_json
from .e2_features import FeatureBank
from .e2_pipeline import generate
from .e2_evaluate import evaluate

REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / "docs/stmdomains/ml-ae-rvae-e2-protocol.md"


def budget():
    if time.process_time() > 3600:
        raise RuntimeError("E2 CPU limit exceeded (60 minutes)")
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > 8 * 1024**2:
        raise RuntimeError("E2 RSS limit exceeded (8 GiB)")


def verify_sources(bank):
    audit = bank.audit()
    for relative, expected in audit["source_hashes"].items():
        if file_hash(bank.inputs.source_root / relative) != expected:
            raise ValueError(f"Source changed during E2: {relative}")
    for path, expected in audit["external_hashes"].items():
        if file_hash(Path(path)) != expected:
            raise ValueError(f"External source changed during E2: {path}")
    for relative, expected in audit["e1_descriptor_hashes"].items():
        if file_hash(bank.inputs.output_root / relative) != expected:
            raise ValueError(f"E1 descriptor changed: {relative}")
    if file_hash(bank.inputs.output_root / "input-audit.json") != audit["e1_input_audit_sha256"]:
        raise ValueError("E1 input audit changed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=REPO / ".scratch/autoencoder-21")
    parser.add_argument("--e1", type=Path, default=REPO / ".scratch/ml-e1-20261110")
    args = parser.parse_args()
    if "/envs/netcat/" not in sys.executable:
        raise RuntimeError("Use the user's netcat environment")
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError("Preserve previous E2 attempts; use a fresh output")
    out.mkdir(parents=True)
    resource.setrlimit(resource.RLIMIT_CPU, (3600, 3610))
    start, cpu = time.monotonic(), time.process_time()
    shutil.copyfile(PROTOCOL, out / "protocol.md")
    modules = [p for p in Path(__file__).parent.glob("e2_*.py") if p.name != "e2_plots.py"]
    modules += [Path(__file__).parent / f"e1_{name}.py" for name in ("inputs", "mechanics", "run")]
    modules += [Path(__file__).parent / "training" / f"{name}.py"
                for name in ("partition", "evaluate", "predict", "texture", "data")]
    for module in modules:
        target = out / "code" / module.relative_to(REPO)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(module, target)
    manifest = dict(schema="stmdomains-e2-run-v1", status="running", base_commit="6742e13",
        source=str(args.source.resolve()), e1=str(args.e1.resolve()), output=str(out),
        python=sys.executable, numpy=np.__version__, protocol_sha256=file_hash(PROTOCOL),
        started_utc=datetime.now(timezone.utc).isoformat(),
        code_sha256={str(p.relative_to(REPO)): file_hash(p) for p in modules},
        encoder_training=False, encoder_inference=False, adapter_policy="reuse28_fit32_on_original_ids",
        scale_px=48, solver_parameters_changed=False, threads=1)
    write_json(out / "manifest.json", manifest)
    try:
        with threadpool_limits(limits=1):
            bank = FeatureBank(args.source, args.e1)
            index, files = generate(bank, out, budget)
            counts = evaluate(bank, out, index, files, budget)
            verify_sources(bank)
        artifact_bytes = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
        if artifact_bytes > 8 * 1024**3:
            raise RuntimeError("E2 artifact limit exceeded (8 GiB)")
        budget()
        manifest.update(status="completed", baseline_exact=5880, groups=len(index),
                        sources_unchanged=True, artifact_bytes=artifact_bytes, **counts)
    finally:
        if manifest["status"] == "running":
            manifest["status"] = "failed"
        manifest.update(wall_seconds=time.monotonic() - start, cpu_seconds=time.process_time() - cpu,
                        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        write_json(out / "manifest.json", manifest)
        print(json.dumps(manifest, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
