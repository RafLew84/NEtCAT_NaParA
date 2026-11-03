"""Fit once and apply descriptor classes without retraining the saved projection."""

from collections.abc import Callable, Mapping
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from threadpoolctl import threadpool_limits

from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings


def validate_k(k: int) -> None:
    if type(k) is not int or not 1 <= k <= 8:
        raise ValueError("Liczba klas K musi być liczbą całkowitą od 1 do 8.")


def project_features(features: NDArray[np.float64], state: Mapping[str, Any]) -> NDArray[np.float64]:
    if state["projection"] == "identity":
        return features
    components = np.asarray(state["pca_components"])
    # Use the same operation order as sklearn PCA.transform.
    return features @ components.T - np.asarray(state["pca_mean"])[None, :] @ components.T


def fit_model(
    selected: NDArray[np.float64], k: int, check: Callable[[], None],
) -> dict[str, Any] | None:
    validate_k(k)
    if len(selected) < k or len(np.unique(np.round(selected, 10), axis=0)) < k:
        return None
    check()
    components = min(24, len(selected) - 1, selected.shape[1])
    # One sample or a constant K1 set has no variance for PCA. Retain the
    # descriptor space so a different pattern can still be refused by radius.
    use_pca = components > 0 and float(np.ptp(selected, axis=0).max()) > 1e-12
    with threadpool_limits(limits=1):
        if use_pca:
            pca = PCA(n_components=components, svd_solver="full", random_state=24)
            pca.fit(selected)
            state = {"projection": "pca", "pca_mean": pca.mean_.tolist(),
                     "pca_components": pca.components_.tolist(), "pca_components_count": components}
        else:
            state = {"projection": "identity", "pca_mean": [], "pca_components": [], "pca_components_count": 0}
        reduced = project_features(selected, state)
        check()
        model = KMeans(n_clusters=k, n_init=20, random_state=24).fit(reduced)
    check()
    if len(np.unique(model.labels_)) != k:
        return None
    distances = np.linalg.norm(reduced[:, None] - model.cluster_centers_[None], axis=2)
    labels = distances.argmin(axis=1)
    if len(np.unique(labels)) != k:
        return None
    within = distances[np.arange(len(selected)), labels]
    radii = [float(np.quantile(within[labels == index], .95)) for index in range(k)]
    state.update({"centers": model.cluster_centers_.tolist(), "class_radius95": radii,
                  "fit_count": len(selected), "fit_scope": "current_frame", "seed": 24, "k": k,
                  "margin_rule": "nearest_vs_second" if k > 1 else "not_applicable_k1"})
    return state


def apply_classes(
    features: NDArray[np.float64], valid: NDArray[np.bool_], state: Mapping[str, Any],
    check: Callable[[], None], *, acceptance: ClassAcceptanceSettings = ClassAcceptanceSettings(),
) -> tuple[NDArray[Any], NDArray[np.bool_], dict[str, NDArray[Any]]]:
    check()
    with threadpool_limits(limits=1):
        reduced = project_features(features, state)
    distances = np.linalg.norm(reduced[:, None] - np.asarray(state["centers"])[None], axis=2)
    labels = distances.argmin(axis=1)
    ordered = np.sort(distances, axis=1)
    # K1 has no competing centroid: omit the margin test, retain the radius test.
    margin = ((ordered[:, 1] - ordered[:, 0]) / np.maximum(ordered[:, 1], 1e-9)
              if state["k"] > 1 else np.ones(len(features)))
    within = distances[np.arange(len(features)), labels]
    radii = np.asarray(state["class_radius95"])
    margin_passed = (margin >= acceptance.class_margin) if state["k"] > 1 else np.ones(len(features), bool)
    radius_limit = acceptance.class_radius_multiplier * radii[labels]
    radius_passed = within <= radius_limit + 1e-12
    reliable = valid & margin_passed & radius_passed
    confidence = np.clip(margin, 0, 1) * np.exp(-.5 * (within / np.maximum(radii[labels], 1e-9)) ** 2)
    check()
    return labels, reliable, {
        "centroid_margin": margin, "centroid_distance": within, "class_confidence": confidence,
        "class_margin_passed": margin_passed, "class_radius_passed": radius_passed,
        "class_radius_limit": radius_limit, "class_reference_radius": radii[labels], "descriptor_valid": valid,
    }


def fit_classes(
    features: NDArray[np.float64], valid: NDArray[np.bool_], fit_mask: NDArray[np.bool_],
    check: Callable[[], None], *, k: int = 5,
) -> tuple[NDArray[Any], NDArray[np.bool_], dict[str, NDArray[Any]], dict[str, Any]] | None:
    state = fit_model(features[fit_mask], k, check)
    if state is None:
        return None
    labels, reliable, details = apply_classes(features, valid, state, check)
    return labels, reliable, details, state
