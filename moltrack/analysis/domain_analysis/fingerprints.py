from __future__ import annotations

import hashlib
import json


def canonical_sha256(payload: object) -> str:
    """Hash a finite JSON-compatible payload with one canonical encoding."""

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
