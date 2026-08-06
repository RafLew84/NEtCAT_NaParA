from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path
import tempfile
from typing import Any


_JSON_WRITE_BUFFER_CHARS = 1024 * 1024


def write_json_atomically(path: Path, payload: Mapping[str, Any]) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            encoder = json.JSONEncoder(indent=2, ensure_ascii=False)
            buffered_chunks: list[str] = []
            buffered_character_count = 0
            for chunk in encoder.iterencode(payload):
                buffered_chunks.append(chunk)
                buffered_character_count += len(chunk)
                if buffered_character_count < _JSON_WRITE_BUFFER_CHARS:
                    continue
                handle.write("".join(buffered_chunks))
                buffered_chunks.clear()
                buffered_character_count = 0
            if buffered_chunks:
                handle.write("".join(buffered_chunks))
            handle.write("\n")
        os.replace(temporary_path, path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
