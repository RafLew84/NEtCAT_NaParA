"""Validation of explicit Deep/ECC and local-consensus evidence schemas."""

from dataclasses import fields
from math import isclose
from typing import Any


def validate_evidence(record: dict[str, Any]) -> None:
    from stmviewer.trial_validation import number, object_record, xy
    from stmviewer.deep_ecc import HybridDiagnostics, HybridFailure
    from stmviewer.local_consensus import LocalDiagnostics, LocalPatchEvidence

    def schema(value: Any, model: Any, label: str) -> dict[str, Any]:
        result = object_record(value, label)
        if set(result) != {field.name for field in fields(model)}:
            raise ValueError(f'{label}: nieprawidłowe pola diagnostyki.')
        return result

    def text(value: Any, label: str, *, optional: bool = False) -> None:
        if value is None and optional:
            return
        if not isinstance(value, str):
            raise ValueError(f'{label}: wymagany tekst.')

    def quality(value: Any, label: str, *, optional: bool = False) -> None:
        if value is None and optional:
            return
        if not 0 <= number(value, label) <= 1:
            raise ValueError(f'{label}: jakość poza zakresem 0–1.')

    def common(diag: dict[str, Any]) -> None:
        if type(diag['settings_version']) is not int or diag['settings_version'] != 1:
            raise ValueError('Nieobsługiwana wersja diagnostyki.')
        for name in ('settings_text', 'weights', 'requested_device', 'actual_device'):
            text(diag[name], name)

    def status(value: Any, label: str, *, optional: bool = False) -> None:
        if value is None and optional:
            return
        if value not in ('ok', 'low_confidence', 'manual_review', 'failed'):
            raise ValueError(f'{label}: nieznany status diagnostyki.')

    def final_matches(diag: dict[str, Any]) -> None:
        if record['manual'] is not None:
            return  # Retained automatic evidence describes the baseline of a manual edit.
        final, shift = diag['final_shift_xy'], record['shift_xy']
        if final is not None and shift is not None and not all(
                isclose(a, b, rel_tol=1e-9, abs_tol=1e-9) for a, b in zip(final, shift)):
            raise ValueError('Końcowe XY diagnostyki różni się od wyniku pary.')

    hybrid = record['hybrid']
    if hybrid is not None:
        hybrid = object_record(hybrid, 'Deep/ECC')
        failed = hybrid.get('final_shift_xy') is None
        hybrid = schema(hybrid, HybridFailure if failed else HybridDiagnostics, 'Deep/ECC')
        common(hybrid)
        xy(hybrid['deep_shift_xy'], 'Start Deep', optional=failed)
        quality(hybrid['deep_quality_score'], 'Jakość Deep', optional=failed)
        status(hybrid['deep_status'], 'Status Deep', optional=failed)
        if failed:
            if hybrid['stage'] not in ('Deep Matcher', 'ECC'):
                raise ValueError('Deep/ECC: nieznany etap przerwania.')
            text(hybrid['reason'], 'Przyczyna przerwania')
            if record['shift_xy'] is not None or record['cumulative_xy'] is not None:
                raise ValueError('Przerwana hybryda nie może mieć pełnego wyniku XY.')
        else:
            xy(hybrid['final_shift_xy'], 'Wynik ECC')
            xy(hybrid['correction_xy'], 'Korekta ECC')
            number(hybrid['ecc_score'], 'Score ECC')
            status(hybrid['ecc_status'], 'Status ECC')
            if not all(isclose(a + b, c, rel_tol=1e-9, abs_tol=1e-9) for a, b, c in zip(
                    hybrid['deep_shift_xy'], hybrid['correction_xy'], hybrid['final_shift_xy'])):
                raise ValueError('Deep/ECC: różnica etapów nie zgadza się z końcowym XY.')
            final_matches(hybrid)
    local = record['local']
    if local is not None:
        local = schema(local, LocalDiagnostics, 'Lokalny konsensus')
        common(local)
        xy(local['deep_shift_xy'], 'Start Deep')
        xy(local['final_shift_xy'], 'Wynik lokalny', optional=True)
        quality(local['deep_quality_score'], 'Jakość Deep', optional=True)
        text(local['deep_status'], 'Status Deep')
        status(local['status'], 'Status lokalny')
        text(local['reason'], 'Powód konsensusu')
        patches = local['patches']
        if not isinstance(patches, (list, tuple)):
            raise ValueError('Lokalny konsensus: wymagana lista fragmentów.')
        for patch in patches:
            patch = schema(patch, LocalPatchEvidence, 'Fragment lokalny')
            for name in ('reference_rect', 'moving_rect'):
                rect = patch[name]
                if rect is None and name == 'moving_rect':
                    continue
                if not isinstance(rect, (tuple, list)) or len(rect) != 4:
                    raise ValueError('Fragment lokalny: wymagany prostokąt o czterech współrzędnych.')
                for coordinate in rect:
                    number(coordinate, 'Prostokąt fragmentu')
                if rect[2] <= 0 or rect[3] <= 0:
                    raise ValueError('Fragment lokalny: rozmiar prostokąta musi być dodatni.')
                if name == 'reference_rect' and (not all(type(v) is int for v in rect)
                                                 or rect[0] < 0 or rect[1] < 0):
                    raise ValueError('Fragment lokalny: nieprawidłowy prostokąt odniesienia.')
            xy(patch['shift_xy'], 'XY fragmentu', optional=True)
            for name in ('score', 'peak_margin', 'peak_contrast'):
                if patch[name] is not None:
                    number(patch[name], name)
            if patch['status'] not in ('inlier', 'outlier', 'unmatched'):
                raise ValueError('Fragment lokalny: nieznany status.')
            text(patch['reason'], 'Powód fragmentu')
        if local['final_shift_xy'] is None and (record['shift_xy'] is not None
                                               or record['cumulative_xy'] is not None):
            raise ValueError('Przerwany konsensus nie może mieć pełnego wyniku XY.')
        final_matches(local)
