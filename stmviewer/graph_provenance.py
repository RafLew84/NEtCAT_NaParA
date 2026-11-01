"""Canonical source/content fingerprints and reproducible Deep configuration."""

from collections.abc import Callable, Sequence
from dataclasses import asdict
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.frame import ImageFrame
from stmviewer.graph_types import GraphConfig, GraphSource
from stmviewer.registration import RegistrationCancelled, RegistrationError

# Only lightweight previous measurements are reused; model/image caches are not retained.
MAX_CACHED_PAIRS = 10_000


def graph_sources(frames: Sequence[ImageFrame], *,
                  cancelled: Callable[[], bool] | None = None) -> tuple[GraphSource, ...]:
    """SHA256 of row-major little-endian float64 original pixels, without copies of a stack."""
    sources = []
    for frame in frames:
        digest = sha256()
        for start in range(0, frame.data.shape[0], 64):
            check_cancelled(cancelled)
            block = np.asarray(frame.data[start:start + 64], dtype='<f8', order='C')
            digest.update(memoryview(block).cast('B'))
        check_cancelled(cancelled)
        sources.append(GraphSource(str(frame.source), frame.source_frame_index,
                                   (int(frame.data.shape[0]), int(frame.data.shape[1])), digest.hexdigest()))
    return tuple(sources)


def check_cancelled(cancelled: Callable[[], bool] | None) -> None:
    if cancelled is not None and cancelled():
        raise RegistrationCancelled


def deep_graph_config(options: DeepMatcherOptions, window: int, device: str, *,
                      cancelled: Callable[[], bool] | None) -> GraphConfig:
    from nanotrack.registration import DeepMatcherTranslationConfig

    weights = options.weights
    if weights is None:
        raise RegistrationError('Wskaż lokalny plik wag LoFTR.')
    digest = sha256()
    with weights.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            check_cancelled(cancelled)
            digest.update(block)
    settings = asdict(DeepMatcherTranslationConfig())
    settings.update(preprocessing='local-loftr-minmax-float32-v1', cache_max_pairs=MAX_CACHED_PAIRS)
    libraries = []
    for library in ('numpy', 'scipy', 'torch', 'kornia'):
        try:
            installed = version(library)
        except PackageNotFoundError:
            installed = 'unavailable'
        libraries.append((library, installed))
    root = Path(__file__).resolve().parent.parent
    code = sha256()
    pair_code = sha256()
    for name in ('stmviewer/graph_registration.py', 'stmviewer/graph_provenance.py',
                 'stmviewer/deep_matcher.py', 'nanotrack/registration/deep_matcher.py'):
        code.update(name.encode('utf-8'))
        content = (root / name).read_bytes()
        code.update(content)
        if name.endswith('/deep_matcher.py'):
            pair_code.update(name.encode('utf-8'))
            pair_code.update(content)
    return GraphConfig(window, str(weights), digest.hexdigest(), options.device, device,
                       tuple(sorted((str(k), str(v)) for k, v in settings.items())),
                       tuple(libraries), 'sha256:' + code.hexdigest(),
                       pair_code_version='sha256:' + pair_code.hexdigest())
