"""Complete step-boundary checkpoints for local, trusted research runs.

These files contain Python/NumPy RNG state and use pickle through torch.save.
Only load checkpoints created by this experiment, never downloaded weights.
The caller finishes optimizer/scheduler updates before saving. Data-loader
prefetch queues and pending gradients are intentionally not supported.
"""
from __future__ import annotations

import hashlib
from copy import deepcopy
import json
import os
from pathlib import Path
import random
import tempfile
from typing import Any

import numpy as np
import torch


SCHEMA = "stmdomains.training-checkpoint.v1"


def config_hash(config: dict[str, Any]) -> str:
    """Hash a JSON configuration, rejecting nonfinite or unserializable values."""
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def capture_rng(sampler: torch.Generator, *,
                np_generator: np.random.Generator | None = None) -> dict[str, Any]:
    return {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "numpy_generator": None if np_generator is None else {
            "bit_generator": type(np_generator.bit_generator).__name__,
            "state": deepcopy(np_generator.bit_generator.state),
        },
        "torch_cpu": torch.get_rng_state(),
        "torch_cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else None,
        "sampler": sampler.get_state(),
        "sampler_device": str(sampler.device),
    }


def _validate_rng(state: dict[str, Any], sampler: torch.Generator,
                  np_generator: np.random.Generator | None) -> None:
    if str(sampler.device) != state["sampler_device"]:
        raise ValueError("Checkpoint sampler device does not match the current generator")
    saved_generator = state.get("numpy_generator")
    if (saved_generator is None) != (np_generator is None):
        raise ValueError("NumPy augmentation generator presence differs from the checkpoint")
    if saved_generator is not None and saved_generator["bit_generator"] != type(np_generator.bit_generator).__name__:
        raise ValueError("NumPy augmentation bit-generator type differs from the checkpoint")
    cuda = state["torch_cuda"]
    if cuda is not None:
        if not torch.cuda.is_available() or len(cuda) != torch.cuda.device_count():
            raise ValueError("Checkpoint requires the same number of visible CUDA devices")


def restore_rng(state: dict[str, Any], sampler: torch.Generator, *,
                np_generator: np.random.Generator | None = None) -> None:
    _validate_rng(state, sampler, np_generator)
    cuda = state["torch_cuda"]
    if cuda is not None:
        torch.cuda.set_rng_state_all(cuda)
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    if np_generator is not None:
        np_generator.bit_generator.state = deepcopy(state["numpy_generator"]["state"])
    torch.set_rng_state(state["torch_cpu"])
    sampler.set_state(state["sampler"])


def read_checkpoint(path: str | Path) -> dict[str, Any]:
    """Read our own local checkpoint; do not use with untrusted files."""
    state = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(state, dict) or state.get("schema") != SCHEMA:
        raise ValueError("Unsupported training checkpoint schema")
    if state.get("config_hash") != config_hash(state["config"]):
        raise ValueError("Training checkpoint configuration hash is invalid")
    return state


def save_checkpoint(path: str | Path, *, model: torch.nn.Module,
                    optimizer: torch.optim.Optimizer, scheduler: Any,
                    sampler: torch.Generator, progress: dict[str, Any],
                    config: dict[str, Any],
                    np_generator: np.random.Generator | None = None) -> None:
    """Atomically save all state needed by the synchronous fp32 training loop."""
    digest = config_hash(config)
    state = {
        "schema": SCHEMA,
        "config": config,
        "config_hash": digest,
        "model": model.state_dict(),
        "model_training": model.training,
        "optimizer": optimizer.state_dict(),
        "scheduler": scheduler.state_dict(),
        "rng": capture_rng(sampler, np_generator=np_generator),
        "progress": progress,
        "runtime": {
            "torch": torch.__version__, "numpy": np.__version__,
            "cuda_runtime": torch.version.cuda,
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "cudnn_deterministic": torch.backends.cudnn.deterministic,
            "cudnn_benchmark": torch.backends.cudnn.benchmark,
            "matmul_allow_tf32": torch.backends.cuda.matmul.allow_tf32,
            "cudnn_allow_tf32": torch.backends.cudnn.allow_tf32,
            "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
            "precision": "float32",
        },
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".",
                                         suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            torch.save(state, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_checkpoint(path: str | Path, *, model: torch.nn.Module,
                    optimizer: torch.optim.Optimizer, scheduler: Any,
                    sampler: torch.Generator,
                    config: dict[str, Any],
                    np_generator: np.random.Generator | None = None) -> dict[str, Any]:
    """Restore an experiment step, rejecting a changed run before loading weights."""
    state = read_checkpoint(path)
    if state["config_hash"] != config_hash(config):
        raise ValueError("Checkpoint configuration does not match the requested run")
    runtime = state["runtime"]
    if runtime["torch"] != torch.__version__ or runtime["numpy"] != np.__version__:
        raise ValueError("Exact continuation requires the recorded Torch/NumPy versions")
    if runtime["cublas_workspace_config"] != os.environ.get("CUBLAS_WORKSPACE_CONFIG"):
        raise ValueError("CUBLAS_WORKSPACE_CONFIG differs from the checkpoint")
    _validate_rng(state["rng"], sampler, np_generator)
    torch.use_deterministic_algorithms(runtime["deterministic_algorithms"])
    torch.backends.cudnn.deterministic = runtime["cudnn_deterministic"]
    torch.backends.cudnn.benchmark = runtime["cudnn_benchmark"]
    torch.backends.cuda.matmul.allow_tf32 = runtime["matmul_allow_tf32"]
    torch.backends.cudnn.allow_tf32 = runtime["cudnn_allow_tf32"]
    model.load_state_dict(state["model"])
    model.train(state["model_training"])
    optimizer.load_state_dict(state["optimizer"])
    scheduler.load_state_dict(state["scheduler"])
    optimizer.zero_grad(set_to_none=True)
    restore_rng(state["rng"], sampler, np_generator=np_generator)
    return state["progress"]
