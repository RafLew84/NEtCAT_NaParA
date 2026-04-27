"""Shared subprocess helpers for cancellable edge-detector backends."""

from __future__ import annotations

from dataclasses import dataclass, field
import subprocess
import threading


class EdgeSubprocessCancelledError(RuntimeError):
    """Raised when an edge-detector subprocess is canceled by the UI."""


@dataclass
class CancellableSubprocessRunner:
    """Small wrapper around ``Popen`` that exposes cooperative cancellation."""

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _process: subprocess.Popen[str] | None = field(default=None, init=False)
    _cancel_requested: bool = field(default=False, init=False)

    def run(
        self,
        command: list[str],
        *,
        cwd: str,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        with self._lock:
            if self._cancel_requested:
                self._cancel_requested = False
                raise EdgeSubprocessCancelledError("Edge-detector worker was canceled.")
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self._process = process

        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr)
        finally:
            with self._lock:
                self._process = None
                was_canceled = self._cancel_requested
                self._cancel_requested = False

        if was_canceled:
            raise EdgeSubprocessCancelledError("Edge-detector worker was canceled.")
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)

    def cancel(self) -> None:
        with self._lock:
            self._cancel_requested = True
            process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
