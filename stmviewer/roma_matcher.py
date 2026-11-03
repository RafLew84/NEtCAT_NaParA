"""RoMa's isolated inference boundary and common original-pixel consensus."""

from collections.abc import Callable
from dataclasses import asdict, replace
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from nanotrack.core import RegistrationFrameResult
from stmviewer.correspondence_types import ImagePreparation, CorrespondenceDiagnostics, CorrespondenceRefusal
from stmviewer.correspondence_consensus import CorrespondenceConfig, estimate_correspondence_translation
from stmviewer.deep_matcher import DeepMatcherOptions

ROMA_METHOD = 'roma_v2'
ROMA_LABEL = 'RoMa v2'
ROMA_PRESETS = ('turbo', 'fast', 'base', 'precise')
PRESET_SIZES = {'turbo': 320, 'fast': 512, 'base': 640, 'precise': 1280}
WEIGHTS_BYTES = 1095883548


def normalized_points_to_original(points: NDArray[np.float64], preparation: ImagePreparation
                                  ) -> NDArray[np.float64]:
    """RoMa [-1,1] edge coordinates → model pixels → original XY, per image."""
    values = np.asarray(points, dtype=np.float64)
    scales = np.asarray(preparation.scale_xy, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2 or not np.isfinite(scales).all() or np.any(scales <= 0):
        raise ValueError('Nieprawidłowe punkty lub skala wejścia RoMa.')
    height, width = preparation.model_shape
    pixels = (values + 1.) * (width / 2., height / 2.)
    return np.asarray((pixels - preparation.padding_ltrb[:2]) / scales, dtype=np.float64)


def default_roma_options() -> DeepMatcherOptions:
    from stmviewer.model_paths import default_model_root, default_roma_interpreter
    root = default_model_root('romav2')
    executable = default_roma_interpreter()
    return DeepMatcherOptions(root / 'weights/romav2.0.1.pt', 'auto', root / 'dinov3',
                              executable, 'turbo', 1000, 20261102)


def roma_unavailable_reason(options: DeepMatcherOptions) -> str | None:
    """Filesystem-only preflight; never imports or runs the configured interpreter."""
    if options.device not in ('auto', 'cpu', 'cuda'):
        return 'Nieznane urządzenie RoMa; wybierz Auto, CPU lub CUDA.'
    if options.preset not in ROMA_PRESETS:
        return 'Nieznany preset RoMa v2.'
    if (type(options.samples) is not int or not 8 <= options.samples <= 10000
            or type(options.seed) is not int or not 0 <= options.seed <= 2 ** 31 - 1):
        return 'RoMa wymaga 8–10000 próbek i ziarna 0–2147483647.'
    try:
        if options.interpreter is None or not options.interpreter.is_file():
            return 'Wskaż interpreter Python osobnego środowiska netcat-romav2.'
        if options.source is None or not (options.source / 'hubconf.py').is_file():
            return 'Wskaż lokalny katalog kodu DINOv3 z plikiem hubconf.py.'
        if options.weights is None or not options.weights.is_file():
            return 'Wskaż lokalne wagi RoMa v2: romav2.0.1.pt.'
        if options.weights.stat().st_size != WEIGHTS_BYTES:
            return 'Nieprawidłowy rozmiar wag RoMa v2; wymagany oryginalny romav2.0.1.pt.'
    except OSError as error:
        return str(error)
    return None


def prepare_roma_image(data: NDArray[np.float64], preset: str
                       ) -> tuple[NDArray[np.float32], ImagePreparation]:
    values = np.asarray(data, dtype=np.float64)
    if values.ndim != 2 or min(values.shape) < 1 or not np.isfinite(values).all():
        raise ValueError('RoMa v2 wymaga niepustego obrazu 2D bez NaN/Inf.')
    low, high = float(values.min()), float(values.max())
    if low == high:
        normalized = np.zeros(values.shape, dtype=np.float32)
    else:
        scale = max(abs(low), abs(high))
        normalized = np.asarray((values / scale - low / scale) / (high / scale - low / scale), dtype=np.float32)
    height, width = values.shape
    side = PRESET_SIZES[preset]
    return normalized, ImagePreparation((height, width), (side, side), (side / width, side / height),
                                        (0, 0, 0, 0), (low, high), 'minmax-float32-rgb-v1', 3)


class RomaEngine(Protocol):
    """External worker boundary, returning normalized paired XY."""

    def match(self, reference: NDArray[np.float32], moving: NDArray[np.float32]
              ) -> tuple[NDArray[np.float64], NDArray[np.float64]]: ...

    def close(self) -> None: ...


class RomaBackend:
    def __init__(self, engine: RomaEngine, *, device: str,
                 provenance: tuple[tuple[str, str], ...], preset: str = 'turbo',
                 config: CorrespondenceConfig = CorrespondenceConfig(),
                 cancelled: Callable[[], bool] | None = None, samples: int = 1000,
                 seed: int = 20261102) -> None:
        self._engine: RomaEngine | None = engine
        self.device, self.provenance, self.config = device, provenance, config
        self.preset, self._cancelled = preset, cancelled
        self.samples, self.seed = samples, seed
        self.last_diagnostics: CorrespondenceDiagnostics | None = None
        self.last_metrics: dict[str, float] = {}
        self.settings_text = ('RoMa v2; ' + preset + '; RGB z szarości; niezależny min/max; '
                              'translation-consensus-v2; poparcie nie jest prawdopodobieństwem poprawnego dryfu; '
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
        self._checkpoint()
        if self._engine is None:
            raise RegistrationError('RoMa v2: zadanie zakończone; proces został zwolniony.')
        preparations: tuple[ImagePreparation, ...] = ()
        try:
            reference, rp = prepare_roma_image(reference_frame, self.preset)
            moving, mp = prepare_roma_image(moving_frame, self.preset)
            preparations = (rp, mp)
            p0, p1 = self._engine.match(reference, moving)
            self.last_metrics = dict(getattr(self._engine, 'last_metrics', {}))
            self._checkpoint()
            original0, original1 = spatially_balanced_points(
                normalized_points_to_original(p0, rp), normalized_points_to_original(p1, mp),
                rp.original_shape, mp.original_shape, samples=self.samples, seed=self.seed)
            self.last_metrics.update(raw_samples=float(len(p0)), spatial_samples=float(len(original0)))
            evidence = estimate_correspondence_translation(
                original0, original1,
                rp.original_shape, mp.original_shape, config=self.config, cancelled=self._cancelled)
            evidence = replace(evidence, preparation=preparations, model_provenance=self.provenance)
            self.last_diagnostics = evidence
            assert evidence.final_shift_xy is not None
            return RegistrationFrameResult(moving_frame_index, evidence.final_shift_xy, ROMA_METHOD,
                                           status=evidence.status)
        except CorrespondenceRefusal as error:
            evidence = replace(error.diagnostics, preparation=preparations, model_provenance=self.provenance)
            self.last_diagnostics = evidence
            raise CorrespondenceRefusal(evidence) from error
        except (RegistrationCancelled, RegistrationError):
            raise
        except Exception as error:
            self._checkpoint()
            raise RegistrationError(f'RoMa v2: {str(error) or type(error).__name__}') from error

    def close(self) -> None:
        engine, self._engine = self._engine, None
        if engine is not None:
            engine.close()


def load_roma_backend(options: DeepMatcherOptions, *, progress: Callable[[str], None] | None = None,
                      cancelled: Callable[[], bool] | None = None) -> RomaBackend:
    from stmviewer.registration import RegistrationError
    from stmviewer.roma_process import RomaProcess
    # Keep the interpreter's symlink: resolving .venv/bin/python to /usr/bin/python
    # would discard pyvenv.cfg and select the wrong environment.
    options = replace(options,
                      interpreter=options.interpreter.expanduser().absolute() if options.interpreter else None,
                      weights=options.weights.expanduser().resolve() if options.weights else None,
                      source=options.source.expanduser().resolve() if options.source else None)
    reason = roma_unavailable_reason(options)
    if reason:
        raise RegistrationError(f'RoMa v2: {reason}')
    assert options.interpreter is not None
    process = RomaProcess(options.interpreter, {
        'weights': str(options.weights), 'source': str(options.source), 'device': options.device,
        'preset': options.preset, 'samples': options.samples, 'seed': options.seed,
    }, progress=progress, cancelled=cancelled)
    return RomaBackend(process, device=process.device, provenance=process.provenance,
                       preset=options.preset, cancelled=cancelled, samples=options.samples, seed=options.seed)


def spatially_balanced_points(p0: NDArray[np.float64], p1: NDArray[np.float64],
                              reference_shape: tuple[int, int], moving_shape: tuple[int, int],
                              *, samples: int, seed: int
                              ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Cap each 8×8 cell in both originals; dense local artifacts get no extra votes.

    This limits a region's votes, not its influence on contextual DINO features.
    It does not establish independent measurements or guarantee a correct drift.
    """
    if p0.ndim != 2 or p0.shape[1] != 2 or p0.shape != p1.shape:
        raise ValueError('Korespondencje RoMa wymagają zgodnych tablic N × 2.')
    valid = np.isfinite(p0).all(axis=1) & np.isfinite(p1).all(axis=1)
    valid &= (p0 >= 0).all(axis=1) & (p1 >= 0).all(axis=1)
    valid &= (p0 < reference_shape[::-1]).all(axis=1) & (p1 < moving_shape[::-1]).all(axis=1)
    p0, p1 = p0[valid], p1[valid]
    cells0 = np.floor(p0 / reference_shape[::-1] * 8).astype(np.int64)
    cells1 = np.floor(p1 / moving_shape[::-1] * 8).astype(np.int64)
    bins0 = cells0[:, 1] * 8 + cells0[:, 0]
    bins1 = cells1[:, 1] * 8 + cells1[:, 0]
    counts0, counts1 = np.zeros(64, dtype=np.int64), np.zeros(64, dtype=np.int64)
    cap = max(1, (samples + 63) // 64)
    chosen = []
    for index in np.random.default_rng(seed).permutation(len(p0)):
        first, second = bins0[index], bins1[index]
        if counts0[first] >= cap or counts1[second] >= cap:
            continue
        chosen.append(index)
        counts0[first] += 1
        counts1[second] += 1
        if len(chosen) >= samples:
            break
    selected = np.asarray(chosen, dtype=np.int64)
    return p0[selected], p1[selected]
