from __future__ import annotations

from dataclasses import asdict
from typing import Any, cast

from moltrack.analysis.domain_analysis import (
    ReferenceReviewDecision,
    ReferenceReviewFrame,
    ReferenceReviewScope,
    ReferenceReviewSignOff,
    ReferenceReviewWorkspace,
)
from moltrack.analysis.domain_analysis.reference_review import (
    ReferenceReviewAbstention,
    ReferenceReviewDisposition,
    ReferenceReviewEligibility,
    ReferenceReviewTarget,
)

from .domain_analysis_payload_validation import (
    integer_field,
    list_field,
    mapping,
    optional_text_field,
    required,
    text_field,
    text_list_field,
)


def reference_reviews_to_payload(
    workspace: ReferenceReviewWorkspace,
) -> list[dict[str, Any]]:
    return [
        {
            "scope": {
                **asdict(frame.scope),
                "source_ids": list(frame.scope.source_ids),
            },
            "decisions": [asdict(value) for value in frame.decisions],
            "sign_off": (
                None if frame.sign_off is None else asdict(frame.sign_off)
            ),
            "state_fingerprint": frame.state_fingerprint,
        }
        for frame in workspace.frames
    ]


def reference_reviews_from_payload(payload: Any) -> ReferenceReviewWorkspace:
    if not isinstance(payload, list):
        raise ValueError("domain_analysis.correction_workspace.reviews must be a list.")
    frames = []
    for index, value in enumerate(payload):
        path = f"domain_analysis.correction_workspace.reviews[{index}]"
        saved = mapping(value, path)
        scope = _scope(required(saved, "scope", path), f"{path}.scope")
        sign_off_payload = required(saved, "sign_off", path)
        sign_off = (
            None
            if sign_off_payload is None
            else _sign_off(sign_off_payload, f"{path}.sign_off")
        )
        frame = ReferenceReviewFrame(
            scope=scope,
            decisions=tuple(
                _decision(item, f"{path}.decisions[{item_index}]")
                for item_index, item in enumerate(
                    list_field(saved, "decisions", path)
                )
            ),
            sign_off=sign_off,
        )
        if frame.state_fingerprint != text_field(
            saved, "state_fingerprint", path
        ):
            raise ValueError(f"{path}.state_fingerprint does not match its review.")
        frames.append(frame)
    return ReferenceReviewWorkspace(tuple(frames))


def _scope(payload: Any, path: str) -> ReferenceReviewScope:
    saved = mapping(payload, path)
    scope = ReferenceReviewScope(
        target=cast(ReferenceReviewTarget, text_field(saved, "target", path)),
        physical_frame_id=text_field(saved, "physical_frame_id", path),
        automatic_fingerprint=text_field(saved, "automatic_fingerprint", path),
        source_geometry_fingerprint=text_field(
            saved, "source_geometry_fingerprint", path
        ),
        annotation_revision=integer_field(saved, "annotation_revision", path),
        source_ids=tuple(text_list_field(saved, "source_ids", path)),
    )
    if scope.fingerprint != text_field(saved, "fingerprint", path):
        raise ValueError(f"{path}.fingerprint does not match its scope.")
    return scope


def _decision(payload: Any, path: str) -> ReferenceReviewDecision:
    saved = mapping(payload, path)
    return ReferenceReviewDecision(
        source_id=text_field(saved, "source_id", path),
        eligibility=cast(
            ReferenceReviewEligibility,
            text_field(saved, "eligibility", path),
        ),
        disposition=cast(
            ReferenceReviewDisposition | None,
            optional_text_field(saved, "disposition", path),
        ),
        abstention=cast(
            ReferenceReviewAbstention | None,
            optional_text_field(saved, "abstention", path),
        ),
        reason_code=optional_text_field(saved, "reason_code", path),
    )


def _sign_off(payload: Any, path: str) -> ReferenceReviewSignOff:
    saved = mapping(payload, path)
    return ReferenceReviewSignOff(
        target=cast(ReferenceReviewTarget, text_field(saved, "target", path)),
        physical_frame_id=text_field(saved, "physical_frame_id", path),
        signed_at_utc=text_field(saved, "signed_at_utc", path),
        signed_state_fingerprint=text_field(
            saved, "signed_state_fingerprint", path
        ),
    )


__all__ = ["reference_reviews_from_payload", "reference_reviews_to_payload"]
