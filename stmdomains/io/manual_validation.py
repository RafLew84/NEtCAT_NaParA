"""Validate saved manual memberships and timelines without fitting any model."""

import re
import numpy as np

from stmdomains.core.frame_presentation import FramePresenter
from stmdomains.core.manual_classes import ManualClassList
from stmdomains.core.manual_class_lists import ManualClassLists
from stmdomains.core.manual_domains import EXCLUDED, MANUAL_METHOD, ManualDomains
from stmdomains.core.manual_project import ManualProjectState, validate_history
from stmdomains.core.series import Series
from stmdomains.io.project_archive import ProjectError
from stmdomains.io.project_results import validate_frame


def validate_list(labels: ManualClassList) -> None:
    if (not all(isinstance(x, str) and re.fullmatch(r'[0-9a-f]{32}', x) for x in (labels.identifier, labels.version))
            or type(labels.generation) is not int or labels.generation < 0
            or not isinstance(labels.source_key, str) or not isinstance(labels.catalogue_id, str)):
        raise ProjectError('Niepoprawna tożsamość listy klas ręcznych.')
    ids = set()
    for label in labels.classes:
        if (not isinstance(label.class_id, str) or not label.class_id or label.class_id in ids
                or not isinstance(label.name, str) or not 1 <= len(label.name.strip()) <= 80
                or not isinstance(label.color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', label.color)
                or label.origin not in ('automatic', 'manual')
                or (label.origin == 'manual' and not re.fullmatch(r'manual-[0-9a-f]{32}', label.class_id))):
            raise ProjectError('Niepoprawny opis klasy ręcznej.')
        ids.add(label.class_id)


def validate_manual(state: ManualProjectState, series: Series, check=lambda: None) -> None:
    validate_history(state)
    presenter = FramePresenter(series)
    revisions = {(r.identifier, r.version): r for r in state.revisions}
    for labels in state.revisions:
        check()
        validate_list(labels)
    starts = {r.identifier: r for r in state.revisions if r.generation == 0}
    for variant in state.variants:
        check()
        if not isinstance(variant.identifier, str) or not re.fullmatch(r'[0-9a-f]{32}', variant.identifier):
            raise ProjectError('Niepoprawne ID wariantu ręcznego.')
        index = variant.frames[0].working_index
        if type(index) is not int or not 0 <= index < series.frame_count:
            raise ProjectError('Korekty odnoszą się do nieznanej klatki.')
        data = presenter.analysis_input(index)
        original = variant.original
        if original is not None:
            if original.class_list is not None:
                raise ProjectError('Wynik bazowy zawiera ręczną listę klas.')
            validate_frame(original, series, presenter)
        source = ManualClassLists.source_key(series.identity, original)
        initial_list = starts[variant.class_list_id]
        expected_list = ManualClassList.from_result(original, source)
        if initial_list.classes != expected_list.classes or initial_list.catalogue_id != expected_list.catalogue_id:
            raise ProjectError('Początkowa lista klas nie odpowiada wynikowi bazowemu.')
        for labels in state.revisions:
            if labels.identifier == variant.class_list_id:
                if labels.source_key != source or labels.catalogue_id != initial_list.catalogue_id:
                    raise ProjectError('Lista klas należy do innego źródła.')
                automatic = {c.class_id for c in labels.classes if c.origin == 'automatic'}
                if automatic != {c.class_id for c in initial_list.classes}:
                    raise ProjectError('Ręczna rewizja zmienia tożsamość klas modelu.')
        restored = ManualDomains.restore(data, variant)
        eligible = {k for k, a in variant.frames[0].assignments.items() if a.status not in EXCLUDED}
        revision = 0
        for number, frame in enumerate(variant.frames):
            check()
            if ((frame.series_id, frame.working_index, frame.source_index) !=
                    (series.identity, index, series.source_frame_indices[index])
                    or set(frame.assignments) != {d.detection_id for d in data.annotations.detections}
                    or frame.classes != (original.classes if original else ())
                    or (frame.catalogue.identifier if frame.catalogue else '') != initial_list.catalogue_id):
                raise ProjectError('Stan korekt należy do innych danych lub modelu.')
            if frame.class_list is not None and (frame.class_list.identifier != variant.class_list_id or
                    revisions.get((frame.class_list.identifier, frame.class_list.version)) is not frame.class_list):
                raise ProjectError('Nieznana rewizja klas w stanie korekt.')
            if number == 0:
                continue
            edit = frame.metadata.get('manual_edit', {})
            current_revision = edit.get('revision')
            if (frame.status != 'complete' or frame.parameters.get('domain_method') != MANUAL_METHOD
                    or type(current_revision) is not int or not revision < current_revision <= variant.revision
                    or edit.get('operation') not in ('new', 'add', 'move', 'remove', 'split', 'merge',
                        'class_create', 'class_update', 'class_delete', 'class_assign', 'class_create_assign')
                    or edit.get('automatic_available') is not (original is not None)
                    or edit.get('source_analysis_id') != (original.metadata.get('analysis_id', '') if original else '')
                    or edit.get('source_parameters') != (original.parameters if original else {})
                    or any(type(i) is not int or not 0 <= i < series.frame_count for i in edit.get('transaction_frames', ()))
                    or not isinstance(frame.message, str) or not set(edit.get('selection', ())) <= eligible):
                raise ProjectError('Niepoprawna operacja historii korekt.')
            revision = current_revision
            known = {c.class_id for c in frame.class_list.classes} if frame.class_list else {c.class_id for c in frame.classes}
            fitted = {c.class_id for c in frame.classes}
            domains: dict[int, str] = {}
            for key, a in frame.assignments.items():
                if (a.detection_id != key or type(a.domain_local_id) is not int or a.domain_local_id < 0
                        or any(not isinstance(value, str) for value in
                               (a.class_id, a.provisional_class_id, a.status, a.rejection_reason))
                        or bool(a.domain_local_id) != (a.status == 'domain')
                        or (a.class_id and a.class_id not in known)
                        or (a.provisional_class_id and a.provisional_class_id not in fitted)
                        or (key not in eligible and (a.domain_local_id or a.class_id))):
                    raise ProjectError('Sprzeczne ręczne przypisanie molekuły lub klasy.')
                if a.domain_local_id:
                    if a.domain_local_id in domains and domains[a.domain_local_id] != a.class_id:
                        raise ProjectError('Ręczna domena zawiera różne klasy.')
                    domains[a.domain_local_id] = a.class_id
            raster = frame.domain_labels
            if raster is not None and (raster.shape != series.frame_shape or raster.dtype != np.dtype('int32') or np.any(raster < 0)):
                raise ProjectError('Niepoprawna geometria ręcznych domen.')
            visible = set(np.unique(raster)) - {0} if raster is not None else set()
            if (not visible <= domains.keys() or set(edit.get('unsupported_domains', ())) != domains.keys() - visible):
                raise ProjectError('Obszary ręczne nie odpowiadają członkostwu domen.')
            if edit['operation'] in ('class_create', 'class_update', 'class_delete'):
                previous = variant.frames[number - 1]
                if frame.assignments != previous.assignments or not np.array_equal(np.asarray(raster), np.asarray(previous.domain_labels)):
                    raise ProjectError('Edycja metadanych klasy zmienia przypisania lub geometrię.')
        if restored.current is not variant.frames[variant.cursor]:
            raise ProjectError('Niezgodny stan odtworzonej historii.')
