"""Background save with cooperative cancellation and GUI overwrite confirmation."""
from __future__ import annotations

from pathlib import Path
import threading

from PyQt6.QtCore import QThread, pyqtSignal

from nanotrack.persistence import NanoTrackSessionSnapshot, SessionSaveCancelled, SessionSaveControl, SessionSaveReceipt, save_session_snapshot


class SessionSaveJob(QThread):
    progress = pyqtSignal(str, int)
    overwrite_requested = pyqtSignal(str)

    def __init__(self, path: str, snapshot: NanoTrackSessionSnapshot, parent=None):
        super().__init__(parent)
        self.path, self.snapshot = path, snapshot
        self.control = SessionSaveControl()
        self.outcome = "pending"
        self.error = ""
        self.receipt: SessionSaveReceipt | None = None
        self._answer = threading.Event()
        self._overwrite = False
        self._last_progress: tuple[str, int] | None = None

    def cancel(self) -> bool:
        accepted = self.control.cancel()
        self._answer.set()
        return accepted

    def confirm_overwrite(self, answer: bool) -> None:
        self._overwrite = answer
        self._answer.set()

    def _confirm(self, path: Path) -> bool:
        self.overwrite_requested.emit(str(path))
        while not self._answer.wait(.05):
            self.control.check()
        self.control.check()
        return self._overwrite

    def _report(self, stage: str, completed: int, total: int) -> None:
        value = stage, min(100, int(completed * 100 / max(total, 1)))
        if value != self._last_progress:
            self.progress.emit(*value)
            self._last_progress = value

    def run(self) -> None:
        try:
            self.receipt = save_session_snapshot(self.path, self.snapshot, control=self.control,
                                                progress=self._report, confirm_overwrite=self._confirm)
            self.outcome = "saved"
        except SessionSaveCancelled:
            self.outcome = "cancelled"
        except Exception as exc:
            self.outcome, self.error = "failed", str(exc)
