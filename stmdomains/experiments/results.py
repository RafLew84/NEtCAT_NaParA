"""Minimal versioned result envelope and pair metrics, independent of algorithms."""

from __future__ import annotations

from collections import Counter
import math

import numpy as np

STATES = {"recognized", "ordered_untyped", "disordered", "ambiguous", "insufficient_data", "not_evaluated"}


def validate_result(result: dict) -> None:
    """Validate a per-sample result; null means unknown, never a forced category."""
    required = {"schema", "sample_id", "input_content_sha256", "run_id", "catalogue_id", "assignments"}
    if not required <= result.keys() or result["schema"] != "stmdomains-result-v1":
        raise ValueError("Missing result envelope or unsupported schema")
    seen = set()
    for row in result["assignments"]:
        fields = {"element_id", "xy", "support_xyxy", "state", "reason", "type_id", "domain_id", "orientation_deg"}
        if not fields <= row.keys():
            raise ValueError("Incomplete assignment")
        if row["element_id"] in seen:
            raise ValueError("Duplicate element assignment")
        seen.add(row["element_id"])
        state = row["state"]
        if state not in STATES:
            raise ValueError("Unknown result state")
        xy, box = np.asarray(row["xy"], float), np.asarray(row["support_xyxy"], float)
        if xy.shape != (2,) or box.shape != (4,) or not np.isfinite(xy).all() or not np.isfinite(box).all():
            raise ValueError("Invalid result geometry")
        if np.any(box[2:] <= box[:2]) or np.any(xy < box[:2]) or np.any(xy > box[2:]):
            raise ValueError("Invalid feature support")
        if state == "recognized" and (row["type_id"] is None or row["domain_id"] is None):
            raise ValueError("Recognized domains require type and domain IDs")
        if state == "ordered_untyped" and row["type_id"] is not None:
            raise ValueError("Unknown type must stay null")
        if state not in {"recognized", "ordered_untyped"} and (row["domain_id"] is not None or row["type_id"] is not None):
            raise ValueError("Unresolved/disordered results cannot have a domain/type")
        if state not in {"recognized", "ordered_untyped"} and not row["reason"]:
            raise ValueError("Refusal requires a reason")
        angle = row["orientation_deg"]
        if angle is not None and not math.isfinite(angle):
            raise ValueError("Invalid orientation")


def pair_scores(reference, predicted) -> dict:
    """Pair merge/split errors conditional on assignment, WITH refusal coverage.

    Reference IDs >0 are evaluated; <=0 are unknown/excluded. Predictions >0
    are assigned groups, <=0 refusals. Label numbers themselves are irrelevant.
    Call separately for spatial domains, orientation groups, and known types.
    """
    ref, pred = np.asarray(reference), np.asarray(predicted)
    if ref.shape != pred.shape or ref.ndim != 1:
        raise ValueError("Pair inputs must be equally sized vectors")
    if ref.dtype.kind not in 'iu' or pred.dtype.kind not in 'iu':
        raise ValueError("Pair labels must be integers")
    valid = ref > 0
    assigned = valid & (pred > 0)
    r, p = ref[assigned], pred[assigned]
    choose2 = lambda n: n * (n-1) // 2
    same_ref = sum(choose2(n) for n in Counter(r.tolist()).values())
    same_pred = sum(choose2(n) for n in Counter(p.tolist()).values())
    same_both = sum(choose2(n) for n in Counter(zip(r.tolist(), p.tolist())).values())
    different_ref = choose2(len(r)) - same_ref
    return dict(reference_elements=int(valid.sum()), assigned_elements=len(r),
                assignment_fraction=float(assigned.sum()/valid.sum()) if valid.any() else None,
                same_reference_pairs=same_ref, different_reference_pairs=different_ref,
                split_pairs=same_ref-same_both, merged_pairs=same_pred-same_both,
                split_rate=(same_ref-same_both)/same_ref if same_ref else None,
                merge_rate=(same_pred-same_both)/different_ref if different_ref else None)
