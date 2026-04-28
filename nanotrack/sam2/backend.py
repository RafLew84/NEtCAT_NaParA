"""Subprocess launcher for SAM2 runs from the main NanoTrack app."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

import numpy as np

from nanotrack.subprocess_utils import CancellableSubprocessRunner, SubprocessCancelledError

from .contract import Sam2RunInput, Sam2RunOutput


DEFAULT_SAM2_PYTHON = Path(r"C:\Users\rlewa\anaconda3\envs\sam2\python.exe")
DEFAULT_SAM2_REPO_PATH = Path(r"C:\Users\rlewa\Documents\PROJEKTY\sam2")
DEFAULT_SAM2_CHECKPOINT = Path(
    r"C:\Users\rlewa\Documents\PROJEKTY\trackleed\tracking_models\sam2\sam2.1_hiera_base_plus.pt"
)
DEFAULT_SAM2_WORKER_SCRIPT = Path(__file__).with_name("run_sam2_subprocess.py")


class Sam2BackendError(RuntimeError):
    """Base error raised by the NanoTrack SAM2 subprocess backend."""


class Sam2BackendTimeoutError(Sam2BackendError):
    """Raised when the SAM2 worker exceeds the configured timeout."""


class Sam2BackendCancelledError(Sam2BackendError):
    """Raised when the SAM2 worker is canceled by the UI."""


@dataclass(frozen=True)
class Sam2BackendConfig:
    """Runtime configuration for the SAM2 subprocess launcher."""

    python_executable: str | Path = DEFAULT_SAM2_PYTHON
    worker_script: str | Path = DEFAULT_SAM2_WORKER_SCRIPT
    checkpoint_path: str | Path = DEFAULT_SAM2_CHECKPOINT
    repo_path: str | Path | None = DEFAULT_SAM2_REPO_PATH
    config_path: str | Path | None = None
    device: str = "auto"
    apply_postprocessing: bool = True
    offload_video_to_cpu: bool = True
    offload_state_to_cpu: bool = False
    async_loading_frames: bool = False
    timeout_sec: float = 600.0
    working_directory: str | Path | None = None

    def __post_init__(self) -> None:
        if self.timeout_sec <= 0:
            raise ValueError("timeout_sec must be positive.")


class Sam2SubprocessBackend:
    """Serialize one SAM2 run to `.npz`, execute the worker, and parse the result."""

    def __init__(self, config: Sam2BackendConfig | None = None):
        self.config = config or Sam2BackendConfig()
        self._runner = CancellableSubprocessRunner()

    def run(self, run_input: Sam2RunInput) -> Sam2RunOutput:
        with TemporaryDirectory(prefix="nanotrack_sam2_") as temp_dir:
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
                raise Sam2BackendError(
                    f"SAM2 executable or worker not found: {exc.filename or exc}."
                ) from exc
            except SubprocessCancelledError as exc:
                raise Sam2BackendCancelledError("SAM2 worker was canceled.") from exc
            except subprocess.TimeoutExpired as exc:
                raise Sam2BackendTimeoutError(
                    self._format_timeout_message(command, exc.stdout, exc.stderr)
                ) from exc

            if completed.returncode != 0:
                raise Sam2BackendError(self._format_subprocess_error(command, completed))

            if not output_path.exists():
                raise Sam2BackendError(
                    "SAM2 worker finished without creating output.npz.\n"
                    f"Command: {self._format_command(command)}\n"
                    f"stdout:\n{completed.stdout.strip() or '<empty>'}\n"
                    f"stderr:\n{completed.stderr.strip() or '<empty>'}"
                )

            return self._read_output(output_path)

    def cancel(self) -> None:
        self._runner.cancel()

    def _write_input(self, path: Path, run_input: Sam2RunInput) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **run_input.to_npz_payload())

    def _read_output(self, path: Path) -> Sam2RunOutput:
        with np.load(path, allow_pickle=False) as payload:
            output_payload = {key: payload[key] for key in payload.files}
        return Sam2RunOutput.from_npz_payload(output_payload)

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
        ]
        if self.config.repo_path is not None:
            command.extend(["--repo-path", str(self.config.repo_path)])
        if self.config.config_path is not None:
            command.extend(["--config", str(self.config.config_path)])
        if self.config.apply_postprocessing:
            command.append("--apply-postprocessing")
        else:
            command.append("--disable-postprocessing")
        if self.config.offload_video_to_cpu:
            command.append("--offload-video-to-cpu")
        if self.config.offload_state_to_cpu:
            command.append("--offload-state-to-cpu")
        if self.config.async_loading_frames:
            command.append("--async-loading-frames")
        return command

    def _working_directory(self) -> str:
        if self.config.working_directory is not None:
            return str(self.config.working_directory)
        return str(Path(self.config.worker_script).resolve().parent)

    def _format_command(self, command: list[str]) -> str:
        return " ".join(command)

    def _format_subprocess_error(self, command: list[str], completed: subprocess.CompletedProcess[str]) -> str:
        stdout = completed.stdout.strip() or "<empty>"
        stderr = completed.stderr.strip() or "<empty>"
        hint = self._format_return_code_hint(completed.returncode)
        hint_block = "" if hint is None else f"\nHint: {hint}\n"
        return (
            "SAM2 worker failed.\n"
            f"Command: {self._format_command(command)}\n"
            f"Exit code: {completed.returncode}\n"
            f"{hint_block}"
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
            f"SAM2 worker timed out after {self.config.timeout_sec:.3f} s.\n"
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

    def _format_return_code_hint(self, return_code: int) -> str | None:
        if int(return_code) == 3221226505:
            return (
                "Windows exit code 3221226505 (0xC0000409) usually means a native crash in a C/CUDA extension. "
                "For large SAM2 batches this is often memory-pressure related. NanoTrack now runs with video "
                "offloaded to CPU, but if the problem persists try a smaller checkpoint or CPU device."
            )
        return None
