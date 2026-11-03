"""Optional Torch/upstream boundary: explicit local imports, no global ``src`` package."""

from collections.abc import Callable
from copy import deepcopy
import gc
import importlib
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec, SourceFileLoader
from importlib.util import spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType
from typing import Any
from uuid import uuid4

import numpy as np
from numpy.typing import NDArray


class _SourceOnlyLoader(SourceFileLoader):
    def get_code(self, fullname: str) -> Any:
        # A checkpointed .py tree must not execute an unrelated cached .pyc.
        return compile(self.get_data(self.path), self.path, 'exec', dont_inherit=True)


class _SourceFinder(MetaPathFinder):
    def __init__(self, namespace: str, source: Path) -> None:
        self.namespace, self.source = namespace, source / 'src'

    def find_spec(self, fullname: str, path: Any = None,
                  target: ModuleType | None = None) -> ModuleSpec | None:
        if fullname != self.namespace and not fullname.startswith(self.namespace + '.'):
            return None
        relative = fullname[len(self.namespace):].lstrip('.').split('.')
        location = self.source.joinpath(*relative) if relative != [''] else self.source
        if location.is_dir():
            initial = location / '__init__.py'
            if not initial.is_file():
                spec = ModuleSpec(fullname, loader=None, is_package=True)
                spec.submodule_search_locations = [str(location)]
                return spec
            return spec_from_file_location(fullname, initial,
                                           loader=_SourceOnlyLoader(fullname, str(initial)),
                                           submodule_search_locations=[str(location)])
        filename = location.with_suffix('.py')
        if filename.is_file():
            return spec_from_file_location(fullname, filename,
                                           loader=_SourceOnlyLoader(fullname, str(filename)))
        return None


class TorchEfficientRuntime:
    def __init__(self, source: Path, weights: Path, requested_device: str,
                 report: Callable[[str], None]) -> None:
        self._namespace = '_stmviewer_eloftr_' + uuid4().hex
        self._finder = _SourceFinder(self._namespace, source)
        self._model: Any = None
        self._torch: Any = None
        self._device = 'cpu'
        self.device = 'CPU'
        try:
            report('EfficientLoFTR: sprawdzanie bibliotek i urządzenia')
            torch = importlib.import_module('torch')
            self._torch = torch
            device = requested_device
            if device == 'auto':
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
            if device == 'cuda' and not torch.cuda.is_available():
                raise RuntimeError('CUDA jest niedostępna w tym środowisku Torch.')
            if device == 'cuda':
                index = torch.cuda.current_device()
                self._device = f'cuda:{index}'
                torch.ones(1, device=self._device).sum().item()
                self.device = f'CUDA:{index} — {torch.cuda.get_device_name(index)}'
            sys.meta_path.insert(0, self._finder)
            upstream = importlib.import_module(self._namespace + '.loftr')
            lightning = importlib.import_module('pytorch_lightning.callbacks.model_checkpoint')
            report('EfficientLoFTR: wczytywanie lokalnego checkpointu')
            unsafe = torch.serialization.get_unsafe_globals_in_checkpoint(weights)
            expected = 'pytorch_lightning.callbacks.model_checkpoint.ModelCheckpoint'
            if set(unsafe) != {expected}:
                raise ValueError('Niezgodne metadane checkpointu EfficientLoFTR.')
            with torch.serialization.safe_globals([lightning.ModelCheckpoint]):
                checkpoint = torch.load(weights, map_location='cpu', weights_only=True)
            self._model = upstream.LoFTR(config=deepcopy(upstream.full_default_cfg))
            self._model.load_state_dict(checkpoint['state_dict'], strict=True)
            del checkpoint
            self._model = upstream.reparameter(self._model).eval()
            report(f'EfficientLoFTR: uruchamianie na {self.device}')
            self._model = self._model.to(self._device)
            report(f'EfficientLoFTR: gotowy — {self.device}')
        except BaseException:
            self.close()
            raise

    def match(self, reference: NDArray[np.float32], moving: NDArray[np.float32]
              ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        if self._model is None:
            raise RuntimeError('Model EfficientLoFTR został zwolniony.')
        batch = {
            'image0': self._torch.from_numpy(reference[None, None]).to(self._device),
            'image1': self._torch.from_numpy(moving[None, None]).to(self._device),
        }
        try:
            with self._torch.inference_mode():
                self._model(batch)
            points = tuple(np.asarray(batch[key].detach().cpu().numpy(), dtype=np.float64)
                           for key in ('mkpts0_f', 'mkpts1_f'))
            return points[0], points[1]
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
