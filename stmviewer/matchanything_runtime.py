"""Pinned MatchAnything inference in an isolated namespace, without training wrappers."""

from collections.abc import Callable
import gc
import importlib
from pathlib import Path
import sys
from typing import Any
from uuid import uuid4

import numpy as np
from numpy.typing import NDArray

from stmviewer.efficient_runtime import _SourceFinder


class TorchMatchAnythingRuntime:
    """One loaded checkpoint with the fixed inference preset published by the authors."""

    def __init__(self, source: Path, weights: Path, requested_device: str,
                 report: Callable[[str], None]) -> None:
        self._namespace = '_stmviewer_matchanything_' + uuid4().hex
        self._finder = _SourceFinder(self._namespace, source)
        self._model: Any = None
        self._torch: Any = None
        self._device = 'cpu'
        self.device = 'CPU'
        try:
            report('MatchAnything-ELoFTR: sprawdzanie urządzenia')
            torch = importlib.import_module('torch')
            self._torch = torch
            device = requested_device
            if device == 'auto':
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
            if device not in ('cpu', 'cuda'):
                raise ValueError('Nieznane urządzenie MatchAnything-ELoFTR.')
            if device == 'cuda':
                if not torch.cuda.is_available():
                    raise RuntimeError('CUDA jest niedostępna w tym środowisku Torch.')
                index = torch.cuda.current_device()
                self._device = f'cuda:{index}'
                torch.ones(1, device=self._device).sum().item()
                self.device = f'CUDA:{index} — {torch.cuda.get_device_name(index)}'
            sys.meta_path.insert(0, self._finder)
            defaults = importlib.import_module(self._namespace + '.config.default')
            # The pinned config's only absolute src import is rebound to this model's
            # namespace. Never install or replace a global src package or sys.path entry.
            path = source / 'configs/models/eloftr_model.py'
            text = path.read_text(encoding='utf-8')
            original = 'from src.config.default import _CN as cfg'
            if text.count(original) != 1:
                raise ValueError('Niezgodny import konfiguracji MatchAnything.')
            text = text.replace(original, f'from {self._namespace}.config.default import _CN as cfg')
            exec(compile(text, str(path), 'exec'), {})
            config = defaults.get_cfg_defaults()
            config.LOFTR.FP16 = False
            config.LOFTR.MATCH_COARSE.THR = 0.001
            config.LOFTR.COARSE.NPE = [832, 832, 832, 832]
            upstream = importlib.import_module(self._namespace + '.loftr')
            report('MatchAnything-ELoFTR: wczytywanie lokalnego checkpointu')
            if torch.serialization.get_unsafe_globals_in_checkpoint(weights):
                raise ValueError('Checkpoint MatchAnything zawiera nieobsługiwane metadane.')
            checkpoint = torch.load(weights, map_location='cpu', weights_only=True)
            if not isinstance(checkpoint, dict) or set(checkpoint) != {'state_dict'}:
                raise ValueError('Nieprawidłowy format checkpointu MatchAnything.')
            self._model = upstream.LoFTR(config=_lower_config(config.LOFTR))
            self._model.load_state_dict(checkpoint['state_dict'], strict=True)
            del checkpoint
            report(f'MatchAnything-ELoFTR: uruchamianie na {self.device}')
            self._model = self._model.eval().to(self._device)
        except BaseException:
            self.close()
            raise

    def match(self, reference: NDArray[np.float32], moving: NDArray[np.float32], *,
              reference_shape: tuple[int, int], moving_shape: tuple[int, int]
              ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        if self._model is None:
            raise RuntimeError('Model MatchAnything-ELoFTR został zwolniony.')
        if reference.ndim != 2 or reference.shape != moving.shape:
            raise ValueError('MatchAnything-ELoFTR wymaga zgodnych wymiarów obrazów pary.')
        if reference.shape != (640, 640) or reference_shape != (480, 640) or moving_shape != (480, 640):
            raise ValueError('MatchAnything wymaga przygotowania zgodnego z presetem 640×480 w kwadracie 640×640.')
        batch: dict[str, Any] = {}
        try:
            for index, (image, original) in enumerate(((reference, reference_shape), (moving, moving_shape))):
                if (len(original) != 2 or min(original) < 1
                        or any(length > limit for length, limit in zip(original, image.shape))):
                    raise ValueError('Nieprawidłowa geometria ważnych próbek MatchAnything.')
                batch[f'image{index}'] = self._torch.from_numpy(image[None, None]).to(self._device)
                # Same nearest-neighbour coarse-mask convention as the authors' adapter.
                # The final original-pixel consensus also excludes refined points outside it.
                mask = ((np.arange(0, image.shape[0], 8)[:, None] < original[0])
                        & (np.arange(0, image.shape[1], 8)[None, :] < original[1]))
                batch[f'mask{index}'] = self._torch.from_numpy(mask[None]).to(self._device)
            with self._torch.inference_mode():
                self._model(batch)
            p0, p1 = (np.asarray(batch[name].detach().cpu().numpy(), dtype=np.float64)
                      for name in ('mkpts0_f', 'mkpts1_f'))
            return p0, p1
        finally:
            batch.clear()

    def close(self) -> None:
        self._model = None
        if self._finder in sys.meta_path:
            sys.meta_path.remove(self._finder)
        for name in list(sys.modules):
            if name == self._namespace or name.startswith(self._namespace + '.'):
                del sys.modules[name]
        gc.collect()
        if self._torch is not None and self._device.startswith('cuda'):
            self._torch.cuda.empty_cache()


def _lower_config(value: Any) -> Any:
    if isinstance(value, dict):
        return {key.lower(): _lower_config(item) for key, item in value.items()}
    return value
