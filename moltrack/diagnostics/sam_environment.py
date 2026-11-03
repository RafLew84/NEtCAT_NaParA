from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Callable

import numpy as np

from moltrack.sam3 import (
    MolTrackSam3BoxPrompt,
    MolTrackSam3OutputProposal,
    MolTrackSam3RunInput,
    MolTrackSam3RunOutput,
    parse_moltrack_sam3_output_npz,
    write_moltrack_sam3_input_npz,
)
from nanotrack.sam2 import (
    DEFAULT_SAM2_PYTHON,
    DEFAULT_SAM2_REPO_PATH,
    DEFAULT_SAM2_WORKER_SCRIPT,
    Sam2RunInput,
    Sam2RunOutput,
)
from moltrack.sam3.backend import (
    DEFAULT_SAM3_PYTHON,
    DEFAULT_SAM3_TRANSFORMERS_WORKER,
    DEFAULT_SAM31_OFFICIAL_WORKER,
)


DEFAULT_SAM2_CHECKPOINT_DIR = Path(r"C:\Users\rlewa\Documents\PROJEKTY\trackleed\tracking_models\sam2")
DEFAULT_SAM3_REPO_PATH = Path(r"C:\Users\rlewa\Documents\PROJEKTY\sam3")
DEFAULT_HF_CACHE_DIR = Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface")
SAM2_CHECKPOINT_GLOB = "*.pt"
WSL_VSOCK_ERROR_MARKER = "UtilBindVsockAnyPort"


@dataclass(frozen=True)
class SamDiagnosticResult:
    name: str
    severity: str
    message: str
    path: str = ""

    def __post_init__(self) -> None:
        severity = str(self.severity).strip().lower()
        if severity not in ("ok", "warning", "error"):
            raise ValueError("SAM diagnostic severity must be one of: ok, warning, error.")
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "path", str(self.path))

    @property
    def ok(self) -> bool:
        return self.severity != "error"


@dataclass(frozen=True)
class SamDiagnosticReport:
    title: str
    results: tuple[SamDiagnosticResult, ...]

    @property
    def ok(self) -> bool:
        return all(result.ok for result in self.results)

    def to_text(self) -> str:
        lines = [str(self.title)]
        for result in self.results:
            path_suffix = f" [{result.path}]" if result.path else ""
            lines.append(f"- {result.severity.upper()}: {result.name}: {result.message}{path_suffix}")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(
            {
                "title": self.title,
                "ok": self.ok,
                "results": [
                    {
                        "name": result.name,
                        "severity": result.severity,
                        "ok": result.ok,
                        "message": result.message,
                        "path": result.path,
                    }
                    for result in self.results
                ],
            },
            indent=2,
            ensure_ascii=False,
        )


def discover_sam2_checkpoints(checkpoint_dir: str | Path = DEFAULT_SAM2_CHECKPOINT_DIR) -> list[Path]:
    checkpoint_path = _runtime_path(checkpoint_dir)
    if not checkpoint_path.exists() or not checkpoint_path.is_dir():
        return []
    return sorted(path for path in checkpoint_path.glob(SAM2_CHECKPOINT_GLOB) if path.is_file())


def build_sam_environment_report(
    *,
    sam2_python: str | Path = DEFAULT_SAM2_PYTHON,
    sam2_checkpoint_dir: str | Path = DEFAULT_SAM2_CHECKPOINT_DIR,
    sam2_repo_path: str | Path | None = DEFAULT_SAM2_REPO_PATH,
    sam2_worker_script: str | Path = DEFAULT_SAM2_WORKER_SCRIPT,
    sam3_python: str | Path = DEFAULT_SAM3_PYTHON,
    sam3_repo_path: str | Path = DEFAULT_SAM3_REPO_PATH,
    sam3_transformers_worker: str | Path = DEFAULT_SAM3_TRANSFORMERS_WORKER,
    sam31_official_worker: str | Path = DEFAULT_SAM31_OFFICIAL_WORKER,
    hf_cache_dir: str | Path = DEFAULT_HF_CACHE_DIR,
) -> SamDiagnosticReport:
    results = [
        _path_result("SAM2 python.exe", sam2_python, expected_kind="file"),
        _path_result("SAM2 worker script", sam2_worker_script, expected_kind="file"),
        _optional_path_result("SAM2 repo", sam2_repo_path, expected_kind="dir"),
        _sam2_checkpoint_result(sam2_checkpoint_dir),
        _path_result("SAM3 python.exe", sam3_python, expected_kind="file"),
        _path_result("SAM3 repo", sam3_repo_path, expected_kind="dir"),
        _path_result("SAM3 transformers worker", sam3_transformers_worker, expected_kind="file"),
        _path_result("SAM3.1 official worker", sam31_official_worker, expected_kind="file"),
        _path_result("Hugging Face cache", hf_cache_dir, expected_kind="dir", missing_severity="warning"),
    ]
    return SamDiagnosticReport("SAM environment diagnostics", tuple(results))


def probe_python_executable(
    python_executable: str | Path,
    *,
    subprocess_run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    timeout_sec: float = 10.0,
) -> SamDiagnosticResult:
    path = str(python_executable)
    try:
        completed = subprocess_run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=float(timeout_sec),
        )
    except FileNotFoundError as exc:
        return SamDiagnosticResult("Python probe", "error", f"Executable not found: {exc}", path)
    except subprocess.TimeoutExpired:
        return SamDiagnosticResult("Python probe", "error", f"Timed out after {timeout_sec:.1f} s.", path)
    except Exception as exc:
        return SamDiagnosticResult("Python probe", "error", str(exc) or exc.__class__.__name__, path)

    output = "\n".join(
        part.strip()
        for part in (str(completed.stdout or ""), str(completed.stderr or ""))
        if part and part.strip()
    )
    if _contains_wsl_vsock_error(output):
        return SamDiagnosticResult(
            "Python probe",
            "warning",
            "WSL interop returned UtilBindVsockAnyPort; env path may still be valid from Windows.",
            path,
        )
    if completed.returncode != 0:
        return SamDiagnosticResult("Python probe", "error", output or f"Exit code {completed.returncode}", path)
    return SamDiagnosticResult("Python probe", "ok", output or "Python executable responded.", path)


def run_fast_sam_contract_smoke(output_dir: str | Path) -> SamDiagnosticReport:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    results = [_run_sam2_contract_smoke(output_path), _run_sam3_contract_smoke(output_path)]
    return SamDiagnosticReport("SAM fast contract smoke", tuple(results))


def _path_result(
    name: str,
    path: str | Path,
    *,
    expected_kind: str,
    missing_severity: str = "error",
) -> SamDiagnosticResult:
    candidate = _runtime_path(path)
    if expected_kind == "file":
        exists = candidate.is_file()
        expected_message = "file found"
        missing_message = "file missing"
    elif expected_kind == "dir":
        exists = candidate.is_dir()
        expected_message = "directory found"
        missing_message = "directory missing"
    else:
        raise ValueError(f"Unsupported expected_kind: {expected_kind!r}")
    if exists:
        return SamDiagnosticResult(name, "ok", expected_message, str(candidate))
    return SamDiagnosticResult(name, missing_severity, missing_message, str(candidate))


def _optional_path_result(
    name: str,
    path: str | Path | None,
    *,
    expected_kind: str,
) -> SamDiagnosticResult:
    if path is None:
        return SamDiagnosticResult(name, "warning", "not configured")
    return _path_result(name, path, expected_kind=expected_kind)


def _runtime_path(path: str | Path) -> Path:
    path_text = str(path)
    if os.name != "nt" and len(path_text) >= 3 and path_text[1] == ":":
        windows_path = PureWindowsPath(path_text)
        drive = windows_path.drive.rstrip(":").lower()
        parts = windows_path.parts[1:]
        return Path("/mnt") / drive / Path(*parts)
    return Path(path)


def _sam2_checkpoint_result(checkpoint_dir: str | Path) -> SamDiagnosticResult:
    checkpoints = discover_sam2_checkpoints(checkpoint_dir)
    if not checkpoints:
        return SamDiagnosticResult("SAM2 checkpoints", "error", "0 found", str(checkpoint_dir))
    return SamDiagnosticResult(
        "SAM2 checkpoints",
        "ok",
        f"{len(checkpoints)} found: {', '.join(path.name for path in checkpoints)}",
        str(checkpoint_dir),
    )


def _run_sam2_contract_smoke(output_dir: Path) -> SamDiagnosticResult:
    try:
        frames = np.arange(1 * 4 * 4, dtype=np.float32).reshape(1, 4, 4)
        run_input = Sam2RunInput(
            track_id=1,
            frame_index_offset=0,
            frames=frames,
            query_box_xyxy=np.asarray([1, 1, 3, 3], dtype=np.float32),
            source_view="raw",
            mask_probability_threshold=0.5,
        )
        input_payload = run_input.to_npz_payload()
        restored_input = Sam2RunInput.from_npz_payload(input_payload)
        mask = np.zeros((1, 4, 4), dtype=bool)
        mask[0, 1:3, 1:3] = True
        output = Sam2RunOutput(
            track_id=restored_input.track_id,
            frame_index_offset=restored_input.frame_index_offset,
            masks=mask,
            visible_mask=np.asarray([True]),
            mask_scores=np.asarray([0.8], dtype=np.float32),
            mask_bboxes_xyxy=np.asarray([[1, 1, 3, 3]], dtype=np.float32),
        )
        restored_output = Sam2RunOutput.from_npz_payload(output.to_npz_payload())
        if restored_output.masks.shape != (1, 4, 4):
            raise ValueError("unexpected SAM2 output mask shape")
        np.savez_compressed(output_dir / "sam2_contract_input.npz", **input_payload)
    except Exception as exc:
        return SamDiagnosticResult("SAM2 contract round-trip", "error", str(exc) or exc.__class__.__name__)
    return SamDiagnosticResult("SAM2 contract round-trip", "ok", "NPZ input/output contract validated")


def _run_sam3_contract_smoke(output_dir: Path) -> SamDiagnosticResult:
    try:
        run_input = MolTrackSam3RunInput(
            frame_index=0,
            source_view="raw",
            frame=np.arange(4 * 4, dtype=np.float32).reshape(4, 4),
            prompts=(MolTrackSam3BoxPrompt(bbox_xyxy=(1, 1, 3, 3), label=1, detection_id="bbox-1"),),
            model_id="facebook/sam3",
            backend="transformers_sam3",
        )
        input_path = output_dir / "sam3_contract_input.npz"
        output_path = output_dir / "sam3_contract_output.npz"
        write_moltrack_sam3_input_npz(run_input, input_path)
        np.savez_compressed(
            output_path,
            bboxes_xyxy=np.asarray([[1, 1, 3, 3]], dtype=np.float32),
            scores=np.asarray([0.9], dtype=np.float32),
            masks=np.ones((1, 4, 4), dtype=np.uint8),
            backend=np.asarray("diagnostic"),
            model_id=np.asarray("facebook/sam3"),
        )
        output = parse_moltrack_sam3_output_npz(output_path, score_threshold=0.5)
        round_trip = MolTrackSam3RunOutput(
            proposals=(
                MolTrackSam3OutputProposal(
                    bbox_xyxy=output.proposals[0].bbox_xyxy,
                    score=output.proposals[0].score,
                    mask=output.proposals[0].mask,
                    metadata=output.proposals[0].metadata,
                ),
            )
        )
        if round_trip.proposal_count != 1:
            raise ValueError("unexpected SAM3 proposal count")
    except Exception as exc:
        return SamDiagnosticResult("SAM3 contract round-trip", "error", str(exc) or exc.__class__.__name__)
    return SamDiagnosticResult("SAM3 contract round-trip", "ok", "NPZ input/output contract validated")


def _contains_wsl_vsock_error(text: str) -> bool:
    return WSL_VSOCK_ERROR_MARKER.lower() in str(text).lower()
