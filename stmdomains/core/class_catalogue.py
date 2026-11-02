"""An immutable fitted catalogue, its source scope and reproducible version."""

from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Literal

from stmdomains.core.immutable import freeze_metadata, plain_metadata

FitScope = Literal["current_frame", "selected_range", "whole_series"]


@dataclass(frozen=True)
class ClassCatalogue:
    series_id: str
    scope: FitScope
    frame_indices: tuple[int, ...]
    state: Mapping[str, Any] = field(repr=False)
    provenance: Mapping[str, Any] = field(repr=False)
    parameters: Mapping[str, Any] = field(repr=False)
    identifier: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("state", "provenance", "parameters"):
            object.__setattr__(self, name, freeze_metadata(getattr(self, name)))
        payload = {"scope": self.scope, "frames": self.frame_indices,
                   "state": self.state, "provenance": self.provenance, "parameters": self.parameters}
        # Runtime session UUID guards reuse; it is not part of the content version.
        encoded = json.dumps(plain_metadata(payload), sort_keys=True, allow_nan=False).encode()
        object.__setattr__(self, "identifier", hashlib.sha256(encoded).hexdigest())

    @property
    def k(self) -> int:
        return int(self.state["k"])

    def metadata(self) -> dict[str, Any]:
        return {"fit_scope": self.scope, "fit_working_indices": self.frame_indices,
                "fit_frames": self.provenance["frames"], "fit_sampling": self.provenance["sampling"],
                "model_state": self.state, "model_id": self.identifier,
                "descriptor_scale_policy": "per-frame median NN spacing after duplicate suppression"}
