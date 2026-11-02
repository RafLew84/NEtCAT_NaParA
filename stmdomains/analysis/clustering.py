"""Fit a local K5 catalogue and retain its actual parameters for provenance."""

from collections.abc import Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from threadpoolctl import threadpool_limits


def fit_classes(
    features: NDArray[np.float64], valid: NDArray[np.bool_], fit_mask: NDArray[np.bool_],
    check: Callable[[], None],
) -> tuple[NDArray[Any], NDArray[np.bool_], dict[str, NDArray[Any]], dict[str, Any]] | None:
    selected = features[fit_mask]
    if len(selected) < 5 or len(np.unique(np.round(selected, 10), axis=0)) < 5:
        return None
    components = min(24, len(selected) - 1, features.shape[1])
    check()
    with threadpool_limits(limits=1):
        pca = PCA(n_components=components, svd_solver="full", random_state=24)
        pca.fit(selected)
        reduced = pca.transform(features)
        check()
        model = KMeans(n_clusters=5, n_init=20, random_state=24).fit(reduced[fit_mask])
    check()
    if len(np.unique(model.labels_)) != 5:
        return None
    distances = np.linalg.norm(reduced[:, None] - model.cluster_centers_[None], axis=2)
    labels = distances.argmin(axis=1)
    ordered = np.sort(distances, axis=1)
    margin = (ordered[:, 1] - ordered[:, 0]) / np.maximum(ordered[:, 1], 1e-9)
    within = distances[np.arange(len(features)), labels]
    radii = np.asarray([np.quantile(within[fit_mask & (labels == index)], .95) for index in range(5)])
    reliable = valid & (margin >= .075) & (within <= 1.10 * radii[labels] + 1e-12)
    confidence = np.clip(margin, 0, 1) * np.exp(-.5 * (within / np.maximum(radii[labels], 1e-9)) ** 2)
    state = {"pca_mean": pca.mean_.tolist(), "pca_components": pca.components_.tolist(),
             "centers": model.cluster_centers_.tolist(), "class_radius95": radii.tolist(),
             "fit_count": int(fit_mask.sum()), "pca_components_count": components,
             "fit_scope": "current_frame", "seed": 24, "k": 5}
    details = {"centroid_margin": margin, "centroid_distance": within, "class_confidence": confidence}
    return labels, reliable, details, state
