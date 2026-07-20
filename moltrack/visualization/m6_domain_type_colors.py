from __future__ import annotations


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


def m6_domain_type_color(type_id: int) -> tuple[int, int, int, int]:
    if isinstance(type_id, bool) or not isinstance(type_id, int) or type_id < 0:
        raise ValueError("type_id must be a non-negative integer.")
    return _TYPE_COLORS[type_id % len(_TYPE_COLORS)]


__all__ = [
    "M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR",
    "m6_domain_type_color",
]
