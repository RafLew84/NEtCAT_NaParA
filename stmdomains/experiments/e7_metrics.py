"""E7 relation diagnostics, without treating unknown/zero labels as negatives."""
from __future__ import annotations

import numpy as np

from .e2_metrics import pair_summary


def relation_metrics(different_score, same, eligible, *, classifier=False):
    """High score means different positive domains; ties at .5 mean different."""
    score, same, eligible = np.asarray(different_score), np.asarray(same), np.asarray(eligible)
    result = pair_summary(score, same, eligible, max_curve_points=64)
    result.pop('roc')
    result.pop('pr')
    keep = eligible & np.isfinite(score)
    result['fixed_threshold'] = None
    if classifier:
        if np.any((score[keep] < 0) | (score[keep] > 1)):
            raise ValueError('Classifier score must be in [0,1]')
        positive, prediction = ~same[keep], score[keep] >= .5
        tp, tn = int((positive & prediction).sum()), int((~positive & ~prediction).sum())
        fp, fn = int((~positive & prediction).sum()), int((positive & ~prediction).sum())
        def ratio(a, b): return a / b if b else None
        sensitivity, specificity = ratio(tp, tp + fn), ratio(tn, tn + fp)
        result['fixed_threshold'] = dict(different_score_threshold=.5,
            tp=tp, tn=tn, fp=fp, fn=fn, different_recall=sensitivity,
            same_recall=specificity, false_different_rate=ratio(fp, tn + fp),
            false_same_rate=ratio(fn, tp + fn), accuracy=ratio(tp + tn, tp + tn + fp + fn),
            balanced_accuracy=(sensitivity + specificity) / 2
                if sensitivity is not None and specificity is not None else None)
    return result
