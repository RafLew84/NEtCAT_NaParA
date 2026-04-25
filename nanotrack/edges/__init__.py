"""Edge-detection contracts and subprocess helpers."""

from .backend import DexiNedBackendConfig, DexiNedBackendError, DexiNedBackendTimeoutError, DexiNedSubprocessBackend
from .contract import DEXINED_CONTRACT_VERSION, DexiNedRunInput, DexiNedRunOutput
from .ddn_backend import DdnBackendConfig, DdnBackendError, DdnBackendTimeoutError, DdnSubprocessBackend
from .hybrid import hybrid_refine_polyline, resample_polyline_xy, sample_polyline_control_points
from .nbed_backend import NbedBackendConfig, NbedBackendError, NbedBackendTimeoutError, NbedSubprocessBackend
from .refinement import EdgeRefinementResult, refine_edge_polyline
from .teed_backend import TeedBackendConfig, TeedBackendError, TeedBackendTimeoutError, TeedSubprocessBackend

__all__ = [
    "DEXINED_CONTRACT_VERSION",
    "DdnBackendConfig",
    "DdnBackendError",
    "DdnBackendTimeoutError",
    "DdnSubprocessBackend",
    "DexiNedBackendConfig",
    "DexiNedBackendError",
    "DexiNedBackendTimeoutError",
    "DexiNedRunInput",
    "DexiNedRunOutput",
    "DexiNedSubprocessBackend",
    "EdgeRefinementResult",
    "hybrid_refine_polyline",
    "NbedBackendConfig",
    "NbedBackendError",
    "NbedBackendTimeoutError",
    "NbedSubprocessBackend",
    "refine_edge_polyline",
    "resample_polyline_xy",
    "sample_polyline_control_points",
    "TeedBackendConfig",
    "TeedBackendError",
    "TeedBackendTimeoutError",
    "TeedSubprocessBackend",
]
