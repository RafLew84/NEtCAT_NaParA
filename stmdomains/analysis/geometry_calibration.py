"""Strict, explicit XY calibration for geometry only; no inferred physical units."""

from collections.abc import Mapping
import re

from stmdomains.core.geometry import PixelCalibration


def calibration_from_header(header: Mapping, shape: tuple[int, int]) -> PixelCalibration:
    fallback = PixelCalibration()
    try:
        general, control = header['General Info'], header['Control']
        if (int(general['Number of rows']), int(general['Number of columns'])) != shape:
            return fallback
        scales = []
        for name, pixels in zip(('X Amplitude', 'Y Amplitude'), shape[::-1]):
            match = re.fullmatch(r'\s*([+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(nm|um|µm|μm|pm|m|Å|Å)\s*', str(control[name]))
            if match is None:
                return fallback
            factors = {'nm': 1., 'um': 1000., 'µm': 1000., 'μm': 1000., 'pm': .001,
                       'm': 1e9, 'Å': .1, 'Å': .1}
            scales.append(float(match[1]) * factors[match[2]] / pixels)
        return PixelCalibration(scales[0], scales[1], 'nm', 'Nagłówek MPP: X/Y Amplitude / liczba kolumn/wierszy; bez walidacji metrologicznej.')
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        return fallback
