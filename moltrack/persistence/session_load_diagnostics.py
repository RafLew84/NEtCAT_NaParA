from __future__ import annotations

from collections.abc import Callable
from functools import wraps
import json
from typing import Literal, ParamSpec, TypeVar


SessionLoadProblemKind = Literal["unsupported", "corrupt"]
_P = ParamSpec("_P")
_Result = TypeVar("_Result")


class MolTrackSessionLoadError(ValueError):
    """Terminal diagnosis for a session that was not activated."""

    def __init__(
        self,
        *,
        kind: SessionLoadProblemKind,
        component: str,
        reason: str,
    ) -> None:
        self.kind = kind
        self.component = component
        self.reason = reason
        super().__init__(
            f"MolTrack session {kind}: {component} cannot be loaded because "
            f"{reason} No session data was activated."
        )


def diagnose_session_load_errors(
    loader: Callable[_P, _Result],
) -> Callable[_P, _Result]:
    """Convert structural load failures into one non-activating diagnosis."""

    @wraps(loader)
    def diagnosed(*args: _P.args, **kwargs: _P.kwargs) -> _Result:
        try:
            return loader(*args, **kwargs)
        except (FileNotFoundError, MolTrackSessionLoadError):
            raise
        except json.JSONDecodeError as exc:
            raise MolTrackSessionLoadError(
                kind="corrupt",
                component="session_file",
                reason=f"invalid JSON at line {exc.lineno}, column {exc.colno}.",
            ) from exc
        except (KeyError, OverflowError, TypeError, UnicodeError, ValueError) as exc:
            reason = str(exc) or type(exc).__name__
            kind: SessionLoadProblemKind = (
                "unsupported"
                if reason.lstrip().startswith("Unsupported")
                else "corrupt"
            )
            raise MolTrackSessionLoadError(
                kind=kind,
                component=_diagnostic_component(reason),
                reason=reason,
            ) from exc

    return diagnosed


def _diagnostic_component(reason: str) -> str:
    if "schema_version" in reason and "MolTrack session" in reason:
        return "schema_version"
    if "registration_view_mode" in reason:
        return "ui.registration_view_mode"
    for component in (
        "working_series.source_frame_indices",
        "working_series.active_frame_index",
        "domain_analysis",
        "position_analysis",
        "source",
    ):
        if component in reason:
            return component
    return "session_file"
