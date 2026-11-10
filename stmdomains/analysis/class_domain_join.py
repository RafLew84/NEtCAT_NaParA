"""Join touching same-class regions explicitly, without growing raster support."""

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

import numpy as np
from numpy.typing import NDArray

from stmdomains.analysis.manual_partition import merge_labels
from stmdomains.core.analysis_result import MoleculeAssignment
from stmdomains.core.annotations import Detection


def join_class_domains(labels: NDArray[np.int32] | None, assignments: Mapping[str, MoleculeAssignment],
                       detections: tuple[Detection, ...], selection: set[str], target_class: str
                       ) -> tuple[dict[str, MoleculeAssignment], NDArray[np.int32] | None, list[dict[str, Any]]]:
    """Use 8-connected contact, matching explicit domain merge; keep the smallest ID.

    Only components reached from the selection are changed. Unclassified and
    class-only points cannot form raster domains, and separated regions stay apart.
    """
    result = dict(assignments)
    if labels is None or not target_class:
        return result, labels, []
    domains = {a.domain_local_id for a in assignments.values() if a.class_id == target_class and a.domain_local_id}
    seeds = {assignments[key].domain_local_id for key in selection} & domains
    graph: dict[int, set[int]] = {key: set() for key in domains}
    allowed = np.isin(labels, sorted(domains))
    for first, second in ((np.s_[:-1, :], np.s_[1:, :]), (np.s_[:, :-1], np.s_[:, 1:]),
                           (np.s_[:-1, :-1], np.s_[1:, 1:]), (np.s_[:-1, 1:], np.s_[1:, :-1])):
        left, right = labels[first], labels[second]
        touching = allowed[first] & allowed[second] & (left != right)
        pairs = np.unique(np.column_stack((left[touching], right[touching])), axis=0)
        for a, b in pairs.tolist():
            graph[a].add(b)
            graph[b].add(a)
    joined = []
    visited: set[int] = set()
    for seed in sorted(seeds):
        if seed in visited:
            continue
        component, pending = set(), [seed]
        while pending:
            member = pending.pop()
            if member in component:
                continue
            component.add(member)
            pending.extend(graph[member] - component)
        visited.update(component)
        if len(component) < 2:
            continue
        target = min(component)
        labels = merge_labels(labels, component, target, detections, result)
        result = {key: replace(value, domain_local_id=target) if value.domain_local_id in component else value
                  for key, value in result.items()}
        joined.append({'source_domains': sorted(component), 'target_domain': target})
    return result, labels, joined
