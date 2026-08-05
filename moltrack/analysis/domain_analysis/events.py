from __future__ import annotations

from collections.abc import Callable

from .models import DomainAnalysisEvent, DomainAnalysisEventStatus


def emit_event(
    on_event: Callable[[DomainAnalysisEvent], None] | None,
    stage_id: str,
    status: DomainAnalysisEventStatus,
    message: str,
    *,
    frame_index: int | None = None,
) -> None:
    if on_event is not None:
        on_event(
            DomainAnalysisEvent(
                stage_id=stage_id,
                status=status,
                message=message,
                frame_index=frame_index,
            )
        )
