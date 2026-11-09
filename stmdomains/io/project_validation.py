"""Validate persisted UI state before replacing the currently open work."""

from collections.abc import Mapping
from math import isfinite
from typing import Any

from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.geometry_domain_settings import GeometryDomainSettings
from stmdomains.analysis.freud_settings import FreudSettings
from stmdomains.analysis.levelset_settings import LevelSetSettings
from stmdomains.analysis.descriptor_settings import DescriptorSettings
from stmdomains.analysis.barrier_settings import BarrierSettings
from stmdomains.analysis.order_settings import OrderSettings
from stmdomains.analysis.series_settings import SeriesAnalysisPlan
from stmdomains.io.project_archive import ProjectError


def analysis_plan(record: Mapping[str, Any]) -> SeriesAnalysisPlan:
    value = dict(record)
    for key, constructor in (('acceptance', ClassAcceptanceSettings), ('domain_settings', DomainSettings),
                              ('order_settings', OrderSettings), ('descriptor_settings', DescriptorSettings),
                              ('barrier_settings', BarrierSettings)):
        if key in value:
            value[key] = constructor(**value[key])
    return SeriesAnalysisPlan(**value)


def validate_project_state(view: Mapping, draft: Mapping, count: int) -> None:
    if not isinstance(view, Mapping) or not isinstance(draft, Mapping):
        raise ProjectError('Niepoprawny stan widoku lub parametrów.')
    if draft.get('domain_method', 'baseline') not in ('baseline', 'geometry', 'freud', 'levelset'):
        raise ProjectError('Nieznana metoda domen w szkicu.')
    validate_inactive_baseline(draft.get('inactive_baseline', {}))
    GeometryDomainSettings(**draft.get('geometry_tolerances', {}))
    FreudSettings(**draft.get('freud_settings', {}))
    LevelSetSettings(**draft.get('levelset_settings', {}))
    DomainSettings(**draft.get('geometry_constraints', {}))
    index = view.get('current_index', 0)
    if type(index) is not int or not 0 <= index < count:
        raise ProjectError('Niepoprawna bieżąca klatka projektu.')
    if view.get('mode', 'raw') not in ('raw', 'expanded_aligned'):
        raise ProjectError('Nieznany widok projektu.')
    gamma = view.get('gamma', 1.)
    if type(gamma) not in (float, int) or not isfinite(gamma) or not .2 <= gamma <= 5:
        raise ProjectError('Niepoprawna gamma projektu.')
    if view.get('assignment_mode', 'domains') not in ('domains', 'classes', 'input'):
        raise ProjectError('Nieznana warstwa przypisań.')
    if 'viewport' in view:
        viewport = view['viewport']
        if not isinstance(viewport, Mapping) or set(viewport) != {'fit', 'scale', 'center'}:
            raise ProjectError('Niepoprawny stan powiększenia projektu.')
        scale, center = viewport['scale'], viewport['center']
        if (type(viewport['fit']) is not bool or type(scale) not in (float, int) or
                not isfinite(scale) or not .0001 <= scale <= 256):
            raise ProjectError('Niepoprawne powiększenie projektu.')
        if (not isinstance(center, (list, tuple)) or len(center) != 2 or
                any(type(v) not in (int, float) or not isfinite(v) for v in center)):
            raise ProjectError('Niepoprawne przesunięcie widoku.')
    layers = view.get('layers', {})
    if not isinstance(layers, Mapping):
        raise ProjectError('Niepoprawny stan warstw projektu.')
    for name in ('centers', 'boxes', 'masks', 'fill', 'outlines', 'numbers', 'barriers'):
        if name in layers and type(layers[name]) is not bool:
            raise ProjectError('Niepoprawny stan warstw projektu.')
    for name in ('mask_opacity', 'domain_opacity'):
        if name in layers and (type(layers[name]) is not int or not 0 <= layers[name] <= 100):
            raise ProjectError('Niepoprawne krycie warstw projektu.')
    if 'plan' in draft:
        analysis_plan(draft['plan'])
        if draft.get('scope') not in ('current_frame', 'selected_range', 'whole_series'):
            raise ProjectError('Niepoprawny zakres szkicu.')
        if draft.get('class_mode') not in ('new', 'existing'):
            raise ProjectError('Niepoprawny wybór katalogu w szkicu.')

        plan = analysis_plan(draft['plan'])
        if (plan.fit_source not in ('same_range', 'selected_range', 'whole_series', 'existing') or
                draft.get('discovery_source', 'same_range') not in ('same_range', 'selected_range', 'whole_series')):
            raise ProjectError('Niepoprawne źródło klas w szkicu.')
        for index in (plan.start, plan.end, plan.fit_start, plan.fit_end, draft.get('scope_start', plan.start)):
            if type(index) is not int or not 0 <= index < count:
                raise ProjectError('Klatka szkicu poza serią.')
        identifier = draft.get('catalogue_id')
        if identifier is not None and (not isinstance(identifier, str) or len(identifier) != 64):
            raise ProjectError('Niepoprawne ID wybranego katalogu.')
    if view.get('playback_rate', 5) not in (1, 2, 5, 10, 20):
        raise ProjectError('Niepoprawne tempo odtwarzania.')


def validate_selection(value: Mapping | None) -> None:
    if value is None:
        return
    selected = value['selected_k']
    if selected is not None and (type(selected) is not int or not 1 <= selected <= 8):
        raise ProjectError('Niepoprawny wybór Auto.')
    if not isinstance(value['reason'], str) or not isinstance(value['rule_version'], str):
        raise ProjectError('Niepoprawny opis Auto.')
    for name in ('max_k', 'seed', 'useful_count', 'active_count', 'fit_count', 'ranking_count'):
        if type(value[name]) is not int or value[name] < 0:
            raise ProjectError('Niepoprawne liczniki Auto.')
    if not 1 <= value['max_k'] <= 8 or (selected is not None and selected > value['max_k']):
        raise ProjectError('Niepoprawny zakres Auto.')
    if not isinstance(value['useful_fraction'], (float, int)) or not 0 <= value['useful_fraction'] <= 1:
        raise ProjectError('Niepoprawny udział użytecznych opisów.')
    for row in value['ranking']:
        if type(row['k']) is not int or not 1 <= row['k'] <= value['max_k']:
            raise ProjectError('Niepoprawny kandydat Auto.')
        if type(row['eligible']) is not bool or not isinstance(row['reason'], str):
            raise ProjectError('Niepoprawna ocena kandydata Auto.')
        for number in (*row['sizes'], *row['radius95'], row['silhouette'], row['separation']):
            if number is not None and (type(number) not in (int, float) or not isfinite(number)):
                raise ProjectError('Niepoprawna miara rankingu Auto.')


def validate_execution(execution: Mapping, indices: tuple[int, ...], count: int) -> None:
    if execution.get('phase', 'restored') not in ('complete', 'cancelled', 'failed', 'undetermined', 'restored'):
        raise ProjectError('Projekt zawiera niedokończony lub nieznany stan wykonania.')
    if 'plan' in execution and analysis_plan(execution['plan']).indices(count) != indices:
        raise ProjectError('Zakres wykonania nie odpowiada zapisanej analizie.')
    validate_selection(execution.get('selection'))


def validate_inactive_baseline(record: Mapping) -> None:
    """Keep editable scalar bounds, deliberately permit invalid cross-field drafts."""
    if not isinstance(record, Mapping):
        raise ProjectError('Niepoprawny nieaktywny szkic bazowy.')
    if not record:
        return
    limits = {
        'domain_settings': {'minimum_domain_size': (1, 3000, int), 'edge_distance_factor': (.05, 10, float),
            'edge_max_hellinger': (0, 1, float), 'region_max_hellinger_diameter': (0, 1, float),
            'raster_radius_factor': (.05, 10, float)},
        'descriptor_settings': {'descriptor_radial_bins': (4, 32, int), 'descriptor_angle_bins': (8, 72, int),
            'descriptor_sigma_factor': (.25, 3, float), 'pca_max_components': (1, 64, int)}}
    if set(record) != set(limits):
        raise ProjectError('Niepełny nieaktywny szkic bazowy.')
    for group, fields in limits.items():
        values = record[group]
        extra = 'geometry_mode' if group == 'domain_settings' else 'descriptor_pair_distance_range'
        if not isinstance(values, Mapping) or set(values) != set(fields) | {extra}:
            raise ProjectError('Niepoprawne pola nieaktywnego szkicu.')
        for key, (low, high, kind) in fields.items():
            value = values[key]
            if (type(value) not in ((int,) if kind is int else (int, float))
                    or not isfinite(value) or not low <= value <= high):
                raise ProjectError('Wartość nieaktywnego szkicu poza zakresem.')
        if group == 'domain_settings':
            if values[extra] not in ('off', 'hellinger_region'):
                raise ProjectError('Nieznana kontrola zgodności szkicu.')
        else:
            pair = values[extra]
            if (not isinstance(pair, (tuple, list)) or len(pair) != 2 or
                    any(type(v) not in (int, float) or not isfinite(v) or not low <= v <= high
                        for v, low, high in zip(pair, (.1, .2), (3.9, 4.)))):
                raise ProjectError('Niepoprawny zakres par w szkicu.')
