"""Existing pair estimators prepared once for a graph calculation."""

from dataclasses import asdict, replace
from typing import Callable

from stmviewer.deep_matcher import DeepMatcherOptions, load_deep_backend
from stmviewer.deep_ecc import HYBRID_METHOD, load_deep_ecc_backend
from stmviewer.local_registration import LOCAL_METHOD, load_deep_local_backend
from stmviewer.graph_methods import graph_method_label, graph_requires_deep
from stmviewer.graph_provenance import cpu_graph_config, deep_graph_config
from stmviewer.graph_types import GraphConfig
from stmviewer.registration import ShiftBackend, create_shift_backend


def load_graph_backend(method: str, options: DeepMatcherOptions, window: int, *,
                       progress: Callable[[str], None], cancelled: Callable[[], bool] | None,
                       ) -> tuple[ShiftBackend, GraphConfig]:
    graph_method_label(method)
    if not graph_requires_deep(method):
        backend = create_shift_backend(method)
        if method == 'tile_correlation_ransac':
            from stmviewer.graph_tile_backend import GraphTileBackend
            backend = GraphTileBackend(getattr(backend, 'config'))
        return backend, cpu_graph_config(method, window, asdict(getattr(backend, 'config')))
    if method == HYBRID_METHOD:
        composite = load_deep_ecc_backend(options, progress=progress, cancelled=cancelled)
        backend, device = composite, composite.device
        text = composite.settings_text
    elif method == LOCAL_METHOD:
        local = load_deep_local_backend(options, progress=progress, cancelled=cancelled)
        backend, device = local, local.device
        text = local.settings_text
    else:
        loaded = load_deep_backend(options, progress=progress, cancelled=cancelled)
        backend, device = loaded.backend, loaded.device
        text = ''
    config = deep_graph_config(options, window, device, cancelled=cancelled, method=method)
    settings = dict(config.backend_settings)
    if text:
        settings.update(settings_text=text, second_stage_device='CPU')
    return backend, replace(config, method=method, backend_settings=tuple(sorted(settings.items())))


def local_pair_refusal(error: Exception) -> bool:
    """Only explicit estimator refusals may leave a missing edge; unknown faults abort."""
    from nanotrack.registration.phase_correlation import PhaseCorrelationBackendError
    from nanotrack.registration.ecc_translation import ECCTranslationBackendError
    from stmviewer.local_consensus import LocalConsensusError

    chain: list[BaseException] = []
    current: BaseException | None = error
    while current is not None and all(current is not item for item in chain):
        chain.append(current)
        current = current.__cause__
    if any(isinstance(item, (MemoryError, OSError, ImportError, SystemError)) for item in chain):
        return False
    for item in chain:
        if isinstance(item, ECCTranslationBackendError):
            reason = str(item)
            if 'too little texture' in reason or 'cannot be normalized for ECC' in reason:
                return True
            cause = item.__cause__
            # OpenCV StsNoConv only. Allocation, argument and arbitrary native faults are fatal.
            if (cause is not None and type(cause).__module__ == 'cv2'
                    and getattr(cause, 'code', None) == -7):
                return True
        if isinstance(item, LocalConsensusError):
            return True
        if isinstance(item, PhaseCorrelationBackendError):
            reason = str(item)
            if 'too little texture' in reason or reason == 'Optical flow produced no valid vectors.':
                return True
            if reason.startswith('Only ') and any(fragment in reason for fragment in (
                ' feature matches;', ' registration tiles;',
            )):
                return True
    return False


def pair_failure_reason(error: Exception) -> str:
    reasons = []
    seen: list[BaseException] = []
    current: BaseException | None = error
    while current is not None and all(current is not item for item in seen):
        seen.append(current)
        reason = str(current) or type(current).__name__
        if reason not in reasons:
            reasons.append(reason)
        current = current.__cause__
    return ' Przyczyna: '.join(reasons)
