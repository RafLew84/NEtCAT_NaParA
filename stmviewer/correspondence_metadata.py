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
    channels = _integer(record['channels'], 1)
    if (normalization, channels) not in (('minmax-float32-v1', 1), ('minmax-float32-rgb-v1', 3),
                                         ('minmax-uint8-demo-gray-v1', 1), ('minmax-uint8-round-v1', 1)):
        raise ValueError('Korespondencje: nieobsługiwane przygotowanie obrazu.')
    return ImagePreparation((oh, ow), (mh, mw), (sx, sy), (left, top, right, bottom),
                             (low, high), normalization, channels)


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
    version = _integer(record['settings_version'], 1)
    if version not in (1, 2):
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
            or status not in ('manual_review', 'low_confidence', 'failed')
            or (status == 'low_confidence' and version < 2)
            or (status in ('manual_review', 'low_confidence')
                and (shift is None or residual is None or inliers == 0))
            or (status == 'failed' and shift is not None)):
        raise ValueError('Korespondencje: niespójne poparcie, status lub przesunięcie.')
    preparation = _items(record['preparation'])
    if len(preparation) not in (0, 2):
        raise ValueError('Korespondencje: wymagane przygotowanie obu obrazów.')
    return CorrespondenceDiagnostics(shift, total, valid, inliers, fraction, reference, moving,
        ref_span, mov_span, residual, status, _text(record['reason']), _text(record['settings_text']),
        tuple(_preparation(item) for item in preparation), _provenance(record['model_provenance']), version)


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


def validate_roma_provenance(provenance: tuple[tuple[str, str], ...]) -> None:
    """Check a saved worker configuration without inspecting or running its paths."""
    metadata = dict(provenance)
    if metadata.get('model') != 'RoMa v2' or metadata.get('preset') not in ('turbo', 'fast', 'base', 'precise'):
        raise ValueError('RoMa: nieobsługiwany model lub preset pochodzenia.')
    for key in ('interpreter_path', 'source_path', 'weights_path'):
        _text(metadata.get(key))
    for key, low, high in (('samples', 8, 10000), ('seed', 0, 2**31 - 1)):
        value = metadata.get(key, '')
        if not value.isascii() or not value.isdecimal() or not low <= int(value) <= high:
            raise ValueError('RoMa: nieprawidłowe ustawienie próbkowania.')


def validate_matchanything_provenance(provenance: tuple[tuple[str, str], ...]) -> None:
    """Validate saved architecture identity without importing optional model code."""
    metadata = dict(_provenance(provenance))
    if (metadata.get('model') != 'MatchAnything-ELoFTR'
            or metadata.get('model_config') != 'configs/models/eloftr_model.py'
            or metadata.get('precision') != 'FP32'
            or metadata.get('inference_policy') != 'hf-match-images-preset-v1'
            or metadata.get('model_threshold') != '0.001'
            or metadata.get('position_encoding') != 'NPE 832,832,832,832'):
        raise ValueError('MatchAnything-ELoFTR: niezgodny model, konfiguracja lub precyzja.')
    for key in ('source_path', 'weights_path', 'actual_device'):
        _text(metadata.get(key))
    for key in ('source_sha256', 'weights_sha256'):
        if re.fullmatch('[0-9a-f]{64}', metadata.get(key, '')) is None:
            raise ValueError('MatchAnything-ELoFTR: brak poprawnej sumy SHA-256.')
    if re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', metadata.get('source_commit', '')) is None:
        raise ValueError('MatchAnything-ELoFTR: brak wersji kodu.')
    if metadata.get('requested_device') not in ('auto', 'cpu', 'cuda'):
        raise ValueError('MatchAnything-ELoFTR: nieprawidłowe urządzenie.')


def validate_lightglue_provenance(provenance: tuple[tuple[str, str], ...]) -> None:
    """Validate both saved model identities without loading optional resources."""
    from stmviewer.lightglue_resources import (
        COORDINATE_MAPPING, EXTRACTOR_CONFIG, MAX_KEYPOINTS, MODEL_CONFIG, PRECISION, PREPROCESSING,
    )
    metadata = dict(_provenance(provenance))
    expected = {
        'model': 'LightGlue + SuperPoint',
        'weights_variant': 'superpoint_lightglue.pth',
        'extractor_weights_variant': 'superpoint_v1.pth',
        'extractor_config': EXTRACTOR_CONFIG,
        'model_config': MODEL_CONFIG,
        'precision': PRECISION,
        'max_keypoints': str(MAX_KEYPOINTS),
        'coordinate_mapping': COORDINATE_MAPPING,
        'preprocessing': PREPROCESSING,
        'aggregation': 'translation-consensus-v2',
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError('LightGlue + SuperPoint: niezgodny model, konfiguracja lub przygotowanie.')
    for key in ('source_path', 'weights_path', 'extractor_weights_path', 'interpreter_path', 'actual_device'):
        _text(metadata.get(key))
    for key in ('source_sha256', 'weights_sha256', 'extractor_weights_sha256'):
        if re.fullmatch('[0-9a-f]{64}', metadata.get(key, '')) is None:
            raise ValueError('LightGlue + SuperPoint: brak poprawnej sumy SHA-256.')
    if re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', metadata.get('source_commit', '')) is None:
        raise ValueError('LightGlue + SuperPoint: brak wersji kodu.')
    if metadata.get('requested_device') not in ('auto', 'cpu', 'cuda'):
        raise ValueError('LightGlue + SuperPoint: nieprawidłowe urządzenie.')



def validate_akaze_provenance(provenance: tuple[tuple[str, str], ...]) -> None:
    """Restore AKAZE identity without importing OpenCV or running the estimator."""
    from stmviewer.akaze_matcher import ADAPTER_VERSION, DETECTOR_CONFIG, MATCHER_CONFIG, NORMALIZATION
    metadata = dict(_provenance(provenance))
    expected = {
        'model': 'AKAZE', 'adapter_version': ADAPTER_VERSION,
        'detector': DETECTOR_CONFIG, 'matcher': MATCHER_CONFIG,
        'selection': 'all mutual matches; no distance cutoff or score weighting',
        'preprocessing': NORMALIZATION + '; native; no padding',
        'coordinate_mapping': 'original-pixels; scale_xy=1,1',
        'aggregation': 'translation-consensus-v2',
        'requested_device': 'cpu', 'actual_device': 'CPU',
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError('AKAZE: niezgodna konfiguracja detektora, matchera lub urządzenia.')
    if any(key in metadata for key in ('weights_path', 'weights_sha256', 'extractor_weights_path')):
        raise ValueError('AKAZE: metoda CPU nie używa plików wag.')
    _text(metadata.get('library_opencv'))
    if re.fullmatch('[0-9a-f]{64}', metadata.get('opencv_build_sha256', '')) is None:
        raise ValueError('AKAZE: brak identyfikatora kompilacji OpenCV.')

def validate_correspondence_method(value: CorrespondenceDiagnostics | None, method: str) -> None:
    """The persisted preparation and provenance must belong to the named estimator."""
    if value is None:
        return
    if method in ('AKAZE', 'akaze'):
        validate_akaze_provenance(value.model_provenance)
        expected = ('minmax-uint8-round-v1', 1)
        if (value.settings_version != 2 or len(value.preparation) != 2
                or any(item.scale_xy != (1., 1.) or item.padding_ltrb != (0, 0, 0, 0)
                       or item.model_shape != item.original_shape for item in value.preparation)):
            raise ValueError('AKAZE: niezgodna geometria oryginałów lub wersja konsensusu.')
    elif method in ('RoMa v2', 'roma_v2'):
        validate_roma_provenance(value.model_provenance)
        expected = ('minmax-float32-rgb-v1', 3)
        if len(value.preparation) != 2:
            raise ValueError('RoMa: brak przygotowania obu obrazów.')
    elif method in ('MatchAnything-ELoFTR', 'matchanything_eloftr'):
        validate_matchanything_provenance(value.model_provenance)
        expected = ('minmax-uint8-demo-gray-v1', 1)
        if len(value.preparation) != 2:
            raise ValueError('MatchAnything-ELoFTR: brak przygotowania obu obrazów.')
    elif method in ('LightGlue + SuperPoint', 'lightglue_superpoint'):
        validate_lightglue_provenance(value.model_provenance)
        expected = ('minmax-float32-v1', 1)
        if (value.settings_version != 2 or len(value.preparation) != 2
                or any(item.scale_xy != (1., 1.) or item.padding_ltrb != (0, 0, 0, 0)
                       or item.model_shape != item.original_shape for item in value.preparation)):
            raise ValueError('LightGlue + SuperPoint: niezgodna geometria oryginałów lub wersja konsensusu.')
    elif method in ('EfficientLoFTR', 'efficient_loftr'):
        if dict(value.model_provenance).get('model') not in (None, 'EfficientLoFTR'):
            raise ValueError('Korespondencje: model nie odpowiada metodzie EfficientLoFTR.')
        expected = ('minmax-float32-v1', 1)
    else:
        raise ValueError('Korespondencje: nieobsługiwana metoda.')
    if any((item.normalization, item.channels) != expected for item in value.preparation):
        raise ValueError('Korespondencje: przygotowanie nie odpowiada metodzie.')
