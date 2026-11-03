"""Bounded, reproducible Auto v1; a refusal is distinct from a one-class fit."""

from collections.abc import Callable, Mapping
from math import ceil
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import silhouette_score
from threadpoolctl import threadpool_limits

from stmdomains.analysis.clustering import fit_model, project_features, validate_k
from stmdomains.core.immutable import freeze_metadata

RULE = {"minimum_samples": 20, "minimum_useful_fraction": .25, "ranking_limit": 1200,
        "single_radius95_max": .15, "cluster_radius95_max": .20,
        "separation_min": .20, "silhouette_min": .50, "silhouette_tie": .02,
        "minimum_cluster_size": 8, "minimum_cluster_fraction": .05}


class AutoSelectionUnavailable(ValueError):
    """Keep the decision available even when no catalogue can be published."""

    def __init__(self, decision: Mapping[str, Any]) -> None:
        self.decision = freeze_metadata(decision)
        super().__init__(str(decision["reason"]))


def _partition(samples: NDArray[np.float64], state: Mapping[str, Any]) -> tuple[NDArray[np.float64], NDArray[Any]]:
    reduced = project_features(samples, state)
    labels = np.linalg.norm(reduced[:, None] - np.asarray(state["centers"])[None], axis=2).argmin(axis=1)
    return reduced, labels


def _geometry(samples: NDArray[np.float64], labels: NDArray[Any], k: int) -> dict[str, Any]:
    means, radii, sizes = [], [], []
    for index in range(k):
        group = samples[labels == index]
        mean = group.mean(axis=0)
        mean /= max(float(np.linalg.norm(mean)), 1e-12)
        means.append(mean)
        radii.append(float(np.quantile(np.linalg.norm(group - mean, axis=1) / np.sqrt(2), .95)))
        sizes.append(len(group))
    separation = None
    if k > 1:
        centers = np.asarray(means)
        distances = np.linalg.norm(centers[:, None] - centers[None], axis=2) / np.sqrt(2)
        separation = float(distances[np.triu_indices(k, 1)].min())
    return {"sizes": sizes, "radius95": radii, "separation": separation}


def _geometry_reasons(geometry: dict[str, Any], k: int, count: int) -> list[str]:
    reasons = []
    if k == 1:
        if max(geometry["radius95"]) > RULE["single_radius95_max"]:
            reasons.append("Jedna klasa nie jest wystarczająco zwarta.")
    else:
        minimum = max(int(RULE["minimum_cluster_size"]), ceil(RULE["minimum_cluster_fraction"] * count))
        if min(geometry["sizes"]) < minimum:
            reasons.append(f"Najmniejsza grupa ma mniej niż {minimum} próbek.")
        if max(geometry["radius95"]) > RULE["cluster_radius95_max"]:
            reasons.append("Zbyt duża zmienność wewnątrz klas.")
        if geometry["separation"] < RULE["separation_min"]:
            reasons.append("Zbyt małe rozdzielenie klas.")
    return reasons


def fit_auto_model(
    selected: NDArray[np.float64], max_k: int, check: Callable[[], None], *,
    active_count: int, useful_count: int, progress: Callable[[str], None] = lambda text: None,
) -> dict[str, Any]:
    """Return the fitted model with its decision, or raise with a recorded refusal.

    Samples are the native unit-norm square-root histograms. Counts before
    bounded sampling control availability; ranking counts describe only the subset.
    """
    validate_k(max_k)
    check()
    ranking: list[dict[str, Any]] = []
    decision: dict[str, Any] = {
        "mode": "auto", "rule_version": "auto-v1", "thresholds": dict(RULE), "seed": 24,
        "max_k": max_k, "selected_k": None, "reason": "", "ranking": ranking,
        "active_count": active_count, "useful_count": useful_count, "fit_count": len(selected),
        "useful_fraction": useful_count / active_count if active_count else 0., "ranking_count": 0,
        "ranking_sampling": "evenly_spaced", "at_upper_bound": False,
    }

    def refuse(reason: str) -> None:
        decision["reason"] = "Auto nierozstrzygnięte: " + reason
        raise AutoSelectionUnavailable(decision)

    if len(selected) < RULE["minimum_samples"] or decision["useful_fraction"] < RULE["minimum_useful_fraction"]:
        refuse(f"potrzeba co najmniej 20 użytecznych otoczeń i udziału 25%; dostępne {len(selected)} "
               f"(udział {decision['useful_fraction']:.1%}).")
    limit = int(RULE["ranking_limit"])
    samples = selected if len(selected) <= limit else selected[np.linspace(0, len(selected) - 1, limit, dtype=int)]
    decision["ranking_count"] = len(samples)
    with threadpool_limits(limits=1):
        for k in range(1, max_k + 1):
            check()
            progress(f"Auto: porównanie K{k}/{max_k} · {len(samples)} otoczeń…")
            state = fit_model(samples, k, check)
            row: dict[str, Any] = {"k": k, "silhouette": None, "eligible": False,
                                   "sizes": [], "radius95": [], "separation": None}
            if state is None:
                row["reason"] = "Za mało różnych otoczeń dla tego K."
            else:
                reduced, labels = _partition(samples, state)
                row.update(_geometry(samples, labels, k))
                reasons = _geometry_reasons(row, k, len(samples))
                if k > 1:
                    row["silhouette"] = float(silhouette_score(reduced, labels))
                    if row["silhouette"] < RULE["silhouette_min"]:
                        reasons.append("Silhouette poniżej 0,50.")
                row["eligible"] = not reasons
                row["reason"] = " ".join(reasons) if reasons else "Spełnia warunki reguły."
            ranking.append(row)
            check()
        if ranking[0]["eligible"]:
            chosen = 1
        else:
            candidates = [row for row in ranking[1:] if row["eligible"]]
            if not candidates:
                refuse("żaden z porównanych wariantów nie spełnia warunków zwartości i rozdzielenia.")
            best = max(row["silhouette"] for row in candidates)
            chosen = min(row["k"] for row in candidates if row["silhouette"] >= best - RULE["silhouette_tie"])
        check()
        progress(f"Auto: końcowe dopasowanie K{chosen} do {len(selected)} otoczeń…")
        final = fit_model(selected, chosen, check)
        if final is None:
            refuse("końcowe dopasowanie nie zachowało wybranych klas.")
        assert final is not None
        _, labels = _partition(selected, final)
        geometry = _geometry(selected, labels, chosen)
        reasons = _geometry_reasons(geometry, chosen, len(selected))
        decision["final_validation"] = {**geometry, "eligible": not reasons, "reason": " ".join(reasons)}
        if reasons:
            refuse("kontrola całego zbioru dopasowania: " + " ".join(reasons))
    check()
    decision.update(selected_k=chosen, at_upper_bound=chosen == max_k,
                    reason=("Jedna zwarta klasa wystarcza." if chosen == 1 else
                            f"K{chosen}: zwarte, rozdzielone grupy; najlepsze silhouette z tolerancją 0,02."))
    if chosen == max_k:
        decision["reason"] += " Wybrano górną granicę przeszukiwania."
    final["class_selection"] = decision
    return final
