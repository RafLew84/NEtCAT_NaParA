"""One source-bound manual variant with immutable previews and undo/redo."""

from dataclasses import replace
from collections.abc import Mapping, Collection
from typing import Any
from uuid import uuid4

import numpy as np
from numpy.typing import NDArray

from stmdomains.analysis.features import prepare_points
from stmdomains.analysis.config import PARAMETERS
from stmdomains.analysis.manual_regions import manual_regions
from stmdomains.analysis.manual_partition import split_labels, merge_labels
from stmdomains.core.analysis_result import AnalysisInput, FrameAnalysis, MoleculeAssignment
from stmdomains.core.manual_classes import ManualClassList

MANUAL_METHOD = 'manual_membership_v1'
EXCLUDED = ('outside_field', 'suppressed_duplicate')


def _source_metadata(member: MoleculeAssignment) -> dict[str, Any]:
    return {'domain_local_id': member.domain_local_id, 'class_id': member.class_id,
            'status': member.status, 'rejection_reason': member.rejection_reason}


def domain_record(domain: int, assignments: Mapping[str, MoleculeAssignment]) -> dict[str, Any]:
    """One membership/class summary shared by operation history and its UI."""
    members = sorted(key for key, member in assignments.items() if member.domain_local_id == domain)
    classes = {assignments[key].class_id for key in members}
    return {'domain_id': domain, 'member_ids': members,
            'class_id': next(iter(classes)) if len(classes) == 1 else ''}


class ManualDomains:
    def __init__(self, data: AnalysisInput, original: FrameAnalysis | None = None) -> None:
        if (data.frame.image.ndim != 2 or data.frame.image.size > PARAMETERS['maximum_image_pixels']
                or len(data.annotations.detections) > PARAMETERS['maximum_input_detections']):
            raise ValueError('Edycja wymaga obrazu 2D do 4 mln pikseli i do 3000 oznaczeń.')
        if original is not None and (original.series_id, original.working_index, original.source_index) != (
                data.series_id, data.frame.working_index, data.frame.source_index):
            raise ValueError('Wynik i oznaczenia należą do różnych klatek.')
        self.data, self.original = data, original
        self.identifier = uuid4().hex
        self._pending: FrameAnalysis | None = None
        self._preview_class_list: ManualClassList | None = None
        self._revision = 0
        self._cursor = 0
        spatial = self._without_analysis()
        if original is not None and set(original.assignments) != set(spatial.assignments):
            raise ValueError('Wynik nie odpowiada oznaczeniom tej klatki.')
        base = original or spatial
        assignments = dict(base.assignments)
        for key, member in spatial.assignments.items():
            if member.status in EXCLUDED and assignments[key].status not in EXCLUDED:
                source = assignments[key]
                assignments[key] = replace(source, domain_local_id=0, class_id='', status=member.status,
                    metadata={**source.metadata, **member.metadata, 'manual_source': _source_metadata(source)})
        self._history = [replace(base, assignments=assignments) if assignments != base.assignments else base]

    def _without_analysis(self) -> FrameAnalysis:
        detections = self.data.annotations.detections
        identifiers = [d.detection_id for d in detections]
        if len(set(identifiers)) != len(identifiers) or any(not key for key in identifiers):
            raise ValueError('Oznaczenia wymagają jednoznacznych ID.')
        shape = self.data.frame.image.shape
        _, _, _, excluded = prepare_points(detections, (shape[0], shape[1]), lambda: None)
        assignments = {}
        for detection in detections:
            status, metadata = excluded.get(detection.detection_id, ('unassigned', {}))
            assignments[detection.detection_id] = MoleculeAssignment(
                detection.detection_id, status=status,
                rejection_reason=status if status in EXCLUDED else 'not_analysed', metadata=metadata)
        return FrameAnalysis(self.data.series_id, self.data.frame.working_index,
                             self.data.frame.source_index, 'complete', 'Brak analizy automatycznej.', assignments)

    @property
    def current(self) -> FrameAnalysis:
        return self._history[self._cursor]

    @property
    def changed(self) -> bool:
        return self._cursor > 0

    @property
    def can_redo(self) -> bool:
        return self._cursor + 1 < len(self._history)

    @property
    def eligible_ids(self) -> frozenset[str]:
        return frozenset(key for key, value in self.current.assignments.items() if value.status not in EXCLUDED)

    def preview(self, operation: str, selection: tuple[str, ...], target: int = 0, *,
                class_list: ManualClassList | None = None) -> FrameAnalysis:
        self._pending = None
        self._preview_class_list = class_list or self.current.class_list
        selected = set(selection)
        if not selected or not selected <= self.eligible_ids:
            raise ValueError('Wybierz aktywne molekuły; duplikaty i punkty poza polem są wyłączone.')
        if operation == 'split':
            return self._split(selected)
        if operation == 'merge':
            return self._merge(selected, target)
        assignments = dict(self.current.assignments)
        domains = {a.domain_local_id for a in assignments.values() if a.domain_local_id > 0}
        if operation == 'new':
            target = max(domains, default=0) + 1
        elif operation in ('add', 'move') and target not in domains:
            raise ValueError('Wybierz istniejącą domenę docelową.')
        elif operation not in ('add', 'move', 'remove'):
            raise ValueError('Nieznana operacja edycji.')
        if operation in ('new', 'add') and any(
                assignments[key].domain_local_id not in (0, target) for key in selected):
            raise ValueError('Molekuły należą do innej domeny. Użyj jawnej operacji Przenieś.')
        target = 0 if operation == 'remove' else target
        if all(assignments[key].domain_local_id == target for key in selected):
            raise ValueError('Operacja nie zmieni żadnego przypisania.')
        for key in selected:
            member = assignments[key]
            source_member = self._history[0].assignments[key]
            assignments[key] = replace(member, domain_local_id=target,
                status='domain' if target else 'unassigned',
                class_id=member.class_id if self.current.class_list is not None else '',
                metadata={**member.metadata, 'manual_source': _source_metadata(source_member)})
        source = self.current.assignments if self.current.class_list is not None else self._history[0].assignments
        affected = {target, *(self.current.assignments[key].domain_local_id for key in selected)} - {0}
        for domain in affected:
            members = [key for key, a in assignments.items() if a.domain_local_id == domain]
            classes = {source[key].class_id for key in members}
            common = next(iter(classes)) if len(classes) == 1 else ''
            for key in members:
                source_member = self._history[0].assignments[key]
                assignments[key] = replace(assignments[key], class_id=common,
                    metadata={**assignments[key].metadata, 'manual_source': _source_metadata(source_member)})
        height, width = self.data.frame.image.shape
        labels, unsupported = manual_regions(self.data.annotations.detections, assignments, (height, width))
        return self._make_preview(assignments, labels, operation, selected, target,
            {'unsupported_domains': unsupported, 'geometry_rule': 'finite_voronoi_0.8_nn_minimum_3_noncollinear'})

    def _split(self, selected: set[str]) -> FrameAnalysis:
        current = self.current.assignments
        sources = {current[key].domain_local_id for key in selected}
        if len(sources) != 1 or 0 in sources:
            raise ValueError('Podział wymaga części jednej domeny. Wybór zawiera kilka domen lub molekuły bez domeny.')
        source = next(iter(sources))
        record = domain_record(source, current)
        if selected == set(record['member_ids']):
            raise ValueError('Wybrano całą domenę. Do podziału zaznacz tylko część jej molekuł.')
        target = max(a.domain_local_id for a in current.values()) + 1
        assignments = dict(current)
        for key in record['member_ids']:
            assignments[key] = replace(current[key], domain_local_id=target if key in selected else source,
                class_id=record['class_id'], metadata={**current[key].metadata,
                    'manual_source': _source_metadata(self._history[0].assignments[key])})
        labels = split_labels(self.current.domain_labels, self.data.annotations.detections, current,
                              source, target, selected)
        return self._make_preview(assignments, labels, 'split', selected, target,
            {'source_domains': [record], 'target_domains': [domain_record(d, assignments) for d in (source, target)],
             'geometry_rule': 'partition_existing_support_nearest_member_v1'})

    def _make_preview(self, assignments: Mapping[str, MoleculeAssignment], labels: NDArray[np.int32] | None,
                      operation: str, selected: set[str], target: int, details: dict[str, Any]) -> FrameAnalysis:
        self._revision += 1
        original = self.original
        domains = {a.domain_local_id for a in assignments.values() if a.domain_local_id > 0}
        visible = set(np.unique(labels)) if labels is not None else set()
        details.setdefault('unsupported_domains', tuple(sorted(domains - visible)))
        self._pending = FrameAnalysis(
            self.data.series_id, self.data.frame.working_index, self.data.frame.source_index,
            'complete', 'Korekta ręczna · tylko w tej sesji.', assignments,
            original.classes if original else (), {'domain_method': MANUAL_METHOD},
            {'manual_edit': {'variant_id': self.identifier, 'revision': self._revision,
                             'operation': operation, 'selection': sorted(selected), 'target': target,
                             'automatic_available': original is not None,
                             'source_analysis_id': original.metadata.get('analysis_id', '') if original else '',
                             'source_parameters': dict(original.parameters) if original else {},
                             **details}},
            labels, catalogue=original.catalogue if original else None, class_list=self._preview_class_list)
        return self._pending

    def _merge(self, selected: set[str], target: int) -> FrameAnalysis:
        current = self.current.assignments
        sources = {current[key].domain_local_id for key in selected}
        if 0 in sources or len(sources) < 2:
            raise ValueError('Wskaż molekuły z co najmniej dwóch domen, bez punktów nieprzypisanych.')
        target = target or min(sources)
        if target not in sources:
            raise ValueError('Docelowe ID musi należeć do jednej z wybranych domen.')
        labels = merge_labels(self.current.domain_labels, sources, target,
                              self.data.annotations.detections, current)
        records = [domain_record(d, current) for d in sorted(sources)]
        classes = {r['class_id'] for r in records}
        common = next(iter(classes)) if len(classes) == 1 else ''
        assignments = dict(current)
        for record in records:
            for key in record['member_ids']:
                assignments[key] = replace(current[key], domain_local_id=target, class_id=common,
                    metadata={**current[key].metadata, 'manual_source': _source_metadata(self._history[0].assignments[key])})
        return self._make_preview(assignments, labels, 'merge', selected, target,
            {'source_domains': records, 'target_domains': [domain_record(target, assignments)],
             'geometry_rule': 'union_existing_support_8_connected_v1'})

    def validate_preview(self, preview: FrameAnalysis) -> None:
        if preview is not self._pending:
            raise ValueError('Podgląd jest nieaktualny. Przygotuj go ponownie.')

    def apply(self, preview: FrameAnalysis) -> None:
        self.validate_preview(preview)
        self._history[self._cursor + 1:] = [preview]
        self._cursor += 1
        self._pending = None

    def preview_classes(self, labels: ManualClassList, operation: str, *, target: str = '',
                        name: str = '', color: str = '', selection: tuple[str, ...] = (),
                        whole_domains: bool = False, occupied: Collection[str] = (),
                        operation_details: Mapping[str, Any] | None = None) -> FrameAnalysis:
        self._pending = None
        self._preview_class_list = labels
        revised = labels if operation == 'assign' else labels.edit(
            'create' if operation == 'create_assign' else operation, target, name=name, color=color,
            occupied=set(occupied) | {a.class_id for a in self.current.assignments.values()})
        if operation == 'create_assign':
            target = revised.classes[-1].class_id
        assignments = dict(self.current.assignments)
        regions = self.current.domain_labels
        selected = set(selection) if operation in ('assign', 'create_assign') else set()
        splits = []
        if operation in ('assign', 'create_assign'):
            if target and target not in {c.class_id for c in revised.classes}:
                raise ValueError('Wybierz klasę z bieżącej listy.')
            if not selected or not selected <= self.eligible_ids:
                raise ValueError('Wybierz aktywne molekuły.')
            domains = {assignments[key].domain_local_id for key in selected}
            if whole_domains:
                if 0 in domains:
                    raise ValueError('W trybie całych domen wybierz członków domen, bez punktów nieprzypisanych.')
                selected = {key for key, a in assignments.items() if a.domain_local_id in domains}
            changed = {key for key in selected if assignments[key].class_id != target}
            if not changed:
                raise ValueError('Wybrane molekuły mają już tę klasę.')
            next_domain = max((a.domain_local_id for a in assignments.values()), default=0) + 1
            for domain in sorted(domains - {0}):
                members = {key for key, a in assignments.items() if a.domain_local_id == domain}
                part = members & changed
                if part and part != members:
                    regions = split_labels(regions, self.data.annotations.detections, assignments,
                                           domain, next_domain, part)
                    for key in part:
                        assignments[key] = replace(assignments[key], domain_local_id=next_domain)
                    splits.append({'source_domain': domain, 'target_domain': next_domain,
                                   'member_ids': sorted(part)})
                    next_domain += 1
            for key in changed:
                source = self.current.assignments[key]
                assignments[key] = replace(assignments[key], class_id=target, provisional_class_id='',
                    metadata={'manual_source': source.metadata.get('manual_source',
                        _source_metadata(self._history[0].assignments[key])),
                        'manual_class_source': {'class_id': source.class_id,
                            'provisional_class_id': source.provisional_class_id, 'metadata': source.metadata},
                        'class_assignment_origin': 'manual'})
        preview = self._make_preview(assignments, regions, 'class_' + operation, selected, 0,
            {'class_list_id': revised.identifier, 'class_list_before': labels.version,
             'class_list_after': revised.version, 'class_target': target, 'splits': splits,
             'whole_domains': whole_domains, **(operation_details or {})})
        self._pending = replace(preview, class_list=revised)
        return self._pending

    def undo(self) -> None:
        self._pending = None
        self._cursor = max(0, self._cursor - 1)

    def redo(self) -> None:
        self._pending = None
        if self.can_redo:
            self._cursor += 1
