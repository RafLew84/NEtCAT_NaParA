"""Execute the predeclared E3 CPU experiment with existing weights in netcat."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time

import numpy as np
import torch
from threadpoolctl import threadpool_limits

from .bundle import file_hash, write_json
from .e2_features import FeatureBank
from .e2_run import verify_sources
from .e3_pipeline import generate, load_adapters

REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / 'docs/stmdomains/ml-ae-rvae-e3-protocol.md'


def budget():
    if time.process_time() > 3600: raise RuntimeError('E3 CPU budget: 60 minutes')
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > 8 * 1024**2:
        raise RuntimeError('E3 RSS budget: 8 GiB')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if '/envs/netcat/' not in sys.executable: raise RuntimeError('Use netcat')
    out = args.out.resolve()
    if out.exists(): raise FileExistsError('Preserve earlier attempts; choose fresh output')
    out.mkdir(parents=True)
    resource.setrlimit(resource.RLIMIT_CPU, (3600, 3610))
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    started, cpu = time.monotonic(), time.process_time()
    source, e1, e2 = [REPO / '.scratch' / name for name in ('autoencoder-21', 'ml-e1-20261110', 'ml-e2-20261110')]
    prior = json.loads((REPO / 'docs/stmdomains/ml-ae-rvae-e2-manifest.json').read_text())
    for name in ('prediction-freeze.json', 'prediction-index.json'):
        expected = prior['files'].get(name)
        if expected is not None and file_hash(e2 / name) != expected: raise ValueError('E2 provenance changed')
    modules = list(Path(__file__).parent.glob('e3_*.py'))
    modules += [Path(__file__).parent / f'e2_{name}.py' for name in ('features', 'pipeline', 'metrics')]
    modules += [Path(__file__).parent / 'training' / f'{name}.py' for name in ('models', 'data', 'checkpoint', 'texture', 'partition', 'evaluate')]
    for p in modules:
        target = out / 'code' / p.relative_to(REPO); target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, target)
    shutil.copyfile(PROTOCOL, out / 'protocol.md')
    manifest = dict(schema='stmdomains-e3-run-v1', status='running', base_commit='ed4762b',
        source=str(source), e1=str(e1), e2=str(e2), output=str(out), python=sys.executable,
        numpy=np.__version__, torch=torch.__version__, device='cpu', threads=1,
        cuda_available=torch.cuda.is_available(), started_utc=datetime.now(timezone.utc).isoformat(),
        protocol_sha256=file_hash(PROTOCOL), code_sha256={str(p.relative_to(REPO)): file_hash(p) for p in modules},
        e2_freeze_sha256=file_hash(e2 / 'prediction-freeze.json'), encoder_training=False,
        encoder_inference=True, adapter_refit=False, source_writes=False)
    write_json(out / 'manifest.json', manifest)
    try:
        with threadpool_limits(limits=1):
            bank = FeatureBank(source, e1)
            index, files, gradients = generate(bank, e2, out, budget)
            from .e3_probe import run_probe
            adapters, _ = load_adapters(bank, e2, out)
            files.update(run_probe(bank, adapters, gradients, out, budget))
            write_json(out / 'source-reader-audit.json', bank.audit())
            files['source-reader-audit.json'] = file_hash(out / 'source-reader-audit.json')
            write_json(out / 'prediction-freeze.json', dict(files=files, protocol_sha256=file_hash(PROTOCOL),
                truth_opened_for_this_run=False, historical_development_data_already_known=True,
                created_utc=datetime.now(timezone.utc).isoformat()))
            from .e3_evaluate import evaluate
            counts = evaluate(bank, out, index, files, gradients, budget)
            verify_sources(bank)
        budget()
        artifact_bytes = sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
        if artifact_bytes > 8 * 1024**3: raise RuntimeError('E3 artifact budget: 8 GiB')
        manifest.update(status='completed', sources_unchanged=True, groups=len(index),
                        artifact_bytes=artifact_bytes, **counts)
    finally:
        if manifest['status'] == 'running': manifest['status'] = 'failed'
        manifest.update(wall_seconds=time.monotonic()-started, cpu_seconds=time.process_time()-cpu,
                        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        write_json(out / 'manifest.json', manifest)
        print(json.dumps(manifest, ensure_ascii=False), flush=True)


if __name__ == '__main__': main()
