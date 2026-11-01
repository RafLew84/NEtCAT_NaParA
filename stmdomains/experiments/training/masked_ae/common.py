"""Separate resource ledger for the bounded issue25 research trial."""
from __future__ import annotations

from contextlib import contextmanager
import json
import math
from pathlib import Path
import resource
import time

from ...bundle import file_hash, write_json

CAPS = {
    'seconds_per_fit_including_validation_and_checkpoint': 900,
    'max_total_fit_seconds': 10800,
    'gpu_tensor_bytes': 8 * 1024**3,
    'process_rss_bytes': 12 * 1024**3,
    'all_checkpoint_bytes': 10 * 1024**3,
    'postprocessing_cpu_seconds_total': 7200,
    'max_total_fits': 12,
}
PROTOCOL_PATH = Path(__file__).with_name('protocol.json')


def read_json(path):
    return json.loads(Path(path).read_text())


class Budget:
    """CPU/RSS checks for non-fit stages, including recorded failed attempts."""
    def __init__(self, root):
        self.root = Path(root)
        self.cpu_started = time.process_time()
        self.wall_started = time.monotonic()
        self.cpu_limit_seconds = float(CAPS['postprocessing_cpu_seconds_total'])
        self.rss_limit_bytes = CAPS['process_rss_bytes']
        self.prior_reports = {}
        self.prior_cpu_seconds = 0.
        for path in sorted(self.root.glob('*.resources.json')):
            value = float(read_json(path)['cpu_seconds'])
            if not math.isfinite(value) or value < 0:
                raise ValueError(f'Invalid CPU ledger: {path}')
            self.prior_cpu_seconds += value
            self.prior_reports[str(path.resolve())] = file_hash(path)
        self.check()

    def measurements(self):
        cpu = time.process_time() - self.cpu_started
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        return dict(cpu_seconds=cpu, wall_seconds=time.monotonic()-self.wall_started,
                    max_rss_bytes=rss, max_rss_kib=rss//1024,
                    prior_cpu_seconds=self.prior_cpu_seconds,
                    cumulative_postprocess_cpu_seconds=self.prior_cpu_seconds+cpu,
                    cpu_limit_seconds=self.cpu_limit_seconds, rss_limit_bytes=self.rss_limit_bytes,
                    prior_reports_sha256=self.prior_reports)

    def check(self):
        value = self.measurements()
        if value['cumulative_postprocess_cpu_seconds'] > self.cpu_limit_seconds:
            raise RuntimeError('Issue25 postprocessing CPU budget exceeded')
        if value['max_rss_bytes'] > self.rss_limit_bytes:
            raise RuntimeError('Issue25 process RSS budget exceeded')

    def checked(self, iterable):
        for value in iterable:
            self.check()
            yield value


@contextmanager
def reporting_stage(root, stage):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    target = root/f'{stage}.resources.json'
    if target.exists():
        raise FileExistsError(f'Keep the previous stage ledger: {target}')
    budget = Budget(root)
    status = 'failed'
    try:
        yield budget
        budget.check()
        status = 'completed'
    finally:
        write_json(target, dict(status=status, **budget.measurements()))
