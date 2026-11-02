"""Strict, runtime-free persistence of original-space correspondence evidence."""
from dataclasses import asdict
import math
import re

from stmviewer.correspondence_types import CorrespondenceDiagnostics, ImagePreparation
from stmviewer.metadata_values import json_object, optional_number

_KEYS = {'final_shift_xy', 'input_count', 'valid_count', 'inlier_count', 'inlier_fraction',
         'reference_support', 'moving_support', 'reference_span_xy', 'moving_span_xy',
         'median_residual_px', 'status', 'reason', 'settings_text', 'preparation',
         'model_provenance', 'settings_version'}
_PREPARATION = {'original_shape', 'model_shape', 'scale_xy', 'padding_ltrb', 'value_range',
                'normalization', 'channels'}


def _items(value: object, length: int | None = None) -> list[object]:
    if not isinstance(value, (list, tuple)) or (length is not None and len(value) != length):
        raise ValueError('Korespondencje: nieprawidłowy rozmiar listy.')
    return list(value)


def _integer(value: object, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError('Korespondencje: nieprawidłowa liczba całkowita.')
    return value


def _number(value: object) -> float:
    number = optional_number({'value': value}, 'value')
    if number is None:
        raise ValueError('Korespondencje: liczba nie może być null.')
    return number


def _xy(value: object) -> tuple[float, float]:
    x, y = _items(value, 2)
    return _number(x), _number(y)


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or '\x00' in value or len(value) > 32768:
        raise ValueError('Korespondencje: nieprawidłowy tekst diagnostyki.')
    return value


def _preparation(value: object) -> ImagePreparation:
    record = json_object(value, _PREPARATION)
    oh, ow = (_integer(item, 1) for item in _items(record['original_shape'], 2))
    mh, mw = (_integer(item, 1) for item in _items(record['model_shape'], 2))
    left, top, right, bottom = (_integer(item) for item in _items(record['padding_ltrb'], 4))
    sx, sy = _xy(record['scale_xy'])
    low, high = _xy(record['value_range'])
    if (sx <= 0 or sy <= 0 or low > high or mw <= left + right or mh <= top + bottom
            or not math.isclose(ow * sx, mw - left - right, rel_tol=1e-9, abs_tol=1e-9)
            or not math.isclose(oh * sy, mh - top - bottom, rel_tol=1e-9, abs_tol=1e-9)):
        raise ValueError('Korespondencje: niespójna geometria przygotowania obrazu.')
    normalization = _text(record['normalization'])
    if normalization != 'minmax-float32-v1' or _integer(record['channels'], 1) != 1:
        raise ValueError('Korespondencje: nieobsługiwane przygotowanie obrazu.')
    return ImagePreparation((oh, ow), (mh, mw), (sx, sy), (left, top, right, bottom),
                             (low, high), normalization, 1)


def _provenance(value: object) -> tuple[tuple[str, str], ...]:
    items = _items(value)
    if len(items) > 128:
        raise ValueError('Korespondencje: zbyt rozbudowane pochodzenie modelu.')
    pairs = []
    for item in items:
        key, content = _items(item, 2)
        name, text = _text(key), _text(content)
        if name.endswith('_sha256') and re.fullmatch('[0-9a-f]{64}', text) is None:
            raise ValueError('Korespondencje: nieprawidłowy SHA-256 pochodzenia.')
        if name == 'source_commit' and re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', text) is None:
            raise ValueError('Korespondencje: nieprawidłowa wersja kodu modelu.')
        pairs.append((name, text))
    if len(dict(pairs)) != len(pairs):
        raise ValueError('Korespondencje: powtórzone pole pochodzenia modelu.')
    return tuple(pairs)


def decode_correspondence(value: object) -> CorrespondenceDiagnostics | None:
    """Restore evidence without loading model code, weights, or images."""
    if value is None:
        return None
    record = json_object(value, _KEYS)
    if _integer(record['settings_version'], 1) != 1:
        raise ValueError('Korespondencje: nieobsługiwana wersja diagnostyki.')
    counts = [_integer(record[key]) for key in ('input_count', 'valid_count', 'inlier_count')]
    total, valid, inliers = counts
    fraction = _number(record['inlier_fraction'])
    reference = tuple(_integer(item) for item in _items(record['reference_support'], 16))
    moving = tuple(_integer(item) for item in _items(record['moving_support'], 16))
    ref_span, mov_span = _xy(record['reference_span_xy']), _xy(record['moving_span_xy'])
    residual = optional_number(record, 'median_residual_px')
    shift = None if record['final_shift_xy'] is None else _xy(record['final_shift_xy'])
    status = _text(record['status'])
    if (not 0 <= inliers <= valid <= total or sum(reference) != inliers or sum(moving) != inliers
            or not math.isclose(fraction, inliers / valid if valid else 0., rel_tol=1e-9, abs_tol=1e-9)
            or any(not 0 <= span <= 1 for span in (*ref_span, *mov_span))
            or (residual is not None and residual < 0)
            or status not in ('manual_review', 'failed')
            or (status == 'manual_review' and (shift is None or residual is None or inliers == 0))
            or (status == 'failed' and shift is not None)):
        raise ValueError('Korespondencje: niespójne poparcie, status lub przesunięcie.')
    preparation = _items(record['preparation'])
    if len(preparation) not in (0, 2):
        raise ValueError('Korespondencje: wymagane przygotowanie obu obrazów.')
    return CorrespondenceDiagnostics(shift, total, valid, inliers, fraction, reference, moving,
        ref_span, mov_span, residual, status, _text(record['reason']), _text(record['settings_text']),
        tuple(_preparation(item) for item in preparation), _provenance(record['model_provenance']))


def encode_correspondence(value: CorrespondenceDiagnostics | None) -> dict[str, object] | None:
    if value is None:
        return None
    record = asdict(value)
    decode_correspondence(record)
    return record


def encode_correspondence_diagnostics(values: tuple[CorrespondenceDiagnostics | None, ...]) -> list[object]:
    return [encode_correspondence(value) for value in values]


def decode_correspondence_diagnostics(value: object, count: int) -> tuple[CorrespondenceDiagnostics | None, ...]:
    items = _items(value)
    if len(items) not in (0, count):
        raise ValueError('Korespondencje: diagnostyka ma inną liczbę klatek.')
    return tuple(decode_correspondence(item) for item in items)


def validate_correspondence_shape(value: CorrespondenceDiagnostics | None,
                                  reference_shape: tuple[int, int], moving_shape: tuple[int, int]) -> None:
    if value is not None and value.preparation:
        shapes = tuple(preparation.original_shape for preparation in value.preparation)
        if shapes != (reference_shape, moving_shape):
            raise ValueError('Korespondencje: przygotowanie nie odpowiada wymiarom oryginałów.')
