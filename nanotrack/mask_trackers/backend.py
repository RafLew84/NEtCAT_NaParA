"""Registry, factory, and subprocess launcher for optional mask trackers."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

import numpy as np

from nanotrack.subprocess_utils import CancellableSubprocessRunner, SubprocessCancelledError

from .config import MaskTrackerBackendConfig, MaskTrackerKind, default_mask_tracker_config
from .contract import MaskTrackerRunInput, MaskTrackerRunOutput
from .sam2_adapter import Sam2MaskTrackerBackend


class MaskTrackerBackendError(RuntimeError):
    """Base error raised by the common mask-tracker backend layer."""


class MaskTrackerBackendTimeoutError(MaskTrackerBackendError):
    """Raised when a mask-tracker worker exceeds the configured timeout."""


class MaskTrackerBackendCancelledError(MaskTrackerBackendError):
    """Raised when a mask-tracker worker is canceled by the UI."""


class MaskTrackerBackendUnavailableError(MaskTrackerBackendError):
    """Raised when a mask-tracker backend cannot be created from local paths."""


class MaskTrackerSubprocessBackend:
    """Serialize one common mask-tracker run to `.npz`, execute a worker, and parse the result."""

    def __init__(self, config: MaskTrackerBackendConfig):
        self.config = config
        self._runner = CancellableSubprocessRunner()

    def run(self, run_input: MaskTrackerRunInput) -> MaskTrackerRunOutput:
        if run_input.tracker_kind is not self.config.kind:
            raise ValueError(
                f"Run input tracker_kind={run_input.tracker_kind.value!r} does not match "
                f"backend kind={self.config.kind.value!r}."
            )

        with TemporaryDirectory(prefix=f"nanotrack_{self.config.kind.value}_") as temp_dir:
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
                raise MaskTrackerBackendError(
                    f"{self.config.kind.value} executable or worker not found: {exc.filename or exc}."
                ) from exc
            except SubprocessCancelledError as exc:
                raise MaskTrackerBackendCancelledError(f"{self.config.kind.value} worker was canceled.") from exc
            except subprocess.TimeoutExpired as exc:
                raise MaskTrackerBackendTimeoutError(
                    self._format_timeout_message(command, exc.stdout, exc.stderr)
                ) from exc

            if completed.returncode != 0:
                raise MaskTrackerBackendError(self._format_subprocess_error(command, completed))

            if not output_path.exists():
                raise MaskTrackerBackendError(
                    f"{self.config.kind.value} worker finished without creating output.npz.\n"
                    f"Command: {self._format_command(command)}\n"
                    f"stdout:\n{completed.stdout.strip() or '<empty>'}\n"
                    f"stderr:\n{completed.stderr.strip() or '<empty>'}"
                )

            return self._read_output(output_path)

    def cancel(self) -> None:
        self._runner.cancel()

    def _write_input(self, path: Path, run_input: MaskTrackerRunInput) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **run_input.to_npz_payload())

    def _read_output(self, path: Path) -> MaskTrackerRunOutput:
        with np.load(path, allow_pickle=False) as payload:
            output_payload = {key: payload[key] for key in payload.files}
        return MaskTrackerRunOutput.from_npz_payload(output_payload)

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
        if self.config.variant is not None:
            command.extend(["--variant", str(self.config.variant)])
        if self.config.config_identifier is not None:
            command.extend(["--config", str(self.config.config_identifier)])
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
        return (
            f"{self.config.kind.value} worker failed.\n"
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
            f"{self.config.kind.value} worker timed out after {self.config.timeout_sec:.3f} s.\n"
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


def create_mask_tracker_backend(
    kind_or_config: MaskTrackerKind | str | MaskTrackerBackendConfig,
    *,
    validate_paths: bool = True,
) -> Sam2MaskTrackerBackend | MaskTrackerSubprocessBackend:
    """Create a mask-tracker backend from a tracker kind or full backend config."""

    config = _coerce_backend_config(kind_or_config)
    if validate_paths:
        validate_mask_tracker_backend_config(config)
    backend_class = MASK_TRACKER_BACKEND_REGISTRY[config.kind]
    return backend_class(config)


def _coerce_backend_config(kind_or_config: MaskTrackerKind | str | MaskTrackerBackendConfig) -> MaskTrackerBackendConfig:
    if isinstance(kind_or_config, MaskTrackerBackendConfig):
        return kind_or_config
    return default_mask_tracker_config(kind_or_config)


def validate_mask_tracker_backend_config(config: MaskTrackerBackendConfig) -> None:
    """Validate local paths required before launching a mask-tracker subprocess."""

    missing: list[tuple[str, Path, str]] = []
    _collect_missing_path(missing, "python_executable", config.python_executable, expect_file=True)
    _collect_missing_path(missing, "worker_script", config.worker_script, expect_file=True)
    _collect_missing_path(missing, "models_dir", config.models_dir, expect_file=False)
    _collect_missing_path(missing, "checkpoint_path", config.checkpoint_path, expect_file=True)
    if config.repo_path is not None:
        _collect_missing_path(missing, "repo_path", config.repo_path, expect_file=False)
    if not missing:
        return

    details = "\n".join(
        f"- {field_name}: {path} ({reason})"
        for field_name, path, reason in missing
    )
    raise MaskTrackerBackendUnavailableError(
        f"Mask tracker backend '{config.kind.value}' is not available.\n"
        f"Missing or invalid required paths:\n{details}"
    )


def _collect_missing_path(
    missing: list[tuple[str, Path, str]],
    field_name: str,
    path_like: str | Path,
    *,
    expect_file: bool,
) -> None:
    path = Path(path_like)
    if not path.exists():
        missing.append((field_name, path, "does not exist"))
        return
    if expect_file and not path.is_file():
        missing.append((field_name, path, "expected file"))
        return
    if not expect_file and not path.is_dir():
        missing.append((field_name, path, "expected directory"))


MASK_TRACKER_BACKEND_REGISTRY = {
    MaskTrackerKind.SAM2: Sam2MaskTrackerBackend,
    MaskTrackerKind.DAM4SAM: MaskTrackerSubprocessBackend,
    MaskTrackerKind.SAMURAI: MaskTrackerSubprocessBackend,
}
