"""DexiNed edge-detection contracts and subprocess helpers."""

from .backend import DexiNedBackendConfig, DexiNedBackendError, DexiNedBackendTimeoutError, DexiNedSubprocessBackend
from .contract import DEXINED_CONTRACT_VERSION, DexiNedRunInput, DexiNedRunOutput
from .hybrid import hybrid_refine_polyline, resample_polyline_xy, sample_polyline_control_points

__all__ = [
    "DEXINED_CONTRACT_VERSION",
    "DexiNedBackendConfig",
    "DexiNedBackendError",
    "DexiNedBackendTimeoutError",
    "DexiNedRunInput",
    "DexiNedRunOutput",
    "DexiNedSubprocessBackend",
    "hybrid_refine_polyline",
    "resample_polyline_xy",
    "sample_polyline_control_points",
]
