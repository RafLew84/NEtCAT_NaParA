"""Immutable, runtime-free parameters shared by every registration entry point."""
from dataclasses import asdict, dataclass, field
import math

from stmviewer.metadata_values import json_object

PARAMETER_METHODS = {'akaze': 'AKAZE', 'lightglue_superpoint': 'LightGlue + SuperPoint'}


def _number(value: object) -> float:
    if type(value) not in (float, int) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError('Parametry: wymagana skończona liczba.')
    return float(value)


def _integer(value: object, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f'Parametry: wymagana liczba całkowita co najmniej {minimum}.')
    return value


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise ValueError('Parametry: wymagana wartość logiczna.')
    return value


@dataclass(frozen=True)
class ContrastParameters:
    mode: str = 'minmax'
    lower: float = 1.
    upper: float = 99.
    clip_limit: float = 2.
    grid_x: int = 8
    grid_y: int = 8

    def __post_init__(self) -> None:
        if self.mode not in ('minmax', 'percentiles', 'clahe'):
            raise ValueError('Nieznane przygotowanie kontrastu.')
        if not 0 <= _number(self.lower) < _number(self.upper) <= 100:
            raise ValueError('Percentyle: wymagane 0 ≤ dolny < górny ≤ 100.')
        if _number(self.clip_limit) <= 0:
            raise ValueError('Limit CLAHE musi być dodatni.')
        _integer(self.grid_x, 1)
        _integer(self.grid_y, 1)

    def normalization(self, *, uint8: bool) -> str:
        suffix = 'uint8-round' if uint8 else 'float32'
        return f'{self.mode}-{suffix}-v1'


@dataclass(frozen=True)
class AkazeParameters:
    threshold: float = .001
    radius: float = 2.
    contrast: ContrastParameters = field(default_factory=ContrastParameters)

    def __post_init__(self) -> None:
        if _number(self.threshold) <= 0 or _number(self.radius) <= 0:
            raise ValueError('Próg AKAZE i tolerancja zgodności muszą być dodatnie.')
        if not isinstance(self.contrast, ContrastParameters):
            raise ValueError('Nieprawidłowe przygotowanie kontrastu.')


@dataclass(frozen=True)
class LightGlueParameters:
    detection_threshold: float = .0005
    nms_radius: int = 4
    max_keypoints: int = 2048
    filter_threshold: float = .1
    full_computation: bool = False
    radius: float = 2.
    contrast: ContrastParameters = field(default_factory=ContrastParameters)

    def __post_init__(self) -> None:
        if not 0 < _number(self.detection_threshold) <= 1:
            raise ValueError('Próg SuperPoint musi mieścić się w (0,1].')
        if not 0 <= _number(self.filter_threshold) <= 1:
            raise ValueError('Próg LightGlue musi mieścić się w [0,1].')
        if _number(self.radius) <= 0:
            raise ValueError('Tolerancja zgodności musi być dodatnia.')
        _integer(self.nms_radius)
        _integer(self.max_keypoints, 1)
        _boolean(self.full_computation)
        if not isinstance(self.contrast, ContrastParameters):
            raise ValueError('Nieprawidłowe przygotowanie kontrastu.')


FeatureParameters = AkazeParameters | LightGlueParameters


@dataclass(frozen=True)
class MethodProfiles:
    akaze: AkazeParameters = field(default_factory=AkazeParameters)
    lightglue: LightGlueParameters = field(default_factory=LightGlueParameters)

    def get(self, method: str) -> FeatureParameters:
        if method == 'akaze':
            return self.akaze
        if method == 'lightglue_superpoint':
            return self.lightglue
        raise ValueError('Ta metoda nie ma jeszcze edytora parametrów.')


def decode_contrast(value: object) -> ContrastParameters:
    record = json_object(value, set(asdict(ContrastParameters())))
    if not isinstance(record['mode'], str):
        raise ValueError('Nieprawidłowy tryb przygotowania kontrastu.')
    return ContrastParameters(record['mode'], _number(record['lower']), _number(record['upper']),
                              _number(record['clip_limit']), _integer(record['grid_x'], 1),
                              _integer(record['grid_y'], 1))


def decode_profile(method: str, value: object) -> FeatureParameters:
    if method == 'akaze':
        record = json_object(value, set(asdict(AkazeParameters())))
        return AkazeParameters(_number(record['threshold']), _number(record['radius']),
                               decode_contrast(record['contrast']))
    if method == 'lightglue_superpoint':
        record = json_object(value, set(asdict(LightGlueParameters())))
        return LightGlueParameters(
            _number(record['detection_threshold']), _integer(record['nms_radius']),
            _integer(record['max_keypoints'], 1), _number(record['filter_threshold']),
            _boolean(record['full_computation']), _number(record['radius']),
            decode_contrast(record['contrast']))
    raise ValueError('Nieznana metoda parametrów.')


def profiles_record(profiles: MethodProfiles) -> dict[str, object]:
    return {'version': 1, **asdict(profiles)}


def decode_profiles(value: object) -> MethodProfiles:
    record = json_object(value, {'version', 'akaze', 'lightglue'})
    if _integer(record['version']) != 1:
        raise ValueError('Nieobsługiwana wersja parametrów metod.')
    akaze = decode_profile('akaze', record['akaze'])
    lightglue = decode_profile('lightglue_superpoint', record['lightglue'])
    assert isinstance(akaze, AkazeParameters) and isinstance(lightglue, LightGlueParameters)
    return MethodProfiles(akaze, lightglue)
