"""SuperPoint/LightGlue correspondences in original pixels and shared consensus."""

from collections.abc import Callable
from dataclasses import asdict, replace
from typing import Protocol
from stmviewer.method_parameters import LightGlueParameters, ContrastParameters
from stmviewer.feature_preparation import prepare_feature_image
from stmviewer.feature_provenance import profile_text
from stmviewer.deep_matcher import DeepMatcherOptions

import numpy as np
from numpy.typing import NDArray
from nanotrack.core import RegistrationFrameResult
from stmviewer.correspondence_consensus import CorrespondenceConfig, estimate_correspondence_translation
from stmviewer.correspondence_types import CorrespondenceDiagnostics, CorrespondenceRefusal, ImagePreparation

LIGHTGLUE_METHOD = 'lightglue_superpoint'
LIGHTGLUE_LABEL = 'LightGlue + SuperPoint'


def prepare_lightglue_image(data: NDArray[np.float64], contrast: ContrastParameters = ContrastParameters()) -> tuple[NDArray[np.float32], ImagePreparation]:
    """Native-size single-channel min/max bridge; no artificial border or rescaling."""
    values = np.asarray(data, dtype=np.float64)
    if values.ndim != 2 or min(values.shape) < 8 or not np.isfinite(values).all():
        raise ValueError('LightGlue + SuperPoint wymaga obrazu 2D co najmniej 8×8 bez NaN/Inf.')
    normalized, preparation = prepare_feature_image(values, contrast, uint8=False)
    return np.asarray(normalized, dtype=np.float32), preparation


class LightGlueEngine(Protocol):
    last_metrics: dict[str, float]

    def match(self, reference: NDArray[np.float32], moving: NDArray[np.float32]
              ) -> tuple[NDArray[np.float64], NDArray[np.float64]]: ...

    def close(self) -> None: ...


class LightGlueBackend:
    """A single reused external model and unweighted global translation estimator."""

    def __init__(self, engine: LightGlueEngine, *, device: str,
                 provenance: tuple[tuple[str, str], ...],
                 config: CorrespondenceConfig = CorrespondenceConfig(),
                 parameters: LightGlueParameters | None = None,
                 cancelled: Callable[[], bool] | None = None) -> None:
        self._engine: LightGlueEngine | None = engine
        self.parameters = parameters or LightGlueParameters(radius=config.inlier_radius)
        config = replace(config, inlier_radius=self.parameters.radius)
        self.device, self.provenance, self.config = device, provenance, config
        self._cancelled = cancelled
        self.last_diagnostics: CorrespondenceDiagnostics | None = None
        self.last_metrics: dict[str, float] = {}
        self.settings_text = ('LightGlue + SuperPoint; ' + profile_text(LIGHTGLUE_METHOD, self.parameters)
                              + '; rozmiar original; resize=None; bez paddingu; translation-consensus-v2; '
                              'poparcie nie jest prawdopodobieństwem dryfu; '
                              + '; '.join(f'{key}={value}' for key, value in asdict(config).items()))

    def _checkpoint(self) -> None:
        if self._cancelled is not None and self._cancelled():
            from stmviewer.registration import RegistrationCancelled
            raise RegistrationCancelled

    def estimate(self, reference_frame: NDArray[np.float64], moving_frame: NDArray[np.float64],
                 *, moving_frame_index: int) -> RegistrationFrameResult:
        from stmviewer.registration import RegistrationCancelled, RegistrationError
        self.last_diagnostics = None
        self.last_metrics = {}
        preparations: tuple[ImagePreparation, ...] = ()
        try:
            self._checkpoint()
            if self._engine is None:
                raise RegistrationError('LightGlue + SuperPoint: model został zwolniony.')
            reference, rp = prepare_lightglue_image(reference_frame, self.parameters.contrast)
            moving, mp = prepare_lightglue_image(moving_frame, self.parameters.contrast)
            preparations = (rp, mp)
            self._checkpoint()
            # Extractor.extract has already returned keypoints in original pixels.
            p0: NDArray[np.float64]
            p1: NDArray[np.float64]
            if reference.min() == reference.max() or moving.min() == moving.max():
                p0 = p1 = np.empty((0, 2), dtype=np.float64)
            else:
                p0, p1 = self._engine.match(reference, moving)
            self.last_metrics = dict(self._engine.last_metrics)
            self._checkpoint()
            evidence = estimate_correspondence_translation(
                p0, p1, rp.original_shape, mp.original_shape, config=self.config, cancelled=self._cancelled)
            evidence = replace(evidence, preparation=preparations, model_provenance=self.provenance)
            self.last_diagnostics = evidence
            assert evidence.final_shift_xy is not None
            return RegistrationFrameResult(moving_frame_index, evidence.final_shift_xy,
                                           LIGHTGLUE_METHOD, status=evidence.status)
        except CorrespondenceRefusal as error:
            evidence = replace(error.diagnostics, preparation=preparations, model_provenance=self.provenance)
            self.last_diagnostics = evidence
            raise CorrespondenceRefusal(evidence) from error
        except (RegistrationCancelled, RegistrationError):
            self.close()
            raise
        except Exception as error:
            self.close()
            self._checkpoint()
            raise RegistrationError(f'LightGlue + SuperPoint: {str(error) or type(error).__name__}') from error

    def close(self) -> None:
        engine, self._engine = self._engine, None
        if engine is not None:
            engine.close()


def default_lightglue_options() -> 'DeepMatcherOptions':
    from pathlib import Path
    from stmviewer.deep_matcher import DeepMatcherOptions
    root = Path.home() / '.cache/stmviewer/lightglue'
    return DeepMatcherOptions(root / 'weights/superpoint_lightglue.pth', 'auto', root / 'source',
                              extractor_weights=root / 'weights/superpoint_v1.pth')


def lightglue_unavailable_reason(options: 'DeepMatcherOptions') -> str | None:
    """Cheap preflight; exact hashes are checked by the loader before any inference."""
    from importlib.util import find_spec
    from stmviewer.lightglue_resources import EXTRACTOR_BYTES, MATCHER_BYTES
    if options.device not in ('auto', 'cpu', 'cuda'):
        return 'Nieznane urządzenie; wybierz Auto, CPU lub CUDA.'
    try:
        if options.source is None or any(not (options.source / 'lightglue' / name).is_file()
                                         for name in ('lightglue.py', 'superpoint.py')):
            return 'Wskaż lokalny kod LightGlue z podkatalogiem lightglue.'
        if options.extractor_weights is None or not options.extractor_weights.is_file():
            return 'Wskaż lokalne wagi ekstraktora SuperPoint: superpoint_v1.pth.'
        if options.weights is None or not options.weights.is_file():
            return 'Wskaż lokalne wagi matchera LightGlue: superpoint_lightglue.pth.'
        if options.extractor_weights.stat().st_size != EXTRACTOR_BYTES:
            return 'Nieprawidłowy rozmiar wag SuperPoint.'
        if options.weights.stat().st_size != MATCHER_BYTES:
            return 'Nieprawidłowy rozmiar wag LightGlue.'
        for name in ('torch', 'torchvision', 'numpy', 'kornia', 'cv2', 'matplotlib'):
            if find_spec(name) is None:
                return f'Brak biblioteki {name} wymaganej przez LightGlue + SuperPoint.'
    except (OSError, ValueError, ImportError) as error:
        return str(error)
    return None


def load_lightglue_backend(options: DeepMatcherOptions, *,
                          parameters: LightGlueParameters = LightGlueParameters(),
                          progress: Callable[[str], None] | None = None,
                          cancelled: Callable[[], bool] | None = None) -> LightGlueBackend:
    """One isolated worker in the app's interpreter, with pinned local artifacts."""
    from pathlib import Path
    import sys
    from stmviewer.lightglue_resources import MAX_KEYPOINTS, validate_resources
    from stmviewer.registration import RegistrationCancelled, RegistrationError
    from stmviewer.roma_process import RomaProcess

    def report(message: str) -> None:
        if cancelled is not None and cancelled():
            raise RegistrationCancelled
        if progress is not None:
            progress(message)
        if cancelled is not None and cancelled():
            raise RegistrationCancelled

    options = replace(options,
                      source=options.source.expanduser().resolve() if options.source else None,
                      weights=options.weights.expanduser().resolve() if options.weights else None,
                      extractor_weights=options.extractor_weights.expanduser().resolve() if options.extractor_weights else None)
    report('LightGlue + SuperPoint: sprawdzanie lokalnych zasobów')
    reason = lightglue_unavailable_reason(options)
    if reason:
        raise RegistrationError(f'LightGlue + SuperPoint: {reason}')
    assert options.source is not None and options.weights is not None and options.extractor_weights is not None
    engine = None
    try:
        validate_resources(options.source, options.weights, options.extractor_weights, report)
        config: dict[str, object] = {
            'source': str(options.source), 'weights': str(options.weights),
            'extractor_weights': str(options.extractor_weights), 'device': options.device,
            'samples': parameters.max_keypoints, 'parameters': asdict(parameters),
        }
        engine = RomaProcess(Path(sys.executable), config, progress=progress, cancelled=cancelled,
                             worker_script=Path(__file__).with_name('lightglue_worker.py'),
                             model_label=LIGHTGLUE_LABEL, temp_prefix='stmviewer-lightglue-')
        report('LightGlue + SuperPoint: gotowy model na ' + engine.device)
        return LightGlueBackend(engine, device=engine.device, provenance=engine.provenance,
                                parameters=parameters, cancelled=cancelled)
    except (RegistrationCancelled, RegistrationError):
        if engine is not None:
            engine.close()
        raise
    except Exception as error:
        if engine is not None:
            engine.close()
        report('LightGlue + SuperPoint: błąd przygotowania')
        raise RegistrationError(f'LightGlue + SuperPoint: {str(error) or type(error).__name__}') from error
