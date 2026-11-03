from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable

from .contract import MolTrackSam3RunInput
from .io import parse_moltrack_sam3_output_npz, write_moltrack_sam3_input_npz


DEFAULT_SAM3_PYTHON = Path(r"C:\Users\rlewa\anaconda3\envs\sam3\python.exe")
DEFAULT_SAM3_TRANSFORMERS_WORKER = Path(__file__).with_name("run_sam3_subprocess.py")
DEFAULT_SAM31_OFFICIAL_WORKER = Path(__file__).with_name("run_sam31_official_subprocess.py")


class MolTrackSam3Error(RuntimeError):
    """Base error for MolTrack SAM3 backend failures."""


@dataclass(frozen=True)
class MolTrackSam3BackendConfig:
    python_executable: str | Path = DEFAULT_SAM3_PYTHON
    transformers_worker_script: str | Path = DEFAULT_SAM3_TRANSFORMERS_WORKER
    official_sam31_worker_script: str | Path = DEFAULT_SAM31_OFFICIAL_WORKER
    device: str = "cuda"
    timeout_sec: float = 600.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "python_executable", Path(self.python_executable))
        object.__setattr__(self, "transformers_worker_script", Path(self.transformers_worker_script))
        object.__setattr__(self, "official_sam31_worker_script", Path(self.official_sam31_worker_script))
        object.__setattr__(self, "device", str(self.device))
        timeout_sec = float(self.timeout_sec)
        if timeout_sec <= 0:
            raise ValueError("SAM3 timeout_sec must be positive.")
        object.__setattr__(self, "timeout_sec", timeout_sec)


SubprocessRun = Callable[..., object]


class MolTrackSam3SubprocessBackend:
    """Run MolTrack SAM3 contract payloads in the dedicated `sam3` interpreter."""

    def __init__(
        self,
        config: MolTrackSam3BackendConfig | None = None,
        *,
        subprocess_run: SubprocessRun | None = None,
    ):
        self.config = config or MolTrackSam3BackendConfig()
        self._subprocess_run = subprocess_run or subprocess.run

    def run(self, run_input: MolTrackSam3RunInput):
        with TemporaryDirectory(prefix="moltrack_sam3_") as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "input.npz"
            output_path = temp_path / "output.npz"
            write_moltrack_sam3_input_npz(run_input, input_path)
            command = self._build_command(run_input, input_path, output_path)
            try:
                completed = self._subprocess_run(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=self.config.timeout_sec,
                )
            except FileNotFoundError as exc:
                raise MolTrackSam3Error(f"SAM3 executable or worker not found: {exc}") from exc
            except subprocess.TimeoutExpired as exc:
                raise MolTrackSam3Error(f"SAM3 worker timed out after {self.config.timeout_sec:.3f} s.") from exc
            except subprocess.CalledProcessError as exc:
                raise MolTrackSam3Error(self._format_process_error(exc)) from exc

            if not output_path.exists():
                stdout = str(getattr(completed, "stdout", "") or "")
                stderr = str(getattr(completed, "stderr", "") or "")
                detail = "\n".join(part for part in (stdout, stderr) if part)
                suffix = f"\n{detail}" if detail else ""
                raise MolTrackSam3Error(f"SAM3 worker finished without creating output.npz.{suffix}")
            return parse_moltrack_sam3_output_npz(
                output_path,
                score_threshold=run_input.score_threshold,
            )

    def _build_command(
        self,
        run_input: MolTrackSam3RunInput,
        input_path: Path,
        output_path: Path,
    ) -> list[str]:
        worker_script = (
            self.config.official_sam31_worker_script
            if run_input.backend == "official_sam31"
            else self.config.transformers_worker_script
        )
        return [
            str(self.config.python_executable),
            str(worker_script),
            "--input-npz",
            str(input_path),
            "--output-npz",
            str(output_path),
            "--model-id",
            run_input.model_id,
            "--device",
            self.config.device,
            "--score-threshold",
            str(float(run_input.score_threshold)),
            "--mask-threshold",
            str(float(run_input.mask_threshold)),
        ]

    def _format_process_error(self, exc: subprocess.CalledProcessError) -> str:
        stdout = str(getattr(exc, "stdout", "") or "")
        stderr = str(getattr(exc, "stderr", "") or "")
        detail = "\n".join(part for part in (stdout, stderr) if part)
        suffix = f"\n{detail}" if detail else ""
        return f"SAM3 worker failed with exit code {exc.returncode}.{suffix}"
