from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

import numpy as np

from moltrack import __version__ as moltrack_version


_ENVIRONMENT_FIELDS = (
    "moltrack_version",
    "git_commit",
    "git_dirty",
    "python_version",
    "numpy_version",
    "scipy_version",
    "qhull_version",
)


def collect_analysis_export_environment() -> dict[str, object | None]:
    """Collect reproducibility versions without making export depend on them."""

    scipy_version = None
    qhull_version = None
    try:
        import scipy
        from scipy.spatial import _qhull

        scipy_version = str(scipy.__version__)
        for attribute_name in ("__qhull_version__", "qhull_version"):
            candidate = getattr(_qhull, attribute_name, None)
            if candidate is not None:
                qhull_version = str(candidate)
                break
    except (ImportError, OSError):
        pass

    git_commit, git_dirty = _git_environment()
    return {
        "moltrack_version": str(moltrack_version),
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "python_version": sys.version.split()[0],
        "numpy_version": str(np.__version__),
        "scipy_version": scipy_version,
        "qhull_version": qhull_version,
    }


def normalize_analysis_export_environment(
    environment: Mapping[str, object] | None,
) -> dict[str, object | None]:
    """Keep a stable manifest shape for injected or collected environments."""

    if environment is None:
        environment = {}
    if not isinstance(environment, Mapping):
        raise TypeError("Analysis export environment provider must return a mapping.")
    return {field_name: environment.get(field_name) for field_name in _ENVIRONMENT_FIELDS}


def resolve_analysis_export_environment(
    provider: Callable[[], Mapping[str, object]] | None,
) -> dict[str, object | None]:
    """Resolve an injected or local environment into the stable manifest shape."""

    environment = collect_analysis_export_environment() if provider is None else provider()
    return normalize_analysis_export_environment(environment)


def _git_environment() -> tuple[str | None, bool | None]:
    repository_root = Path(__file__).resolve().parents[2]
    commit = _run_git(repository_root, "rev-parse", "HEAD")
    if commit is None:
        return None, None
    status = _run_git(repository_root, "status", "--porcelain")
    return commit, None if status is None else bool(status)


def _run_git(repository_root: Path, *arguments: str) -> str | None:
    try:
        completed = subprocess.run(
            ("git", "-C", str(repository_root), *arguments),
            capture_output=True,
            check=False,
            text=True,
            timeout=2.0,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()
