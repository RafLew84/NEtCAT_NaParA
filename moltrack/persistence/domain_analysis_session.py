from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
from typing import Any, cast

from moltrack.analysis.domain_analysis import (
    DOMAIN_ANALYSIS_RETRY_REQUIRED_DIAGNOSIS,
    DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION,
    ClassifierConfiguration,
    DomainAnalysisPublication,
    DomainAnalysisRequest,
    DomainAnalysisResult,
    DomainAnalysisSessionState,
    DomainAnalysisSessionDiagnostic,
    DomainAnalysisViewSettings,
    DomainComponentKey,
    M6FrameGate,
    M6Gate,
    M6PresentationProvenance,
    M6PublishedComponent,
    validate_classifier_outcome_for_gate,
)
from moltrack.analysis.domain_analysis.events import (
    ClassifierStatus,
    DomainAnalysisRunStatus,
)
from moltrack.analysis.domain_analysis.geometry import (
    CoordinateView,
    GeometryMode,
)
from moltrack.analysis.domain_analysis.models import M6ComponentType
from moltrack.analysis.domain_analysis.classic_diagnostic_funnel import build_classic_molecule_diagnostic_funnels

from .domain_analysis_cache_payload import (
    domain_analysis_cache_from_payload,
    domain_analysis_cache_to_payload,
)
from .domain_backend_payload import (
    backend_evidence_from_payload,
    backend_evidence_to_payload,
    backend_identity_from_payload,
    backend_identity_to_payload,
)
from .domain_analysis_classifier_payload import (
    classifier_configuration_from_payload,
    classifier_configuration_to_payload,
    classifier_outcomes_from_payload,
    classifier_outcomes_to_payload,
)
from .domain_analysis_opaque_payload import opaque_components_from_payload
from .domain_analysis_membership_payload import (
    published_molecule_from_payload,
    published_molecule_to_payload,
)
from .domain_analysis_payload_validation import (
    float_pair_field as _float_pair,
    float_pairs_field as _float_pairs,
    float_quad_field as _float_quad,
    integer_field as _require_integer,
    integer_pair_field as _integer_pair,
    integer_pairs_field as _integer_pairs,
    list_field as _require_list,
    mapping as _require_mapping,
    number_field as _require_number,
    pairs_to_lists as _pairs_to_lists,
    required as _required,
    text_field as _require_text,
    text_list_field as _require_text_list,
)


_PUBLISHED_RESULT_SCHEMA_VERSION = 2
_M6_GATE_SCHEMA_VERSION = 3
_DOMAIN_ANALYSIS_KNOWN_FIELDS = frozenset({
    "schema_version",
    "classifier_status",
    "draft",
    "view_settings",
    "selected_component",
    "run",
    "published_result",
    "cache",
})


def domain_analysis_state_from_ui_state(
    ui_state: Any | None,
) -> DomainAnalysisSessionState | None:
    if isinstance(ui_state, Mapping):
        candidate = ui_state.get("domain_analysis")
    else:
        candidate = getattr(ui_state, "domain_analysis", None)
    if candidate is None:
        return None
    if not isinstance(candidate, DomainAnalysisSessionState):
        raise TypeError(
            "domain_analysis must be a DomainAnalysisSessionState."
        )
    return candidate


def domain_analysis_state_to_payload(
    state: DomainAnalysisSessionState | None,
) -> dict[str, Any]:
    saved = DomainAnalysisSessionState() if state is None else state
    draft = saved.draft
    if draft is not None and draft.backend_id is None:
        raise ValueError("Domain Analysis draft requires an explicit backend.")
    selected = saved.selected_component
    run_status = (
        "retry_required" if saved.run_status == "running" else saved.run_status
    )
    run_diagnosis = (
        DOMAIN_ANALYSIS_RETRY_REQUIRED_DIAGNOSIS
        if saved.run_status == "running"
        else saved.run_diagnosis
    )
    payload = {
        "schema_version": saved.schema_version,
        "classifier_status": saved.classifier_status,
        "draft": (
            None
            if draft is None
            else {
                "frame_start": draft.frame_range.start,
                "frame_stop": draft.frame_range.stop,
                "backend_id": draft.backend_id,
                "geometry_mode": draft.geometry_mode,
                "classifier_ids": list(draft.classifier_ids),
                "physical_frame_ids": list(saved.draft_physical_frame_ids),
                "classifier_configurations": [
                    classifier_configuration_to_payload(value)
                    for value in saved.draft_classifier_configurations
                ],
            }
        ),
        "view_settings": {
            "overlay_visible": saved.view_settings.overlay_visible,
            "overlay_opacity_percent": (
                saved.view_settings.overlay_opacity_percent
            ),
        },
        "selected_component": (
            None
            if selected is None
            else {
                "physical_frame_id": selected.physical_frame_id,
                "lattice_domain_id": selected.lattice_domain_id,
            }
        ),
        "run": {
            "status": run_status,
            "diagnosis": run_diagnosis,
        },
        "published_result": (
            None
            if saved.published_result is None
            else _publication_to_payload(saved.published_result)
        ),
        "cache": domain_analysis_cache_to_payload(
            saved.m6_cache_records,
            saved.classifier_cache_records,
        ),
    }
    payload.update({
        key: deepcopy(value) for key, value in saved.opaque_components
    })
    return payload


def domain_analysis_state_from_payload(
    payload: Any,
) -> DomainAnalysisSessionState:
    section = _require_mapping(payload, "domain_analysis")
    _require_version(
        section,
        DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION,
        "domain_analysis",
    )
    draft, draft_configurations, draft_physical_frame_ids = (
        _draft_from_payload(section)
    )
    m6_cache_records, classifier_cache_records, cache_diagnostics = (
        _cache_from_payload(section)
    )
    classifier_status = _require_text(
        section,
        "classifier_status",
        "domain_analysis",
    )
    publication_payload = _required(section, "published_result", "domain_analysis")
    publication = None
    publication_diagnostics: tuple[DomainAnalysisSessionDiagnostic, ...] = ()
    publication_was_rejected = False
    if publication_payload is not None:
        try:
            publication, publication_diagnostics = _publication_from_payload(
                publication_payload,
                fallback_configurations=draft_configurations,
            )
        except (TypeError, ValueError) as exc:
            publication_was_rejected = True
            publication_diagnostics = (DomainAnalysisSessionDiagnostic(
                component="published_result",
                identifier="domain-analysis-publication",
                schema_version=str(_PUBLISHED_RESULT_SCHEMA_VERSION),
                reason=str(exc),
            ),)
    state = _workspace_state_from_payload(
        section,
        draft=draft,
        draft_configurations=draft_configurations,
        draft_physical_frame_ids=draft_physical_frame_ids,
        publication=publication,
        ignore_selected_component=publication_was_rejected,
    )
    opaque_components, opaque_diagnostics = opaque_components_from_payload(
        section,
        known_fields=_DOMAIN_ANALYSIS_KNOWN_FIELDS,
    )
    state = replace(
        state,
        opaque_components=opaque_components,
        diagnostics=(
            publication_diagnostics
            + cache_diagnostics
            + opaque_diagnostics
        ),
    )
    state = _restore_compatible_cache(
        state,
        m6_cache_records=m6_cache_records,
        classifier_cache_records=classifier_cache_records,
    )
    if (
        state.classifier_status != classifier_status
        and not publication_diagnostics
    ):
        raise ValueError(
            "domain_analysis.classifier_status does not match its published "
            "result."
        )
    return state


def _cache_from_payload(
    section: Mapping[str, Any],
) -> tuple[
    tuple[Any, ...],
    tuple[Any, ...],
    tuple[DomainAnalysisSessionDiagnostic, ...],
]:
    try:
        return domain_analysis_cache_from_payload(section.get("cache"))
    except (TypeError, ValueError) as exc:
        return (), (), (DomainAnalysisSessionDiagnostic(
            component="cache",
            identifier="domain-analysis-cache",
            schema_version="unknown",
            reason=str(exc),
        ),)


def _publication_to_payload(
    publication: DomainAnalysisPublication,
) -> dict[str, Any]:
    request = publication.request
    if request.backend_id is None:
        raise ValueError("Published Domain Analysis requires an explicit backend.")
    gate = publication.result.m6_gate
    if gate is None:
        raise ValueError("A published Domain Analysis result requires an M6 gate.")
    return {
        "schema_version": _PUBLISHED_RESULT_SCHEMA_VERSION,
        "request": {
            "frame_start": request.frame_range.start,
            "frame_stop": request.frame_range.stop,
            "backend_id": request.backend_id,
            "geometry_mode": request.geometry_mode,
            "classifier_ids": list(request.classifier_ids),
        },
        "request_fingerprint": publication.request_fingerprint,
        "run_status": publication.result.run_status,
        "classifier_status": publication.result.classifier_status,
        "m6_gate": _gate_to_payload(gate),
        "classifier_outcomes": classifier_outcomes_to_payload(
            publication.result.classifier_outcomes
        ),
    }


def _publication_from_payload(
    payload: Any,
    *,
    fallback_configurations: tuple[ClassifierConfiguration, ...],
) -> tuple[
    DomainAnalysisPublication,
    tuple[DomainAnalysisSessionDiagnostic, ...],
]:
    saved = _require_mapping(payload, "domain_analysis.published_result")
    _require_version(
        saved,
        _PUBLISHED_RESULT_SCHEMA_VERSION,
        "domain_analysis.published_result",
    )
    request = _publication_request_from_payload(saved)
    classifier_ids = request.classifier_ids
    gate = _gate_from_payload(
        _required(saved, "m6_gate", "domain_analysis.published_result")
    )
    outcomes, diagnostics = classifier_outcomes_from_payload(
        saved.get("classifier_outcomes"),
        path="domain_analysis.published_result.classifier_outcomes",
        requested_classifier_ids=classifier_ids,
        fallback_configurations=fallback_configurations,
        failure_frame_index=request.frame_range.start,
        validate_outcome=lambda outcome: (
            validate_classifier_outcome_for_gate(outcome, gate)
        ),
    )
    run_status = _require_text(
            saved,
            "run_status",
            "domain_analysis.published_result",
        )
    classifier_status = _require_text(
            saved,
            "classifier_status",
            "domain_analysis.published_result",
        )
    if diagnostics and classifier_ids:
        run_status = "completed_with_errors"
        classifier_status = "completed_with_errors"
    result = DomainAnalysisResult(
        run_status=cast(DomainAnalysisRunStatus, run_status),
        m6_gate=gate,
        classifier_status=cast(ClassifierStatus, classifier_status),
        classifier_outcomes=outcomes,
    )
    result = replace(result, molecule_diagnostic_funnels=(
        build_classic_molecule_diagnostic_funnels(result)
    ))
    publication = DomainAnalysisPublication(request=request, result=result)
    expected_fingerprint = _require_text(
        saved,
        "request_fingerprint",
        "domain_analysis.published_result",
    )
    if publication.request_fingerprint != expected_fingerprint:
        raise ValueError(
            "domain_analysis.published_result request_fingerprint does not "
            "match its request."
        )
    return publication, diagnostics


def _publication_request_from_payload(
    saved: Mapping[str, Any],
) -> DomainAnalysisRequest:
    path = "domain_analysis.published_result.request"
    payload = _require_mapping(
        _required(saved, "request", "domain_analysis.published_result"),
        path,
    )
    return DomainAnalysisRequest(
        frame_range=range(
            _require_integer(payload, "frame_start", path),
            _require_integer(payload, "frame_stop", path),
        ),
        backend_id=_require_text(payload, "backend_id", path),
        geometry_mode=cast(
            GeometryMode,
            _require_text(payload, "geometry_mode", path),
        ),
        classifier_ids=tuple(
            _require_text_list(payload, "classifier_ids", path)
        ),
    )


def _gate_to_payload(gate: M6Gate) -> dict[str, Any]:
    return {
        "schema_version": _M6_GATE_SCHEMA_VERSION,
        "frames": [_frame_to_payload(frame) for frame in gate.frames],
    }


def _gate_from_payload(payload: Any) -> M6Gate:
    saved = _require_mapping(payload, "domain_analysis.published_result.m6_gate")
    version = _require_integer(
        saved,
        "schema_version",
        "domain_analysis.published_result.m6_gate",
    )
    if version == 1:
        raise ValueError(
            "M6 gate schema_version 1 lacks atomic source-kind provenance; "
            "the published result was rejected instead of guessing it."
        )
    _require_version(
        saved,
        _M6_GATE_SCHEMA_VERSION,
        "domain_analysis.published_result.m6_gate",
    )
    frames = _require_list(
        saved,
        "frames",
        "domain_analysis.published_result.m6_gate",
    )
    return M6Gate(frames=tuple(
        _frame_from_payload(value, index=index)
        for index, value in enumerate(frames)
    ))


def _frame_to_payload(frame: M6FrameGate) -> dict[str, Any]:
    provenance = frame.presentation_provenance
    return {
        "frame_index": frame.frame_index,
        "physical_frame_id": frame.physical_frame_id,
        "coordinate_frame": frame.coordinate_frame,
        "coordinate_transform_fingerprint": (
            frame.coordinate_transform_fingerprint
        ),
        "presentation_provenance": {
            "raw_shape": list(provenance.raw_shape),
            "expanded_shape": list(provenance.expanded_shape),
            "source_view": provenance.source_view,
            "frame_origin_xy": list(provenance.frame_origin_xy),
            "canvas_offset_xy": list(provenance.canvas_offset_xy),
            "registration_fingerprint": provenance.registration_fingerprint,
        },
        "source_geometry_fingerprint": frame.source_geometry_fingerprint,
        "backend_identity": backend_identity_to_payload(frame.backend_identity),
        "native_evidence": backend_evidence_to_payload(frame.native_evidence),
        "pixel_area_nm2": frame.pixel_area_nm2,
        "full_domains": [
            _component_to_payload(value) for value in frame.full_domains
        ],
        "small_ordered_islands": [
            _component_to_payload(value)
            for value in frame.small_ordered_islands
        ],
        "outside_members": [
            published_molecule_to_payload(value)
            for value in frame.outside_members
        ],
        "outside_pixels_xy": _pairs_to_lists(frame.outside_pixels_xy),
        "outside_area_nm2": frame.outside_area_nm2,
        "analyzed_source_ids": list(frame.analyzed_source_ids),
        "analyzed_pixels_xy": _pairs_to_lists(frame.analyzed_pixels_xy),
        "analyzed_area_nm2": frame.analyzed_area_nm2,
        "m6_gate_fingerprint": frame.m6_gate_fingerprint,
    }


def _frame_from_payload(payload: Any, *, index: int) -> M6FrameGate:
    path = f"domain_analysis.published_result.m6_gate.frames[{index}]"
    saved = _require_mapping(payload, path)
    provenance_payload = _require_mapping(
        _required(saved, "presentation_provenance", path),
        f"{path}.presentation_provenance",
    )
    frame = M6FrameGate(
        frame_index=_require_integer(saved, "frame_index", path),
        physical_frame_id=_require_text(saved, "physical_frame_id", path),
        coordinate_frame=_require_text(saved, "coordinate_frame", path),
        coordinate_transform_fingerprint=_require_text(
            saved, "coordinate_transform_fingerprint", path
        ),
        presentation_provenance=_provenance_from_payload(
            provenance_payload,
            path=f"{path}.presentation_provenance",
        ),
        source_geometry_fingerprint=_require_text(
            saved, "source_geometry_fingerprint", path
        ),
        backend_identity=backend_identity_from_payload(
            _required(saved, "backend_identity", path),
            path=f"{path}.backend_identity",
        ),
        native_evidence=backend_evidence_from_payload(
            _required(saved, "native_evidence", path),
            path=f"{path}.native_evidence",
        ),
        pixel_area_nm2=_require_number(saved, "pixel_area_nm2", path),
        full_domains=_components_from_payload(saved, "full_domains", path),
        small_ordered_islands=_components_from_payload(
            saved, "small_ordered_islands", path
        ),
        outside_members=tuple(
            published_molecule_from_payload(
                value,
                path=f"{path}.outside_members[{member_index}]",
            )
            for member_index, value in enumerate(
                _require_list(saved, "outside_members", path)
            )
        ),
        outside_pixels_xy=_integer_pairs(saved, "outside_pixels_xy", path),
        outside_area_nm2=_require_number(saved, "outside_area_nm2", path),
        analyzed_source_ids=tuple(_require_text_list(
            saved, "analyzed_source_ids", path
        )),
        analyzed_pixels_xy=_integer_pairs(saved, "analyzed_pixels_xy", path),
        analyzed_area_nm2=_require_number(saved, "analyzed_area_nm2", path),
    )
    expected_fingerprint = _require_text(
        saved, "m6_gate_fingerprint", path
    )
    if frame.m6_gate_fingerprint != expected_fingerprint:
        raise ValueError(f"{path}.m6_gate_fingerprint does not match its frame.")
    return frame


def _provenance_from_payload(
    saved: Mapping[str, Any],
    *,
    path: str,
) -> M6PresentationProvenance:
    return M6PresentationProvenance(
        raw_shape=_integer_pair(saved, "raw_shape", path),
        expanded_shape=_integer_pair(saved, "expanded_shape", path),
        source_view=cast(
            CoordinateView,
            _require_text(saved, "source_view", path),
        ),
        frame_origin_xy=_float_pair(saved, "frame_origin_xy", path),
        canvas_offset_xy=_float_pair(saved, "canvas_offset_xy", path),
        registration_fingerprint=_require_text(
            saved, "registration_fingerprint", path
        ),
    )


def _component_to_payload(component: M6PublishedComponent) -> dict[str, Any]:
    return {
        "lattice_domain_id": component.lattice_domain_id,
        "component_type": component.component_type,
        "members": [
            published_molecule_to_payload(value)
            for value in component.members
        ],
        "core_source_ids": list(component.core_source_ids),
        "halo_source_ids": list(component.halo_source_ids),
        "footprint_pixels_xy": _pairs_to_lists(
            component.footprint_pixels_xy
        ),
        "footprint_area_nm2": component.footprint_area_nm2,
        "centroid_xy_nm": list(component.centroid_xy_nm),
        "bounds_xyxy_nm": list(component.bounds_xyxy_nm),
        "qc_flags": list(component.qc_flags),
    }


def _components_from_payload(
    saved: Mapping[str, Any],
    field_name: str,
    path: str,
) -> tuple[M6PublishedComponent, ...]:
    values = _require_list(saved, field_name, path)
    return tuple(
        _component_from_payload(
            value,
            path=f"{path}.{field_name}[{index}]",
        )
        for index, value in enumerate(values)
    )


def _component_from_payload(
    payload: Any,
    *,
    path: str,
) -> M6PublishedComponent:
    saved = _require_mapping(payload, path)
    return M6PublishedComponent(
        lattice_domain_id=_require_text(saved, "lattice_domain_id", path),
        component_type=cast(
            M6ComponentType,
            _require_text(saved, "component_type", path),
        ),
        members=tuple(
            published_molecule_from_payload(
                value,
                path=f"{path}.members[{member_index}]",
            )
            for member_index, value in enumerate(
                _require_list(saved, "members", path)
            )
        ),
        core_source_ids=tuple(_require_text_list(
            saved, "core_source_ids", path
        )),
        halo_source_ids=tuple(_require_text_list(
            saved, "halo_source_ids", path
        )),
        footprint_pixels_xy=_integer_pairs(
            saved, "footprint_pixels_xy", path
        ),
        footprint_area_nm2=_require_number(
            saved, "footprint_area_nm2", path
        ),
        centroid_xy_nm=_float_pair(saved, "centroid_xy_nm", path),
        bounds_xyxy_nm=_float_quad(saved, "bounds_xyxy_nm", path),
        qc_flags=tuple(_require_text_list(saved, "qc_flags", path)),
    )


def _workspace_state_from_payload(
    section: Mapping[str, Any],
    *,
    draft: DomainAnalysisRequest | None,
    draft_configurations: tuple[ClassifierConfiguration, ...],
    draft_physical_frame_ids: tuple[str, ...],
    publication: DomainAnalysisPublication | None,
    ignore_selected_component: bool,
) -> DomainAnalysisSessionState:
    path = "domain_analysis"
    view_payload = section.get("view_settings")
    view_settings = DomainAnalysisViewSettings()
    if view_payload is not None:
        saved_view = _require_mapping(view_payload, f"{path}.view_settings")
        visible = _required(
            saved_view, "overlay_visible", f"{path}.view_settings"
        )
        if not isinstance(visible, bool):
            raise ValueError(
                "domain_analysis.view_settings.overlay_visible must be a bool."
            )
        view_settings = DomainAnalysisViewSettings(
            overlay_visible=visible,
            overlay_opacity_percent=_require_integer(
                saved_view,
                "overlay_opacity_percent",
                f"{path}.view_settings",
            ),
        )
    selected_payload = section.get("selected_component")
    selected = None
    if selected_payload is not None and not ignore_selected_component:
        saved_selected = _require_mapping(
            selected_payload,
            f"{path}.selected_component",
        )
        selected = DomainComponentKey(
            physical_frame_id=_require_text(
                saved_selected, "physical_frame_id", f"{path}.selected_component"
            ),
            lattice_domain_id=_require_text(
                saved_selected, "lattice_domain_id", f"{path}.selected_component"
            ),
        )
    run_payload = section.get("run")
    run_status = "idle"
    run_diagnosis = None
    if run_payload is not None:
        saved_run = _require_mapping(run_payload, f"{path}.run")
        run_status = _require_text(saved_run, "status", f"{path}.run")
        run_diagnosis = _required(saved_run, "diagnosis", f"{path}.run")
        if run_diagnosis is not None and not isinstance(run_diagnosis, str):
            raise ValueError("domain_analysis.run.diagnosis must be text or null.")
    if run_status == "running":
        run_status = "retry_required"
        run_diagnosis = DOMAIN_ANALYSIS_RETRY_REQUIRED_DIAGNOSIS
    return DomainAnalysisSessionState(
        draft=draft,
        draft_classifier_configurations=draft_configurations,
        draft_physical_frame_ids=draft_physical_frame_ids,
        published_result=publication,
        view_settings=view_settings,
        selected_component=selected,
        run_status=cast(Any, run_status),
        run_diagnosis=run_diagnosis,
    )


def _draft_from_payload(
    section: Mapping[str, Any],
) -> tuple[
    DomainAnalysisRequest | None,
    tuple[ClassifierConfiguration, ...],
    tuple[str, ...],
]:
    payload = section.get("draft")
    if payload is None:
        return None, (), ()
    path = "domain_analysis.draft"
    saved = _require_mapping(payload, path)
    classifier_ids = tuple(_require_text_list(saved, "classifier_ids", path))
    request = DomainAnalysisRequest(
        frame_range=range(
            _require_integer(saved, "frame_start", path),
            _require_integer(saved, "frame_stop", path),
        ),
        backend_id=_require_text(saved, "backend_id", path),
        geometry_mode=cast(
            GeometryMode,
            _require_text(saved, "geometry_mode", path),
        ),
        classifier_ids=classifier_ids,
    )
    configuration_payloads = saved.get("classifier_configurations")
    if configuration_payloads is None:
        if classifier_ids:
            raise ValueError(
                "domain_analysis.draft.classifier_configurations are required "
                "for active classifiers."
            )
        return request, (), tuple(
            _require_text_list(saved, "physical_frame_ids", path)
            if "physical_frame_ids" in saved
            else ()
        )
    configurations = tuple(
        classifier_configuration_from_payload(
            value,
            path=f"{path}.classifier_configurations[{index}]",
        )
        for index, value in enumerate(
            _require_list(saved, "classifier_configurations", path)
        )
    )
    return request, configurations, tuple(
        _require_text_list(saved, "physical_frame_ids", path)
        if "physical_frame_ids" in saved
        else ()
    )


def _restore_compatible_cache(
    state: DomainAnalysisSessionState,
    *,
    m6_cache_records: tuple[Any, ...],
    classifier_cache_records: tuple[Any, ...],
) -> DomainAnalysisSessionState:
    restored = state
    for index, record in enumerate(m6_cache_records):
        try:
            restored = replace(
                restored,
                m6_cache_records=restored.m6_cache_records + (record,),
            )
        except (TypeError, ValueError) as exc:
            restored = _with_diagnostic(
                restored,
                component="m6_cache",
                identifier=f"domain_analysis.cache.m6_frames[{index}]",
                reason=str(exc),
            )
    for index, record in enumerate(classifier_cache_records):
        try:
            restored = replace(
                restored,
                classifier_cache_records=(
                    restored.classifier_cache_records + (record,)
                ),
            )
        except (TypeError, ValueError) as exc:
            restored = _with_diagnostic(
                restored,
                component="classifier_cache",
                identifier=(
                    f"domain_analysis.cache.classifier_frames[{index}]"
                ),
                reason=str(exc),
            )
    return restored


def _with_diagnostic(
    state: DomainAnalysisSessionState,
    *,
    component: str,
    identifier: str,
    reason: str,
) -> DomainAnalysisSessionState:
    return replace(
        state,
        diagnostics=state.diagnostics + (DomainAnalysisSessionDiagnostic(
            component=component,
            identifier=identifier,
            schema_version="1",
            reason=reason,
        ),),
    )


def _require_version(
    payload: Mapping[str, Any],
    expected: int,
    path: str,
) -> None:
    version = _require_integer(payload, "schema_version", path)
    if version != expected:
        raise ValueError(f"Unsupported {path} schema_version: {version}.")
