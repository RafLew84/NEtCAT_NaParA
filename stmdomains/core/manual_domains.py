"""One source-bound manual variant with immutable previews and undo/redo."""

from dataclasses import replace
from typing import Any
from uuid import uuid4

from stmdomains.analysis.features import prepare_points
from stmdomains.analysis.config import PARAMETERS
from stmdomains.analysis.manual_regions import manual_regions
from stmdomains.core.analysis_result import AnalysisInput, FrameAnalysis, MoleculeAssignment

MANUAL_METHOD = 'manual_membership_v1'
EXCLUDED = ('outside_field', 'suppressed_duplicate')


def _source_metadata(member: MoleculeAssignment) -> dict[str, Any]:
    return {'domain_local_id': member.domain_local_id, 'class_id': member.class_id,
            'status': member.status, 'rejection_reason': member.rejection_reason}


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

    def preview(self, operation: str, selection: tuple[str, ...], target: int = 0) -> FrameAnalysis:
        self._pending = None
        selected = set(selection)
        if not selected or not selected <= self.eligible_ids:
            raise ValueError('Wybierz aktywne molekuły; duplikaty i punkty poza polem są wyłączone.')
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
                status='domain' if target else 'unassigned', class_id='',
                metadata={**member.metadata, 'manual_source': _source_metadata(source_member)})
        source = self._history[0].assignments
        affected = {target, *(self.current.assignments[key].domain_local_id for key in selected)} - {0}
        for domain in affected:
            members = [key for key, a in assignments.items() if a.domain_local_id == domain]
            classes = {source[key].class_id for key in members}
            common = next(iter(classes)) if len(classes) == 1 else ''
            for key in members:
                source_member = source[key]
                assignments[key] = replace(assignments[key], class_id=common,
                    metadata={**assignments[key].metadata, 'manual_source': _source_metadata(source_member)})
        height, width = self.data.frame.image.shape
        labels, unsupported = manual_regions(self.data.annotations.detections, assignments, (height, width))
        self._revision += 1
        original = self.original
        self._pending = FrameAnalysis(
            self.data.series_id, self.data.frame.working_index, self.data.frame.source_index,
            'complete', 'Korekta ręczna · tylko w tej sesji.', assignments,
            original.classes if original else (), {'domain_method': MANUAL_METHOD},
            {'manual_edit': {'variant_id': self.identifier, 'revision': self._revision,
                             'operation': operation, 'selection': sorted(selected), 'target': target,
                             'automatic_available': original is not None,
                             'source_analysis_id': original.metadata.get('analysis_id', '') if original else '',
                             'source_parameters': dict(original.parameters) if original else {},
                             'unsupported_domains': unsupported,
                             'geometry_rule': 'finite_voronoi_0.8_nn_minimum_3_noncollinear'}},
            labels, catalogue=original.catalogue if original else None)
        return self._pending

    def apply(self, preview: FrameAnalysis) -> None:
        if preview is not self._pending:
            raise ValueError('Podgląd jest nieaktualny. Przygotuj go ponownie.')
        self._history[self._cursor + 1:] = [preview]
        self._cursor += 1
        self._pending = None

    def undo(self) -> None:
        self._pending = None
        self._cursor = max(0, self._cursor - 1)

    def redo(self) -> None:
        self._pending = None
        if self.can_redo:
            self._cursor += 1
