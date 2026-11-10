"""Stream source identity without keeping a second image file in memory."""

from collections.abc import Callable
import hashlib
from pathlib import Path


def source_digest(path: Path, check: Callable[[], None] = lambda: None) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            check()
            digest.update(chunk)
    check()
    return digest.hexdigest()
