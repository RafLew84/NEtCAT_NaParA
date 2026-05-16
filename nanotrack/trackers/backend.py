"""Subprocess launcher for point-tracker runs from the main NanoTrack app."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

import numpy as np

from .contract import PointTrackerRunInput, PointTrackerRunOutput


class PointTrackerBackendError(RuntimeError):
    """Base error raised by the NanoTrack point-tracker subprocess backend."""


class PointTrackerBackendTimeoutError(PointTrackerBackendError):
    """Raised when the point-tracker worker exceeds the configured timeout."""


@dataclass(frozen=True)
class PointTrackerBackendConfig:
    """Runtime configuration for a generic point-tracker subprocess launcher."""

    model_name: str
    python_executable: str | Path
    worker_script: str | Path
    checkpoint_path: str | Path | None = None
    repo_path: str | Path | None = None
    device: str = "auto"
    timeout_sec: float = 300.0
    working_directory: str | Path | None = None

    def __post_init__(self) -> None:
        if not str(self.model_name).strip():
            raise ValueError("model_name must be a non-empty string.")
        if self.timeout_sec <= 0:
            raise ValueError("timeout_sec must be positive.")


class PointTrackerSubprocessBackend:
    """Serialize one point-tracker run to `.npz`, execute the worker, and parse the result."""

    def __init__(self, config: PointTrackerBackendConfig):
        self.config = config

    def run(self, run_input: PointTrackerRunInput) -> PointTrackerRunOutput:
        with TemporaryDirectory(prefix="nanotrack_tracker_") as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "input.npz"
            output_path = temp_path / "output.npz"
            self._write_input(input_path, run_input)

            command = self._build_command(input_path, output_path)
            cwd = self._working_directory()

            try:
                completed = subprocess.run(
                    command,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=self.config.timeout_sec,
                    check=False,
                )
            except FileNotFoundError as exc:
                raise PointTrackerBackendError(
                    f"{self.config.model_name} executable or worker not found: {exc.filename or exc}."
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise PointTrackerBackendTimeoutError(
                    self._format_timeout_message(command, exc.stdout, exc.stderr)
                ) from exc

            if completed.returncode != 0:
                raise PointTrackerBackendError(self._format_subprocess_error(command, completed))

            if not output_path.exists():
                raise PointTrackerBackendError(
                    f"{self.config.model_name} worker finished without creating output.npz.\n"
                    f"Command: {self._format_command(command)}\n"
                    f"stdout:\n{completed.stdout.strip() or '<empty>'}\n"
                    f"stderr:\n{completed.stderr.strip() or '<empty>'}"
                )

            return self._read_output(output_path)

    def _write_input(self, path: Path, run_input: PointTrackerRunInput) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **run_input.to_npz_payload())

    def _read_output(self, path: Path) -> PointTrackerRunOutput:
        with np.load(path, allow_pickle=False) as payload:
            output_payload = {key: payload[key] for key in payload.files}
        return PointTrackerRunOutput.from_npz_payload(output_payload)

    def _build_command(self, input_path: Path, output_path: Path) -> list[str]:
        command = [
            str(self.config.python_executable),
            str(self.config.worker_script),
            "--input-npz",
            str(input_path),
            "--output-npz",
            str(output_path),
            "--model-name",
            self.config.model_name,
            "--device",
            self.config.device,
        ]
        if self.config.repo_path is not None:
            command.extend(["--repo-path", str(self.config.repo_path)])
        if self.config.checkpoint_path is not None:
            command.extend(["--checkpoint", str(self.config.checkpoint_path)])
        return command

    def _working_directory(self) -> str:
        if self.config.working_directory is not None:
            return str(self.config.working_directory)
        return str(Path(self.config.worker_script).resolve().parent)

    def _format_command(self, command: list[str]) -> str:
        return " ".join(command)

    def _format_subprocess_error(
        self,
        command: list[str],
        completed: subprocess.CompletedProcess[str],
    ) -> str:
        stdout = completed.stdout.strip() or "<empty>"
        stderr = completed.stderr.strip() or "<empty>"
        return (
            f"{self.config.model_name} worker failed.\n"
            f"Command: {self._format_command(command)}\n"
            f"Exit code: {completed.returncode}\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )

    def _format_timeout_message(
        self,
        command: list[str],
        stdout: str | bytes | None,
        stderr: str | bytes | None,
    ) -> str:
        stdout_text = self._coerce_stream_text(stdout)
        stderr_text = self._coerce_stream_text(stderr)
        return (
            f"{self.config.model_name} worker timed out after {self.config.timeout_sec:.3f} s.\n"
            f"Command: {self._format_command(command)}\n"
            f"stdout:\n{stdout_text}\n"
            f"stderr:\n{stderr_text}"
        )

    def _coerce_stream_text(self, value: str | bytes | None) -> str:
        if value is None:
            return "<empty>"
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        value = value.strip()
        return value or "<empty>"
