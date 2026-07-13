"""One-frame SAM2 image batch subprocess backend."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from nanotrack.subprocess_utils import CancellableSubprocessRunner, SubprocessCancelledError

from .backend import (
    DEFAULT_SAM2_CHECKPOINT,
    DEFAULT_SAM2_PYTHON,
    DEFAULT_SAM2_REPO_PATH,
    Sam2BackendError,
)
from .image_batch_contract import (
    Sam2ImageBatchInput,
    Sam2ImageBatchOutput,
    read_sam2_image_batch_output_npz,
    validate_sam2_image_batch_pair,
    write_sam2_image_batch_input_npz,
)


DEFAULT_SAM2_IMAGE_BATCH_WORKER_SCRIPT = Path(__file__).with_name(
    "run_sam2_image_batch_subprocess.py"
)


class Sam2ImageBatchBackendError(Sam2BackendError):
    """Base error raised by the one-frame SAM2 image batch backend."""


class Sam2ImageBatchBackendTimeoutError(Sam2ImageBatchBackendError):
    """Raised when the image batch worker exceeds its timeout."""


class Sam2ImageBatchBackendCancelledError(Sam2ImageBatchBackendError):
    """Raised when the image batch worker is canceled."""


@dataclass(frozen=True)
class Sam2ImageBatchBackendConfig:
    python_executable: str | Path = DEFAULT_SAM2_PYTHON
    worker_script: str | Path = DEFAULT_SAM2_IMAGE_BATCH_WORKER_SCRIPT
    checkpoint_path: str | Path = DEFAULT_SAM2_CHECKPOINT
    repo_path: str | Path | None = DEFAULT_SAM2_REPO_PATH
    config_path: str | Path | None = None
    device: str = "auto"
    apply_postprocessing: bool = True
    timeout_sec: float = 600.0
    working_directory: str | Path | None = None

    def __post_init__(self) -> None:
        if float(self.timeout_sec) <= 0.0:
            raise ValueError("timeout_sec must be positive.")


class Sam2ImageBatchSubprocessBackend:
    """Run all BBox prompts for one frame in one SAM2 subprocess."""

    def __init__(self, config: Sam2ImageBatchBackendConfig | None = None) -> None:
        self.config = config or Sam2ImageBatchBackendConfig()
        self._runner = CancellableSubprocessRunner()

    def run(self, run_input: Sam2ImageBatchInput) -> Sam2ImageBatchOutput:
        if not isinstance(run_input, Sam2ImageBatchInput):
            raise TypeError("run_input must be Sam2ImageBatchInput.")
        with TemporaryDirectory(prefix="nanotrack_sam2_image_batch_") as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "input.npz"
            output_path = temp_path / "output.npz"
            write_sam2_image_batch_input_npz(input_path, run_input)
            command = self._build_command(input_path, output_path)

            try:
                completed = self._runner.run(
                    command,
                    cwd=self._working_directory(),
                    timeout=float(self.config.timeout_sec),
                )
            except FileNotFoundError as error:
                raise Sam2ImageBatchBackendError(
                    f"SAM2 image batch executable or worker not found: {error.filename or error}."
                ) from error
            except SubprocessCancelledError as error:
                raise Sam2ImageBatchBackendCancelledError(
                    "SAM2 image batch worker was canceled."
                ) from error
            except subprocess.TimeoutExpired as error:
                raise Sam2ImageBatchBackendTimeoutError(
                    self._format_timeout_message(command, error.stdout, error.stderr)
                ) from error

            if completed.returncode != 0:
                raise Sam2ImageBatchBackendError(
                    self._format_subprocess_error(command, completed)
                )
            if not output_path.exists():
                raise Sam2ImageBatchBackendError(
                    "SAM2 image batch worker finished without creating output.npz.\n"
                    f"Command: {self._format_command(command)}\n"
                    f"stdout:\n{completed.stdout.strip() or '<empty>'}\n"
                    f"stderr:\n{completed.stderr.strip() or '<empty>'}"
                )
            try:
                output = read_sam2_image_batch_output_npz(output_path)
                return validate_sam2_image_batch_pair(run_input, output)
            except (KeyError, TypeError, ValueError, OSError) as error:
                raise Sam2ImageBatchBackendError(
                    f"SAM2 image batch worker produced invalid output.npz: {error}"
                ) from error

    def cancel(self) -> None:
        self._runner.cancel()

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
            str(self.config.device),
        ]
        if self.config.repo_path is not None:
            command.extend(("--repo-path", str(self.config.repo_path)))
        if self.config.config_path is not None:
            command.extend(("--config", str(self.config.config_path)))
        command.append(
            "--apply-postprocessing"
            if self.config.apply_postprocessing
            else "--disable-postprocessing"
        )
        return command

    def _working_directory(self) -> str:
        if self.config.working_directory is not None:
            return str(self.config.working_directory)
        return str(Path(self.config.worker_script).resolve().parent)

    @staticmethod
    def _format_command(command: list[str]) -> str:
        return " ".join(command)

    def _format_subprocess_error(
        self,
        command: list[str],
        completed: subprocess.CompletedProcess[str],
    ) -> str:
        return (
            "SAM2 image batch worker failed.\n"
            f"Command: {self._format_command(command)}\n"
            f"Exit code: {completed.returncode}\n"
            f"stdout:\n{completed.stdout.strip() or '<empty>'}\n"
            f"stderr:\n{completed.stderr.strip() or '<empty>'}"
        )

    def _format_timeout_message(
        self,
        command: list[str],
        stdout: str | bytes | None,
        stderr: str | bytes | None,
    ) -> str:
        return (
            f"SAM2 image batch worker timed out after {self.config.timeout_sec:.3f} s.\n"
            f"Command: {self._format_command(command)}\n"
            f"stdout:\n{_coerce_stream_text(stdout)}\n"
            f"stderr:\n{_coerce_stream_text(stderr)}"
        )


def _coerce_stream_text(value: str | bytes | None) -> str:
    if value is None:
        return "<empty>"
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return value.strip() or "<empty>"
