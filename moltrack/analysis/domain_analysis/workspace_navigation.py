from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .classifier_contract import validated_text
from .models import DomainAnalysisResult, M6PublishedComponent
from .texture_abc_adapter import ABC_ORIENTATION_CLASSIFIER_ID


DomainHierarchyHighlightKind = Literal[
    "domain",
    "orientation_subdomain",
    "small_ordered_islands",
    "unassigned",
]


@dataclass(frozen=True, order=True)
class DomainHierarchyHighlight:
    """Frame-local navigation target independent from editing selection."""

    physical_frame_id: str
    target_kind: DomainHierarchyHighlightKind
    lattice_domain_id: str | None = None
    orientation_label: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "physical_frame_id",
            validated_text(self.physical_frame_id, "physical_frame_id"),
        )
        if self.target_kind not in {
            "domain",
            "orientation_subdomain",
            "small_ordered_islands",
            "unassigned",
        }:
            raise ValueError(f"Unsupported highlight target: {self.target_kind!r}.")
        domain_id = self.lattice_domain_id
        orientation = self.orientation_label
        if self.target_kind in {"domain", "orientation_subdomain"}:
            domain_id = validated_text(domain_id, "lattice_domain_id")
        elif domain_id is not None:
            raise ValueError("Auxiliary group highlights cannot name a domain.")
        if self.target_kind == "orientation_subdomain":
            orientation = validated_text(orientation, "orientation_label")
            if orientation != "Unknown" and not (
                len(orientation) == 1 and "A" <= orientation <= "Z"
            ):
                raise ValueError("orientation_label must be A-Z or Unknown.")
        elif orientation is not None:
            raise ValueError("Only subdomain highlights can name an orientation.")
        object.__setattr__(self, "lattice_domain_id", domain_id)
        object.__setattr__(self, "orientation_label", orientation)


@dataclass(frozen=True)
class SetDomainHierarchyHighlight:
    highlight: DomainHierarchyHighlight | None


def display_orientation_label(value: str) -> str:
    """Normalize the automatic classifier's unknown state for navigation."""

    return "Unknown" if value == "Unknown orientation" else value


def hierarchy_reference_diagnosis(
    active_physical_frame_id: str,
    published_result: DomainAnalysisResult | None,
    highlight: DomainHierarchyHighlight,
) -> str | None:
    """Explain why a frame-local navigation target is invalid, if it is."""

    if highlight.physical_frame_id != active_physical_frame_id:
        return "Hierarchy highlight must belong to the active frame."
    if published_result is None:
        return "Hierarchy highlight requires a published active-frame result."
    gate = published_result.m6_gate
    frame = next(
        (
            value
            for value in (() if gate is None else gate.frames)
            if value.physical_frame_id == highlight.physical_frame_id
        ),
        None,
    )
    if frame is None:
        return "Hierarchy highlight requires a published active-frame result."
    if highlight.target_kind in {"small_ordered_islands", "unassigned"}:
        return None
    component = next(
        (
            value
            for value in frame.full_domains
            if value.lattice_domain_id == highlight.lattice_domain_id
        ),
        None,
    )
    if component is None:
        return "Highlighted domain does not exist in the published result."
    if highlight.target_kind == "domain":
        return None
    labels = _published_orientation_labels(
        published_result,
        frame.frame_index,
        component,
    )
    if highlight.orientation_label not in labels:
        return "Highlighted orientation subdomain does not exist."
    return None


def _published_orientation_labels(
    result: DomainAnalysisResult,
    frame_index: int,
    component: M6PublishedComponent,
) -> set[str]:
    source_ids = set(component.source_ids)
    return {
        display_orientation_label(str(value.orientation_label))
        for outcome in (result.classifier_outcomes or ())
        if outcome.classifier_id == ABC_ORIENTATION_CLASSIFIER_ID
        and outcome.status == "completed"
        for value in outcome.molecule_classifications
        if value.frame_index == frame_index
        and value.source_id in source_ids
        and value.orientation_label is not None
    }


__all__ = [
    "DomainHierarchyHighlight",
    "DomainHierarchyHighlightKind",
    "SetDomainHierarchyHighlight",
    "display_orientation_label",
    "hierarchy_reference_diagnosis",
]
