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


def _library_versions(libraries: Sequence[str]) -> tuple[tuple[str, str], ...]:
    installed_versions = []
    for library in libraries:
        try:
            installed = version(library)
        except PackageNotFoundError:
            installed = 'unavailable'
        installed_versions.append((library, installed))
    return tuple(installed_versions)


def _code_version(root: Path, files: Sequence[str]) -> str:
    digest = sha256()
    for name in files:
        digest.update(name.encode('utf-8'))
        digest.update((root / name).read_bytes())
    return 'sha256:' + digest.hexdigest()


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
    names = ['numpy', 'scipy', 'torch', 'kornia']
    if method == 'deep_matcher_ecc':
        names.extend(('opencv-python', 'scikit-image'))
    libraries = _library_versions(names)
    root = Path(__file__).resolve().parent.parent
    files = ['stmviewer/graph_registration.py', 'stmviewer/graph_provenance.py',
             'stmviewer/graph_backends.py', 'stmviewer/graph_methods.py',
             'stmviewer/registration.py', 'stmviewer/deep_matcher.py',
             'nanotrack/registration/deep_matcher.py']
    if method == 'deep_matcher_ecc':
        files.extend(('stmviewer/deep_ecc.py', 'nanotrack/registration/ecc_translation.py',
                      'nanotrack/registration/phase_correlation.py'))
    elif method == 'deep_local_consensus':
        files.extend(('stmviewer/local_registration.py', 'stmviewer/local_consensus.py'))
    return GraphConfig(window, str(weights), digest.hexdigest(), options.device, device,
                       tuple(sorted((str(k), str(v)) for k, v in settings.items())),
                       libraries, _code_version(root, files), settings_version=2, method=method)


def cpu_graph_config(method: str, window: int, settings: dict[str, object]) -> GraphConfig:
    """Record the selected CPU estimator without importing any model runtime."""
    settings = {**settings, 'cache_max_pairs': MAX_CACHED_PAIRS}
    libraries = _library_versions(('numpy', 'scipy', 'scikit-image', 'opencv-python'))
    root = Path(__file__).resolve().parent.parent
    names = ['stmviewer/graph_registration.py', 'stmviewer/graph_provenance.py',
             'stmviewer/registration.py', 'stmviewer/graph_backends.py',
             'stmviewer/graph_methods.py']
    if method == 'tile_correlation_ransac':
        names.append('stmviewer/graph_tile_backend.py')
    names.extend(str(path.relative_to(root)) for path in sorted(
        (root / 'nanotrack/registration').glob('*.py')))
    return GraphConfig(window, None, None, 'cpu', 'CPU',
                       tuple(sorted((str(k), str(v)) for k, v in settings.items())),
                       libraries, _code_version(root, names), settings_version=2, method=method)


def _correspondence_graph_config(window: int, provenance: tuple[tuple[str, str], ...],
                                 consensus: dict[str, object], method: str,
                                 model_files: Sequence[str]) -> GraphConfig:
    metadata = dict(provenance)
    settings = {**metadata, 'cache_max_pairs': str(MAX_CACHED_PAIRS),
                **{f'consensus_{key}': str(value) for key, value in consensus.items()}}
    libraries = tuple((key.removeprefix('library_'), value) for key, value in provenance
                      if key.startswith('library_'))
    root = Path(__file__).resolve().parent.parent
    files = ('stmviewer/graph_registration.py', 'stmviewer/graph_provenance.py',
             'stmviewer/graph_backends.py', 'stmviewer/correspondence_types.py',
             'stmviewer/correspondence_consensus.py', *model_files)
    return GraphConfig(window, metadata['weights_path'], metadata['weights_sha256'],
                       metadata['requested_device'], metadata['actual_device'],
                       tuple(sorted(settings.items())), libraries, _code_version(root, files),
                       settings_version=2, method=method)


def efficient_graph_config(window: int, provenance: tuple[tuple[str, str], ...],
                           consensus: dict[str, object]) -> GraphConfig:
    """Persist the exact optional model and aggregation without runtime imports on restore."""
    return _correspondence_graph_config(window, provenance, consensus, 'efficient_loftr',
        ('stmviewer/efficient_matcher.py', 'stmviewer/efficient_runtime.py'))


def roma_graph_config(window: int, provenance: tuple[tuple[str, str], ...],
                      consensus: dict[str, object]) -> GraphConfig:
    """Record the isolated RoMa worker and original-pixel aggregation configuration."""
    files = tuple('stmviewer/' + path.name for path in sorted(Path(__file__).parent.glob('roma_*.py')))
    return _correspondence_graph_config(window, provenance, consensus, 'roma_v2', files)


def matchanything_graph_config(window: int, provenance: tuple[tuple[str, str], ...],
                               consensus: dict[str, object]) -> GraphConfig:
    """Record MatchAnything inference and the unchanged correspondence consensus."""
    files = tuple('stmviewer/' + path.name for path in sorted(Path(__file__).parent.glob('matchanything_*.py')))
    return _correspondence_graph_config(window, provenance, consensus, 'matchanything_eloftr', files)
