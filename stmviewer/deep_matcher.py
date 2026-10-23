"""Local-only LoFTR adapter injected into NanoTrack's unchanged translation estimator."""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from importlib.util import find_spec

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from stmviewer.registration import ShiftBackend


@dataclass(frozen=True)
class DeepMatcherOptions:
    weights: Path | None = None
    device: str = 'auto'


@dataclass(frozen=True)
class LoadedDeepMatcher:
    backend: 'ShiftBackend'
    device: str


def deep_unavailable_reason(options: DeepMatcherOptions) -> str | None:
    """Cheap preflight only; loading is verified separately in the worker."""
    if options.device not in ('auto', 'cpu', 'cuda'):
        return 'Nieznane urządzenie; wybierz Auto, CPU lub CUDA.'
    if options.weights is None:
        return 'Wskaż lokalny plik wag LoFTR outdoor (.ckpt).'
    try:
        if not options.weights.is_file():
            return f'Nie znaleziono pliku wag: {options.weights}'
        for name in ('torch', 'kornia'):
            if find_spec(name) is None:
                return f'Brak biblioteki {name}; zainstaluj zależności Deep Matcher.'
    except (OSError, ImportError, ValueError) as error:
        return str(error)
    return None


def load_deep_backend(options: DeepMatcherOptions, *,
                      progress: Callable[[str], None] | None = None,
                      cancelled: Callable[[], bool] | None = None) -> LoadedDeepMatcher:
    from stmviewer.registration import RegistrationCancelled, RegistrationError

    def report(text: str) -> None:
        if cancelled is not None and cancelled():
            raise RegistrationCancelled
        if progress is not None:
            progress(text)
        if cancelled is not None and cancelled():
            raise RegistrationCancelled

    stage = 'Sprawdzanie bibliotek i urządzenia'
    report(stage)
    reason = deep_unavailable_reason(options)
    if reason:
        raise RegistrationError(f'Deep Matcher: {reason}')
    try:
        import torch
        from kornia.feature import LoFTR
        from nanotrack.registration import DeepMatcherTranslationBackend

        device_name = options.device
        if device_name == 'auto':
            device_name = 'cuda' if torch.cuda.is_available() else 'cpu'
        if device_name == 'cuda' and not torch.cuda.is_available():
            raise RuntimeError('CUDA jest niedostępna w tym środowisku Torch.')
        device = torch.device('cuda', torch.cuda.current_device()) if device_name == 'cuda' else torch.device('cpu')
        if device.type == 'cuda':
            torch.ones(1, device=device).sum().item()  # Verify actual execution, not just hardware presence.
        stage = 'Wczytywanie wag lokalnych'
        report(stage)
        checkpoint = torch.load(options.weights, map_location='cpu', weights_only=True)
        stage = 'Sprawdzanie zgodności wag LoFTR'
        report(stage)
        model = LoFTR(pretrained=None)
        model.load_state_dict(checkpoint['state_dict'], strict=True)
        stage = f'Uruchamianie modelu na {str(device).upper()}'
        report(stage)
        model = model.eval().to(device)
        matcher = _LocalLoFTR(model, torch, str(device))
        label = 'CPU' if device.type == 'cpu' else f'CUDA:{device.index} — {torch.cuda.get_device_name(device)}'
        report(f'Deep Matcher: {label}')
        return LoadedDeepMatcher(DeepMatcherTranslationBackend(matcher=matcher), label)
    except RegistrationCancelled:
        raise
    except Exception as error:
        if cancelled is not None and cancelled():
            raise RegistrationCancelled from error
        raise RegistrationError(f'Deep Matcher — {stage}: {str(error) or type(error).__name__}') from error


class _LocalLoFTR:
    def __init__(self, model: Any, torch: Any, device: str) -> None:
        self._model = model
        self._torch = torch
        self._device = device

    def match(self, reference_frame: NDArray[np.float32], moving_frame: NDArray[np.float32]
              ) -> dict[str, NDArray[np.float64]]:
        with self._torch.no_grad():
            output = self._model({'image0': self._tensor(reference_frame),
                                  'image1': self._tensor(moving_frame)})
        return {key: np.asarray(output[key].detach().cpu().numpy(), dtype=np.float64)
                for key in ('keypoints0', 'keypoints1', 'confidence') if key in output}

    def _tensor(self, frame: NDArray[np.float32]) -> Any:
        values = np.asarray(frame, dtype=np.float32)
        low, high = float(np.min(values)), float(np.max(values))
        normalized = (values - low) / max(high - low, float(np.finfo(np.float32).eps))
        return self._torch.from_numpy(normalized[None, None, :, :]).float().to(self._device)
