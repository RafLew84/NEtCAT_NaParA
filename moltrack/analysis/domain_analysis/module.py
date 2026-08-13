from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from math import fsum
from typing import TYPE_CHECKING, Protocol

from .backend_contract import DomainBackendIdentity
from .cache import (
    DEFAULT_CLASSIFIER_CACHE_MAX_ENTRIES,
    DEFAULT_M6_CACHE_MAX_ENTRIES,
    ClassifierFrameCache,
    M6CacheDisposition,
    M6FrameCache,
    RawFrameFingerprintMemo,
    m6_frame_cache_key,
)
from .canonical_geometry import canonicalize_frame
from .diagnostic_funnel import build_molecule_diagnostic_funnels
from .classifier_runner import (
    MoleculeClassifierAdapter,
    not_run_classifier_outcomes,
    run_requested_classifiers,
)
from .events import cancellation_requested, emit_event
from .fingerprints import canonical_sha256
from .geometry import (
    DomainAnalysisSeries,
    M6AnalyzedMolecule,
    M6CanonicalFrame,
    M6PublishedMolecule,
)
from .models import (
    DomainAnalysisEvent,
    DomainAnalysisFailure,
    DomainAnalysisRequest,
    DomainAnalysisResult,
    GeometryMode,
    M6ComponentMembership,
    M6ComponentType,
    M6FrameComputation,
    M6FrameGate,
    M6Gate,
    M6PublishedComponent,
)
from .m6_preset_library import M6RunConfiguration

if TYPE_CHECKING:
    from .session_cache_scope import DomainAnalysisSessionCacheRecords


class M6Adapter(Protocol):
    backend_identity: DomainBackendIdentity

    def analyze_frame(
        self,
        frame: M6CanonicalFrame,
        *,
        frame_index: int,
        geometry_mode: GeometryMode,
    ) -> M6FrameComputation: ...


class M6FrameAnalysisError(RuntimeError):
    """Expected M6 backend failure for the frame currently being analyzed."""


class DomainAnalysisModule:
    """Synchronous seam that owns M6 gate construction and publication."""

    def __init__(
        self,
        backend_adapters: Mapping[str, M6Adapter],
        classifier_adapters: Mapping[str, MoleculeClassifierAdapter],
        *,
        m6_cache_max_entries: int = DEFAULT_M6_CACHE_MAX_ENTRIES,
        classifier_cache_max_entries: int = (
            DEFAULT_CLASSIFIER_CACHE_MAX_ENTRIES
        ),
    ) -> None:
        self._backend_adapters = dict(backend_adapters)
        _validate_backend_registry(self._backend_adapters)
        self._classifier_adapters = dict(classifier_adapters)
        self._m6_cache = M6FrameCache(max_entries=m6_cache_max_entries)
        self._classifier_cache = ClassifierFrameCache(
            max_entries=classifier_cache_max_entries,
        )
        self._raw_frame_fingerprints = RawFrameFingerprintMemo(
            max_entries=classifier_cache_max_entries,
        )

    def run(
        self,
        series: DomainAnalysisSeries,
        request: DomainAnalysisRequest,
        *,
        on_event: Callable[[DomainAnalysisEvent], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> DomainAnalysisResult:
        _validate_run_request(
            request,
            self._backend_adapters,
            self._classifier_adapters,
        )
        assert request.backend_id is not None
        adapter = _adapter_for_run(
            self._backend_adapters[request.backend_id],
            request.m6_configuration,
        )
        identity = adapter.backend_identity
        emit_event(on_event, "run", "started", "Domain Analysis started.")
        m6_range = self._run_m6_range(
            series, request, adapter, identity,
            on_event=on_event, is_cancelled=is_cancelled,
        )
        if isinstance(m6_range, DomainAnalysisResult):
            return m6_range
        gate, canonical_frames = m6_range
        emit_event(on_event, "m6", "published", "Complete M6 gate published.")
        result = self._complete_run(
            series, request, gate, canonical_frames,
            on_event=on_event, is_cancelled=is_cancelled,
        )
        return replace(
            result,
            molecule_diagnostic_funnels=(
                build_molecule_diagnostic_funnels(result)
            ),
        )

    def session_cache_records(
        self,
    ) -> DomainAnalysisSessionCacheRecords:
        """Return the complete bounded caches in schema-v2 record form."""
        from .session_cache_scope import DomainAnalysisSessionCacheRecords
        from .session_state import (
            DomainAnalysisClassifierCacheRecord,
            DomainAnalysisM6CacheRecord,
        )

        return DomainAnalysisSessionCacheRecords(
            m6_records=tuple(
                DomainAnalysisM6CacheRecord(key=key, computation=computation)
                for key, computation in self._m6_cache.records()
            ),
            classifier_records=tuple(
                DomainAnalysisClassifierCacheRecord(key=key, record=record)
                for key, record in self._classifier_cache.records()
            ),
        )

    def restore_session_cache_records(
        self,
        records: DomainAnalysisSessionCacheRecords,
    ) -> None:
        """Atomically replace the module caches from validated schema-v2 state."""
        from .session_cache_scope import DomainAnalysisSessionCacheRecords

        if not isinstance(records, DomainAnalysisSessionCacheRecords):
            raise TypeError("records must be DomainAnalysisSessionCacheRecords.")
        restored_m6 = M6FrameCache(max_entries=self._m6_cache.max_entries)
        restored_classifier = ClassifierFrameCache(
            max_entries=self._classifier_cache.max_entries,
        )
        for m6_record in records.m6_records:
            restored_m6.put(m6_record.key, m6_record.computation)
        for classifier_record in records.classifier_records:
            restored_classifier.put(
                classifier_record.key,
                classifier_record.record,
            )
        self._m6_cache = restored_m6
        self._classifier_cache = restored_classifier

    def _run_m6_range(
        self,
        series: DomainAnalysisSeries,
        request: DomainAnalysisRequest,
        adapter: M6Adapter,
        identity: DomainBackendIdentity,
        *,
        on_event: Callable[[DomainAnalysisEvent], None] | None,
        is_cancelled: Callable[[], bool] | None,
    ) -> tuple[M6Gate, tuple[M6CanonicalFrame, ...]] | DomainAnalysisResult:
        frames: list[M6FrameGate] = []
        canonical_frames: list[M6CanonicalFrame] = []
        for frame_index in request.frame_indices:
            if cancellation_requested(is_cancelled):
                return _canceled_result(
                    request.classifier_ids,
                    self._classifier_adapters,
                    on_event=on_event,
                )
            try:
                published_frame, disposition, canonical_frame = self._run_m6_frame(
                    series,
                    request,
                    adapter,
                    identity,
                    frame_index=frame_index,
                )
            except M6FrameAnalysisError as exc:
                return _failed_result(
                    exc,
                    frame_index=frame_index,
                    classifier_ids=request.classifier_ids,
                    classifier_adapters=self._classifier_adapters,
                    on_event=on_event,
                )
            frames.append(published_frame)
            canonical_frames.append(canonical_frame)
            _emit_m6_frame_progress(on_event, disposition, frame_index)
            if cancellation_requested(is_cancelled):
                return _canceled_result(
                    request.classifier_ids,
                    self._classifier_adapters,
                    on_event=on_event,
                )
        return M6Gate(frames=tuple(frames)), tuple(canonical_frames)

    def _complete_run(
        self,
        series: DomainAnalysisSeries,
        request: DomainAnalysisRequest,
        gate: M6Gate,
        canonical_frames: tuple[M6CanonicalFrame, ...],
        *,
        on_event: Callable[[DomainAnalysisEvent], None] | None,
        is_cancelled: Callable[[], bool] | None,
    ) -> DomainAnalysisResult:
        if request.classifier_ids:
            return run_requested_classifiers(
                series,
                request.classifier_ids,
                gate,
                canonical_frames,
                self._classifier_adapters,
                geometry_mode=request.geometry_mode,
                frame_cache=self._classifier_cache,
                raw_fingerprint_memo=self._raw_frame_fingerprints,
                on_event=on_event,
                is_cancelled=is_cancelled,
            )
        emit_event(on_event, "run", "completed", "M6-only request completed.")
        return DomainAnalysisResult(
            run_status="completed",
            m6_gate=gate,
            classifier_status="not_requested",
            classifier_outcomes=None,
        )

    def _run_m6_frame(
        self,
        series: DomainAnalysisSeries,
        request: DomainAnalysisRequest,
        adapter: M6Adapter,
        identity: DomainBackendIdentity,
        *,
        frame_index: int,
    ) -> tuple[M6FrameGate, M6CacheDisposition, M6CanonicalFrame]:
        canonical_frame = canonicalize_frame(
            series,
            frame_index=frame_index,
            geometry_mode=request.geometry_mode,
        )
        cache_key = m6_frame_cache_key(
            canonical_frame,
            geometry_mode=request.geometry_mode,
            backend_identity=identity,
            configuration_fingerprint=(
                request.m6_configuration.configuration_fingerprint
                if request.m6_configuration is not None
                else None
            ),
        )
        disposition, cached = self._m6_cache.lookup(cache_key)
        if cached is None:
            computation = adapter.analyze_frame(
                canonical_frame,
                frame_index=frame_index,
                geometry_mode=request.geometry_mode,
            )
            _validate_computation(
                computation,
                canonical_frame,
                frame_index=frame_index,
                backend_identity=identity,
            )
        else:
            computation = replace(cached, frame_index=frame_index)
        published = _publish_frame(
            computation,
            canonical_frame,
            backend_identity=identity,
        )
        if cached is None:
            self._m6_cache.put(cache_key, computation)
        return published, disposition, canonical_frame


def _emit_m6_frame_progress(
    on_event: Callable[[DomainAnalysisEvent], None] | None,
    disposition: M6CacheDisposition,
    frame_index: int,
) -> None:
    emit_event(
        on_event,
        "m6",
        "progress",
        (
            "M6 frame reused from cache."
            if disposition == "available"
            else "M6 frame completed without publishing a partial gate."
        ),
        frame_index=frame_index,
    )

def _validate_run_request(
    request: DomainAnalysisRequest,
    backend_adapters: Mapping[str, M6Adapter],
    classifier_adapters: Mapping[str, MoleculeClassifierAdapter],
) -> None:
    if not isinstance(request, DomainAnalysisRequest):
        raise TypeError("request must be a DomainAnalysisRequest.")
    if request.backend_id is None:
        raise ValueError("Domain Analysis requires an explicit domain backend.")
    if request.backend_id is not None and request.backend_id not in backend_adapters:
        raise ValueError(f"Unavailable domain backend: {request.backend_id!r}.")
    unknown_classifiers = set(request.classifier_ids).difference(
        classifier_adapters
    )
    if unknown_classifiers:
        raise ValueError(
            f"Unavailable classifier IDs: {sorted(unknown_classifiers)!r}."
        )


def _adapter_for_run(
    adapter: M6Adapter,
    configuration: M6RunConfiguration | None,
) -> M6Adapter:
    factory = getattr(adapter, "for_run", None)
    if configuration is None:
        if callable(factory):
            raise ValueError(
                "A frozen M6 configuration is required by the selected backend."
            )
        return adapter
    if not callable(factory):
        if adapter.backend_identity == configuration.backend_identity:
            return adapter
        raise ValueError(
            "Selected domain backend cannot execute the frozen M6 configuration."
        )
    configured = factory(configuration)
    if configured.backend_identity != configuration.backend_identity:
        raise ValueError("Domain backend did not preserve the frozen configuration.")
    return configured


def _validate_backend_registry(
    adapters: Mapping[str, M6Adapter],
) -> None:
    if not adapters:
        raise ValueError("Domain backend registry cannot be empty.")
    for backend_id, adapter in adapters.items():
        if not isinstance(adapter.backend_identity, DomainBackendIdentity):
            raise TypeError("Domain adapter must expose DomainBackendIdentity.")
        if backend_id != adapter.backend_identity.backend_id:
            raise ValueError("Domain backend registry key does not match its adapter.")


def _validate_computation(
    computation: M6FrameComputation,
    canonical_frame: M6CanonicalFrame,
    *,
    frame_index: int,
    backend_identity: DomainBackendIdentity,
) -> None:
    if not isinstance(computation, M6FrameComputation):
        raise TypeError("M6 adapter must return M6FrameComputation.")
    if computation.frame_index != frame_index:
        raise ValueError("M6 adapter returned a result for another frame.")
    if computation.backend_identity != backend_identity:
        raise ValueError("Domain backend identity changed during the run.")
    if (
        computation.molecules != canonical_frame.molecules
        or computation.analyzed_pixels_xy != canonical_frame.analyzed_pixels_xy
        or computation.pixel_area_nm2 != canonical_frame.pixel_area_nm2
        or computation.coordinate_frame != canonical_frame.coordinate_frame
        or computation.coordinate_transform_fingerprint
        != canonical_frame.coordinate_transform_fingerprint
    ):
        raise ValueError("M6 adapter changed canonical frame geometry.")


def _failed_result(
    error: M6FrameAnalysisError,
    *,
    frame_index: int,
    classifier_ids: tuple[str, ...],
    classifier_adapters: Mapping[str, MoleculeClassifierAdapter],
    on_event: Callable[[DomainAnalysisEvent], None] | None,
) -> DomainAnalysisResult:
    message = str(error).strip() or error.__class__.__name__
    emit_event(on_event, "m6", "failed", message, frame_index=frame_index)
    outcomes = not_run_classifier_outcomes(
        classifier_ids, classifier_adapters, on_event=on_event,
    )
    emit_event(on_event, "run", "failed", "Domain Analysis failed.")
    return DomainAnalysisResult(
        run_status="failed",
        m6_gate=None,
        classifier_status="not_run" if outcomes is not None else "not_requested",
        classifier_outcomes=outcomes,
        failure=DomainAnalysisFailure(
            stage_id="m6",
            frame_index=frame_index,
            message=message,
        ),
    )


def _canceled_result(
    classifier_ids: tuple[str, ...],
    classifier_adapters: Mapping[str, MoleculeClassifierAdapter],
    *,
    on_event: Callable[[DomainAnalysisEvent], None] | None,
) -> DomainAnalysisResult:
    emit_event(
        on_event,
        "m6",
        "canceled",
        "M6 range canceled before atomic publication.",
    )
    outcomes = not_run_classifier_outcomes(
        classifier_ids, classifier_adapters, on_event=on_event,
    )
    emit_event(on_event, "run", "canceled", "Domain Analysis canceled.")
    return DomainAnalysisResult(
        run_status="canceled",
        m6_gate=None,
        classifier_status="not_run" if outcomes is not None else "not_requested",
        classifier_outcomes=outcomes,
        failure=None,
    )


def _publish_frame(
    computation: M6FrameComputation,
    canonical_frame: M6CanonicalFrame,
    *,
    backend_identity: DomainBackendIdentity,
) -> M6FrameGate:
    molecule_by_id = {value.source_id: value for value in computation.molecules}
    memberships = computation.full_domains + computation.small_ordered_islands
    _validate_membership_source_ids(memberships, known_ids=set(molecule_by_id))
    assigned_ids = {
        source_id
        for membership in memberships
        for source_id in membership.source_ids
    }
    partition_pixels = _partition_pixels_by_nearest_molecule(
        computation.molecules,
        assigned_ids=assigned_ids,
    )
    full_domains = tuple(
        _publish_component(
            value,
            "full_domain",
            molecule_by_id,
            partition_pixels,
            computation.pixel_area_nm2,
        )
        for value in computation.full_domains
    )
    islands = tuple(
        _publish_component(
            value,
            "small_ordered_island",
            molecule_by_id,
            partition_pixels,
            computation.pixel_area_nm2,
        )
        for value in computation.small_ordered_islands
    )
    outside_ids = tuple(sorted(set(molecule_by_id).difference(assigned_ids)))
    outside = tuple(molecule_by_id[source_id] for source_id in outside_ids)
    outside_pixels = _partition_pixels(outside, partition_pixels)
    return M6FrameGate(
        frame_index=computation.frame_index,
        physical_frame_id=canonical_frame.physical_frame_id,
        coordinate_frame=computation.coordinate_frame,
        coordinate_transform_fingerprint=computation.coordinate_transform_fingerprint,
        presentation_provenance=canonical_frame.presentation_provenance,
        source_geometry_fingerprint=_source_geometry_fingerprint(
            computation.molecules,
            pixel_area_nm2=computation.pixel_area_nm2,
        ),
        backend_identity=backend_identity,
        native_evidence=computation.native_evidence,
        pixel_area_nm2=computation.pixel_area_nm2,
        full_domains=full_domains,
        small_ordered_islands=islands,
        outside_members=tuple(
            M6PublishedMolecule(
                source_id=value.source_id,
                source_kind=value.source_kind,
                point_xy_nm=value.centroid_xy_nm,
                raw_centroid_xy=value.raw_centroid_xy,
            )
            for value in outside
        ),
        outside_pixels_xy=outside_pixels,
        outside_area_nm2=len(outside_pixels) * computation.pixel_area_nm2,
        analyzed_source_ids=tuple(molecule_by_id),
        analyzed_pixels_xy=computation.analyzed_pixels_xy,
        analyzed_area_nm2=(
            len(computation.analyzed_pixels_xy) * computation.pixel_area_nm2
        ),
    )


def _publish_component(
    membership: M6ComponentMembership,
    component_type: M6ComponentType,
    molecule_by_id: dict[str, M6AnalyzedMolecule],
    partition_pixels: dict[str, tuple[tuple[int, int], ...]],
    pixel_area_nm2: float,
) -> M6PublishedComponent:
    molecules = tuple(molecule_by_id[source_id] for source_id in membership.source_ids)
    points = tuple(value.centroid_xy_nm for value in molecules)
    footprint_pixels = _partition_pixels(molecules, partition_pixels)
    x_values = tuple(value[0] for value in points)
    y_values = tuple(value[1] for value in points)
    count = len(molecules)
    identity_fingerprint = canonical_sha256({
        "component_type": component_type,
        "source_ids": membership.source_ids,
    })
    component_prefix = (
        "m6-full"
        if component_type == "full_domain"
        else "m6-island"
    )
    return M6PublishedComponent(
        lattice_domain_id=(
            f"{component_prefix}-{identity_fingerprint[:12]}"
        ),
        component_type=component_type,
        members=tuple(
            M6PublishedMolecule(
                source_id=value.source_id,
                source_kind=value.source_kind,
                point_xy_nm=value.centroid_xy_nm,
                raw_centroid_xy=value.raw_centroid_xy,
            )
            for value in molecules
        ),
        core_source_ids=membership.core_source_ids,
        halo_source_ids=membership.halo_source_ids,
        footprint_pixels_xy=footprint_pixels,
        footprint_area_nm2=len(footprint_pixels) * pixel_area_nm2,
        centroid_xy_nm=(fsum(x_values) / count, fsum(y_values) / count),
        bounds_xyxy_nm=(min(x_values), min(y_values), max(x_values), max(y_values)),
        qc_flags=membership.qc_flags,
    )


def _validate_membership_source_ids(
    memberships: tuple[M6ComponentMembership, ...],
    *,
    known_ids: set[str],
) -> None:
    for membership in memberships:
        member_ids = set(membership.source_ids)
        unknown_ids = member_ids.difference(known_ids)
        if unknown_ids:
            raise ValueError(
                "M6 component references unknown source IDs: "
                f"{sorted(unknown_ids)!r}."
            )


def _partition_pixels_by_nearest_molecule(
    molecules: tuple[M6AnalyzedMolecule, ...],
    *,
    assigned_ids: set[str],
) -> dict[str, tuple[tuple[int, int], ...]]:
    candidates_by_pixel: dict[
        tuple[int, int],
        list[M6AnalyzedMolecule],
    ] = {}
    for molecule in molecules:
        for pixel in molecule.footprint_pixels_xy:
            candidates_by_pixel.setdefault(pixel, []).append(molecule)
    owned: dict[str, list[tuple[int, int]]] = {
        molecule.source_id: [] for molecule in molecules
    }
    for pixel, candidates in candidates_by_pixel.items():
        pixel_center = (pixel[0] + 0.5, pixel[1] + 0.5)
        owner = min(
            candidates,
            key=lambda molecule: (
                (molecule.raw_centroid_xy[0] - pixel_center[0]) ** 2
                + (molecule.raw_centroid_xy[1] - pixel_center[1]) ** 2,
                molecule.source_id not in assigned_ids,
                molecule.source_id,
            ),
        )
        owned[owner.source_id].append(pixel)
    return {
        source_id: tuple(sorted(pixels))
        for source_id, pixels in owned.items()
    }


def _partition_pixels(
    molecules: tuple[M6AnalyzedMolecule, ...],
    partition_pixels: dict[str, tuple[tuple[int, int], ...]],
) -> tuple[tuple[int, int], ...]:
    return tuple(sorted({
        pixel
        for molecule in molecules
        for pixel in partition_pixels[molecule.source_id]
    }))


def _source_geometry_fingerprint(
    molecules: tuple[M6AnalyzedMolecule, ...],
    *,
    pixel_area_nm2: float,
) -> str:
    payload = {
        "pixel_area_nm2": pixel_area_nm2,
        "molecules": [
            {
                "source_id": value.source_id,
                "centroid_xy_nm": value.centroid_xy_nm,
                "footprint_pixels_xy": value.footprint_pixels_xy,
            }
            for value in molecules
        ],
    }
    return canonical_sha256(payload)
