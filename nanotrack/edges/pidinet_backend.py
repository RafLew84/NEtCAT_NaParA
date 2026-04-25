"""Subprocess launcher for PiDiNet runs from the main NanoTrack app."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

import numpy as np

from .contract import DexiNedRunInput, DexiNedRunOutput


DEFAULT_PIDINET_PYTHON = Path(r"C:\Users\rlewa\anaconda3\envs\pidinet_gpu\python.exe")
DEFAULT_PIDINET_REPO_PATH = Path(r"C:\Users\rlewa\Documents\PROJEKTY\PiDiNet")
DEFAULT_PIDINET_CHECKPOINT = Path(r"C:\Users\rlewa\Documents\PROJEKTY\PiDiNet\trained_models\table5_pidinet.pth")
DEFAULT_PIDINET_WORKER_SCRIPT = Path(__file__).with_name("run_pidinet_subprocess.py")


class PidinetBackendError(RuntimeError):
    """Base error raised by the NanoTrack PiDiNet subprocess backend."""


class PidinetBackendTimeoutError(PidinetBackendError):
    """Raised when the PiDiNet worker exceeds the configured timeout."""


@dataclass(frozen=True)
class PidinetBackendConfig:
    """Runtime configuration for the PiDiNet subprocess launcher."""

    python_executable: str | Path = DEFAULT_PIDINET_PYTHON
    worker_script: str | Path = DEFAULT_PIDINET_WORKER_SCRIPT
    checkpoint_path: str | Path = DEFAULT_PIDINET_CHECKPOINT
    repo_path: str | Path | None = DEFAULT_PIDINET_REPO_PATH
    model_name: str = "pidinet_converted"
    model_config: str = "carv4"
    use_sa: bool = True
    use_dil: bool = True
    evaluate_converted: bool = True
    device: str = "auto"
    timeout_sec: float = 300.0
    working_directory: str | Path | None = None

    def __post_init__(self) -> None:
        if self.timeout_sec <= 0:
            raise ValueError("timeout_sec must be positive.")


class PidinetSubprocessBackend:
    """Serialize one PiDiNet run to `.npz`, execute the worker, and parse the result."""

    def __init__(self, config: PidinetBackendConfig | None = None):
        self.config = config or PidinetBackendConfig()

    def run(self, run_input: DexiNedRunInput) -> DexiNedRunOutput:
        with TemporaryDirectory(prefix="nanotrack_pidinet_") as temp_dir:
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
                raise PidinetBackendError(
                    f"PiDiNet executable or worker not found: {exc.filename or exc}."
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise PidinetBackendTimeoutError(
                    self._format_timeout_message(command, exc.stdout, exc.stderr)
                ) from exc

            if completed.returncode != 0:
                raise PidinetBackendError(self._format_subprocess_error(command, completed))

            if not output_path.exists():
                raise PidinetBackendError(
                    "PiDiNet worker finished without creating output.npz.\n"
                    f"Command: {self._format_command(command)}\n"
                    f"stdout:\n{completed.stdout.strip() or '<empty>'}\n"
                    f"stderr:\n{completed.stderr.strip() or '<empty>'}"
                )

            return self._read_output(output_path)

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
            "--model",
            str(self.config.model_name),
            "--model-config",
            str(self.config.model_config),
            "--device",
            self.config.device,
        ]
        if self.config.use_sa:
            command.append("--sa")
        if self.config.use_dil:
            command.append("--dil")
        if self.config.evaluate_converted:
            command.append("--evaluate-converted")
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
            "PiDiNet worker failed.\n"
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
            f"PiDiNet worker timed out after {self.config.timeout_sec:.3f} s.\n"
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
