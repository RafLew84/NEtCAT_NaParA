from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from string import hexdigits
from typing import Literal

from .cache import (
    ClassifierFrameCacheKey,
    ClassifierFrameCacheRecord,
    M6FrameCacheKey,
)
from .classifier_contract import ClassifierConfiguration
from .classifier_models import (
    ClassifierOutcome,
    MoleculeClassification,
    classifier_frame_result_fingerprint,
)
from .correction_workspace_quarantine import CorrectionWorkspaceQuarantine
from .geometry import GeometryMode
from .models import (
    DomainAnalysisRequest,
    M6FrameComputation,
    M6FrameGate,
    M6Gate,
)
from .orientation_class_catalog import OrientationClassCatalog
from .reference_review import ReferenceReviewPolicy, ReferenceReviewWorkspace
from .domain_correction import DomainCorrectionModule
from .workspace_correction import (
    DomainCorrectionWorkspaceState,
    initialize_domain_corrections,
)
from .workspace_controller import (
    DomainAnalysisPublication,
    DomainComponentKey,
)


DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION = 2
DOMAIN_ANALYSIS_RETRY_REQUIRED_DIAGNOSIS = (
    "Saved while Domain Analysis was running; retry must be started explicitly."
)
DomainAnalysisSessionRunStatus = Literal[
    "idle",
    "running",
    "completed",
    "completed_with_errors",
    "canceled",
    "failed",
    "retry_required",
]
_RESERVED_OPAQUE_COMPONENT_NAMES = frozenset({
    "schema_version",
    "classifier_status",
    "draft",
    "view_settings",
    "selected_component",
    "run",
    "published_result",
    "correction_workspace",
    "cache",
})


@dataclass(frozen=True)
class DomainAnalysisViewSettings:
    """Persistent Domain Analysis overlay settings."""

    overlay_visible: bool = True
    overlay_opacity_percent: int = 100

    def __post_init__(self) -> None:
        if not isinstance(self.overlay_visible, bool):
            raise TypeError("overlay_visible must be a bool.")
        opacity = self.overlay_opacity_percent
        if (
            isinstance(opacity, bool)
            or not isinstance(opacity, int)
            or not 0 <= opacity <= 100
        ):
            raise ValueError("overlay_opacity_percent must be between 0 and 100.")


@dataclass(frozen=True)
class DomainAnalysisSessionDiagnostic:
    """A persisted component that Open could not safely activate."""

    component: str
    identifier: str
    schema_version: str
    reason: str

    def __post_init__(self) -> None:
        for field_name in (
            "component",
            "identifier",
            "schema_version",
            "reason",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be non-empty text.")
            object.__setattr__(self, field_name, value.strip())


@dataclass(frozen=True)
class DomainAnalysisM6CacheRecord:
    """One complete M6 cache key/value pair safe for session persistence."""

    key: M6FrameCacheKey
    computation: M6FrameComputation

    def __post_init__(self) -> None:
        if not isinstance(self.key, M6FrameCacheKey):
            raise TypeError("key must be an M6FrameCacheKey.")
        if not isinstance(self.computation, M6FrameComputation):
            raise TypeError("computation must be an M6FrameComputation.")
        if self.key.geometry_mode not in {
            "segmentation_preferred",
            "bbox_centers",
        }:
            raise ValueError(
                f"Unsupported M6 cache geometry_mode: {self.key.geometry_mode!r}."
            )
        if any(
            not isinstance(value, str) or not value.strip()
            for value in (
                self.key.physical_frame_id,
                self.key.coordinate_transform_fingerprint,
                self.key.m6_settings_fingerprint,
                self.key.m6_algorithm_version,
            )
        ) or (
            self.key.configuration_fingerprint is not None
            and (
                not isinstance(self.key.configuration_fingerprint, str)
                or not self.key.configuration_fingerprint.strip()
            )
        ):
            raise ValueError("M6 cache key fields must be non-empty strings.")
        if (
            self.key.coordinate_transform_fingerprint
            != self.computation.coordinate_transform_fingerprint
            or self.key.backend_identity
            != self.computation.backend_identity
        ):
            raise ValueError("M6 cache key does not match its computation.")


@dataclass(frozen=True)
class DomainAnalysisClassifierCacheRecord:
    """One complete classifier cache key/value pair without raw pixels."""

    key: ClassifierFrameCacheKey
    record: ClassifierFrameCacheRecord

    def __post_init__(self) -> None:
        if not isinstance(self.key, ClassifierFrameCacheKey):
            raise TypeError("key must be a ClassifierFrameCacheKey.")
        if not isinstance(self.record, ClassifierFrameCacheRecord):
            raise TypeError("record must be a ClassifierFrameCacheRecord.")
        expected = classifier_frame_result_fingerprint(
            self.record.classifications
        )
        if self.record.result_fingerprint != expected:
            raise ValueError("Classifier cache result fingerprint is invalid.")
        if any(
            value.identity != self.key.configuration.identity
            or value.physical_frame_id != self.key.physical_frame_id
            or value.m6_gate_fingerprint != self.key.m6_gate_fingerprint
            for value in self.record.classifications
        ):
            raise ValueError("Classifier cache key does not match its results.")
        raw_fingerprint = self.key.raw_frame_fingerprint
        if raw_fingerprint is not None and (
            len(raw_fingerprint) != 64
            or any(character not in hexdigits for character in raw_fingerprint)
        ):
            raise ValueError("raw_frame_fingerprint must be a SHA-256 hex digest.")


@dataclass(frozen=True)
class DomainAnalysisSessionState:
    """Authoritative schema-v2 Domain Analysis workspace snapshot."""

    draft: DomainAnalysisRequest | None = None
    draft_classifier_configurations: tuple[
        ClassifierConfiguration, ...
    ] = ()
    draft_physical_frame_ids: tuple[str, ...] = ()
    published_result: DomainAnalysisPublication | None = None
    correction_workspace_quarantine: CorrectionWorkspaceQuarantine | None = None
    orientation_class_catalog: OrientationClassCatalog = field(
        default_factory=OrientationClassCatalog
    )
    domain_corrections: DomainCorrectionWorkspaceState = field(
        default_factory=DomainCorrectionWorkspaceState
    )
    reference_reviews: ReferenceReviewWorkspace = field(
        default_factory=ReferenceReviewWorkspace
    )
    view_settings: DomainAnalysisViewSettings = field(
        default_factory=DomainAnalysisViewSettings
    )
    selected_component: DomainComponentKey | None = None
    run_status: DomainAnalysisSessionRunStatus = "idle"
    run_diagnosis: str | None = None
    m6_cache_records: tuple[DomainAnalysisM6CacheRecord, ...] = ()
    classifier_cache_records: tuple[
        DomainAnalysisClassifierCacheRecord, ...
    ] = ()
    opaque_components: tuple[tuple[str, object], ...] = ()
    diagnostics: tuple[DomainAnalysisSessionDiagnostic, ...] = ()
    schema_version: int = DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported Domain Analysis session schema_version: "
                f"{self.schema_version}."
            )
        _normalize_session_collections(self)
        _validate_workspace_values(self)
        _normalize_opaque_components(self)
        if not isinstance(self.orientation_class_catalog, OrientationClassCatalog):
            raise TypeError(
                "orientation_class_catalog must be an OrientationClassCatalog."
            )
        if not isinstance(self.domain_corrections, DomainCorrectionWorkspaceState):
            raise TypeError(
                "domain_corrections must be a DomainCorrectionWorkspaceState."
            )
        if not isinstance(self.reference_reviews, ReferenceReviewWorkspace):
            raise TypeError("reference_reviews must be a ReferenceReviewWorkspace.")
        _normalize_correction_workspace(self)

    @property
    def classifier_status(self) -> str:
        publication = self.published_result
        if publication is None and self.correction_workspace_quarantine is not None:
            publication = self.correction_workspace_quarantine.automatic_snapshot
        if publication is None:
            return "not_run"
        return publication.result.classifier_status


def _normalize_correction_workspace(state: DomainAnalysisSessionState) -> None:
    publication = state.published_result
    corrections = state.domain_corrections
    reviews = state.reference_reviews
    if publication is None:
        if corrections.correction_set is not None or reviews.frames:
            raise ValueError(
                "Correction workspace data requires a published automatic result."
            )
        return
    module = DomainCorrectionModule()
    if corrections.correction_set is None:
        corrections = initialize_domain_corrections(module, publication.result)
        object.__setattr__(state, "domain_corrections", corrections)
    else:
        expected = module.project(publication.result, corrections.correction_set)
        if expected != corrections.effective_projection:
            raise ValueError(
                "Effective projection must be derived from the published result "
                "and active correction set."
            )
    policy = ReferenceReviewPolicy()
    if not reviews.frames:
        reviews = policy.initialize(publication.result, corrections)
        object.__setattr__(state, "reference_reviews", reviews)
    elif policy.synchronize(reviews, publication.result, corrections) != reviews:
        raise ValueError("Reference Review scopes do not match corrections.")
    correction_set = corrections.correction_set
    assert correction_set is not None
    state.orientation_class_catalog.validate_assignments(
        value.orientation_label for value in correction_set.orientation_decisions
    )


def _normalize_session_collections(state: DomainAnalysisSessionState) -> None:
    draft_configurations = tuple(state.draft_classifier_configurations)
    draft_physical_frame_ids = tuple(state.draft_physical_frame_ids)
    m6_records = tuple(state.m6_cache_records)
    classifier_records = tuple(state.classifier_cache_records)
    diagnostics = tuple(state.diagnostics)
    if any(
        not isinstance(value, ClassifierConfiguration)
        for value in draft_configurations
    ):
        raise TypeError(
            "draft_classifier_configurations contain an invalid value."
        )
    if any(
        not isinstance(value, DomainAnalysisM6CacheRecord)
        for value in m6_records
    ):
        raise TypeError("m6_cache_records contain an invalid value.")
    if any(
        not isinstance(value, DomainAnalysisClassifierCacheRecord)
        for value in classifier_records
    ):
        raise TypeError("classifier_cache_records contain an invalid value.")
    if any(
        not isinstance(value, DomainAnalysisSessionDiagnostic)
        for value in diagnostics
    ):
        raise TypeError("diagnostics contain an invalid value.")
    object.__setattr__(
        state,
        "draft_classifier_configurations",
        draft_configurations,
    )
    object.__setattr__(
        state,
        "draft_physical_frame_ids",
        draft_physical_frame_ids,
    )
    object.__setattr__(state, "m6_cache_records", m6_records)
    object.__setattr__(
        state,
        "classifier_cache_records",
        classifier_records,
    )
    object.__setattr__(state, "diagnostics", diagnostics)
    if len({value.key for value in m6_records}) != len(m6_records):
        raise ValueError("M6 session cache keys must be unique.")
    if len({value.key for value in classifier_records}) != len(
        classifier_records
    ):
        raise ValueError("Classifier session cache keys must be unique.")


def _normalize_opaque_components(state: DomainAnalysisSessionState) -> None:
    opaque_components = tuple(state.opaque_components)
    if any(
        not isinstance(item, tuple)
        or len(item) != 2
        or not isinstance(item[0], str)
        or not item[0].strip()
        or not _is_json_value(item[1])
        for item in opaque_components
    ):
        raise ValueError(
            "opaque_components must contain named JSON-compatible payloads."
        )
    if len({key for key, _ in opaque_components}) != len(opaque_components):
        raise ValueError("opaque component names must be unique.")
    if any(
        key in _RESERVED_OPAQUE_COMPONENT_NAMES
        for key, _ in opaque_components
    ):
        raise ValueError("opaque component names cannot replace known fields.")
    if any(_contains_raw_pixels(value) for _, value in opaque_components):
        raise ValueError("opaque component contains raw pixels.")
    object.__setattr__(state, "opaque_components", opaque_components)


def _validate_workspace_values(state: DomainAnalysisSessionState) -> None:
    if state.draft is not None and not isinstance(
        state.draft,
        DomainAnalysisRequest,
    ):
        raise TypeError("draft must be a DomainAnalysisRequest.")
    _validate_draft_configurations(state)
    publication = state.published_result
    if publication is not None and not isinstance(
        publication,
        DomainAnalysisPublication,
    ):
        raise TypeError("published_result must be a DomainAnalysisPublication.")
    quarantine = state.correction_workspace_quarantine
    if quarantine is not None and not isinstance(
        quarantine,
        CorrectionWorkspaceQuarantine,
    ):
        raise TypeError(
            "correction_workspace_quarantine must be a "
            "CorrectionWorkspaceQuarantine."
        )
    if quarantine is not None and publication is not None:
        raise ValueError(
            "A quarantined automatic snapshot cannot also be active."
        )
    if not isinstance(state.view_settings, DomainAnalysisViewSettings):
        raise TypeError("view_settings must be DomainAnalysisViewSettings.")
    if state.selected_component is not None:
        _validate_selected_component(state.selected_component, publication)
    _validate_publication_classifiers(publication)
    _validate_cache_scope(state)
    if state.run_status not in {
        "idle", "running", "completed", "completed_with_errors",
        "canceled", "failed", "retry_required",
    }:
        raise ValueError(f"Unsupported session run_status: {state.run_status!r}.")
    diagnosis = state.run_diagnosis
    if diagnosis is not None and (
        not isinstance(diagnosis, str) or not diagnosis.strip()
    ):
        raise ValueError("run_diagnosis must be a non-empty string.")
    if state.run_status == "retry_required" and diagnosis is None:
        raise ValueError("retry_required must explain that an explicit retry is needed.")
    object.__setattr__(
        state,
        "run_diagnosis",
        None if diagnosis is None else diagnosis.strip(),
    )


def _validate_draft_configurations(state: DomainAnalysisSessionState) -> None:
    configurations = state.draft_classifier_configurations
    if state.draft is None:
        if configurations or state.draft_physical_frame_ids:
            raise ValueError(
                "Draft configurations and frame IDs require a draft request."
            )
        return
    classifier_ids = tuple(
        value.identity.classifier_id for value in configurations
    )
    if classifier_ids != state.draft.classifier_ids:
        raise ValueError(
            "Draft classifier configurations must match the active classifier IDs."
        )
    physical_frame_ids = state.draft_physical_frame_ids
    if physical_frame_ids and (
        len(physical_frame_ids) != len(state.draft.frame_indices)
        or any(
            not isinstance(value, str) or not value.strip()
            for value in physical_frame_ids
        )
        or len(set(physical_frame_ids)) != len(physical_frame_ids)
    ):
        raise ValueError(
            "Draft physical frame IDs must align with the active frame range."
        )


def _validate_publication_classifiers(
    publication: DomainAnalysisPublication | None,
) -> None:
    if publication is None:
        return
    requested = publication.request.classifier_ids
    outcomes = publication.result.classifier_outcomes
    if requested:
        if outcomes is None or tuple(
            outcome.classifier_id for outcome in outcomes
        ) != requested:
            raise ValueError(
                "Published classifier outcomes must match the frozen request."
            )
    elif outcomes is not None:
        raise ValueError("M6-only publication cannot contain classifier outcomes.")
    _validate_classifier_gate_references(publication)


def _validate_classifier_gate_references(
    publication: DomainAnalysisPublication,
) -> None:
    gate = publication.result.m6_gate
    outcomes = publication.result.classifier_outcomes or ()
    if gate is None:
        return
    for outcome in outcomes:
        validate_classifier_outcome_for_gate(outcome, gate)


def validate_classifier_outcome_for_gate(
    outcome: ClassifierOutcome,
    gate: M6Gate,
) -> None:
    """Reject an outcome unless its atomic payload covers the entire M6 gate."""

    if outcome.status != "completed":
        return
    frames = {
        (frame.frame_index, frame.physical_frame_id): frame
        for frame in gate.frames
    }
    provenance_keys = {
        (value.frame_index, value.physical_frame_id)
        for value in outcome.frame_result_provenance
    }
    if provenance_keys != set(frames):
        raise ValueError(
            "Classifier outcome does not cover the complete published M6 gate."
        )
    expected_classifications = {
        (frame.frame_index, frame.physical_frame_id, source_id)
        for frame in gate.frames
        for source_id in frame.analyzed_source_ids
    }
    actual_classifications = {
        (value.frame_index, value.physical_frame_id, value.source_id)
        for value in outcome.molecule_classifications
    }
    if actual_classifications != expected_classifications:
        raise ValueError(
            "Classifier outcome does not cover the complete published M6 gate."
        )
    expected_summaries = {
        (frame.frame_index, frame.physical_frame_id, domain.lattice_domain_id)
        for frame in gate.frames
        for domain in frame.full_domains
    }
    actual_summaries = {
        (value.frame_index, value.physical_frame_id, value.lattice_domain_id)
        for value in outcome.domain_summaries
    }
    if actual_summaries != expected_summaries:
        raise ValueError(
            "Classifier outcome does not cover the complete published M6 gate."
        )
    for provenance in outcome.frame_result_provenance:
        if (provenance.frame_index, provenance.physical_frame_id) not in frames:
            raise ValueError(
                "Classifier provenance does not match the published M6 gate."
            )
    for value in outcome.molecule_classifications:
        frame = frames.get((value.frame_index, value.physical_frame_id))
        if (
            frame is None
            or value.m6_gate_fingerprint != frame.m6_gate_fingerprint
            or not _published_partition_contains(frame, value)
        ):
            raise ValueError(
                "Classifier result does not match the published M6 gate."
            )
    for summary in outcome.domain_summaries:
        frame = frames.get((summary.frame_index, summary.physical_frame_id))
        if (
            frame is None
            or summary.m6_gate_fingerprint != frame.m6_gate_fingerprint
            or not any(
                domain.lattice_domain_id == summary.lattice_domain_id
                for domain in frame.full_domains
            )
        ):
            raise ValueError(
                "Classifier summary does not match the published M6 gate."
            )


def _validate_cache_scope(state: DomainAnalysisSessionState) -> None:
    requests = tuple(
        value
        for value in (
            state.draft,
            None if state.published_result is None else state.published_result.request,
        )
        if value is not None
    )
    allowed_indices = {
        index for request in requests for index in request.frame_indices
    }
    allowed_geometry_modes = {
        request.geometry_mode for request in requests
    }
    publication = state.published_result
    published_frames = () if publication is None else (
        publication.result.m6_gate.frames
        if publication.result.m6_gate is not None
        else ()
    )
    draft_frame_ids: dict[int, str] = {}
    if state.draft is not None and state.draft_physical_frame_ids:
        draft_frame_ids = dict(zip(
            state.draft.frame_indices,
            state.draft_physical_frame_ids,
            strict=True,
        ))
    _validate_m6_cache_scope(
        state,
        allowed_indices=allowed_indices,
        allowed_geometry_modes=allowed_geometry_modes,
        published_frames=published_frames,
        draft_frame_ids=draft_frame_ids,
    )
    _validate_classifier_cache_scope(
        state,
        allowed_indices=allowed_indices,
        published_frames=published_frames,
    )


def _validate_m6_cache_scope(
    state: DomainAnalysisSessionState,
    *,
    allowed_indices: set[int],
    allowed_geometry_modes: set[GeometryMode],
    published_frames: tuple[M6FrameGate, ...],
    draft_frame_ids: dict[int, str],
) -> None:
    publication = state.published_result
    for record in state.m6_cache_records:
        if (
            record.computation.frame_index not in allowed_indices
            or record.key.geometry_mode not in allowed_geometry_modes
        ):
            raise ValueError("M6 cache record is outside the active workspace.")
        matches_publication = any(
            record.key.physical_frame_id == frame.physical_frame_id
            and record.key.coordinate_transform_fingerprint
            == frame.coordinate_transform_fingerprint
            and record.key.backend_identity == frame.backend_identity
            for frame in published_frames
            if frame.frame_index == record.computation.frame_index
            and publication is not None
            and publication.request.geometry_mode == record.key.geometry_mode
            and (
                publication.request.m6_configuration is None
                or record.key.configuration_fingerprint
                == publication.request.m6_configuration.configuration_fingerprint
            )
        )
        matches_draft = (
            state.draft is not None
            and (
                state.draft.backend_id is None
                or state.draft.backend_id == record.key.backend_identity.backend_id
            )
            and state.draft.geometry_mode == record.key.geometry_mode
            and (
                state.draft.m6_configuration is None
                or record.key.configuration_fingerprint
                == state.draft.m6_configuration.configuration_fingerprint
            )
            and draft_frame_ids.get(record.computation.frame_index)
            == record.key.physical_frame_id
        )
        if not (matches_publication or matches_draft):
            raise ValueError("M6 cache record is outside the active workspace.")


def _validate_classifier_cache_scope(
    state: DomainAnalysisSessionState,
    *,
    allowed_indices: set[int],
    published_frames: tuple[M6FrameGate, ...],
) -> None:
    publication = state.published_result
    active_configurations = set(state.draft_classifier_configurations)
    if publication is not None:
        active_configurations.update(
            value.configuration
            for value in publication.result.classifier_outcomes or ()
        )
    published_gate_keys = {
        (frame.physical_frame_id, frame.m6_gate_fingerprint)
        for frame in published_frames
    }
    cached_physical_ids = {
        value.key.physical_frame_id for value in state.m6_cache_records
    }
    for classifier_record in state.classifier_cache_records:
        if classifier_record.key.configuration not in active_configurations:
            raise ValueError(
                "Classifier cache record does not use an active classifier "
                "configuration."
            )
        if not (
            (
                classifier_record.key.physical_frame_id,
                classifier_record.key.m6_gate_fingerprint,
            ) in published_gate_keys
            or classifier_record.key.physical_frame_id in cached_physical_ids
        ):
            raise ValueError(
                "Classifier cache record is outside the active workspace."
            )
        if any(
            value.frame_index not in allowed_indices
            for value in classifier_record.record.classifications
        ):
            raise ValueError(
                "Classifier cache record is outside the active workspace."
            )


def _published_partition_contains(
    frame: M6FrameGate,
    value: MoleculeClassification,
) -> bool:
    partition = value.m6_partition
    source_id = value.source_id
    lattice_domain_id = value.lattice_domain_id
    if partition == "outside":
        return source_id in frame.outside_source_ids
    components = (
        frame.full_domains
        if partition == "full_domain"
        else frame.small_ordered_islands
    )
    return any(
        component.lattice_domain_id == lattice_domain_id
        and source_id in component.source_ids
        for component in components
    )


def _validate_selected_component(
    selected: DomainComponentKey,
    publication: DomainAnalysisPublication | None,
) -> None:
    if not isinstance(selected, DomainComponentKey):
        raise TypeError("selected_component must be a DomainComponentKey.")
    gate = None if publication is None else publication.result.m6_gate
    if gate is None or not any(
        frame.physical_frame_id == selected.physical_frame_id
        and any(
            component.lattice_domain_id == selected.lattice_domain_id
            for component in frame.full_domains
            + frame.small_ordered_islands
        )
        for frame in gate.frames
    ):
        raise ValueError("selected_component is absent from the published result.")


def _is_json_value(value: object) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return isfinite(value)
    if isinstance(value, list):
        return all(_is_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _is_json_value(item)
            for key, item in value.items()
        )
    return False


def _contains_raw_pixels(value: object) -> bool:
    if isinstance(value, list):
        return any(_contains_raw_pixels(item) for item in value)
    if isinstance(value, dict):
        return any(
            key in {"raw_frame", "raw_image", "raw_pixels"}
            or _contains_raw_pixels(item)
            for key, item in value.items()
        )
    return False
