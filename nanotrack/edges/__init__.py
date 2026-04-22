"""DexiNed edge-detection contracts and subprocess helpers."""

from .backend import DexiNedBackendConfig, DexiNedBackendError, DexiNedBackendTimeoutError, DexiNedSubprocessBackend
from .contract import DEXINED_CONTRACT_VERSION, DexiNedRunInput, DexiNedRunOutput
from .hybrid import hybrid_refine_polyline, resample_polyline_xy, sample_polyline_control_points
from .refinement import EdgeRefinementResult, refine_edge_polyline

__all__ = [
    "DEXINED_CONTRACT_VERSION",
    "DexiNedBackendConfig",
    "DexiNedBackendError",
    "DexiNedBackendTimeoutError",
    "DexiNedRunInput",
    "DexiNedRunOutput",
    "DexiNedSubprocessBackend",
    "EdgeRefinementResult",
    "hybrid_refine_polyline",
    "refine_edge_polyline",
    "resample_polyline_xy",
    "sample_polyline_control_points",
]
