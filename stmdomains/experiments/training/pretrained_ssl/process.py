"""Execute a stage with wait4 accounting, including externally terminated workers.

Runtime logs live in .execution and are excluded from the numerical freeze.
For non-fit stages, charge only CPU not already counted by internal ledgers.
This also includes child-renderer costs reaped by the reporting worker.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

from ...bundle import file_hash, write_json
from .common import Budget, read_json


def run(root, stage, command, *, fit_suite=False, ledger_stages=None):
    root = Path(root).resolve()
    logdir = root / '.execution'
    logdir.mkdir(parents=True, exist_ok=True)
    report = logdir / (stage + '.json')
    stdout = logdir / (stage + '.log')
    if report.exists() or stdout.exists():
        raise FileExistsError('Preserve the previous process attempt')
    prior = {p.name: file_hash(p) for p in root.glob('*.resources.json')}
    budget = Budget(root)
    wall = time.monotonic()
    with stdout.open('w') as stream:
        child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in child.stdout:
            stream.write(line)
            stream.flush()
            print(line, end='', flush=True)
        _, status, usage = os.wait4(child.pid, 0)
        child.returncode = os.waitstatus_to_exitcode(status)
    cpu = usage.ru_utime + usage.ru_stime
    observed = dict(command=command, returncode=child.returncode,
        cpu_seconds=cpu, user_cpu_seconds=usage.ru_utime, system_cpu_seconds=usage.ru_stime,
        wall_seconds=time.monotonic() - wall, max_rss_bytes=usage.ru_maxrss * 1024,
        accounting='wait4 child rusage; includes descendants reaped by the child',
        fit_suite=fit_suite, stdout_sha256=file_hash(stdout))
    for name, digest in prior.items():
        if file_hash(root / name) != digest:
            raise ValueError('Earlier resource report changed: ' + name)
    internal = [root / f'{name}.resources.json' for name in (ledger_stages or [stage])]
    internal = [p for p in internal if p.exists() and p.name not in prior]
    counted = sum(float(read_json(p)['cpu_seconds']) for p in internal)
    observed['internal_report_cpu_seconds'] = counted
    observed['internal_reports'] = {p.name: file_hash(p) for p in internal}
    write_json(report, observed)
    if not fit_suite:
        destination = root / (stage + '-process-overhead.resources.json')
        if destination.exists():
            raise FileExistsError(destination)
        extra = max(0., cpu - counted) + budget.measurements()['cpu_seconds']
        write_json(destination, dict(status='completed' if child.returncode == 0 else 'failed',
            cpu_seconds=extra, max_rss_bytes=observed['max_rss_bytes'],
            wall_seconds=observed['wall_seconds'], returncode=child.returncode,
            process_report=str(report.relative_to(root)), process_report_sha256=file_hash(report),
            accounting='wait4 CPU minus new internal CPU ledgers plus wrapper CPU; no double counting'))
        Budget(root).check()
    if child.returncode:
        raise SystemExit(child.returncode if child.returncode > 0 else 128 - child.returncode)
    return observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage', required=True)
    parser.add_argument('--fit-suite', action='store_true')
    parser.add_argument('--ledger-stage', action='append', help='Owned internal ledger; default matches --stage')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('Supply a command after --')
    run(args.output, args.stage, command, fit_suite=args.fit_suite, ledger_stages=args.ledger_stage)


if __name__ == '__main__':
    main()
