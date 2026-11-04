"""Versioned result records and a bounded, lazy cache of saved frame masks."""

from collections import OrderedDict
from collections.abc import Iterator, Mapping
from dataclasses import asdict, replace
import io
from pathlib import Path
from threading import RLock
from typing import Any
import zipfile

import numpy as np

from stmdomains.core.analysis_result import FrameAnalysis, MoleculeAssignment, ResultClass
from stmdomains.core.class_catalogue import ClassCatalogue
from stmdomains.core.frame_presentation import FramePresenter
from stmdomains.core.immutable import plain_metadata
from stmdomains.core.project import ProjectAnalysis
from stmdomains.core.series import Series
from stmdomains.analysis.provenance import input_fingerprint
from stmdomains.io.project_masks import check_labels, load_labels
from stmdomains.io.project_barriers import check_barriers, load_barriers, save_barriers
from stmdomains.analysis.descriptor_settings import DescriptorSettings
from stmdomains.analysis.barrier_settings import BarrierSettings
from stmdomains.analysis.clustering import validate_model_dimensions
from stmdomains.io.project_validation import validate_execution, validate_selection
from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.geometry_domain_settings import GeometryDomainSettings, METHOD
from stmdomains.analysis.order_settings import OrderSettings
from stmdomains.io.project_archive import ProjectError, json_bytes, put_bytes, read_json


def catalogue_record(catalogue: ClassCatalogue) -> dict:
    return {'identifier': catalogue.identifier, 'scope': catalogue.scope, 'indices': catalogue.frame_indices,
            'state': plain_metadata(catalogue.state), 'provenance': plain_metadata(catalogue.provenance),
            'parameters': plain_metadata(catalogue.parameters)}


def load_catalogue(record: dict, series: Series) -> ClassCatalogue:
    if (record['scope'] not in ('current_frame', 'selected_range', 'whole_series') or
            not valid_indices(record['indices'], series.frame_count)):
        raise ProjectError('Niepoprawny zakres katalogu klas.')
    catalogue = ClassCatalogue(series.identity, record['scope'], tuple(record['indices']), record['state'],
                               record['provenance'], record['parameters'])
    if catalogue.identifier != record['identifier'] or type(catalogue.state['k']) is not int or not 1 <= catalogue.k <= 8:
        raise ProjectError('Niezgodna tożsamość lub liczba klas katalogu.')
    if 'class_selection' in catalogue.state and catalogue.state['class_selection'] is None:
        raise ProjectError('Brak wymaganej decyzji Auto w katalogu.')
    validate_selection(catalogue.state.get("class_selection"))
    descriptor = DescriptorSettings.from_parameters(catalogue.parameters)
    validate_model_dimensions(catalogue.state, descriptor.dimension, descriptor.pca_max_components)
    return catalogue


def valid_indices(indices: Any, count: int) -> bool:
    return (isinstance(indices, (list, tuple)) and bool(indices) and
            all(type(i) is int and 0 <= i < count for i in indices) and len(set(indices)) == len(indices))


def frame_record(result: FrameAnalysis) -> dict:
    return {'working_index': result.working_index, 'source_index': result.source_index,
            'status': result.status, 'message': result.message,
            'assignments': {key: {'detection_id': item.detection_id, 'domain_local_id': item.domain_local_id,
                'class_id': item.class_id, 'provisional_class_id': item.provisional_class_id,
                'status': item.status, 'rejection_reason': item.rejection_reason,
                'metadata': plain_metadata(item.metadata)} for key, item in result.assignments.items()},
            'classes': [asdict(item) for item in result.classes],
            'parameters': plain_metadata(result.parameters), 'metadata': plain_metadata(result.metadata),
            'catalogue': result.catalogue.identifier if result.catalogue else None,
            'domain_labels': result.domain_labels is not None, 'barrier_mask': result.barrier_mask is not None}


def validate_frame(result: FrameAnalysis, series: Series, presenter: FramePresenter) -> None:
    geometric = result.parameters.get('domain_method') == METHOD
    if geometric:
        GeometryDomainSettings.from_parameters(result.parameters)
        if result.classes or result.catalogue is not None or result.metadata.get('phase_boundary_tested') is not False:
            raise ProjectError('Sprzeczny opis eksperymentalnej metody geometrycznej.')
    ClassAcceptanceSettings.from_parameters(result.parameters)
    DomainSettings.from_parameters(result.parameters)
    OrderSettings.from_parameters(result.parameters)
    descriptor = DescriptorSettings.from_parameters(result.parameters)
    BarrierSettings.from_parameters(result.parameters)
    validate_selection(result.metadata.get("class_selection"))
    if not isinstance(result.message, str):
        raise ProjectError('Niepoprawny opis wyniku.')
    if any(not isinstance(value, str) for item in result.classes for value in (item.class_id, item.color)):
        raise ProjectError('Niepoprawny opis klasy.')
    index = result.working_index
    if (result.series_id != series.identity or type(index) is not int or not 0 <= index < series.frame_count or
            result.source_index != series.source_frame_indices[index] or
            result.status not in ('complete', 'no_annotations', 'insufficient_data')):
        raise ProjectError('Wynik należy do innej klatki lub ma niepoprawny stan.')
    data = presenter.analysis_input(index)
    if set(result.assignments) != {d.detection_id for d in data.annotations.detections}:
        raise ProjectError('Przypisania nie odpowiadają oznaczeniom molekuł.')
    classes = {item.class_id for item in result.classes}
    if len(classes) != len(result.classes) or '' in classes:
        raise ProjectError('Niepoprawne ID klas wyniku.')
    domain_classes: dict[int, str] = {}
    for key, item in result.assignments.items():
        if any(not isinstance(value, str) for value in (item.detection_id, item.class_id,
                item.provisional_class_id, item.status, item.rejection_reason)):
            raise ProjectError('Niepoprawny opis przypisania.')
        domain = item.domain_local_id
        if (item.detection_id != key or type(domain) is not int or domain < 0 or
                (domain and (item.status != 'domain' or (item.class_id != '' if geometric else item.class_id not in classes))) or
                (not domain and (item.class_id or item.status == 'domain')) or
                (item.provisional_class_id and item.provisional_class_id not in classes)):
            raise ProjectError('Sprzeczne przypisanie molekuły do domeny lub klasy.')
        if domain:
            if domain in domain_classes and domain_classes[domain] != item.class_id:
                raise ProjectError('Domena zawiera sprzeczne klasy.')
            domain_classes[domain] = item.class_id
    if result.status != 'complete' and domain_classes:
        raise ProjectError('Niewykonana analiza zawiera przypisane domeny.')
    labels = result.domain_labels
    if labels is not None and (labels.shape != series.frame_shape or
            set(np.unique(labels)) - {0} != set(domain_classes)):
        raise ProjectError('Maska domen ma inne wymiary lub ID niż przypisania.')
    if result.catalogue is not None:
        if descriptor != DescriptorSettings.from_parameters(result.catalogue.parameters):
            raise ProjectError('Opis wyniku nie odpowiada katalogowi klas.')
        if result.catalogue.k != len(classes) or result.metadata.get('model_id') != result.catalogue.identifier:
            raise ProjectError('Wynik odwołuje się do innego katalogu klas.')
    if result.barrier_mask is not None and (result.status != 'complete' or result.barrier_mask.shape != series.frame_shape or
            int(result.barrier_mask.sum()) != result.metadata.get('barriers', {}).get('dilated_pixels')):
        raise ProjectError('Maska barier nie odpowiada klatce lub metadanym.')
    expected = result.metadata.get('input_sha256')
    if expected is not None and expected != input_fingerprint(data):
        raise ProjectError('Wynik obliczono dla innych obrazów lub oznaczeń.')


def save_analysis(archive: zipfile.ZipFile, entries: dict, analysis: ProjectAnalysis, series: Series, check) -> dict:
    if not isinstance(analysis.identifier, str) or not analysis.identifier or not valid_indices(analysis.indices, series.frame_count):
        raise ProjectError('Niepoprawna tożsamość lub zakres analizy.')
    if set(analysis.statuses) != set(analysis.indices) or not set(analysis.frames) <= set(analysis.indices):
        raise ProjectError('Niepełna lista stanów zakresu analizy.')
    validate_execution(analysis.execution, analysis.indices, series.frame_count)
    statuses = {str(i): plain_metadata(s) for i, s in analysis.statuses.items()}
    for index in analysis.indices:
        status = statuses[str(index)]['status']
        if status not in ('complete', 'no_annotations', 'insufficient_data', 'error', 'not_run', 'unavailable'):
            raise ProjectError('Niepoprawny stan klatki.')
        if index not in analysis.frames and status in ('complete', 'no_annotations', 'insufficient_data'):
            raise ProjectError('Brak wyniku klatki oznaczonej jako wykonana.')
    catalogues = {c.identifier: c for c in analysis.catalogues}
    presenter = verification_presenter(series)
    for index in analysis.frames:
        check()
        result = analysis.frames[index]
        if result.working_index != index:
            raise ProjectError('Niezgodny indeks wyniku klatki.')
        validate_frame(result, series, presenter)
        if statuses[str(index)]['status'] != result.status:
            raise ProjectError('Stan klatki nie odpowiada wynikowi.')
        statuses[str(index)].update(assigned=result.assigned_count, active=result.active_count, domains=result.domain_count)
        if result.catalogue:
            catalogues[result.catalogue.identifier] = result.catalogue
        put_bytes(archive, entries, f'frames/{index}.json', json_bytes(frame_record(result)))
        if result.barrier_mask is not None:
            save_barriers(archive, entries, index, result.barrier_mask)
        if result.domain_labels is not None:
            output = io.BytesIO()
            np.save(output, np.asarray(result.domain_labels, dtype='<i4'), allow_pickle=False)
            put_bytes(archive, entries, f'frames/{index}.npy', output.getvalue())
    for catalogue in catalogues.values():
        check()
        if catalogue.series_id != series.identity:
            raise ProjectError('Katalog pochodzi z innej serii.')
        put_bytes(archive, entries, f'catalogues/{catalogue.identifier}.json', json_bytes(catalogue_record(catalogue)))
    return {'identifier': analysis.identifier, 'indices': analysis.indices, 'frames': list(analysis.frames),
            'statuses': statuses,
            'catalogues': list(catalogues), 'execution': plain_metadata(analysis.execution)}


def verification_presenter(series: Series) -> FramePresenter:
    # Fingerprints use images and detection centres, never input segmentation masks.
    # Reuse the annotation adapter without decoding those unrelated rasters.
    payload = {key: value for key, value in series.raw_payload.items() if key != 'molecular_segmentations'}
    return FramePresenter(replace(series, raw_payload=payload))


def read_result(root: Path, index: int, series: Series, catalogues: Mapping[str, ClassCatalogue], *,
                load_mask: bool) -> FrameAnalysis:
    record = read_json(root / f'frames/{index}.json')
    if type(record['domain_labels']) is not bool:
        raise ProjectError('Niepoprawny stan maski domen.')
    if type(record.get('barrier_mask', False)) is not bool:
        raise ProjectError('Niepoprawny stan maski barier.')
    labels = load_labels(root / f'frames/{index}.npy', series.frame_shape) if load_mask and record['domain_labels'] else None
    barrier = load_barriers(root / f'frames/{index}.barriers.npy', series.frame_shape,
                            record['metadata']['barriers']['dilated_pixels']) if load_mask and record.get('barrier_mask') else None
    assignments = {key: MoleculeAssignment(**item) for key, item in record['assignments'].items()}
    catalogue = catalogues[record['catalogue']] if record['catalogue'] is not None else None
    return FrameAnalysis(series.identity, record['working_index'], record['source_index'], record['status'],
                         record['message'], assignments, tuple(ResultClass(**item) for item in record['classes']),
                         record['parameters'], record['metadata'], labels, catalogue, barrier)


class SavedFrameResults(Mapping[int, FrameAnalysis]):
    """Cache at most three immutable frame results; source files live with the Series."""

    def __init__(self, root: Path, series: Series, indices: tuple[int, ...], catalogues: Mapping[str, ClassCatalogue]) -> None:
        self.root, self.series, self.indices, self.catalogues = root, series, indices, catalogues
        self._cache: OrderedDict[int, FrameAnalysis] = OrderedDict()
        self._lock = RLock()

    def __contains__(self, index: object) -> bool:
        return index in self.indices

    def __iter__(self) -> Iterator[int]:
        return iter(self.indices)

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, index: int) -> FrameAnalysis:
        if index not in self.indices:
            raise KeyError(index)
        with self._lock:
            if index not in self._cache:
                self._cache[index] = read_result(self.root, index, self.series, self.catalogues, load_mask=True)
            self._cache.move_to_end(index)
            while len(self._cache) > 3:
                self._cache.popitem(last=False)
            return self._cache[index]


def load_analysis(record: dict | None, root: Path, series: Series, entries: dict, check) -> ProjectAnalysis | None:
    if record is None:
        if any(name.startswith(('frames/', 'catalogues/')) for name in entries):
            raise ProjectError('Projekt bez analizy zawiera niepowiązane wyniki.')
        return None
    if not isinstance(record['identifier'], str) or not record['identifier'] or not valid_indices(record['indices'], series.frame_count):
        raise ProjectError('Niepoprawny zakres analizy.')
    indices = tuple(record['indices'])
    validate_execution(record['execution'], indices, series.frame_count)
    frames = tuple(record['frames'])
    if any(type(i) is not int for i in frames) or len(set(frames)) != len(frames) or not set(frames) <= set(indices):
        raise ProjectError('Niepoprawna lista wyników klatek.')
    catalogues = {}
    for identifier in record['catalogues']:
        check()
        if f'catalogues/{identifier}.json' not in entries or identifier in catalogues:
            raise ProjectError('Niepoprawne odwołanie do katalogu.')
        catalogue = load_catalogue(read_json(root / f'catalogues/{identifier}.json'), series)
        if catalogue.identifier != identifier:
            raise ProjectError('Niezgodne ID katalogu.')
        catalogues[identifier] = catalogue
    results = SavedFrameResults(root, series, frames, catalogues)
    statuses = {int(i): value for i, value in record['statuses'].items()}
    if set(statuses) != set(indices):
        raise ProjectError('Brak stanów części klatek analizy.')
    expected_entries = {'source.mpp', 'input.json', 'project.json', *(f'catalogues/{i}.json' for i in catalogues)}
    presenter = verification_presenter(series)
    for index in indices:
        check()
        if not isinstance(statuses[index].get('message', ''), str):
            raise ProjectError('Niepoprawny opis stanu klatki.')
        status = statuses[index]['status']
        if status not in ('complete', 'no_annotations', 'insufficient_data', 'error', 'not_run', 'unavailable'):
            raise ProjectError('Niepoprawny stan klatki analizy.')
        if index in results:
            result = read_result(root, index, series, catalogues, load_mask=False)
            validate_frame(result, series, presenter)
            if result.working_index != index or result.status != status:
                raise ProjectError('Stan lub indeks nie odpowiada wynikowi klatki.')
            if any(statuses[index].get(name) != value for name, value in (
                    ('assigned', result.assigned_count), ('active', result.active_count), ('domains', result.domain_count))):
                raise ProjectError('Liczniki nie odpowiadają przypisaniom klatki.')
            expected_entries.add(f'frames/{index}.json')
            if read_json(root / f'frames/{index}.json').get('barrier_mask'):
                if result.status != 'complete':
                    raise ProjectError('Niewykonana analiza zawiera maskę barier.')
                check_barriers(root / f'frames/{index}.barriers.npy', series.frame_shape,
                               result.metadata.get('barriers', {}).get('dilated_pixels'), check)
                expected_entries.add(f'frames/{index}.barriers.npy')
            if read_json(root / f'frames/{index}.json')['domain_labels']:
                check_labels(root / f'frames/{index}.npy', series.frame_shape,
                             {item.domain_local_id for item in result.assignments.values()} - {0}, check)
                expected_entries.add(f'frames/{index}.npy')
        elif status in ('complete', 'no_annotations', 'insufficient_data'):
            raise ProjectError('Brak wymaganego wyniku klatki.')
    if expected_entries != set(entries):
        raise ProjectError('Brakujące lub niepowiązane części wyniku.')
    return ProjectAnalysis(record['identifier'], indices, results, statuses, tuple(catalogues.values()), record['execution'])
