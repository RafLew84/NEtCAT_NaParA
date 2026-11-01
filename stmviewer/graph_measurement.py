"""One Deep graph relation with shared refusal and failure handling."""
from collections.abc import Callable

from stmviewer.frame import ImageFrame
from stmviewer.graph_provenance import check_cancelled
from stmviewer.graph_types import GraphEdge
from stmviewer.registration import RegistrationError, ShiftBackend, estimate_confidence


def measure_graph_pair(backend: ShiftBackend, frames: tuple[ImageFrame, ...], i: int, j: int, *,
                        cancelled: Callable[[], bool] | None = None) -> GraphEdge:
    """Measure j onto i; local refusal remains an edge, execution failure aborts."""
    from nanotrack.registration.phase_correlation import PhaseCorrelationBackendError

    check_cancelled(cancelled)
    try:
        result = backend.estimate(frames[i].data, frames[j].data, moving_frame_index=j)
    except PhaseCorrelationBackendError as error:
        check_cancelled(cancelled)
        return GraphEdge(i, j, None, 'missing', str(error) or type(error).__name__)
    except Exception as error:
        check_cancelled(cancelled)
        raise RegistrationError(f'Deep — klatki {i + 1}–{j + 1}: '
                                f'{str(error) or type(error).__name__}') from error
    check_cancelled(cancelled)
    status, score = estimate_confidence('deep_matcher_translation', result)
    return GraphEdge(i, j, (float(result.shift_xy[0]), float(result.shift_xy[1])),
                     status, quality_score=score)
