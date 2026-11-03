from __future__ import annotations

import hashlib
import json

from ._m6_settings_fingerprint import m6_settings_fingerprint
from .molecular_m6_analysis import MolecularM6OrientationAnalysis


def m6_context_fingerprint(analysis: MolecularM6OrientationAnalysis) -> str:
    """Identify the shared M6 interpretation context without frame-local data."""

    if not isinstance(analysis, MolecularM6OrientationAnalysis):
        raise TypeError("analysis must be MolecularM6OrientationAnalysis.")
    payload = {
        "source_view": analysis.source_view,
        "coordinate_frame": analysis.coordinate_frame,
        "orientation_reference": analysis.orientation_reference,
        "spatial_calibration_fingerprint": (
            analysis.spatial_calibration_fingerprint
        ),
        "m6_settings_fingerprint": m6_settings_fingerprint(analysis.settings),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()
