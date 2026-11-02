"""Canonical source/content fingerprints and reproducible estimator configuration."""

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
                      cancelled: Callable[[], bool] | None,
                      method: str = 'deep_matcher_translation') -> GraphConfig:
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
    names = ['numpy', 'scipy', 'torch', 'kornia']
    if method == 'deep_matcher_ecc':
        names.extend(('opencv-python', 'scikit-image'))
    for library in names:
        try:
            installed = version(library)
        except PackageNotFoundError:
            installed = 'unavailable'
        libraries.append((library, installed))
    root = Path(__file__).resolve().parent.parent
    code = sha256()
    files = ['stmviewer/graph_registration.py', 'stmviewer/graph_provenance.py',
             'stmviewer/graph_backends.py', 'stmviewer/graph_methods.py',
             'stmviewer/registration.py', 'stmviewer/deep_matcher.py',
             'nanotrack/registration/deep_matcher.py']
    if method == 'deep_matcher_ecc':
        files.extend(('stmviewer/deep_ecc.py', 'nanotrack/registration/ecc_translation.py',
                      'nanotrack/registration/phase_correlation.py'))
    elif method == 'deep_local_consensus':
        files.extend(('stmviewer/local_registration.py', 'stmviewer/local_consensus.py'))
    for name in files:
        code.update(name.encode('utf-8'))
        code.update((root / name).read_bytes())
    return GraphConfig(window, str(weights), digest.hexdigest(), options.device, device,
                       tuple(sorted((str(k), str(v)) for k, v in settings.items())),
                       tuple(libraries), 'sha256:' + code.hexdigest(), settings_version=2, method=method)


def cpu_graph_config(method: str, window: int, settings: dict[str, object]) -> GraphConfig:
    """Record the selected CPU estimator without importing any model runtime."""
    settings = {**settings, 'cache_max_pairs': MAX_CACHED_PAIRS}
    libraries = []
    for library in ('numpy', 'scipy', 'scikit-image', 'opencv-python'):
        try:
            installed = version(library)
        except PackageNotFoundError:
            installed = 'unavailable'
        libraries.append((library, installed))
    root = Path(__file__).resolve().parent.parent
    code = sha256()
    names = ['stmviewer/graph_registration.py', 'stmviewer/graph_provenance.py',
             'stmviewer/registration.py', 'stmviewer/graph_backends.py',
             'stmviewer/graph_methods.py']
    if method == 'tile_correlation_ransac':
        names.append('stmviewer/graph_tile_backend.py')
    names.extend(str(path.relative_to(root)) for path in sorted(
        (root / 'nanotrack/registration').glob('*.py')))
    for name in names:
        code.update(name.encode('utf-8'))
        code.update((root / name).read_bytes())
    return GraphConfig(window, None, None, 'cpu', 'CPU',
                       tuple(sorted((str(k), str(v)) for k, v in settings.items())),
                       tuple(libraries), 'sha256:' + code.hexdigest(),
                       settings_version=2, method=method)
