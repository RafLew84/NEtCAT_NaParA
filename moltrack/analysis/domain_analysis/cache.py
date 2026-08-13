from __future__ import annotations

import hashlib
import json
import weakref
from collections import OrderedDict
from dataclasses import asdict, dataclass, replace
from numbers import Integral
from typing import Generic, Literal, TypeAlias, TypeVar

import numpy as np

from .backend_contract import DomainBackendIdentity
from .classifier_contract import ClassifierConfiguration
from .classifier_models import (
    MoleculeClassification,
    classifier_frame_result_fingerprint,
)
from .fingerprints import canonical_sha256
from .geometry import GeometryMode, M6CanonicalFrame
from .models import M6FrameComputation, M6FrameGate


DEFAULT_M6_CACHE_MAX_ENTRIES = 64
DEFAULT_CLASSIFIER_CACHE_MAX_ENTRIES = 64
CacheDisposition: TypeAlias = Literal["available", "stale", "missing"]
M6CacheDisposition: TypeAlias = CacheDisposition
ClassifierCacheDisposition: TypeAlias = CacheDisposition
_Key = TypeVar("_Key")
_Value = TypeVar("_Value")


class _BoundedLru(Generic[_Key, _Value]):
    """Shared entry-count-bounded LRU storage without domain invalidation."""

    def __init__(self, *, max_entries: int) -> None:
        self.max_entries = _positive_entry_limit(max_entries)
        self._entries: OrderedDict[_Key, _Value] = OrderedDict()

    def get(self, key: _Key) -> _Value | None:
        value = self._entries.get(key)
        if value is not None:
            self._entries.move_to_end(key)
        return value

    def peek(self, key: _Key) -> _Value | None:
        return self._entries.get(key)

    def keys(self) -> tuple[_Key, ...]:
        return tuple(self._entries)

    def items(self) -> tuple[tuple[_Key, _Value], ...]:
        return tuple(self._entries.items())

    def remove(self, key: _Key) -> None:
        self._entries.pop(key, None)

    def put(self, key: _Key, value: _Value) -> None:
        self._entries.pop(key, None)
        self._entries[key] = value
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)


@dataclass(frozen=True)
class M6FrameCacheKey:
    """Complete computational identity of one canonical M6 frame input."""

    physical_frame_id: str
    geometry_mode: GeometryMode
    coordinate_transform_fingerprint: str
    backend_identity: DomainBackendIdentity
    configuration_fingerprint: str | None = None

    @property
    def m6_settings_fingerprint(self) -> str:
        return self.backend_identity.settings_fingerprint

    @property
    def m6_algorithm_version(self) -> str:
        return self.backend_identity.algorithm_version


class M6FrameCache:
    """Entry-count-bounded LRU for complete M6 frame computations."""

    def __init__(
        self,
        *,
        max_entries: int = DEFAULT_M6_CACHE_MAX_ENTRIES,
    ) -> None:
        self._entries = _BoundedLru[M6FrameCacheKey, M6FrameComputation](
            max_entries=max_entries,
        )
        self.max_entries = self._entries.max_entries

    def lookup(
        self,
        key: M6FrameCacheKey,
    ) -> tuple[M6CacheDisposition, M6FrameComputation | None]:
        computation = self._entries.get(key)
        if computation is not None:
            return "available", computation
        if any(
            existing.physical_frame_id == key.physical_frame_id
            for existing in self._entries.keys()
        ):
            return "stale", None
        return "missing", None

    def put(
        self,
        key: M6FrameCacheKey,
        computation: M6FrameComputation,
    ) -> None:
        existing = self._entries.peek(key)
        if (
            existing is not None
            and existing.result_fingerprint != computation.result_fingerprint
        ):
            raise ValueError(
                "M6 cache key produced a different result fingerprint."
            )
        self._entries.put(key, computation)

    def records(
        self,
    ) -> tuple[tuple[M6FrameCacheKey, M6FrameComputation], ...]:
        return self._entries.items()


def m6_frame_cache_key(
    frame: M6CanonicalFrame,
    *,
    geometry_mode: GeometryMode,
    backend_identity: DomainBackendIdentity,
    configuration_fingerprint: str | None = None,
) -> M6FrameCacheKey:
    return M6FrameCacheKey(
        physical_frame_id=frame.physical_frame_id,
        geometry_mode=geometry_mode,
        coordinate_transform_fingerprint=frame.coordinate_transform_fingerprint,
        backend_identity=backend_identity,
        configuration_fingerprint=configuration_fingerprint,
    )


@dataclass(frozen=True)
class ClassifierFrameCacheKey:
    """Complete identity of one classifier's immutable frame input."""

    physical_frame_id: str
    configuration: ClassifierConfiguration
    m6_gate_fingerprint: str
    raw_frame_fingerprint: str | None
    raw_sampling_geometry_fingerprint: str


@dataclass(frozen=True)
class ClassifierFrameCacheRecord:
    """Complete one-frame classifier payload without source pixel retention."""

    classifications: tuple[MoleculeClassification, ...]
    result_fingerprint: str


class ClassifierFrameCache:
    """Entry-count-bounded LRU of complete classifier frame records."""

    def __init__(
        self,
        *,
        max_entries: int = DEFAULT_CLASSIFIER_CACHE_MAX_ENTRIES,
    ) -> None:
        self._entries = _BoundedLru[
            ClassifierFrameCacheKey,
            ClassifierFrameCacheRecord,
        ](max_entries=max_entries)
        self.max_entries = self._entries.max_entries

    def lookup(
        self,
        key: ClassifierFrameCacheKey,
    ) -> tuple[ClassifierCacheDisposition, ClassifierFrameCacheRecord | None]:
        record = self._entries.get(key)
        if record is not None:
            return "available", record
        if any(
            existing.physical_frame_id == key.physical_frame_id
            and existing.configuration.identity.classifier_id
            == key.configuration.identity.classifier_id
            for existing in self._entries.keys()
        ):
            return "stale", None
        return "missing", None

    def put(
        self,
        key: ClassifierFrameCacheKey,
        record: ClassifierFrameCacheRecord,
    ) -> None:
        existing = self._entries.peek(key)
        if (
            existing is not None
            and existing.result_fingerprint != record.result_fingerprint
        ):
            raise ValueError(
                "Classifier cache key produced a different result fingerprint."
            )
        self._entries.put(key, record)

    def records(
        self,
    ) -> tuple[
        tuple[ClassifierFrameCacheKey, ClassifierFrameCacheRecord], ...
    ]:
        return self._entries.items()


@dataclass(frozen=True)
class _RawFrameFingerprintEntry:
    raw_frame: weakref.ReferenceType[np.ndarray]
    fingerprint: str


class RawFrameFingerprintMemo:
    """Bounded SHA-256 memo that never retains raw frame pixels."""

    def __init__(self, *, max_entries: int) -> None:
        self._entries = _BoundedLru[
            tuple[str, int],
            _RawFrameFingerprintEntry,
        ](max_entries=max_entries)
        self.max_entries = self._entries.max_entries

    def fingerprint(
        self,
        physical_frame_id: str,
        raw_frame: np.ndarray,
    ) -> str:
        key = (physical_frame_id, id(raw_frame))
        entry = self._entries.get(key)
        if entry is not None and entry.raw_frame() is raw_frame:
            return entry.fingerprint
        fingerprint = raw_frame_sha256(raw_frame)
        self._entries.put(key, _RawFrameFingerprintEntry(
            raw_frame=weakref.ref(raw_frame),
            fingerprint=fingerprint,
        ))
        self._remove_dead_entries()
        return fingerprint

    def _remove_dead_entries(self) -> None:
        dead = tuple(
            key for key in self._entries.keys()
            if (value := self._entries.peek(key)) is not None
            and value.raw_frame() is None
        )
        for key in dead:
            self._entries.remove(key)


def classifier_frame_cache_key(
    gate_frame: M6FrameGate,
    canonical_frame: M6CanonicalFrame,
    configuration: ClassifierConfiguration,
    *,
    geometry_mode: GeometryMode,
    raw_frame_fingerprint: str | None,
) -> ClassifierFrameCacheKey:
    return ClassifierFrameCacheKey(
        physical_frame_id=gate_frame.physical_frame_id,
        configuration=configuration,
        m6_gate_fingerprint=gate_frame.m6_gate_fingerprint,
        raw_frame_fingerprint=raw_frame_fingerprint,
        raw_sampling_geometry_fingerprint=_sampling_geometry_fingerprint(
            gate_frame,
            canonical_frame,
            geometry_mode=geometry_mode,
        ),
    )


def classifier_frame_cache_record(
    classifications: tuple[MoleculeClassification, ...],
) -> ClassifierFrameCacheRecord:
    values = tuple(sorted(
        classifications,
        key=lambda value: value.source_id,
    ))
    return ClassifierFrameCacheRecord(
        classifications=values,
        result_fingerprint=classifier_frame_result_fingerprint(values),
    )


def classifications_for_frame_index(
    record: ClassifierFrameCacheRecord,
    frame_index: int,
) -> tuple[MoleculeClassification, ...]:
    if all(value.frame_index == frame_index for value in record.classifications):
        return record.classifications
    return tuple(
        replace(value, frame_index=frame_index)
        for value in record.classifications
    )


def classifier_frame_cache_key_fingerprint(
    key: ClassifierFrameCacheKey,
) -> str:
    return canonical_sha256(asdict(key))


def raw_frame_sha256(raw_frame: np.ndarray) -> str:
    """Hash dtype, shape and exact canonical C-order raw bytes."""

    values = np.asarray(raw_frame)
    if values.dtype.hasobject:
        raise TypeError("Raw classifier frames cannot use an object dtype.")
    header = json.dumps(
        {"dtype": values.dtype.str, "shape": values.shape},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256()
    digest.update(header)
    digest.update(b"\0")
    contiguous = values if values.flags.c_contiguous else np.ascontiguousarray(values)
    digest.update(memoryview(contiguous).cast("B"))
    return digest.hexdigest()


def _sampling_geometry_fingerprint(
    gate_frame: M6FrameGate,
    canonical_frame: M6CanonicalFrame,
    *,
    geometry_mode: GeometryMode,
) -> str:
    molecule_by_id = {
        value.source_id: value for value in canonical_frame.molecules
    }
    domains = []
    for domain in gate_frame.full_domains:
        domains.append({
            "lattice_domain_id": domain.lattice_domain_id,
            "molecules": [
                {
                    "source_id": source_id,
                    "raw_centroid_xy": molecule_by_id[source_id].raw_centroid_xy,
                    "footprint_pixels_xy": (
                        molecule_by_id[source_id].footprint_pixels_xy
                    ),
                }
                for source_id in domain.source_ids
            ],
        })
    return canonical_sha256({
        "schema_version": "domain-analysis-raw-sampling-v1",
        "geometry_mode": geometry_mode,
        "coordinate_transform_fingerprint": (
            canonical_frame.coordinate_transform_fingerprint
        ),
        "domains": domains,
    })


def _positive_entry_limit(value: int) -> int:
    if (
        not isinstance(value, Integral)
        or isinstance(value, bool)
        or value <= 0
    ):
        raise ValueError("max_entries must be a positive integer.")
    return int(value)
