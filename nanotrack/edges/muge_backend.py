"""Subprocess launcher for MuGE runs from the main NanoTrack app."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

import numpy as np

from .contract import DexiNedRunInput, DexiNedRunOutput
from .subprocess_utils import CancellableSubprocessRunner


DEFAULT_MUGE_PYTHON = Path(r"C:\Users\rlewa\anaconda3\envs\uaed_gpu\python.exe")
DEFAULT_MUGE_REPO_PATH = Path(r"C:\Users\rlewa\Documents\PROJEKTY\UAED_MuGE")
DEFAULT_MUGE_CHECKPOINT = Path(
    r"C:\Users\rlewa\Documents\PROJEKTY\UAED_MuGE\checkpoints\MuGE\muge-epoch-19-checkpoint.pth"
)
DEFAULT_MUGE_WORKER_SCRIPT = Path(__file__).with_name("run_muge_subprocess.py")
DEFAULT_MUGE_GRANULARITY = 0.5


class MugeBackendError(RuntimeError):
    """Base error raised by the NanoTrack MuGE subprocess backend."""


class MugeBackendTimeoutError(MugeBackendError):
    """Raised when the MuGE worker exceeds the configured timeout."""


@dataclass(frozen=True)
class MugeBackendConfig:
    """Runtime configuration for the MuGE subprocess launcher."""

    python_executable: str | Path = DEFAULT_MUGE_PYTHON
    worker_script: str | Path = DEFAULT_MUGE_WORKER_SCRIPT
    checkpoint_path: str | Path = DEFAULT_MUGE_CHECKPOINT
    repo_path: str | Path | None = DEFAULT_MUGE_REPO_PATH
    distribution: str = "gs"
    device: str = "auto"
    granularity: float = DEFAULT_MUGE_GRANULARITY
    timeout_sec: float = 300.0
    working_directory: str | Path | None = None

    def __post_init__(self) -> None:
        if self.timeout_sec <= 0:
            raise ValueError("timeout_sec must be positive.")
        if not str(self.distribution).strip():
            raise ValueError("distribution must be non-empty.")
        granularity = float(self.granularity)
        if not np.isfinite(granularity) or not 0.0 <= granularity <= 1.0:
            raise ValueError("granularity must be within [0, 1].")
        object.__setattr__(self, "granularity", granularity)


class MugeSubprocessBackend:
    """Serialize one MuGE run to `.npz`, execute the worker, and parse the result."""

    def __init__(self, config: MugeBackendConfig | None = None):
        self.config = config or MugeBackendConfig()
        self._runner = CancellableSubprocessRunner()

    def run(self, run_input: DexiNedRunInput) -> DexiNedRunOutput:
        with TemporaryDirectory(prefix="nanotrack_muge_") as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "input.npz"
            output_path = temp_path / "output.npz"
            self._write_input(input_path, run_input)

            command = self._build_command(input_path, output_path)
            cwd = self._working_directory()

            try:
                completed = self._runner.run(
                    command,
                    cwd=cwd,
                    timeout=self.config.timeout_sec,
                )
            except FileNotFoundError as exc:
                raise MugeBackendError(
                    f"MuGE executable or worker not found: {exc.filename or exc}."
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise MugeBackendTimeoutError(
                    self._format_timeout_message(command, exc.stdout, exc.stderr)
                ) from exc

            if completed.returncode != 0:
                raise MugeBackendError(self._format_subprocess_error(command, completed))

            if not output_path.exists():
                raise MugeBackendError(
                    "MuGE worker finished without creating output.npz.\n"
                    f"Command: {self._format_command(command)}\n"
                    f"stdout:\n{completed.stdout.strip() or '<empty>'}\n"
                    f"stderr:\n{completed.stderr.strip() or '<empty>'}"
                )

            return self._read_output(output_path)

    def cancel(self) -> None:
        self._runner.cancel()

    def _write_input(self, path: Path, run_input: DexiNedRunInput) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **run_input.to_npz_payload())

    def _read_output(self, path: Path) -> DexiNedRunOutput:
        with np.load(path, allow_pickle=False) as payload:
            output_payload = {key: payload[key] for key in payload.files}
        return DexiNedRunOutput.from_npz_payload(output_payload)

    def _build_command(self, input_path: Path, output_path: Path) -> list[str]:
        command = [
            str(self.config.python_executable),
            str(self.config.worker_script),
            "--input-npz",
            str(input_path),
            "--output-npz",
            str(output_path),
            "--checkpoint",
            str(self.config.checkpoint_path),
            "--device",
            self.config.device,
            "--distribution",
            str(self.config.distribution),
            "--granularity",
            f"{self.config.granularity:.12g}",
        ]
        if self.config.repo_path is not None:
            command.extend(["--repo-path", str(self.config.repo_path)])
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
            "MuGE worker failed.\n"
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
            f"MuGE worker timed out after {self.config.timeout_sec:.3f} s.\n"
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
