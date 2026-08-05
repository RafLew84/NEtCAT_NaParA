from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from numbers import Integral
from typing import Literal

from .geometry import GeometryMode, M6CanonicalFrame
from .models import M6FrameComputation


DEFAULT_M6_CACHE_MAX_ENTRIES = 64
M6CacheDisposition = Literal["available", "stale", "missing"]


@dataclass(frozen=True)
class M6FrameCacheKey:
    """Complete computational identity of one canonical M6 frame input."""

    physical_frame_id: str
    geometry_mode: GeometryMode
    coordinate_transform_fingerprint: str
    m6_settings_fingerprint: str
    m6_algorithm_version: str


class M6FrameCache:
    """Entry-count-bounded LRU for complete M6 frame computations."""

    def __init__(
        self,
        *,
        max_entries: int = DEFAULT_M6_CACHE_MAX_ENTRIES,
    ) -> None:
        if (
            not isinstance(max_entries, Integral)
            or isinstance(max_entries, bool)
            or max_entries <= 0
        ):
            raise ValueError("max_entries must be a positive integer.")
        self.max_entries: int = int(max_entries)
        self._entries: OrderedDict[M6FrameCacheKey, M6FrameComputation] = (
            OrderedDict()
        )

    def lookup(
        self,
        key: M6FrameCacheKey,
    ) -> tuple[M6CacheDisposition, M6FrameComputation | None]:
        computation = self._entries.get(key)
        if computation is not None:
            self._entries.move_to_end(key)
            return "available", computation
        if any(
            existing.physical_frame_id == key.physical_frame_id
            for existing in self._entries
        ):
            return "stale", None
        return "missing", None

    def put(
        self,
        key: M6FrameCacheKey,
        computation: M6FrameComputation,
    ) -> None:
        self._entries.pop(key, None)
        self._entries[key] = computation
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)


def m6_frame_cache_key(
    frame: M6CanonicalFrame,
    *,
    geometry_mode: GeometryMode,
    m6_settings_fingerprint: str,
    m6_algorithm_version: str,
) -> M6FrameCacheKey:
    return M6FrameCacheKey(
        physical_frame_id=frame.physical_frame_id,
        geometry_mode=geometry_mode,
        coordinate_transform_fingerprint=frame.coordinate_transform_fingerprint,
        m6_settings_fingerprint=m6_settings_fingerprint,
        m6_algorithm_version=m6_algorithm_version,
    )
