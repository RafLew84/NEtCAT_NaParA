from __future__ import annotations

import json
from dataclasses import asdict
from hashlib import sha256

from .first_shell_graph import FIRST_SHELL_GRAPH_ALGORITHM_VERSION, FirstShellGraph


def first_shell_graph_fingerprint(graph: FirstShellGraph) -> str:
    """Fingerprint the complete normalized first-shell graph contract."""

    if not isinstance(graph, FirstShellGraph):
        raise TypeError("graph must be a FirstShellGraph.")
    payload = {
        "schema": FIRST_SHELL_GRAPH_ALGORITHM_VERSION,
        "graph": asdict(graph),
    }
    encoded = json.dumps(
        payload,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()
