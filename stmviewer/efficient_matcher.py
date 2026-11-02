"""EfficientLoFTR's local-only boundary, shared by pair, chain and graph jobs."""

from collections.abc import Callable
from dataclasses import asdict, replace
from typing import Protocol
from importlib.util import find_spec
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from nanotrack.core import RegistrationFrameResult
from stmviewer.correspondence_types import ImagePreparation, CorrespondenceDiagnostics, CorrespondenceRefusal
from stmviewer.correspondence_consensus import CorrespondenceConfig, estimate_correspondence_translation
from stmviewer.deep_matcher import DeepMatcherOptions

EFFICIENT_METHOD = 'efficient_loftr'
EFFICIENT_LABEL = 'EfficientLoFTR'
SOURCE_COMMIT = '07e9c1401e71e9c556b1fda9d86d060af36ba176'
SOURCE_SHA256 = '4007cea8f5fdcaeb46cfab76fe72c94666c49181a077e66eb1deff0268ef78ec'
WEIGHTS_SHA256 = '0af6291141c736e75e94b7f8aae4399b77c7731b3f08758212b2cfe370188878'
WEIGHTS_BYTES = 192797577


def default_efficient_options() -> DeepMatcherOptions:
    root = Path.home() / '.cache' / 'stmviewer' / 'efficientloftr'
    return DeepMatcherOptions(root / 'weights' / 'eloftr_outdoor.ckpt', 'auto', root / 'source')


def efficient_unavailable_reason(options: DeepMatcherOptions) -> str | None:
    """Cheap local preflight. Exact hashes and imports are checked in the worker."""
    if options.device not in ('auto', 'cpu', 'cuda'):
        return 'Nieznane urządzenie; wybierz Auto, CPU lub CUDA.'
    source = options.source
    try:
        if source is None or not (source / 'src/loftr/loftr.py').is_file():
            return 'Wskaż katalog lokalnego kodu EfficientLoFTR (z podkatalogiem src/loftr).'
        if options.weights is None or not options.weights.is_file():
            return 'Wskaż lokalne wagi EfficientLoFTR: eloftr_outdoor.ckpt.'
        if options.weights.stat().st_size != WEIGHTS_BYTES:
            return 'Nieprawidłowy rozmiar wag EfficientLoFTR; wymagany oryginalny eloftr_outdoor.ckpt.'
        for library in ('torch', 'einops', 'kornia', 'yacs', 'loguru', 'pytorch_lightning', 'joblib'):
            if find_spec(library) is None:
                return f'Brak biblioteki {library} wymaganej przez EfficientLoFTR.'
    except (OSError, ValueError, ImportError) as error:
        return str(error)
    return None


def prepare_image(data: 'NDArray[np.float64]') -> tuple['NDArray[np.float32]', 'ImagePreparation']:
    """Independent, overflow-safe min/max; pad right/bottom without resizing."""
    values = np.asarray(data, dtype=np.float64)
    if values.ndim != 2 or min(values.shape) < 1 or not np.isfinite(values).all():
        raise ValueError('EfficientLoFTR wymaga niepustego obrazu 2D bez NaN/Inf.')
    low, high = float(values.min()), float(values.max())
    if low == high:
        normalized = np.zeros(values.shape, dtype=np.float32)
    else:
        scale = max(abs(low), abs(high))
        normalized = np.asarray((values / scale - low / scale) / (high / scale - low / scale), dtype=np.float32)
    height, width = values.shape
    bottom, right = -height % 32, -width % 32
    prepared = np.pad(normalized, ((0, bottom), (0, right)), mode='constant')
    metadata = ImagePreparation((height, width), (height + bottom, width + right),
                                (1., 1.), (0, 0, right, bottom), (low, high))
    return prepared, metadata


def points_to_original(points: 'NDArray[np.float64]', preparation: 'ImagePreparation'
                       ) -> 'NDArray[np.float64]':
    """Invert separate X/Y scaling and model-space padding for either image."""
    values = np.asarray(points, dtype=np.float64)
    scales = np.asarray(preparation.scale_xy, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2 or not np.isfinite(scales).all() or np.any(scales <= 0):
        raise ValueError('Nieprawidłowe punkty lub skala wejścia modelu.')
    return np.asarray((values - preparation.padding_ltrb[:2]) / scales, dtype=np.float64)


class CorrespondenceEngine(Protocol):
    """External inference boundary; model-space grayscale images to paired XY."""

    def match(self, reference: NDArray[np.float32], moving: NDArray[np.float32]
              ) -> tuple[NDArray[np.float64], NDArray[np.float64]]: ...

    def close(self) -> None: ...


class EfficientBackend:
    def __init__(self, engine: CorrespondenceEngine, *, device: str,
                 provenance: tuple[tuple[str, str], ...],
                 config: CorrespondenceConfig = CorrespondenceConfig(),
                 cancelled: Callable[[], bool] | None = None) -> None:
        self._engine: CorrespondenceEngine | None = engine
        self.device = device
        self.provenance = provenance
        self.config = config
        self._cancelled = cancelled
        self.last_diagnostics: CorrespondenceDiagnostics | None = None
        self.settings_text = ('EfficientLoFTR outdoor; full; FP32; oryginały, niezależny min/max; '
                              'bez skalowania, padding do wielokrotności 32; translation-consensus-v1; '
                              'poparcie nie jest prawdopodobieństwem poprawnego dryfu.; '
                              + '; '.join(f'{key}={value}' for key, value in asdict(config).items()))

    def _checkpoint(self) -> None:
        if self._cancelled is not None and self._cancelled():
            from stmviewer.registration import RegistrationCancelled
            raise RegistrationCancelled

    def estimate(self, reference_frame: NDArray[np.float64], moving_frame: NDArray[np.float64],
                 *, moving_frame_index: int) -> RegistrationFrameResult:
        from stmviewer.registration import RegistrationCancelled, RegistrationError

        self.last_diagnostics = None
        self._checkpoint()
        if self._engine is None:
            raise RegistrationError('EfficientLoFTR: zadanie zostało zakończone; model jest zwolniony.')
        preparations: tuple[ImagePreparation, ...] = ()
        try:
            reference, reference_preparation = prepare_image(reference_frame)
            moving, moving_preparation = prepare_image(moving_frame)
            preparations = (reference_preparation, moving_preparation)
            self._checkpoint()
            p0, p1 = self._engine.match(reference, moving)
            self._checkpoint()
            evidence = estimate_correspondence_translation(
                points_to_original(p0, reference_preparation), points_to_original(p1, moving_preparation),
                reference_preparation.original_shape, moving_preparation.original_shape,
                config=self.config, cancelled=self._cancelled,
            )
            evidence = replace(evidence, preparation=preparations, model_provenance=self.provenance)
            self.last_diagnostics = evidence
            self._checkpoint()
            assert evidence.final_shift_xy is not None
            return RegistrationFrameResult(moving_frame_index, evidence.final_shift_xy, EFFICIENT_METHOD,
                                           status=evidence.status)
        except CorrespondenceRefusal as error:
            evidence = replace(error.diagnostics, preparation=preparations, model_provenance=self.provenance)
            self.last_diagnostics = evidence
            raise CorrespondenceRefusal(evidence) from error
        except (RegistrationCancelled, RegistrationError):
            raise
        except Exception as error:
            self._checkpoint()
            raise RegistrationError(f'EfficientLoFTR: {str(error) or type(error).__name__}') from error

    def close(self) -> None:
        engine, self._engine = self._engine, None
        if engine is not None:
            engine.close()


def load_efficient_backend(options: DeepMatcherOptions, *,
                           progress: Callable[[str], None] | None = None,
                           cancelled: Callable[[], bool] | None = None) -> EfficientBackend:
    """Validate exact local artifacts before importing code or deserializing weights."""
    from hashlib import sha256
    from importlib.metadata import PackageNotFoundError, version
    from stmviewer.registration import RegistrationCancelled, RegistrationError

    def report(text: str) -> None:
        if cancelled is not None and cancelled():
            raise RegistrationCancelled
        if progress is not None:
            progress(text)
        if cancelled is not None and cancelled():
            raise RegistrationCancelled

    report('EfficientLoFTR: sprawdzanie lokalnych plików')
    reason = efficient_unavailable_reason(options)
    if reason:
        raise RegistrationError(f'EfficientLoFTR: {reason}')
    source, weights = options.source, options.weights
    assert source is not None and weights is not None
    engine = None
    try:
        digest = sha256()
        for file in sorted((source / 'src').rglob('*.py')):
            report('EfficientLoFTR: sprawdzanie wersji kodu')
            digest.update(file.relative_to(source).as_posix().encode('utf-8'))
            digest.update(b'\0')
            digest.update(file.read_bytes())
            digest.update(b'\0')
        source_hash = digest.hexdigest()
        if source_hash != SOURCE_SHA256:
            raise ValueError(f'Niezgodny kod EfficientLoFTR; wymagany commit {SOURCE_COMMIT}.')
        digest = sha256()
        with weights.open('rb') as stream:
            while block := stream.read(1024 * 1024):
                report('EfficientLoFTR: sprawdzanie SHA-256 wag')
                digest.update(block)
        weights_hash = digest.hexdigest()
        if weights_hash != WEIGHTS_SHA256:
            raise ValueError('Niezgodna suma SHA-256 wag EfficientLoFTR.')
        from stmviewer.efficient_runtime import TorchEfficientRuntime
        engine = TorchEfficientRuntime(source, weights, options.device, report)
        provenance = {
            'source_path': str(source.resolve()), 'source_commit': SOURCE_COMMIT,
            'source_sha256': source_hash, 'source_license': 'PRL v1.0',
            'weights_path': str(weights.resolve()), 'weights_sha256': weights_hash,
            'weights_variant': 'eloftr_outdoor.ckpt', 'requested_device': options.device,
            'actual_device': engine.device, 'precision': 'FP32',
            'model_config': 'full_default_cfg; reparameter; eval',
            'preprocessing': 'minmax-float32-v1; no resize; right/bottom zero padding to 32',
            'aggregation': 'translation-consensus-v1',
        }
        for name in ('torch', 'torchvision', 'numpy', 'einops', 'kornia', 'yacs', 'loguru',
                     'pytorch-lightning', 'torchmetrics', 'joblib'):
            try:
                provenance['library_' + name] = version(name)
            except PackageNotFoundError:
                provenance['library_' + name] = 'unavailable'
        report('EfficientLoFTR: model załadowany')
        return EfficientBackend(engine, device=engine.device, provenance=tuple(sorted(provenance.items())),
                                cancelled=cancelled)
    except (RegistrationCancelled, RegistrationError):
        if engine is not None:
            engine.close()
        raise
    except Exception as error:
        if engine is not None:
            engine.close()
        report('EfficientLoFTR: błąd przygotowania')
        raise RegistrationError(f'EfficientLoFTR: {str(error) or type(error).__name__}') from error
