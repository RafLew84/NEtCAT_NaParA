"""Run the bounded E7 synthetic-supervised relation probe in netcat."""
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
import sklearn
import torch
from threadpoolctl import threadpool_limits

from .bundle import file_hash, write_json
from .e2_features import FeatureBank
from .e2_run import verify_sources

REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / 'docs/stmdomains/ml-ae-rvae-e7-protocol.md'


def budget():
    if time.process_time() > 1800: raise RuntimeError('E7 CPU budget: 30 minutes')
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > 8 * 1024**2:
        raise RuntimeError('E7 RSS budget: 8 GiB')


def protect_evaluation_reads():
    """Install after publishing truth; fitting can read only training truth."""
    state = dict(protected=True, blocked=[])
    def audit(event, args):
        if event != 'open' or not isinstance(args[0], (str, bytes)):
            return
        path = args[0].decode() if isinstance(args[0], bytes) else args[0]
        forbidden = any(token in path.replace('\\', '/') for token in
                        ('/evaluation_truth/', '/evaluation/', '/references/', 'manual_domain'))
        if state['protected'] and forbidden:
            state['blocked'].append(path)
            raise PermissionError('Evaluation reference cannot be opened before E7 prediction freeze')
    sys.addaudithook(audit)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if '/envs/netcat/' not in sys.executable: raise RuntimeError('Use netcat')
    out = args.out.resolve()
    if out.exists(): raise FileExistsError('Preserve existing attempts; use a new output directory')
    out.mkdir(parents=True)
    resource.setrlimit(resource.RLIMIT_CPU, (1800, 1810))
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    started, cpu = time.monotonic(), time.process_time()
    modules = sorted(Path(__file__).parent.glob('*.py'))
    modules += sorted((Path(__file__).parent / 'training').glob('*.py'))
    for path in modules:
        target = out / 'code' / path.relative_to(REPO)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    shutil.copyfile(PROTOCOL, out / 'protocol.md')
    source, e1, e2 = [REPO / '.scratch' / n for n in
                     ('autoencoder-21', 'ml-e1-20261110', 'ml-e2-20261110')]
    prior = json.loads((REPO / 'docs/stmdomains/ml-ae-rvae-e2-manifest.json').read_text())
    if file_hash(e2 / 'prediction-freeze.json') != prior['files']['prediction-freeze.json']:
        raise ValueError('E2 freeze provenance changed')
    e2_frozen = json.loads((e2 / 'prediction-freeze.json').read_text())
    if file_hash(e2 / 'prediction-index.json') != e2_frozen['files']['prediction-index.json']:
        raise ValueError('E2 index provenance changed')
    manifest = dict(schema='stmdomains-e7-run-v1', status='running', base_commit='630f29d',
        output=str(out), python=sys.executable, numpy=np.__version__, sklearn=sklearn.__version__,
        torch=torch.__version__, device='cpu', threads=1, cuda_available=torch.cuda.is_available(),
        source=str(source), e1=str(e1), e2=str(e2),
        e2_freeze_sha256=file_hash(e2 / 'prediction-freeze.json'),
        started_utc=datetime.now(timezone.utc).isoformat(), protocol_sha256=file_hash(PROTOCOL),
        code_sha256={str(p.relative_to(REPO)): file_hash(p) for p in modules},
        encoder_training=False, synthetic_supervised_probes=True, real_supervised_training=False,
        independent_stm_test=False, source_writes=False)
    write_json(out / 'manifest.json', manifest)
    guard = None
    try:
        with threadpool_limits(limits=1):
            from .e7_data import prepare_data
            from .e7_features import prepare_features
            from .e7_probe import fit_probes
            from .e7_predict import predict_all
            bank = FeatureBank(source, e1)
            entries, files = prepare_data(bank, out)
            guard = protect_evaluation_reads()
            entries, new_files = prepare_features(bank, out, entries, budget)
            files.update(new_files)
            models, new_files = fit_probes(out, entries, budget)
            files.update(new_files)
            index, new_files = predict_all(bank, e2, out, entries, models, budget)
            files.update(new_files)
            write_json(out / 'source-reader-audit.json', bank.audit())
            files['source-reader-audit.json'] = file_hash(out / 'source-reader-audit.json')
            write_json(out / 'prediction-freeze.json', dict(schema='stmdomains-e7-freeze-v1',
                files=files, models=len(models), entries=len(index),
                protocol_sha256=file_hash(PROTOCOL), validation_or_stm_truth_read_by_predictor=False,
                reference_read_guard=guard, created_utc=datetime.now(timezone.utc).isoformat()))
            guard['protected'] = False
            from .e7_evaluate import evaluate
            counts = evaluate(out, entries, index, files, budget)
            verify_sources(bank)
        budget()
        size = sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
        if size > 8 * 1024**3: raise RuntimeError('E7 artifact budget: 8 GiB')
        manifest.update(status='completed', artifact_bytes=size, sources_unchanged=True,
                        classifier_fits=len(models), **counts)
    finally:
        if guard is not None: guard['protected'] = False
        if manifest['status'] == 'running': manifest['status'] = 'failed'
        manifest.update(wall_seconds=time.monotonic()-started, cpu_seconds=time.process_time()-cpu,
                        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        write_json(out / 'manifest.json', manifest)
        print(json.dumps({k: v for k, v in manifest.items() if k != 'code_sha256'}, ensure_ascii=False), flush=True)


if __name__ == '__main__': main()
