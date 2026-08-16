from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from .correction_rebase_models import (
    ApplyPreparedCorrectionRebase,
    CorrectionRebaseIssue,
    CorrectionRebaseIssueKind,
    CorrectionRebasePromotion,
    CorrectionRebaseRecord,
    CorrectionRebaseResolution,
    PendingAutomaticCandidate,
    PrepareCorrectionRebase,
    PreparedCorrectionRebase,
    automatic_candidate_fingerprint,
)
from .detection_identity import CorrectionSourceMapping, DetectionIdentity
from .domain_correction_models import (
    DomainCorrectionReviewTarget,
    DomainCorrectionWorkspace,
    ManualOrientationDecision,
)
from .fingerprints import canonical_sha256
from .manual_domain_models import ManualDomainRecord
from .manual_domain_projection import source_footprints_for_frame
from .models import (
    DomainAnalysisRequest,
    DomainAnalysisResult,
    M6FrameGate,
    M6PublishedMolecule,
)


class CorrectionRebasePolicy:
    """Compare and atomically transfer portable decisions to one new anchor."""

    def __init__(
        self,
        *,
        record_id_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._record_id_factory = record_id_factory or (lambda: str(uuid4()))
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def pending_candidate(
        self,
        active_request: DomainAnalysisRequest,
        active_result: DomainAnalysisResult,
        candidate_request: DomainAnalysisRequest,
        candidate_result: DomainAnalysisResult,
    ) -> PendingAutomaticCandidate | None:
        active_fingerprint = automatic_candidate_fingerprint(
            active_request,
            active_result,
        )
        candidate_fingerprint = automatic_candidate_fingerprint(
            candidate_request,
            candidate_result,
        )
        if candidate_fingerprint == active_fingerprint:
            return None
        return PendingAutomaticCandidate(
            candidate_request,
            candidate_result,
            candidate_fingerprint,
        )

    def prepare(
        self,
        active_request: DomainAnalysisRequest,
        active_result: DomainAnalysisResult,
        correction_set: DomainCorrectionWorkspace,
        candidate: PendingAutomaticCandidate,
        resolutions: tuple[CorrectionRebaseResolution, ...] = (),
    ) -> PreparedCorrectionRebase:
        active_fingerprint = automatic_candidate_fingerprint(
            active_request,
            active_result,
        )
        if correction_set.automatic_fingerprint != correction_anchor_fingerprint(
            active_result
        ):
            raise ValueError("Active correction revision has a stale automatic anchor.")
        source_keys = _corrected_source_keys(correction_set)
        active_sources = _source_fingerprints(active_result)
        candidate_sources = _source_fingerprints(candidate.result)
        active_footprints = _source_footprints(active_result)
        candidate_footprints = _source_footprints(candidate.result)
        portable = tuple(
            key
            for key in source_keys
            if key in candidate_sources
            and active_sources.get(key) is not None
            and active_sources[key] == candidate_sources[key]
        )
        issues = tuple(
            _issue_for(
                key,
                candidate_sources,
                active_footprints,
                candidate_footprints,
                tuple(
                    value
                    for value in active_footprints
                    if value not in candidate_sources
                ),
            )
            for key in source_keys
            if key not in portable
        )
        resolution_by_id = {value.issue_id: value for value in resolutions}
        unknown = tuple(sorted(set(resolution_by_id).difference(
            value.issue_id for value in issues
        )))
        if unknown:
            raise ValueError(f"Rebase resolutions reference unknown issues: {unknown!r}.")
        mapping = [
            CorrectionSourceMapping(
                source_identity=identity,
                target_source_ids=(identity.source_id,),
            )
            for identity in portable
        ]
        blocking: list[str] = []
        for issue in issues:
            resolution = resolution_by_id.get(issue.issue_id)
            if resolution is None:
                continue
            targets = _resolved_targets(issue, resolution, candidate_sources)
            mapping.append(CorrectionSourceMapping(
                source_identity=DetectionIdentity(
                    physical_frame_id=issue.physical_frame_id,
                    source_id=issue.source_id,
                ),
                target_source_ids=targets,
            ))
        blocking.extend(_mapping_conflicts(correction_set, tuple(mapping)))
        return PreparedCorrectionRebase(
            expected_correction_revision=correction_set.revision,
            active_automatic_fingerprint=active_fingerprint,
            candidate_automatic_fingerprint=candidate.automatic_fingerprint,
            portable_source_keys=portable,
            issues=issues,
            resolutions=resolutions,
            source_mapping=tuple(mapping),
            blocking_reasons=tuple(blocking),
        )

    def promote(
        self,
        preview: PreparedCorrectionRebase,
        active_request: DomainAnalysisRequest,
        active_result: DomainAnalysisResult,
        correction_set: DomainCorrectionWorkspace,
        candidate: PendingAutomaticCandidate,
    ) -> CorrectionRebasePromotion:
        current = self.prepare(
            active_request,
            active_result,
            correction_set,
            candidate,
            preview.resolutions,
        )
        if current != preview:
            raise ValueError("Prepared Correction Rebase is stale.")
        if not preview.is_ready:
            raise ValueError("Every Correction Rebase issue must be resolved.")
        decisions, domains, boundary_keys = _transferred_state(
            correction_set,
            preview.source_mapping,
        )
        review_targets: tuple[DomainCorrectionReviewTarget, ...] = (
            "m6",
            "orientation",
        )
        review_revisions = tuple(
            (target, correction_set.review_revision(target) + 1)
            for target in review_targets
        )
        successor = DomainCorrectionWorkspace(
            automatic_fingerprint=correction_anchor_fingerprint(candidate.result),
            revision=correction_set.revision + 1,
            orientation_decisions=decisions,
            manual_domains=domains,
            cleared_boundary_source_keys=boundary_keys,
            baseline_orientation_decisions=decisions,
            baseline_manual_domains=domains,
            legacy_boundary_source_keys=boundary_keys,
            review_revisions=review_revisions,
        )
        record = CorrectionRebaseRecord(
            record_id=self._record_id_factory(),
            recorded_at=self._clock(),
            previous_request=active_request,
            previous_result=active_result,
            previous_correction_set=correction_set,
            promoted_automatic_fingerprint=candidate.automatic_fingerprint,
            source_mapping=preview.source_mapping,
            resolutions=preview.resolutions,
        )
        return CorrectionRebasePromotion(successor, record)


def correction_anchor_fingerprint(result: DomainAnalysisResult) -> str:
    gate = result.m6_gate
    if gate is None:
        raise ValueError("Domain corrections require a published M6 gate.")
    return canonical_sha256({
        "schema_version": "domain-correction-automatic-anchor-v1",
        "m6_frames": [
            (frame.physical_frame_id, frame.m6_gate_fingerprint)
            for frame in gate.frames
        ],
        "classifiers": [
            (outcome.classifier_id, outcome.classifier_result_fingerprint)
            for outcome in result.classifier_outcomes or ()
        ],
    })


def _corrected_source_keys(
    correction_set: DomainCorrectionWorkspace,
) -> tuple[DetectionIdentity, ...]:
    keys = {
        DetectionIdentity(
            physical_frame_id=value.physical_frame_id,
            source_id=value.source_id,
        )
        for value in correction_set.orientation_decisions
    }
    keys.update(
        DetectionIdentity(
            physical_frame_id=domain.physical_frame_id,
            source_id=source_id,
        )
        for domain in correction_set.manual_domains
        for source_id in domain.restore_source_ids
    )
    keys.update(correction_set.cleared_boundary_source_keys)
    return tuple(sorted(keys))


def _source_fingerprints(
    result: DomainAnalysisResult,
) -> dict[DetectionIdentity, str | None]:
    gate = result.m6_gate
    if gate is None:
        return {}
    fingerprints: dict[DetectionIdentity, str | None] = {}
    for frame in gate.frames:
        footprints = source_footprints_for_frame(frame)
        molecules = _molecule_index(frame)
        for source_id in frame.analyzed_source_ids:
            footprint = footprints[source_id]
            molecule = molecules[source_id]
            identity = DetectionIdentity(
                physical_frame_id=frame.physical_frame_id,
                source_id=source_id,
            )
            fingerprints[identity] = (
                None
                if footprint is None
                else canonical_sha256({
                    "schema_version": "correction-rebase-source-v1",
                    "physical_frame_id": frame.physical_frame_id,
                    "source_id": source_id,
                    "coordinate_transform_fingerprint": (
                        frame.coordinate_transform_fingerprint
                    ),
                    "pixel_area_nm2": frame.pixel_area_nm2,
                    "source_kind": molecule.source_kind,
                    "point_xy_nm": molecule.point_xy_nm,
                    "footprint_pixels_xy": footprint,
                })
            )
    return fingerprints


def _source_footprints(
    result: DomainAnalysisResult,
) -> dict[DetectionIdentity, frozenset[tuple[int, int]] | None]:
    gate = result.m6_gate
    if gate is None:
        return {}
    return {
        DetectionIdentity(
            physical_frame_id=frame.physical_frame_id,
            source_id=source_id,
        ): (
            None if footprint is None else frozenset(footprint)
        )
        for frame in gate.frames
        for source_id, footprint in source_footprints_for_frame(frame).items()
    }


def _molecule_index(frame: M6FrameGate) -> dict[str, M6PublishedMolecule]:
    values = {
        member.source_id: member
        for component in frame.full_domains + frame.small_ordered_islands
        for member in component.members
    }
    values.update({value.source_id: value for value in frame.outside_members})
    return values


def _issue_for(
    key: DetectionIdentity,
    candidate_sources: dict[DetectionIdentity, str | None],
    active_footprints: dict[
        DetectionIdentity,
        frozenset[tuple[int, int]] | None,
    ],
    candidate_footprints: dict[
        DetectionIdentity,
        frozenset[tuple[int, int]] | None,
    ],
    missing_source_keys: tuple[DetectionIdentity, ...],
) -> CorrectionRebaseIssue:
    frame_id = key.physical_frame_id
    source_id = key.source_id
    candidates = (source_id,) if key in candidate_sources else _overlap_targets(
        key,
        active_footprints,
        candidate_footprints,
    )
    if key in candidate_sources:
        kind: CorrectionRebaseIssueKind = "changed_geometry"
    elif len(candidates) > 1:
        kind = "split"
    elif len(candidates) == 1 and sum(
        candidates[0] in _overlap_targets(
            missing_key,
            active_footprints,
            candidate_footprints,
        )
        for missing_key in missing_source_keys
        if missing_key.physical_frame_id == frame_id
    ) > 1:
        kind = "merge"
    else:
        kind = "missing_target"
    return CorrectionRebaseIssue(
        issue_id=canonical_sha256({"frame": frame_id, "source": source_id})[:20],
        physical_frame_id=frame_id,
        source_id=source_id,
        kind=kind,
        candidate_source_ids=candidates,
    )


def _overlap_targets(
    source_key: DetectionIdentity,
    active_footprints: dict[
        DetectionIdentity,
        frozenset[tuple[int, int]] | None,
    ],
    candidate_footprints: dict[
        DetectionIdentity,
        frozenset[tuple[int, int]] | None,
    ],
) -> tuple[str, ...]:
    physical_frame_id = source_key.physical_frame_id
    source_footprint = active_footprints.get(source_key)
    if not source_footprint:
        return ()
    return tuple(sorted(
        candidate_identity.source_id
        for candidate_identity, candidate_footprint in candidate_footprints.items()
        if candidate_identity.physical_frame_id == physical_frame_id
        and candidate_footprint
        and not source_footprint.isdisjoint(candidate_footprint)
    ))


def _resolved_targets(
    issue: CorrectionRebaseIssue,
    resolution: CorrectionRebaseResolution,
    candidate_sources: dict[DetectionIdentity, str | None],
) -> tuple[str, ...]:
    if resolution.action == "dropped":
        return ()
    targets = (
        (issue.source_id,)
        if resolution.action == "reapplied"
        else resolution.target_source_ids
    )
    missing = tuple(
        value
        for value in targets
        if DetectionIdentity(
            physical_frame_id=issue.physical_frame_id,
            source_id=value,
        ) not in candidate_sources
    )
    if missing:
        raise ValueError(f"Rebase resolution targets do not exist: {missing!r}.")
    return targets


def _mapping_conflicts(
    correction_set: DomainCorrectionWorkspace,
    mapping: tuple[CorrectionSourceMapping, ...],
) -> tuple[str, ...]:
    mapped = {
        value.source_identity: tuple(
            DetectionIdentity(
                physical_frame_id=value.source_identity.physical_frame_id,
                source_id=target_id,
            )
            for target_id in value.target_source_ids
        )
        for value in mapping
    }
    orientation_by_target: dict[DetectionIdentity, ManualOrientationDecision] = {}
    conflicts: set[str] = set()
    for decision in correction_set.orientation_decisions:
        identity = DetectionIdentity(
            physical_frame_id=decision.physical_frame_id,
            source_id=decision.source_id,
        )
        for target in mapped.get(identity, ()):
            previous = orientation_by_target.get(target)
            if previous is not None and (
                previous.orientation_label != decision.orientation_label
                or previous.reason_code != decision.reason_code
            ):
                conflicts.add(f"Conflicting orientation decisions target {target!r}.")
            orientation_by_target[target] = decision
    domain_by_target: dict[DetectionIdentity, str] = {}
    for domain in correction_set.manual_domains:
        if domain.is_deleted:
            continue
        for source_id in domain.source_ids:
            identity = DetectionIdentity(
                physical_frame_id=domain.physical_frame_id,
                source_id=source_id,
            )
            for target in mapped.get(identity, ()):
                previous_domain = domain_by_target.get(target)
                if (
                    previous_domain is not None
                    and previous_domain != domain.manual_domain_id
                ):
                    conflicts.add(f"Conflicting manual domains target {target!r}.")
                domain_by_target[target] = domain.manual_domain_id
    return tuple(sorted(conflicts))


def _transferred_state(
    correction_set: DomainCorrectionWorkspace,
    mapping: tuple[CorrectionSourceMapping, ...],
) -> tuple[
    tuple[ManualOrientationDecision, ...],
    tuple[ManualDomainRecord, ...],
    tuple[DetectionIdentity, ...],
]:
    targets = {
        value.source_identity: value.target_source_ids
        for value in mapping
    }
    decisions_by_key = {
        DetectionIdentity(
            physical_frame_id=decision.physical_frame_id,
            source_id=target_id,
        ): ManualOrientationDecision(
            decision.physical_frame_id,
            target_id,
            decision.orientation_label,
            decision.reason_code,
        )
        for decision in correction_set.orientation_decisions
        for target_id in targets.get(
            DetectionIdentity(
                physical_frame_id=decision.physical_frame_id,
                source_id=decision.source_id,
            ),
            (),
        )
    }
    decisions = tuple(decisions_by_key[key] for key in sorted(decisions_by_key))
    domains: list[ManualDomainRecord] = []
    for domain in correction_set.manual_domains:
        active_ids = _mapped_ids(domain.physical_frame_id, domain.source_ids, targets)
        restore_ids = _mapped_ids(
            domain.physical_frame_id,
            domain.restore_source_ids,
            targets,
        )
        if not restore_ids:
            domains.append(ManualDomainRecord(
                domain.physical_frame_id,
                domain.manual_domain_id,
                (),
                domain.restore_source_ids,
                True,
            ))
            continue
        domains.append(ManualDomainRecord(
            domain.physical_frame_id,
            domain.manual_domain_id,
            active_ids if not domain.is_deleted else (),
            restore_ids,
            domain.is_deleted or not active_ids,
        ))
    boundary_keys = tuple(sorted(
        DetectionIdentity(
            physical_frame_id=identity.physical_frame_id,
            source_id=target_id,
        )
        for identity in correction_set.cleared_boundary_source_keys
        for target_id in targets.get(identity, ())
    ))
    return tuple(decisions), tuple(domains), boundary_keys


def _mapped_ids(
    physical_frame_id: str,
    source_ids: tuple[str, ...],
    mapping: dict[DetectionIdentity, tuple[str, ...]],
) -> tuple[str, ...]:
    return tuple(sorted({
        target_id
        for source_id in source_ids
        for target_id in mapping.get(
            DetectionIdentity(
                physical_frame_id=physical_frame_id,
                source_id=source_id,
            ),
            (),
        )
    }))


__all__ = [
    "ApplyPreparedCorrectionRebase",
    "CorrectionRebaseIssue",
    "CorrectionRebasePolicy",
    "CorrectionRebasePromotion",
    "CorrectionRebaseRecord",
    "CorrectionRebaseResolution",
    "PendingAutomaticCandidate",
    "PrepareCorrectionRebase",
    "PreparedCorrectionRebase",
    "automatic_candidate_fingerprint",
    "correction_anchor_fingerprint",
]
