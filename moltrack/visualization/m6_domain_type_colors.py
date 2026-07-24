from __future__ import annotations

from colorsys import hsv_to_rgb


M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR = (120, 125, 130, 210)
_TYPE_COLORS = (
    (0, 114, 178, 220),
    (213, 94, 0, 220),
    (0, 158, 115, 220),
    (204, 121, 167, 220),
    (230, 159, 0, 220),
    (86, 180, 233, 220),
    (122, 90, 170, 220),
    (60, 60, 60, 220),
)
_GOLDEN_RATIO_CONJUGATE = 0.6180339887498949
_EXTENDED_SATURATIONS = (0.62, 0.74, 0.86)
_EXTENDED_VALUES = (0.72, 0.84, 0.94)


def m6_domain_type_color(type_id: int) -> tuple[int, int, int, int]:
    if isinstance(type_id, bool) or not isinstance(type_id, int) or type_id < 0:
        raise ValueError("type_id must be a non-negative integer.")
    if type_id < len(_TYPE_COLORS):
        return _TYPE_COLORS[type_id]
    hue = (0.11 + type_id * _GOLDEN_RATIO_CONJUGATE) % 1.0
    saturation = _EXTENDED_SATURATIONS[
        (type_id // len(_TYPE_COLORS)) % len(_EXTENDED_SATURATIONS)
    ]
    value = _EXTENDED_VALUES[
        (type_id // (len(_TYPE_COLORS) * len(_EXTENDED_SATURATIONS)))
        % len(_EXTENDED_VALUES)
    ]
    red, green, blue = hsv_to_rgb(hue, saturation, value)
    return (
        round(red * 255.0),
        round(green * 255.0),
        round(blue * 255.0),
        220,
    )


__all__ = [
    "M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR",
    "m6_domain_type_color",
]
