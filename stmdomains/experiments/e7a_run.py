"""Bounded E7a replay/partition experiment in netcat, without training or inference."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import shutil
import sys
import time

from threadpoolctl import threadpool_limits

from .bundle import file_hash, write_json
from .e7_run import protect_evaluation_reads
from .e7a_predict import predict_all, RULES

REPO = Path(__file__).resolve().parents[2]


def verify_e7(source):
    prior = json.loads((REPO / 'docs/stmdomains/ml-ae-rvae-e7-manifest.json').read_text())
    for name, expected in prior['files'].items():
        if file_hash(source / name) != expected:
            raise ValueError(f'E7 versioned source changed: {name}')
    freeze = json.loads((source / 'prediction-freeze.json').read_text())
    for name, expected in freeze['files'].items():
        if file_hash(source / name) != expected:
            raise ValueError(f'E7 frozen source changed: {name}')
    for checkpoint in prior['checkpoint_lineage'].values():
        path = Path(prior['run']['source']) / checkpoint['checkpoint']
        if file_hash(path) != checkpoint['checkpoint_sha256']:
            raise ValueError('Original encoder checkpoint changed')
    return dict(versioned_files=len(prior['files']), frozen_files=len(freeze['files']),
                checkpoints=len(prior['checkpoint_lineage']), freeze_sha256=file_hash(source / 'prediction-freeze.json'))


def budget():
    if time.process_time() > 600 or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > 8 * 1024**2:
        raise RuntimeError('E7a resource budget exceeded')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if '/envs/netcat/' not in sys.executable:
        raise RuntimeError('Use netcat')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = REPO / '.scratch/ml-e7-20261111'
    resource.setrlimit(resource.RLIMIT_CPU, (600, 610))
    started, cpu = time.monotonic(), time.process_time()
    protocol = REPO / 'docs/stmdomains/ml-ae-rvae-e7a-protocol.md'
    modules = sorted(Path(__file__).parent.glob('*.py')) + sorted((Path(__file__).parent / 'training').glob('*.py'))
    for path in modules:
        target = out / 'code' / path.relative_to(REPO)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    shutil.copyfile(protocol, out / 'protocol.md')
    manifest = dict(status='running', schema='stmdomains-e7a-run-v1', base_commit='f807216',
        started_utc=datetime.now(timezone.utc).isoformat(), python=sys.executable,
        source=str(source), output=str(out), protocol_sha256=file_hash(protocol),
        code_sha256={str(p.relative_to(REPO)): file_hash(p) for p in modules},
        fitting=False, encoder_inference=False, independent_test=False, rules=RULES)
    write_json(out / 'manifest.json', manifest)
    guard = None
    try:
        manifest['source_audit_before'] = verify_e7(source)
        guard = protect_evaluation_reads()
        with threadpool_limits(limits=1):
            source_index = json.loads((source / 'prediction-index.json').read_text())
            if len(source_index) != 840:
                raise ValueError('Unexpected E7 matrix')
            index, files = predict_all(source, out, source_index, budget)
            write_json(out / 'prediction-freeze.json', dict(files=files, reference_guard=dict(guard),
                source_freeze_sha256=manifest['source_audit_before']['freeze_sha256'],
                protocol_sha256=file_hash(protocol), created_utc=datetime.now(timezone.utc).isoformat()))
            guard['protected'] = False
            for name, expected in files.items():
                if file_hash(out / name) != expected:
                    raise ValueError('New prediction changed before evaluation')
            from .e7a_evaluate import evaluate
            manifest.update(evaluate(source, out, index, budget))
        manifest['source_audit_after'] = verify_e7(source)
        budget()
        size = sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
        if size > 2 * 1024**3:
            raise RuntimeError('E7a artifact budget exceeded')
        manifest.update(status='completed', artifact_bytes=size, sources_unchanged=True)
    finally:
        if guard is not None:
            guard['protected'] = False
        if manifest['status'] == 'running':
            manifest['status'] = 'failed'
        manifest.update(wall_seconds=time.monotonic()-started, cpu_seconds=time.process_time()-cpu,
                        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        write_json(out / 'manifest.json', manifest)
        print(json.dumps({k: v for k, v in manifest.items() if k != 'code_sha256'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
