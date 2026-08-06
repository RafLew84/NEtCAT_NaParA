from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import Generic, TypeVar


SnapshotT = TypeVar("SnapshotT")


class DomainAnalysisWorkspaceSubscription:
    """Idempotent handle for one workspace-state consumer."""

    def __init__(self, disconnect: Callable[[], bool]) -> None:
        self._disconnect = disconnect

    def disconnect(self) -> bool:
        return self._disconnect()


class DomainAnalysisWorkspaceStateChanged(Generic[SnapshotT]):
    """Thread-safe, detachable fan-out for immutable workspace snapshots."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._callbacks: dict[int, Callable[[SnapshotT], None]] = {}
        self._next_token = 1

    def connect(
        self,
        callback: Callable[[SnapshotT], None],
    ) -> DomainAnalysisWorkspaceSubscription:
        if not callable(callback):
            raise TypeError("callback must be callable.")
        with self._lock:
            token = self._next_token
            self._next_token += 1
            self._callbacks[token] = callback

        def disconnect() -> bool:
            with self._lock:
                return self._callbacks.pop(token, None) is not None

        return DomainAnalysisWorkspaceSubscription(disconnect)

    def emit(self, snapshot: SnapshotT) -> None:
        with self._lock:
            callbacks = tuple(self._callbacks.items())
            first_error: Exception | None = None
            for token, callback in callbacks:
                if token not in self._callbacks:
                    continue
                try:
                    callback(snapshot)
                except Exception as error:
                    if first_error is None:
                        first_error = error
        if first_error is not None:
            raise first_error

    def __call__(self, snapshot: SnapshotT) -> None:
        self.emit(snapshot)
