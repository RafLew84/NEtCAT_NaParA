from __future__ import annotations

import hashlib
import json

from .m6_settings import MolecularM6OrientationAnalysisSettings


def m6_settings_fingerprint(settings: MolecularM6OrientationAnalysisSettings) -> str:
    """Return a stable fingerprint of the complete M6 settings contract."""

    if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
        raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
    payload = json.dumps(
        settings.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()
