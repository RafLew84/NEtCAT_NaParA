"""MatchAnything-ELoFTR, local resources and shared original-pixel consensus."""

from collections.abc import Callable
from dataclasses import asdict, replace
from typing import Protocol
import numpy as np
from numpy.typing import NDArray
from nanotrack.core import RegistrationFrameResult
from stmviewer.correspondence_consensus import CorrespondenceConfig, estimate_correspondence_translation
from stmviewer.correspondence_types import CorrespondenceDiagnostics, CorrespondenceRefusal, ImagePreparation
from stmviewer.efficient_matcher import prepare_image

from importlib.util import find_spec

from stmviewer.deep_matcher import DeepMatcherOptions

MATCHANYTHING_METHOD = 'matchanything_eloftr'
MATCHANYTHING_LABEL = 'MatchAnything-ELoFTR'
SOURCE_COMMIT = '6a7bcb589ec8da3a9e861e799122beaa5eba2193'
WEIGHTS_SHA256 = 'b394fd368488e5e3136906daac825fadd3dd5376755dcdf5cb6ede0de20f6e7e'
WEIGHTS_BYTES = 64366723
SOURCE_SHA256 = 'e7bb0235d9a7ebd38bf99fc34e9dcaaee325a0f55ecd8a2f12f1cce3671fc98f'


def default_matchanything_options() -> DeepMatcherOptions:
    from stmviewer.model_paths import default_model_root
    root = default_model_root('matchanything')
    return DeepMatcherOptions(root / 'weights/matchanything_eloftr.ckpt', 'auto', root / 'source')


def matchanything_unavailable_reason(options: DeepMatcherOptions) -> str | None:
    """Cheap local preflight; exact hashes are verified before importing vendor code."""
    if options.device not in ('auto', 'cpu', 'cuda'):
        return 'Nieznane urządzenie; wybierz Auto, CPU lub CUDA.'
    try:
        if options.source is None or not (options.source / 'src/loftr/loftr.py').is_file():
            return 'Wskaż lokalny kod MatchAnything z podkatalogiem src/loftr.'
        if options.weights is None or not options.weights.is_file():
            return 'Wskaż lokalne wagi MatchAnything-ELoFTR: matchanything_eloftr.ckpt.'
        if options.weights.stat().st_size != WEIGHTS_BYTES:
            return 'Nieprawidłowy rozmiar wag MatchAnything-ELoFTR.'
        for name in ('torch', 'numpy', 'einops', 'kornia', 'yacs', 'loguru', 'cv2', 'PIL'):
            if find_spec(name) is None:
                return f'Brak biblioteki {name} wymaganej przez MatchAnything-ELoFTR.'
    except (OSError, ValueError, ImportError) as error:
        return str(error)
    return None




def prepare_matchanything_image(data: NDArray[np.float64]) -> tuple[NDArray[np.float32], ImagePreparation]:
    """STM min/max bridge followed by the pinned authors' match_images library preset.

    The preset forces 640×480 (before square padding); 832 is the first-stage
    maximum side and the positional encoding setting, not the final input size.
    """
    import cv2
    from PIL import Image

    normalized, original = prepare_image(data)
    height, width = original.original_shape
    # The demonstration accepts RGB uint8. STM is grayscale, replicated to RGB.
    image = np.repeat((normalized[:height, :width] * 255.).astype(np.uint8)[..., None], 3, axis=2)
    values = image.astype(np.float32)
    if max(height, width) > 832:
        ratio = 832. / max(height, width)
        intermediate = (int(round(width * ratio)), int(round(height * ratio)))
        if min(intermediate) < 1:
            raise ValueError('Proporcje obrazu są zbyt skrajne dla skalowania MatchAnything do 832 px.')
        values = np.asarray(cv2.resize(values, intermediate, interpolation=cv2.INTER_AREA), dtype=np.float32)
    # Authors' resize_image switches both axes to LINEAR when either expands.
    interpolation = cv2.INTER_LINEAR if values.shape[1] < 640 or values.shape[0] < 480 else cv2.INTER_AREA
    values = np.asarray(cv2.resize(values, (640, 480), interpolation=interpolation), dtype=np.float32)
    # match_images divides the tensor by255; the model wrapper multiplies it back
    # before uint8/PIL grayscale. Its dfactor32 resize is a no-op at640×480.
    values = ((values / np.float32(255.)) * np.float32(255.)).astype(np.uint8)
    gray = Image.fromarray(values).convert('L').resize((640, 480), Image.Resampling.LANCZOS)
    prepared = np.pad(np.asarray(gray, dtype=np.float32) / np.float32(255.), ((0, 160), (0, 0)))
    metadata = ImagePreparation((height, width), (640, 640), (640. / width, 480. / height),
        (0, 0, 0, 160), original.value_range, 'minmax-uint8-demo-gray-v1', 1)
    return prepared, metadata


def matchanything_points_to_original(points: NDArray[np.float64], preparation: ImagePreparation
                                     ) -> NDArray[np.float64]:
    """Authors' half-pixel centre mapping, including separate X/Y resize factors."""
    values = np.asarray(points, dtype=np.float64)
    scales = np.asarray(preparation.scale_xy, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2 or not np.isfinite(scales).all() or np.any(scales <= 0):
        raise ValueError('Nieprawidłowe punkty lub skala wejścia MatchAnything.')
    return np.asarray((values - preparation.padding_ltrb[:2] + .5) / scales - .5, dtype=np.float64)


class MatchAnythingEngine(Protocol):
    """Local external model; masks derive from each model input's unpadded shape."""
    def match(self, reference: NDArray[np.float32], moving: NDArray[np.float32], *,
              reference_shape: tuple[int, int], moving_shape: tuple[int, int]
              ) -> tuple[NDArray[np.float64], NDArray[np.float64]]: ...

    def close(self) -> None: ...


class MatchAnythingBackend:
    def __init__(self, engine: MatchAnythingEngine, *, device: str,
                 provenance: tuple[tuple[str, str], ...],
                 config: CorrespondenceConfig = CorrespondenceConfig(),
                 cancelled: Callable[[], bool] | None = None) -> None:
        self._engine: MatchAnythingEngine | None = engine
        self.device, self.provenance, self.config = device, provenance, config
        self._cancelled = cancelled
        self.last_diagnostics: CorrespondenceDiagnostics | None = None
        self.settings_text = ('MatchAnything-ELoFTR; preset biblioteki autorów hf-match-images-preset-v1; '
                              'FP32; próg 0,001; min/max → uint8; AREA/LINEAR 640×480; '
                              'PIL szarość, kwadrat 640×640 z maską; NPE 832×832; '
                              'translation-consensus-v2; poparcie nie jest prawdopodobieństwem dryfu; '
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
            raise RegistrationError('MatchAnything-ELoFTR: zadanie zakończone; model zwolniony.')
        preparations: tuple[ImagePreparation, ...] = ()
        try:
            reference, rp = prepare_matchanything_image(reference_frame)
            moving, mp = prepare_matchanything_image(moving_frame)
            preparations = (rp, mp)
            self._checkpoint()
            p0, p1 = self._engine.match(reference, moving, reference_shape=(480, 640),
                                        moving_shape=(480, 640))
            self._checkpoint()
            evidence = estimate_correspondence_translation(
                matchanything_points_to_original(p0, rp), matchanything_points_to_original(p1, mp),
                rp.original_shape, mp.original_shape, config=self.config, cancelled=self._cancelled)
            evidence = replace(evidence, preparation=preparations, model_provenance=self.provenance)
            self.last_diagnostics = evidence
            assert evidence.final_shift_xy is not None
            return RegistrationFrameResult(moving_frame_index, evidence.final_shift_xy,
                                           MATCHANYTHING_METHOD, status=evidence.status)
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
            raise RegistrationError(f'MatchAnything-ELoFTR: {str(error) or type(error).__name__}') from error

    def close(self) -> None:
        engine, self._engine = self._engine, None
        if engine is not None:
            engine.close()


def load_matchanything_backend(options: DeepMatcherOptions, *,
                               progress: Callable[[str], None] | None = None,
                               cancelled: Callable[[], bool] | None = None) -> MatchAnythingBackend:
    """Validate pinned artifacts before deserializing weights or importing vendor code."""
    from hashlib import sha256
    from importlib.metadata import PackageNotFoundError, version
    from stmviewer.registration import RegistrationCancelled, RegistrationError

    def report(text: str) -> None:
        if cancelled is not None and cancelled():
            raise RegistrationCancelled
        if progress:
            progress(text)
        if cancelled is not None and cancelled():
            raise RegistrationCancelled

    options = replace(options, source=options.source.expanduser().resolve() if options.source else None,
                      weights=options.weights.expanduser().resolve() if options.weights else None)
    report('MatchAnything-ELoFTR: sprawdzanie lokalnych plików')
    reason = matchanything_unavailable_reason(options)
    if reason:
        raise RegistrationError(f'MatchAnything-ELoFTR: {reason}')
    source, weights = options.source, options.weights
    assert source is not None and weights is not None
    engine = None
    try:
        digest = sha256()
        for file in sorted((path for path in source.rglob('*') if path.is_file()
                            and '__pycache__' not in path.parts and '.git' not in path.parts),
                           key=lambda path: path.relative_to(source).as_posix()):
            report('MatchAnything-ELoFTR: sprawdzanie wersji kodu')
            relative = file.relative_to(source).as_posix()
            digest.update(f'{sha256(file.read_bytes()).hexdigest()}  {relative}\n'.encode('utf-8'))
        if digest.hexdigest() != SOURCE_SHA256:
            raise ValueError(f'Niezgodny kod MatchAnything; wymagany commit {SOURCE_COMMIT}.')
        digest = sha256()
        with weights.open('rb') as stream:
            while block := stream.read(1024 * 1024):
                report('MatchAnything-ELoFTR: sprawdzanie SHA-256 wag')
                digest.update(block)
        if digest.hexdigest() != WEIGHTS_SHA256:
            raise ValueError('Niezgodna suma SHA-256 wag MatchAnything-ELoFTR.')
        from stmviewer.matchanything_runtime import TorchMatchAnythingRuntime
        engine = TorchMatchAnythingRuntime(source, weights, options.device, report)
        provenance = {
            'model': MATCHANYTHING_LABEL, 'source_path': str(source), 'source_commit': SOURCE_COMMIT,
            'source_sha256': SOURCE_SHA256, 'source_license': 'HF source Apache-2.0; upstream GitHub PRL v1.0',
            'weights_path': str(weights), 'weights_sha256': WEIGHTS_SHA256,
            'weights_variant': 'matchanything_eloftr.ckpt', 'weights_license': 'see upstream distribution',
            'requested_device': options.device, 'actual_device': engine.device, 'precision': 'FP32',
            'model_config': 'configs/models/eloftr_model.py', 'model_threshold': '0.001',
            'position_encoding': 'NPE 832,832,832,832',
            'runtime': 'isolated namespace; eval; no reparameterization',
            'inference_policy': 'hf-match-images-preset-v1',
            'inference_source': 'imcui/hloc/match_dense.py:confs[matchanything_eloftr],match_images',
            'coordinate_mapping': '(model_xy + 0.5) / scale_xy - 0.5',
            'preprocessing': 'minmax-uint8-demo-gray-v1; max832 then force640x480 AREA-or-LINEAR; PIL gray; square640 masks',
            'aggregation': 'translation-consensus-v2',
        }
        for name in ('torch', 'numpy', 'einops', 'kornia', 'yacs', 'loguru', 'opencv-python', 'Pillow'):
            try:
                provenance['library_' + name] = version(name)
            except PackageNotFoundError:
                provenance['library_' + name] = 'unavailable'
        report('MatchAnything-ELoFTR: model załadowany')
        return MatchAnythingBackend(engine, device=engine.device, provenance=tuple(sorted(provenance.items())),
                                    cancelled=cancelled)
    except (RegistrationCancelled, RegistrationError):
        if engine is not None:
            engine.close()
        raise
    except Exception as error:
        if engine is not None:
            engine.close()
        report('MatchAnything-ELoFTR: błąd przygotowania')
        raise RegistrationError(f'MatchAnything-ELoFTR: {str(error) or type(error).__name__}') from error
