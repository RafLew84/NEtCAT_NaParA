"""Run the frozen E5 locality protocol in netcat; never train encoders."""
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
import torch
from threadpoolctl import threadpool_limits

from .bundle import file_hash, write_json
from .e2_features import FeatureBank
from .e2_run import verify_sources

REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / 'docs/stmdomains/ml-ae-rvae-e5-protocol.md'


def budget():
    if time.process_time() > 3600: raise RuntimeError('E5 CPU budget: 60 minutes')
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > 8 * 1024**2:
        raise RuntimeError('E5 RSS budget: 8 GiB')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if '/envs/netcat/' not in sys.executable: raise RuntimeError('Use netcat')
    out = args.out.resolve()
    if out.exists(): raise FileExistsError('Preserve earlier attempts; choose fresh output')
    out.mkdir(parents=True)
    resource.setrlimit(resource.RLIMIT_CPU, (3600, 3610))
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    started, cpu = time.monotonic(), time.process_time()
    source, e1, e2 = [REPO / '.scratch' / name for name in
                     ('autoencoder-21', 'ml-e1-20261110', 'ml-e2-20261110')]
    prior = json.loads((REPO / 'docs/stmdomains/ml-ae-rvae-e2-manifest.json').read_text())
    for name in ('prediction-freeze.json', 'prediction-index.json'):
        expected = prior['files'].get(name)
        if expected is not None and file_hash(e2 / name) != expected:
            raise ValueError('E2 provenance changed')
    modules = sorted(Path(__file__).parent.glob('*.py'))
    modules += sorted((Path(__file__).parent / 'training').glob('*.py'))
    for path in modules:
        target = out / 'code' / path.relative_to(REPO)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    shutil.copyfile(PROTOCOL, out / 'protocol.md')
    manifest = dict(schema='stmdomains-e5-run-v1', status='running', base_commit='8168349',
        source=str(source), e1=str(e1), e2=str(e2), output=str(out), python=sys.executable,
        numpy=np.__version__, torch=torch.__version__, device='cpu', threads=1,
        cuda_available=torch.cuda.is_available(), started_utc=datetime.now(timezone.utc).isoformat(),
        protocol_sha256=file_hash(PROTOCOL), code_sha256={str(p.relative_to(REPO)): file_hash(p) for p in modules},
        encoder_training=False, encoder_inference=True, adapter_refit=True,
        adapter_policy='matched historical training IDs with all new footprints inside split', source_writes=False)
    write_json(out / 'manifest.json', manifest)
    try:
        with threadpool_limits(limits=1):
            from .e5_generate import generate
            bank = FeatureBank(source, e1)
            index, files = generate(bank, e2, out, budget)
            write_json(out / 'source-reader-audit.json', bank.audit())
            files['source-reader-audit.json'] = file_hash(out / 'source-reader-audit.json')
            freeze = json.loads((out / 'prediction-freeze.json').read_text())
            freeze.update(files=files, protocol_sha256=file_hash(PROTOCOL),
                truth_opened_for_this_run=False, historical_development_data_already_known=True,
                created_utc=datetime.now(timezone.utc).isoformat())
            write_json(out / 'prediction-freeze.json', freeze)
            from .e5_evaluate import evaluate
            counts = evaluate(bank, out, index, files, budget)
            verify_sources(bank)
        budget()
        artifact_bytes = sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
        if artifact_bytes > 16 * 1024**3: raise RuntimeError('E5 artifact budget: 16 GiB')
        manifest.update(status='completed', sources_unchanged=True, groups=len(index),
                        artifact_bytes=artifact_bytes, **counts)
    finally:
        if manifest['status'] == 'running': manifest['status'] = 'failed'
        manifest.update(wall_seconds=time.monotonic()-started, cpu_seconds=time.process_time()-cpu,
                        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        write_json(out / 'manifest.json', manifest)
        print(json.dumps({k: v for k, v in manifest.items() if k != 'code_sha256'}, ensure_ascii=False), flush=True)


if __name__ == '__main__': main()
