"""Persistent subprocess session for SAM2 image batch inference."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
from pathlib import Path
from queue import Empty, Queue
import subprocess
from tempfile import TemporaryDirectory
from threading import Event, Lock, Thread
from typing import Any

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


SAM2_PERSISTENT_IMAGE_BATCH_PROTOCOL_VERSION = 1
DEFAULT_SAM2_PERSISTENT_IMAGE_BATCH_WORKER_SCRIPT = Path(__file__).with_name(
    "run_sam2_persistent_image_batch_subprocess.py"
)
_STREAM_EOF = object()


class Sam2PersistentImageBatchBackendError(Sam2BackendError):
    """Base error raised by a persistent SAM2 image batch session."""


class Sam2PersistentImageBatchProtocolError(Sam2PersistentImageBatchBackendError):
    """Raised when the worker violates the JSON Lines protocol."""


class Sam2PersistentImageBatchTimeoutError(Sam2PersistentImageBatchBackendError):
    """Raised when the worker does not answer within the configured timeout."""


class Sam2PersistentImageBatchCancelledError(Sam2PersistentImageBatchBackendError):
    """Raised when the caller cancels a persistent SAM2 session."""


@dataclass(frozen=True)
class Sam2PersistentFrameDiagnostics:
    """Latest per-frame memory measurements reported by the worker."""

    host_rss_bytes: int
    peak_host_rss_bytes: int
    current_vram_bytes: int
    peak_vram_bytes: int

    def __post_init__(self) -> None:
        for name in (
            "host_rss_bytes",
            "peak_host_rss_bytes",
            "current_vram_bytes",
            "peak_vram_bytes",
        ):
            value = int(getattr(self, name))
            if value < 0:
                raise ValueError(f"{name} must be non-negative.")
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class Sam2PersistentImageBatchBackendConfig:
    python_executable: str | Path = DEFAULT_SAM2_PYTHON
    worker_script: str | Path = DEFAULT_SAM2_PERSISTENT_IMAGE_BATCH_WORKER_SCRIPT
    checkpoint_path: str | Path = DEFAULT_SAM2_CHECKPOINT
    repo_path: str | Path | None = DEFAULT_SAM2_REPO_PATH
    config_path: str | Path | None = None
    device: str = "auto"
    apply_postprocessing: bool = True
    startup_timeout_sec: float = 600.0
    frame_timeout_sec: float = 600.0
    close_timeout_sec: float = 5.0
    working_directory: str | Path | None = None

    def __post_init__(self) -> None:
        for name in ("startup_timeout_sec", "frame_timeout_sec", "close_timeout_sec"):
            if float(getattr(self, name)) <= 0.0:
                raise ValueError(f"{name} must be positive.")


class Sam2PersistentImageBatchBackend:
    """Open run-scoped sessions that reuse one loaded SAM2 model."""

    def __init__(
        self,
        config: Sam2PersistentImageBatchBackendConfig | None = None,
    ) -> None:
        self.config = config or Sam2PersistentImageBatchBackendConfig()

    def open_session(self) -> "Sam2PersistentImageBatchSession":
        return Sam2PersistentImageBatchSession(self.config)


class Sam2PersistentImageBatchSession:
    """Synchronous frame protocol over one long-lived worker process."""

    def __init__(self, config: Sam2PersistentImageBatchBackendConfig) -> None:
        self.config = config
        self._temporary_directory = TemporaryDirectory(
            prefix="nanotrack_sam2_persistent_"
        )
        self._temp_path = Path(self._temporary_directory.name)
        self._stdout_messages: Queue[str | object] = Queue()
        self._stderr_lines: deque[str] = deque(maxlen=200)
        self._request_lock = Lock()
        self._cancel_requested = Event()
        self._request_number = 0
        self._last_diagnostics: Sam2PersistentFrameDiagnostics | None = None
        self._started = False
        self._closed = False
        self._process: subprocess.Popen[str] | None = None
        self._stdout_thread: Thread | None = None
        self._stderr_thread: Thread | None = None

    @property
    def process_id(self) -> int:
        if self._process is None:
            raise Sam2PersistentImageBatchBackendError("SAM2 session is not running.")
        return int(self._process.pid)

    @property
    def is_running(self) -> bool:
        return (
            not self._closed
            and self._process is not None
            and self._process.poll() is None
        )

    @property
    def temporary_directory(self) -> Path:
        return self._temp_path

    @property
    def last_diagnostics(self) -> Sam2PersistentFrameDiagnostics | None:
        return self._last_diagnostics

    def __enter__(self) -> "Sam2PersistentImageBatchSession":
        if self._closed:
            raise Sam2PersistentImageBatchBackendError("SAM2 session is closed.")
        if not self._started:
            try:
                self._start()
                self._started = True
            except BaseException:
                self.close()
                raise
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def segment_frame(self, run_input: Sam2ImageBatchInput) -> Sam2ImageBatchOutput:
        if not isinstance(run_input, Sam2ImageBatchInput):
            raise TypeError("run_input must be Sam2ImageBatchInput.")
        with self._request_lock:
            self._require_open()
            self._request_number += 1
            request_id = f"frame-{self._request_number}"
            input_path = self._temp_path / f"{request_id}-input.npz"
            output_path = self._temp_path / f"{request_id}-output.npz"
            write_sam2_image_batch_input_npz(input_path, run_input)
            self._send_message(
                {
                    "protocol_version": SAM2_PERSISTENT_IMAGE_BATCH_PROTOCOL_VERSION,
                    "type": "segment_frame",
                    "request_id": request_id,
                    "input_npz": str(input_path),
                    "output_npz": str(output_path),
                }
            )
            response = self._read_message(
                timeout=float(self.config.frame_timeout_sec),
                phase=f"frame request {request_id}",
            )
            self._require_message_type(response, "frame_result")
            if response.get("request_id") != request_id:
                raise Sam2PersistentImageBatchProtocolError(
                    f"SAM2 worker returned request_id {response.get('request_id')!r}; "
                    f"expected {request_id!r}."
                )
            if Path(str(response.get("output_npz", ""))).resolve() != output_path.resolve():
                raise Sam2PersistentImageBatchProtocolError(
                    "SAM2 worker returned an unexpected output_npz path."
                )
            try:
                diagnostics = _read_frame_diagnostics(response)
                output = read_sam2_image_batch_output_npz(output_path)
                validated_output = validate_sam2_image_batch_pair(run_input, output)
                self._last_diagnostics = diagnostics
                return validated_output
            except (KeyError, TypeError, ValueError, OSError) as error:
                raise Sam2PersistentImageBatchBackendError(
                    f"SAM2 persistent worker produced invalid output NPZ: {error}"
                ) from error
            finally:
                input_path.unlink(missing_ok=True)
                output_path.unlink(missing_ok=True)

    def cancel(self) -> None:
        self._cancel_requested.set()
        process = self._process
        if process is not None and process.poll() is None:
            self._stop_process(process)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        process = self._process
        if process is not None and process.poll() is None:
            try:
                self._send_message(
                    {
                        "protocol_version": SAM2_PERSISTENT_IMAGE_BATCH_PROTOCOL_VERSION,
                        "type": "close",
                    },
                    allow_closed=True,
                )
                process.wait(timeout=float(self.config.close_timeout_sec))
            except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
                self._stop_process(process)
        if process is not None:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
        for thread in (self._stdout_thread, self._stderr_thread):
            if thread is not None:
                thread.join(timeout=0.2)
        self._temporary_directory.cleanup()

    def _start(self) -> None:
        if self._cancel_requested.is_set():
            raise Sam2PersistentImageBatchCancelledError(
                "SAM2 persistent worker was canceled."
            )
        command = self._build_command()
        try:
            self._process = subprocess.Popen(
                command,
                cwd=self._working_directory(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except FileNotFoundError as error:
            raise Sam2PersistentImageBatchBackendError(
                f"SAM2 persistent executable or worker not found: {error.filename or error}."
            ) from error
        if self._cancel_requested.is_set():
            self._stop_process(self._process)
            raise Sam2PersistentImageBatchCancelledError(
                "SAM2 persistent worker was canceled."
            )
        assert self._process.stdout is not None
        assert self._process.stderr is not None
        self._stdout_thread = Thread(
            target=self._read_stdout,
            args=(self._process.stdout,),
            daemon=True,
        )
        self._stderr_thread = Thread(
            target=self._read_stderr,
            args=(self._process.stderr,),
            daemon=True,
        )
        self._stdout_thread.start()
        self._stderr_thread.start()
        ready = self._read_message(
            timeout=float(self.config.startup_timeout_sec),
            phase="startup handshake",
        )
        self._require_message_type(ready, "ready")

    def _build_command(self) -> list[str]:
        command = [
            str(self.config.python_executable),
            str(self.config.worker_script),
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

    def _send_message(
        self,
        message: dict[str, Any],
        *,
        allow_closed: bool = False,
    ) -> None:
        if not allow_closed:
            self._require_open()
        process = self._process
        if process is None or process.stdin is None:
            raise Sam2PersistentImageBatchBackendError("SAM2 worker stdin is unavailable.")
        process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        process.stdin.flush()

    def _read_message(self, *, timeout: float, phase: str) -> dict[str, Any]:
        try:
            item = self._stdout_messages.get(timeout=timeout)
        except Empty as error:
            raise Sam2PersistentImageBatchTimeoutError(
                f"SAM2 persistent worker timed out during {phase} after {timeout:.3f} s."
            ) from error
        if item is _STREAM_EOF:
            if self._cancel_requested.is_set():
                raise Sam2PersistentImageBatchCancelledError(
                    "SAM2 persistent worker was canceled."
                )
            raise Sam2PersistentImageBatchBackendError(self._process_exit_message(phase))
        try:
            message = json.loads(str(item))
        except json.JSONDecodeError as error:
            raise Sam2PersistentImageBatchProtocolError(
                f"SAM2 worker returned malformed JSON during {phase}: {error.msg}."
            ) from error
        if not isinstance(message, dict):
            raise Sam2PersistentImageBatchProtocolError(
                f"SAM2 worker returned a non-object message during {phase}."
            )
        version = message.get("protocol_version")
        if version != SAM2_PERSISTENT_IMAGE_BATCH_PROTOCOL_VERSION:
            raise Sam2PersistentImageBatchProtocolError(
                f"SAM2 worker protocol_version is {version!r}; "
                f"expected {SAM2_PERSISTENT_IMAGE_BATCH_PROTOCOL_VERSION}."
            )
        if message.get("type") == "error":
            raise Sam2PersistentImageBatchBackendError(
                f"SAM2 persistent worker error during {phase}: "
                f"{message.get('message', '<no message>')}"
            )
        return message

    @staticmethod
    def _require_message_type(message: dict[str, Any], expected: str) -> None:
        if message.get("type") != expected:
            raise Sam2PersistentImageBatchProtocolError(
                f"SAM2 worker returned message type {message.get('type')!r}; "
                f"expected {expected!r}."
            )

    def _require_open(self) -> None:
        if self._cancel_requested.is_set():
            raise Sam2PersistentImageBatchCancelledError(
                "SAM2 persistent worker was canceled."
            )
        if self._closed:
            raise Sam2PersistentImageBatchBackendError("SAM2 session is closed.")
        if self._process is None or self._process.poll() is not None:
            raise Sam2PersistentImageBatchBackendError(
                self._process_exit_message("request")
            )

    def _process_exit_message(self, phase: str) -> str:
        return_code = self._process.poll() if self._process is not None else None
        if self._process is not None and return_code is None:
            try:
                return_code = self._process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                return_code = None
        stderr = "".join(self._stderr_lines).strip() or "<empty>"
        return (
            f"SAM2 persistent worker stopped during {phase}.\n"
            f"Exit code: {return_code}\n"
            f"stderr:\n{stderr}"
        )

    def _read_stdout(self, stream: Any) -> None:
        try:
            for line in stream:
                self._stdout_messages.put(line.rstrip("\r\n"))
        finally:
            self._stdout_messages.put(_STREAM_EOF)

    def _read_stderr(self, stream: Any) -> None:
        for line in stream:
            self._stderr_lines.append(line)

    @staticmethod
    def _stop_process(process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1.0)


def _read_frame_diagnostics(
    message: dict[str, Any],
) -> Sam2PersistentFrameDiagnostics | None:
    payload = message.get("diagnostics")
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise Sam2PersistentImageBatchProtocolError(
            "SAM2 worker diagnostics must be a JSON object."
        )
    try:
        return Sam2PersistentFrameDiagnostics(
            host_rss_bytes=int(payload["host_rss_bytes"]),
            peak_host_rss_bytes=int(
                payload.get("peak_host_rss_bytes", payload["host_rss_bytes"])
            ),
            current_vram_bytes=int(payload["current_vram_bytes"]),
            peak_vram_bytes=int(payload["peak_vram_bytes"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise Sam2PersistentImageBatchProtocolError(
            f"SAM2 worker returned invalid frame diagnostics: {error}"
        ) from error
