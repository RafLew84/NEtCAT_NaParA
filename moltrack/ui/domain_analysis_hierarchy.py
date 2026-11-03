from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis.domain_analysis import (
    ABC_ORIENTATION_CLASSIFIER_ID,
    DomainAnalysisPublication,
    DomainAnalysisWorkspaceSnapshot,
    DomainHierarchyHighlight,
    EffectiveM6Domain,
    M6FrameGate,
    M6PublishedComponent,
    display_orientation_label,
)


@dataclass(frozen=True)
class DomainHierarchyNode:
    label: str
    molecule_count: int
    highlight: DomainHierarchyHighlight
    children: tuple[DomainHierarchyNode, ...] = ()


@dataclass(frozen=True)
class DomainAnalysisHierarchyPresentation:
    nodes: tuple[DomainHierarchyNode, ...]
    ledger_summary: str


class DomainAnalysisHierarchySheet(QWidget):
    """Thin hierarchy and ledger-summary adapter for one workspace snapshot."""

    highlight_requested = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("domainAnalysisHierarchySheet")
        self._current_highlight: DomainHierarchyHighlight | None = None
        layout = QVBoxLayout(self)
        self.tree = QTreeWidget(self)
        self.tree.setObjectName("domainAnalysisHierarchyTree")
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(("Domain / orientation", "Count"))
        layout.addWidget(self.tree, 1)
        self.ledger_summary_label = QLabel("Ledger: no published result", self)
        self.ledger_summary_label.setObjectName("domainAnalysisLedgerSummary")
        layout.addWidget(self.ledger_summary_label)
        self.tree.currentItemChanged.connect(self._on_current_item_changed)

    @property
    def current_highlight(self) -> DomainHierarchyHighlight | None:
        return self._current_highlight

    def render_snapshot(self, snapshot: DomainAnalysisWorkspaceSnapshot) -> None:
        presentation = build_domain_analysis_hierarchy(snapshot)
        self._current_highlight = snapshot.hierarchy_highlight
        with QSignalBlocker(self.tree):
            self.tree.clear()
            items: dict[DomainHierarchyHighlight, QTreeWidgetItem] = {}
            for node in presentation.nodes:
                item = _tree_item(node)
                self.tree.addTopLevelItem(item)
                items[node.highlight] = item
                for child in node.children:
                    child_item = _tree_item(child)
                    item.addChild(child_item)
                    items[child.highlight] = child_item
                item.setExpanded(bool(node.children))
            current = (
                None
                if snapshot.hierarchy_highlight is None
                else items.get(snapshot.hierarchy_highlight)
            )
            if current is None:
                self.tree.setCurrentItem(None)
            else:
                self.tree.setCurrentItem(current)
        self.ledger_summary_label.setText(presentation.ledger_summary)

    def _on_current_item_changed(
        self,
        current: QTreeWidgetItem | None,
        _previous: QTreeWidgetItem | None,
    ) -> None:
        value = (
            None
            if current is None
            else current.data(0, Qt.ItemDataRole.UserRole)
        )
        if value is not None and not isinstance(value, DomainHierarchyHighlight):
            raise TypeError("Hierarchy items must contain canonical highlights.")
        self.highlight_requested.emit(value)


def build_domain_analysis_hierarchy(
    snapshot: DomainAnalysisWorkspaceSnapshot,
) -> DomainAnalysisHierarchyPresentation:
    if not isinstance(snapshot, DomainAnalysisWorkspaceSnapshot):
        raise TypeError("snapshot must be a DomainAnalysisWorkspaceSnapshot.")
    published_frame = _published_frame(snapshot)
    if published_frame is None:
        return DomainAnalysisHierarchyPresentation(
            nodes=(),
            ledger_summary="Ledger: no published result",
        )
    publication, frame = published_frame
    orientation_by_source = _orientation_by_source(snapshot, publication, frame)
    projection = snapshot.domain_corrections.effective_projection
    effective_domains = () if projection is None else tuple(
        value
        for value in projection.domains
        if value.physical_frame_id == frame.physical_frame_id
    )
    effective_molecules = () if projection is None else tuple(
        value
        for value in projection.molecules
        if value.physical_frame_id == frame.physical_frame_id
    )
    island_count = (
        sum(
            value.m6_partition == "small_ordered_island"
            for value in effective_molecules
        )
        if projection is not None
        else sum(len(component.members) for component in frame.small_ordered_islands)
    )
    outside_count = (
        sum(value.m6_partition == "outside" for value in effective_molecules)
        if projection is not None
        else len(frame.outside_members)
    )
    nodes = (
        tuple(
            _effective_domain_node(domain, orientation_by_source)
            for domain in effective_domains
        )
        if projection is not None
        else tuple(
            _domain_node(frame, component, orientation_by_source)
            for component in frame.full_domains
        )
    ) + (
        DomainHierarchyNode(
            label="Small ordered islands",
            molecule_count=island_count,
            highlight=DomainHierarchyHighlight(
                frame.physical_frame_id,
                "small_ordered_islands",
            ),
        ),
        DomainHierarchyNode(
            label="Unassigned molecules",
            molecule_count=outside_count,
            highlight=DomainHierarchyHighlight(
                frame.physical_frame_id,
                "unassigned",
            ),
        ),
    )
    full_count = (
        sum(value.molecule_count for value in effective_domains)
        if projection is not None
        else sum(len(component.members) for component in frame.full_domains)
    )
    return DomainAnalysisHierarchyPresentation(
        nodes=nodes,
        ledger_summary=(
            f"Ledger: {len(frame.analyzed_source_ids)} molecules · "
            f"{full_count} full-domain · {island_count} small-island · "
            f"{outside_count} unassigned"
        ),
    )


def _domain_node(
    frame: M6FrameGate,
    component: M6PublishedComponent,
    orientation_by_source: dict[str, str],
) -> DomainHierarchyNode:
    domain_id = component.lattice_domain_id
    counts = Counter(
        orientation_by_source[source_id]
        for source_id in component.source_ids
        if source_id in orientation_by_source
    )
    children = tuple(
        DomainHierarchyNode(
            label=label,
            molecule_count=count,
            highlight=DomainHierarchyHighlight(
                physical_frame_id=frame.physical_frame_id,
                target_kind="orientation_subdomain",
                lattice_domain_id=domain_id,
                orientation_label=label,
            ),
        )
        for label, count in sorted(counts.items(), key=_orientation_sort_key)
    )
    return DomainHierarchyNode(
        label=f"Domain {domain_id}",
        molecule_count=len(component.members),
        highlight=DomainHierarchyHighlight(
            physical_frame_id=frame.physical_frame_id,
            target_kind="domain",
            lattice_domain_id=domain_id,
        ),
        children=children,
    )


def _effective_domain_node(
    domain: EffectiveM6Domain,
    orientation_by_source: dict[str, str],
) -> DomainHierarchyNode:
    counts = Counter(
        orientation_by_source[source_id]
        for source_id in domain.source_ids
        if source_id in orientation_by_source
    )
    label = f"Domain {domain.lattice_domain_id}"
    if domain.is_tombstone:
        label += " (tombstone)"
    return DomainHierarchyNode(
        label=label,
        molecule_count=domain.molecule_count,
        highlight=DomainHierarchyHighlight(
            physical_frame_id=domain.physical_frame_id,
            target_kind="domain",
            lattice_domain_id=domain.lattice_domain_id,
        ),
        children=tuple(
            DomainHierarchyNode(
                label=orientation_label,
                molecule_count=count,
                highlight=DomainHierarchyHighlight(
                    physical_frame_id=domain.physical_frame_id,
                    target_kind="orientation_subdomain",
                    lattice_domain_id=domain.lattice_domain_id,
                    orientation_label=orientation_label,
                ),
            )
            for orientation_label, count in sorted(
                counts.items(),
                key=_orientation_sort_key,
            )
        ),
    )
def _published_frame(
    snapshot: DomainAnalysisWorkspaceSnapshot,
) -> tuple[DomainAnalysisPublication, M6FrameGate] | None:
    publication = snapshot.published
    gate = None if publication is None else publication.result.m6_gate
    frame = next(
        (
            value
            for value in (() if gate is None else gate.frames)
            if value.physical_frame_id == snapshot.active_physical_frame_id
        ),
        None,
    )
    return (
        None
        if publication is None or frame is None
        else (publication, frame)
    )


def _orientation_by_source(
    snapshot: DomainAnalysisWorkspaceSnapshot,
    publication: DomainAnalysisPublication,
    frame: M6FrameGate,
) -> dict[str, str]:
    projection = snapshot.domain_corrections.effective_projection
    if projection is not None:
        return {
            source_id: subdomain.orientation_label
            for subdomain in projection.orientation_subdomains
            if subdomain.physical_frame_id == frame.physical_frame_id
            for source_id in subdomain.source_ids
        }
    return {
        value.source_id: display_orientation_label(value.orientation_label)
        for outcome in (publication.result.classifier_outcomes or ())
        if outcome.classifier_id == ABC_ORIENTATION_CLASSIFIER_ID
        and outcome.status == "completed"
        for value in outcome.molecule_classifications
        if value.frame_index == frame.frame_index
        and value.physical_frame_id == frame.physical_frame_id
        and value.m6_partition == "full_domain"
        and value.orientation_label is not None
    }


def _orientation_sort_key(value: tuple[str, int]) -> tuple[int, str]:
    label, _count = value
    return (1 if label == "Unknown" else 0, label)


def _tree_item(node: DomainHierarchyNode) -> QTreeWidgetItem:
    item = QTreeWidgetItem((node.label, str(node.molecule_count)))
    item.setData(0, Qt.ItemDataRole.UserRole, node.highlight)
    return item


__all__ = [
    "DomainAnalysisHierarchyPresentation",
    "DomainAnalysisHierarchySheet",
    "DomainHierarchyNode",
    "build_domain_analysis_hierarchy",
]
