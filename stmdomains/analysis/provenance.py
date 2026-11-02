"""Content identity for reuse of fitted per-molecule classes."""

import hashlib
import json

import numpy as np

from stmdomains.core.analysis_result import AnalysisInput


def input_fingerprint(data: AnalysisInput) -> str:
    image = np.asarray(data.frame.image, dtype=float)
    digest = hashlib.sha256()
    digest.update(str(image.shape).encode())
    digest.update(np.ascontiguousarray(image, dtype="<f8").tobytes())
    digest.update(data.annotations.detection_state.encode())
    for item in sorted(data.annotations.detections, key=lambda item: item.detection_id):
        digest.update(json.dumps((item.detection_id, item.center_xy, item.outside_field,
                                  item.metadata.get("origin"), item.metadata.get("confidence")),
                                 ensure_ascii=False, default=str).encode())
    return digest.hexdigest()
