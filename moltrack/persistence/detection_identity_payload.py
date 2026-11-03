from __future__ import annotations

from typing import Any

from moltrack.analysis.domain_analysis.detection_identity import DetectionIdentity


def identities_to_payload(
    values: tuple[DetectionIdentity, ...],
) -> list[list[str]]:
    return [
        [value.physical_frame_id, value.source_id]
        for value in values
    ]


def identities_from_payload(
    payload: Any,
    path: str,
) -> tuple[DetectionIdentity, ...]:
    if not isinstance(payload, list) or any(
        not isinstance(value, list)
        or len(value) != 2
        or any(not isinstance(item, str) or not item for item in value)
        for value in payload
    ):
        raise ValueError(f"{path} must contain Detection Identity pairs.")
    return tuple(
        DetectionIdentity(physical_frame_id=value[0], source_id=value[1])
        for value in payload
    )


__all__ = [
    "identities_from_payload",
    "identities_to_payload",
]
