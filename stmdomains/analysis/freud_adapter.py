"""Bounded subprocess lifetime, cancellation and useful optional-dependency errors."""

from collections.abc import Callable
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

import numpy as np

from stmdomains.analysis.freud_neighbors import Environments
from stmdomains.analysis.freud_settings import FreudSettings
from stmdomains.core.analysis_result import AnalysisCancelled

TIME_LIMIT_SECONDS = 90.
MAX_POINTS = 1000


def require_freud() -> None:
    if importlib.util.find_spec('freud') is None:
        raise ValueError('Brak opcjonalnego freud-analysis. W środowisku netcat zainstaluj freud-analysis==3.6.1. '
                         'Pozostałe metody działają bez tej biblioteki.')


def compare_environments(environments: Environments, settings: FreudSettings,
                         cancelled: Callable[[], bool], *, time_limit: float = TIME_LIMIT_SECONDS):
    require_freud()
    if len(environments.points) > MAX_POINTS:
        raise ValueError(f'Próba freud obsługuje maksymalnie {MAX_POINTS} aktywnych molekuł w klatce.')
    if cancelled():
        raise AnalysisCancelled()
    if not len(environments.eligible):
        from importlib.metadata import version
        return np.zeros(len(environments.points), np.int32), version('freud-analysis')
    with TemporaryDirectory(prefix='stmdomains-freud-') as directory:
        folder = Path(directory)
        source, target = folder/'input.npz', folder/'output.json'
        np.savez(source, points=environments.points, query=environments.query, neighbor=environments.neighbor,
                 eligible=environments.eligible, tolerance=settings.tolerance, registration=settings.registration)
        environment = {**os.environ, 'MPLCONFIGDIR': str(folder/'mpl'), 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'}
        started = time.monotonic()
        with (folder/'stderr.txt').open('w+') as errors:
            process = subprocess.Popen([sys.executable, '-m', 'stmdomains.analysis.freud_worker', str(source), str(target)],
                cwd=Path(__file__).resolve().parents[2], env=environment, stdout=subprocess.DEVNULL, stderr=errors)
            try:
                while process.poll() is None:
                    if cancelled():
                        raise AnalysisCancelled()
                    if time.monotonic()-started > time_limit:
                        raise ValueError(f'Freud przekroczył limit {time_limit:g} s. Zmniejsz liczbę sąsiadów '
                                         'lub wyłącz dopasowanie obrotu/odbicia. Poprzedni wynik jest zachowany.')
                    time.sleep(.05)
                if cancelled():
                    raise AnalysisCancelled()
                if process.returncode:
                    errors.seek(0)
                    detail = errors.read(4000)
                    raise ValueError(f'Obliczenia freud nie powiodły się (kod {process.returncode}). {detail}')
                result = json.loads(target.read_text())
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2)
    labels = np.asarray(result['labels'])
    if labels.shape != (len(environments.points),) or labels.dtype.kind not in 'iu':
        raise ValueError('Freud zwrócił nieprawidłowe etykiety.')
    # Canonical IDs by spatial order; labels of invalid environments are not classes.
    canonical = np.zeros(len(labels), np.int32)
    mapping: dict[int, int] = {}
    for i in environments.eligible:
        key = int(labels[i])
        if key not in mapping:
            mapping[key] = len(mapping)+1
        canonical[i] = mapping[key]
    return canonical, str(result['version'])
