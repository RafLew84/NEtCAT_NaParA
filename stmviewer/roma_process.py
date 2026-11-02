"""Versioned, cancellable RoMa worker transport; no Torch in the GUI process."""

from collections.abc import Callable
import json
import os
from pathlib import Path
from queue import Empty, Full, Queue
import subprocess
from tempfile import TemporaryDirectory
from threading import Event, Thread
from time import monotonic
from typing import Any
from zipfile import ZipFile

import numpy as np
from numpy.typing import NDArray

PROTOCOL_VERSION = 1
MAX_MESSAGE = 65536


class RomaProcess:
    """Own one interpreter/model and temporary image pair for a calculation."""

    def __init__(self, interpreter: Path, configuration: dict[str, object], *,
                 progress: Callable[[str], None] | None = None,
                 cancelled: Callable[[], bool] | None = None,
                 worker_script: Path | None = None, timeout_s: float = 600.) -> None:
        self._temp = TemporaryDirectory(prefix='stmviewer-roma-')
        self.directory = Path(self._temp.name)
        self._process: subprocess.Popen[str] | None = None
        self._messages: Queue[str | None] = Queue(maxsize=64)
        self._reader: Thread | None = None
        self._stopping = Event()
        self._log = (self.directory / 'worker.log').open('w+', encoding='utf-8')
        self._sequence = 0
        self._cancelled, self._progress = cancelled, progress
        self._timeout = timeout_s
        samples = configuration.get('samples', 1000)
        if type(samples) is not int or not 8 <= samples <= 10000:
            self._log.close()
            self._temp.cleanup()
            raise ValueError('RoMa wymaga od 8 do 10000 próbek.')
        self._samples = samples
        self.last_metrics: dict[str, float] = {}
        self.device = ''
        self.provenance: tuple[tuple[str, str], ...] = ()
        try:
            self._checkpoint()
            interpreter = interpreter.expanduser().absolute()
            script = (worker_script or Path(__file__).with_name('roma_worker.py')).expanduser().absolute()
            environment = {key: value for key, value in os.environ.items()
                           if key not in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP')}
            self._process = subprocess.Popen(
                [str(interpreter), '-I', '-B', '-u', str(script), str(self.directory)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._log,
                text=True, encoding='utf-8', errors='replace', bufsize=1, env=environment,
                cwd=self.directory)
            self._reader = Thread(target=self._read, name='roma-protocol', daemon=True)
            self._reader.start()
            response = self._request('initialize', configuration=configuration)
            if response.get('kind') != 'ready' or not isinstance(response.get('device'), str):
                raise ValueError('Nieprawidłowa odpowiedź inicjalizacji RoMa.')
            provenance = response.get('provenance')
            if (not isinstance(provenance, dict) or len(provenance) > 128
                    or any(not isinstance(k, str) or not isinstance(v, str) for k, v in provenance.items())):
                raise ValueError('Nieprawidłowe pochodzenie modelu RoMa.')
            self.device = response['device']
            if self.device != 'CPU' and not self.device.startswith('CUDA:'):
                raise ValueError('Nieprawidłowe faktyczne urządzenie RoMa.')
            requested = configuration.get('device', 'auto')
            if ((requested == 'cpu' and self.device != 'CPU')
                    or (requested == 'cuda' and not self.device.startswith('CUDA:'))):
                raise ValueError('Proces RoMa zmienił wskazane urządzenie.')
            self.provenance = tuple(sorted(provenance.items()))
        except BaseException as error:
            self.close()
            from stmviewer.registration import RegistrationCancelled, RegistrationError
            if isinstance(error, (RegistrationCancelled, RegistrationError, KeyboardInterrupt, SystemExit)):
                raise
            raise RegistrationError(f'RoMa v2: {str(error) or type(error).__name__}') from error

    @property
    def returncode(self) -> int | None:
        return self._process.poll() if self._process is not None else None

    def _enqueue(self, value: str | None) -> None:
        while not self._stopping.is_set():
            try:
                self._messages.put(value, timeout=.05)
                return
            except Full:
                continue

    def _read(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        try:
            while not self._stopping.is_set():
                line = self._process.stdout.readline(MAX_MESSAGE + 1)
                if not line:
                    break
                self._enqueue(line)
                if len(line) > MAX_MESSAGE:
                    break
        finally:
            self._enqueue(None)

    def _checkpoint(self) -> None:
        if self._cancelled is not None and self._cancelled():
            from stmviewer.registration import RegistrationCancelled
            raise RegistrationCancelled

    def _request(self, kind: str, **payload: object) -> dict[str, Any]:
        from stmviewer.registration import RegistrationError
        try:
            self._checkpoint()
            process = self._process
            if process is None or process.poll() is not None or process.stdin is None:
                raise ValueError('Proces RoMa zakończył pracę.')
            self._sequence += 1
            process.stdin.write(json.dumps({'version': PROTOCOL_VERSION, 'id': self._sequence,
                                            'kind': kind, **payload}, allow_nan=False) + '\n')
            process.stdin.flush()
            deadline = monotonic() + self._timeout
            while True:
                self._checkpoint()
                if monotonic() > deadline:
                    raise ValueError('Przekroczono czas oczekiwania na proces RoMa.')
                try:
                    line = self._messages.get(timeout=.05)
                except Empty:
                    continue
                if line is None:
                    self._log.flush()
                    self._log.seek(0, 2)
                    self._log.seek(max(0, self._log.tell() - 2000))
                    raise ValueError('Proces RoMa zamknął połączenie (EOF). ' + self._log.read())
                if len(line) > MAX_MESSAGE:
                    raise ValueError('Zbyt długa wiadomość procesu RoMa.')
                value = json.loads(line)
                if (not isinstance(value, dict) or type(value.get('version')) is not int
                        or value.get('version') != PROTOCOL_VERSION or type(value.get('id')) is not int
                        or value.get('id') != self._sequence):
                    raise ValueError('Niezgodna wersja lub identyfikator protokołu RoMa.')
                if value.get('kind') == 'progress':
                    if self._progress:
                        self._progress(str(value.get('message', 'RoMa v2'))[:1000])
                    continue
                if value.get('kind') == 'error':
                    raise ValueError(str(value.get('message', 'Błąd procesu RoMa')))
                return value
        except BaseException as error:
            self.close()
            from stmviewer.registration import RegistrationCancelled
            if isinstance(error, (RegistrationCancelled, KeyboardInterrupt, SystemExit)):
                raise
            raise RegistrationError(f'RoMa v2: {str(error) or type(error).__name__}') from error

    def match(self, reference: NDArray[np.float32], moving: NDArray[np.float32]
              ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        from stmviewer.registration import RegistrationError
        try:
            self._checkpoint()
            np.save(self.directory / 'reference.npy', reference, allow_pickle=False)
            np.save(self.directory / 'moving.npy', moving, allow_pickle=False)
            response = self._request('match')
            if (response.get('kind') != 'matched' or response.get('reference_shape') != list(reference.shape)
                    or response.get('moving_shape') != list(moving.shape)):
                raise ValueError('Niezgodna geometria odpowiedzi RoMa.')
            output = self.directory / 'points.npz'
            if output.stat().st_size > 8192 + self._samples * 4 * 8:
                raise ValueError('Przekroczony limit liczby punktów RoMa.')
            with ZipFile(output) as archive:
                if sum(item.file_size for item in archive.infolist()) > 8192 + self._samples * 4 * 8:
                    raise ValueError('Przekroczony rozmiar tablic odpowiedzi RoMa.')
            with np.load(output, allow_pickle=False) as arrays:
                if set(arrays.files) != {'reference', 'moving'}:
                    raise ValueError('Nieznane tablice odpowiedzi RoMa.')
                p0, p1 = arrays['reference'], arrays['moving']
                if (p0.ndim != 2 or p0.shape[1] != 2 or p0.shape != p1.shape
                        or len(p0) > self._samples or p0.dtype.kind != 'f' or p1.dtype.kind != 'f'
                        or not np.isfinite(p0).all() or not np.isfinite(p1).all()):
                    raise ValueError('Nieprawidłowe korespondencje procesu RoMa.')
                result = np.asarray(p0, dtype=np.float64), np.asarray(p1, dtype=np.float64)
            metrics = response.get('metrics', {})
            if not isinstance(metrics, dict) or len(metrics) > 16:
                raise ValueError('Nieprawidłowe pomiary procesu RoMa.')
            self.last_metrics = {str(k): float(v) for k, v in metrics.items()}
            if not all(np.isfinite(v) and v >= 0 for v in self.last_metrics.values()):
                raise ValueError('Nieprawidłowe pomiary procesu RoMa.')
            self._checkpoint()
            return result
        except BaseException as error:
            self.close()
            from stmviewer.registration import RegistrationCancelled
            if isinstance(error, (RegistrationCancelled, RegistrationError, KeyboardInterrupt, SystemExit)):
                raise
            raise RegistrationError(f'RoMa v2: {str(error) or type(error).__name__}') from error
        finally:
            for name in ('reference.npy', 'moving.npy', 'points.npz'):
                (self.directory / name).unlink(missing_ok=True)

    def close(self) -> None:
        self._stopping.set()
        process = self._process
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=1.)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5.)
            if process.stdin:
                try:
                    process.stdin.close()
                except OSError:
                    pass
            if self._reader:
                self._reader.join(timeout=1.)
            if process.stdout:
                process.stdout.close()
        self._log.close()
        self._temp.cleanup()
