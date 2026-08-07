from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from math import fsum
from typing import Protocol

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


class M6Adapter(Protocol):
    m6_settings_fingerprint: str
    m6_algorithm_version: str

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
        m6_adapter: M6Adapter,
        classifier_adapters: Mapping[str, MoleculeClassifierAdapter],
        *,
        m6_cache_max_entries: int = DEFAULT_M6_CACHE_MAX_ENTRIES,
        classifier_cache_max_entries: int = (
            DEFAULT_CLASSIFIER_CACHE_MAX_ENTRIES
        ),
    ) -> None:
        self._m6_adapter = m6_adapter
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
        _validate_run_request(request, self._classifier_adapters)
        settings_fingerprint = _adapter_identity(
            self._m6_adapter.m6_settings_fingerprint,
            "m6_settings_fingerprint",
        )
        algorithm_version = _adapter_identity(
            self._m6_adapter.m6_algorithm_version,
            "m6_algorithm_version",
        )
        emit_event(on_event, "run", "started", "Domain Analysis started.")
        m6_range = self._run_m6_range(
            series, request, settings_fingerprint, algorithm_version,
            on_event=on_event, is_cancelled=is_cancelled,
        )
        if isinstance(m6_range, DomainAnalysisResult):
            return m6_range
        gate, canonical_frames = m6_range
        emit_event(on_event, "m6", "published", "Complete M6 gate published.")
        return self._complete_run(
            series, request, gate, canonical_frames,
            on_event=on_event, is_cancelled=is_cancelled,
        )

    def _run_m6_range(
        self,
        series: DomainAnalysisSeries,
        request: DomainAnalysisRequest,
        settings_fingerprint: str,
        algorithm_version: str,
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
                    frame_index=frame_index,
                    settings_fingerprint=settings_fingerprint,
                    algorithm_version=algorithm_version,
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
        *,
        frame_index: int,
        settings_fingerprint: str,
        algorithm_version: str,
    ) -> tuple[M6FrameGate, M6CacheDisposition, M6CanonicalFrame]:
        canonical_frame = canonicalize_frame(
            series,
            frame_index=frame_index,
            geometry_mode=request.geometry_mode,
        )
        cache_key = m6_frame_cache_key(
            canonical_frame,
            geometry_mode=request.geometry_mode,
            m6_settings_fingerprint=settings_fingerprint,
            m6_algorithm_version=algorithm_version,
        )
        disposition, cached = self._m6_cache.lookup(cache_key)
        if cached is None:
            computation = self._m6_adapter.analyze_frame(
                canonical_frame,
                frame_index=frame_index,
                geometry_mode=request.geometry_mode,
            )
            _validate_computation(
                computation,
                canonical_frame,
                frame_index=frame_index,
                settings_fingerprint=settings_fingerprint,
            )
        else:
            computation = replace(cached, frame_index=frame_index)
        published = _publish_frame(
            computation,
            canonical_frame,
            m6_algorithm_version=algorithm_version,
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
    classifier_adapters: Mapping[str, MoleculeClassifierAdapter],
) -> None:
    if not isinstance(request, DomainAnalysisRequest):
        raise TypeError("request must be a DomainAnalysisRequest.")
    unknown_classifiers = set(request.classifier_ids).difference(
        classifier_adapters
    )
    if unknown_classifiers:
        raise ValueError(
            f"Unavailable classifier IDs: {sorted(unknown_classifiers)!r}."
        )


def _validate_computation(
    computation: M6FrameComputation,
    canonical_frame: M6CanonicalFrame,
    *,
    frame_index: int,
    settings_fingerprint: str,
) -> None:
    if not isinstance(computation, M6FrameComputation):
        raise TypeError("M6 adapter must return M6FrameComputation.")
    if computation.frame_index != frame_index:
        raise ValueError("M6 adapter returned a result for another frame.")
    if computation.m6_settings_fingerprint != settings_fingerprint:
        raise ValueError("M6 adapter settings fingerprint changed during the run.")
    if (
        computation.molecules != canonical_frame.molecules
        or computation.analyzed_pixels_xy != canonical_frame.analyzed_pixels_xy
        or computation.pixel_area_nm2 != canonical_frame.pixel_area_nm2
        or computation.coordinate_frame != canonical_frame.coordinate_frame
        or computation.coordinate_transform_fingerprint
        != canonical_frame.coordinate_transform_fingerprint
    ):
        raise ValueError("M6 adapter changed canonical frame geometry.")


def _adapter_identity(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"M6 adapter {name} must be a non-empty string.")
    return value.strip()


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
    m6_algorithm_version: str,
) -> M6FrameGate:
    molecule_by_id = {value.source_id: value for value in computation.molecules}
    memberships = computation.full_domains + computation.small_ordered_islands
    _validate_membership_source_ids(memberships, known_ids=set(molecule_by_id))
    full_domains = tuple(
        _publish_component(
            value,
            "full_domain",
            molecule_by_id,
            computation.pixel_area_nm2,
        )
        for value in computation.full_domains
    )
    islands = tuple(
        _publish_component(
            value,
            "small_ordered_island",
            molecule_by_id,
            computation.pixel_area_nm2,
        )
        for value in computation.small_ordered_islands
    )
    assigned_ids = {
        source_id
        for membership in memberships
        for source_id in membership.source_ids
    }
    outside_ids = tuple(sorted(set(molecule_by_id).difference(assigned_ids)))
    outside = tuple(molecule_by_id[source_id] for source_id in outside_ids)
    outside_pixels = _molecule_pixels(outside)
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
        m6_settings_fingerprint=computation.m6_settings_fingerprint,
        m6_algorithm_version=m6_algorithm_version,
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
    pixel_area_nm2: float,
) -> M6PublishedComponent:
    molecules = tuple(molecule_by_id[source_id] for source_id in membership.source_ids)
    points = tuple(value.centroid_xy_nm for value in molecules)
    footprint_pixels = _molecule_pixels(molecules)
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


def _molecule_pixels(
    molecules: tuple[M6AnalyzedMolecule, ...],
) -> tuple[tuple[int, int], ...]:
    return tuple(sorted({
        pixel
        for molecule in molecules
        for pixel in molecule.footprint_pixels_xy
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
