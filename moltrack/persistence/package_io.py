from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_package_files(root: Path) -> tuple[str, ...]:
    return tuple(sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    ))


def publish_path(staged: Path, destination: Path, *, overwrite: bool) -> None:
    if not path_exists(destination):
        os.replace(staged, destination)
        return
    if not overwrite:
        raise FileExistsError(f"Package destination already exists: {destination}")
    file_descriptor, backup_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".backup",
        dir=destination.parent,
    )
    os.close(file_descriptor)
    backup = Path(backup_name)
    backup.unlink()
    os.replace(destination, backup)
    try:
        os.replace(staged, destination)
    except BaseException:
        os.replace(backup, destination)
        raise
    else:
        remove_path(backup)


def remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path_exists(path):
        path.unlink()


def path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()
