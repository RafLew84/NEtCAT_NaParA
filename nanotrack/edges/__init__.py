"""Edge-detection contracts and subprocess helpers."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .backend import DexiNedBackendConfig, DexiNedBackendError, DexiNedBackendTimeoutError, DexiNedSubprocessBackend
from .contract import DEXINED_CONTRACT_VERSION, DexiNedRunInput, DexiNedRunOutput
from .ddn_backend import DdnBackendConfig, DdnBackendError, DdnBackendTimeoutError, DdnSubprocessBackend
from .hybrid import hybrid_refine_polyline, resample_polyline_xy, sample_polyline_control_points
from .muge_backend import MugeBackendConfig, MugeBackendError, MugeBackendTimeoutError, MugeSubprocessBackend
from .nbed_backend import NbedBackendConfig, NbedBackendError, NbedBackendTimeoutError, NbedSubprocessBackend
from .pidinet_backend import (
    PidinetBackendConfig,
    PidinetBackendError,
    PidinetBackendTimeoutError,
    PidinetSubprocessBackend,
)
if TYPE_CHECKING:
    from .quality import assess_edge_geometry_quality, format_edge_geometry_review
    from .refinement import EdgeRefinementResult, refine_edge_polyline
from .subprocess_utils import EdgeSubprocessCancelledError
from .teed_backend import TeedBackendConfig, TeedBackendError, TeedBackendTimeoutError, TeedSubprocessBackend
from .uaed_backend import UaedBackendConfig, UaedBackendError, UaedBackendTimeoutError, UaedSubprocessBackend


def __getattr__(name: str) -> Any:
    # Model interpreters need only the NPZ contract, not the GUI's SciPy/skimage analysis.
    modules = {"assess_edge_geometry_quality": ".quality", "format_edge_geometry_review": ".quality",
               "EdgeRefinementResult": ".refinement", "refine_edge_polyline": ".refinement"}
    if name not in modules:
        raise AttributeError(name)
    value = getattr(import_module(modules[name], __name__), name)
    globals()[name] = value
    return value

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
    "EdgeSubprocessCancelledError",
    "assess_edge_geometry_quality",
    "format_edge_geometry_review",
    "hybrid_refine_polyline",
    "MugeBackendConfig",
    "MugeBackendError",
    "MugeBackendTimeoutError",
    "MugeSubprocessBackend",
    "NbedBackendConfig",
    "NbedBackendError",
    "NbedBackendTimeoutError",
    "NbedSubprocessBackend",
    "PidinetBackendConfig",
    "PidinetBackendError",
    "PidinetBackendTimeoutError",
    "PidinetSubprocessBackend",
    "refine_edge_polyline",
    "resample_polyline_xy",
    "sample_polyline_control_points",
    "TeedBackendConfig",
    "TeedBackendError",
    "TeedBackendTimeoutError",
    "TeedSubprocessBackend",
    "UaedBackendConfig",
    "UaedBackendError",
    "UaedBackendTimeoutError",
    "UaedSubprocessBackend",
]
